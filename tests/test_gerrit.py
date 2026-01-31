#
# Copyright 2023-2024 Haiku, Inc. All rights reserved.
# Distributed under the terms of the MIT License.
#
# Authors:
#  Niels Sascha Reedijk, niels.reedijk@gmail.com
#
import json
import os
import unittest
from typing import Any

from formatchecker.gerrit import Context
from formatchecker.models import ReviewInput, HashtagsInput


def context_get_mock(self, url: str, params=None):
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    # ContextTest.setUpClass()
    if url == "changes/" and params is None:
        # This is the get operation to check if the Gerrit URL is valid
        return
    # ContextTest.test_get_change()
    elif url == "changes/test_get_change/revisions/current/files":
        with open(os.path.join(data_path, "test_gerrit_revision_files.json")) as f:
            return json.load(f)
    elif url =="changes/test_get_change/revisions/current/files/%2FCOMMIT_MSG/content":
        # This file is added, so only support getting the new contents
        if params is None:
            return "COMMIT_MSG line 1\nCOMMIT_MSG line 2\n"
        elif params == {"parent": "1"}:
            raise RuntimeError("The COMMIT_MSG file is added, so the base version should not be requested")
        else:
            raise RuntimeError("Invalid request for COMMIT_MSG content")
    elif url =="changes/test_get_change/revisions/current/files/src%2Ffile_implicitly_modified/content":
        # This file is modified, so there is new and parent contents
        if params is None:
            return "file_implicitly_modified line 1\n2Ffile_implicitly_modified base line 2\n"
        elif params == {"parent": "1"}:
            return "file_implicitly_modified line 1\n2Ffile_implicitly_modified patched line 2\n"
        else:
            raise RuntimeError("Invalid request for src/file_implicitly_modified content")
    elif url =="changes/test_get_change/revisions/current/files/src%2Ffile_deleted/content":
        # This file is deleted, so only support getting the old contents
        if params is None:
            raise RuntimeError("The src/file_deleted file is deleted, so the patched version should not be requested")
        elif params == {"parent": "1"}:
            return "file_deleted line 1\nfile_deleted line 2\n"
        else:
            raise RuntimeError("Invalid request for src/file_implicitly_modified content")
    elif url =="changes/test_get_change/revisions/current/files/src%2Ffile_renamed/content":
        # This is the new path of a renamed file, so only support getting the new contents
        if params is None:
            return "file_renamed line 1\nfile_renamed base line 2\n"
        elif params == {"parent": "1"}:
            raise RuntimeError("The src/file_renamed file is added, so the base version should not be requested")
        else:
            raise RuntimeError("Invalid request for src/file_renamed content")
    elif url =="changes/test_get_change/revisions/current/files/old%2Ffile_renamed/content":
        # This is the old path of a renamed file, so only support getting the old contents
        if params is None:
            raise RuntimeError("The old/file_renamed file was renamed, so the patched version should not be requested")
        elif params == {"parent": "1"}:
            return "file_renamed line 1\nfile_renamed patched line 2\n"
        else:
            raise RuntimeError("Invalid request for old/file_renamed content")
    elif url =="changes/test_get_change/revisions/current/files/src%2Ffile_copied/content":
        # This is the new path of a copied file, so only support getting the new contents
        if params is None:
            return "file_copied line 1\nfile_copied base line 2\n"
        elif params == {"parent": "1"}:
            raise RuntimeError("The src/file_copied file is added, so the base version should not be requested")
        else:
            raise RuntimeError("Invalid request for src/file_copied content")
    elif url =="changes/test_get_change/revisions/current/files/old%2Ffile_copied/content":
        # This is the old path of a copied file, so only support getting the old contents
        if params is None:
            raise RuntimeError("The old/file_copied file was copied in this change, so the patched version should not be requested")
        elif params == {"parent": "1"}:
            return "file_copied line 1\nfile_copied patched line 2\n"
        else:
            raise RuntimeError("Invalid request for old/file_copied content")
    elif url =="changes/test_get_change/revisions/current/files/src%2Ffile_rewritten/content":
        # This file is modified, so there is new and parent contents
        if params is None:
            return "file_rewritten line 1\n2Ffile_rewritten base line 2\n"
        elif params == {"parent": "1"}:
            return "file_rewritten line 1\n2Ffile_rewritten patched line 2\n"
        else:
            raise RuntimeError("Invalid request for src/file_rewritten content")
    raise ValueError("Input URL is not mocked: %s" % url)


