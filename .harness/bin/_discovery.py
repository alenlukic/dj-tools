"""Repo discovery: traverse, detect manifests/docs/surfaces, infer profile."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from _state import now_iso

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".cursor",
    ".harness/runs", ".harness/change_summaries", ".harness/pr_descriptions",
}

MANIFEST_NAMES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "setup.py", "setup.cfg", "pyproject.toml", "Pipfile",
    "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
    "Gemfile", "Gemfile.lock", "composer.json",
    "Makefile", "CMakeLists.txt", "build.gradle", "pom.xml",
    "MANIFEST.yaml",
}

CI_PATTERNS = {
    ".github/workflows", ".gitlab-ci.yml", "Jenkinsfile",
    ".circleci/config.yml", ".travis.yml", "azure-pipelines.yml",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
}

DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}

INSTRUCTION_SURFACE_NAMES = {
    "AGENTS.md", "HUMANS.md", "CLAUDE.md", "README.md",
    "BOOTSTRAP.md", "CONTRIBUTING.md",
}

FRAMEWORK_MARKERS = {
    "next.config.js": "Next.js",
    "next.config.mjs": "Next.js",
    "next.config.ts": "Next.js",
    "nuxt.config.ts": "Nuxt",
    "angular.json": "Angular",
    "vite.config.ts": "Vite",
    "vite.config.js": "Vite",
    "webpack.config.js": "Webpack",
    "tailwind.config.js": "Tailwind CSS",
    "tailwind.config.ts": "Tailwind CSS",
    "tsconfig.json": "TypeScript",
    "jest.config.js": "Jest",
    "jest.config.ts": "Jest",
    "vitest.config.ts": "Vitest",
    "pytest.ini": "pytest",
    "conftest.py": "pytest",
    ".eslintrc.js": "ESLint",
    ".eslintrc.json": "ESLint",
    "eslint.config.js": "ESLint",
    "biome.json": "Biome",
    ".prettierrc": "Prettier",
    "terraform.tf": "Terraform",
    "main.tf": "Terraform",
}

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".sql": "SQL",
    ".css": "CSS",
    ".scss": "SCSS",
    ".html": "HTML",
    ".mdc": "MDC",
}

HIGH_RISK_INDICATORS = {
    "terraform", "secrets", "deploy", "infra", "migration",
    "auth", "security", ".env", "credentials",
}


def _should_skip(path: Path, repo_root: Path) -> bool:
    rel = str(path.relative_to(repo_root))
    for skip in SKIP_DIRS:
        if rel == skip or rel.startswith(skip + "/"):
            return True
    return False


def scan_repo(repo_root: str) -> dict[str, Any]:
    """Full traversal producing raw inventory data."""
    root = Path(repo_root)
    inventory: dict[str, Any] = {
        "repo_root": str(root),
        "scanned_at": now_iso(),
        "manifests": [],
        "ci_configs": [],
        "scripts": [],
        "docs": [],
        "entrypoints": [],
        "framework_markers": [],
        "instruction_surfaces": [],
        "major_directories": [],
        "language_stats": {},
        "high_risk_paths": [],
        "inferred_relationships": [],
    }

    lang_counts: dict[str, int] = {}
    top_dirs: set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        if _should_skip(dp, root):
            dirnames.clear()
            continue

        rel_dir = str(dp.relative_to(root))
        if rel_dir != "." and rel_dir.count("/") == 0:
            top_dirs.add(rel_dir)

        for fn in filenames:
            fp = dp / fn
            rel = str(fp.relative_to(root))

            if fn in MANIFEST_NAMES:
                inventory["manifests"].append(rel)

            for ci in CI_PATTERNS:
                if rel == ci or rel.startswith(ci + "/") or fn == ci:
                    inventory["ci_configs"].append(rel)
                    break

            ext = fp.suffix.lower()
            if ext in DOC_EXTENSIONS:
                inventory["docs"].append(rel)

            if fn in INSTRUCTION_SURFACE_NAMES:
                inventory["instruction_surfaces"].append(rel)

            if fn in FRAMEWORK_MARKERS:
                inventory["framework_markers"].append({
                    "file": rel,
                    "framework": FRAMEWORK_MARKERS[fn],
                })

            if ext in LANGUAGE_EXTENSIONS:
                lang = LANGUAGE_EXTENSIONS[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            if fn.endswith(".sh") or fn == "Makefile":
                inventory["scripts"].append(rel)

            if fn in ("main.py", "app.py", "index.ts", "index.js", "main.go", "main.rs"):
                inventory["entrypoints"].append(rel)

            for risk in HIGH_RISK_INDICATORS:
                if risk in rel.lower():
                    inventory["high_risk_paths"].append(rel)
                    break

    inventory["major_directories"] = sorted(top_dirs)
    inventory["language_stats"] = dict(sorted(lang_counts.items(), key=lambda x: -x[1]))

    _infer_relationships(inventory)

    return inventory


def _infer_relationships(inv: dict[str, Any]) -> None:
    """Lightweight relationship inference from co-located files."""
    rels = []
    manifest_dirs = {str(Path(m).parent) for m in inv["manifests"]}
    for md in manifest_dirs:
        if md != ".":
            rels.append({
                "type": "workspace_member",
                "path": md,
                "evidence": [m for m in inv["manifests"] if m.startswith(md + "/") or Path(m).parent == Path(md)],
            })
    inv["inferred_relationships"] = rels


def infer_profile(inventory: dict[str, Any], repo_root: str) -> dict[str, Any]:
    """Build repo-profile.yaml from raw inventory."""
    root = Path(repo_root)
    repo_name = root.name

    languages = []
    for lang, count in inventory.get("language_stats", {}).items():
        if lang not in ("YAML", "JSON", "TOML"):
            languages.append({"name": lang, "file_count": count, "confidence": 0.8})

    frameworks = []
    seen_fw = set()
    for fm in inventory.get("framework_markers", []):
        fw = fm["framework"]
        if fw not in seen_fw:
            seen_fw.add(fw)
            frameworks.append({
                "name": fw,
                "evidence": fm["file"],
                "confidence": 0.9,
            })

    modules = _infer_modules(inventory, repo_root)

    commands = _infer_commands(inventory, repo_root)

    surfaces = {}
    for s in inventory.get("instruction_surfaces", []):
        name = Path(s).name
        surfaces[name] = s

    docs_map = []
    for d in inventory.get("docs", []):
        docs_map.append({"path": d, "type": "documentation"})

    high_risk = []
    seen_hr = set()
    for p in inventory.get("high_risk_paths", []):
        domain = _classify_risk_domain(p)
        if domain and domain not in seen_hr:
            seen_hr.add(domain)
            high_risk.append({"domain": domain, "evidence": p})

    profile = {
        "schema_version": "1",
        "repo": {
            "name": repo_name,
            "root": str(root),
            "description": f"Repository: {repo_name}",
        },
        "languages": languages,
        "frameworks": frameworks,
        "modules": [m["name"] for m in modules],
        "commands": {c["command_id"]: c["kind"] for c in commands},
        "runtime_surfaces": inventory.get("major_directories", []),
        "high_risk_domains": high_risk,
        "docs_map": docs_map,
        "instruction_surfaces": surfaces,
        "confidence": {
            "languages": 0.8,
            "frameworks": 0.9 if frameworks else 0.5,
            "modules": 0.7,
            "commands": 0.6,
        },
        "last_scanned": now_iso(),
        "last_verified": None,
    }
    return profile


def _infer_modules(inventory: dict[str, Any], repo_root: str) -> list[dict[str, Any]]:
    """Infer module/workspace boundaries."""
    modules = []
    root = Path(repo_root)

    harness_indicators = [
        p for p in inventory.get("scripts", [])
        if p.startswith(".harness/")
    ]
    if harness_indicators or (root / ".harness").is_dir():
        modules.append({
            "name": "harness",
            "path": ".harness",
            "type": "tooling",
            "confidence": 0.95,
            "evidence": harness_indicators[:3] if harness_indicators else [".harness/pipeline.yaml"],
            "ownership": "repo-infrastructure",
        })

    manifest_dirs = set()
    for m in inventory.get("manifests", []):
        d = str(Path(m).parent)
        if d != ".":
            manifest_dirs.add(d)

    for md in sorted(manifest_dirs):
        if not md.startswith(".harness"):
            modules.append({
                "name": Path(md).name,
                "path": md,
                "type": "workspace_member",
                "confidence": 0.7,
                "evidence": [m for m in inventory["manifests"] if str(Path(m).parent) == md],
                "ownership": "unknown",
            })

    if not modules:
        modules.append({
            "name": root.name,
            "path": ".",
            "type": "monolith",
            "confidence": 0.5,
            "evidence": ["root-level project"],
            "ownership": "unknown",
        })

    return modules


def _infer_commands(inventory: dict[str, Any], repo_root: str) -> list[dict[str, Any]]:
    """Infer command registry from known scripts and harness config."""
    commands = []
    root = Path(repo_root)

    pipeline_yaml = root / ".harness" / "pipeline.yaml"
    if pipeline_yaml.exists():
        commands.append({
            "command_id": "pipeline-runner",
            "kind": "build",
            "canonical": "python3 .harness/bin/pipeline.py",
            "alternates": [],
            "scope": "repo",
            "confidence": 0.95,
            "evidence": ".harness/pipeline.yaml",
            "last_verified": None,
        })

    setup_sh = root / ".harness" / "bin" / "setup.sh"
    if setup_sh.exists():
        commands.append({
            "command_id": "ide-setup",
            "kind": "local-run",
            "canonical": "bash .harness/bin/setup.sh",
            "alternates": [],
            "scope": "repo",
            "confidence": 0.95,
            "evidence": ".harness/bin/setup.sh",
            "last_verified": None,
        })

    bootstrap_py = root / ".harness" / "bin" / "bootstrap.py"
    if bootstrap_py.exists():
        commands.append({
            "command_id": "bootstrap",
            "kind": "local-run",
            "canonical": "python3 .harness/bin/bootstrap.py",
            "alternates": [],
            "scope": "repo",
            "confidence": 0.95,
            "evidence": ".harness/bin/bootstrap.py",
            "last_verified": None,
        })

    for script in inventory.get("scripts", []):
        if script.startswith(".harness/"):
            continue
        cmd_id = Path(script).stem
        commands.append({
            "command_id": cmd_id,
            "kind": "local-run",
            "canonical": f"bash {script}",
            "alternates": [],
            "scope": "repo",
            "confidence": 0.6,
            "evidence": script,
            "last_verified": None,
        })

    return commands


def _classify_risk_domain(path):
    # type: (str) -> Optional[str]
    lower = path.lower()
    if "terraform" in lower or "infra" in lower:
        return "infrastructure"
    if "secret" in lower or "credential" in lower:
        return "secrets"
    if "deploy" in lower:
        return "deployment"
    if "auth" in lower or "security" in lower:
        return "security"
    if "migration" in lower:
        return "migration"
    if ".env" in lower:
        return "environment-config"
    return None


def infer_module_map(inventory: dict[str, Any], repo_root: str) -> list[dict[str, Any]]:
    return _infer_modules(inventory, repo_root)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
