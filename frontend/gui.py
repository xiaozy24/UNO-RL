import pygame
import sys
import threading
import re
from communicator.communicator import Communicator
from communicator.comm_event import CommEvent, UpdateHandEvent, UpdateStateEvent, AskMoveEvent, PlayCardEvent, DrawCardEvent, ChallengeResponseEvent, AskChallengeEvent, AskPlayDrawnCardEvent, PlayDrawnCardResponseEvent, AnimationCompleteEvent
from frontend.gui_assets import AssetManager
from backend.card import Card
from config.enums import CardColor, CardType

SCREEN_WIDTH, SCREEN_HEIGHT = 1000, 700
FPS = 30
CARD_WIDTH = 80
CARD_HEIGHT = 120

class GUIAnimation:
    def __init__(self, img, start_pos, end_pos, duration=15, on_complete=None): # duration in frames
        self.img = img
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.duration = duration
        self.current_frame = 0
        self.finished = False
        self.on_complete = on_complete
    
    def update(self):
        # Allow one-time completion trigger
        if self.finished: return 

        self.current_frame += 1
        if self.current_frame >= self.duration:
            self.finished = True
            if self.on_complete:
                self.on_complete()
            
    def draw(self, screen):
        t = self.current_frame / self.duration
        # Linear interpolation
        # start_pos is center or top-left? 
        # Usually positions are centers or top-lefts. 
        # In _draw, player positions are centers usually? 
        # let's assume passed positions are Top-Left for blit.
        
        x = self.start_pos[0] + (self.end_pos[0] - self.start_pos[0]) * t
        y = self.start_pos[1] + (self.end_pos[1] - self.start_pos[1]) * t
        screen.blit(self.img, (x, y))

ANSWER_DRAWN_COLOR_MAP = {
    CardColor.RED: (200, 30, 30), 
    CardColor.BLUE: (30, 30, 200),
    CardColor.GREEN: (30, 200, 30),
    CardColor.YELLOW: (200, 200, 0),
    CardColor.WILD: (0, 0, 0)
}

