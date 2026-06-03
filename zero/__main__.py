import sys
from zero.orchestrator import Orchestrator

def main():
    orch = Orchestrator()
    if "--text" in sys.argv:        # dev mode: type instead of speak
        import asyncio
        while True:
            t = input("you> ").strip()
            if t in ("exit", "quit"): break
            print("zero>", asyncio.run(orch.brain.ask_text(t)))
    else:
        orch.run()

if __name__ == "__main__":
    main()
