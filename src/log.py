# ============================================================
# ANSI Logging Utility
# ============================================================
from io import StringIO
from pprint import pprint
import random
import re
import sys
from time import sleep


indents = {
    "err": lambda m: f"{ansi_text(' ✗ ', 'red', ansi_codes=[0])}{m}",
    "err0": lambda m: f"{ansi_text('✗', 'red', ansi_codes=[0])}{m}",
    "succ": lambda m: f"{ansi_text(' ✓ ', 'green', ansi_codes=[0])}{m}",
    "succ0": lambda m: f"{ansi_text('✓', 'green', ansi_codes=[0])}{m}",
    "arr": lambda m: f"{ansi_text(' → ', 'blue', ansi_codes=[1])}{m}",
    "arr0": lambda m: f"{ansi_text('→', 'blue', ansi_codes=[1])}{m}",
    "ind": lambda m: f"{ansi_text('  ' * int(m), ansi_codes=[0])}",
}

colors = {
    "w": lambda m: ansi_text(m, "white"),
    "b": lambda m: ansi_text(m, "blue"),
    "c": lambda m: ansi_text(m, "cyan"),
    "y": lambda m: ansi_text(m, "yellow"),
    "r": lambda m: ansi_text(m, "red"),
    "g": lambda m: ansi_text(m, "green"),
}

help = {
    "hf": lambda m: ansi_text(m, "blue", ansi_codes=[1]),
    "hfl": lambda m: ansi_text(m, "blue", ansi_codes=[3]),
    "hv": lambda m: ansi_text(m, ansi_codes=[2]),
    "hvl": lambda m: ansi_text(m, ansi_codes=[2, 3]),
    "hur": lambda m: ansi_text(m, "yellow", ansi_codes=[1]),
    "hu": lambda m: ansi_text(m, "yellow", ansi_codes=[0]),
    "hul": lambda m: ansi_text(m, "yellow", ansi_codes=[3]),
    "fn": lambda m: ansi_text(m, "blue", ansi_codes=[1]),
    "fh": lambda m: ansi_text(m, "green", ansi_codes=[1]),
}

pprnt = {
    "ppi0": lambda m: ansi_text(m, "green", ansi_codes=[1]),
    "ppi1": lambda m: ansi_text(m, "cyan", ansi_codes=[1]),
    "ppi2": lambda m: ansi_text(m, "cyan", ansi_codes=[2]),
    "ppi3": lambda m: ansi_text(m, "cyan", ansi_codes=[2, 3]),
    "ppl0": lambda m: ansi_text(m, "white", ansi_codes=[0]),
    "ppl1": lambda m: ansi_text(m, "white", ansi_codes=[0]),
    "ppl2": lambda m: ansi_text(m, "white", ansi_codes=[2]),
    "ppl3": lambda m: ansi_text(m, "white", ansi_codes=[2, 3]),
}


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


def format_styled_text(
    text: str, styles: dict = help | indents | colors | pprnt
) -> str:
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


def clean(lines: int = 1):
    while lines > 0:
        lines -= 1
        sys.stdout.write("\033[F\033[K")  # Remonte + efface la ligne
        sys.stdout.flush()


def pp_log(data, stream: bool = False):
    """
    Pretty-print data using the logging utility.

    Args:
        data: Data to pretty-print.
    """
    import pprint

    pretty_text = pprint.pformat(data)
    buffer = StringIO()
    indentl = lambda i: f"{{ind/{i}}}"

    pretty_text = re.sub(r"\s+", "", pretty_text)
    indentcodes = sorted([f"{k}/" for k in pprnt if k.startswith("ppi")])
    leafcodes = sorted([f"{k}/" for k in pprnt if k.startswith("ppl")])
    sc = False
    vw = False
    indent = 0
    for char in pretty_text[1:-1]:
        ppi = indentcodes[min(indent, len(indentcodes) - 1)]
        if char == "'":
            if not vw:
                if not sc:
                    buffer.write(f"{{{ppi}[")
                    sc = True
                else:
                    buffer.write(f"]}}")
                    sc = False
            else:
                buffer.write(char)
        elif char == ":":
            vw = True
            ppl = leafcodes[min(indent, len(leafcodes) - 1)]
            buffer.write(f"{{arr/}}{{{ppl}")
        elif char == "{" or char == "[":
            indent += 1
            if vw:
                buffer.write("}")
            vw = False
            buffer.write("\n")
            buffer.write(indentl(indent))
        elif char == "}" or char == "]":
            indent -= 1
            buffer.write(indentl(indent))
            buffer.write("")
        elif char == ",":
            if vw:
                buffer.write("}")
            vw = False
            buffer.write("\n")
            buffer.write(indentl(indent))
        else:
            buffer.write(char)
        buffer.flush()

    if vw:
        buffer.write("}")
    pretty_text = buffer.getvalue()

    log(pretty_text, stream)


def log(message: str = "", stream: bool = False, nl: bool = True) -> None:
    """
    Log a message with styled text formatting and streaming.
    Args:
        message: Message to log.
        stream: If True, stream output character by character.
        nl: If True, print a newline at the end.
    """
    message = format_styled_text(message)

    if stream:
        loops = 0
        mod = 5
        # Stream mode: write character by character for visual effect
        for char in message:
            sys.stdout.write(char)
            if loops % mod == 0:
                loops = 0
                mod = random.randint(4, 7)
                sleep(
                    0.03 + random.random() * 0.06
                )  # Random delay between 30 and 60 ms
            loops += 1
            sleep(random.random() * 0.02)  # Random delay between 0 and 20 ms
            sys.stdout.flush()

    else:
        # Normal mode
        sys.stdout.write(message)
        sys.stdout.flush()
    if nl:
        print()  # Newline at the end


def log_args(args: dict):
    """
    Log command-line arguments in a formatted way.

    Args:
        args: Dictionary of command-line arguments.
    """
    log("Command-line Arguments:", stream=False)
    import pprint

    pprint.pprint(args)
