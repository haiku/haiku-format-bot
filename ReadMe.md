Haiku Format Bot
================

The Haiku project has [coding guidelines](https://www.haiku-os.org/development/coding-guidelines)
which includes the coding style. Part of the code review process is to review and enforce that
style. In order to make it easier for contributors, the `haiku-format` tool has been built. It
extends `clang-format` and codifies the Haiku style.

The goal of this tool is to apply the `haiku-format` tool to changes to the Haiku code base sent
in for code review, and if there are style fixes necessary, then post those as suggestions to
Gerrit so that users can further decide what to do next.

Currently, the tool is considered to be experimental, both in the sense that it is likely that
the `haiku-format` configuration needs to be further tweaked over time, as well as the newness
of this tool itself.

About haiku-format
------------------
For formatting, a customized `clang-format` called `haiku-format` is used. It is currently
[maintained on Github](https://github.com/owenca/haiku-format).

General Design of the Format-Check-Bot
--------------------------------------

The tool's functionality is implemented in the following modules:

1. The `core.py` module implements the main logic for evaluating a specific Gerrit change.
   That means it fetches a change from Gerrit, runs `haiku-format` over the changes, and
   posts them back to Gerrit.
2. The `gerrit.py` module implements the logic to exchange data with Gerrit. GET requests are
   converted into the models that are used by other parts of this tool. POST requests
   are serialized from the internal models into the json format Gerrit expects.
3. The `llvm.py` module is based on the LLVM code that helps users run `clang-format` over a
   diff. It contains the tools to identify which parts of a file have been patched, and it
   has the logic of running clang-format/haiku-format, and then capturing which segments should
   be reformatted.
4. The `models.py` module contains the internal models that codify business logic when processing
   Gerrit changes, as well as the data structures that are sent to Gerrit when posting the
   reviews.
5. The `runners.py` module implements the logic to select changes for Gerrit that need to be
   formatted, apply the formatting, and submit the reviews. It includes error handling,
   in order to let the system skip changes that cannot be reformatted due to a bug in this bot,
   or at any other layer.

Development and Testing
-----------------------

In order to do local development or testing, you require:

- Python 3 (version 3.14 is recommended)
- Requests module
- A build of `haiku-format` in a location in `PATH`

In order to use the functionality to reformat a Gerrit change, you run the following command
from the root of the project:

```bash
# Run the haiku format bot on change 1000. The result is stored in a file called `review.json`
python3 -m formatchecker.core 1000

# Run the haiku format bot for a single and submit it
export GERRIT_USER=user
export GERRIT_PASSWORD=http_password_for_user
python3 -m formatchecker.core --submit 1000

# Run the haiku format bot on all changes in the past 3 days. If they have been checked before, they are excluded.
export GERRIT_USER=user
export GERRIT_PASSWORD=http_password_for_user
python3 -m formatchecker.runner --submit
```

The test suite can be run using `python3 -m unittest` in the root of the project.

Docker Build
------------

The repository comes with a Dockerfile packaged. It is compatible with `docker` and `podman`.
The build runs in two steps. The first step builds a specific version of `haiku-format`,
which is then copied over to an image that contains the format check bot.

Some example commands:
```bash
# Build the image
podman build -t format-check-bot:dev .

# Run the format check for change 1000
podman run format-check-bot:dev python3 -m formatchecker.core 1000

# Run the format check for change 1000 and submit
podman run -e GERRIT_USERNAME=user -e GERRIT_PASSWORD=http_password_for-user format-check-bot:dev python3 -m formatchecker.core --submit 1000

# Run the format check in daemon mode
podman run -e GERRIT_USERNAME=user -e GERRIT_PASSWORD=http_password_for-user format-check-bot:dev python3 -m formatchecker.runner --daemon --submit

```
