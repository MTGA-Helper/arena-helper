# ==============================================================================
# Script Name: run_pipeline.py
# Accomplishment: Foolproof Python execution runner for the Deck Evidence Engine workflow.
# ==============================================================================

import argparse
import subprocess
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Arena Helper Evidence Engine Pipeline")
    parser.add_argument("--action", default="generate", choices=["generate", "log"], help="Action to perform")
    parser.add_argument("--deck", default="MWA-001", help="Benchmark ID")
    parser.add_argument("--result", default="WIN", choices=["WIN", "LOSS"], help="Match result")
    parser.add_argument("--rank", default="Platinum", help="Ladder rank")
    parser.add_argument("--turns", type=int, default=7, help="Turn count")
    parser.add_argument("--opponent", default="Mono-Red", help="Opponent archetype")

    args = parser.parse_args()

    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    if args.action == "log":
        log_script = os.path.join(scripts_dir, "log_match.py")
        cmd = [
            sys.executable, log_script,
            "--deck", args.deck,
            "--result", args.result,
            "--rank", args.rank,
            "--turns", str(args.turns),
            "--opponent", args.opponent
        ]
        print(f"[+] Executing match log for {args.deck}...")
        subprocess.run(cmd)
    
    # Always generate/display the updated evidence card
    card_script = os.path.join(scripts_dir, "generate_evidence_card.py")
    print(f"[+] Generating Evidence Card for {args.deck}...")
    subprocess.run([sys.executable, card_script, args.deck])

if __name__ == "__main__":
    main()
