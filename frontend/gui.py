import pygame
import sys
import threading
from communicator.communicator import Communicator
from communicator.comm_event import CommEvent, UpdateHandEvent, UpdateStateEvent, AskMoveEvent, PlayCardEvent, DrawCardEvent
from frontend.gui_assets import AssetManager
from backend.card import Card
from config.enums import CardColor, CardType

SCREEN_WIDTH, SCREEN_HEIGHT = 1000, 700
FPS = 30
CARD_WIDTH = 80
CARD_HEIGHT = 120

class UNOGUI:
    def __init__(self, comm: Communicator, player_id: int):
        self.comm = comm
        self.player_id = player_id
        self.running = True
        self.screen = None
        self.clock = None
        
        self.hand = [] # List of Card objects
        self.top_card = None # Card object
        self.current_player_idx = -1
        self.message = "Waiting for game start..."
        self.my_turn = False
        
        self.card_rects = [] # To store (rect, index)
    
    def run(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"UNO-RL Player {self.player_id}")
        self.clock = pygame.time.Clock()
        
        AssetManager.get_instance().load_assets()
        
        while self.running:
            self._handle_input()
            self._process_events()
            self._draw()
            self.clock.tick(FPS)
            
        pygame.quit()
        sys.exit()

    def _process_events(self):
        while not self.comm.btf_queue.empty():
            try:
                event = self.comm.btf_queue.get_nowait()
                # Use my_event_name if serialized from dict, or class check if direct object
                event_name = getattr(event, "my_event_name", type(event).__name__)
                
                if event_name == "UpdateHandEvent":
                    self.hand = event.hand
                elif event_name == "UpdateStateEvent":
                    self.top_card = event.top_card
                    self.current_player_idx = event.current_player_index
                    self.message = event.msg
                    # Reset turn state if it's not me anymore
                    if self.current_player_idx != self.player_id:
                        self.my_turn = False
                elif event_name == "AskMoveEvent":
                    if self.current_player_idx == self.player_id:
                        self.my_turn = True
                        self.message = "Your Turn! Select a card to play or Draw Pile."
            except Exception as e:
                print(f"Error processing event: {e}")

    def _handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.comm.stop()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and self.my_turn:
                    pos = pygame.mouse.get_pos()
                    self._check_click(pos)

    def _check_click(self, pos):
        # Check Draw Pile
        cx, cy = SCREEN_WIDTH//2, SCREEN_HEIGHT//2 - 60
        draw_rect = pygame.Rect(cx + 100, cy, CARD_WIDTH, CARD_HEIGHT)
        if draw_rect.collidepoint(pos):
             print("Drawing card...")
             self.comm.send_to_backend(DrawCardEvent())
             self.my_turn = False
             return

        # Check Hand (Reversed for Z-order)
        for rect, index in reversed(self.card_rects):
            if rect.collidepoint(pos):
                print(f"Clicked card index {index}")
                # Default RED for Wild for now
                self.comm.send_to_backend(PlayCardEvent(index, CardColor.RED)) 
                self.my_turn = False
                return

    def _draw(self):
        self.screen.fill((34, 139, 34)) # Forest Green
        
        # Draw Top Card
        cx, cy = SCREEN_WIDTH//2 - 40, SCREEN_HEIGHT//2 - 60
        if self.top_card:
            img = AssetManager.get_instance().get_card_image(self.top_card)
            self.screen.blit(img, (cx, cy))
        else:
            pygame.draw.rect(self.screen, (0,0,0), (cx, cy, CARD_WIDTH, CARD_HEIGHT), 2)
            
        # Draw Draw Pile
        back_img = AssetManager.get_instance().back_image
        if back_img:
            self.screen.blit(back_img, (cx + 100, cy))
        
        # Draw Hand
        self.card_rects = []
        if self.hand:
            total_width = len(self.hand) * 50 + CARD_WIDTH
            start_x = (SCREEN_WIDTH - total_width) // 2
            y = SCREEN_HEIGHT - 150
            
            for i, card in enumerate(self.hand):
                x = start_x + i * 50
                img = AssetManager.get_instance().get_card_image(card)
                self.screen.blit(img, (x, y))
                self.card_rects.append((pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT), i))
        
        # Draw Message
        if AssetManager.get_instance().font:
            text = AssetManager.get_instance().font.render(self.message, True, (255, 255, 255))
            self.screen.blit(text, (20, 20))
            
            info = f"Current Player: {self.current_player_idx}"
            if self.my_turn: info += " (YOU)"
            info_text = AssetManager.get_instance().font.render(info, True, (255, 255, 0) if self.my_turn else (200, 200, 200))
            self.screen.blit(info_text, (20, 50))

        pygame.display.flip()
