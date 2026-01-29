import torch
import numpy as np
from config.enums import CardColor, CardType, Direction

# Fixed consistent ordering for cards
COLOR_ORDER = [CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW]
TYPE_ORDER = [CardType.NUMBER, CardType.SKIP, CardType.REVERSE, CardType.DRAW_TWO, CardType.WILD, CardType.WILD_DRAW_FOUR]

def get_card_index(card):
    """
    Returns a unique index 0-53 for each card type.
    0-9: Red 0-9
    10-12: Red Skip, Rev, +2
    13-22: Blue 0-9
    23-25: Blue Skip, Rev, +2
    ...
    52: Wild
    53: Wild Draw 4
    """
    if card.card_type == CardType.WILD:
        return 52
    if card.card_type == CardType.WILD_DRAW_FOUR:
        return 53
    
    # Color base
    c_idx = -1
    if card.color == CardColor.RED: c_idx = 0
    elif card.color == CardColor.BLUE: c_idx = 1
    elif card.color == CardColor.GREEN: c_idx = 2
    elif card.color == CardColor.YELLOW: c_idx = 3
    
    if c_idx == -1: return 52 # Fallback
    
    offset = c_idx * 13
    
    if card.card_type == CardType.NUMBER:
        return offset + card.value
    elif card.card_type == CardType.SKIP:
        return offset + 10
    elif card.card_type == CardType.REVERSE:
        return offset + 11
    elif card.card_type == CardType.DRAW_TWO:
        return offset + 12
        
    return 0

def encode_state(player, game_manager):
    """
    Encodes the game state from the perspective of 'player'.
    Features:
    - My Hand (54): Count of each card type.
    - Top Card (54): One-hot.
    - Current Color (4): One-hot (R, B, G, Y).
    - Opponent Hand Sizes (3): Relative to current player.
    - Direction (1): 1 or -1.
    """
    # 1. Hand
    hand_feats = np.zeros(54, dtype=np.float32)
    for card in player.hand:
        idx = get_card_index(card)
        hand_feats[idx] += 1
        
    # 2. Top Card
    top_feats = np.zeros(54, dtype=np.float32)
    top_card = game_manager.deck.peek_discard_pile()
    if top_card:
        top_feats[get_card_index(top_card)] = 1
        
    # 3. Current Color
    color_feats = np.zeros(4, dtype=np.float32)
    cc = game_manager.current_color
    if cc == CardColor.RED: color_feats[0] = 1
    elif cc == CardColor.BLUE: color_feats[1] = 1
    elif cc == CardColor.GREEN: color_feats[2] = 1
    elif cc == CardColor.YELLOW: color_feats[3] = 1
    # If None or Wild, maybe all zeros or specific logic. 
    # Usually active color is set after Wild.
    
    # 4. Opponent Hand Sizes
    # Get indices relative to self
    all_players = game_manager.players
    my_idx = player.player_id
    opp_feats = []
    num_p = len(all_players)
    for i in range(1, num_p):
        opp_idx = (my_idx + i) % num_p
        opp_feats.append(len(all_players[opp_idx].hand))
    opp_feats = np.array(opp_feats, dtype=np.float32)
    
    # 5. Direction
    dir_feat = np.array([1.0 if game_manager.direction == Direction.CLOCKWISE else -1.0], dtype=np.float32)
    
    return np.concatenate([hand_feats, top_feats, color_feats, opp_feats, dir_feat])

STATE_DIM = 54 + 54 + 4 + 3 + 1
