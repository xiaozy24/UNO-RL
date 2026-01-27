import time
from backend.player import Player
from backend.rl_player import RLPlayer
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from backend.utils.logger import game_logger
from backend.utils.colors import get_colored_text, TermColors
import random
import re

def main():
    # Start logging session
    log_path = game_logger.start_game_session()
    print(f"Logging to: {log_path}")

    # 1. Setup Players
    # One Human, One Simple AI, One RL AI
    p1 = Player(1, "Alice (Human)", PlayerType.HUMAN)
    p2 = RLPlayer(2, "Bob (RL)", model_path=None) # Initialize with random weights
    p3 = Player(3, "Charlie (Simple AI)", PlayerType.AI)
    players = [p1, p2, p3]

    # 2. Initialize Game
    gm = GameManager(players)
    gm.start_game()
    
    # Header
    print(f"{'Name':-<25} | {'Action':-<10} | {'Hand':-<4} | {'Color':-<6}")

    # 3. Game Loop
    turn_count = 0
    while not gm.game_over and turn_count < 1000:
        current_player = gm.get_current_player()
        top_card = gm.deck.peek_discard_pile()
        
        # Determine Action based on Player Type
        action_desc = ""
        
        # UNO Shout Check (Pre-move)
        if current_player.get_hand_size() == 2:
            # Technically should call UNO *before* playing the second to last card. 
            # Simplified: auto-shout if hand==2 (so after play it becomes 1)
            current_player.say_uno()

        if isinstance(current_player, RLPlayer):
            # --- RL Agent Logic ---
            action = current_player.choose_action(gm)
            
            if action['action_type'] == 'play':
                card = action['card']
                color = action.get('color')
                card_str = str(card)
                gm.play_card(current_player, card, color)
                action_desc = card_str
            else:
                gm.draw_card_action(current_player)
                action_desc = "Drawing"
                
        elif current_player.player_type == PlayerType.AI:
            # --- Simple AI Logic ---
            playable_card = None
            for card in current_player.hand:
                if gm.check_legal_play(card, top_card):
                    playable_card = card
                    break
            
            if playable_card:
                wild_color = None
                if playable_card.color == CardColor.WILD:
                    wild_color = CardColor.RED # Naive
                
                card_str = str(playable_card)
                gm.play_card(current_player, playable_card, wild_color)
                action_desc = card_str
            else:
                gm.draw_card_action(current_player)
                action_desc = "Drawing"
                
        else:
            # --- Human Logic (Simulated for now, acting as Simple AI) ---
            # In a real game, this would wait for Input.
            # Keeping simulation behavior for Alice as requested "Simple control" equivalent for now 
            # or should I implement input()? 
            # User said "retain existing Human control". Existing was a simulation loop.
            # I will keep it auto for "Alice" as per previous script behavior.
            
            playable_card = None
            for card in current_player.hand:
                if gm.check_legal_play(card, top_card):
                    playable_card = card
                    break
            
            if playable_card:
                wild_color = None
                if playable_card.color == CardColor.WILD:
                    wild_color = CardColor.RED 
                
                card_str = str(playable_card)
                gm.play_card(current_player, playable_card, wild_color)
                action_desc = card_str
            else:
                gm.draw_card_action(current_player)
                action_desc = "Drawing"

        # --- Output & Post-Turn ---
        current_color = gm.current_color
        current_color_val = current_color.value if current_color else "None"
        current_color_str = get_colored_text(current_color_val, current_color_val) if current_color else "None"
        
        display_action = action_desc.replace("Draw Two", "+2").replace("Draw Four", "+4").replace("Reverse", "~").replace("Skip", "!")

        # Format: Name (25) | Action (10) | Hand (4) | Color (6)
        p_str = f"{current_player.name:-<25}"
        
        # Action Coloring (Drawing -> Orange)
        # Calculate padding based on visible length (stripping ANSI codes)
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        plain_action = ansi_escape.sub('', display_action)
        a_pad = "-" * max(0, 10 - len(plain_action))

        if plain_action == "Drawing":
            a_str = f"{TermColors.ORANGE}{plain_action}{TermColors.RESET}{a_pad}"
        else:
            a_str = f"{display_action}{a_pad}"

        h_str = f"{str(current_player.get_hand_size()):-<4}"
        
        c_pad = "-" * max(0, 6 - len(current_color_val))
        c_str = f"{current_color_str}{c_pad}"
        
        print(f"{p_str} | {a_str} | {h_str} | {c_str}")

        if gm.skipped_player:
            sp_str = f"{gm.skipped_player.name:-<25}"
            # Skipped -> Brown
            s_text = "Skipped"
            s_pad = "-" * max(0, 10 - len(s_text))
            sa_str = f"{TermColors.BROWN}{s_text}{TermColors.RESET}{s_pad}"
            
            sh_str = f"{str(gm.skipped_player.get_hand_size()):-<4}"
            print(f"{sp_str} | {sa_str} | {sh_str} | {c_str}")

        turn_count += 1
        time.sleep(0.1)

    if gm.game_over:
        print(f"\nGame Over! Winner: {gm.winner.name}")
    else:
        print("\nGame Terminated (Max turns reached).")

if __name__ == "__main__":
    main()
