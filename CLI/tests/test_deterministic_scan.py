import unittest

from aira.deterministic_scan import scan_inline_source

try:
    import esprima  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - optional parser dependency
    esprima = None


class DeterministicScanTests(unittest.TestCase):
    def test_python_deterministic_scan_is_parser_backed(self):
        code = (
            "def save_record(db, record):\n"
            "    try:\n"
            "        write_audit(record)\n"
            "        db.insert(record)\n"
            "    except Exception:\n"
            "        return True\n"
        )

        result = scan_inline_source(code, "python")

        self.assertTrue(result["meta"]["parser_backed"])
        self.assertEqual(result["checks"]["success_integrity"], "FAIL")
        self.assertEqual(result["checks"]["exception_handling"], "FAIL")
        self.assertEqual(result["checks"]["audit_integrity"], "FAIL")

    @unittest.skipUnless(esprima is not None, "esprima parser is not installed")
    def test_javascript_deterministic_scan_uses_ast_rules_when_available(self):
        code = (
            "async function initSystem() {\n"
            "  try {\n"
            "    writeAudit(event);\n"
            "  } catch (e) {\n"
            "    console.error(e);\n"
            "    return true;\n"
            "  }\n"
            "}\n"
        )

        result = scan_inline_source(code, "javascript")

        self.assertTrue(result["meta"]["parser_backed"])
        self.assertEqual(result["checks"]["exception_handling"], "FAIL")
        self.assertEqual(result["checks"]["success_integrity"], "FAIL")
        self.assertEqual(result["checks"]["audit_integrity"], "FAIL")
        self.assertEqual(result["checks"]["startup_integrity"], "FAIL")

    def test_unsupported_language_is_rejected(self):
        with self.assertRaises(ValueError):
            scan_inline_source("print('hello')", "ruby")


if __name__ == "__main__":
    unittest.main()