class UNOGUI:
    def __init__(self, comm: Communicator, player_id: int):
        self.comm = comm
        self.player_id = player_id
        self.running = True
        self.screen = None
        self.clock = None
        
        self.hand = [] # List of Card objects
        self.top_card = None # Card object (Visual)
        self.active_color = None # Current active color (Visual)
        
        self.server_top_card = None # Real backend state
        self.server_active_color = None # Real backend state
        self.server_hand = [] # Buffered Hand
        self.server_hand_counts = {} # Buffered Hand Counts
        
        self.current_player_idx = -1
        self.message = "Waiting for game start..."
        self.my_turn = False
        
        self.card_rects = [] # To store (rect, index)
        self.skip_rect = None # For Skip Button
        
        self.hand_counts = {} # {pid: count}
        self.challenging = False # State flag for challenge UI
        self.yes_rect = None
        self.no_rect = None
        
        # Color Picker State
        self.picking_color = False
        self.color_picker_rects = [] # (rect, color_enum)
        self.color_pick_callback = None # Function to call with selected color

        # Drawn Card Play State
        self.answering_drawn = False
        self.drawn_card_obj = None # Valid Card object
        self.active_color = None # Current active color on the board
        self.animations = [] # List of GUIAnimation objects

    def run(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
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
                    self.server_hand = event.hand
                    if not self.animations:
                         self.hand = self.server_hand

                elif event_name == "UpdateStateEvent":
                    self.server_top_card = event.top_card
                    self.server_active_color = getattr(event, "active_color", None)
                    self.server_hand_counts = getattr(event, "hand_counts", {})
                    
                    self.current_player_idx = event.current_player_index
                    self.message = event.msg
                    # Reset turn state if it's not me anymore
                    if self.current_player_idx != self.player_id:
                        self.my_turn = False
                    
                    # Only update visual state if no animations are running
                    if not self.animations:
                         self.top_card = self.server_top_card
                         self.active_color = self.server_active_color
                         self.hand_counts = self.server_hand_counts
                
                elif event_name == "PlayerPlayedCardEvent":
                    try:
                        pid = event.player_id
                        card = event.card
                        
                        if self.screen:
                            w, h = self.screen.get_size()
                            # Same positions map as _draw
                            positions = {
                                0: (w - 150, h - 100),
                                1: (w - 80, h // 2),
                                2: (w // 2, 120),
                                3: (80, h // 2)
                            }
                            v_idx = (pid - self.player_id) % 4
                            start_center = positions.get(v_idx, (0,0))
                            
                            sx = start_center[0] - CARD_WIDTH // 2
                            sy = start_center[1] - CARD_HEIGHT // 2
                            ex = w // 2 - CARD_WIDTH // 2
                            ey = h // 2 - CARD_HEIGHT // 2
                            
                            img = AssetManager.get_instance().get_card_image(card)
                            
                            def on_landed():
                                # Force visual update to this card when it lands
                                self.top_card = card
                                # If server already sent newer state, sync to it
                                if self.server_top_card:
                                     # If the server top card is different (e.g. +4 resolved?), verify.
                                     # But usually it waits.
                                     # We trust the animation card is the top card at this moment.
                                     pass
                                # Sync active color if we have server knowledge, otherwise hold
                                if self.server_active_color:
                                     self.active_color = self.server_active_color
                                else:
                                     # If no server update yet, active_color might be stale? 
                                     # Or logic: top card changed -> color usually top card color.
                                     pass
                                self.comm.send_to_backend(AnimationCompleteEvent())

                            self.animations.append(GUIAnimation(img, (sx, sy), (ex, ey), duration=15, on_complete=on_landed))
                    except Exception as e:
                        print(f"Anim error: {e}")

                elif event_name == "PlayerDrewCardEvent":
                    try:
                        pid = event.player_id
                        # count = event.count # Not used visually except maybe multiple animations?
                        
                        if self.screen:
                            w, h = self.screen.get_size()
                            positions = {
                                0: (w - 150, h - 100),
                                1: (w - 80, h // 2),
                                2: (w // 2, 120),
                                3: (80, h // 2)
                            }
                            v_idx = (pid - self.player_id) % 4
                            target_center = positions.get(v_idx, (0,0))
                            
                            # Start from Center Deck
                            sx = w // 2 + 100 # Offset of Draw Pile
                            sy = h // 2 - 60
                            ex = target_center[0] - CARD_WIDTH // 2
                            ey = target_center[1] - CARD_HEIGHT // 2
                            
                            img = AssetManager.get_instance().back_image
                            
                            def on_landed():
                                # Commit Buffered State
                                self.hand = self.server_hand
                                self.hand_counts = self.server_hand_counts
                                self.comm.send_to_backend(AnimationCompleteEvent())

                            self.animations.append(GUIAnimation(img, (sx, sy), (ex, ey), duration=15, on_complete=on_landed))

                    except Exception as e:
                        print(f"Draw Anim error: {e}")

                elif event_name == "AskMoveEvent":
                    if self.current_player_idx == self.player_id:
                        self.my_turn = True
                        self.message = "Your Turn! Select a card to play or Draw Pile."
                
                elif event_name == "AskChallengeEvent":
                    self.challenging = True
                    self.message = f"Challenge {event.victim_name}'s +4?" # victim_name was sent
                
                elif event_name == "AskPlayDrawnCardEvent":
                    self.answering_drawn = True
                    self.drawn_card_obj = event.card
                    
                    # Format card name
                    c_str = str(event.card)
                    # Strip ANSI codes
                    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                    c_str = ansi_escape.sub('', c_str)
                    
                    formatted_name = c_str.replace("Draw Two", "+2").replace("Draw Four", "+4").replace("Reverse", "~").replace("Skip", "!")
                    
                    c_rgb = ANSWER_DRAWN_COLOR_MAP.get(event.card.color, (0,0,0))
                    # Handle Wild +4 which might be WILD color
                    if event.card.color == CardColor.WILD:
                        c_rgb = (0, 0, 0)

                    self.message = [("You drew ", (0,0,0)), (formatted_name, c_rgb), (". Play it?", (0,0,0))]
                    
            except Exception as e:
                print(f"Error processing event: {e}")

    def _handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.comm.stop()
            elif event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    pos = pygame.mouse.get_pos()
                    if self.picking_color:
                        self._check_color_click(pos)
                    elif self.answering_drawn:
                        self._check_drawn_click(pos)
                    elif self.challenging:
                        self._check_challenge_click(pos)
                    elif self.my_turn:
                        self._check_click(pos)

    def _check_color_click(self, pos):
        for rect, color in self.color_picker_rects:
            if rect.collidepoint(pos):
                print(f"Picked Color: {color.value}")
                self.picking_color = False
                if self.color_pick_callback:
                    self.color_pick_callback(color)
                    self.color_pick_callback = None
                return

    def _check_drawn_click(self, pos):
        # We reuse loop logic or draw logic for yes/no buttons position
        # Positions: Center screen
        w, h = self.screen.get_size()
        dx, dy, dw, dh = w//2 - 150, h//2 - 100, 300, 200
        yes_rect = pygame.Rect(dx + 30, dy + 120, 100, 50)
        no_rect = pygame.Rect(dx + 170, dy + 120, 100, 50)
        
        if yes_rect.collidepoint(pos):
             print("Play Drawn Card: YES")
             # Check if Wild
             if self.drawn_card_obj.color == CardColor.WILD:
                 self.answering_drawn = False
                 self.picking_color = True
                 self.message = "Pick Color for Wild..."
                 self.color_pick_callback = lambda c: self.comm.send_to_backend(PlayDrawnCardResponseEvent(True, c))
             else:
                 self.comm.send_to_backend(PlayDrawnCardResponseEvent(True))
                 self.answering_drawn = False
                 self.message = "Waiting..."
        elif no_rect.collidepoint(pos):
             print("Play Drawn Card: NO")
             self.comm.send_to_backend(PlayDrawnCardResponseEvent(False))
             self.answering_drawn = False
             self.message = "Waiting..."

    def _check_challenge_click(self, pos):
        # Dynamic center rects calculation needed if positions are dynamic
        w, h = self.screen.get_size()
        dx, dy, dw, dh = w//2 - 150, h//2 - 100, 300, 200
        yes_rect = pygame.Rect(dx + 30, dy + 120, 100, 50)
        no_rect = pygame.Rect(dx + 170, dy + 120, 100, 50)

        if yes_rect.collidepoint(pos):
             print("Challenge: YES")
             self.comm.send_to_backend(ChallengeResponseEvent(True))
             self.challenging = False
             self.message = "Waiting..."
        elif no_rect.collidepoint(pos):
             print("Challenge: NO")
             self.comm.send_to_backend(ChallengeResponseEvent(False))
             self.challenging = False
             self.message = "Waiting..."

    def _check_click(self, pos):
        w, h = self.screen.get_size()
        
        # Check Skip Button
        # Logic must match _draw logic for Skip Button position
        # P0 at (w - 150, h - 100). Skip at ax + 80 = w - 70.
        ax = w - 150
        ay = h - 100
        bx = ax + 80
        by = ay
        skip_rect = pygame.Rect(0, 0, 80, 50)
        skip_rect.center = (bx, by)
        
        if skip_rect.collidepoint(pos):
             print("Skipping/Drawing...")
             self.comm.send_to_backend(DrawCardEvent())
             self.my_turn = False
             return

        # Check Draw Pile
        cx, cy = w//2, h//2 - 60
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
                
                # Check for Wild to trigger picker
                clicked_card = self.hand[index]
                if clicked_card.color == CardColor.WILD:
                    self.picking_color = True
                    self.message = "Pick Color..."
                    self.color_pick_callback = lambda c: self.comm.send_to_backend(PlayCardEvent(index, c))
                else:
                    self.comm.send_to_backend(PlayCardEvent(index, CardColor.RED)) 
                
                self.my_turn = False
                return

    def _draw(self):
        self.screen.fill((240, 234, 224)) # Zhuguosha Background Color
        w, h = self.screen.get_size()
        
        player_img = AssetManager.get_instance().player_image
        if not player_img:
             player_img = AssetManager.get_instance().back_image
        
        # Player Positions relative to view (pid 0 is human/self)
        # 4 Players: Bottom(0), Right(1), Top(2), Left(3)
        # Using fixed layout based on screen size
        positions = {
            0: (w - 150, h - 100),       # P0 (Self) - Shifted Right
            1: (w - 80, h // 2),        # P1
            2: (w // 2, 120),                        # P2 - Moved down (was 80)
            3: (80, h // 2)                        # P3
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
        cx, cy = w//2 - 40, h//2 - 60
        if self.top_card:
            img = AssetManager.get_instance().get_card_image(self.top_card)
            self.screen.blit(img, (cx, cy))
        else:
            pygame.draw.rect(self.screen, (0,0,0), (cx, cy, CARD_WIDTH, CARD_HEIGHT), 2)
            
        # Draw Draw Pile
        pile_img = AssetManager.get_instance().back_image
        # Try to show active color on the draw pile if available
        if self.active_color and self.active_color in [CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW]:
             alt_img = AssetManager.get_instance().get_default_card_image(self.active_color)
             if alt_img:
                 pile_img = alt_img

        if pile_img:
            self.screen.blit(pile_img, (cx + 100, cy))
        
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
            start_x = (w - total_width) // 2
            y = h - 140
            
            for i, card in enumerate(self.hand):
                x = start_x + i * 50
                img = AssetManager.get_instance().get_card_image(card)
                self.screen.blit(img, (x, y))
                self.card_rects.append((pygame.Rect(x, y, CARD_WIDTH, CARD_HEIGHT), i))
        
        # Draw Animations
        # Iterate backwards to remove safely
        for anim in self.animations[:]:
            anim.update()
            if anim.finished:
                self.animations.remove(anim)
            else:
                anim.draw(self.screen)

        # Draw Skip Button
        self.skip_rect = None
        if self.my_turn:
            # Position to the right of self avatar
            ax, ay = positions[0]
            # Moved slightly left (closer to avatar or left of it?) 
            # Previous was ax + 150. Reduced to ax + 80.
            bx = ax + 80 
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
        if self.challenging or self.answering_drawn:
            # overlay
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            s.fill((0,0,0,128))
            self.screen.blit(s, (0,0))
            
            # Dialog Box
            dx, dy, dw, dh = w//2 - 150, h//2 - 100, 300, 200
            pygame.draw.rect(self.screen, (255, 255, 255), (dx, dy, dw, dh))
            
            if font:
                 if isinstance(self.message, list):
                     total_w = sum(font.size(t)[0] for t, c in self.message)
                     h = font.get_height()
                     curr_x = dx + (dw - total_w) // 2
                     y = dy + 50 - h // 2
                     for t, c in self.message:
                         s = font.render(t, True, c)
                         self.screen.blit(s, (curr_x, y))
                         curr_x += s.get_width()
                 else:
                     msg_color = (0,0,0)
                     msg = font.render(self.message, True, msg_color)
                     self.screen.blit(msg, msg.get_rect(center=(dx+dw//2, dy+50)))
                 
            # Yes Button
            self.yes_rect = pygame.Rect(dx + 30, dy + 120, 100, 50)
            pygame.draw.rect(self.screen, (0, 200, 0), self.yes_rect) # Green
            if font:
                 label = "Yes" if self.answering_drawn else "Challenge"
                 t = font.render(label, True, (0,0,0))
                 self.screen.blit(t, t.get_rect(center=self.yes_rect.center))
                 
            # No Button
            self.no_rect = pygame.Rect(dx + 170, dy + 120, 100, 50)
            pygame.draw.rect(self.screen, (200, 0, 0), self.no_rect) # Red
            if font:
                 label = "No" if self.answering_drawn else "Pass"
                 t = font.render(label, True, (0,0,0))
                 self.screen.blit(t, t.get_rect(center=self.no_rect.center))

        # Draw Color Picker
        if self.picking_color:
             s = pygame.Surface((w, h), pygame.SRCALPHA)
             s.fill((0,0,0,128))
             self.screen.blit(s, (0,0))
             
             colors = [CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW]
             color_rgb = {
                 CardColor.RED: (200, 30, 30), 
                 CardColor.BLUE: (30, 30, 200),
                 CardColor.GREEN: (30, 200, 30),
                 CardColor.YELLOW: (200, 200, 0)
             }
             
             cx, cy = w//2, h//2
             size = 100
             offsets = [(-size-10, -size-10), (10, -size-10), (-size-10, 10), (10, 10)]
             
             self.color_picker_rects = []
             
             if font:
                 t = font.render("Pick a Color", True, (255,255,255))
                 self.screen.blit(t, t.get_rect(center=(cx, cy-150)))
             
             for i, c in enumerate(colors):
                 ox, oy = offsets[i]
                 rect = pygame.Rect(cx + ox, cy + oy, size, size)
                 pygame.draw.rect(self.screen, color_rgb[c], rect)
                 self.color_picker_rects.append((rect, c))


        # Draw Message
        if AssetManager.get_instance().font:
            font = AssetManager.get_instance().font
            if isinstance(self.message, list):
                curr_x, y = 20, 20
                for t, c in self.message:
                    s = font.render(t, True, c)
                    self.screen.blit(s, (curr_x, y))
                    curr_x += s.get_width()
            else:
                text = font.render(self.message, True, (0, 0, 0)) # Black text on light bg
                self.screen.blit(text, (20, 20))
            
            info = f"Current Player: {self.current_player_idx}"
            if self.my_turn: info += " (YOU)"
            info_text = AssetManager.get_instance().font.render(info, True, (255, 0, 0) if self.my_turn else (100, 100, 100))
            self.screen.blit(info_text, (20, 50))

        # Game Over Overlay
        if "Game Over" in self.message and AssetManager.get_instance().font:
             font = AssetManager.get_instance().font
             s = pygame.Surface((w, h), pygame.SRCALPHA)
             s.fill((0, 0, 0, 200)) # Dark semi-transparent
             self.screen.blit(s, (0,0))
             
             text = font.render(self.message, True, (255, 215, 0)) # Gold
             rect = text.get_rect(center=(w//2, h//2))
             self.screen.blit(text, rect)
             
             sub = font.render("Close window to exit", True, (200, 200, 200))
             sub_rect = sub.get_rect(center=(w//2, h//2 + 50))
             self.screen.blit(sub, sub_rect)

        pygame.display.flip()
