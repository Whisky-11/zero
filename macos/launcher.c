/*
 * Zero.app launcher — the app bundle's main executable.
 *
 * Why a native launcher instead of py2app: macOS grants privacy permissions
 * (Microphone, Accessibility, Screen Recording, Automation) to the *responsible*
 * process — the app the user launched. A child process inherits that
 * responsibility (like programs started from Terminal), so running the venv's
 * Python as a CHILD of this signed bundle makes every prompt say "Zero" and every
 * grant stick to com.ahmad.zero, while the Python code keeps running straight
 * from the repo (edit + restart, no rebuild).
 *
 * It: cds to the repo, fixes PATH (launchd/Finder give a bare one, so the
 * `claude` CLI would not be found), unsets ANTHROPIC_API_KEY, runs
 * `.venv/bin/python -m zero --app`, forwards SIGTERM/SIGINT, and restarts the
 * child after a crash (at most 5 times in 10 minutes). Exit 0 = the user quit.
 */
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <signal.h>
#include <spawn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef ZERO_DIR
#error "build with -DZERO_DIR=\"/path/to/zero\" (see macos/build-app.sh)"
#endif

extern char **environ;
static volatile pid_t child = 0;
static volatile sig_atomic_t stopping = 0;

static void forward(int sig) {
    stopping = 1;
    if (child > 0) kill(child, sig);
}

static void app_path(char *out, size_t n) {
    /* .../Zero.app/Contents/MacOS/Zero -> .../Zero.app */
    char exe[PATH_MAX]; uint32_t sz = sizeof exe; char real[PATH_MAX];
    out[0] = 0;
    if (_NSGetExecutablePath(exe, &sz) != 0 || !realpath(exe, real)) return;
    for (int i = 0; i < 3; i++) { char *s = strrchr(real, '/'); if (!s) return; *s = 0; }
    snprintf(out, n, "%s", real);
}

int main(void) {
    const char *dir = getenv("ZERO_HOME");
    if (!dir || !*dir) dir = ZERO_DIR;
    if (chdir(dir) != 0) { fprintf(stderr, "Zero: cannot cd to %s: %s\n", dir, strerror(errno)); return 1; }

    char python[PATH_MAX];
    snprintf(python, sizeof python, "%s/.venv/bin/python", dir);
    if (access(python, X_OK) != 0) {
        fprintf(stderr, "Zero: %s missing — create the venv (see README, macOS setup)\n", python);
        char cmd[PATH_MAX + 256];
        snprintf(cmd, sizeof cmd, "/usr/bin/osascript -e 'display alert \"Zero can't start\" message "
                 "\"No Python venv at %s/.venv. Follow the macOS setup in the README.\"'", dir);
        system(cmd);
        return 1;
    }

    const char *home = getenv("HOME"); if (!home) home = "";
    const char *old = getenv("PATH"); if (!old) old = "";
    char path[8192];
    snprintf(path, sizeof path,
             "%s/.local/bin:%s/.claude/local:%s/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:"
             "/usr/bin:/bin:/usr/sbin:/sbin:%s", home, home, home, old);
    setenv("PATH", path, 1);
    unsetenv("ANTHROPIC_API_KEY");     /* Zero bills the subscription, never the API */
    setenv("ZERO_HOME", dir, 1);
    setenv("PYTHONUNBUFFERED", "1", 1);
    char app[PATH_MAX]; app_path(app, sizeof app);
    if (app[0]) setenv("ZERO_APP_PATH", app, 1);

    char out_log[PATH_MAX], err_log[PATH_MAX];
    snprintf(out_log, sizeof out_log, "%s/zero.run.out.log", dir);
    snprintf(err_log, sizeof err_log, "%s/zero.run.err.log", dir);

    struct sigaction sa; memset(&sa, 0, sizeof sa); sa.sa_handler = forward;
    sigaction(SIGTERM, &sa, NULL); sigaction(SIGINT, &sa, NULL); sigaction(SIGHUP, &sa, NULL);

    char *argv[] = { python, "-m", "zero", "--app", NULL };
    time_t crashes[5] = {0}; int ci = 0;
    for (;;) {
        posix_spawn_file_actions_t fa;
        posix_spawn_file_actions_init(&fa);
        posix_spawn_file_actions_addopen(&fa, 1, out_log, O_WRONLY | O_CREAT | O_APPEND, 0644);
        posix_spawn_file_actions_addopen(&fa, 2, err_log, O_WRONLY | O_CREAT | O_APPEND, 0644);
        pid_t pid;
        int rc = posix_spawn(&pid, python, &fa, NULL, argv, environ);
        posix_spawn_file_actions_destroy(&fa);
        if (rc != 0) { fprintf(stderr, "Zero: spawn failed: %s\n", strerror(rc)); return 1; }
        child = pid;

        int status = 0;
        while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
        child = 0;
        if (stopping) return 0;
        if (WIFEXITED(status) && WEXITSTATUS(status) == 0) return 0;   /* Quit Zero */
        /* terminated on purpose (pkill, logout) — a crash is SIGSEGV/SIGABRT/SIGKILL/exit!=0 */
        if (WIFSIGNALED(status) && (WTERMSIG(status) == SIGTERM || WTERMSIG(status) == SIGINT)) return 0;

        /* crashed: restart, unless it keeps crashing (5 in 10 minutes) */
        time_t now = time(NULL);
        if (crashes[ci] && now - crashes[ci] < 600) {
            system("/usr/bin/osascript -e 'display notification \"Zero keeps crashing — "
                   "see zero.run.err.log\" with title \"Zero\"'");
            return 1;
        }
        crashes[ci] = now; ci = (ci + 1) % 5;
        sleep(5);
        if (stopping) return 0;
    }
}
