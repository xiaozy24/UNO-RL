import time
import random
from backend.player import Player
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from communicator.communicator import Communicator
from communicator.comm_event import UpdateHandEvent, UpdateStateEvent, AskMoveEvent, PlayCardEvent, DrawCardEvent, AskChallengeEvent, ChallengeResponseEvent, AskPlayDrawnCardEvent, PlayDrawnCardResponseEvent

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

def backend_main_loop(comm: Communicator, game_manager: GameManager, human_player_id: int):
    gm = game_manager
    gm.challenge_decider = make_challenge_decider(comm, human_player_id)
    gm.start_game()
    
    human = next((p for p in gm.players if p.player_id == human_player_id), None)
    if human:
        comm.send_to_frontend(UpdateHandEvent(human.hand))
    
    while not gm.game_over:
        current_player = gm.get_current_player()
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
                     card = gm.deck.draw_card()
                     if card:
                         current_player.add_card(card)
                         comm.send_to_frontend(UpdateHandEvent(current_player.hand))
                         
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
                             valid_move_made = True
                             comm.send_to_frontend(UpdateHandEvent(current_player.hand))
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
                        played = True
                        break
            
            if not played:
                card = gm.deck.draw_card()
                if card:
                    current_player.add_card(card)
                    if gm.check_legal_play(card, top_card):
                         choice = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                         gm.play_card(current_player, card, choice)
                    else:
                         gm._advance_turn()
                else:
                    gm._advance_turn()
            
            time.sleep(1)

    winner_name = gm.winner.name if gm.winner else "Nobody"
    comm.send_to_frontend(UpdateStateEvent(top_card, -1, f"Game Over! Winner: {winner_name}"))
