import random
from typing import List, Optional
from backend.card import Card
from config.enums import CardColor, CardType
from backend.utils.logger import game_logger

class Deck:
    """Deck class for managing the draw pile and discard pile."""

    def __init__(self):
        self.cards: List[Card] = []
        self.discard_pile: List[Card] = []
        self._initialize_deck()
        self.shuffle()

    def _initialize_deck(self):
        """Create the standard 108 UNO cards."""
        game_logger.info("Initializing deck...")
        colors = [CardColor.RED, CardColor.YELLOW, CardColor.BLUE, CardColor.GREEN]
        
        for color in colors:
            # 1 zero card per color
            self.cards.append(Card(color, CardType.NUMBER, 0))
            
            # 2 of each number 1-9
            for i in range(1, 10):
                self.cards.append(Card(color, CardType.NUMBER, i))
                self.cards.append(Card(color, CardType.NUMBER, i))
            
            # 2 of each action card
            for action_type in [CardType.SKIP, CardType.REVERSE, CardType.DRAW_TWO]:
                self.cards.append(Card(color, action_type))
                self.cards.append(Card(color, action_type))
        
        # Wild cards
        for _ in range(4):
            self.cards.append(Card(CardColor.WILD, CardType.WILD))
            self.cards.append(Card(CardColor.WILD, CardType.WILD_DRAW_FOUR))

        game_logger.info(f"Deck initialized with {len(self.cards)} cards.")

    def shuffle(self):
        """Shuffle the draw pile."""
        random.shuffle(self.cards)
        game_logger.info("Deck shuffled.")

    def draw_card(self) -> Optional[Card]:
        """Draw a single card. If deck is empty, reshuffle discard pile (except top card)."""
        if not self.cards:
            if not self.discard_pile:
                game_logger.warning("Deck and discard pile are both empty!")
                return None
            
            # Reshuffle discard pile to form new deck
            # Keep the top card of the discard pile
            top_card = self.discard_pile.pop()
            self.cards = self.discard_pile
            self.discard_pile = []
            self.shuffle()
            self.discard_pile.append(top_card)
            
            game_logger.info("Reshuffled discard pile into draw deck.")

        if self.cards:
             return self.cards.pop()
        return None

    def discard(self, card: Card):
        """Add a card to the discard pile."""
        self.discard_pile.append(card)

    def peek_discard_pile(self) -> Optional[Card]:
        """Look at the top card of the discard pile."""
        if self.discard_pile:
            return self.discard_pile[-1]
        return None
