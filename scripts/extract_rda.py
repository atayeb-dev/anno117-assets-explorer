import argparse
import subprocess
import pathlib
from tkinter import Tk, filedialog

WORKDIR = pathlib.Path(__file__).resolve().parent.parent
RDA_CONSOLE_EXEC = f"{WORKDIR}/rda_console/RdaConsole.exe"


def extract_rda(rda_path, output_dir, filter_pattern=""):
    rda_path = pathlib.Path(rda_path)
    output_dir = pathlib.Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        RDA_CONSOLE_EXEC,
        "extract",
        "-f",
        rda_path,
        "-y",
        "-o",
        output_dir,
    ]
    if filter_pattern:
        cmd.extend(["--filter", filter_pattern])
    subprocess.run(cmd, check=True)


def select_file():
    root = Tk()
    root.withdraw()
    filepath = filedialog.askopenfilename(
        title="Select an RDA file",
        filetypes=[("RDA files", "*.rda"), ("All files", "*.*")],
    )
    return filepath


def main():

    parser = argparse.ArgumentParser(
        description="Extract RDA files for Anno 117 using RdaConsole (https://github.com/anno-mods/RdaConsole)."
    )

    parser.add_argument(
        "-i", "--input", type=pathlib.Path, help="Path to the .rda file to extract"
    )

    parser.add_argument(
        "-o",
        "--output",
        type=pathlib.Path,
        default=f"{WORKDIR}/unpacked",
        help="Output directory (default: ./unpacked)",
    )

    parser.add_argument(
        "--filter",
        type=str,
        default="",
        help="Optional regex pattern for rda extraction",
    )

    args = parser.parse_args()
    input = args.input
    if not input:
        input = select_file()
    output = args.output
    filter = argparse.filter
    print(f"extracting rda: {input} to {output}")
    if filter:
        print(f"Specified filter regex: {filter}")
    extract_rda(input, output, filter)
    print(f"Extraction complete")


if __name__ == "__main__":
    main()
