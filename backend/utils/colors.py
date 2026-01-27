class TermColors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def get_colored_text(text: str, color_name: str) -> str:
    """
    Apply generic color based on string content (e.g. 'Red', 'Blue').
    This is simple matching for the specific enum values.
    """
    code = TermColors.RESET
    upper_text = str(text).upper()
    
    if "RED" in upper_text:
        code = TermColors.RED
    elif "BLUE" in upper_text:
        code = TermColors.BLUE
    elif "GREEN" in upper_text:
        code = TermColors.GREEN
    elif "YELLOW" in upper_text:
        code = TermColors.YELLOW
    elif "WILD" in upper_text:
        code = TermColors.MAGENTA
        
    return f"{code}{text}{TermColors.RESET}"
