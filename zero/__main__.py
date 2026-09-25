import sys


def main():
    if "--app" in sys.argv:         # macOS menu-bar app (what Zero.app runs)
        from zero.app import main as app_main
        return app_main()
    if "--window" in sys.argv:      # native HUD window (spawned by the menu bar)
        from zero.window import main as window_main
        return window_main()
    from zero.orchestrator import Orchestrator
    orch = Orchestrator()
    if "--text" in sys.argv:        # dev mode: type instead of speak
        while True:
            t = input("you> ").strip()
            if t in ("exit", "quit"): break
            print("zero>", orch.brain.ask(t))
    else:
        orch.run()

if __name__ == "__main__":
    main()
