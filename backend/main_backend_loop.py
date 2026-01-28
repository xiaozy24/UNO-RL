import time
import random
from backend.player import Player
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from communicator.communicator import Communicator
from communicator.comm_event import UpdateHandEvent, UpdateStateEvent, AskMoveEvent, PlayCardEvent, DrawCardEvent, AskChallengeEvent, ChallengeResponseEvent, AskPlayDrawnCardEvent, PlayDrawnCardResponseEvent, PlayerPlayedCardEvent,  PlayerDrewCardEvent, AnimationCompleteEvent

def make_challenge_decider(comm: Communicator, human_pid: int):
    def decider(victim, previous_color):
        if victim.player_type != PlayerType.HUMAN:
            # Simple AI logic: Challenge ~30%
            return random.random() < 0.3
        
        # Human decision needed
        comm.send_to_frontend(AskChallengeEvent(victim.name))
        
        while True:
            event = comm.ftb_queue.get()
            name = getattr(event, "my_event_name", type(event).__name__)
            if name == "ChallengeResponseEvent":
                return event.challenge
            # Ignore other events (like duplicate plays) or re-queue them if critical
            # Ideally we should only get ChallengeResponse here because UI mode blocks other inputs
    
    return decider

def wait_for_animation(comm: Communicator):
    """Blocks until AnimationCompleteEvent is received."""
    start_time = time.time()
    while True:
        # Check timeout? 2-3 seconds max for animation
        if time.time() - start_time > 3.0:
            break
            
        try:
            # Peek or get loop? We need to filter specific events.
            # Using get() might steal events meant for other parts if logic was complex,
            # but in this synchronous block phase, we expect ONLY AnimComplete or harmless noise.
            
            # Since ftb_queue is FIFO, if there are other events (like clicks buffered), they might block us.
            # But during animation, UI should block input.
            
            event = comm.ftb_queue.get(timeout=0.1)
            name = getattr(event, "my_event_name", type(event).__name__)
            if name == "AnimationCompleteEvent":
                return
            # If other events, maybe re-queue or ignore? 
            # Ideally UI blocks user input during animation.
        except:
            pass

def send_sync_state(comm: Communicator, gm: GameManager):
    counts = {p.player_id: len(p.hand) for p in gm.players}
    comm.send_to_frontend(UpdateStateEvent(
        top_card=gm.deck.peek_discard_pile(), 
        current_player_index=gm.current_player_index, 
        msg="", 
        hand_counts=counts, 
        active_color=gm.current_color
    ))

