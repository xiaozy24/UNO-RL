import numpy as np
import torch
from config.enums import CardColor, CardType
from backend.card import Card

# Card Encoding Map
# 4 Colors * 13 Types (0-9, Skip, Rev, D2) = 52
# Wild = 52
# Wild Draw 4 = 53

COLOR_MAP = {
    CardColor.RED: 0,
    CardColor.YELLOW: 1,
    CardColor.GREEN: 2,
    CardColor.BLUE: 3,
    CardColor.WILD: 4
}

TYPE_MAP = {
    CardType.NUMBER: 0, # Uses value 0-9
    CardType.SKIP: 10,
    CardType.REVERSE: 11,
    CardType.DRAW_TWO: 12,
    CardType.WILD: 13,
    CardType.WILD_DRAW_FOUR: 14
}

def card_to_id(card: Card) -> int:
    if card.color == CardColor.WILD:
        if card.card_type == CardType.WILD:
            return 52
        elif card.card_type == CardType.WILD_DRAW_FOUR:
            return 53
    
    # Colored Cards
    color_val = COLOR_MAP.get(card.color)
    if color_val is None or color_val > 3:
        raise ValueError(f"Invalid color for ID mapping: {card}")
    
    base = color_val * 13
    
    if card.card_type == CardType.NUMBER:
        return base + card.value
    elif card.card_type == CardType.SKIP:
        return base + 10
    elif card.card_type == CardType.REVERSE:
        return base + 11
    elif card.card_type == CardType.DRAW_TWO:
        return base + 12
        
    raise ValueError(f"Unknown card type: {card}")

def id_to_card(card_id: int) -> Card:
    if card_id == 52:
        return Card(CardColor.WILD, CardType.WILD)
    if card_id == 53:
        return Card(CardColor.WILD, CardType.WILD_DRAW_FOUR)
        
    color_val = card_id // 13
    remainder = card_id % 13
    
    color = list(COLOR_MAP.keys())[list(COLOR_MAP.values()).index(color_val)]
    
    if remainder < 10:
        return Card(color, CardType.NUMBER, value=remainder)
    elif remainder == 10:
        return Card(color, CardType.SKIP)
    elif remainder == 11:
        return Card(color, CardType.REVERSE)
    elif remainder == 12:
        return Card(color, CardType.DRAW_TWO)

    raise ValueError(f"Invalid card_id: {card_id}")

def encode_hand(hand: list[Card]) -> np.ndarray:
    # 54 dim array count
    arr = np.zeros(54, dtype=np.int8)
    for card in hand:
        arr[card_to_id(card)] += 1
    return arr

def encode_onehot(card: Card) -> np.ndarray:
    arr = np.zeros(54, dtype=np.int8)
    if card:
        arr[card_to_id(card)] = 1
    return arr

# Action Encodings
# We explicitly map "Play Wild Red" etc.
# 0-51: Colored Cards (0-9, Skip, Rev, +2) * 4 Colors
# 52-55: Wild (R, Y, G, B)
# 56-59: Wild+4 (R, Y, G, B)
# 60: Draw / Pass (Context dependent)
# 61: Challenge Success (Yes)
# 62: Challenge Fail (No) - Actually just boolean choice, let's say 61=Yes, 62=No.

def act_id_to_card_action(act_id: int):
    """
    Returns (CardObject, ColorChoice, IsChallenge/Special)
    """
    if 0 <= act_id <= 51:
        # Standard colored card
        # Logic: We can map back to card_to_id space.
        # But wait, card_to_id maps Wild to 52/53.
        # Here we have colored cards 0-51.
        # 0-12 Red, 13-25 Yellow, 26-38 Green, 39-51 Blue.
        color_idx = act_id // 13
        type_idx = act_id % 13
        
        color = [CardColor.RED, CardColor.YELLOW, CardColor.GREEN, CardColor.BLUE][color_idx]
        
        if type_idx < 10:
            return Card(color, CardType.NUMBER, value=type_idx), None, None
        elif type_idx == 10:
            return Card(color, CardType.SKIP), None, None
        elif type_idx == 11:
            return Card(color, CardType.REVERSE), None, None
        elif type_idx == 12:
            return Card(color, CardType.DRAW_TWO), None, None
            
    elif 52 <= act_id <= 55:
        # Wild
        color_idx = act_id - 52
        color = [CardColor.RED, CardColor.YELLOW, CardColor.GREEN, CardColor.BLUE][color_idx]
        return Card(CardColor.WILD, CardType.WILD), color, None
        
    elif 56 <= act_id <= 59:
        # Wild +4
        color_idx = act_id - 56
        color = [CardColor.RED, CardColor.YELLOW, CardColor.GREEN, CardColor.BLUE][color_idx]
        return Card(CardColor.WILD, CardType.WILD_DRAW_FOUR), color, None
        
    elif act_id == 60:
        return None, None, "DRAW" # Or Pass
        
    elif act_id == 61:
        return None, None, "CHALLENGE_YES"
        
    elif act_id == 62:
        return None, None, "CHALLENGE_NO"
        
    return None, None, None

def card_action_to_act_id(card: Card, color_choice: CardColor = None, special: str = None) -> int:
    if special == "DRAW" or special == "PASS":
        return 60
    if special == "CHALLENGE_YES":
        return 61
    if special == "CHALLENGE_NO":
        return 62
        
    if card.color == CardColor.WILD:
        # Must have color_choice
        base = 52 if card.card_type == CardType.WILD else 56
        if color_choice == CardColor.RED: offset = 0
        elif color_choice == CardColor.YELLOW: offset = 1
        elif color_choice == CardColor.GREEN: offset = 2
        elif color_choice == CardColor.BLUE: offset = 3
        else: offset = 0 # Default?
        return base + offset
    else:
        # Standard
        # Map color 
        c_map = {CardColor.RED: 0, CardColor.YELLOW: 1, CardColor.GREEN: 2, CardColor.BLUE: 3}
        base = c_map[card.color] * 13
        
        if card.card_type == CardType.NUMBER:
            return base + card.value
        elif card.card_type == CardType.SKIP:
            return base + 10
        elif card.card_type == CardType.REVERSE:
            return base + 11
        elif card.card_type == CardType.DRAW_TWO:
            return base + 12
            
    return 60 # Fallback

def encode_action_onehot(act_id):
    arr = np.zeros(63, dtype=np.int8)
    if 0 <= act_id < 63:
        arr[act_id] = 1
    return arr

