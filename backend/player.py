from typing import List, Optional
from backend.card import Card
from config.enums import PlayerType, CardColor, CardType
from backend.utils.logger import game_logger

class Player:
    """Player class."""

    def __init__(self, player_id: int, name: str, player_type: PlayerType):
        self.player_id = player_id
        self.name = name
        self.player_type = player_type
        self.hand: List[Card] = []
        self.has_said_uno = False

    def add_card(self, card: Card):
        self.hand.append(card)

    def remove_card(self, card: Card) -> bool:
        """Remove a card from hand. Returns True if successful."""
        # We need to find the specific card instance or equivalent match
        try:
            # Finding exact match logic or equal value logic. 
            # Since Card doesn't have unique ID, we rely on value equality usually.
            # But specific instance might be better if UI passes it. 
            # For now, let's assume we pass the index or we just check matching attributes.
            # Python's list.remove compares by equality.
            # But our Card class object equality (default) is by instance ID.
            # Let's check Card implementation... I didn't add __eq__. 
            # I should rely on the object instance being passed from the Hand list itself.
            self.hand.remove(card)
            return True
        except ValueError:
             game_logger.error(f"Card {card} not found in player {self.name}'s hand.")
             return False

    def get_hand_size(self) -> int:
        return len(self.hand)

    def sort_hand(self):
        """Sort hand by color and then by value/type for display."""
        # Custom sort key: Color (enum value) -> Type -> Value
        # Note: Enums might not strictly compare nicely without defined order, but string value works.
        self.hand.sort(key=lambda c: (c.color.value, c.card_type.value, c.value if c.value is not None else -1))

    def reset_uno_status(self):
        self.has_said_uno = False

    def say_uno(self):
        self.has_said_uno = True
        game_logger.info(f"Player {self.name} says UNO!")

    def has_playable_card(self, top_card: Card, current_color: CardColor = None) -> bool:
        """
        Check if player has any playable card.
        Args:
            top_card: The card on top of the discard pile.
            current_color: The active color (important if top card is Wild). 
                           If None, use top_card.color.
        """
        effective_color = current_color if current_color else top_card.color
        
        for card in self.hand:
            # 1. Wild cards are always playable
            if card.color == CardColor.WILD:
                return True
            
            # 2. Match color
            if card.color == effective_color:
                return True
            
            # 3. Match value/symbol (only if not checking wild color override logic strictly, 
            # but standard UNO allows matching number/symbol even if color is different)
            # EXCEPT if the top card was a Wild card that set a color, you usually have to match that COLOR.
            # However, if top card is a Blue 7, and I have a Red 7, I can play it.
            # If top card is a Wild (Blue), I must play Blue. I cannot play Red 7 just because Wild has no "7".
            # So:
            # If top is Wild/Wild4: Must match the *announced* color (effective_color).
            # If top is colored card: Match color OR match symbol/value.
            
            if top_card.color != CardColor.WILD:
                 if card.color == effective_color: return True
                 if card.card_type == top_card.card_type:
                     if card.card_type == CardType.NUMBER:
                         if card.value == top_card.value: return True
                     else:
                         # Action cards match by type (e.g. Skip on Skip)
                         return True
            else:
                # Top is Wild, strictly match defined color
                if card.color == effective_color: return True
                
        return False
        
    def __str__(self):
        return f"{self.name} ({self.player_type.value}) - {len(self.hand)} cards"
