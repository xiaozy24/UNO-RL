from typing import Optional
from backend.player import Player
from config.enums import PlayerType, CardColor, CardType
from rl.model import RLAgent
from rl.utils import encode_state
from backend.utils.logger import game_logger
import random

class RLPlayer(Player):
    """
    RL-controlled Player.
    """
    def __init__(self, player_id: int, name: str, model_path: str = None, epsilon: float = 0.0):
        super().__init__(player_id, name, PlayerType.AI)
        self.agent = RLAgent(model_path)
        self.epsilon = epsilon
    
    def choose_action(self, game_manager) -> dict:
        """
        Decides the move.
        Returns dict: {'action_type': 'play'|'draw', 'card': Card, 'color': CardColor}
        """
        top_card = game_manager.deck.peek_discard_pile()
        
        # 1. Identify Legal Moves
        legal_cards = []
        for card in self.hand:
            if game_manager.check_legal_play(card, top_card):
                legal_cards.append(card)
        
        if not legal_cards:
            return {'action_type': 'draw'}
            
        # 2. Expand Moves (Handle Wild Color Choices)
        # For every legal card, if it's Wild, we have 4 variations (Red, Blue, Green, Yellow).
        # We need to score each variation.
        
        candidate_moves = [] # Tuple: (card, chosen_color_if_wild)
        
        for card in legal_cards:
            if card.color == CardColor.WILD:
                for color in [CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW]:
                    candidate_moves.append((card, color))
            else:
                candidate_moves.append((card, None))
                
        # 3. Create Features for Batch Processing
        input_tensors = []
        for card, color in candidate_moves:
            # Encode state assuming this action is taken (conceptually inputting State + Action)
            t = encode_state(self, game_manager, card, color)
            input_tensors.append(t)
            
        # 4. Agent Selection
        best_idx = self.agent.select_action(None, input_tensors, self.epsilon)
        
        # 5. Return Action
        best_card, best_color = candidate_moves[best_idx]
        
        # Return extra info for training (the feature vector of the chosen action)
        chosen_feature = input_tensors[best_idx]
        
        return {
            'action_type': 'play',
            'card': best_card,
            'color': best_color,
            'feature': chosen_feature # For training
        }
