from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml


HARNESS_VERSION = "3.0.0-candidate.1"
SCHEMA = "harness-project-governance/v3"
RECORDS_SCHEMA = "harness-records/v1"
INDEX_SCHEMA = "harness-vector-index/v2"
CORE_INVARIANTS = {
    "authority_consistency",
    "acceptance_required",
    "content_identity",
    "current_uniqueness",
    "lineage_acyclic",
    "source_required",
}
PROPOSAL_STATES = {"draft", "active", "merged", "completed", "archived"}
DOCUMENT_STATES = {"proposed", "current", "legacy", "history"}
ROLES = {"DEV", "SPEC", "RELEASE", "COMPACT", "LEGACY"}
PLACEHOLDERS = re.compile(r"(?i)(<[^>]+>|\bTBD\b|\bTODO\b|fill[- ]?me|coming soon)")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)")
TOKEN_RE = re.compile(r"[A-Za-z0-9_.:/@-]+|[\u3400-\u9fff]")
STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "to", "while", "with"}
_ACTIVE_LOCKS: dict[str, int] = {}


class HarnessError(Exception):
    def __init__(self, message: str, *, code: str = "validation_error", exit_code: int = 3, details: Any = None):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.details = details


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def yaml_text(value: Any) -> str:
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=1000)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HarnessError(f"required file is missing: {path}", code="not_initialized", exit_code=4)
    except yaml.YAMLError as exc:
        raise HarnessError(f"invalid YAML in {path}: {exc}")
    if not isinstance(value, dict):
        raise HarnessError(f"YAML root must be a mapping: {path}")
    return value


