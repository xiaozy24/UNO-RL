import time
from backend.player import Player
from backend.rl_player import RLPlayer
from backend.game_manager import GameManager
from config.enums import PlayerType, CardColor
from backend.utils.logger import game_logger
from backend.utils.colors import get_colored_text, TermColors
import random
import re

def print_interactive_msg(msg: str):
    """Print a message padded to the standard table width (54 chars including separators)."""
    # Standard line: 25 + 3 + 10 + 3 + 4 + 3 + 6 = 54
    total_len = 54
    # Strip ANSI codes for length calculation
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    plain_msg = ansi_escape.sub('', msg)
    
    padding = max(0, total_len - len(plain_msg))
    print(f"{msg}{'-' * padding}")

def format_card_name(card_name: str) -> str:
    """Format card name for display (e.g. Draw Two -> +2)."""
    return card_name.replace("Draw Two", "+2").replace("Draw Four", "+4").replace("Reverse", "~").replace("Skip", "!")


def ai_challenge_decider(victim, previous_color):
    """Simple AI always challenges +4 if it has valid cards (bluff check) or randomly?"""
    # For now, Simple AI / RL Agent will simply challenge 50% of the time or simple heuristic
    # Let's say: if victim has a lot of cards, maybe they don't care, if few, they care?
    # Or just random 30% challenge rate for variety.
    return random.random() < 0.3

def human_challenge_decider(victim, previous_color):
    """Return True if human victim chooses to challenge +4."""
    if getattr(victim, "player_type", None) != PlayerType.HUMAN:
        # Delegate to AI logic if victim is not human (e.g. RL vs Simple AI)
        return ai_challenge_decider(victim, previous_color)
        
    print_interactive_msg("[Challenge +4?]{1. Yes, 2. No}")
    while True:
        try:
            user_input = input("Input:")
            choice = int(user_input)
            if choice == 1:
                return True
            if choice == 2:
                return False
            print_interactive_msg("[Illegal Input]")
        except ValueError:
            print_interactive_msg("[Illegal Input]")