def context_post_mock(self, url: str, content: list[Any] | dict[str, Any]):
    # ContextTest.test_publish_review()
    if url == "changes/test_publish_review/revisions/current/review":
        assert (content == {"message": "test_publish_review", "tag": "autogenerated:experimental-formatting-bot"})
        return
    elif url == "changes/test_publish_review/revisions/custom_revision/review":
        assert (content == {"message": "test_publish_review", "tag": "autogenerated:experimental-formatting-bot"})
        return
    elif url == "changes/test_set_hashtags/hashtags":
        assert (content == {"add": ["add1", "add2"]})
        return ["add1", "add2", "existing"]
    raise ValueError("Input URL is not mocked: %s" % url)


def context_query_mock(self, query_options: list[str], params: dict[str, Any]) -> list[Any]:
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    # ContextTest.test_get_change_id_from_number()
    if query_options == ["change:5692"]:
        with open(os.path.join(data_path, "test_gerrit_get_change.json")) as f:
            return json.load(f)
    elif query_options == ["change:19000"]:
        return []


class ContextTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Context._get = context_get_mock
        Context._post = context_post_mock
        Context._query = context_query_mock
        cls._context = Context("https://test-gerrit/")

    @classmethod
    def get_auth(cls) -> tuple[str, str]:
        return cls._context.auth

    def test_get_change_id_from_number(self):
        self.assertEqual(self._context.get_change_and_revision_from_number(5692),
                         ("haiku~dev%2Fnetservices~I0dadd1dfd3fb36256bd6f4a2530dbbe12afefce5", "701299b"))
        self.assertRaises(ValueError, self._context.get_change_and_revision_from_number, 19000)

    def test_get_change(self):
        change = self._context.get_change("test_get_change")
        # Validate that the file content was requested correctly
        self.assertEqual(change.files[0].filename, "/COMMIT_MSG")
        self.assertIsNone(change.files[0].base_contents)
        self.assertIsNotNone(change.files[0].patch_contents)
        self.assertEqual(change.files[1].filename, "src/file_implicitly_modified")
        self.assertIsNotNone(change.files[1].base_contents)
        self.assertIsNotNone(change.files[1].patch_contents)
        self.assertEqual(change.files[2].filename, "src/file_deleted")
        self.assertIsNotNone(change.files[2].base_contents)
        self.assertIsNone(change.files[2].patch_contents)

    def test_publish_review(self):
        """Test whether the Context.publish_review() method posts the data to the right URL"""
        review_input = ReviewInput("test_publish_review")
        self._context.publish_review("test_publish_review", review_input)
        self._context.publish_review("test_publish_review", review_input, "custom_revision")

    def test_format_query_string(self):
        # Test single option (so no + expected)
        query_options = ["change:1000"]
        url_with_no_params = "https://mocktest/changes/"
        url = self._context._append_query_string(url_with_no_params, query_options)
        self.assertEqual(url, "https://mocktest/changes/?q=change:1000")

        # Test multiple options
        query_options = ["change:1000", "-is:wip"]
        url = self._context._append_query_string(url_with_no_params, query_options)
        self.assertEqual(url, "https://mocktest/changes/?q=change:1000+-is:wip")
        url_with_params = "https://mocktest/changes/?o=CURRENT&n=2"
        url = self._context._append_query_string(url_with_params, query_options)
        self.assertEqual(url, "https://mocktest/changes/?o=CURRENT&n=2&q=change:1000+-is:wip")

    def test_hashtags(self):
        # Test modifying the hashtags on a Gerrit Change
        modifications = HashtagsInput(add=["add1", "add2"])
        new_tags = self._context.set_hashtags("test_set_hashtags", modifications)
        self.assertEqual(new_tags, ["add1", "add2", "existing"])

    def test_auth(self):
        """Test whether Context.auth() correctly picks up values from the environment.
        Note: this test will manipulate the values of the GERRIT_USERNAME and GERRIT_PASSWORD values. If it fails
        midway, some mock data may leak into the environment. On success, previously set variables might be unset.
        """
        username = "_username"
        password = "_password"

        # Clean up env
        if "GERRIT_USERNAME" in os.environ.keys():
            del os.environ["GERRIT_USERNAME"]
        if "GERRIT_PASSWORD" in os.environ.keys():
            del os.environ["GERRIT_PASSWORD"]

        # Test failure with no auth info set
        self.assertRaises(RuntimeError, self.get_auth)
        # Test failure with partial env info set
        os.environ["GERRIT_USERNAME"] = username
        self.assertRaises(RuntimeError, self.get_auth)
        del os.environ["GERRIT_USERNAME"]
        os.environ["GERRIT_PASSWORD"] = password
        self.assertRaises(RuntimeError, self.get_auth)

        # Test success
        os.environ["GERRIT_USERNAME"] = username
        self.assertEqual(self.get_auth(), (username, password))

        # Make sure that the auth stays sticky, even if the environment variables are unset
        del os.environ["GERRIT_USERNAME"]
        del os.environ["GERRIT_PASSWORD"]
        self.assertEqual(self.get_auth(), (username, password))


if __name__ == '__main__':
    unittest.main()
