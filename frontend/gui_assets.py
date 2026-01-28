import pygame
import os
from config.enums import CardColor, CardType
from backend.card import Card

CARD_WIDTH, CARD_HEIGHT = 80, 120
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "assets", "cards")

class AssetManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.images = {}
        self.back_image = None
        self.font = None
        self.initialized = False

    def load_assets(self):
        if self.initialized: return
        
        try:
             self.font = pygame.font.SysFont("Arial", 24, bold=True)
        except:
             self.font = pygame.font.Font(None, 24)

        colors = ["red", "blue", "green", "yellow"]
        enum_colors = [CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW]
        
        color_map = {
            CardColor.RED: "red",
            CardColor.BLUE: "blue",
            CardColor.GREEN: "green",
            CardColor.YELLOW: "yellow"
        }

        for c_enum in enum_colors:
            c_str = color_map[c_enum]
            folder = os.path.join(ASSETS_DIR, c_str)
            
            # Numbers
            for i in range(10):
                fname = f"uno_{c_str}_{i}.png"
                key = (c_enum, CardType.NUMBER, i)
                self.images[key] = self._load(os.path.join(folder, fname))
            
            # Action
            self.images[(c_enum, CardType.SKIP, None)] = self._load(os.path.join(folder, f"uno_{c_str}_Skip.png"))
            self.images[(c_enum, CardType.REVERSE, None)] = self._load(os.path.join(folder, f"uno_{c_str}_Reverse.png"))
            self.images[(c_enum, CardType.DRAW_TWO, None)] = self._load(os.path.join(folder, f"uno_{c_str}_+2.png"))

        black_folder = os.path.join(ASSETS_DIR, "black")
        self.images[(CardColor.WILD, CardType.WILD, None)] = self._load(os.path.join(black_folder, "uno_black_wild.png"))
        self.images[(CardColor.WILD, CardType.WILD_DRAW_FOUR, None)] = self._load(os.path.join(black_folder, "uno_black_+4.png"))
        
        self.back_image = self._load(os.path.join(ASSETS_DIR, "misc", "uno_back.png"))
        self.player_image = self._load(os.path.join(ASSETS_DIR, "misc", "uno_player.png"))
        self.initialized = True

    def _load(self, path):
        try:
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.smoothscale(img, (CARD_WIDTH, CARD_HEIGHT))
        except Exception as e:
            print(f"Warning: Asset not found {path} ({e})")
            s = pygame.Surface((CARD_WIDTH, CARD_HEIGHT))
            s.fill((100, 100, 100))
            return s

    def get_card_image(self, card: Card):
        if not card: return self.back_image
        
        # Handle Wilds specifically regardless of their temporary 'color' status if modified (though usually they keep WILD color type)
        if card.card_type == CardType.WILD:
             return self.images.get((CardColor.WILD, CardType.WILD, None))
        if card.card_type == CardType.WILD_DRAW_FOUR:
             return self.images.get((CardColor.WILD, CardType.WILD_DRAW_FOUR, None))
             
        key = (card.color, card.card_type, card.value)
        return self.images.get(key, self.back_image)
