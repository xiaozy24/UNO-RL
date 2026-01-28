import pygame
import sys
import threading
from communicator.communicator import Communicator
from communicator.comm_event import CommEvent, UpdateHandEvent, UpdateStateEvent, AskMoveEvent, PlayCardEvent, DrawCardEvent, ChallengeResponseEvent
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
        self.skip_rect = None # For Skip Button
        
        self.hand_counts = {} # {pid: count}
        self.challenging = False # State flag for challenge UI
        self.yes_rect = None
        self.no_rect = None
    
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
                    self.hand_counts = getattr(event, "hand_counts", {})
                
                elif event_name == "AskMoveEvent":
                    if self.current_player_idx == self.player_id:
                        self.my_turn = True
                        self.message = "Your Turn! Select a card to play or Draw Pile."
                
                elif event_name == "AskChallengeEvent":
                    self.challenging = True
                    self.message = f"Challenge {event.victim_name}'s +4?" # victim_name was sent
                    
            except Exception as e:
                print(f"Error processing event: {e}")

    def _handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.comm.stop()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    pos = pygame.mouse.get_pos()
                    if self.challenging:
                        self._check_challenge_click(pos)
                    elif self.my_turn:
                        self._check_click(pos)

    def _check_challenge_click(self, pos):
        if self.yes_rect and self.yes_rect.collidepoint(pos):
             print("Challenge: YES")
             self.comm.send_to_backend(ChallengeResponseEvent(True))
             self.challenging = False
             self.message = "Waiting..."
        elif self.no_rect and self.no_rect.collidepoint(pos):
             print("Challenge: NO")
             self.comm.send_to_backend(ChallengeResponseEvent(False))
             self.challenging = False
             self.message = "Waiting..."

    def _check_click(self, pos):
        # Check Skip Button
        if self.skip_rect and self.skip_rect.collidepoint(pos):
             print("Skipping/Drawing...")
             self.comm.send_to_backend(DrawCardEvent())
             self.my_turn = False
             return

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
        self.screen.fill((240, 234, 224)) # Zhuguosha Background Color
        
        player_img = AssetManager.get_instance().player_image
        if not player_img:
             player_img = AssetManager.get_instance().back_image
        
        # Player Positions relative to view (pid 0 is human/self)
        # 4 Players: Bottom(0), Right(1), Top(2), Left(3)
        # Using fixed layout based on screen size
        positions = {
            0: (SCREEN_WIDTH - 150, SCREEN_HEIGHT - 100),      # P0 (Self) - Shifted Right
            1: (SCREEN_WIDTH - 80, SCREEN_HEIGHT // 2),        # P1
            2: (SCREEN_WIDTH // 2, 80),                        # P2
            3: (80, SCREEN_HEIGHT // 2)                        # P3
        }
        
        font = AssetManager.get_instance().font

        # Draw Players
        for pid in range(4):
            # Calculate visual index if we had variable player_id, but here human is always 0.
            # If main script changes human ID, we'd need: v_idx = (pid - self.player_id) % 4
            v_idx = (pid - self.player_id) % 4
            if v_idx not in positions: continue
            
            cx, cy = positions[v_idx]
            
            if player_img:
                rect = player_img.get_rect(center=(cx, cy))
                self.screen.blit(player_img, rect)
                
                # Highlight active player
                if pid == self.current_player_idx:
                     pygame.draw.rect(self.screen, (255, 0, 0), rect, 3) # Red border
            
            # Draw Hand Count
            count = self.hand_counts.get(pid, 0)
            if font:
                 count_text = font.render(f"Cards: {count}", True, (0,0,0))
                 # Position above for 0, below for 2, side for 1,3
                 count_rect = count_text.get_rect(midbottom=(cx, cy - CARD_HEIGHT//2 - 5))
                 self.screen.blit(count_text, count_rect)
                     
            # Draw Label
            if font:
                label = f"P{pid}"
                if pid == self.player_id: label += " (You)"
                text = font.render(label, True, (0,0,0))
                text_rect = text.get_rect(midtop=(cx, cy + CARD_HEIGHT//2 + 5))
                self.screen.blit(text, text_rect)

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
            # Overlap hand over the player avatar area or slightly above?
            # Standard UNO games have hand at bottom. 
            # Our avatar is at Bottom Center (y=SCREEN_HEIGHT-100).
            # Hand y was SCREEN_HEIGHT - 150. This overlaps avatar.
            # Let's move hand slightly up or down.
            # Moving hand up to y = SCREEN_HEIGHT - 160
            
            total_width = len(self.hand) * 50 + CARD_WIDTH
            start_x = (SCREEN_WIDTH - total_width) // 2
            y = SCREEN_HEIGHT - 140
            
            for i, card in enumerate(self.hand):
                x = start_x + i * 50
                img = AssetManager.get_instance().get_card_image(card)
                self.screen.blit(img, (x, y))
                self.card_rects.append((pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT), i))
        
        # Draw Skip Button
        self.skip_rect = None
        if self.my_turn:
            # Position to the right of self avatar
            ax, ay = positions[0]
            bx = ax + 150
            by = ay
            
            box_surf = pygame.Surface((80, 50))
            box_surf.fill((200, 30, 30)) # Red
            
            if font:
                text_surf = font.render("SKIP", True, (0,0,0))
                s_rect = box_surf.get_rect(center=(bx, by))
                self.skip_rect = s_rect # Save for click
                
                self.screen.blit(box_surf, s_rect)
                t_rect = text_surf.get_rect(center=s_rect.center)
                self.screen.blit(text_surf, t_rect)

        # Draw Challenge UI
        self.yes_rect = None
        self.no_rect = None
        if self.challenging:
            # overlay
            s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            s.fill((0,0,0,128))
            self.screen.blit(s, (0,0))
            
            # Dialog Box
            dx, dy, dw, dh = SCREEN_WIDTH//2 - 150, SCREEN_HEIGHT//2 - 100, 300, 200
            pygame.draw.rect(self.screen, (255, 255, 255), (dx, dy, dw, dh))
            
            if font:
                 msg = font.render(self.message, True, (0,0,0))
                 self.screen.blit(msg, msg.get_rect(center=(dx+dw//2, dy+50)))
                 
            # Yes Button
            self.yes_rect = pygame.Rect(dx + 30, dy + 120, 100, 50)
            pygame.draw.rect(self.screen, (0, 200, 0), self.yes_rect) # Green
            if font:
                 t = font.render("Challenge", True, (0,0,0))
                 self.screen.blit(t, t.get_rect(center=self.yes_rect.center))
                 
            # No Button
            self.no_rect = pygame.Rect(dx + 170, dy + 120, 100, 50)
            pygame.draw.rect(self.screen, (200, 0, 0), self.no_rect) # Red
            if font:
                 t = font.render("Pass", True, (0,0,0))
                 self.screen.blit(t, t.get_rect(center=self.no_rect.center))


        # Draw Message
        if AssetManager.get_instance().font:
            text = AssetManager.get_instance().font.render(self.message, True, (0, 0, 0)) # Black text on light bg
            self.screen.blit(text, (20, 20))
            
            info = f"Current Player: {self.current_player_idx}"
            if self.my_turn: info += " (YOU)"
            info_text = AssetManager.get_instance().font.render(info, True, (255, 0, 0) if self.my_turn else (100, 100, 100))
            self.screen.blit(info_text, (20, 50))

        pygame.display.flip()
