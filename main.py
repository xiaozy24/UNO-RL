import time
from backend.player import Player
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from backend.utils.logger import game_logger
from backend.utils.colors import get_colored_text

def main():
    # Start logging session
    log_path = game_logger.start_game_session()
    print(f"Logging to: {log_path}")

    # 1. Setup Players
    p1 = Player(1, "Alice (Human)", PlayerType.HUMAN)
    p2 = Player(2, "Bob (AI)", PlayerType.AI)
    p3 = Player(3, "Charlie (AI)", PlayerType.AI)
    players = [p1, p2, p3]

    # 2. Initialize Game
    gm = GameManager(players)
    gm.start_game()

    # 3. Simple Simulation Loop (Auto-play for testing)
    turn_count = 0
    while not gm.game_over and turn_count < 100:
        current_player = gm.get_current_player()
        top_card = gm.deck.peek_discard_pile()
        
        # Simple AI Logic for everyone for testing
        playable_card = None
        for card in current_player.hand:
            if gm.check_legal_play(card, top_card):
                playable_card = card
                break
        
        if playable_card:
            # Pick color for Wild
            wild_color = None
            if playable_card.color == CardColor.WILD:
                # Naive strategy: Pick most frequent color in hand
                # Or just random
                wild_color = CardColor.RED # Simplified
            
            # Simulate "UNO" call
            if current_player.get_hand_size() == 2:
                current_player.say_uno()
            
            # Capture card string BEFORE playing because play_card might discard it into pile (ref handled)
            # but more importantly we want to print it.
            # Actually Card object __str__ handles color.
            card_str = str(playable_card)
            
            gm.play_card(current_player, playable_card, wild_color)
            action_text = f"{current_player.name} {card_str}"
        else:
            gm.draw_card_action(current_player)
            action_text = f"{current_player.name} drawing"
            
        # Print Active Color
        current_color = gm.current_color
        current_color_str = "None"
        if current_color:
            current_color_str = get_colored_text(current_color.value, current_color.value)
        
        print(f"{action_text} | {current_player.get_hand_size()} | {current_color_str}")

        # Check for skipped player
        if gm.skipped_player:
             # Use white/default color or maybe grey? keeping it simple or maybe format matches standard.
             print(f"{gm.skipped_player.name} skipped | {gm.skipped_player.get_hand_size()} | {current_color_str}")

        turn_count += 1
        time.sleep(0.1)

    if gm.game_over:
        print(f"\nGame Over! Winner: {gm.winner.name}")
    else:
        print("\nGame Terminated (Max turns reached).")

if __name__ == "__main__":
    main()