def safe_rel(root: Path, value: str | Path) -> str:
    p = Path(value)
    full = (root / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        return full.relative_to(root.resolve()).as_posix()
    except ValueError:
        raise HarnessError(f"path escapes project root: {value}")


def resolve_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser().resolve()
    proc = subprocess.run(["git", "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    if proc.returncode == 0:
        return Path(proc.stdout.strip()).resolve()
    return Path.cwd().resolve()


def config_path(root: Path) -> Path:
    return root / ".harness" / "project.yaml"


def records_path(root: Path) -> Path:
    return root / ".harness" / "records.yaml"


def default_records() -> dict[str, Any]:
    return {
        "schema": RECORDS_SCHEMA,
        "modules": [],
        "contracts": [],
        "proposals": [],
        "documents": [],
        "evidence": [],
        "migrations": [],
    }


def pending_transactions(root: Path) -> list[str]:
    txn_root = root / ".harness" / "transactions"
    if not txn_root.is_dir():
        return []
    return [p.name for p in txn_root.iterdir() if p.is_dir() and not (p / "COMMITTED").exists()]


def load_project(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    pending = pending_transactions(root)
    if pending:
        raise HarnessError(
            "an interrupted mutation requires recovery by a mutating command",
            code="recovery_required",
            exit_code=4,
            details={"transactions": pending},
        )
    cfg = load_yaml(config_path(root))
    rec = load_yaml(records_path(root))
    if cfg.get("schema") != SCHEMA:
        raise HarnessError(f"unsupported project schema: {cfg.get('schema')!r}")
    if rec.get("schema") != RECORDS_SCHEMA:
        raise HarnessError(f"unsupported records schema: {rec.get('schema')!r}")
    for key in ("modules", "contracts", "proposals", "documents", "evidence", "migrations"):
        if not isinstance(rec.get(key), list):
            raise HarnessError(f"records field must be a list: {key}")
    return cfg, rec


@contextlib.contextmanager
def bounded_lock(path: Path, timeout: float = 10.0) -> Iterator[None]:
    key = str(path.resolve())
    if _ACTIVE_LOCKS.get(key, 0):
        _ACTIVE_LOCKS[key] += 1
        try:
            yield
        finally:
            _ACTIVE_LOCKS[key] -= 1
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise HarnessError(f"timed out waiting for lock: {path}", code="lock_timeout", exit_code=4)
                time.sleep(0.05)
        try:
            _ACTIVE_LOCKS[key] = 1
            yield
        finally:
            _ACTIVE_LOCKS.pop(key, None)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def mutation_guard(root: Path) -> Iterator[None]:
    """Serialize recovery, read/validate, and commit for project mutations."""
    with bounded_lock(root / ".harness" / "write.lock"):
        recover_transactions(root)
        yield


def recover_transactions(root: Path) -> None:
    txn_root = root / ".harness" / "transactions"
    if not txn_root.is_dir():
        return
    for txn in sorted(txn_root.iterdir()):
        if not txn.is_dir():
            continue
        manifest = txn / "manifest.json"
        if not manifest.exists():
            shutil.rmtree(txn, ignore_errors=True)
            continue
        entries = json.loads(manifest.read_text(encoding="utf-8"))
        if not (txn / "COMMITTED").exists():
            for entry in reversed(entries):
                target = root / entry["path"]
                backup = txn / "old" / entry["path"]
                if entry["existed"]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if backup.exists():
                        os.replace(backup, target)
                elif target.exists():
                    if target.is_file() or target.is_symlink():
                        target.unlink()
                    else:
                        shutil.rmtree(target)
        shutil.rmtree(txn, ignore_errors=True)


def atomic_batch_write(root: Path, writes: dict[str, bytes | None]) -> None:
    """Apply a prepared file plan with crash recovery. None deletes a file."""
    txn_root = root / ".harness" / "transactions"
    txn = txn_root / str(uuid.uuid4())
    new_root, old_root = txn / "new", txn / "old"
    new_root.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    for rel, content in sorted(writes.items()):
        rel = safe_rel(root, rel)
        target = root / rel
        entries.append({"path": rel, "existed": target.exists(), "delete": content is None})
        if target.exists():
            backup = old_root / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        if content is not None:
            staged = new_root / rel
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(content)
    (txn / "manifest.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    try:
        for entry in entries:
            target = root / entry["path"]
            if entry["delete"]:
                if target.exists():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(new_root / entry["path"], target)
        (txn / "COMMITTED").write_text("ok\n", encoding="utf-8")
    except BaseException:
        recover_transactions(root)
        raise
    shutil.rmtree(txn, ignore_errors=True)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise HarnessError("unterminated YAML frontmatter")
    try:
        meta = yaml.safe_load("".join(lines[1:end])) or {}
    except yaml.YAMLError as exc:
        raise HarnessError(f"invalid document frontmatter: {exc}")
    if not isinstance(meta, dict):
        raise HarnessError("document frontmatter must be a mapping")
    return meta, "".join(lines[end + 1 :]).lstrip("\n")


def render_document(doc: dict[str, Any], body: str) -> bytes:
    meta = {
        "id": doc["id"],
        "role": doc["role"],
        "status": doc["status"],
        "proposal": doc.get("proposal_id"),
        "source-kind": doc["source"]["kind"],
        "merged-into": doc.get("merged_into"),
    }
    if doc.get("contract_ids"):
        meta["contracts"] = doc["contract_ids"]
    return ("---\n" + yaml_text(meta) + "---\n\n" + body.rstrip() + "\n").encode("utf-8")


def update_document(root: Path, doc: dict[str, Any], *, old_path: str | None = None) -> dict[str, bytes | None]:
    source_path = root / (old_path or doc["path"])
    _, body = split_frontmatter(source_path.read_text(encoding="utf-8"))
    writes: dict[str, bytes | None] = {doc["path"]: render_document(doc, body)}
    if old_path and old_path != doc["path"]:
        writes[old_path] = None
    return writes


def markdown_body_identity(root: Path, docs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = []
    for doc in sorted(docs, key=lambda x: x["id"]):
        _, body = split_frontmatter((root / doc["path"]).read_text(encoding="utf-8"))
        items.append({"document_id": doc["id"], "sha256": sha256_bytes(body.encode("utf-8"))})
    if not items:
        raise HarnessError("docs-only identity has no proposal documents", code="empty_identity")
    digest = sha256_bytes(json.dumps(items, sort_keys=True, separators=(",", ":")).encode())
    return {"kind": "document-bodies", "items": items, "sha256": digest}


def compact_sections(body: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## (DEV|SPEC|RELEASE)\s*$", body))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[match.group(1)] = body[match.end() : end].strip()
    if set(result) != {"DEV", "SPEC", "RELEASE"} or any(not value for value in result.values()):
        raise HarnessError("compact proposal must contain nonempty ## DEV, ## SPEC, and ## RELEASE sections")
    return result


def contract_content_identity(root: Path, docs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for doc in docs:
        _, body = split_frontmatter((root / doc["path"]).read_text(encoding="utf-8"))
        if doc["role"] == "COMPACT":
            sections = compact_sections(body)
            for role in ("SPEC", "RELEASE"):
                items.append({"role": role, "contract_ids": sorted(doc.get("contract_ids", [])), "sha256": sha256_bytes(sections[role].encode())})
        elif doc["role"] in {"SPEC", "RELEASE"}:
            items.append({"role": doc["role"], "contract_ids": sorted(doc.get("contract_ids", [])), "sha256": sha256_bytes(body.strip().encode())})
    items.sort(key=lambda x: (x["role"], x["contract_ids"]))
    if not items:
        raise HarnessError("proposal has no contract content", code="empty_identity")
    return {"kind": "contract-content-v1", "items": items, "sha256": sha256_bytes(json.dumps(items, sort_keys=True, separators=(",", ":")).encode())}


def content_identity(root: Path, rel_paths: Iterable[str]) -> dict[str, Any]:
    declared_paths = sorted({safe_rel(root, value) for value in rel_paths})
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for rel in declared_paths:
        target = root / rel
        if not target.exists():
            raise HarnessError(f"identity path does not exist: {rel}", code="empty_identity")
        candidates = [target] if target.is_file() else sorted(p for p in target.rglob("*") if p.is_file())
        for path in candidates:
            item_rel = path.relative_to(root).as_posix()
            if item_rel.startswith(".harness/") or "/.git/" in f"/{item_rel}/" or item_rel.startswith(".git/"):
                continue
            if item_rel in seen:
                continue
            seen.add(item_rel)
            files.append({"path": item_rel, "sha256": sha256_file(path)})
    if not files:
        raise HarnessError("implementation_paths resolve to no implementation files", code="empty_identity")
    digest = sha256_bytes(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
    return {"kind": "content-tree", "declared_paths": declared_paths, "items": files, "sha256": digest}


def verify_identity(root: Path, identity: dict[str, Any], proposal_docs: list[dict[str, Any]]) -> bool:
    if identity.get("kind") == "content-tree":
        declared = identity.get("declared_paths")
        if not declared:
            return False
        return content_identity(root, declared)["sha256"] == identity.get("sha256")
    if identity.get("kind") == "document-bodies":
        ids = {x["document_id"] for x in identity.get("items", [])}
        return markdown_body_identity(root, [d for d in proposal_docs if d["id"] in ids])["sha256"] == identity.get("sha256")
    return False


def proposal_acceptance_identity(root: Path, rec: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    docs = [d for d in rec["documents"] if d.get("proposal_id") == proposal["id"] and d["role"] in {"SPEC", "RELEASE", "COMPACT"}]
    contract_content = contract_content_identity(root, docs)
    implementation = contract_content if proposal.get("docs_only") else content_identity(root, proposal.get("implementation_paths", []))
    scope = {
        "proposal_id": proposal["id"],
        "changes": proposal["changes"],
        "required_scenarios": proposal["required_scenarios"],
        "docs_only": bool(proposal.get("docs_only")),
    }
    value = {"kind": "proposal-acceptance-v1", "implementation": implementation, "contract_content": contract_content, "scope": scope}
    value["sha256"] = sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
    return value


def verify_proposal_acceptance_identity(root: Path, rec: dict[str, Any], proposal: dict[str, Any], identity: dict[str, Any]) -> bool:
    if identity.get("kind") != "proposal-acceptance-v1":
        return False
    try:
        current = proposal_acceptance_identity(root, rec, proposal)
    except HarnessError:
        return False
    return current.get("sha256") == identity.get("sha256")


def record_map(records: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {str(x["id"]): x for x in records[key]}


def current_contracts(records: dict[str, Any]) -> list[dict[str, Any]]:
    return [x for x in records["contracts"] if x.get("status") == "current"]


def contract_key(value: dict[str, Any]) -> tuple[str, str]:
    return str(value.get("contract_id")), str(value.get("scope"))


def contract_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    keep = {k: value.get(k) for k in ("record_id", "contract_id", "module_id", "scope", "version", "source_document_id")}
    keep["sha256"] = sha256_bytes(json.dumps(keep, sort_keys=True).encode())
    return keep


def parse_change(text: str) -> dict[str, Any]:
    parts = text.split(":", 4)
    if len(parts) != 5 or parts[0] not in {"add", "modify", "supersede"} or not all(parts):
        raise HarnessError("--change must be ACTION:CONTRACT:MODULE:SCOPE:VERSION")
    action, contract_id, module_id, scope, version = parts
    return {
        "action": action,
        "contract_id": contract_id,
        "module_id": module_id,
        "scope": scope,
        "version": version,
    }


def id_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "contract"


def proposal_document_body(proposal_id: str, title: str, scenarios: list[str], role: str, change: dict[str, Any] | None = None) -> str:
    scenario_lines = "\n".join(f"- {item}" for item in scenarios)
    if role == "DEV":
        return f"# {title} - Development Record\n\n## Scope\n{title}\n\n## Decisions and verification\nRecord implementation decisions, failures, fixes, and commands here without rewriting prior results.\n"
    assert change is not None
    identity = f"{change['contract_id']} / {change['scope']} / {change['version']}"
    if role == "SPEC":
        return f"# {title} - Proposed Specification\n\n## Contract identity\n{identity}\n\n## Intent\nThis proposal defines candidate behavior for {change['contract_id']}.\n\n## Required acceptance scenarios\n{scenario_lines}\n\n## Non-goals\nOnly the registered contract scope may be promoted.\n"
    return f"# {title} - Pending Release Contract\n\n## Contract identity\n{identity}\n\n## Scope\nCandidate delivery for {change['contract_id']} in {proposal_id}.\n\n## Distribution\nPending. Acceptance does not by itself assert deployment or publication.\n"


def make_document(doc_id: str, path: str, role: str, status: str, proposal_id: str | None, *, source_kind: str = "proposal", contract_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": doc_id,
        "path": path,
        "role": role,
        "status": status,
        "proposal_id": proposal_id,
        "module_ids": [],
        "contract_ids": contract_ids or [],
        "source": {"kind": source_kind, "proposal_id": proposal_id},
        "merged_into": None,
    }


def governance_root(cfg: dict[str, Any]) -> str:
    return str(cfg.get("governance_root", "docs"))


def generate_indexes(records: dict[str, Any], base: str = "docs") -> dict[str, bytes]:
    proposal_rows, spec_rows, release_rows = [], [], []
    for p in sorted(records["proposals"], key=lambda x: x["id"]):
        proposal_rows.append(f"| {p['id']} | [{p['title']}](./{p['id']}/README.md) | {p['status']} | {p.get('merged_into') or ''} |")
    for d in sorted(records["documents"], key=lambda x: x["id"]):
        if d["status"] not in {"current", "history"}:
            continue
        if not (d["path"].startswith(f"{base}/SPEC/") or d["path"].startswith(f"{base}/RELEASE/")):
            continue
        row = f"| {d.get('proposal_id') or ''} | [{d['id']}](./{Path(d['path']).name}) | {d['status']} | {', '.join(d.get('contract_ids', []))} |"
        if d["role"] == "SPEC":
            spec_rows.append(row)
        elif d["role"] == "RELEASE":
            release_rows.append(row)
    files = {
        f"{base}/README.md": "# Governance Registry\n\n- [Proposals](PROPOSALS/README.md)\n- [Current specifications](SPEC/README.md)\n- [Accepted release contracts](RELEASE/README.md)\n\nLifecycle status is owned by `.harness/records.yaml`; these indexes are generated views.\n",
        f"{base}/PROPOSALS/README.md": "# Proposal Registry\n\n| Proposal | Document | Status | Merged into |\n| --- | --- | --- | --- |\n" + ("\n".join(proposal_rows) if proposal_rows else "|  |  |  |  |") + "\n",
        f"{base}/SPEC/README.md": "# Current Specification Registry\n\n| Proposal | Document | Status | Contracts |\n| --- | --- | --- | --- |\n" + ("\n".join(spec_rows) if spec_rows else "|  |  |  |  |") + "\n",
        f"{base}/RELEASE/README.md": "# Accepted Release Registry\n\nAccepted here means user-approved delivery contract; it does not imply deployment.\n\n| Proposal | Document | Status | Contracts |\n| --- | --- | --- | --- |\n" + ("\n".join(release_rows) if release_rows else "|  |  |  |  |") + "\n",
    }
    return {k: v.encode("utf-8") for k, v in files.items()}


def bundled_runtime() -> tuple[dict[str, bytes], dict[str, Any]]:
    base = Path(__file__).parent
    names = ("harness.py", "harnesslib.py", "model-manifest.json", "requirements.lock")
    files = {f".harness/runtime/{name}": (base / name).read_bytes() for name in names}
    manifest = {"harness_version": HARNESS_VERSION, "files": {path: sha256_bytes(data) for path, data in files.items()}}
    return files, manifest


def runtime_upgrade(root: Path, *, apply: bool = False) -> dict[str, Any]:
    cfg, _ = load_project(root)
    new_files, new_manifest = bundled_runtime()
    installed_path = root / ".harness" / "runtime-manifest.json"
    installed = json.loads(installed_path.read_text(encoding="utf-8")) if installed_path.exists() else {"files": {}}
    changed, conflicts = [], []
    for rel, content in new_files.items():
        target = root / rel
        new_hash = sha256_bytes(content)
        current_hash = sha256_file(target) if target.is_file() else None
        installed_hash = installed.get("files", {}).get(rel)
        if current_hash == new_hash:
            continue
        changed.append(rel)
        if current_hash is not None and current_hash != installed_hash:
            conflicts.append(rel)
    result = {"from_version": cfg.get("harness_version"), "to_version": HARNESS_VERSION, "changed": changed, "conflicts": conflicts, "extensions_preserved": ".harness/extensions"}
    if apply:
        if conflicts:
            raise HarnessError("runtime upgrade would overwrite local managed-file changes", code="upgrade_conflict", details=result)
        cfg["harness_version"] = HARNESS_VERSION
        writes: dict[str, bytes | None] = {rel: data for rel, data in new_files.items()}
        writes[".harness/runtime-manifest.json"] = (json.dumps(new_manifest, indent=2, sort_keys=True) + "\n").encode()
        writes[".harness/project.yaml"] = yaml_text(cfg).encode()
        atomic_batch_write(root, writes)
        result["applied"] = True
    else:
        result["applied"] = False
    return result


def create_project(root: Path, project_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    targets = [config_path(root), records_path(root)]
    if any(p.exists() for p in targets):
        if config_path(root).exists() and records_path(root).exists():
            cfg, rec = load_project(root)
            return {"changed": False, "project_id": cfg["project_id"], "documents": len(rec["documents"])}
        raise HarnessError("partial harness already exists; init will not overwrite it", code="conflict")
    existing_docs = root / "docs" / "README.md"
    base = "docs/governance" if existing_docs.exists() else "docs"
    cfg = {
        "schema": SCHEMA,
        "harness_version": HARNESS_VERSION,
        "project_id": project_id,
        "governance_root": base,
        "created_at": utc_now(),
        "core_invariants": sorted(CORE_INVARIANTS),
        "embedding": {
            "model_manifest": "model-manifest.json",
            "chunk_schema": "markdown-headings-360-v2",
        },
        "legacy_roots": [],
        "lock_policy": {"enabled": True, "exemptions": []},
    }
    rec = default_records()
    runtime_files, runtime_manifest = bundled_runtime()
    writes: dict[str, bytes | None] = {
        ".harness/project.yaml": yaml_text(cfg).encode(),
        ".harness/records.yaml": yaml_text(rec).encode(),
        ".harness/runtime-manifest.json": (json.dumps(runtime_manifest, indent=2, sort_keys=True) + "\n").encode(),
    }
    writes.update(runtime_files)
    writes.update(generate_indexes(rec, base))
    notices: list[str] = []
    agents = root / "AGENTS.md"
    if not agents.exists():
        writes["AGENTS.md"] = (
            "# Agent entry\n\n"
            "Project definition status is owned by `.harness/records.yaml`. Read current specifications through "
            f"`{base}/SPEC/README.md` and run `python .harness/runtime/harness.py --root . check` before promotion. "
            "Existing source and legacy documents are not formal unless registered.\n"
        ).encode()
    else:
        notices.append("Existing AGENTS.md was preserved; add a pointer to .harness/records.yaml and the vendored check command if it is not already routed there.")
    ignore_rules = [".harness/index/", ".harness/transactions/", ".harness/*.lock", ".harness/cache/"]
    gitignore = root / ".gitignore"
    existing_ignore = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    missing_rules = [rule for rule in ignore_rules if rule not in existing_ignore.splitlines()]
    if missing_rules:
        prefix = existing_ignore
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        writes[".gitignore"] = (prefix + "\n# Harness rebuildable runtime state\n" + "\n".join(missing_rules) + "\n").encode()
    if not dry_run:
        atomic_batch_write(root, writes)
    return {"changed": True, "project_id": project_id, "planned_files": sorted(writes), "dry_run": dry_run, "integration_notices": notices}


def create_proposal(root: Path, proposal_id: str, title: str, changes: list[dict[str, Any]], scenarios: list[str], identity_paths: list[str], docs_only: bool, layout: str = "split", *, dry_run: bool = False) -> dict[str, Any]:
    cfg, rec = load_project(root)
    gov = governance_root(cfg)
    if proposal_id in record_map(rec, "proposals"):
        raise HarnessError(f"proposal already exists: {proposal_id}", code="conflict")
    if not changes:
        raise HarnessError("a proposal requires at least one --change")
    if not scenarios:
        raise HarnessError("a proposal requires at least one --required-scenario")
    if docs_only and identity_paths:
        raise HarnessError("--docs-only cannot be combined with --implementation-path")
    if not docs_only and not identity_paths:
        raise HarnessError("non-docs proposal requires at least one --implementation-path", code="empty_identity")
    if layout == "compact" and len(changes) != 1:
        raise HarnessError("compact layout supports exactly one changed contract; use split for larger proposals")
    modules = record_map(rec, "modules")
    for change in changes:
        if change["module_id"] not in modules:
            module = {"id": change["module_id"], "title": change["module_id"], "paths": []}
            rec["modules"].append(module)
            modules[change["module_id"]] = module
    current = {contract_key(c): c for c in current_contracts(rec)}
    baselines = []
    for change in changes:
        key = contract_key(change)
        existing = current.get(key)
        if change["action"] == "add" and existing:
            raise HarnessError(f"cannot add existing current contract: {key}", code="conflict")
        if change["action"] in {"modify", "supersede"} and not existing:
            raise HarnessError(f"cannot {change['action']} missing current contract: {key}", code="conflict")
        if existing:
            baselines.append(contract_snapshot(existing))
    base = f"{gov}/PROPOSALS/{proposal_id}"
    if layout == "compact":
        docs = [make_document(f"{proposal_id}-compact", f"{base}/PROPOSAL.md", "COMPACT", "proposed", proposal_id, contract_ids=[changes[0]["contract_id"]])]
    else:
        docs = [make_document(f"{proposal_id}-dev", f"{base}/DEV.md", "DEV", "proposed", proposal_id)]
        compact_names = len(changes) == 1
        for change in changes:
            slug = id_slug(change["contract_id"])
            suffix = "" if compact_names else f"-{slug}"
            docs.extend([
                make_document(f"{proposal_id}-spec{suffix}", f"{base}/SPEC{suffix}.md", "SPEC", "proposed", proposal_id, contract_ids=[change["contract_id"]]),
                make_document(f"{proposal_id}-release{suffix}", f"{base}/RELEASE{suffix}.md", "RELEASE", "proposed", proposal_id, contract_ids=[change["contract_id"]]),
            ])
    proposal = {
        "id": proposal_id,
        "title": title,
        "status": "active",
        "created_at": utc_now(),
        "changes": changes,
        "baseline": baselines,
        "required_scenarios": scenarios,
        "implementation_paths": [safe_rel(root, p) for p in identity_paths],
        "docs_only": docs_only,
        "layout": layout,
        "document_ids": [d["id"] for d in docs],
        "merged_into": None,
    }
    rec["proposals"].append(proposal)
    rec["documents"].extend(docs)
    readme_links = ["- [Compact proposal](PROPOSAL.md)"] if layout == "compact" else ["- [Development record](DEV.md)"]
    for d in docs:
        if d["role"] not in {"DEV", "COMPACT"}:
            readme_links.append(f"- [{d['role']} for {d['contract_ids'][0]}]({Path(d['path']).name})")
    readme = f"---\nproposal: {proposal_id}\n---\n\n# {title}\n\nStatus is owned by `.harness/records.yaml`.\n\n" + "\n".join(readme_links) + "\n"
    writes: dict[str, bytes | None] = {f"{base}/README.md": readme.encode()}
    for d in docs:
        if d["role"] == "COMPACT":
            change = changes[0]
            body = f"# {title} - Compact Proposal\n\n## DEV\n\n" + proposal_document_body(proposal_id, title, scenarios, "DEV") + "\n## SPEC\n\n" + proposal_document_body(proposal_id, title, scenarios, "SPEC", change) + "\n## RELEASE\n\n" + proposal_document_body(proposal_id, title, scenarios, "RELEASE", change)
        else:
            change = next((c for c in changes if d.get("contract_ids") == [c["contract_id"]]), None)
            body = proposal_document_body(proposal_id, title, scenarios, d["role"], change)
        writes[d["path"]] = render_document(d, body)
    writes[".harness/records.yaml"] = yaml_text(rec).encode()
    writes.update(generate_indexes(rec, gov))
    if not dry_run:
        with bounded_lock(root / ".harness" / "write.lock"):
            atomic_batch_write(root, writes)
    return {"proposal": proposal, "planned_files": sorted(writes), "dry_run": dry_run}


def merge_proposal(root: Path, source_id: str, target_id: str, scope: str, *, dry_run: bool = False) -> dict[str, Any]:
    if source_id == target_id:
        raise HarnessError("a proposal cannot merge into itself", code="cycle")
    cfg, rec = load_project(root)
    proposals = record_map(rec, "proposals")
    source, target = proposals.get(source_id), proposals.get(target_id)
    if not source or not target:
        raise HarnessError("merge source and target must both exist")
    if source["status"] not in {"draft", "active"} or target["status"] not in {"draft", "active"}:
        raise HarnessError("merge source and target must be active or draft", code="invalid_transition")
    if source.get("layout") == "compact" or target.get("layout") == "compact":
        raise HarnessError("expand compact proposals by promoting or recreating them with split layout before merge", code="merge_conflict")
    cursor = target
    visited = {source_id}
    while cursor.get("merged_into"):
        nxt = cursor["merged_into"]
        if nxt in visited:
            raise HarnessError("proposal merge would create a cycle", code="cycle")
        visited.add(nxt)
        cursor = proposals.get(nxt) or {}
    source["status"] = "merged"
    source["merged_into"] = target_id
    source["merge_scope"] = scope
    source["merged_at"] = utc_now()
    target.setdefault("merged_from", []).append({"proposal_id": source_id, "scope": scope})
    source_contract_ids = {x["contract_id"] for x in source["changes"]}
    target_contract_ids = {x["contract_id"] for x in target["changes"]}
    if source_contract_ids & target_contract_ids:
        raise HarnessError(f"merge has overlapping contract changes requiring explicit consolidation: {sorted(source_contract_ids & target_contract_ids)}", code="merge_conflict")
    target_changes = {(x["action"], x["contract_id"], x["scope"], x["version"]) for x in target["changes"]}
    for change in source["changes"]:
        key = (change["action"], change["contract_id"], change["scope"], change["version"])
        if key not in target_changes:
            target["changes"].append(change)
    baseline_keys = {(x["contract_id"], x["scope"]) for x in target["baseline"]}
    target["baseline"].extend(x for x in source["baseline"] if (x["contract_id"], x["scope"]) not in baseline_keys)
    target["required_scenarios"] = list(dict.fromkeys(target["required_scenarios"] + source["required_scenarios"]))
    target["implementation_paths"] = sorted(set(target.get("implementation_paths", [])) | set(source.get("implementation_paths", [])))
    target["docs_only"] = bool(target.get("docs_only") and source.get("docs_only"))
    writes: dict[str, bytes | None] = {}
    for doc in rec["documents"]:
        if doc.get("proposal_id") == source_id:
            doc["status"] = "history"
            doc["merged_into"] = target_id
            writes.update(update_document(root, doc))
    target_dev = next((d for d in rec["documents"] if d.get("proposal_id") == target_id and d["role"] == "DEV"), None)
    source_dev = next((d for d in rec["documents"] if d.get("proposal_id") == source_id and d["role"] == "DEV"), None)
    if target_dev and source_dev:
        _, target_body = split_frontmatter((root / target_dev["path"]).read_text(encoding="utf-8"))
        _, source_body = split_frontmatter((root / source_dev["path"]).read_text(encoding="utf-8"))
        writes[target_dev["path"]] = render_document(target_dev, target_body.rstrip() + f"\n\n## Merged development record from {source_id}\n\nScope: {scope}\n\n" + source_body.rstrip() + "\n")
    target_base = f"{governance_root(cfg)}/PROPOSALS/{target_id}"
    for source_doc in [d for d in rec["documents"] if d.get("proposal_id") == source_id and d["role"] in {"SPEC", "RELEASE"}]:
        contract_id = source_doc["contract_ids"][0]
        clone_id = f"{target_id}-merged-{id_slug(source_doc['id'])}"
        clone_path = f"{target_base}/{source_doc['role']}-merged-{id_slug(contract_id)}.md"
        clone = make_document(clone_id, clone_path, source_doc["role"], "proposed", target_id, contract_ids=[contract_id])
        clone["origin_document_id"] = source_doc["id"]
        _, source_body = split_frontmatter((root / source_doc["path"]).read_text(encoding="utf-8"))
        rec["documents"].append(clone)
        target["document_ids"].append(clone_id)
        writes[clone_path] = render_document(clone, f"# Merged from {source_id}\n\nMerge scope: {scope}\n\n" + source_body.rstrip() + "\n")
    writes[".harness/records.yaml"] = yaml_text(rec).encode()
    writes.update(generate_indexes(rec, governance_root(cfg)))
    if not dry_run:
        with bounded_lock(root / ".harness" / "write.lock"):
            atomic_batch_write(root, writes)
    return {"source": source_id, "target": target_id, "scope": scope, "dry_run": dry_run}


def archive_proposal(root: Path, proposal_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    cfg, rec = load_project(root)
    p = record_map(rec, "proposals").get(proposal_id)
    if not p:
        raise HarnessError(f"unknown proposal: {proposal_id}")
    if p["status"] in {"completed", "merged"}:
        raise HarnessError(f"cannot archive {p['status']} proposal", code="invalid_transition")
    p["status"] = "archived"
    p["archived_at"] = utc_now()
    writes: dict[str, bytes | None] = {}
    for doc in rec["documents"]:
        if doc.get("proposal_id") == proposal_id:
            doc["status"] = "history"
            writes.update(update_document(root, doc))
    writes[".harness/records.yaml"] = yaml_text(rec).encode()
    writes.update(generate_indexes(rec, governance_root(cfg)))
    if not dry_run:
        with bounded_lock(root / ".harness" / "write.lock"):
            atomic_batch_write(root, writes)
    return {"proposal_id": proposal_id, "status": "archived", "dry_run": dry_run}


def proposal_identity(root: Path, rec: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    return proposal_acceptance_identity(root, rec, proposal)


def add_evidence(root: Path, proposal_id: str, scenario: str, result: str, environment: str, command: str, user_acknowledged: bool, user_ack_basis: str | None, *, dry_run: bool = False) -> dict[str, Any]:
    cfg, rec = load_project(root)
    gov = governance_root(cfg)
    proposal = record_map(rec, "proposals").get(proposal_id)
    if not proposal or proposal["status"] not in {"draft", "active"}:
        raise HarnessError("evidence target must be an active or draft proposal")
    if scenario not in proposal["required_scenarios"]:
        raise HarnessError(f"scenario is not registered on proposal: {scenario}")
    if result not in {"pass", "fail"}:
        raise HarnessError("evidence result must be pass or fail")
    if user_acknowledged and not user_ack_basis:
        raise HarnessError("--user-acknowledged requires --user-ack-basis")
    identity = proposal_identity(root, rec, proposal)
    evidence = {
        "id": f"ev-{uuid.uuid4().hex[:16]}",
        "proposal_id": proposal_id,
        "scenario": scenario,
        "result": result,
        "environment": environment,
        "command": command,
        "artifact_identity": identity,
        "recorded_at": utc_now(),
        "user_acknowledgement": {
            "status": "confirmed" if user_acknowledged else "pending",
            "basis": user_ack_basis,
            "claim": "Explicit acknowledgement was supplied to the CLI; the tool does not authenticate the speaker.",
        },
    }
    rec["evidence"].append(evidence)
    if not dry_run:
        with bounded_lock(root / ".harness" / "write.lock"):
            atomic_batch_write(root, {".harness/records.yaml": yaml_text(rec).encode()})
    return {"evidence": evidence, "dry_run": dry_run}


def validate_proposal_preflight(root: Path, proposal: dict[str, Any], docs: list[dict[str, Any]]) -> None:
    if proposal.get("layout") == "compact":
        if len(docs) != 1 or docs[0].get("role") != "COMPACT" or docs[0].get("status") != "proposed":
            raise HarnessError("compact proposal requires one proposed COMPACT document", code="proposal_layout")
    else:
        dev = [d for d in docs if d["role"] == "DEV"]
        specs = [d for d in docs if d["role"] == "SPEC"]
        releases = [d for d in docs if d["role"] == "RELEASE"]
        changed = {c["contract_id"] for c in proposal["changes"]}
        if len(dev) != 1 or {c for d in specs for c in d.get("contract_ids", [])} != changed or {c for d in releases for c in d.get("contract_ids", [])} != changed:
            raise HarnessError("proposal document coverage does not match changed contracts", code="proposal_layout")
    for doc in docs:
        path = root / doc["path"]
        if not path.is_file():
            raise HarnessError(f"proposal document is missing: {doc['path']}", code="document_missing")
        meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
        mirror = {"id": doc["id"], "role": doc["role"], "status": doc["status"], "proposal": doc.get("proposal_id"), "source-kind": doc["source"]["kind"], "merged-into": doc.get("merged_into")}
        for key, expected in mirror.items():
            if meta.get(key) != expected:
                raise HarnessError(f"proposal document metadata drift: {doc['path']} {key}", code="authority_consistency")
        if not body.strip() or PLACEHOLDERS.search(body):
            raise HarnessError(f"proposal document is empty or unfinished: {doc['path']}", code="document_content")
        if doc["role"] == "COMPACT":
            compact_sections(body)


def promote_proposal(root: Path, proposal_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    cfg, rec = load_project(root)
    gov = governance_root(cfg)
    proposal = record_map(rec, "proposals").get(proposal_id)
    if not proposal:
        raise HarnessError(f"unknown proposal: {proposal_id}")
    if proposal["status"] not in {"draft", "active"}:
        raise HarnessError(f"proposal cannot be promoted from {proposal['status']}", code="invalid_transition")
    docs = [d for d in rec["documents"] if d.get("proposal_id") == proposal_id]
    validate_proposal_preflight(root, proposal, docs)
    compact_source: dict[str, Any] | None = None
    compact_body: dict[str, str] = {}
    if proposal.get("layout") == "compact":
        compact_source = docs[0]
        _, body = split_frontmatter((root / compact_source["path"]).read_text(encoding="utf-8"))
        compact_body = compact_sections(body)
        contract_id = proposal["changes"][0]["contract_id"]
        base = f"{gov}/PROPOSALS/{proposal_id}"
        dev_docs = [make_document(f"{proposal_id}-dev", f"{base}/DEV.md", "DEV", "proposed", proposal_id)]
        spec_docs = [make_document(f"{proposal_id}-spec", f"{base}/SPEC.md", "SPEC", "proposed", proposal_id, contract_ids=[contract_id])]
        release_docs = [make_document(f"{proposal_id}-release", f"{base}/RELEASE.md", "RELEASE", "proposed", proposal_id, contract_ids=[contract_id])]
    else:
        dev_docs = [d for d in docs if d["role"] == "DEV"]
        spec_docs = [d for d in docs if d["role"] == "SPEC"]
        release_docs = [d for d in docs if d["role"] == "RELEASE"]
    change_contracts = {c["contract_id"] for c in proposal["changes"]}
    if len(dev_docs) != 1 or len(spec_docs) != len(change_contracts) or len(release_docs) != len(change_contracts):
        raise HarnessError("proposal requires one DEV and one SPEC/RELEASE per changed contract")
    spec_by_contract = {d["contract_ids"][0]: d for d in spec_docs if len(d.get("contract_ids", [])) == 1}
    release_by_contract = {d["contract_ids"][0]: d for d in release_docs if len(d.get("contract_ids", [])) == 1}
    if set(spec_by_contract) != change_contracts or set(release_by_contract) != change_contracts:
        raise HarnessError("proposal SPEC/RELEASE contract coverage is incomplete or ambiguous")
    relevant = [e for e in rec["evidence"] if e["proposal_id"] == proposal_id]
    selected: dict[str, dict[str, Any]] = {}
    for scenario in proposal["required_scenarios"]:
        matches = [e for e in relevant if e["scenario"] == scenario]
        if not matches:
            raise HarnessError(f"missing evidence for required scenario: {scenario}", code="acceptance_required")
        latest = matches[-1]
        if latest["result"] != "pass":
            raise HarnessError(f"latest evidence failed for scenario: {scenario}", code="acceptance_required")
        if latest["user_acknowledgement"]["status"] != "confirmed" or not latest["user_acknowledgement"].get("basis"):
            raise HarnessError(f"explicit user acknowledgement missing for scenario: {scenario}", code="acceptance_required")
        if not verify_proposal_acceptance_identity(root, rec, proposal, latest["artifact_identity"]):
            raise HarnessError(f"accepted artifact changed for scenario: {scenario}", code="stale_evidence")
        selected[scenario] = latest
    current = {contract_key(c): c for c in current_contracts(rec)}
    baseline = {(x["contract_id"], x["scope"]): x for x in proposal["baseline"]}
    for change in proposal["changes"]:
        key = contract_key(change)
        existing = current.get(key)
        if change["action"] == "add":
            if existing:
                raise HarnessError(f"parallel change introduced contract after proposal baseline: {key}", code="baseline_conflict")
        else:
            expected = baseline.get(key)
            if not existing or not expected or contract_snapshot(existing)["sha256"] != expected["sha256"]:
                raise HarnessError(f"current contract changed since proposal baseline: {key}", code="baseline_conflict")
    writes: dict[str, bytes | None] = {}
    if compact_source:
        rec["documents"] = [d for d in rec["documents"] if d["id"] != compact_source["id"]]
        rec["documents"].extend(dev_docs + spec_docs + release_docs)
        proposal["document_ids"] = [d["id"] for d in dev_docs + spec_docs + release_docs]
        writes[compact_source["path"]] = None
        dev_docs[0]["status"] = "history"
        writes[dev_docs[0]["path"]] = render_document(dev_docs[0], compact_body["DEV"])
    else:
        dev_docs[0]["status"] = "history"
        writes.update(update_document(root, dev_docs[0]))
    compact = len(change_contracts) == 1
    for doc in spec_docs + release_docs:
        old = doc["path"]
        doc["status"] = "current"
        suffix = "" if compact else f"--{id_slug(doc['contract_ids'][0])}"
        doc["path"] = f"{gov}/{doc['role']}/{proposal_id}{suffix}.md"
        doc["promoted_at"] = utc_now()
        if compact_source:
            writes[doc["path"]] = render_document(doc, compact_body[doc["role"]])
        else:
            writes.update(update_document(root, doc, old_path=old))
    for change in proposal["changes"]:
        key = contract_key(change)
        existing = current.get(key)
        record_id = f"{change['contract_id']}@{change['version']}#{change['scope']}"
        if any(c["record_id"] == record_id for c in rec["contracts"]):
            raise HarnessError(f"contract record identity already exists: {record_id}", code="conflict")
        if existing:
            existing["status"] = "history"
            existing["superseded_by"] = record_id
            old_source_id = existing.get("source_document_id")
            old_doc = next((d for d in rec["documents"] if d["id"] == old_source_id), None)
            if old_doc and old_doc.get("status") == "current":
                old_doc["status"] = "history"
                old_doc["superseded_by_contract"] = record_id
                writes.update(update_document(root, old_doc))
                for peer in rec["documents"]:
                    if peer.get("proposal_id") == old_doc.get("proposal_id") and peer.get("role") == "RELEASE" and peer.get("status") == "current" and change["contract_id"] in peer.get("contract_ids", []):
                        peer["status"] = "history"
                        peer["superseded_by_contract"] = record_id
                        writes.update(update_document(root, peer))
        rec["contracts"].append({
            "id": record_id,
            "record_id": record_id,
            "contract_id": change["contract_id"],
            "module_id": change["module_id"],
            "scope": change["scope"],
            "version": change["version"],
            "status": "current",
            "source": {"kind": "proposal", "proposal_id": proposal_id},
            "source_document_id": spec_by_contract[change["contract_id"]]["id"],
            "implementation_paths": proposal["implementation_paths"],
            "validation_scenarios": proposal["required_scenarios"],
            "supersedes": existing["record_id"] if existing else None,
            "superseded_by": None,
        })
    proposal["status"] = "completed"
    if compact_source:
        proposal["promoted_from_layout"] = "compact"
        proposal["layout"] = "split"
    proposal["completed_at"] = utc_now()
    proposal["acceptance_evidence_ids"] = [selected[s]["id"] for s in proposal["required_scenarios"]]
    links = ["- [Archived development record](DEV.md)"]
    for doc in spec_docs + release_docs:
        links.append(f"- [{doc['role']} for {doc['contract_ids'][0]}](../../{doc['role']}/{Path(doc['path']).name})")
    readme = f"---\nproposal: {proposal_id}\n---\n\n# {proposal['title']}\n\nStatus is owned by `.harness/records.yaml`.\n\n" + "\n".join(links) + "\n"
    writes[f"{gov}/PROPOSALS/{proposal_id}/README.md"] = readme.encode()
    writes[".harness/records.yaml"] = yaml_text(rec).encode()
    writes.update(generate_indexes(rec, gov))
    if not dry_run:
        with bounded_lock(root / ".harness" / "write.lock"):
            atomic_batch_write(root, writes)
    return {"proposal_id": proposal_id, "status": "completed", "evidence_ids": proposal["acceptance_evidence_ids"], "planned_files": sorted(writes), "dry_run": dry_run}


def register_legacy(root: Path, path: str, document_id: str, *, migration_scope: str | None = None, authorization: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    _, rec = load_project(root)
    rel = safe_rel(root, path)
    if not (root / rel).is_file():
        raise HarnessError(f"legacy document does not exist: {rel}")
    if document_id in record_map(rec, "documents"):
        raise HarnessError(f"document id already exists: {document_id}", code="conflict")
    if bool(migration_scope) != bool(authorization):
        raise HarnessError("special migration requires both --migration-scope and --authorization")
    source = {"kind": "migration" if authorization else "legacy-unverified", "authorization": authorization, "scope": migration_scope}
    doc = {
        "id": document_id, "path": rel, "role": "LEGACY", "status": "legacy", "proposal_id": None,
        "module_ids": [], "contract_ids": [], "source": source, "merged_into": None,
    }
    rec["documents"].append(doc)
    if authorization:
        rec["migrations"].append({"id": f"migration-{uuid.uuid4().hex[:12]}", "scope": migration_scope, "authorization": authorization, "documents": [document_id], "recorded_at": utc_now()})
    if not dry_run:
        with bounded_lock(root / ".harness" / "write.lock"):
            atomic_batch_write(root, {".harness/records.yaml": yaml_text(rec).encode()})
    return {"document": doc, "dry_run": dry_run}


def adopt_migration(root: Path, path: str, document_id: str, contract: str, migration_scope: str, authorization: str, user_ack_basis: str, *, dry_run: bool = False) -> dict[str, Any]:
    cfg, rec = load_project(root)
    parts = contract.split(":", 3)
    if len(parts) != 4 or not all(parts):
        raise HarnessError("--contract must be CONTRACT:MODULE:SCOPE:VERSION")
    contract_id, module_id, contract_scope, version = parts
    if any(contract_key(c) == (contract_id, contract_scope) and c.get("status") == "current" for c in rec["contracts"]):
        raise HarnessError(f"migration would conflict with current contract: {(contract_id, contract_scope)}", code="conflict")
    source_rel = safe_rel(root, path)
    source_path = root / source_rel
    if not source_path.is_file():
        raise HarnessError(f"migration source does not exist: {source_rel}")
    if document_id in record_map(rec, "documents"):
        raise HarnessError(f"document id already exists: {document_id}", code="conflict")
    source_text = source_path.read_text(encoding="utf-8")
    _, body = split_frontmatter(source_text)
    if not body.strip() or PLACEHOLDERS.search(body):
        raise HarnessError("migration source is empty or unfinished")
    migration_id = f"migration-{uuid.uuid4().hex[:12]}"
    doc_path = f"{governance_root(cfg)}/SPEC/migration-{id_slug(document_id)}.md"
    doc = make_document(document_id, doc_path, "SPEC", "current", None, source_kind="migration", contract_ids=[contract_id])
    doc["source"] = {"kind": "migration", "migration_id": migration_id, "original_path": source_rel}
    migration = {
        "id": migration_id,
        "scope": migration_scope,
        "authorization": authorization,
        "user_ack_basis": user_ack_basis,
        "documents": [document_id],
        "source": {"path": source_rel, "sha256": sha256_file(source_path)},
        "recorded_at": utc_now(),
    }
    rec["migrations"].append(migration)
    if module_id not in record_map(rec, "modules"):
        rec["modules"].append({"id": module_id, "title": module_id, "paths": []})
    record_id = f"{contract_id}@{version}#{contract_scope}"
    rec["contracts"].append({
        "id": record_id, "record_id": record_id, "contract_id": contract_id, "module_id": module_id,
        "scope": contract_scope, "version": version, "status": "current",
        "source": {"kind": "migration", "migration_id": migration_id}, "source_document_id": document_id,
        "implementation_paths": [], "validation_scenarios": [], "supersedes": None, "superseded_by": None,
    })
    rec["documents"].append(doc)
    writes: dict[str, bytes | None] = {
        doc_path: render_document(doc, f"# Migrated specification: {contract_id}\n\nOriginal source: `{source_rel}`.\n\n" + body.rstrip() + "\n"),
        ".harness/records.yaml": yaml_text(rec).encode(),
    }
    writes.update(generate_indexes(rec, governance_root(cfg)))
    if not dry_run:
        atomic_batch_write(root, writes)
    return {"migration": migration, "document": doc, "contract_record_id": record_id, "dry_run": dry_run}


def exact_markdown_links(path: Path) -> set[str]:
    return {m.group(1) for m in LINK_RE.finditer(path.read_text(encoding="utf-8"))}


def _cycle_errors(edges: dict[str, str | None], label: str) -> list[str]:
    errors = []
    for start in edges:
        seen: set[str] = set()
        cur: str | None = start
        while cur and cur in edges:
            if cur in seen:
                errors.append(f"{label} cycle includes {cur}")
                break
            seen.add(cur)
            cur = edges[cur]
    return errors


def secret_fixture_allowlist(root: Path, cfg: dict[str, Any]) -> set[tuple[str, int, str]]:
    """G41 project extension: exempt exact public fixtures, never whole trees."""
    manifest_rel = (cfg.get("secret_scan") or {}).get("fixture_manifest")
    if not manifest_rel:
        return set()
    manifest = json.loads((root / safe_rel(root, manifest_rel)).read_text(encoding="utf-8"))
    if manifest.get("schema") != "g41mxe-secret-fixtures/v1" or not isinstance(manifest.get("fixtures"), list):
        raise HarnessError("invalid secret fixture manifest", code="fixture_identity")
    allowed: set[tuple[str, int, str]] = set()
    for row in manifest["fixtures"]:
        rel = safe_rel(root, row["path"])
        lines = row.get("lines")
        if (rel != row["path"] or row.get("rule") != "credential-assignment" or
                not isinstance(row.get("reason"), str) or not row["reason"].strip() or
                not isinstance(lines, list) or not lines or
                any(type(n) is not int or n < 1 for n in lines) or
                not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", "")))):
            raise HarnessError(f"invalid fixture entry: {rel}", code="fixture_identity")
        path = root / rel
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            raise HarnessError(f"public fixture identity changed: {rel}", code="fixture_identity")
        for n in lines:
            key = (rel, n, row["rule"])
            if key in allowed:
                raise HarnessError(f"duplicate fixture entry: {rel}:{n}", code="fixture_identity")
            allowed.add(key)
    return allowed


def project_scan_files(root: Path) -> Iterator[Path]:
    """Do not rescan disposable build copies or dependency/Git caches."""
    excluded = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in excluded and
                   not (Path(directory) == root and d == "build")]
        for name in files:
            path = Path(directory) / name
            if path.is_file():
                yield path


def check_project(root: Path, *, audit: bool = False) -> dict[str, Any]:
    missing = [p.relative_to(root).as_posix() for p in (config_path(root), records_path(root)) if not p.exists()]
    if missing and audit:
        return {"valid": False, "audit": True, "errors": [{"rule": "not_initialized", "message": f"missing governance authority: {path}"} for path in missing], "warnings": [], "summary": {"errors": len(missing), "warnings": 0}}
    cfg, rec = load_project(root)
    gov = governance_root(cfg)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    def err(rule: str, message: str) -> None:
        errors.append({"rule": rule, "message": message})
    for key in CORE_INVARIANTS:
        if key not in set(cfg.get("core_invariants", [])):
            err("core_invariants", f"core invariant cannot be disabled: {key}")
    for collection in ("modules", "contracts", "proposals", "documents", "evidence", "migrations"):
        ids = [str(x.get("id", "")) for x in rec[collection]]
        if "" in ids:
            err("identity", f"{collection} contains an empty id")
        for duplicate in sorted({x for x in ids if ids.count(x) > 1}):
            err("identity", f"duplicate {collection} id: {duplicate}")
    proposals, documents = record_map(rec, "proposals"), record_map(rec, "documents")
    evidence_by_id = record_map(rec, "evidence")
    migrations_by_id = record_map(rec, "migrations")
    for p in rec["proposals"]:
        if p.get("status") not in PROPOSAL_STATES:
            err("proposal_state", f"proposal {p.get('id')} has invalid status {p.get('status')}")
        if not p.get("required_scenarios"):
            err("acceptance_required", f"proposal {p.get('id')} has no required scenarios")
        if not p.get("docs_only") and not p.get("implementation_paths"):
            err("content_identity", f"proposal {p.get('id')} has no implementation paths")
        if p.get("status") == "merged" and (not p.get("merged_into") or p.get("merged_into") == p.get("id")):
            err("merge", f"merged proposal {p.get('id')} needs a distinct target")
        for did in p.get("document_ids", []):
            if did not in documents:
                err("registration", f"proposal {p.get('id')} references missing document {did}")
    errors.extend({"rule": "merge_cycle", "message": x} for x in _cycle_errors({p["id"]: p.get("merged_into") for p in rec["proposals"]}, "proposal merge"))
    current_seen: dict[tuple[str, str], str] = {}
    lineage = {}
    contract_records = {c.get("record_id", c.get("id")): c for c in rec["contracts"]}
    for c in rec["contracts"]:
        if not c.get("version") or not c.get("scope") or not c.get("contract_id"):
            err("contract_schema", f"contract {c.get('id')} lacks contract/version/scope identity")
        if c.get("status") == "current":
            key = contract_key(c)
            if key in current_seen:
                err("current_uniqueness", f"multiple current definitions for {key}: {current_seen[key]}, {c.get('id')}")
            current_seen[key] = c.get("id")
        source = c.get("source") or {}
        if source.get("kind") not in {"proposal", "migration"}:
            err("source_required", f"contract {c.get('id')} lacks proposal or authorized migration source")
        if source.get("kind") == "proposal" and source.get("proposal_id") not in proposals:
            err("source_required", f"contract {c.get('id')} points to missing proposal")
        if source.get("kind") == "proposal" and source.get("proposal_id") in proposals and c.get("status") == "current":
            origin = proposals[source["proposal_id"]]
            if origin.get("status") != "completed":
                err("source_required", f"current contract {c.get('id')} source proposal is not completed")
        if source.get("kind") == "migration":
            matching = [m for m in rec["migrations"] if m.get("authorization") and c.get("source_document_id") in m.get("documents", [])]
            if not matching:
                err("source_required", f"contract {c.get('id')} migration source lacks a registered authorization record")
        lineage[c.get("record_id", c.get("id"))] = c.get("supersedes")
        for relation in ("supersedes", "superseded_by"):
            target_id = c.get(relation)
            if not target_id:
                continue
            target = contract_records.get(target_id)
            if not target:
                err("lineage_acyclic", f"contract {c.get('record_id', c.get('id'))} has dangling {relation}: {target_id}")
                continue
            if contract_key(target) != contract_key(c):
                err("lineage_acyclic", f"contract {relation} crosses stable id or scope: {c.get('record_id')} -> {target_id}")
            reciprocal = "superseded_by" if relation == "supersedes" else "supersedes"
            if target.get(reciprocal) != c.get("record_id", c.get("id")):
                err("lineage_acyclic", f"contract lineage is not reciprocal: {c.get('record_id')} {relation} {target_id}")
    errors.extend({"rule": "lineage_acyclic", "message": x} for x in _cycle_errors(lineage, "contract supersedes"))
    expected_indexes = generate_indexes(rec, gov)
    for rel, expected in expected_indexes.items():
        p = root / rel
        if not p.exists() or p.read_bytes() != expected:
            err("index_drift", f"generated index differs from authority: {rel}")
    registered_paths = {d["path"] for d in rec["documents"]}
    for area in ("PROPOSALS", "SPEC", "RELEASE"):
        lifecycle_root = root / gov / area
        if lifecycle_root.is_dir():
            for path in lifecycle_root.rglob("*.md"):
                if path.name == "README.md":
                    continue
                rel = path.relative_to(root).as_posix()
                if rel not in registered_paths:
                    err("registration", f"lifecycle document is not registered: {rel}")
    for doc in rec["documents"]:
        if doc.get("status") not in DOCUMENT_STATES or doc.get("role") not in ROLES:
            err("document_schema", f"document {doc.get('id')} has invalid role/status")
            continue
        path = root / doc["path"]
        if not path.is_file():
            err("document_missing", f"document path missing: {doc['path']}")
            continue
        if doc["role"] != "LEGACY":
            try:
                meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
            except HarnessError as exc:
                err("frontmatter", f"{doc['path']}: {exc}")
                continue
            mirror = {"id": doc["id"], "role": doc["role"], "status": doc["status"], "proposal": doc.get("proposal_id"), "source-kind": doc["source"]["kind"], "merged-into": doc.get("merged_into")}
            for key, expected in mirror.items():
                if meta.get(key) != expected:
                    err("authority_consistency", f"{doc['path']} mirrors {key}={meta.get(key)!r}, authority requires {expected!r}")
            if not body.strip() or PLACEHOLDERS.search(body):
                err("document_content", f"document is empty or contains unfinished placeholders: {doc['path']}")
        if doc.get("proposal_id") and doc["proposal_id"] not in proposals:
            err("registration", f"document {doc['id']} points to unregistered proposal {doc['proposal_id']}")
        if doc["status"] == "current" and doc["source"].get("kind") not in {"proposal", "migration"}:
            err("source_required", f"current document {doc['id']} lacks a valid source")
        if doc["status"] == "current" and doc["source"].get("kind") == "migration":
            matching = [m for m in rec["migrations"] if m.get("authorization") and doc["id"] in m.get("documents", [])]
            if not matching:
                err("source_required", f"current document {doc['id']} lacks registered migration authorization")
    for p in rec["proposals"]:
        pdocs = [d for d in rec["documents"] if d.get("proposal_id") == p["id"]]
        if p.get("layout") == "compact":
            expected = "proposed" if p["status"] in {"draft", "active"} else "history"
            if len(pdocs) != 1 or pdocs[0].get("role") != "COMPACT" or pdocs[0].get("status") != expected:
                err("proposal_layout", f"compact proposal {p['id']} requires one {expected} COMPACT document")
            continue
        dev_docs = [d for d in pdocs if d["role"] == "DEV"]
        spec_docs = [d for d in pdocs if d["role"] == "SPEC"]
        release_docs = [d for d in pdocs if d["role"] == "RELEASE"]
        changed = {c["contract_id"] for c in p.get("changes", [])}
        spec_coverage = [c for d in spec_docs for c in d.get("contract_ids", [])]
        release_coverage = [c for d in release_docs for c in d.get("contract_ids", [])]
        if len(dev_docs) != 1 or sorted(spec_coverage) != sorted(changed) or sorted(release_coverage) != sorted(changed) or len(spec_coverage) != len(set(spec_coverage)) or len(release_coverage) != len(set(release_coverage)):
            err("proposal_layout", f"proposal {p['id']} requires one DEV and unambiguous SPEC/RELEASE coverage per contract")
            continue
        if p["status"] == "completed":
            has_current_contract = any(c.get("status") == "current" and (c.get("source") or {}).get("proposal_id") == p["id"] for c in rec["contracts"])
            if dev_docs[0]["status"] != "history":
                err("proposal_state", f"completed proposal {p['id']} has inconsistent document states")
            for doc in spec_docs + release_docs:
                contract_current = any(c.get("status") == "current" and (c.get("source") or {}).get("proposal_id") == p["id"] and c.get("contract_id") in doc.get("contract_ids", []) for c in rec["contracts"])
                expected = "current" if contract_current else "history"
                if doc["status"] != expected:
                    err("proposal_state", f"completed proposal {p['id']} document {doc['id']} should be {expected}")
            evidence_ids = p.get("acceptance_evidence_ids") or []
            chosen = [evidence_by_id.get(eid) for eid in evidence_ids]
            chosen = [e for e in chosen if e]
            for scenario in p.get("required_scenarios", []):
                matches = [e for e in chosen if e.get("proposal_id") == p["id"] and e.get("scenario") == scenario]
                if len(matches) != 1:
                    err("acceptance_required", f"completed proposal {p['id']} lacks exactly one selected evidence for {scenario}")
                    continue
                ev = matches[0]
                ack = ev.get("user_acknowledgement") or {}
                identity = ev.get("artifact_identity") or {}
                if ev.get("result") != "pass" or ack.get("status") != "confirmed" or not ack.get("basis"):
                    err("acceptance_required", f"completed proposal {p['id']} selected evidence is not pass plus explicit acknowledgement: {scenario}")
                if identity.get("kind") != "proposal-acceptance-v1" or not identity.get("sha256"):
                    err("content_identity", f"completed proposal {p['id']} selected evidence lacks a complete acceptance identity: {scenario}")
            if has_current_contract:
                for ev in chosen:
                    if not verify_proposal_acceptance_identity(root, rec, p, ev.get("artifact_identity") or {}):
                        err("content_identity", f"current definition from proposal {p['id']} no longer matches accepted content identity")
        elif p["status"] == "merged":
            if any(d["status"] != "history" or d.get("merged_into") != p["merged_into"] for d in pdocs):
                err("proposal_state", f"merged proposal {p['id']} documents must be history with merged_into")
        elif p["status"] in {"draft", "active"} and any(d["status"] != "proposed" for d in pdocs):
            err("proposal_state", f"active proposal {p['id']} documents must be proposed")
    for contract in current_contracts(rec):
        source_doc = documents.get(contract.get("source_document_id"))
        if not source_doc or source_doc.get("status") != "current" or source_doc.get("role") != "SPEC" or contract["contract_id"] not in source_doc.get("contract_ids", []):
            err("current_uniqueness", f"current contract {contract['record_id']} must reference one current SPEC carrying its stable contract id")
    # Exact link targets, not filename substrings.
    for rel in expected_indexes:
        p = root / rel
        if not p.exists():
            continue
        for target in exact_markdown_links(p):
            if not (p.parent / target).resolve().is_file():
                err("link_integrity", f"broken index link in {rel}: {target}")
    # Accepted versions must use exact nonempty immutable identities when a registry exists.
    versions = root / "versions.yaml"
    if versions.exists():
        data = load_yaml(versions)
        for row in data.get("versions", []):
            if row.get("status") in {"active", "accepted"} and not str(row.get("immutable_identity", "")).strip():
                err("version_identity", f"accepted version {row.get('id')} has empty immutable identity")
            source = row.get("source_file")
            expected = row.get("source_value")
            if source and expected is not None:
                actual = (root / safe_rel(root, source)).read_text(encoding="utf-8").strip()
                if actual != str(expected):
                    err("version_anchor", f"version anchor mismatch for {row.get('id')}: exact value differs")
    # Secret findings intentionally report only rule and location, never the matched value.
    secret_rules = {
        "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "github-token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
        "credential-assignment": re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"\s$<{]{8,}['\"]"),
    }
    allowed_fixtures = secret_fixture_allowlist(root, cfg)
    for path in project_scan_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".harness/index/") or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(lines, 1):
            for rule, pattern in secret_rules.items():
                if pattern.search(line) and (rel, line_no, rule) not in allowed_fixtures:
                    err("secret_scan", f"{rule} shape at {rel}:{line_no}")
    lock_policy = cfg.get("lock_policy") or {}
    if lock_policy.get("enabled", True):
        exemptions = lock_policy.get("exemptions") or []
        manifests = {
            "package.json": ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb"),
            "Cargo.toml": ("Cargo.lock",),
            "go.mod": ("go.sum",),
            "pyproject.toml": ("uv.lock", "poetry.lock", "Pipfile.lock"),
        }
        for path in project_scan_files(root):
            if path.name not in manifests:
                continue
            rel = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, pattern) for pattern in exemptions):
                continue
            if not any((path.parent / name).exists() for name in manifests[path.name]):
                err("lockfiles", f"manifest lacks a configured lockfile or exemption: {rel}")
    result = {"valid": not errors, "audit": audit, "errors": errors, "warnings": warnings, "summary": {"errors": len(errors), "warnings": len(warnings)}}
    if errors and not audit:
        raise HarnessError("harness validation failed", code="check_failed", details=result)
    return result


def regenerate_indexes(root: Path, *, check_only: bool = False) -> dict[str, Any]:
    cfg, rec = load_project(root)
    expected = generate_indexes(rec, governance_root(cfg))
    changed = [rel for rel, value in expected.items() if not (root / rel).exists() or (root / rel).read_bytes() != value]
    if check_only and changed:
        raise HarnessError("generated indexes are stale", code="stale_index", exit_code=5, details={"changed": changed})
    if not check_only and changed:
        with bounded_lock(root / ".harness" / "write.lock"):
            atomic_batch_write(root, expected)
    return {"fresh": not changed, "changed": changed, "check_only": check_only}


def git_state(root: Path) -> dict[str, str | None]:
    def run(*args: str) -> str | None:
        p = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
        return p.stdout.strip() if p.returncode == 0 else None
    return {"head": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current"), "git_common_dir": run("rev-parse", "--git-common-dir")}


def workspace_identity(root: Path, cfg: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    state = git_state(root)
    branch_identity = state["branch"] or (f"detached-{state['head']}" if state["head"] else "no-git")
    payload = {"project_id": cfg["project_id"], "root": str(root.resolve()), "git_common_dir": state["git_common_dir"], "branch_identity": branch_identity}
    return sha256_bytes(json.dumps(payload, sort_keys=True).encode())[:20], {**payload, **state}


def model_manifest_path() -> Path:
    return Path(__file__).with_name("model-manifest.json")


def model_manifest() -> dict[str, Any]:
    return json.loads(model_manifest_path().read_text(encoding="utf-8"))


def embedding_fingerprint() -> str:
    payload = {"index_schema": INDEX_SCHEMA, "model": model_manifest(), "chunking": {"algorithm": "markdown-headings-char-bound-v2", "max_chars": 360}}
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())


def model_cache_dir() -> Path:
    manifest = model_manifest()
    base = Path(os.environ.get("HARNESS_MODEL_CACHE", Path.home() / ".cache" / "harness-project-governance" / "models"))
    return base / manifest["model_id"].replace("/", "--") / manifest["revision"]


def model_status() -> dict[str, Any]:
    manifest, base = model_manifest(), model_cache_dir()
    files = []
    ready = True
    for item in manifest["files"]:
        p = base / item["path"]
        valid = p.is_file() and p.stat().st_size == item["size"] and sha256_file(p) == item["sha256"]
        ready &= valid
        files.append({"path": str(p), "valid": valid, "expected_size": item["size"]})
    return {"ready": ready, "model_id": manifest["model_id"], "revision": manifest["revision"], "files": files, "total_bytes": sum(x["size"] for x in manifest["files"])}


def prepare_model() -> dict[str, Any]:
    manifest, base = model_manifest(), model_cache_dir()
    base.mkdir(parents=True, exist_ok=True)
    with bounded_lock(base / ".prepare.lock", timeout=120.0):
        for item in manifest["files"]:
            target = base / item["path"]
            if target.is_file() and target.stat().st_size == item["size"] and sha256_file(target) == item["sha256"]:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + f".{os.getpid()}.part")
            url = f"https://huggingface.co/{manifest['model_id']}/resolve/{manifest['revision']}/{item['path']}"
            with urllib.request.urlopen(url, timeout=60) as response, tmp.open("wb") as out:
                shutil.copyfileobj(response, out, length=1024 * 1024)
            if tmp.stat().st_size != item["size"] or sha256_file(tmp) != item["sha256"]:
                tmp.unlink(missing_ok=True)
                raise HarnessError(f"downloaded model file failed size/hash verification: {item['path']}", code="model_invalid", exit_code=4)
            os.replace(tmp, target)
    return model_status()


class Embedder:
    def __init__(self) -> None:
        status = model_status()
        if not status["ready"]:
            raise HarnessError("embedding model is missing or invalid; run `model prepare`", code="model_unavailable", exit_code=4, details=status)
        try:
            import numpy as np
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise HarnessError(f"embedding dependency unavailable: {exc}; install scripts/requirements.lock", code="dependency_unavailable", exit_code=4)
        self.np, self.manifest = np, model_manifest()
        base = model_cache_dir()
        self.tokenizer = Tokenizer.from_file(str(base / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=self.manifest["max_tokens"])
        self.tokenizer.enable_padding()
        self.session = ort.InferenceSession(str(base / "onnx" / "model_quantized.onnx"), providers=["CPUExecutionProvider"])

    def encode(self, texts: list[str], *, query: bool) -> Any:
        if not texts:
            return self.np.empty((0, self.manifest["dimension"]), dtype=self.np.float32)
        prefix = self.manifest["query_prefix"] if query else self.manifest["passage_prefix"]
        enc = self.tokenizer.encode_batch([prefix + t for t in texts])
        ids = self.np.asarray([x.ids for x in enc], dtype=self.np.int64)
        masks = self.np.asarray([x.attention_mask for x in enc], dtype=self.np.int64)
        types = self.np.asarray([x.type_ids for x in enc], dtype=self.np.int64)
        hidden = self.session.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": masks, "token_type_ids": types})[0]
        weighted = hidden * masks[..., None]
        pooled = weighted.sum(axis=1) / self.np.clip(masks.sum(axis=1, keepdims=True), 1, None)
        pooled /= self.np.clip(self.np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
        return pooled.astype(self.np.float32)


def index_paths(root: Path, cfg: dict[str, Any]) -> tuple[Path, str, dict[str, Any]]:
    wid, state = workspace_identity(root, cfg)
    base = root / ".harness" / "index" / wid
    return base / "vectors.sqlite3", wid, state


def chunk_document(root: Path, doc: dict[str, Any], max_chars: int = 360) -> list[dict[str, Any]]:
    text = (root / doc["path"]).read_text(encoding="utf-8")
    line_offset = 0
    if doc["role"] != "LEGACY":
        raw_lines = text.splitlines()
        if raw_lines and raw_lines[0].strip() == "---":
            end = next((i for i in range(1, len(raw_lines)) if raw_lines[i].strip() == "---"), None)
            if end is None:
                raise HarnessError(f"unterminated frontmatter: {doc['path']}")
            body_lines = raw_lines[end + 1 :]
            line_offset = end + 1
            while body_lines and not body_lines[0].strip():
                body_lines.pop(0)
                line_offset += 1
            lines = body_lines
        else:
            lines = raw_lines
    else:
        lines = text.splitlines()
    chunks, heading, start, buffer = [], "", 1, []
    def flush(end: int) -> None:
        nonlocal buffer, start
        value = "\n".join(buffer).strip()
        if value:
            chunks.append({"heading": heading, "line_start": start, "line_end": end, "text": value})
        buffer = []
    for i, line in enumerate(lines, 1):
        segments = [line[j : j + max_chars] for j in range(0, len(line), max_chars)] or [""]
        for segment_index, segment in enumerate(segments):
            if segment_index == 0 and line.startswith("#") and (not buffer or sum(len(x) + 1 for x in buffer) > 120):
                flush(i - 1)
                heading = line.lstrip("# ").strip()
                start = i
            if not buffer:
                start = i
            if buffer and sum(len(x) + 1 for x in buffer) + len(segment) + 1 > max_chars:
                flush(i if segment_index else i - 1)
                start = i
            buffer.append(segment)
            if sum(len(x) + 1 for x in buffer) >= max_chars:
                flush(i)
                start = i
    flush(len(lines))
    for n, chunk in enumerate(chunks):
        chunk.update({
            "id": f"{doc['id']}:{n}", "document_id": doc["id"], "path": doc["path"], "role": doc["role"],
            "status": doc["status"], "proposal_id": doc.get("proposal_id"), "contract_ids": doc.get("contract_ids", []),
            "source_kind": doc["source"]["kind"], "content_hash": sha256_bytes(chunk["text"].encode()),
        })
        chunk["line_start"] += line_offset
        chunk["line_end"] += line_offset
    return chunks


def catalog_snapshot(root: Path, rec: dict[str, Any]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    docs, chunks = [], []
    for doc in sorted(rec["documents"], key=lambda x: x["id"]):
        path = root / doc["path"]
        if not path.is_file():
            continue
        item = {"id": doc["id"], "path": doc["path"], "status": doc["status"], "role": doc["role"], "sha256": sha256_file(path)}
        docs.append(item)
        chunks.extend(chunk_document(root, doc))
    authority = {
        "documents": [{k: d.get(k) for k in ("id", "path", "role", "status", "proposal_id", "module_ids", "contract_ids", "source", "merged_into")} for d in rec["documents"]],
        "contracts": [{k: c.get(k) for k in ("id", "contract_id", "module_id", "scope", "version", "status", "source", "source_document_id", "supersedes", "superseded_by")} for c in rec["contracts"]],
        "proposals": [{k: p.get(k) for k in ("id", "status", "changes", "required_scenarios", "merged_into", "document_ids")} for p in rec["proposals"]],
    }
    payload = {"documents": docs, "authority": authority, "embedding_fingerprint": embedding_fingerprint(), "schema": INDEX_SCHEMA}
    return sha256_bytes(json.dumps(payload, sort_keys=True).encode()), docs, chunks


def connect_index(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, path TEXT NOT NULL, status TEXT NOT NULL, role TEXT NOT NULL, sha256 TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS chunks (
        id TEXT PRIMARY KEY, document_id TEXT NOT NULL, path TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL,
        proposal_id TEXT, contract_ids TEXT NOT NULL, source_kind TEXT NOT NULL, heading TEXT NOT NULL,
        line_start INTEGER NOT NULL, line_end INTEGER NOT NULL, text TEXT NOT NULL, content_hash TEXT NOT NULL,
        embedding BLOB, dimension INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status);
      CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
    """)
    return conn


def sync_index(root: Path, *, rebuild: bool = False, lexical_only: bool = False) -> dict[str, Any]:
    cfg, rec = load_project(root)
    db, wid, state = index_paths(root, cfg)
    db.parent.mkdir(parents=True, exist_ok=True)
    with bounded_lock(db.parent / "sync.lock", timeout=30.0):
        digest, docs, chunks = catalog_snapshot(root, rec)
        existing_vectors: dict[str, bytes] = {}
        expected_model = f"{model_manifest()['model_id']}@{model_manifest()['revision']}"
        expected_fingerprint = embedding_fingerprint()
        if not rebuild and not lexical_only and db.exists():
            old = connect_index(db)
            try:
                old_meta = {k: json.loads(v) for k, v in old.execute("SELECT key,value FROM meta")}
                if old_meta.get("mode") == "semantic" and old_meta.get("embedding_fingerprint") == expected_fingerprint:
                    existing_vectors = {h: blob for h, blob in old.execute("SELECT content_hash,embedding FROM chunks WHERE embedding IS NOT NULL")}
            finally:
                old.close()
        vectors: list[Any] = [None] * len(chunks)
        missing_indexes: list[int] = []
        if not lexical_only:
            import numpy as np
            for idx, chunk in enumerate(chunks):
                blob = existing_vectors.get(chunk["content_hash"])
                if blob:
                    vectors[idx] = np.frombuffer(blob, dtype=np.float32).copy()
                else:
                    missing_indexes.append(idx)
            if missing_indexes:
                embedder = Embedder()
                encoded = embedder.encode([chunks[i]["text"] for i in missing_indexes], query=False)
                for idx, vector in zip(missing_indexes, encoded):
                    vectors[idx] = vector
        # Prevent a concurrent document mutation from being committed as fresh.
        _, rec_after = load_project(root)
        digest_after, _, _ = catalog_snapshot(root, rec_after)
        if digest_after != digest:
            raise HarnessError("documents changed during index build; retry sync", code="catalog_changed", exit_code=5)
        if rebuild and db.exists():
            db.unlink()
        conn = connect_index(db)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM documents")
            conn.execute("DELETE FROM chunks")
            conn.executemany("INSERT INTO documents(id,path,status,role,sha256) VALUES(:id,:path,:status,:role,:sha256)", docs)
            for chunk, vector in zip(chunks, vectors):
                conn.execute("""INSERT INTO chunks(id,document_id,path,role,status,proposal_id,contract_ids,source_kind,heading,line_start,line_end,text,content_hash,embedding,dimension)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    chunk["id"], chunk["document_id"], chunk["path"], chunk["role"], chunk["status"], chunk["proposal_id"],
                    json.dumps(chunk["contract_ids"]), chunk["source_kind"], chunk["heading"], chunk["line_start"], chunk["line_end"],
                    chunk["text"], chunk["content_hash"], None if vector is None else vector.tobytes(), 0 if vector is None else int(vector.shape[0]),
                ))
            meta = {
                "index_schema": INDEX_SCHEMA, "catalog_hash": digest, "model_identity": expected_model,
                "embedding_fingerprint": expected_fingerprint,
                "workspace_id": wid, "workspace_state": state, "mode": "lexical" if lexical_only else "semantic", "updated_at": utc_now(),
            }
            conn.executemany("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", [(k, json.dumps(v, sort_keys=True)) for k, v in meta.items()])
            conn.commit()
        finally:
            conn.close()
    return {"workspace_id": wid, "database": str(db), "catalog_hash": digest, "documents": len(docs), "chunks": len(chunks), "embedded_chunks": 0 if lexical_only else len(missing_indexes), "reused_chunks": 0 if lexical_only else len(chunks) - len(missing_indexes), "mode": "lexical" if lexical_only else "semantic"}


def index_status(root: Path) -> dict[str, Any]:
    cfg, rec = load_project(root)
    db, wid, state = index_paths(root, cfg)
    digest, docs, chunks = catalog_snapshot(root, rec)
    result = {"initialized": db.is_file(), "fresh": False, "workspace_id": wid, "database": str(db), "current_catalog_hash": digest, "documents": len(docs), "chunks": len(chunks), "workspace_state": state}
    if not db.is_file():
        return result
    conn = connect_index(db)
    try:
        meta = {k: json.loads(v) for k, v in conn.execute("SELECT key,value FROM meta")}
    finally:
        conn.close()
    result["meta"] = meta
    result["fresh"] = meta.get("catalog_hash") == digest and meta.get("index_schema") == INDEX_SCHEMA and meta.get("embedding_fingerprint") == embedding_fingerprint() and meta.get("workspace_id") == wid
    return result


def lexical_score(query: str, text: str) -> float:
    q = {x.lower() for x in TOKEN_RE.findall(query) if x.lower() not in STOPWORDS}
    t = {x.lower() for x in TOKEN_RE.findall(text) if x.lower() not in STOPWORDS}
    if not q:
        return 0.0
    return len(q & t) / len(q) + (0.5 if query.lower() in text.lower() else 0.0)


def search_index(root: Path, query: str, scopes: list[str], limit: int, lexical_fallback: bool = False, exact_id: str | None = None) -> dict[str, Any]:
    status = index_status(root)
    allowed = set(scopes)
    invalid = allowed - DOCUMENT_STATES
    if invalid:
        raise HarnessError(f"invalid search scopes: {sorted(invalid)}")
    mode, warning = "semantic", None
    rows: list[sqlite3.Row] = []
    if status["initialized"] and status["fresh"]:
        conn = connect_index(Path(status["database"]))
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in allowed)
        rows = conn.execute(f"SELECT * FROM chunks WHERE status IN ({placeholders})", tuple(sorted(allowed))).fetchall()
        meta = {k: json.loads(v) for k, v in conn.execute("SELECT key,value FROM meta")}
        mode = meta.get("mode", "semantic")
    elif lexical_fallback:
        _, rec = load_project(root)
        chunks = [c for d in rec["documents"] if d["status"] in allowed for c in chunk_document(root, d)]
        rows = chunks  # type: ignore[assignment]
        conn = None
        mode, warning = "lexical-fallback", "vector index is missing or stale"
    else:
        code = "index_stale" if status["initialized"] else "index_uninitialized"
        raise HarnessError("vector index is missing or stale; run `index sync` or request --lexical-fallback", code=code, exit_code=5, details=status)
    try:
        semantic = mode == "semantic"
        qvec = Embedder().encode([query], query=True)[0] if semantic else None
        import numpy as np
        scored = []
        for row in rows:
            item = dict(row)
            contracts = item["contract_ids"] if isinstance(item["contract_ids"], list) else json.loads(item["contract_ids"])
            exact = exact_id and (exact_id == item["document_id"] or exact_id in contracts or exact_id == item.get("proposal_id"))
            lex = lexical_score(query, item["text"] + " " + item["document_id"] + " " + " ".join(contracts))
            sem = 0.0
            if semantic and item.get("embedding"):
                vec = np.frombuffer(item["embedding"], dtype=np.float32)
                sem = float(np.dot(qvec, vec))
            role_boost = 0.04 if item["role"] == "SPEC" else 0.0
            score = (1.0 if exact else 0.0) + (0.78 * sem if semantic else 0.0) + 0.22 * lex + role_boost
            if exact or score > 0:
                scored.append((score, sem, lex, item, contracts))
        scored.sort(key=lambda x: (-x[0], x[3]["document_id"], x[3]["line_start"]))
        results = [{
            "score": round(score, 6), "semantic_score": round(sem, 6) if semantic else None, "lexical_score": round(lex, 6),
            "document_id": item["document_id"], "path": item["path"], "line_start": item["line_start"], "line_end": item["line_end"],
            "heading": item["heading"], "role": item["role"], "status": item["status"], "proposal_id": item.get("proposal_id"),
            "contract_ids": contracts, "source_kind": item["source_kind"], "content_hash": item["content_hash"], "text": item["text"],
        } for score, sem, lex, item, contracts in scored[:limit]]
    finally:
        if status["initialized"] and status["fresh"] and conn is not None:
            conn.close()
    current_gap = "current" in allowed and not any(x["status"] == "current" for x in results)
    return {"query": query, "mode": mode, "warning": warning, "scopes": sorted(allowed), "index_fresh": bool(status["fresh"]), "current_definition_gap": current_gap, "results": results}


def read_documents(root: Path, document_id: str | None, contract_id: str | None, scope: str = "current", contract_scope: str | None = None) -> dict[str, Any]:
    _, rec = load_project(root)
    docs = rec["documents"]
    if document_id:
        docs = [d for d in docs if d["id"] == document_id and d.get("status") == scope]
    elif contract_id:
        contracts = [c for c in rec["contracts"] if c["contract_id"] == contract_id and c.get("status") == scope and (contract_scope is None or c.get("scope") == contract_scope)]
        ids = {c["source_document_id"] for c in contracts}
        docs = [d for d in docs if d["id"] in ids and d.get("status") == scope]
    else:
        raise HarnessError("read requires --document-id or --contract-id")
    if not docs:
        raise HarnessError("no matching document", code="not_found", exit_code=4)
    contract_matches = [c for c in rec["contracts"] if c.get("source_document_id") in {d["id"] for d in docs} and c.get("status") == scope]
    return {"scope": scope, "contract_scope": contract_scope, "contracts": contract_matches, "documents": [{**d, "content": (root / d["path"]).read_text(encoding="utf-8")} for d in docs]}


def catalog_documents(root: Path, scopes: list[str]) -> dict[str, Any]:
    _, rec = load_project(root)
    allowed = set(scopes)
    return {
        "scopes": sorted(allowed),
        "documents": [d for d in sorted(rec["documents"], key=lambda x: x["id"]) if d.get("status") in allowed],
        "contracts": [c for c in sorted(rec["contracts"], key=lambda x: x["id"]) if c.get("status") in allowed],
    }
