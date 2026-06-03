"""Tests for blast radius detection."""
from pr_today.risk.blast_radius import analyze_blast_radius


def _make_file(filename: str) -> dict:
    return {"filename": filename, "status": "modified", "additions": 10, "deletions": 5, "changes": 15, "patch": ""}


class TestBlastRadius:
    def test_single_module(self):
        files = [_make_file("auth/login.py"), _make_file("auth/middleware.py")]
        report = analyze_blast_radius(files)
        assert "auth" in report.affected_modules
        assert report.total_modules_affected >= 1

    def test_multiple_modules(self):
        files = [
            _make_file("auth/login.py"),
            _make_file("payment/handler.py"),
            _make_file("session/store.py"),
        ]
        report = analyze_blast_radius(files)
        assert report.total_modules_affected >= 3
        assert "auth" in report.affected_modules
        assert "payment" in report.affected_modules
        assert "session" in report.affected_modules

    def test_shared_library_detection(self):
        files = [_make_file("packages/shared/utils.py")]
        report = analyze_blast_radius(files)
        assert len(report.shared_libraries_impacted) > 0

    def test_service_detection(self):
        files = [_make_file("payment-service/handler.py")]
        report = analyze_blast_radius(files)
        assert "payment-service" in report.affected_modules

    def test_cross_cutting_concerns(self):
        files = [
            _make_file("src/middleware/rate_limit.py"),
            _make_file("src/auth/oauth.py"),
            _make_file("src/logging/formatter.py"),
        ]
        report = analyze_blast_radius(files)
        assert "Middleware Layer" in report.cross_cutting_concerns
        assert "Authentication" in report.cross_cutting_concerns
        assert "Logging Infrastructure" in report.cross_cutting_concerns

    def test_empty_files(self):
        report = analyze_blast_radius([])
        assert report.total_modules_affected == 0
        assert len(report.affected_modules) == 0
