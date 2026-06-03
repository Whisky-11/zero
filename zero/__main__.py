import sys
from zero.orchestrator import Orchestrator

def main():
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
