import sys
import os
import csv
import datetime
import torch

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rl_agent import RLAgentHandler
from train_challenge_backend import ChallengeBackend

def main():
    print("Starting Evaluation (10000 games)...")
    
    model_path = "challenge_model_latest.pth"
    if not os.path.exists(model_path):
        model_path = "challenge_model_init.pth"
        if not os.path.exists(model_path):
            print("No model found. Please run init or train script first.")
            return
            
    print(f"Loading model from {model_path}")
    agent = RLAgentHandler(model_path)
    agent.is_train = False # Deterministic mode
    
    trainer = ChallengeBackend(agent)
    
    f = open("challenge_eval.csv", "w", newline='')
    writer = csv.writer(f)
    writer.writerow(["Time", "Correct", "Total", "Accuracy", "WinRate", "ChallengeRate"])
    
    total_games = 10000
    
    for i in range(total_games):
        trainer.run_game()
        if (i+1) % 1000 == 0:
            s = trainer.stats
            acc = s["correct"]/s["total"] if s["total"]>0 else 0
            print(f"Progress {i+1}/{total_games} - Acc: {acc:.2%}")
            
    s = trainer.stats
    acc = s["correct"]/s["total"] if s["total"]>0 else 0
    wr = s["wins"]/s["games"]
    cr = s["challenge_attempts"]/s["total"] if s["total"]>0 else 0
    
    writer.writerow([datetime.datetime.now(), s["correct"], s["total"], f"{acc:.4f}", f"{wr:.4f}", f"{cr:.4f}"])
    f.close()
    
    print("Evaluation Complete.")
    print(f"Final Accuracy: {acc:.4f}")
    print(f"Final Win Rate: {wr:.4f}")
    print(f"Challenge Rate: {cr:.4f}")

if __name__ == "__main__":
    main()
