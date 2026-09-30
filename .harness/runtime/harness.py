#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import yaml

from harnesslib import (
    HarnessError,
    add_evidence,
    adopt_migration,
    archive_proposal,
    check_project,
    catalog_documents,
    content_identity,
    create_project,
    create_proposal,
    index_status,
    merge_proposal,
    model_status,
    mutation_guard,
    parse_change,
    prepare_model,
    promote_proposal,
    read_documents,
    regenerate_indexes,
    register_legacy,
    resolve_root,
    runtime_upgrade,
    search_index,
    sync_index,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description="Project-definition governance and retrieval CLI")
    p.add_argument("--root", help="project root; defaults to Git root or cwd")
    p.add_argument("--human", action="store_true", help="render YAML for humans instead of the stable JSON envelope")
    p.add_argument("--debug", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    x = sub.add_parser("init", help="initialize governance without adopting existing material")
    x.add_argument("--project-id", required=True)
    x.add_argument("--dry-run", action="store_true")

    x = sub.add_parser("check", help="validate authority, lifecycle, links, identity, and evidence")
    x.add_argument("--audit", action="store_true", help="report violations with exit 0 and make no changes")

    proposal = sub.add_parser("proposal", help="manage proposal lifecycle").add_subparsers(dest="proposal_command", required=True)
    x = proposal.add_parser("create")
    x.add_argument("--id", required=True)
    x.add_argument("--title", required=True)
    x.add_argument("--change", action="append", required=True, help="ACTION:CONTRACT:MODULE:SCOPE:VERSION")
    x.add_argument("--required-scenario", action="append", required=True)
    x.add_argument("--implementation-path", action="append", default=[])
    x.add_argument("--docs-only", action="store_true")
    x.add_argument("--layout", choices=("split", "compact"), default="split")
    x.add_argument("--dry-run", action="store_true")
    x = proposal.add_parser("merge")
    x.add_argument("--source", required=True)
    x.add_argument("--target", required=True)
    x.add_argument("--scope", required=True)
    x.add_argument("--dry-run", action="store_true")
    x = proposal.add_parser("archive")
    x.add_argument("--id", required=True)
    x.add_argument("--dry-run", action="store_true")
    x = proposal.add_parser("promote")
    x.add_argument("--id", required=True)
    x.add_argument("--dry-run", action="store_true")

    evidence = sub.add_parser("evidence", help="append E2E evidence; never infer acknowledgement").add_subparsers(dest="evidence_command", required=True)
    x = evidence.add_parser("add")
    x.add_argument("--proposal", required=True)
    x.add_argument("--scenario", required=True)
    x.add_argument("--result", choices=("pass", "fail"), required=True)
    x.add_argument("--environment", required=True)
    x.add_argument("--command", dest="evidence_command_text", required=True)
    x.add_argument("--user-acknowledged", action="store_true", help="use only after explicit user recognition")
    x.add_argument("--user-ack-basis", help="traceable basis for the explicit recognition")
    x.add_argument("--dry-run", action="store_true")

    legacy = sub.add_parser("legacy", help="register legacy material without making it formal").add_subparsers(dest="legacy_command", required=True)
    x = legacy.add_parser("add")
    x.add_argument("--path", required=True)
    x.add_argument("--document-id", required=True)
    x.add_argument("--migration-scope")
    x.add_argument("--authorization")
    x.add_argument("--dry-run", action="store_true")

    migration = sub.add_parser("migration", help="explicitly adopt authorized legacy specification scope").add_subparsers(dest="migration_command", required=True)
    x = migration.add_parser("adopt")
    x.add_argument("--path", required=True)
    x.add_argument("--document-id", required=True)
    x.add_argument("--contract", required=True, help="CONTRACT:MODULE:SCOPE:VERSION")
    x.add_argument("--migration-scope", required=True)
    x.add_argument("--authorization", required=True)
    x.add_argument("--user-ack-basis", required=True)
    x.add_argument("--dry-run", action="store_true")

    index = sub.add_parser("index", help="manage generated views and the project-local vector index").add_subparsers(dest="index_command", required=True)
    x = index.add_parser("generate")
    x.add_argument("--check", action="store_true")
    index.add_parser("status")
    x = index.add_parser("sync")
    x.add_argument("--lexical-only", action="store_true", help="explicit degraded index; never reported as semantic")
    x = index.add_parser("rebuild")
    x.add_argument("--lexical-only", action="store_true")

    x = sub.add_parser("search", help="search indexed documents with lifecycle filters")
    x.add_argument("query")
    x.add_argument("--scope", action="append", choices=("current", "proposed", "legacy", "history"), default=[])
    x.add_argument("--limit", type=int, default=8)
    x.add_argument("--exact-id")
    x.add_argument("--lexical-fallback", action="store_true")

    x = sub.add_parser("read", help="read authoritative source documents by stable identity")
    g = x.add_mutually_exclusive_group(required=True)
    g.add_argument("--document-id")
    g.add_argument("--contract-id")
    x.add_argument("--scope", choices=("current", "proposed", "legacy", "history"), default="current")
    x.add_argument("--contract-scope", help="filter a stable contract id by its declared applicability scope")

    x = sub.add_parser("catalog", help="list registered identities without ranking")
    x.add_argument("--scope", action="append", choices=("current", "proposed", "legacy", "history"), default=[])

    model = sub.add_parser("model", help="prepare or inspect the pinned local embedding model").add_subparsers(dest="model_command", required=True)
    model.add_parser("prepare")
    model.add_parser("status")

    identity = sub.add_parser("identity", help="compute a deterministic implementation content identity").add_subparsers(dest="identity_command", required=True)
    x = identity.add_parser("compute")
    x.add_argument("--path", action="append", required=True)

    upgrade = sub.add_parser("upgrade", help="preview or apply managed runtime updates without touching extensions").add_subparsers(dest="upgrade_command", required=True)
    upgrade.add_parser("preview")
    upgrade.add_parser("apply")
    return p


def dispatch(args: argparse.Namespace) -> dict:
    root = resolve_root(args.root)
    if args.command == "init":
        return create_project(root, args.project_id, dry_run=args.dry_run)
    if args.command == "check":
        return check_project(root, audit=args.audit)
    if args.command == "proposal":
        if args.proposal_command == "create":
            return create_proposal(root, args.id, args.title, [parse_change(x) for x in args.change], args.required_scenario, args.implementation_path, args.docs_only, args.layout, dry_run=args.dry_run)
        if args.proposal_command == "merge":
            return merge_proposal(root, args.source, args.target, args.scope, dry_run=args.dry_run)
        if args.proposal_command == "archive":
            return archive_proposal(root, args.id, dry_run=args.dry_run)
        if args.proposal_command == "promote":
            return promote_proposal(root, args.id, dry_run=args.dry_run)
    if args.command == "evidence" and args.evidence_command == "add":
        return add_evidence(root, args.proposal, args.scenario, args.result, args.environment, args.evidence_command_text, args.user_acknowledged, args.user_ack_basis, dry_run=args.dry_run)
    if args.command == "legacy" and args.legacy_command == "add":
        return register_legacy(root, args.path, args.document_id, migration_scope=args.migration_scope, authorization=args.authorization, dry_run=args.dry_run)
    if args.command == "migration" and args.migration_command == "adopt":
        return adopt_migration(root, args.path, args.document_id, args.contract, args.migration_scope, args.authorization, args.user_ack_basis, dry_run=args.dry_run)
    if args.command == "index":
        if args.index_command == "generate":
            return regenerate_indexes(root, check_only=args.check)
        if args.index_command == "status":
            return index_status(root)
        if args.index_command in {"sync", "rebuild"}:
            return sync_index(root, rebuild=args.index_command == "rebuild", lexical_only=args.lexical_only)
    if args.command == "search":
        scopes = args.scope or ["current"]
        return search_index(root, args.query, scopes, args.limit, lexical_fallback=args.lexical_fallback, exact_id=args.exact_id)
    if args.command == "read":
        return read_documents(root, args.document_id, args.contract_id, args.scope, args.contract_scope)
    if args.command == "catalog":
        return catalog_documents(root, args.scope or ["current"])
    if args.command == "model":
        return prepare_model() if args.model_command == "prepare" else model_status()
    if args.command == "identity" and args.identity_command == "compute":
        return content_identity(root, args.path)
    if args.command == "upgrade":
        return runtime_upgrade(root, apply=args.upgrade_command == "apply")
    raise AssertionError("unhandled command")


def emit(payload: dict, *, human: bool) -> None:
    if human:
        print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).rstrip())
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def main() -> int:
    p = parser()
    args = p.parse_args()
    try:
        root = resolve_root(args.root)
        mutation = (
            args.command == "init"
            or args.command in {"proposal", "evidence", "legacy", "migration"}
            or (args.command == "upgrade" and args.upgrade_command == "apply")
            or (args.command == "index" and (args.index_command in {"sync", "rebuild"} or (args.index_command == "generate" and not args.check)))
        ) and not bool(getattr(args, "dry_run", False))
        if mutation:
            with mutation_guard(root):
                data = dispatch(args)
        else:
            data = dispatch(args)
        emit({"ok": True, "data": data, "error": None}, human=args.human)
        return 0
    except HarnessError as exc:
        emit({"ok": False, "data": exc.details, "error": {"code": exc.code, "message": str(exc)}}, human=args.human)
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        emit({"ok": False, "data": None, "error": {"code": "internal_error", "message": str(exc)}}, human=args.human)
        if args.debug:
            traceback.print_exc(file=sys.stderr)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
