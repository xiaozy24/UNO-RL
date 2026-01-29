from enum import Enum, auto

class CardColor(Enum):
    RED = "Red"
    YELLOW = "Yellow"
    BLUE = "Blue"
    GREEN = "Green"
    WILD = "Wild" # For Wild cards that don't have a color initially

class CardType(Enum):
    NUMBER = "Number"
    SKIP = "Skip"
    REVERSE = "Reverse"
    DRAW_TWO = "Draw Two"
    WILD = "Wild"
    WILD_DRAW_FOUR = "Wild Draw Four"

class PlayerType(Enum):
    HUMAN = "Human"
    AI = "AI"
    RL = "RL"

class Direction(Enum):
    CLOCKWISE = 1
    COUNTER_CLOCKWISE = -1
