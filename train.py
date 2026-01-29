import sys
import os
import torch
import csv
import time
import random
from collections import defaultdict

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.game_manager import GameManager
from backend.player import Player
from config.enums import PlayerType
from rl_agent import RLAgentHandler
from train_backend import run_game_epoch

class ReplayBuffer:
    def __init__(self, capacity=100000):
        self.capacity = capacity
        self.buffer = []
        self.position = 0

    def push(self, transitions):
        for t in transitions:
            if len(self.buffer) < self.capacity:
                self.buffer.append(None)
            self.buffer[self.position] = t
            self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        return random.sample(self.buffer, batch_size)

    def __len__(self):
        return len(self.buffer)

def train():
    print("Starting UNO RL Training (Experience Replay + Revised Rewards)...")
    model_path = "uno_rl_model.pth"
    agent = RLAgentHandler(model_path if os.path.exists(model_path) else None)
    agent.is_train = True
    agent.model.train() 
    
    # Use 1e-4 as it is safer than 1e-1
    optimizer = torch.optim.Adam(agent.model.parameters(), lr=1e-4)
    loss_fn = torch.nn.MSELoss()
    
    log_file_1000 = "train_log_1000.csv"
    log_file_50000 = "train_log_50000.csv"
    
    # Ensure headers exists
    for f in [log_file_1000, log_file_50000]:
        if not os.path.exists(f):
            with open(f, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Time", "Wins", "Total", "WinRate"])
                
    total_games = 0
    wins_1000 = 0
    wins_50000 = 0
    
    replay_buffer = ReplayBuffer(capacity=100000)
    BATCH_SIZE = 4096
    
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
            
            # Revised Reward Structure
            reward = 1.0 if won else -0.33
            
            # Penalize remaining cards if lost
            rl_player = [p for p in gm.players if p.player_type == PlayerType.RL][0]
            if not won:
                reward -= len(rl_player.hand) * 0.05
            
            # Collect transitions from this game
            game_transitions = []
            for step in agent.history:
                # Challenge specific reward logic could go here if needed.
                # For now, apply global outcome reward to all steps.
                step_reward = reward
                
                game_transitions.append({
                    "state": step["state"],
                    "head": step["head"],
                    "action": step["action"],
                    "target": torch.tensor([step_reward], dtype=torch.float32)
                })
            
            replay_buffer.push(game_transitions)
                
            if won:
                wins_1000 += 1
                wins_50000 += 1
            
            # Train every 100 games
            if total_games % 100 == 0:
                if len(replay_buffer) >= BATCH_SIZE:
                    optimizer.zero_grad()
                    
                    batch_items = replay_buffer.sample(BATCH_SIZE)
                    
                    grouped = defaultdict(list)
                    for t in batch_items:
                        grouped[t["head"]].append(t)
                        
                    losses = []
                    for head, items in grouped.items():
                        if not items: continue
                        states = torch.cat([x["state"] for x in items], dim=0)
                        targets = torch.cat([x["target"] for x in items], dim=0)
                        
                        all_outputs = agent.model(states)
                        head_outputs = all_outputs[head]
                        
                        actions = torch.tensor([x["action"] for x in items], dtype=torch.long).unsqueeze(1)
                        # No sigmoid, pure linear output to predict Q-value (unbounded reward sum)
                        preds = head_outputs.gather(1, actions).squeeze(1)
                        
                        losses.append(loss_fn(preds, targets))
                        
                    if losses:
                        total_loss = sum(losses)
                        total_loss.backward()
                        optimizer.step()
                        
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
