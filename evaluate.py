import sys
import os
import csv
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.game_manager import GameManager
from backend.player import Player
from config.enums import PlayerType
from rl_agent import RLAgentHandler
from train_backend import run_game_epoch

def evaluate():
    print("Starting Evaluation...")
    model_path = "uno_rl_model.pth"
    # Even if model doesn't exist, we might evaluate the initialized random model if user wants base check.
    # But usually eval implies trained model.
    if not os.path.exists(model_path):
        print(f"Model {model_path} not found! EVALUATING RANDOM MODEL.")
        agent = RLAgentHandler(None)
    else:
        agent = RLAgentHandler(model_path)
    
    agent.is_train = False # Evaluation mode
    
    log_file = "evaluate_log.csv"
    if not os.path.exists(log_file):
        with open(log_file, 'w', newline='') as f:
            csv.writer(f).writerow(["Time", "WinRate", "Games"])
            
    total_games = 10000
    wins = 0
    
    start_t = time.time()
    print(f"Running {total_games} games...")
    for i in range(total_games):
        p1 = Player(0, "RL", PlayerType.RL)
        p2 = Player(1, "S1", PlayerType.AI)
        p3 = Player(2, "S2", PlayerType.AI)
        p4 = Player(3, "S3", PlayerType.AI)
        gm = GameManager([p1, p2, p3, p4])
        
        won = run_game_epoch(gm, agent)
        if won: wins += 1
        
        if (i+1) % 1000 == 0:
            print(f"Game {i+1}/{total_games}. Current Rate: {wins/(i+1):.2%}")
            
    rate = wins / total_games
    t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    
    print(f"Evaluation Complete. Rate: {rate:.2%}")
    with open(log_file, 'a', newline='') as f:
        csv.writer(f).writerow([t_str, rate, total_games])

if __name__ == "__main__":
    evaluate()
