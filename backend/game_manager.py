import random
from typing import List, Optional
from backend.player import Player
from backend.deck import Deck
from backend.card import Card
from config.enums import CardType, CardColor, Direction, PlayerType
from config.settings import INITIAL_HAND_SIZE, UNO_PENALTY_CARDS
from backend.utils.logger import game_logger

class GameManager:
    """Manages the flow of the UNO game."""

    def __init__(self, players: List[Player]):
        self.players = players
        self.deck = Deck()
        self.current_player_index = 0
        self.direction = Direction.CLOCKWISE
        self.current_color = None # The active valid color (especially after Wild)
        self.game_over = False
        self.winner: Optional[Player] = None
        self.skipped_player: Optional[Player] = None

    def start_game(self):
        """Initialize game state, deal cards."""
        game_logger.info("Starting new game.")
        self.deck.shuffle()
        
        # Deal initial hands
        for _ in range(INITIAL_HAND_SIZE):
            for player in self.players:
                card = self.deck.draw_card()
                if card:
                    player.add_card(card)
        
        # Flip start card
        start_card = self.deck.draw_card()
        while start_card and start_card.card_type == CardType.WILD_DRAW_FOUR:
            # Cannot start with Wild Draw Four (House rule/Standard rule usually)
            self.deck.discard(start_card) # Effectively bury it or reshuffle? 
            # Standard rules says put it back in deck.
            # Simplified: just draw another
            self.deck.cards.insert(0, start_card) # Put back
            self.deck.shuffle()
            start_card = self.deck.draw_card()
            
        self.deck.discard(start_card)
        game_logger.info(f"Start card is: {start_card}")

        # Set initial current color
        if start_card.color == CardColor.WILD:
            # If start card is Wild, usually first player calls color.
            # For simplicity, let's randomly pick valid color or Default Red.
            # Or ask first player. Implementing random for now.
             self.current_color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
        else:
            self.current_color = start_card.color

        return start_card # Return start_card so main can display it

    def _handle_initial_card_effect(self, card: Card):
        if card.card_type == CardType.SKIP:
            game_logger.info("First player skipped!")
            self._advance_turn()
        elif card.card_type == CardType.REVERSE:
            game_logger.info("Direction reversed!")
            self.direction = Direction.COUNTER_CLOCKWISE
            if len(self.players) == 2:
                # In 2 player game, Reverse acts like Skip
                self._advance_turn()
            else:
                # Move to the "last" player basically as current is 0
                self.current_player_index = len(self.players) - 1 
                # Note: Logic for 'next player' needs to be robust
                return # We manually set index, so stop here to play turn
                
        elif card.card_type == CardType.DRAW_TWO:
            # First player draws 2 and turn skipped
            target = self.players[self.current_player_index]
            game_logger.info(f"{target.name} must draw 2 cards due to start card!")
            cards = [self.deck.draw_card() for _ in range(2)]
            for c in cards: 
                if c: target.add_card(c)
            self._advance_turn()

    def get_current_player(self) -> Player:
        return self.players[self.current_player_index]

    def _advance_turn(self):
        """Move index to next player."""
        step = 1 if self.direction == Direction.CLOCKWISE else -1
        self.current_player_index = (self.current_player_index + step) % len(self.players)

    def check_legal_play(self, card: Card, top_card: Card) -> bool:
        """Check if a card can be played on top of another."""
        # 1. Wild is always legal
        if card.color == CardColor.WILD:
            return True
            
        # 2. Match Current Active Color
        if card.color == self.current_color:
            return True
        
        # 3. Match Value/Type (if previous was not Wild forcing a color)
        # If top card is Wild and we are here, it means card.color != current_color.
        # But if Top is Wild, users MUST play current_color.
        if top_card.color == CardColor.WILD:
            # Strict rule: Must match announced color.
            return False 
            
        # Standard matching logic (Color matched handled above)
        if card.card_type == top_card.card_type:
            # If Number, value must match? Actually Type match implies symbol match for Actions.
            if card.card_type == CardType.NUMBER:
                 return card.value == top_card.value
            return True # Action on Action of same type is allowed (e.g. Red Skip on Blue Skip)
            
        return False

    def play_card(self, player: Player, card: Card, wild_color_choice: CardColor = None) -> bool:
        """
        Player attempts to play a card. 
        Returns True if successful, False if illegal move.
        """
        self.skipped_player = None # Reset skipped player state
        
        if player != self.get_current_player():
            game_logger.warning(f"Not {player.name}'s turn!")
            return False

        top_card = self.deck.peek_discard_pile()
        if not self.check_legal_play(card, top_card):
            game_logger.warning(f"Illegal move by {player.name}: {card} on {top_card} (active color: {self.current_color})")
            return False

        # Execute Play
        player.remove_card(card)
        self.deck.discard(card)
        game_logger.info(f"{player.name} played {card}.")

        # Check UNO status
        if player.get_hand_size() == 1:
            if not player.has_said_uno:
                 # In a real game, this is where others can catch them.
                 # For auto-check:
                 game_logger.info(f"{player.name} has 1 card left!")

        if player.get_hand_size() == 0:
            self.game_over = True
            self.winner = player
            game_logger.info(f"{player.name} wins!")
            return True

        # Update State based on Card
        self._apply_card_effect(card, wild_color_choice)
        
        # Next Turn
        self._advance_turn()
        return True

    def _apply_card_effect(self, card: Card, wild_color_choice: CardColor):
        # Update current color
        if card.color == CardColor.WILD:
            if wild_color_choice:
                self.current_color = wild_color_choice
                game_logger.info(f"Color changed to {self.current_color.value}")
            else:
                 # Fallback if no choice provided (AI should provide, Human should provide)
                 # Random for safety
                 self.current_color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                 game_logger.info(f"Color defaulted to {self.current_color.value}")
        else:
            self.current_color = card.color

        # Special Effects
        if card.card_type == CardType.SKIP:
            next_player_idx = (self.current_player_index + (1 if self.direction == Direction.CLOCKWISE else -1)) % len(self.players)
            self.skipped_player = self.players[next_player_idx]
            self._advance_turn()
            game_logger.info("Next player skipped.")

        elif card.card_type == CardType.REVERSE:
            self.direction = Direction.COUNTER_CLOCKWISE if self.direction == Direction.CLOCKWISE else Direction.CLOCKWISE
            game_logger.info("Direction reversed.")
            if len(self.players) == 2:
                # 2 Players: Reverse acts as Skip
                next_player_idx = (self.current_player_index + (1 if self.direction == Direction.CLOCKWISE else -1)) % len(self.players)
                self.skipped_player = self.players[next_player_idx]
                self._advance_turn()

        elif card.card_type == CardType.DRAW_TWO:
            next_player_idx = (self.current_player_index + (1 if self.direction == Direction.CLOCKWISE else -1)) % len(self.players)
            victim = self.players[next_player_idx]
            self.skipped_player = victim
            game_logger.info(f"{victim.name} draws 2 cards and is skipped.")
            for _ in range(2):
                c = self.deck.draw_card()
                if c: victim.add_card(c)
            # Skip the victim
            self._advance_turn()

        elif card.card_type == CardType.WILD_DRAW_FOUR:
             next_player_idx = (self.current_player_index + (1 if self.direction == Direction.CLOCKWISE else -1)) % len(self.players)
             victim = self.players[next_player_idx]
             self.skipped_player = victim
             game_logger.info(f"{victim.name} draws 4 cards and is skipped.")
             for _ in range(4):
                c = self.deck.draw_card()
                if c: victim.add_card(c)
             self._advance_turn()

    def draw_card_action(self, player: Player):
        """Current player draws a card (voluntarily or forced if cannot play)."""
        self.skipped_player = None # Reset skipped player state
        
        if player != self.get_current_player():
            return

        card = self.deck.draw_card()
        if card:
            player.add_card(card)
            game_logger.info(f"{player.name} drew a card.")
            # Optional: Allow playing immediately if playable?
            # Standard rule: If drawn card is playable, can play it.
            # Implementation: Return the card, let UI/Controller decide to call play_card again.
            # For now, simplistic finish turn logic:
            # If playable, we might want to autoplay it for AI, or let Human decide.
            # Here we just pass turn for simplicity unless we implement "playable check" logic return.
            self._advance_turn()

