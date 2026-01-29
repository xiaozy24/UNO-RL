import sys
import os
import random
import time
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.game_manager import GameManager
from backend.player import Player
from config.enums import PlayerType
from backend.card import Card, CardType, CardColor
from rl_agent import RLAgentHandler

class ChallengeBackend:
    def __init__(self, agent):
        self.agent = agent
        self.current_gm = None
        self.stats = {
            "correct": 0,
            "total": 0,
            "wins": 0,
            "games": 0,
            "challenge_attempts": 0
        }
        
    def reset_stats(self):
        self.stats = {
            "correct": 0,
            "total": 0,
            "wins": 0,
            "games": 0,
            "challenge_attempts": 0
        }

    def challenge_decider(self, victim, previous_color):
        gm = self.current_gm
        # Note: pending_wild_draw_four is cleared by GM before calling this callback.
        # But checking GM code, resolve is called BEFORE advance_turn.
        # So current_player_index is the Attacker.
        
        attacker = gm.players[gm.current_player_index]
        
        # Ground Truth: Did attacker have the previous color?
        # If yes, they are bluffing -> Challenge is Correct.
        # If no, they are legal -> Challenge is Incorrect.
        att_hand = attacker.hand
        has_color = any(c.color == previous_color for c in att_hand)
        
        # Agent Decision
        # Note: We pass gm to agent so it can encode state
        do_challenge, prob_challenge = self.agent.should_challenge_probabilistic(victim, gm)
        
        # Update Stats
        self.stats["total"] += 1
        if do_challenge:
            self.stats["challenge_attempts"] += 1
        
        # Calculate Reward and Correctness
        # Case 1: Attacker Legal (has_color=False)
        #   - Challenge: -1.0 (Wrong)
        #   - No Challenge: 1.0 (Right)
        # Case 2: Attacker Illegal (has_color=True)
        #   - Challenge: 1.0 (Right)
        #   - No Challenge: -1.0 (Wrong)
        
        reward = 0.0
        current_correct = False
        
        if not has_color: # Legal
            if do_challenge:
                reward = -1.0
                current_correct = False
            else:
                reward = 1.0
                current_correct = True
        else: # Illegal/Bluff
            if do_challenge:
                reward = 1.0
                current_correct = True
            else:
                reward = -1.0
                current_correct = False
                
        if current_correct:
            self.stats["correct"] += 1
            
        # Inject reward into the last history item if training
        if self.agent.is_train and self.agent.history:
            # The last history item should be the one from should_challenge_probabilistic
            last_hist = self.agent.history[-1]
            if last_hist["head"] == "challenge":
                last_hist["reward"] = reward
        
        return do_challenge

    def run_game(self):
        # Setup 4 players: 1 RL, 3 SimpleAI (Random Legal)
        
        players = [
            Player(0, "RL_Agent", PlayerType.AI), 
            Player(1, "SimpleAI_1", PlayerType.AI), 
            Player(2, "SimpleAI_2", PlayerType.AI),
            Player(3, "SimpleAI_3", PlayerType.AI)
        ]
        
        self.current_gm = GameManager(players)
        
        # Set the challenge decider for the RL agent
        # We need to hook ONLY the RL agent's decision?
        # Or GameManager uses one global decider?
        # GameManager.challenge_decider is a single callback.
        # We need to filter inside if it's the RL agent.
        
        original_decider = self.challenge_decider
        
        def filtered_decider(victim, color):
            if victim.name == "RL_Agent":
                return original_decider(victim, color)
            else:
                # SimpleAI logic (approx 0.3 chance)
                # Or just return False/Random?
                # Using standard logic usually inside SimpleAI?
                # GameManager expects decider to return bool.
                # If SimpleAI is victim, let's just use random 0.3 like standard SimpleAI
                return random.random() < 0.3
                
        self.current_gm.challenge_decider = filtered_decider
        
        # Override RL Agent's selection methods to use our agent
        # We need to patch the AI logic for RL_Agent?
        # GameManager calls `player.choose_card` etc.
        # But `choose_card` is manual for humans.
        # We need a loop that calls agent.
        
        gm = self.current_gm
        
        # Override decider
        # Note: We must capture the 'bound' simple decider logic or implement it here
        # standard_decider uses self.current_gm which is correct.
        
        standard_decider = self.challenge_decider
        
        def filtered_decider(victim, color):
            # Log attempts to debug frequency
            # print(f"DEBUG: +4 Played against {victim.name}")
            if victim.name == "RL_Agent":
                 return standard_decider(victim, color)
            else:
                 return random.random() < 0.3
        
        gm.challenge_decider = filtered_decider
        
        gm.start_game()
        
        while not gm.game_over:
            curr_player = gm.get_current_player()
            
            if curr_player.name == "RL_Agent":
                 # RL Action
                 top = gm.deck.peek_discard_pile()
                 legal_cards = [c for c in curr_player.hand if gm.check_legal_play(c, top)]
                 
                 card_to_play = self.agent.select_card(curr_player, gm, legal_cards)
                 
                 if card_to_play and (card_to_play.card_type == CardType.WILD or card_to_play.card_type == CardType.WILD_DRAW_FOUR):
                     color = self.agent.select_color(curr_player, gm)
                     gm.play_card(curr_player, card_to_play, color)
                 elif card_to_play:
                     gm.play_card(curr_player, card_to_play)
                 else:
                     gm.draw_card_action(curr_player)
                     
            else:
                # SimpleAI logic
                top = gm.deck.peek_discard_pile()
                legal = [c for c in curr_player.hand if gm.check_legal_play(c, top)]
                if legal:
                    c = random.choice(legal)
                    color = None
                    if c.card_type in [CardType.WILD, CardType.WILD_DRAW_FOUR]:
                         # SimpleAI randomly picks color? Or picks most abundant color in hand?
                         # Let's say random for now.
                        color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                    gm.play_card(curr_player, c, color)
                else:
                    gm.draw_card_action(curr_player)

        if gm.winner and gm.winner.name == "RL_Agent":
            self.stats["wins"] += 1
        self.stats["games"] += 1

