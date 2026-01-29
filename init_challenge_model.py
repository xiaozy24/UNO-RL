import torch
import torch.nn as nn
import numpy as np
import sys
import os

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rl_model import UNOAgent
from rl_agent import RLAgentHandler
from train_challenge_backend import ChallengeBackend

def init_weights(m):
    if isinstance(m, nn.Linear):
        torch.nn.init.xavier_uniform_(m.weight)
        if m.bias is not None:
             m.bias.data.fill_(0.01)

def main():
    print("Initializing Model for +4 Challenge Training...")
    model = UNOAgent()
    model.apply(init_weights)
    
    # Specific initialization for challenge_head to achieve ~0.3 probability
    # Head has 2 outputs. We want Softmax(out)[1] ~= 0.3
    # We set weights to very small random values (noise) and biases specific.
    # bias[0] = 0, bias[1] = ln(0.3/0.7) ~= -0.8473
    
    with torch.no_grad():
        model.challenge_head.weight.fill_(0.0) # Zero out influence of input for now to ensure 0.3 base
        # Or keep small random weights so it learns?
        # "Model in initial parameters should perform as 0.3 probability"
        # If I zero weights, it is exactly 0.3 everywhere.
        # But then gradients might be stuck if inputs don't matter?
        # No, gradients will flow back to weights.
        torch.nn.init.normal_(model.challenge_head.weight, mean=0.0, std=0.01)
        
        model.challenge_head.bias[0] = 0.0
        model.challenge_head.bias[1] = np.log(0.3/0.7)
        
    save_path = "challenge_model_init.pth"
    torch.save(model.state_dict(), save_path)
    print(f"Model saved to {save_path}")
    
    # Verification
    print("Verifying initial performance (Target: ~30% challenge rate)...")
    agent_handler = RLAgentHandler(save_path)
    agent_handler.is_train = True # Use probabilistic sampling
    
    trainer = ChallengeBackend(agent_handler)
    
    for i in range(1000):
        if (i+1) % 100 == 0:
            print(f"Game {i+1}...")
        trainer.run_game()
        
    stats = trainer.stats
    challenge_rate = stats["challenge_attempts"] / stats["total"] if stats["total"] > 0 else 0
    
    print(f"Verification Results over {stats['games']} games:")
    print(f"Total Decisions: {stats['total']}")
    print(f"Challenge Attempts: {stats['challenge_attempts']}")
    print(f"Challenge Rate: {challenge_rate:.4f}")
    
    if 0.25 <= challenge_rate <= 0.35:
        print("SUCCESS: Initial Challenge Rate is approximately 0.3.")
    else:
        print("WARNING: Challenge Rate deviates from 0.3.")

if __name__ == "__main__":
    main()
