import sys
import os
import torch
import csv
import time
from collections import defaultdict

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.game_manager import GameManager
from backend.player import Player
from config.enums import PlayerType
from rl_agent import RLAgentHandler
from train_backend import run_game_epoch

def train():
    print("Starting UNO RL Training...")
    model_path = "uno_rl_model.pth"
    agent = RLAgentHandler(model_path if os.path.exists(model_path) else None)
    agent.is_train = True
    agent.model.train() 
    
    optimizer = torch.optim.Adam(agent.model.parameters(), lr=1e-1)
    loss_fn = torch.nn.MSELoss()
    
    log_file_1000 = "train_log_1000.csv"
    log_file_50000 = "train_log_50000.csv"
    
    for f in [log_file_1000, log_file_50000]:
        if not os.path.exists(f):
            with open(f, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Time", "Wins", "Total", "WinRate"])
                
    total_games = 0
    wins_1000 = 0
    wins_50000 = 0
    
    batch_transitions = [] 
    
    try:
        while True:
            # Create Game: 1 RL vs 3 SimpleAI
            p1 = Player(0, "RL", PlayerType.RL)
            p2 = Player(1, "S1", PlayerType.AI)
            p3 = Player(2, "S2", PlayerType.AI)
            p4 = Player(3, "S3", PlayerType.AI)
            gm = GameManager([p1, p2, p3, p4])
            
            agent.clear_history()
            won = run_game_epoch(gm, agent)
            total_games += 1
            
            reward = 1.0 if won else 0.0
            
            for step in agent.history:
                batch_transitions.append({
                    "state": step["state"],
                    "head": step["head"],
                    "action": step["action"],
                    "target": torch.tensor([reward], dtype=torch.float32)
                })
                
            if won:
                wins_1000 += 1
                wins_50000 += 1
                
            if total_games % 100 == 0:
                optimizer.zero_grad()
                
                grouped = defaultdict(list)
                for t in batch_transitions:
                    grouped[t["head"]].append(t)
                    
                losses = []
                for head, items in grouped.items():
                    if not items: continue
                    states = torch.cat([x["state"] for x in items], dim=0)
                    targets = torch.cat([x["target"] for x in items], dim=0)
                    
                    all_outputs = agent.model(states)
                    head_outputs = all_outputs[head]
                    
                    actions = torch.tensor([x["action"] for x in items], dtype=torch.long).unsqueeze(1)
                    # Get predicted values for the specific actions taken
                    preds = torch.sigmoid(head_outputs).gather(1, actions).squeeze(1)
                    
                    losses.append(loss_fn(preds, targets))
                    
                if losses:
                    total_loss = sum(losses)
                    total_loss.backward()
                    optimizer.step()
                    
                batch_transitions = []
                torch.save(agent.model.state_dict(), model_path)
                
            if total_games % 1000 == 0:
                tr_wins = wins_1000
                rate = tr_wins / 1000.0
                t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                print(f"[{t_str}] Games: {total_games}, Wins (last 1000): {tr_wins}, Rate: {rate:.2%}")
                with open(log_file_1000, 'a', newline='') as f:
                    csv.writer(f).writerow([t_str, tr_wins, 1000, rate])
                wins_1000 = 0
                
            if total_games % 50000 == 0:
                tr_wins = wins_50000
                rate = tr_wins / 50000.0
                t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                print(f"[{t_str}] Games: {total_games}, Wins (last 50000): {tr_wins}, Rate: {rate:.2%}")
                with open(log_file_50000, 'a', newline='') as f:
                    csv.writer(f).writerow([t_str, tr_wins, 50000, rate])
                wins_50000 = 0
                
    except KeyboardInterrupt:
        print("Training stopped by user.")

if __name__ == "__main__":
    train()
