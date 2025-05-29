#!/usr/bin/env python3
import os
import json
import sys

from bot_helpers import logger


def build_resources(language: str = None, input_dir: str = ".", output_file: str = "res.json"):
    """
    Reads res.<lang>.json from input_dir and writes it to output_file.
    Only rebuilds if necessary.
    """
    if not language:
        language = os.getenv("BOT_LANG", "en")
    src = os.path.join(input_dir, f"res.{language}.json")

    if not os.path.isfile(src):
        logger.error(f"Error: source file {src!r} not found.")
        sys.exit(1)

    rebuild_needed = True
    if os.path.isfile(output_file):
        src_mtime = os.path.getmtime(src)
        out_mtime = os.path.getmtime(output_file)
        rebuild_needed = src_mtime > out_mtime
        logger.info(f"Source file timestamp: {src_mtime}")
        logger.info(f"Output file timestamp: {out_mtime}")

    if rebuild_needed:
        logger.info(f"Rebuilding {output_file} from {src}")
        with open(src, encoding="utf-8") as f:
            data = json.load(f)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        logger.info(f"Skipping rebuild of {output_file} (up to date)")