def main():
    # Start logging session
    log_path = game_logger.start_game_session()
    print(f"Logging to: {log_path}")

    # 1. Setup Players
    # One Human, One Simple AI, One RL AI
    p1 = Player(1, "Alice (HumanBack)", PlayerType.HUMAN)
    p2 = RLPlayer(2, "Bob (RL)", model_path=None) # Initialize with random weights
    p3 = Player(3, "Charlie (Simple AI)", PlayerType.AI)
    players = [p1, p2, p3]

    # 2. Initialize Game
    gm = GameManager(players)
    # Hook challenge decider for +4
    gm.challenge_decider = human_challenge_decider
    start_card = gm.start_game()
    
    # Header
    print(f"{'Name':-<25} | {'Action':-<10} | {'Hand':-<4} | {'Color':-<6}")

    # Display First Card
    print_interactive_msg(f"[First Card]{{{start_card}}}")

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
                # RL chose to 'draw' (usually means no legal move in current implementation)
                # Mimic 'Skip and Draw' logic:
                # 1. Draw card manually (game_manager.draw_card_action advances turn, so we do it manually to check playability)
                drawn_card = gm.deck.draw_card()
                if drawn_card:
                    current_player.add_card(drawn_card)
                    
                    # 2. Check playability
                    if gm.check_legal_play(drawn_card, top_card):
                        # Simple Heuristic: Always play if legal (to win faster)
                        wild_color = None
                        if drawn_card.color == CardColor.WILD:
                             wild_color = random.choice([CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW])
                        
                        gm.play_card(current_player, drawn_card, wild_color)
                        action_desc = f"{str(drawn_card)} (Drew)"
                    else:
                        gm._advance_turn()
                        action_desc = "Drawing"
                else:
                    gm._advance_turn()
                    action_desc = "Drawing"

                
        elif current_player.player_type == PlayerType.AI:
            # --- Simple AI Logic ---
            # 1. Determine if we WANT to play a card or Skip (0).
            # Simple AI: Always play if possible.
            legal_cards = [c for c in current_player.hand if gm.check_legal_play(c, top_card)]
            
            playable_card = None
            if legal_cards:
                # Simple AI always picks first legal card (no skipping strategy yet)
                playable_card = legal_cards[0]
            
            if playable_card:
                wild_color = None
                if playable_card.color == CardColor.WILD:
                    wild_color = CardColor.RED # Naive
                
                card_str = str(playable_card)
                gm.play_card(current_player, playable_card, wild_color)
                action_desc = card_str
            else:
                # Must Draw
                drawn_card = gm.deck.draw_card()
                if drawn_card:
                    current_player.add_card(drawn_card)
                    
                    if gm.check_legal_play(drawn_card, top_card):
                        # Play immediately
                        wild_color = None
                        if drawn_card.color == CardColor.WILD:
                            wild_color = CardColor.RED # Naive
                        
                        gm.play_card(current_player, drawn_card, wild_color)
                        action_desc = f"{str(drawn_card)} (Drew)"
                    else:
                        gm._advance_turn()
                        action_desc = "Drawing"
                else:
                    gm._advance_turn()
                    action_desc = "Drawing"
                
        else:
            # --- HumanBack Logic ---
            # Interaction Logic
            if gm.skipped_player == current_player: # Although skipped player usually doesn't reach here
                print_interactive_msg("[Skipped]")
            else:
                legal_cards = [c for c in current_player.hand if gm.check_legal_play(c, top_card)]
                
                if legal_cards:
                    # Show Hand Cards
                    hand_str = ", ".join([format_card_name(str(c)) for c in current_player.hand])
                    print_interactive_msg(f"[Hand Cards]{{{hand_str}}}")

                    # Construct available cards string
                    # Add 0. Skip option
                    card_options = [f"{i+1}. {format_card_name(str(c))}" for i, c in enumerate(legal_cards)]
                    cards_str = "0. Skip, " + ", ".join(card_options)
                    print_interactive_msg(f"[Available Cards]{{{cards_str}}}")
                    
                    while True:
                        try:
                            user_input = input("Input:")
                            choice = int(user_input)
                            
                            # CHOICE 0: SKIP & DRAW
                            if choice == 0:
                                drawn_card = gm.deck.draw_card()
                                if drawn_card:
                                    current_player.add_card(drawn_card)
                                    print_interactive_msg(f"[Skip and Draw]{{{drawn_card}}}")
                                    
                                    if gm.check_legal_play(drawn_card, top_card):
                                        print_interactive_msg("[Use?]{1. Yes, 2. No}")
                                        while True:
                                            try:
                                                use_input = input("Input:")
                                                use_choice = int(use_input)
                                                if use_choice == 1:
                                                    # Play the drawn card
                                                    wild_color = None
                                                    if drawn_card.color == CardColor.WILD:
                                                        colors = [CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW]
                                                        colored_options = [f"{i+1}. {get_colored_text(c.value, c.value)}" for i, c in enumerate(colors)]
                                                        options_str = ", ".join(colored_options)
                                                        print_interactive_msg(f"[Choose Color]{{{options_str}}}")
                                                        while True:
                                                            try:
                                                                color_input = input("Input:")
                                                                c_choice = int(color_input)
                                                                if 1 <= c_choice <= 4:
                                                                    wild_color = colors[c_choice - 1]
                                                                    break
                                                                print_interactive_msg("[Illegal Input]")
                                                            except ValueError:
                                                                print_interactive_msg("[Illegal Input]")
                                                    
                                                    gm.play_card(current_player, drawn_card, wild_color)
                                                    action_desc = str(drawn_card)
                                                    break
                                                elif use_choice == 2:
                                                    # Keep card, pass turn
                                                    gm._advance_turn()
                                                    action_desc = "Drawing"
                                                    break
                                                else:
                                                    print_interactive_msg("[Illegal Input]")
                                            except ValueError:
                                                print_interactive_msg("[Illegal Input]")
                                    else:
                                        # Cannot play drawn card
                                        gm._advance_turn()
                                        action_desc = "Drawing"
                                else:
                                    # Deck empty (rare/handled usually)
                                    gm._advance_turn()
                                    action_desc = "Drawing"
                                break

                            elif 1 <= choice <= len(legal_cards):
                                card = legal_cards[choice - 1]
                                
                                # Wild Color Selection
                                wild_color = None
                                if card.color == CardColor.WILD:
                                    colors = [CardColor.RED, CardColor.BLUE, CardColor.GREEN, CardColor.YELLOW]
                                    # Format options with colors
                                    colored_options = [f"{i+1}. {get_colored_text(c.value, c.value)}" for i, c in enumerate(colors)]
                                    options_str = ", ".join(colored_options)
                                    print_interactive_msg(f"[Choose Color]{{{options_str}}}")

                                    while True:
                                        try:
                                            color_input = input("Input:")
                                            c_choice = int(color_input)
                                            if 1 <= c_choice <= 4:
                                                wild_color = colors[c_choice - 1]
                                                break
                                            else:
                                                print_interactive_msg("[Illegal Input]")
                                        except ValueError:
                                            print_interactive_msg("[Illegal Input]") 

                                card_str = str(card)
                                gm.play_card(current_player, card, wild_color)
                                action_desc = card_str
                                break
                            else:
                                print_interactive_msg("[Illegal Input]")
                        except ValueError:
                            print_interactive_msg("[Illegal Input]")
                else:
                    # No legal moves -> Auto draw
                    gm.draw_card_action(current_player)
                    action_desc = "Drawing"
            
            # --- HumanFront Logic (Empty) ---
            # Waiting for completion
            pass

        # --- Output & Post-Turn ---
        current_color = gm.current_color
        current_color_val = current_color.value if current_color else "None"
        current_color_str = get_colored_text(current_color_val, current_color_val) if current_color else "None"
        
        display_action = format_card_name(action_desc)

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

        # Resolve +4 challenge after action output (if pending)
        challenge_result = gm.resolve_pending_wild_draw_four()
        if challenge_result == "Succeeded":
            print_interactive_msg("[Challenge Succeeded]")
        elif challenge_result == "Failed":
            print_interactive_msg("[Challenge Failed]")

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
