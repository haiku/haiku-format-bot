#
# Copyright 2024 Haiku, Inc. All rights reserved.
# Distributed under the terms of the MIT License.
#
# Authors:
#  Niels Sascha Reedijk, niels.reedijk@gmail.com
#
"""
This module implements the logic to select changes for Gerrit that need to be formatted, apply the formatting, and
submit the reviews. It includes error handling, in order to let the system skip changes that cannot be reformatted due
to a bug in this bot, or at any other layer.

The module can run independently.
"""
import logging
import sys
import time
import traceback
from datetime import date, timedelta

from .core import reformat_change
from .gerrit import Context
from .models import HashtagsInput

_ALL_CHANGES_QUERY_OPTIONS = list([
    "status:open",
    "repo:haiku",
    "-is:wip",
    "-label:Haiku-Format=ANY",
    "-hashtag:format-bot-skip",
    "-hashtag:format-bot-failed",
    "limit:100"
])


def format_changes(after: date, submit: bool = False):
    """Fetch all relevant changes from Gerrit, and apply haiku-format.

    This method is designed to be called repeatedly.
    """
    logger = logging.getLogger("runner")
    logger.info("Fetching all changes from Gerrit")
    context = Context("https://review.haiku-os.org/")
    query_options = _ALL_CHANGES_QUERY_OPTIONS.copy()
    query_options.append("after:%i-%i-%i" % (after.year, after.month, after.day))
    changes = context.query_changes(query_options, {"o": "CURRENT_REVISION"})
    logger.info("Found %i changes" % len(changes))

    for change in reversed(changes):
        try:
            reformat_change(context, change["id"], change["current_revision"], submit)
        except RuntimeError as e:
            logger.error("Error calling reformat_change:\n%s" % traceback.format_exc())
            logger.info("Reformatting change failed, setting `format-bot-failed` hashtag to skip in future")
            if submit:
                context.set_hashtags(change["id"], HashtagsInput(add=["format-bot-failed"]))


def daemon_mode(timeout: int, after: date, submit: bool = False):
    logger = logging.getLogger("daemon")
    logger.info("Starting daemon with timeout set to %i seconds" % timeout)
    if not submit:
        logger.warning("Running in dry-run mode (submit is set to false)")
    while True:
        logger.info("Starting daemon run")
        format_changes(after, submit)
        logger.info("Daemon run finished. Sleeping for %i seconds" % timeout)
        time.sleep(timeout)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="haiku-format-bot",
        description="Automates running `haiku-format` on changes on Haiku's Gerrit instance")
    parser.add_argument("--days", type=int, default=3,
                        help="Number of days in the past to select changes for reformatting")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Time in seconds to wait between runs when in daemon mode")
    parser.add_argument('--daemon', action="store_true", help="submit")
    parser.add_argument('--submit', action="store_true", help="submit the reviews to gerrit")
    args = parser.parse_args()
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', stream=sys.stdout,
                        datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
    start_date = date.today() - timedelta(days=args.days)
    if args.daemon:
        daemon_mode(args.timeout, start_date, args.submit)
    else:
        format_changes(start_date, args.submit)
