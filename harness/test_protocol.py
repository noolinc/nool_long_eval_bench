#!/usr/bin/env python3
"""Deterministic tests for the frozen protocol/corpus boundary."""

import copy
import json
import unittest

from protocol import DEFAULT_PROTOCOL, REPO, load_protocol, validate_corpus


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol, cls.digest, _ = load_protocol(DEFAULT_PROTOCOL)
        cls.corpus = json.loads(
            (REPO / "tasks/fleet_service/tickets_v3.json").read_text())

    def test_pinned_protocol_and_current_corpus(self):
        self.assertEqual(len(self.digest), 64)
        self.assertTrue(validate_corpus(self.corpus, self.protocol))

    def test_accept_command_requires_ticket_placeholder(self):
        corpus = copy.deepcopy(self.corpus)
        corpus["commands"]["accept"] = ["go", "test", "./accept/all/"]
        with self.assertRaisesRegex(ValueError, "placeholder"):
            validate_corpus(corpus, self.protocol)

    def test_duplicate_ticket_ids_are_rejected(self):
        corpus = copy.deepcopy(self.corpus)
        corpus["tickets"].append(copy.deepcopy(corpus["tickets"][0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_corpus(corpus, self.protocol)


if __name__ == "__main__":
    unittest.main()
