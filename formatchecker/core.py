#
# Copyright 2023-2024 Haiku, Inc. All rights reserved.
# Distributed under the terms of the MIT License.
#
# Authors:
#  Niels Sascha Reedijk, niels.reedijk@gmail.com
#
"""
This module contains the core high-level objects and functions that are used to fetch a change,
reformat it, and publish those changes back to Gerrit.
"""
import json
import logging
import re
import sys

from .gerrit import Context
from .models import Change, ReviewInput, CommentRange, CommentInput, ReformatType, strip_empty_values_from_input_dict, \
    NotifyEnum
from .llvm import run_clang_format

EXTENSION_PATTERN = (r"^.*\.(?:cpp|cc|c\+\+|cxx|cppm|ccm|cxxm|c\+\+m|c|cl|h|hh|hpp"
                     r"|hxx|m|mm|inc|js|ts|proto|protodevel|java|cs|json|s?vh?)$")


def reformat_change(context: Context, change_id: int | str, revision_id: str = "current", submit: bool = False):
    """Function to fetch a change, reformat it.
    The function returns a dict that contains the data that can be posted to the review endpoint on Gerrit.
    """
    logger = logging.getLogger("core")
    logger.info("Fetching change details for %s" % str(change_id))
    if isinstance(change_id, int):
        # convert a change number to an id
        change_id, revision_id = context.get_change_and_revision_from_number(change_id)
    change = context.get_change(change_id, revision_id)
    for f in change.files:
        if not re.match(EXTENSION_PATTERN, f.filename, re.IGNORECASE):
            logger.info("Ignoring %s because it does not seem to be a file that `clang-format` can handle" % f.filename)
            continue
        if f.patch_contents is None:
            logger.info("Skipping %s because the file is deleted in the patch" % f.filename)
            continue
        if f.base_contents is not None:
            # Check if the file is a modified file (i.e. it has base and patch contents). If so, add the segments to a
            # list.
            if len(f.patch_segments) == 0:
                logger.info("Skipping %s because the changes in the patch are only deletions" % f.filename)
                continue
            segments = []
            for segment in f.patch_segments:
                segments.append(segment.format_range())
        else:
            # The patched file is new, add an empty segment list so that haiku-format reformats it in its entirety.
            segments = []
        reformatted_content = run_clang_format(f.patch_contents, segments)
        f.formatted_contents = reformatted_content
        if f.formatted_contents is None:
            logger.info("%s: no reformats" % f.filename)
        else:
            logger.info("%s: %i segment(s) reformatted" % (f.filename, len(f.format_segments)))

    review_input = _change_to_review_input(change, logger)
    # Convert review input into json
    if submit:
        context.publish_review(change_id, review_input, revision_id)
        logger.info("The review has been submitted to Gerrit")
    else:
        output = strip_empty_values_from_input_dict(review_input)
        with open("review.json", "wt") as f:
            f.write(json.dumps(output, indent=4))
        url = "/a/changes/%s/revisions/%s/review" % (change_id, revision_id)
        logger.info("POST the contents of review.json to: %s", url)


def _change_to_review_input(change: Change, logger) -> ReviewInput:
    """Internal function that converts a change into a ReviewInput object that can be pushed to Gerrit"""
    comments: dict[str, list[CommentInput]] = {}
    for f in change.files:
        if f.formatted_contents is None or len(f.format_segments) == 0:
            continue
        # WORKAROUND: get all lines in class definitions
        skip_lines_set = set(get_class_lines_in_file(f.patch_contents))
        for segment in f.format_segments:
            end = segment.end
            match segment.reformat_type:
                case ReformatType.INSERTION:
                    end = segment.start
                    operation = "insert after"
                case ReformatType.MODIFICATION:
                    operation = "change"
            # WORKAROUND: check if the reformatted segment overlaps with a class definition
            segment_lines_set = set(range(segment.start, end + 1, 1))
            if len(skip_lines_set & segment_lines_set) > 0:
                logger.warning("Class Workaround: [%s] skipped lines %s" % (f.filename, str(segment_lines_set)))
                continue
            # As per the documentation, set the end point to character 0 of the next line to select all lines
            # between start_line and end_line (excluding any content of end_line)
            # https://review.haiku-os.org/Documentation/rest-api-changes.html#comment-range
            # However, this does not seem to work with Gerrit 3.7.1 as it seems to select the entirety of end_line
            # as well. So comment this out, put keeping a note just in case this is a bug in this particular Gerrit
            # version and it needs to come back in the future.
            # end += 1
            comment_range = CommentRange(segment.start, 0, end, 0)
            if segment.reformat_type == ReformatType.DELETION:
                message = "Suggestion from `haiku-format` is to remove this line/these lines."
            else:
                message = ("Suggestion from `haiku-format` (%s):\n```c++\n%s```"
                           % (operation, "".join(segment.formatted_content)))
            comments.setdefault(f.filename, []).extend([CommentInput(
                message=message, range=comment_range
            )])

    if len(comments) == 0:
        message = "Experimental `haiku-format` bot: no formatting changes suggested for this commit."
        labels = {"Haiku-Format": +1}
    else:
        message = ("Experimental `haiku-format` bot: some formatting changes suggested.\nNote that this bot is "
                   "experimental and the suggestions may not be correct. There is a known issue with changes "
                   "in header files: `haiku-format` does not yet correctly output the column layout of the contents "
                   "of classes.\n\nYou can see and apply the suggestions by running `haiku-format` in your local "
                   "repository. For example, if in your local checkout this change is applied to a local checkout, you "
                   "can use the following command to automatically reformat:\n```\ngit-haiku-format HEAD~\n```")
        labels = {"Haiku-Format": -1}

    return ReviewInput(message=message, comments=comments, labels=labels, notify=NotifyEnum.OWNER)


_CLASS_DECLARATION_PATTERN = re.compile('^(?:class|struct) .*;$')
_CLASS_DEFINITION_START_PATTERN = re.compile('^(?:class|struct) .*$')


def get_class_lines_in_file(contents: list[str]) -> list[int]:
    """Parse a list of contents to find top level classes, and return a list of line numbers that are inside the class.

    This utility is part of a WORKAROUND to skip parsing the contents of class definitions.
    """
    if len(contents) == 0:
        return []

    skip_lines = []
    in_class = False
    level = 0
    for lineno, line in enumerate(contents, start=1):
        if not in_class:
            # Try to skip declarations (or empty single line class definitions)
            if _CLASS_DECLARATION_PATTERN.match(line):
                continue
            # Look for 'class' at the beginning of the line. This will not catch nested classes.
            if _CLASS_DEFINITION_START_PATTERN.match(line):
                in_class = True
                level += line.count('{')
                level -= line.count('}')
            # even if we found a class, we allow clang-format to reformat the first line
            continue

        # update level
        level += line.count('{')
        level -= line.count('}')
        if level == 0:
            in_class = False
            continue
        skip_lines.append(lineno)
    return skip_lines


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        prog="format-check",
        description="Checks the formatting of a patch on Haiku's Gerrit instance and publishes reformats if necessary")
    parser.add_argument('--submit', action="store_true", help="submit the review to gerrit")
    parser.add_argument('change_number', type=int)
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    gerrit = Context("https://review.haiku-os.org/")
    reformat_change(gerrit, args.change_number, submit=args.submit)
