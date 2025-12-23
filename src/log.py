# ============================================================
# ANSI Logging Utility
# ============================================================
import re
import sys


def ansi_text(text: str, color: str = "default", ansi_codes: list[int] = [0]) -> str:
    """
    Wrap text with ANSI escape codes for color and style.

    Args:
        text: Text to format.
        color: Color name (red, green, yellow, blue, magenta, cyan, white, default).
        style: Style code (0=normal, 1=bold, 3=italic, 4=underline).

    Returns:
        Formatted text with ANSI codes.
    """
    color_code = "37"  # Default white
    if color == "red":
        color_code = 31
    elif color == "green":
        color_code = 32
    elif color == "yellow":
        color_code = 33
    elif color == "blue":
        color_code = 34
    elif color == "magenta":
        color_code = 35
    elif color == "cyan":
        color_code = 36
    elif color == "white":
        color_code = 37

    ansi_start = f"\033[{';'.join(str(code) for code in ansi_codes)};{color_code}m"
    ansi_end = "\033[0m"
    return f"{ansi_start}{text}{ansi_end}"


def format_styled_text(text: str, styles: dict = None) -> str:
    """
    Format text with custom inline style tags.

    Args:
        text: Text with {tag}content{/tag} placeholders
        styles: Dict mapping tag names to style functions

    Returns:
        Formatted text with styles applied

    Example:
        text = format_styled_text(
            "This is {bold}important{/bold} and {error}critical{/error}",
            styles={
                "bold": lambda x: ansi_text(x, ansi_codes=[1]),
                "error": lambda x: ansi_text(x, "red", [1]),
                "success": lambda x: ansi_text(x, "green", [1])
            }
        )
    """
    if not styles:
        return text

    result = text
    for tag_name, style_func in styles.items():
        pattern = r"\{" + rf"{tag_name}/" + r"(.*?)\}"
        result = re.sub(pattern, lambda m: style_func(m.group(1)), result)

    return result


styles = {
    "hf": lambda x: ansi_text(x, "blue", ansi_codes=[1]),
    "hfl": lambda x: ansi_text(x, "blue", ansi_codes=[3]),
    "hv": lambda x: ansi_text(x, ansi_codes=[2]),
    "hvl": lambda m: ansi_text(m, ansi_codes=[2, 3]),
    "hur": lambda x: ansi_text(x, "yellow", ansi_codes=[1]),
    "hu": lambda x: ansi_text(x, "yellow", ansi_codes=[0]),
    "hul": lambda x: ansi_text(x, "yellow", ansi_codes=[3]),
    "fn": lambda m: ansi_text(m, "blue", ansi_codes=[1]),
    "fh": lambda m: ansi_text(m, "green", ansi_codes=[1]),
    "b": lambda x: ansi_text(x, "blue"),
    "c": lambda x: ansi_text(x, "cyan"),
    "y": lambda x: ansi_text(x, "yellow"),
    "r": lambda x: ansi_text(x, "red"),
    "g": lambda x: ansi_text(x, "green"),
    "err": lambda m: f"{ansi_text('✗', 'red', ansi_codes=[1])} {m}",
    "succ": lambda m: f"{ansi_text('✓', 'green', ansi_codes=[1])} {m}",
}


def log(message: str, stream=False) -> None:
    """
    Log a message with styled text formatting and streaming.
    Args:
        message: Message to log.
        stream: If True, stream output character by character.
    """
    message = format_styled_text(message, styles=styles)

    if stream:
        # Stream mode: write character by character for visual effect
        for char in message:
            sys.stdout.write(char)
            from time import sleep

            sleep(0.01)
            sys.stdout.flush()
        print()  # Newline at the end
    else:
        # Normal mode
        print(message)


def log_args(args: dict):
    """
    Log command-line arguments in a formatted way.

    Args:
        args: Dictionary of command-line arguments.
    """
    log("Command-line Arguments:", stream=False)
    import pprint

    pprint.pprint(args)
