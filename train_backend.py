from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from rl_agent import RLAgentHandler
import random

def run_game_epoch(gm: GameManager, rl_agent: RLAgentHandler):
    # Setup challenge decider
    def challenge_decider(victim, prev_color):
        if victim.player_type == PlayerType.RL:
            return rl_agent.should_challenge(victim, gm)
        else:
            return random.random() < 0.3 # SimpleAI
            
    gm.challenge_decider = challenge_decider
    
    # Start
    gm.start_game()
    
    # Loop
    while not gm.game_over:
        curr_player = gm.get_current_player()
        top_card = gm.deck.peek_discard_pile()
        
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
            # Simple AI (Mimic main_backend_loop logic roughly)
            # Find first legal card
            legal_cards = [c for c in curr_player.hand if gm.check_legal_play(c, top_card)]
            if legal_cards:
                 card = legal_cards[0] 
                 color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                 gm.play_card(curr_player, card, color)
            else:
                 # Draw
                 card = gm.deck.draw_card()
                 if card:
                     curr_player.add_card(card)
                     if gm.check_legal_play(card, top_card):
                         # SimpleAI plays drawn card if it can
                         color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                         gm.play_card(curr_player, card, color)
                     else:
                         gm._advance_turn()
                 else:
                     gm._advance_turn()

    # Return True if RL won
    return gm.winner and gm.winner.player_type == PlayerType.RL