def backend_main_loop(comm: Communicator, game_manager: GameManager, human_player_id: int):
    gm = game_manager
    
    # Define Callbacks
    def on_play_anim(pid, card):
        comm.send_to_frontend(PlayerPlayedCardEvent(pid, card))
        send_sync_state(comm, gm)
        if pid == human_player_id:
             p = next((x for x in gm.players if x.player_id == pid), None)
             if p:
                 comm.send_to_frontend(UpdateHandEvent(p.hand))
        wait_for_animation(comm)
        
    def on_draw_anim(pid, count=1):
        comm.send_to_frontend(PlayerDrewCardEvent(pid, count))
        send_sync_state(comm, gm)
        if pid == human_player_id:
             p = next((x for x in gm.players if x.player_id == pid), None)
             if p:
                 comm.send_to_frontend(UpdateHandEvent(p.hand))
        wait_for_animation(comm)
        
    gm.on_play_card_animation = on_play_anim
    gm.on_draw_card_animation = on_draw_anim
    
    gm.challenge_decider = make_challenge_decider(comm, human_player_id)
    gm.start_game()
    
    human = next((p for p in gm.players if p.player_id == human_player_id), None)
    if human:
        comm.send_to_frontend(UpdateHandEvent(human.hand))
    
    # prev_hand_counts is removed because we now use explicit events in GameManager callbacks
    
    while not gm.game_over:
        current_player = gm.get_current_player()
        
        # Check for draws... REMOVED since we hook into GM now.
        # But we still need to send UpdateHandEvent implicitly?
        # The callbacks send PlayerDrewCardEvent, but UpdateHandEvent carries the list.
        # We can send UpdateHandEvent manually in the loop like before.

        top_card = gm.deck.peek_discard_pile()
        
        color_info = ""
        if gm.current_color:
             color_info = f"Current Color: {gm.current_color.value}"
        else:
             color_info = f"Top Card Color: {top_card.color.value if top_card else 'None'}"
             
        msg = f"Turn: {current_player.name}. {color_info}"
        
        # Determine active color for GUI display
        active_color = gm.current_color if gm.current_color else (top_card.color if top_card else None)
        
        # Collect hand counts
        hand_counts = {p.player_id: len(p.hand) for p in gm.players}
        comm.send_to_frontend(UpdateStateEvent(top_card, current_player.player_id, msg, hand_counts, active_color=active_color))
        
        if human and current_player.player_id == human.player_id: 
             comm.send_to_frontend(UpdateHandEvent(human.hand))

        time.sleep(0.5)

        if current_player.player_type == PlayerType.HUMAN:
            comm.send_to_frontend(AskMoveEvent())
            
            valid_move_made = False
            while not valid_move_made and not gm.game_over:
                event = comm.ftb_queue.get()
                name = getattr(event, "my_event_name", type(event).__name__)
                
                if name == "DrawCardEvent":
                     # Use internal draw mech to trigger animate callback
                     if self_draw_helper(gm, current_player): 
                         comm.send_to_frontend(UpdateHandEvent(current_player.hand))
                         
                         card = current_player.hand[-1] # roughly last card
                         top_card = gm.deck.peek_discard_pile() # refresh
                         
                         # Check if playable
                         if gm.check_legal_play(card, top_card):
                             comm.send_to_frontend(AskPlayDrawnCardEvent(card))
                             
                             valid_response = False
                             while not valid_response:
                                 resp = comm.ftb_queue.get()
                                 r_name = getattr(resp, "my_event_name", type(resp).__name__)
                                 if r_name == "PlayDrawnCardResponseEvent":
                                     if resp.play:
                                         choice = resp.color_choice
                                         # Logic to ensure proper play
                                         if gm.play_card(current_player, card, choice):
                                             # PlayerPlayedCardEvent sent inside play_card callback
                                             comm.send_to_frontend(UpdateHandEvent(current_player.hand))
                                             valid_move_made = True
                                         else:
                                             # Valid check passed earlier, so this is rare.
                                             # Maybe state changed or bug.
                                             gm._advance_turn()
                                             valid_move_made = True
                                     else:
                                         gm._advance_turn()
                                         valid_move_made = True
                                     valid_response = True
                         else:
                             gm._advance_turn()
                             valid_move_made = True
                     else:
                         gm._advance_turn()
                         valid_move_made = True
                         
                elif name == "PlayCardEvent":
                     idx = event.card_index
                     if 0 <= idx < len(current_player.hand):
                         card = current_player.hand[idx]
                         
                         choice = event.color_choice
                         if not choice and card.color == CardColor.WILD:
                             choice = CardColor.RED # Default fallback
                             
                         if gm.play_card(current_player, card, choice):
                             # Played event sent in callback
                             valid_move_made = True
                             send_sync_state(comm, gm)
                         else:
                             comm.send_to_frontend(UpdateStateEvent(top_card, current_player.player_id, "Illegal Move! Try again.", active_color=active_color))
                             comm.send_to_frontend(AskMoveEvent())
                     else:
                         pass
        else:
            # AI Logic
            played = False
            for card in current_player.hand:
                if gm.check_legal_play(card, top_card):
                    choice = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                    if gm.play_card(current_player, card, choice):
                        # Played event sent in callback
                        played = True
                        send_sync_state(comm, gm)
                        break
            
            if not played:
                # Use helper to trigger animation callback
                if self_draw_helper(gm, current_player):
                    card = current_player.hand[-1]
                    top_card = gm.deck.peek_discard_pile() # refresh
                    
                    if gm.check_legal_play(card, top_card):
                         choice = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                         gm.play_card(current_player, card, choice)
                         send_sync_state(comm, gm)
                    else:
                         gm._advance_turn()
                else:
                    gm._advance_turn()
            
            
            time.sleep(1)

    winner_name = gm.winner.name if gm.winner else "Nobody"
    # We might need top_card. If loop ran, it is defined. If not, peek.
    top_card = gm.deck.peek_discard_pile()
    comm.send_to_frontend(UpdateStateEvent(top_card, -1, f"Game Over! Winner: {winner_name}", active_color=gm.current_color))

def self_draw_helper(gm, player):
    # gm.deck.draw_card() manual call bypassed callbacks.
    # We need a way to invoke _perform_single_draw from outside or expose it.
    # Since _perform_single_draw is private in GM but we need it here.
    # Let's add a public wrapper in GM or access it.
    # Or just replicate logic:
    
    # Actually, better to expose a `gm.draw_card_for_player(player)` method.
    # But since I cannot easily add method and update calls in one hunk without context of the whole class,
    # I'll rely on the existing _perform_single_draw IF I made it public (I didn't rename it yet).
    # I replaced _perform_single_draw def with private. 
    # Let's use `gm._perform_single_draw(player)` (Python allows access).
    c = gm._perform_single_draw(player)
    return c is not None
