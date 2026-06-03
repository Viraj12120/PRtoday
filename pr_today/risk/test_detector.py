"""
PR Sentinel - Missing Test Detection Module.

Analyzes changed source files against existing test files in the PR
to detect potentially missing unit or integration tests.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set
import re


@dataclass
class MissingTestReport:
    """Report of potentially missing tests for changed source files."""
    files_without_tests: List[str] = field(default_factory=list)
    files_with_tests: List[str] = field(default_factory=list)
    test_files_modified: List[str] = field(default_factory=list)
    coverage_ratio: float = 0.0  # 0.0 - 1.0
    missing_integration_tests: bool = False
    missing_unit_tests: bool = False


# Patterns that identify test files
TEST_FILE_PATTERNS = [
    re.compile(r"test[_\-].*\.(py|js|ts|go|rb|java|rs)$", re.IGNORECASE),
    re.compile(r".*[_\-]test\.(py|js|ts|go|rb|java|rs)$", re.IGNORECASE),
    re.compile(r".*\.test\.(js|ts|jsx|tsx)$", re.IGNORECASE),
    re.compile(r".*\.spec\.(js|ts|jsx|tsx)$", re.IGNORECASE),
    re.compile(r".*_test\.go$", re.IGNORECASE),
    re.compile(r".*Tests?\.(java|cs)$", re.IGNORECASE),
]

# Patterns that identify integration test files
INTEGRATION_TEST_PATTERNS = [
    re.compile(r"integration[_\-]?test", re.IGNORECASE),
    re.compile(r"test[_\-]?integration", re.IGNORECASE),
    re.compile(r"e2e[_\-]?test", re.IGNORECASE),
    re.compile(r"test[_\-]?e2e", re.IGNORECASE),
]

# Source file extensions worth tracking
SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rb",
    ".java", ".cs", ".rs", ".swift", ".kt",
}

# Directories that contain non-source code (skip these)
SKIP_DIRS = {
    "node_modules", "vendor", "dist", "build", "__pycache__",
    ".git", ".venv", "venv", "env",
    "docs", "doc", "documentation",
    "assets", "static", "public", "images",
}


def _is_test_file(filename: str) -> bool:
    """Check if a file is a test file."""
    basename = filename.replace("\\", "/").split("/")[-1]
    return any(p.match(basename) for p in TEST_FILE_PATTERNS)


def _is_integration_test(filename: str) -> bool:
    """Check if a file is an integration test."""
    return any(p.search(filename) for p in INTEGRATION_TEST_PATTERNS)


def _is_source_file(filename: str) -> bool:
    """Check if a file is a source code file worth tracking."""
    # Skip files in excluded directories
    parts = filename.replace("\\", "/").lower().split("/")
    if any(part in SKIP_DIRS for part in parts):
        return False

    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1]
    return ext.lower() in SOURCE_EXTENSIONS


def _source_to_test_name(filename: str) -> str:
    """
    Convert a source filename to its expected test filename pattern.
    e.g. 'auth.py' -> 'test_auth' or 'auth_test'
    """
    basename = filename.replace("\\", "/").split("/")[-1]
    name_without_ext = basename.rsplit(".", 1)[0] if "." in basename else basename
    return name_without_ext.lower()


def detect_missing_tests(files: List[Dict[str, Any]]) -> MissingTestReport:
    """
    Analyze changed files to detect missing tests.

    Args:
        files: List of file dicts from the GitHub API.

    Returns:
        MissingTestReport with coverage analysis.
    """
    source_files: List[str] = []
    test_files: List[str] = []
    integration_tests: List[str] = []

    for f in files:
        filename = f.get("filename", "")
        is_test = _is_test_file(filename)
        is_integ = _is_integration_test(filename)
        if is_test or is_integ:
            test_files.append(filename)
            if is_integ:
                integration_tests.append(filename)
        elif _is_source_file(filename):
            source_files.append(filename)

    # Build a set of "covered" source names from the test files present in the PR
    covered_names: Set[str] = set()
    for tf in test_files:
        basename = tf.replace("\\", "/").split("/")[-1].lower()
        # Extract the source name from test file name
        # test_auth.py -> auth, auth_test.py -> auth, auth.test.js -> auth
        cleaned = basename
        for prefix in ["test_", "test-"]:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
        for suffix in ["_test", "-test", ".test", ".spec"]:
            idx = cleaned.find(suffix)
            if idx != -1:
                cleaned = cleaned[:idx]
        # Remove extension
        if "." in cleaned:
            cleaned = cleaned.rsplit(".", 1)[0]
        covered_names.add(cleaned)

    # Check which source files have corresponding tests in the PR
    files_with_tests: List[str] = []
    files_without_tests: List[str] = []

    for sf in source_files:
        source_name = _source_to_test_name(sf)
        if source_name in covered_names:
            files_with_tests.append(sf)
        else:
            files_without_tests.append(sf)

    total_source = len(source_files)
    covered_count = len(files_with_tests)
    coverage_ratio = covered_count / total_source if total_source > 0 else 1.0

    # Determine if integration tests are missing
    has_critical_changes = any(
        any(p in f.get("filename", "").lower() for p in ["api", "service", "handler", "controller", "route"])
        for f in files
    )

    return MissingTestReport(
        files_without_tests=files_without_tests,
        files_with_tests=files_with_tests,
        test_files_modified=test_files,
        coverage_ratio=coverage_ratio,
        missing_integration_tests=has_critical_changes and len(integration_tests) == 0,
        missing_unit_tests=len(files_without_tests) > 0,
    )
