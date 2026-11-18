# SPDX-License-Identifier: MIT
"""Write the verified edition to the contest's output directory."""

import os
from pathlib import Path
from struct import unpack


def main() -> None:
    source = Path(__file__).resolve().with_name("entry.png")
    edition = source.read_bytes()
    if not edition.startswith(b"\x89PNG\r\n\x1a\n") or edition[12:16] != b"IHDR":
        raise ValueError("edition is not a PNG")
    width, height = unpack(">II", edition[16:24])
    if len(edition) > 1_048_576 or not (0 < width <= 1024 and 0 < height <= 1024):
        raise ValueError("edition exceeds the contest limits")

    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "entry.png").write_bytes(edition)


if __name__ == "__main__":
    main()
