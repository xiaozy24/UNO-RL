import numpy as np
import torch
from config.enums import CardColor, CardType
from backend.card import Card

# Encoding constants
COLOR_MAP = {CardColor.RED: 0, CardColor.YELLOW: 1, CardColor.BLUE: 2, CardColor.GREEN: 3, CardColor.WILD: 4}
TYPE_MAP = {
    CardType.NUMBER: 0, 
    CardType.SKIP: 1, 
    CardType.REVERSE: 2, 
    CardType.DRAW_TWO: 3, 
    CardType.WILD: 4, 
    CardType.WILD_DRAW_FOUR: 5
}

# Feature size calculation
# Own Hand: 108 cards (count encoding or binary) -> 108
# Top Card: One hot (Color 5 + Type 6 + Value 10 (0-9)) -> 21
# Opponent Hand Counts (Top 3 other players): 3 -> 3
# Current Active Color: 5 (One hot) -> 5
# Action Encoding: Same as Card Encoding (One hot 108 types? Or simpler features) -> 21 (Color/Type/Value)
# Total ~ 108 + 21 + 3 + 5 + 21 = ~158. Let's pad to 200.

STATE_DIM = 200

def encode_card(card: Card):
    """Encodes a card into a feature vector [Color(5), Type(6), Value(10)]."""
    vec = np.zeros(21, dtype=np.float32)
    
    # Color
    if card.color in COLOR_MAP:
        vec[COLOR_MAP[card.color]] = 1.0
        
    # Type
    if card.card_type in TYPE_MAP:
        vec[5 + TYPE_MAP[card.card_type]] = 1.0
        
    # Value
    if card.value is not None:
        vec[5 + 6 + card.value] = 1.0
        
    return vec

def encode_state(player, game_manager, action_card=None, wild_color_choice=None):
    """
    Encodes the game state from the perspective of 'player'.
    If 'action_card' is provided, it encodes the state AFTER taking that action (conceptually),
    or simply concatenates the action encoding for Q-value estimation.
    For this simple version, we stick to: Input = [State_Features, Action_Features]
    """
    
    # 1. Own Hand Encoding (108 slots, count or binary)
    # Since specific card instances matter less than "Red 5", we map standard deck to indices.
    # Simplified: Just Bag-of-Cards encoding based on (Color, Type, Value) feature sum?
    # Better: Full one-hot for cards is too big? No, 108 is fine.
    # But for simplicity, let's just use the feature vector of the hand *distribution*.
    # Actually, we defined encode_card as 21-dim. We can sum them up? Lossy.
    # Let's Flatten Hand: Sort hand, encode top 20 cards? 
    # Let's just use a fixed 54-dimension vector (since 2 of each card, maybe just unique cards 54?)
    # Let's stick to the architecture: State Part + Action Part.
    
    features = np.zeros(STATE_DIM, dtype=np.float32)
    idx = 0
    
    # --- GLOBAL STATE ---
    
    # Top Card
    top_card = game_manager.deck.peek_discard_pile()
    if top_card:
        tc_vec = encode_card(top_card)
        features[idx:idx+21] = tc_vec
    idx += 21
    
    # Active Color
    if game_manager.current_color in COLOR_MAP:
        features[idx + COLOR_MAP[game_manager.current_color]] = 1.0
    idx += 5
    
    # Opponent Hand Sizes (Relative to current player)
    # Get all players starting from next player
    p_idx = game_manager.players.index(player)
    num_players = len(game_manager.players)
    for i in range(1, 4): # Max 3 opponents
        target_idx = (p_idx + i) % num_players
        if target_idx == p_idx: break # Less than 4 players
        opponent = game_manager.players[target_idx]
        # Normalize hand size 0-20?
        features[idx] = opponent.get_hand_size() / 20.0 
        idx += 1
        
    # Move idx pointer to fixed start for Hand
    idx = 50 # Arbitrary offset for cleanliness
    
    # --- OWN HAND ---
    # Hand Summary: We can put the aggregated features of the hand?
    # Or simplified: Just encode the counts of each Color (4), count of Action Types?
    # Let's do: Counts of Red, Yellow, Blue, Green, Wild (5)
    # Counts of Number, Skip, Reverse, Draw2, Wild, Wild4 (6)
    # Counts of 0-9 (10)
    
    counts = np.zeros(21)
    for c in player.hand:
        counts += encode_card(c)
    
    features[idx:idx+21] = counts
    idx += 21
    
    # --- ACTION ---
    # If action_card is provided, we encode it.
    if action_card:
        ac_vec = encode_card(action_card)
        features[idx:idx+21] = ac_vec
        
        # If action is Wild, we also need to encode the CHOSEN COLOR.
        # This is tricky because the action is (Card, Color).
        if wild_color_choice:
             # Add extra one-hot for chosen color
             if wild_color_choice in COLOR_MAP:
                 features[idx+21+COLOR_MAP[wild_color_choice]] = 1.0
    
    return torch.from_numpy(features).float()
