import time
from backend.player import Player
from backend.rl_player import RLPlayer
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from backend.utils.logger import game_logger
from backend.utils.colors import get_colored_text
import random

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

    # 3. Game Loop
    turn_count = 0
    while not gm.game_over and turn_count < 1000:
        current_player = gm.get_current_player()
        top_card = gm.deck.peek_discard_pile()
        
        # Determine Action based on Player Type
        action_text = ""
        
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
                action_text = f"{current_player.name} {card_str}"
            else:
                gm.draw_card_action(current_player)
                action_text = f"{current_player.name} drawing"
                
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
                action_text = f"{current_player.name} {card_str}"
            else:
                gm.draw_card_action(current_player)
                action_text = f"{current_player.name} drawing"
                
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
                action_text = f"{current_player.name} {card_str}"
            else:
                gm.draw_card_action(current_player)
                action_text = f"{current_player.name} drawing"

        # --- Output & Post-Turn ---
        current_color = gm.current_color
        current_color_str = "None"
        if current_color:
            current_color_str = get_colored_text(current_color.value, current_color.value)
        
        print(f"{action_text} | {current_player.get_hand_size()} | {current_color_str}")

        if gm.skipped_player:
             # Just checking if skipped_player works needs name
             print(f"{gm.skipped_player.name} skipped | {gm.skipped_player.get_hand_size()} | {current_color_str}")

        turn_count += 1
        time.sleep(0.1)

    if gm.game_over:
        print(f"\nGame Over! Winner: {gm.winner.name}")
    else:
        print("\nGame Terminated (Max turns reached).")

if __name__ == "__main__":
    main()
