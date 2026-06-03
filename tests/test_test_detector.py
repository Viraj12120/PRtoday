"""Tests for missing test detection."""
from pr_today.risk.test_detector import detect_missing_tests, _is_test_file, _is_source_file


def _make_file(filename: str) -> dict:
    return {"filename": filename, "status": "modified", "additions": 10, "deletions": 5, "changes": 15, "patch": ""}


class TestIsTestFile:
    def test_python_test(self):
        assert _is_test_file("test_auth.py") is True
        assert _is_test_file("auth_test.py") is True

    def test_js_test(self):
        assert _is_test_file("auth.test.js") is True
        assert _is_test_file("auth.spec.ts") is True

    def test_go_test(self):
        assert _is_test_file("auth_test.go") is True

    def test_not_test(self):
        assert _is_test_file("auth.py") is False
        assert _is_test_file("main.go") is False


class TestIsSourceFile:
    def test_python_source(self):
        assert _is_source_file("src/auth.py") is True

    def test_js_source(self):
        assert _is_source_file("src/app.tsx") is True

    def test_non_source(self):
        assert _is_source_file("README.md") is False
        assert _is_source_file("docs/guide.md") is False

    def test_skip_dirs(self):
        assert _is_source_file("node_modules/pkg/index.js") is False
        assert _is_source_file("vendor/lib/main.go") is False


class TestDetectMissingTests:
    def test_all_covered(self):
        files = [
            _make_file("src/auth.py"),
            _make_file("tests/test_auth.py"),
        ]
        report = detect_missing_tests(files)
        assert len(report.files_without_tests) == 0
        assert report.coverage_ratio == 1.0
        assert report.missing_unit_tests is False

    def test_missing_tests(self):
        files = [
            _make_file("src/auth.py"),
            _make_file("src/payment.py"),
            _make_file("tests/test_auth.py"),
        ]
        report = detect_missing_tests(files)
        assert len(report.files_without_tests) == 1
        assert "src/payment.py" in report.files_without_tests
        assert report.missing_unit_tests is True
        assert report.coverage_ratio == 0.5

    def test_no_source_files(self):
        files = [
            _make_file("README.md"),
            _make_file("docs/guide.md"),
        ]
        report = detect_missing_tests(files)
        assert len(report.files_without_tests) == 0
        assert report.coverage_ratio == 1.0

    def test_missing_integration_tests(self):
        files = [
            _make_file("src/api/handler.py"),
            _make_file("tests/test_handler.py"),
        ]
        report = detect_missing_tests(files)
        assert report.missing_integration_tests is True

    def test_has_integration_tests(self):
        files = [
            _make_file("src/api/handler.py"),
            _make_file("tests/test_handler.py"),
            _make_file("tests/integration_test_api.py"),
        ]
        report = detect_missing_tests(files)
        assert report.missing_integration_tests is False

    def test_empty_pr(self):
        report = detect_missing_tests([])
        assert report.coverage_ratio == 1.0
        assert report.missing_unit_tests is False
