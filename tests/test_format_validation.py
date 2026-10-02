"""Regression tests for certificate-format rejection at the API and CLI boundary."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from semantic_certificates.checker import check


ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "cases" / "guarded-division.json").read_text())


def malformed_availability_cases():
    """Named JSON-representable cases that previously reached mapping methods."""
    return {
        "guard-ready-array": ("guard_ready", ["p", "h"]),
        "guard-ready-string": ("guard_ready", "ph"),
        "guard-ready-null": ("guard_ready", None),
        "input-ready-array": ("input_ready", ["x", "y", "z"]),
        "input-ready-string": ("input_ready", "xyz"),
        "input-ready-null": ("input_ready", None),
    }


class AvailabilityFormatTests(unittest.TestCase):
    def test_api_rejects_non_object_availability_maps(self):
        for name, (field, value) in malformed_availability_cases().items():
            with self.subTest(name=name):
                certificate = deepcopy(BASE)
                certificate[field] = value
                verdict = check(certificate)
                self.assertFalse(verdict.accepted)
                self.assertEqual(verdict.issues[0]["code"], "format")
                self.assertEqual(
                    verdict.issues[0]["message"], f"{field} must be an object"
                )

    def test_api_checks_exact_keys_and_integer_releases(self):
        cases = {
            "guard-missing-key": ("guard_ready", {"p": 3}),
            "guard-extra-key": ("guard_ready", {"p": 3, "h": 0, "q": 1}),
            "input-missing-key": ("input_ready", {"x": 0, "y": 0}),
            "input-extra-key": (
                "input_ready",
                {"x": 0, "y": 0, "z": 0, "w": 0},
            ),
            "guard-bool-release": ("guard_ready", {"p": True, "h": 0}),
            "input-string-release": (
                "input_ready",
                {"x": 0, "y": "0", "z": 0},
            ),
            "guard-negative-release": ("guard_ready", {"p": -1, "h": 0}),
            "input-large-release": (
                "input_ready",
                {"x": 0, "y": 0, "z": 4097},
            ),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name):
                certificate = deepcopy(BASE)
                certificate[field] = value
                verdict = check(certificate)
                self.assertFalse(verdict.accepted)
                self.assertEqual(verdict.issues[0]["code"], "format")

        normal = check(deepcopy(BASE))
        self.assertTrue(normal.accepted, normal.issues)

    def test_cli_returns_json_and_status_two_for_malformed_maps(self):
        cli_cases = {
            name: (field, value, f"{field} must be an object")
            for name, (field, value) in malformed_availability_cases().items()
        }
        cli_cases.update(
            {
                "guard-ready-missing-key": (
                    "guard_ready",
                    {"p": 3},
                    "guard_ready keys must exactly match declarations",
                ),
                "input-ready-bool-release": (
                    "input_ready",
                    {"x": 0, "y": True, "z": 0},
                    "input_ready[y] release time must be an integer in [0, 4096]",
                ),
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name, (field, value, expected_message) in cli_cases.items():
                with self.subTest(name=name):
                    certificate = deepcopy(BASE)
                    certificate[field] = value
                    path = directory / f"{name}.json"
                    path.write_text(json.dumps(certificate))
                    proc = subprocess.run(
                        [sys.executable, "-m", "semantic_certificates", str(path)],
                        cwd=ROOT,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=20,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 2)
                    self.assertEqual(proc.stderr, "")
                    result = json.loads(proc.stdout)
                    self.assertFalse(result["accepted"])
                    self.assertEqual(result["issues"][0]["code"], "format")
                    self.assertEqual(
                        result["issues"][0]["message"], expected_message
                    )

            normal_path = directory / "normal.json"
            normal_path.write_text(json.dumps(BASE))
            proc = subprocess.run(
                [sys.executable, "-m", "semantic_certificates", str(normal_path)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stderr, "")
            result = json.loads(proc.stdout)
            self.assertTrue(result["accepted"])


if __name__ == "__main__":
    unittest.main()
