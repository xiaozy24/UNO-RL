import logging
import time
import os
import sys
import random

# Add current directory to sys.path
sys.path.append(os.getcwd())

from backend.player import Player
from backend.rl_player import RLPlayer
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from backend.card import Card
from backend.utils.logger import game_logger

# Suppress Logs
logging.basicConfig(level=logging.ERROR)
if hasattr(game_logger, 'logger') and game_logger.logger:
    game_logger.logger.setLevel(logging.ERROR)
# Also disable propagation effectively if needed
game_logger.logger.propagate = False

def simple_ai_turn(gm, player):
    """
    Heuristic:
    1. Check legal plays.
    2. If legal, play first found (Wild -> Red).
    3. If not, draw.
    4. If drawn is legal, play it (Wild -> Red).
    """
    top_card = gm.deck.peek_discard_pile()
    legal = [c for c in player.hand if gm.check_legal_play(c, top_card)]
    
    if legal:
        c = legal[0]
        wc = None
        if c.color == CardColor.WILD:
            wc = CardColor.RED 
        gm.play_card(player, c, wc)
    else:
        drawn = gm.deck.draw_card()
        if drawn:
            player.add_card(drawn)
            if gm.check_legal_play(drawn, top_card):
                 wc = None
                 if drawn.color == CardColor.WILD:
                      wc = CardColor.RED
                 gm.play_card(player, drawn, wc)
            else:
                gm._advance_turn()
        else:
            gm._advance_turn()

def challenge_proxy(victim, previous_color, gm):
    if isinstance(victim, RLPlayer):
        return victim.challenge_decision(gm, previous_color)
    else:
        # Simple AI Random Challenge (30% chance)
        return random.random() < 0.3

def update_history_proxy(players, pid, card):
    for p in players:
        if isinstance(p, RLPlayer):
            p.update_history(card)

def run_evaluation(model_path, num_games=1000):
    wins = 0
    start_time = time.time()
    
    print(f"Starting evaluation...")
    print(f"Model: {model_path}")
    print(f"Total Games: {num_games}")
    print("-" * 30)
    
    # Pre-instantiate RL Player to load model once if possible?
    # RLPlayer constructor loads model. To simulate fresh state each game, 
    # we might want to reload or just reset history.
    # The history is in self.history (deque).
    # We should create a helper to reset the RL player state but keep the model.
    # But RLPlayer architecture tightly couples model and player.
    # Re-creating RLPlayer 1000 times means loading torch model 1000 times -> SLOW.
    
    # Optimized: precise setup
    p1 = RLPlayer(1, "RL_Agent", model_path=model_path, device='cpu')
    p2 = Player(2, "AI_2", PlayerType.AI)
    p3 = Player(3, "AI_3", PlayerType.AI)
    p4 = Player(4, "AI_4", PlayerType.AI)
    
    for i in range(num_games):
        # Reset Players for new game
        # Player class doesn't strictly need reset if we pass them fresh to GM 
        # BUT GM modifies player.hand. We need to clear hands.
        p1.hand = []
        p2.hand = []
        p3.hand = []
        p4.hand = []
        
        # Reset RL History
        if hasattr(p1, 'history'):
            p1.history.clear()
            
        players = [p1, p2, p3, p4]
        gm = GameManager(players)
        
        # Hooks
        # Challenge decision needs GM access
        gm.challenge_decider = lambda v, pc: challenge_proxy(v, pc, gm)
        
        # Animation/History Hook
        gm.on_play_card_animation = lambda pid, c: update_history_proxy(players, pid, c)
        
        # Start
        start_card = gm.start_game()
        p1.update_history(start_card)
        
        turns = 0
        while not gm.game_over and turns < 1000:
            turns += 1
            current_player = gm.get_current_player()
            
            # Say UNO
            if current_player.get_hand_size() == 2:
                current_player.say_uno()
            
            if current_player.player_id == 1: # RL Agent
                # RL Logic
                try:
                    action = current_player.choose_action(gm)
                    if action['action_type'] == 'play':
                        gm.play_card(current_player, action['card'], action['color'])
                    elif action['action_type'] == 'draw':
                        drawn = gm.deck.draw_card()
                        if drawn:
                            current_player.add_card(drawn)
                            play_it, color = current_player.play_drawn_decision(gm, drawn)
                            if play_it and gm.check_legal_play(drawn, gm.deck.peek_discard_pile()):
                                gm.play_card(current_player, drawn, color)
                            else:
                                gm._advance_turn()
                        else:
                            gm._advance_turn()
                except Exception as e:
                    print(f"Error in Game {i}, Turn {turns}: {e}")
                    # If RL fails, treat as loss or break
                    break
                    
            else:
                # Simple AI
                simple_ai_turn(gm, current_player)
        
        if gm.winner and gm.winner.name == "RL_Agent":
            wins += 1
            
        if (i+1) % 100 == 0:
            print(f"Progress: {i+1}/{num_games} | Current Win Rate: {wins/(i+1)*100:.2f}%")

    win_rate = wins / num_games
    end_time = time.time()
    duration = end_time - start_time
    
    print("-" * 30)
    print(f"Evaluation Complete in {duration:.2f}s")
    print(f"Final Win Rate: {win_rate*100:.2f}% ({wins}/{num_games})")
    
    # Save results
    result_line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Model: {model_path} | Games: {num_games} | Win Rate: {win_rate*100:.2f}%\n"
    with open("evaluation_results.txt", "a") as f:
        f.write(result_line)
    print(f"Result saved to evaluation_results.txt")

if __name__ == "__main__":
    MODEL_FILE = "/home/xiaozy24/python_code/uno_checkpoints/uno_rl/model.tar"
    if os.path.exists(MODEL_FILE):
        run_evaluation(MODEL_FILE, num_games=1000)
    else:
        print(f"Model file not found: {MODEL_FILE}")
