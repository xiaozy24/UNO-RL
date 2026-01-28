import logging
import time
from tqdm import tqdm
from backend.player import Player
from backend.rl_player import RLPlayer
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from backend.utils.logger import game_logger

# Suppress Logs
if hasattr(game_logger, 'logger') and game_logger.logger:
    game_logger.logger.setLevel(logging.ERROR)


def simple_ai_challenge(victim, previous_color):
    import random
    return random.random() < 0.3

def verify_challenge_decider(victim, previous_color):
    if isinstance(victim, RLPlayer):
        # We need access to gm... challenge_decider signature doesn't pass gm.
        # But RLPlayer needs gm to build obs.
        # Implies we need to bind this method to a closure that captures gm
        # OR attached to Verify Loop instance
        return victim.challenge_decision(victim.current_gm_ref, previous_color)
    else:
        return simple_ai_challenge(victim, previous_color)

def run_game(ep_idx):
    p1 = RLPlayer(1, "RL_Agent")
    p2 = Player(2, "AI_2", PlayerType.AI)
    p3 = Player(3, "AI_3", PlayerType.AI)
    p4 = Player(4, "AI_4", PlayerType.AI)
    
    players = [p1, p2, p3, p4]
    gm = GameManager(players)
    
    # Inject GM ref into RL Player manually for challenge callback context
    p1.current_gm_ref = gm
    
    # Hook Challenge
    gm.challenge_decider = verify_challenge_decider
    
    # Animation Hooks (None)
    gm.on_play_card_animation = lambda pid, c: p1.update_history(c) # Track history
    
    start_card = gm.start_game()
    p1.update_history(start_card)
    
    turns = 0
    while not gm.game_over and turns < 1000:
        turns += 1
        current_player = gm.get_current_player()
        top_card = gm.deck.peek_discard_pile()
        
        if current_player.get_hand_size() == 2:
            current_player.say_uno()
            
        if isinstance(current_player, RLPlayer):
            # RL
            action = current_player.choose_action(gm)
            if action['action_type'] == 'play':
                gm.play_card(current_player, action['card'], action['color'])
            else:
                # Draw
                drawn = gm.deck.draw_card()
                if drawn:
                    current_player.add_card(drawn)
                    # Decision to play
                    play_it, color = current_player.play_drawn_decision(gm, drawn)
                    if play_it and gm.check_legal_play(drawn, gm.deck.peek_discard_pile()):
                        gm.play_card(current_player, drawn, color)
                    else:
                        gm._advance_turn()
                else:
                    gm._advance_turn()
                    
        else:
            # Simple AI (Random/First Legal)
            legal = [c for c in current_player.hand if gm.check_legal_play(c, top_card)]
            if legal:
                c = legal[0]
                wc = None
                if c.color == CardColor.WILD:
                    wc = CardColor.RED # Simplified
                gm.play_card(current_player, c, wc)
            else:
                drawn = gm.deck.draw_card()
                if drawn:
                    current_player.add_card(drawn)
                    if gm.check_legal_play(drawn, top_card):
                         wc = None
                         if drawn.color == CardColor.WILD:
                              wc = CardColor.RED
                         gm.play_card(current_player, drawn, wc)
                    else:
                        gm._advance_turn()
                else:
                    gm._advance_turn()
                    
    if gm.winner and isinstance(gm.winner, RLPlayer):
        return 1
    return 0

if __name__ == "__main__":
    wins = 0
    total = 1000
    print(f"Running {total} games to verify initial RL performance...")
    for i in tqdm(range(total)):
        wins += run_game(i)
        
    print(f"RL Agent Win Rate: {wins/total * 100:.2f}%")
