from enum import Enum
from config.enums import CardColor, CardType
from backend.card import Card

class CommEvent:
    def __init__(self, _event_id: int = 0):
        self._event_id = _event_id

class AckEvent(CommEvent):
    def __init__(self, event_id: int, success: bool, message: str = ""):
        super().__init__()
        self.ack_event_id = event_id
        self.success = success
        self.message = message

def to_dict_recursive(obj) -> dict:
    if isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, (list, tuple)):
        return [to_dict_recursive(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: to_dict_recursive(value) for key, value in obj.items()}
    elif hasattr(obj, '__dict__'):
        data = vars(obj)
        result = {}
        for key, value in data.items():
            result[key] = to_dict_recursive(value)
        
        if issubclass(type(obj), CommEvent):
             result["my_event_name"] = type(obj).__name__
        # Special handling for Card object to reconstruct it easily later if needed, 
        # though standard vars() is usually enough if we know the type on the other side.
        if isinstance(obj, Card):
             result["_class_name"] = "Card"
             
        return result
    else:
        return obj

def update_instance_from_dict_optimized(instance, data: dict):
    if not isinstance(data, dict):
        return instance

    for key, value in data.items():
        if hasattr(instance, key):
            current_attr = getattr(instance, key)
            
            if hasattr(current_attr, '__dict__') and current_attr is not None and isinstance(value, dict):
                update_instance_from_dict_optimized(current_attr, value)
            
            elif current_attr is None and isinstance(value, dict):
                # Try to infer type from _class_name if present
                if value.get("_class_name") == "Card":
                    # Reconstruct Card
                    # Card(color: CardColor, card_type: CardType, value: Optional[int] = None)
                    # We need to convert string Enums back to Enum objects
                    try:
                        color_str = value.get("color")
                        type_str = value.get("card_type")
                        val = value.get("value")
                        
                        # Find matching Enum
                        color_enum = next((c for c in CardColor if c.value == color_str), None)
                        if not color_enum:
                             # Default or error handling
                             color_enum = CardColor.RED 

                        type_enum = next((t for t in CardType if t.value == type_str), None)
                        if not type_enum:
                             type_enum = CardType.NUMBER
                        
                        new_card = Card(color_enum, type_enum, val)
                        setattr(instance, key, new_card)
                    except Exception as e:
                        print(f"Error reconstructing Card: {e}")
                        setattr(instance, key, value)
                else:
                    setattr(instance, key, value)
            
            elif (isinstance(current_attr, (list, tuple)) or current_attr is None) and isinstance(value, list):
                # Handle lists of Cards
                new_list = []
                for item in value:
                    if isinstance(item, dict) and item.get("_class_name") == "Card":
                         try:
                            color_str = item.get("color")
                            type_str = item.get("card_type")
                            val = item.get("value")
                            
                            color_enum = next((c for c in CardColor if c.value == color_str), CardColor.RED)
                            type_enum = next((t for t in CardType if t.value == type_str), CardType.NUMBER)
                            
                            new_card = Card(color_enum, type_enum, val)
                            new_list.append(new_card)
                         except:
                            new_list.append(item)
                    else:
                        new_list.append(item)
                setattr(instance, key, new_list)
            
            elif isinstance(current_attr, Enum) or (current_attr is None and isinstance(value, str)):
                 # Handle generic Enum restoration if current_attr is already an Enum
                 if isinstance(current_attr, Enum):
                     # Try to find matching value in Enum 
                     try:
                         # This assumes simple value match
                         new_enum = next((e for e in type(current_attr) if e.value == value), current_attr)
                         setattr(instance, key, new_enum)
                     except:
                         setattr(instance, key, value)
                 else:
                     setattr(instance, key, value)
            else:
                setattr(instance, key, value)

class UpdateHandEvent(CommEvent):
    def __init__(self, hand: list):
        super().__init__()
        self.hand = hand

class UpdateStateEvent(CommEvent):
    def __init__(self, top_card: Card, current_player_index: int, msg: str = "", hand_counts: dict = None, active_color: CardColor = None):
        super().__init__()
        self.top_card = top_card
        self.current_player_index = current_player_index
        self.msg = msg
        self.hand_counts = hand_counts if hand_counts else {}
        self.active_color = active_color

class AskMoveEvent(CommEvent):
    def __init__(self, valid_moves: list = None):
        super().__init__()
        self.valid_moves = valid_moves if valid_moves else []

class PlayCardEvent(CommEvent):
    def __init__(self, card_index: int, color_choice: CardColor = None):
        super().__init__()
        self.card_index = card_index
        self.color_choice = color_choice

class DrawCardEvent(CommEvent):
    def __init__(self):
        super().__init__()

class AskChallengeEvent(CommEvent):
    def __init__(self, victim_name: str):
        super().__init__()
        self.victim_name = victim_name

class ChallengeResponseEvent(CommEvent):
    def __init__(self, challenge: bool):
        super().__init__()
        self.challenge = challenge

class AskPlayDrawnCardEvent(CommEvent):
    def __init__(self, card: Card):
        super().__init__()
        self.card = card

class PlayDrawnCardResponseEvent(CommEvent):
    def __init__(self, play: bool, color_choice: CardColor = None):
        super().__init__()
        self.play = play
        self.color_choice = color_choice
