import threading
import sys
import os

# Ensure UNO-RL to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from communicator.communicator import Communicator
from frontend.gui import UNOGUI
from backend.main_backend_loop import backend_main_loop
from backend.game_manager import GameManager
from backend.player import Player
from config.enums import PlayerType

def main():
    print("Starting UNO-RL Integrated Mode...")
    # 1. Init Communicator
    comm = Communicator()
    
    # 2. Setup Game (1 Human, 3 Bots)
    p1 = Player(0, "You", PlayerType.HUMAN)
    p2 = Player(1, "Bot-A", PlayerType.AI)
    p3 = Player(2, "Bot-B", PlayerType.AI)
    p4 = Player(3, "Bot-C", PlayerType.AI)
    
    players = [p1, p2, p3, p4]
    gm = GameManager(players)
    
    # 3. Start Backend Thread
    backend_thread = threading.Thread(target=backend_main_loop, args=(comm, gm, 0), daemon=True)
    backend_thread.start()
    
    # 4. Start Frontend (Main Thread)
    gui = UNOGUI(comm, 0)
    gui.run()

if __name__ == "__main__":
    main()
