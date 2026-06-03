"""
PR Sentinel - Blast Radius Detection Module.

Determines which modules, services, and shared libraries are impacted by a PR.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set


@dataclass
class BlastRadiusReport:
    """The blast radius analysis for a PR."""
    affected_modules: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    shared_libraries_impacted: List[str] = field(default_factory=list)
    cross_cutting_concerns: List[str] = field(default_factory=list)
    total_modules_affected: int = 0


# Patterns that indicate shared/cross-cutting code
SHARED_PATTERNS = {
    "shared", "common", "utils", "helpers", "lib", "core",
    "pkg", "internal", "sdk", "api-client", "client",
}

# Patterns that indicate service boundaries
SERVICE_PATTERNS = {
    "service", "services", "server", "api", "gateway",
    "worker", "handler", "controller", "microservice",
}

# Cross-cutting concern patterns
CROSS_CUTTING_PATTERNS = {
    "middleware": "Middleware Layer",
    "auth": "Authentication",
    "logging": "Logging Infrastructure",
    "monitoring": "Monitoring/Observability",
    "cache": "Caching Layer",
    "queue": "Message Queue",
    "events": "Event System",
    "config": "Configuration",
    "i18n": "Internationalization",
    "l10n": "Localization",
}


def _extract_top_level_module(filepath: str) -> str:
    """Extract the top-level module/directory from a file path."""
    parts = filepath.replace("\\", "/").split("/")
    # Skip common root directories
    skip = {"src", "app", "apps", "packages", "lib", "internal"}
    for part in parts:
        if part and part not in skip and not part.startswith("."):
            return part
    return parts[0] if parts else "root"


def _detect_shared_libraries(modules: Set[str], files: List[Dict[str, Any]]) -> List[str]:
    """Detect if any changed files are in shared library directories."""
    shared = set()
    for f in files:
        filepath = f.get("filename", "").replace("\\", "/").lower()
        parts = filepath.split("/")
        for part in parts:
            if part in SHARED_PATTERNS:
                # Use the parent context for a better name
                idx = parts.index(part)
                if idx > 0:
                    shared.add(f"{parts[idx-1]}/{part}")
                else:
                    shared.add(part)
    return sorted(shared)


def _detect_services(files: List[Dict[str, Any]]) -> List[str]:
    """Detect which services are affected based on directory naming conventions."""
    services = set()
    for f in files:
        filepath = f.get("filename", "").replace("\\", "/").lower()
        parts = filepath.split("/")
        for i, part in enumerate(parts):
            if part in SERVICE_PATTERNS and i > 0:
                services.add(parts[i - 1])
            elif part.endswith("-service") or part.endswith("_service"):
                services.add(part)
    return sorted(services)


def _detect_cross_cutting(files: List[Dict[str, Any]]) -> List[str]:
    """Detect cross-cutting concerns that are modified."""
    concerns = set()
    for f in files:
        filepath = f.get("filename", "").replace("\\", "/").lower()
        parts = filepath.split("/")
        for part in parts:
            if part in CROSS_CUTTING_PATTERNS:
                concerns.add(CROSS_CUTTING_PATTERNS[part])
    return sorted(concerns)


def analyze_blast_radius(files: List[Dict[str, Any]]) -> BlastRadiusReport:
    """
    Analyze the blast radius of a PR by examining which modules/services are affected.

    Args:
        files: List of file dicts from the GitHub API.

    Returns:
        BlastRadiusReport with affected modules, services, and shared libraries.
    """
    # Extract unique top-level modules
    modules: Set[str] = set()
    for f in files:
        module = _extract_top_level_module(f.get("filename", ""))
        modules.add(module)

    affected_modules = sorted(modules)
    affected_services = _detect_services(files)
    shared_libs = _detect_shared_libraries(modules, files)
    cross_cutting = _detect_cross_cutting(files)

    return BlastRadiusReport(
        affected_modules=affected_modules,
        affected_services=affected_services,
        shared_libraries_impacted=shared_libs,
        cross_cutting_concerns=cross_cutting,
        total_modules_affected=len(affected_modules),
    )
