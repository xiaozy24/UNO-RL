import sys
import os
import unittest
import threading
import time

# Add parent directory to path to import modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from backend.game_manager import GameManager
from backend.player import Player
from backend.card import Card
from config.enums import PlayerType, CardColor, CardType
from communicator.communicator import Communicator
from communicator.comm_event import AskChallengeEvent, ChallengeResponseEvent
from backend.main_backend_loop import make_challenge_decider

class TestChallengeLogic(unittest.TestCase):
    def test_human_challenge_trigger(self):
        print("\n--- Testing Human Challenge Trigger ---")
        # 1. Setup
        comm = Communicator()
        # Correct Constructor: player_id, name, player_type
        p0 = Player(0, "AI", PlayerType.AI)
        p1 = Player(1, "Human", PlayerType.HUMAN)
        players = [p0, p1]
        
        gm = GameManager(players)
        
        # Inject the decider logic that connects to Communicator
        gm.challenge_decider = make_challenge_decider(comm, 1) # Position argument
        
        # 2. Prepare Scenario
        # P0 plays Wild Draw 4. P1 (Human) is next.
        # P0 needs a +4 in hand.
        wd4 = Card(CardColor.WILD, CardType.WILD_DRAW_FOUR)
        p0.add_card(wd4)
        # Give P0 another card of matching color (BLUE) so it IS a bluff.
        # Previous color is set to BLUE in step 4.
        p0.add_card(Card(CardColor.BLUE, CardType.NUMBER, 1))
        
        # Ensure it's P0's turn
        gm.current_player_index = 0
        
        # 3. Thread to handle the blocking wait and communicate
        def frontend_simulator():
            print("Simulator: Waiting for AskChallengeEvent...")
            # Wait for the event in the queue
            try:
                # We expect UpdateStateEvent first (from play_card updates usually) or just the AskChallengeEvent
                # But play_card calls resolve -> make_challenge_decider -> sends AskChallengeEvent.
                # It doesn't put other events before that in the synchronous block usually, 
                # although play_card logs info.
                
                # Loop until we get the challenge event or timeout
                start_time = time.time()
                while time.time() - start_time < 5:
                    if not comm.btf_queue.empty():
                        event = comm.btf_queue.get()
                        
                        # Handle both object and dict serialization if any happens (here objects are direct)
                        event_name = getattr(event, "my_event_name", type(event).__name__)
                        
                        print(f"Simulator: Received event '{event_name}'")
                        
                        if event_name == "AskChallengeEvent":
                            print("Simulator: SUCCESS - AskChallengeEvent identified!")
                            self.event_received = True
                            
                            # Send response to unblock backend
                            print("Simulator: Sending ChallengeResponseEvent(True)...")
                            resp = ChallengeResponseEvent(True)
                            comm.ftb_queue.put(resp)
                            return
                    else:
                        time.sleep(0.1)
                
                print("Simulator: Timeout waiting for AskChallengeEvent")
                self.event_received = False

            except Exception as e:
                print(f"Simulator: Error: {e}")
                self.event_received = False

        self.event_received = False
        t = threading.Thread(target=frontend_simulator)
        t.daemon = True
        t.start()
        
        # 4. Trigger Action (This will block until simulator sends response)
        print("Main: AI playing Wild Draw 4...")
        
        # Set a color so not None
        gm.current_color = CardColor.BLUE
        
        # This call blocks inside resolve_pending_wild_draw_four -> proper_decider -> comm.get()
        success = gm.play_card(p0, wd4, CardColor.RED)
        
        print(f"Main: Play finished. Success: {success}")
        
        t.join(timeout=6)
        
        self.assertTrue(self.event_received, "Should have received AskChallengeEvent in frontend queue")
        self.assertTrue(success, "The card play should be successful")
        self.assertEqual(gm.last_challenge_result, "Succeeded", "AI had Blue card matching Blue background, so +4 was illegal (Bluff). Challenge should succeed.")

if __name__ == "__main__":
    unittest.main()
