import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aira.llm import LLMConfig, LLMRoutingError
from aira.scanner import AIRAScanner


class ScannerModeTests(unittest.TestCase):
    def test_static_scan_respects_file_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            included = root / "keep.py"
            excluded = root / "skip.py"
            source = (
                "def save_record(db, record):\n"
                "    try:\n"
                "        db.insert(record)\n"
                "        return True\n"
                "    except Exception:\n"
                "        return True\n"
            )
            included.write_text(source, encoding="utf-8")
            excluded.write_text(source, encoding="utf-8")

            scanner = AIRAScanner(str(root), exclude_dirs=["skip.py"])
            result = scanner.scan(mode="static")

        self.assertEqual(result.files_scanned, 1)
        self.assertTrue(all(finding["file"] != "skip.py" for finding in result.findings))
        self.assertTrue(any(finding["file"] == "keep.py" for finding in result.findings))

    def test_test_coverage_scan_respects_excluded_test_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            included = root / "test_keep.py"
            excluded = root / "test_skip.py"
            test_source = (
                "def test_happy_path():\n"
                "    assert True\n"
            )
            included.write_text(test_source, encoding="utf-8")
            excluded.write_text(test_source, encoding="utf-8")

            scanner = AIRAScanner(str(root), exclude_dirs=["test_skip.py"])
            result = scanner.scan(mode="static")

        coverage_findings = [finding for finding in result.findings if finding["check_id"] == "C14"]
        self.assertEqual(len(coverage_findings), 1)
        self.assertEqual(coverage_findings[0]["file"], "test_keep.py")

    def test_hybrid_falls_back_to_static_when_llm_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sample.py"
            target.write_text(
                "def save_record(db, record):\n"
                "    try:\n"
                "        db.insert(record)\n"
                "        return True\n"
                "    except Exception:\n"
                "        return True\n",
                encoding="utf-8",
            )

            scanner = AIRAScanner(str(target))
            with mock.patch("aira.scanner.run_llm_json_audit", side_effect=LLMRoutingError("no provider")):
                result = scanner.scan(mode="hybrid", llm_config=LLMConfig(provider="auto"))

        self.assertEqual(result.metadata["mode"], "hybrid")
        self.assertEqual(result.metadata["llm_fallback"], "static_only")
        self.assertEqual(result.check_results["success_integrity"], "FAIL")

    def test_llm_mode_normalizes_provider_response(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sample.py"
            target.write_text("print('hello')\n", encoding="utf-8")

            scanner = AIRAScanner(str(target))
            fake_response = {
                "provider": "openai-compatible",
                "model": "gpt-oss-120b",
                "text": json.dumps(
                    {
                        "ai_failure_audit": {
                            "success_integrity": "PASS",
                            "audit_integrity": "UNKNOWN",
                            "exception_handling": "UNKNOWN",
                            "fallback_control": "UNKNOWN",
                            "bypass_controls": "UNKNOWN",
                            "return_contracts": "UNKNOWN",
                            "logic_consistency": "UNKNOWN",
                            "background_tasks": "UNKNOWN",
                            "environment_safety": "UNKNOWN",
                            "startup_integrity": "UNKNOWN",
                            "determinism": "UNKNOWN",
                            "lineage": "UNKNOWN",
                            "confidence_representation": "UNKNOWN",
                            "test_coverage_symmetry": "UNKNOWN",
                            "idempotency_safety": "UNKNOWN",
                        },
                        "findings": [
                            {
                                "check_id": "C05",
                                "check_name": "BYPASS / OVERRIDE PATHS",
                                "severity": "MEDIUM",
                                "file": "sample.py",
                                "line": 1,
                                "description": "Potential bypass detected.",
                                "snippet": "print('hello')",
                            }
                        ],
                    }
                ),
            }

            with mock.patch("aira.scanner.run_llm_json_audit", return_value=fake_response):
                result = scanner.scan(mode="llm", llm_config=LLMConfig(provider="openai-compatible", model="gpt-oss-120b"))

        self.assertEqual(result.metadata["provider"], "openai-compatible")
        self.assertEqual(result.metadata["model"], "gpt-oss-120b")
        self.assertEqual(result.check_results["logic_consistency"], "UNKNOWN")
        self.assertEqual(result.findings[0]["check_id"], "C05")

    def test_llm_mode_drops_human_review_only_findings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sample.py"
            target.write_text("print('hello')\n", encoding="utf-8")

            scanner = AIRAScanner(str(target))
            fake_response = {
                "provider": "ollama",
                "model": "minimax-m2:cloud",
                "text": json.dumps(
                    {
                        "ai_failure_audit": {
                            "logic_consistency": "FAIL",
                            "lineage": "FAIL",
                        },
                        "findings": [
                            {
                                "check_id": "C07",
                                "check_name": "PARALLEL LOGIC DRIFT",
                                "severity": "HIGH",
                                "file": "sample.py",
                                "line": 1,
                                "description": "Human-review check should not survive normalization.",
                                "snippet": "print('hello')",
                            },
                            {
                                "check_id": "C12",
                                "check_name": "SOURCE-TO-OUTPUT LINEAGE",
                                "severity": "HIGH",
                                "file": "sample.py",
                                "line": 1,
                                "description": "Human-review check should not survive normalization.",
                                "snippet": "print('hello')",
                            },
                        ],
                    }
                ),
            }

            with mock.patch("aira.scanner.run_llm_json_audit", return_value=fake_response):
                result = scanner.scan(mode="llm", llm_config=LLMConfig(provider="ollama", model="minimax-m2:cloud"))

        self.assertEqual(result.check_results["logic_consistency"], "UNKNOWN")
        self.assertEqual(result.check_results["lineage"], "UNKNOWN")
        self.assertEqual(result.findings, [])


if __name__ == "__main__":
    unittest.main()
