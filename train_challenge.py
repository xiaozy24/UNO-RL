import torch
import torch.optim as optim
import torch.nn as nn
import numpy as np
import sys
import os
import csv
import datetime

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rl_model import UNOAgent
from rl_agent import RLAgentHandler
from train_challenge_backend import ChallengeBackend

def update_weights(model, optimizer, batch_data):
    if not batch_data:
        return
        
    # batch_data is list of dicts: {'state': tensor, 'action': int, 'reward': float}
    
    states = torch.cat([x['state'] for x in batch_data])
    actions = torch.tensor([x['action'] for x in batch_data], dtype=torch.long)
    rewards = torch.tensor([x['reward'] for x in batch_data], dtype=torch.float32)
    
    # Forward pass
    # We need to run forward pass on states to get current Q values
    # But backbone is frozen, so only head gradients matter.
    # However, we need the features.
    
    # model(states) returns dict of heads.
    # We only care about "challenge" head.
    
    model.train() # Set to train mode (though backbone signals are detached or requires_grad=False)
    
    outputs = model(states) 
    chal_logits = outputs["challenge"] # [Batch, 2]
    
    # Q-Learning Loss:
    # Q(s, a) should approach r
    # Gather the Q-values for the taken actions
    
    q_values = chal_logits.gather(1, actions.unsqueeze(1)).squeeze(1)
    
    # Loss = MSE(Q, r)
    loss = nn.MSELoss()(q_values, rewards)
    
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

def main():
    # Setup CSVs
    f1 = open("challenge_train_1k.csv", "w", newline='')
    writer1 = csv.writer(f1)
    writer1.writerow(["Time", "Games", "Correct", "Total", "Accuracy", "WinRate", "ChallengeRate"])
    
    f2 = open("challenge_train_50k.csv", "w", newline='')
    writer2 = csv.writer(f2)
    writer2.writerow(["Time", "Games", "Correct", "Total", "Accuracy", "WinRate", "ChallengeRate"])
    
    # Load Model (Create new if not exists, but we rely on init script)
    model_path = "challenge_model_init.pth"
    if not os.path.exists(model_path):
        print("Error: Run init_challenge_model.py first!")
        return

    agent = RLAgentHandler(model_path)
    agent.is_train = True
    
    # Freeze backbone
    for param in agent.model.parameters():
        param.requires_grad = False
    for param in agent.model.challenge_head.parameters():
        param.requires_grad = True
        
    optimizer = optim.Adam(agent.model.challenge_head.parameters(), lr=1e-3)
    
    trainer = ChallengeBackend(agent)
    
    # Trackers
    stats_1k = {"correct": 0, "total": 0, "wins": 0, "games": 0, "attempts": 0}
    stats_50k = {"correct": 0, "total": 0, "wins": 0, "games": 0, "attempts": 0}
    
    total_games_played = 0
    
    print("Starting +4 Challenge Training Loop...")
    
    try:
        while True:
            # Run 100 games batch for update
            agent.clear_history()
            
            for _ in range(100):
                trainer.reset_stats() # Reset the single-game stats
                trainer.run_game()
                
                # Accumulate
                s = trainer.stats
                for st in [stats_1k, stats_50k]:
                    st["correct"] += s["correct"]
                    st["total"] += s["total"]
                    st["wins"] += s["wins"]
                    st["games"] += s["games"]
                    st["attempts"] += s["challenge_attempts"]
                
                total_games_played += 1
                
                # 1k Logging
                if total_games_played % 1000 == 0:
                    acc = stats_1k["correct"] / stats_1k["total"] if stats_1k["total"] > 0 else 0
                    win_rate = stats_1k["wins"] / stats_1k["games"]
                    chal_rate = stats_1k["attempts"] / stats_1k["total"] if stats_1k["total"] > 0 else 0
                    
                    log_row = [
                        datetime.datetime.now(),
                        total_games_played,
                        stats_1k["correct"],
                        stats_1k["total"],
                        f"{acc:.4f}",
                        f"{win_rate:.4f}",
                        f"{chal_rate:.4f}"
                    ]
                    print(f"[1k Log] Game {total_games_played}: Acc={acc:.2%}, WR={win_rate:.2%}, ChRate={chal_rate:.2%}")
                    writer1.writerow(log_row)
                    f1.flush()
                    
                    stats_1k = {"correct": 0, "total": 0, "wins": 0, "games": 0, "attempts": 0}

                # 50k Logging (simulated, we might not reach it quickly, but logic is here)
                if total_games_played % 50000 == 0:
                    acc = stats_50k["correct"] / stats_50k["total"] if stats_50k["total"] > 0 else 0
                    win_rate = stats_50k["wins"] / stats_50k["games"]
                    chal_rate = stats_50k["attempts"] / stats_50k["total"] if stats_50k["total"] > 0 else 0
                    
                    log_row = [
                        datetime.datetime.now(),
                        total_games_played,
                        stats_50k["correct"],
                        stats_50k["total"],
                        f"{acc:.4f}",
                        f"{win_rate:.4f}",
                        f"{chal_rate:.4f}"
                    ]
                    print(f"[50k Log] Game {total_games_played}: Acc={acc:.2%}, WR={win_rate:.2%}")
                    writer2.writerow(log_row)
                    f2.flush()
                    
                    stats_50k = {"correct": 0, "total": 0, "wins": 0, "games": 0, "attempts": 0}

            # Update Parameters
            # Filter history for challenge steps
            challenge_data = [
                h for h in agent.history 
                if h.get("head") == "challenge" and h.get("reward") is not None
            ]
            
            if challenge_data:
                update_weights(agent.model, optimizer, challenge_data)
            
            # Save checkpoint occasionally
            if total_games_played % 5000 == 0:
                 torch.save(agent.model.state_dict(), f"challenge_model_{total_games_played}.pth")
                 torch.save(agent.model.state_dict(), "challenge_model_latest.pth")

    except KeyboardInterrupt:
        print("Training stopped.")
        f1.close()
        f2.close()

if __name__ == "__main__":
    main()
