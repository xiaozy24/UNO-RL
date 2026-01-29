import torch
import os
import sys
import numpy as np

# Add path to ensure we can import backend/rl_utils modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rl_model import UNOAgent
from backend.game_manager import GameManager
from backend.player import Player
from config.enums import PlayerType
from rl_agent import RLAgentHandler
from train_backend import run_game_epoch

def init_and_verify():
    print("Initializing UNO RL Model Parameters...")
    model = UNOAgent()
    
    # Initialize weights to be small to ensure near-uniform probability initially (Random Policy)
    for p in model.parameters():
        if p.dim() > 1:
            # Use small gain to keep logits close to 0, ensuring sigmoid ~ 0.5
            torch.nn.init.xavier_uniform_(p, gain=0.01) 
        else:
            torch.nn.init.zeros_(p)
            
    # Save model to the location expected by train.py and evaluate.py
    # Assuming script is run from project root or UNO-RL folder, we stick to relative filename
    # used in those scripts: "uno_rl_model.pth"
    # To be safe, let's put it in the same directory as this script if we want it isolated,
    # but train.py uses "uno_rl_model.pth" in CWD. 
    # Let's write to CWD to match train.py behavior.
    
    model_path = "uno_rl_model.pth"
    torch.save(model.state_dict(), model_path)
    print(f"Model initialized and saved to {os.path.abspath(model_path)}")
    
    print("Verifying performance (target ~25%)...")
    
    # Load the agent with the model we just saved
    agent = RLAgentHandler(model_path)
    agent.is_train = False # Evaluation mode (Deterministic based on scores, but scores are random-ish)
    
    wins = 0
    total = 1000
    
    # Use deterministic seed for reproducibility of the check?
    # No, we want to measure average performance.
    
    print(f"Running {total} games against SimpleAI (First-Card Strategy)...")
    for i in range(total):
        p1 = Player(0, "RL", PlayerType.RL)
        p2 = Player(1, "S1", PlayerType.AI)
        p3 = Player(2, "S2", PlayerType.AI)
        p4 = Player(3, "S3", PlayerType.AI)
        gm = GameManager([p1, p2, p3, p4])
        
        if run_game_epoch(gm, agent):
            wins += 1
            
        if (i+1) % 100 == 0:
            print(f"Progress: {i+1}/{total}, Wins: {wins}")
            
    rate = wins / total
    print(f"Verification Complete. Wins: {wins}/{total}. Rate: {rate:.2%}")
    
    if 0.20 <= rate <= 0.30:
        print("SUCCESS: Win rate is within acceptable range (20%-30%).")
    else:
        print("WARNING: Win rate is outside expected range. This might be normal variance or indicate bias.")

if __name__ == "__main__":
    init_and_verify()
