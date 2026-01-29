from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from rl_agent import RLAgentHandler
import random

def run_game_epoch(gm: GameManager, rl_agent: RLAgentHandler):
    # Setup challenge decider
    def challenge_decider(victim, prev_color):
        if victim.player_type == PlayerType.RL:
            initial_count = len(rl_agent.history)
            choice = rl_agent.should_challenge(victim, gm)
            
            if len(rl_agent.history) > initial_count:
                 # Mark the index we just added
                 rl_agent.history[-1]["challenge_pending"] = True
                 
            return choice
        else:
            return random.random() < 0.3 # SimpleAI
            
    gm.challenge_decider = challenge_decider
    
    # Start
    gm.start_game()
    
    # Loop
    while not gm.game_over:
        curr_player = gm.get_current_player()
        top_card = gm.deck.peek_discard_pile()
        
        # Check pending challenge result
        if rl_agent.is_train and rl_agent.history:
            last = rl_agent.history[-1]
            if last.get("challenge_pending"):
                outcome = gm.last_challenge_result
                # Outcome: True = Challenger Won. False = Challenger Lost.
                if outcome is not None and last["action"] == 1: # We Challenged
                     last["challenge_success"] = outcome
                
                del last["challenge_pending"]

        if curr_player.player_type == PlayerType.RL:
            # 1. Check legal plays
            legal_cards = [c for c in curr_player.hand if gm.check_legal_play(c, top_card)]
            
            if legal_cards:
                # Choose card
                card = rl_agent.select_card(curr_player, gm, legal_cards)
                
                # Choose color if Wild
                color = None
                if card.color == CardColor.WILD:
                    color = rl_agent.select_color(curr_player, gm)
                
                # Play
                gm.play_card(curr_player, card, color)
            else:
                # Must draw
                card = gm.deck.draw_card()
                if card:
                    curr_player.add_card(card)
                    # Check if playable
                    if gm.check_legal_play(card, top_card):
                        if rl_agent.should_play_drawn(curr_player, gm, card):
                             color = None
                             if card.color == CardColor.WILD:
                                 color = rl_agent.select_color(curr_player, gm)
                             gm.play_card(curr_player, card, color)
                        else:
                             gm._advance_turn()
                    else:
                        gm._advance_turn()
                else:
                    gm._advance_turn()
        
        else:
            # Simple AI (Random but valid)
            legal_cards = [c for c in curr_player.hand if gm.check_legal_play(c, top_card)]
            if legal_cards:
                 card = random.choice(legal_cards) 
                 # Pick a valid color from enum, avoiding "WILD" string if we need concrete
                 color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                 gm.play_card(curr_player, card, color)
            else:
                 # Draw
                 card = gm.deck.draw_card()
                 if card:
                     curr_player.add_card(card)
                     if gm.check_legal_play(card, top_card):
                         if random.random() < 0.5:
                             color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                             gm.play_card(curr_player, card, color)
                         else:
                             gm._advance_turn()
                     else:
                         gm._advance_turn()
                 else:
                     gm._advance_turn()

    # Return True if RL won
    return gm.winner and gm.winner.player_type == PlayerType.RL
