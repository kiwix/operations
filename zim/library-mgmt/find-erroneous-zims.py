#!/usr/bin/env python

import io
import logging
import os
import pathlib
import sys

import PIL.Image
from zimscraperlib.zim import Archive

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
    format="%(levelname)s %(message)s",
)
logger = logging.getLogger("find-script")

req_metadata = (
    "Counter",
    "Title",
    "Name",
    "Language",
)

common_metadata = (
    "Description",
    "Creator",
    "Publisher",
    # "Flavour",
    "Tags",
    "Date",
)

attributes = ("uuid", "filesize", "media_counter", "article_counter")


class Feedback:
    def __init__(self, fpath):
        self.fpath = fpath
        self.errors = {}

    def add(self, message, level=logging.WARNING):
        self.errors[message] = level

    @property
    def has_errors(self):
        return bool(self.errors)

    def print(self):
        if not self.has_errors:
            return

        content = f"{self.fpath}\n"
        for message, level in self.errors.items():
            content += f"  {logging.getLevelName(level)[0]}> {message}\n"
        logger.log(max(self.errors.values()), content)


def main(root: pathlib.Path):
    logger.info(f"Starting off {root}")
    for index, zim_path in enumerate(sorted(root.rglob("*.zim"), key=lambda f: f.name)):
        feedback = Feedback(zim_path.relative_to(root))
        logger.debug(f"[{index}] {zim_path}")

        try:
            zim = Archive(zim_path)
        except Exception as exc:
            feedback.add(f"Unreadable: {exc}", level=logging.ERROR)
            continue

        for name in req_metadata:
            try:
                zim.get_text_metadata(name)
            except RuntimeError:
                feedback.add(f"Missing {name} metadata", level=logging.ERROR)

        if not zim.has_illustration(48):
            feedback.add("Missing Illustration", level=logging.ERROR)
        else:
            if zim.get_illustration_item(48).mimetype != "image/png":
                feedback.add("Illustration is not PNG", level=logging.ERROR)
            else:
                with PIL.Image.open(
                    io.BytesIO(zim.get_illustration_item(48).content)
                ) as image:
                    if image.size != (48, 48):
                        feedback.add(
                            f"Illustration size is wrong: {image.size}",
                            logging.WARNING,
                        )

        for name in common_metadata:
            try:
                zim.get_text_metadata(name)
            except RuntimeError:
                feedback.add(f"Missing {name} metadata", level=logging.WARNING)

        for attr in attributes:
            if not getattr(zim, attr):
                feedback.add(
                    f"Invalid {attr}: {getattr(zim, attr)}", level=logging.ERROR
                )

        feedback.print()
    logger.info(f"Seen {index} ZIMs")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} ZIM_ROOT")
        sys.exit(1)
    sys.exit(main(pathlib.Path(sys.argv[1])))
