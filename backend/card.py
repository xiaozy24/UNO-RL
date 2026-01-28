from typing import Optional
from config.enums import CardColor, CardType
from backend.utils.colors import TermColors, get_colored_text

class Card:
    """Card class for UNO game."""

    def __init__(self, color: CardColor, card_type: CardType, value: Optional[int] = None):
        """
        Initialize a card.

        Args:
            color: The color of the card.
            card_type: The type of the card (Number, Skip, etc.).
            value: The numerical value for Number cards (0-9). None for special cards.
        """
        self.color = color
        self.card_type = card_type
        self.value = value
    
    def __str__(self) -> str:
        color_name = self.color.value
        type_name = self.card_type.value
        
        display_str = ""
        if self.card_type == CardType.NUMBER:
            display_str = f"{color_name} {self.value}"
        elif self.color == CardColor.WILD:
            display_str = f"{type_name}"
        else:
            display_str = f"{color_name} {type_name}"

        return get_colored_text(display_str, self.color.value)

    def __repr__(self) -> str:
        return f"Card(color={self.color}, type={self.card_type}, value={self.value})"

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.color == other.color and self.card_type == other.card_type and self.value == other.value

    def is_match(self, other_card: 'Card') -> bool:

        """
        Check if this card matches another card (e.g., top of the discard pile).
        
        Args:
            other_card: The card to match against.
            
        Returns:
            True if matching, False otherwise.
        """
        # Wild cards always match
        if self.color == CardColor.WILD or other_card.color == CardColor.WILD:
            return True # Note: Logic might be more complex for playing logic vs matching logic
        
        # Color match
        if self.color == other_card.color:
            return True
        
        # Value match (for number cards)
        if self.card_type == CardType.NUMBER and other_card.card_type == CardType.NUMBER:
            return self.value == other_card.value
            
        # Type match (for action cards like Skip, Reverse, Draw Two)
        if self.card_type == other_card.card_type:
            return True
        
        return False
        
    def score(self) -> int:
        """Return the score value of the card."""
        if self.card_type == CardType.NUMBER:
            return self.value
        if self.card_type in [CardType.SKIP, CardType.REVERSE, CardType.DRAW_TWO]:
            return 20
        if self.card_type in [CardType.WILD, CardType.WILD_DRAW_FOUR]:
            return 50
        return 0
