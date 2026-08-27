#!/usr/bin/env python3
"""Validate a frozen study protocol and one or more fleet corpora."""

import argparse
import json
from pathlib import Path

from protocol import DEFAULT_PROTOCOL, REPO, protocol_provenance, validate_corpus


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("corpora", nargs="*",
                        default=["tasks/fleet_service/tickets_v3.json"])
    args = parser.parse_args()
    provenance, protocol = protocol_provenance(args.protocol)
    print(f"protocol {provenance['id']} sha256={provenance['sha256']}")
    for raw in args.corpora:
        path = Path(raw)
        if not path.is_absolute():
            path = REPO / path
        corpus = json.loads(path.read_text())
        validate_corpus(corpus, protocol)
        print(f"corpus {corpus['corpus']} repository={corpus['repository']} "
              f"language={corpus['language']} tickets={len(corpus['tickets'])}: ok")


if __name__ == "__main__":
    main()
