"""Command line utilities for interacting with the CV bank."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

from .db import CVDatabase
from .text import extract_text_from_file
from .utils import format_candidate, parse_skills

DEFAULT_DB_PATH = Path("cv_bank.db")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a searchable database of CVs")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file (default: %(default)s)",
    )
    parser.add_argument(
        "--storage",
        type=Path,
        default=None,
        help="Directory where uploaded CV files will be stored (default: alongside the database)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialise the database schema")
    init_parser.set_defaults(func=handle_init)

    add_parser = subparsers.add_parser("add", help="Add a new CV entry")
    add_parser.add_argument("name", help="Full name of the candidate")
    add_parser.add_argument("--email")
    add_parser.add_argument("--phone")
    add_parser.add_argument("--job-title")
    add_parser.add_argument("--company")
    add_parser.add_argument("--location", help="Governorate / city / region")
    add_parser.add_argument("--notes", help="Additional notes", default=None)
    add_parser.add_argument(
        "--skill",
        action="append",
        dest="skill_flags",
        help="Skill to associate with the CV (can be specified multiple times)",
    )
    add_parser.add_argument(
        "--skills",
        help="Comma separated list of skills (an alternative to multiple --skill flags)",
    )
    add_parser.add_argument(
        "--file",
        type=Path,
        help="Path to the CV file to store",
    )
    add_parser.add_argument(
        "--text-source",
        type=Path,
        help=(
            "Optional path to a plain text version of the CV. If omitted the tool will try to extract text "
            "from --file when possible."
        ),
    )
    add_parser.set_defaults(func=handle_add)

    list_parser = subparsers.add_parser("list", help="Show stored CVs with optional filters")
    list_parser.add_argument("--skill")
    list_parser.add_argument("--location")
    list_parser.add_argument("--company")
    list_parser.add_argument("--job-title")
    list_parser.set_defaults(func=handle_list)

    search_parser = subparsers.add_parser("search", help="Search for CVs using keywords")
    search_parser.add_argument("keywords", nargs="+", help="Words to search for across the CV database")
    search_parser.set_defaults(func=handle_search)

    show_parser = subparsers.add_parser("show", help="Display a single CV entry")
    show_parser.add_argument("candidate_id", type=int)
    show_parser.set_defaults(func=handle_show)

    delete_parser = subparsers.add_parser("delete", help="Remove a CV entry")
    delete_parser.add_argument("candidate_id", type=int)
    delete_parser.set_defaults(func=handle_delete)

    return parser


def build_db(args: argparse.Namespace) -> CVDatabase:
    storage = args.storage if args.storage is not None else None
    return CVDatabase(args.db, storage)


def handle_init(args: argparse.Namespace) -> None:
    db = build_db(args)
    db.initialize()
    print(f"Database initialised at {db.db_path}")
    print(f"CV files will be stored in: {db.storage_dir}")


def handle_add(args: argparse.Namespace) -> None:
    db = build_db(args)
    db.initialize()
    skills = parse_skills(args.skills, args.skill_flags)
    cv_text = None

    text_source = args.text_source
    file_source = args.file
    if text_source:
        cv_text = text_source.read_text(encoding="utf-8")
    elif file_source:
        cv_text = extract_text_from_file(file_source)

    candidate_id = db.add_candidate(
        name=args.name,
        email=args.email,
        phone=args.phone,
        job_title=args.job_title,
        company=args.company,
        location=args.location,
        notes=args.notes,
        skills=skills,
        cv_text=cv_text,
        source_file=file_source,
    )
    print(f"Stored CV #{candidate_id} for {args.name}")


def handle_list(args: argparse.Namespace) -> None:
    db = build_db(args)
    db.initialize()
    candidates = db.list_candidates(
        skill=args.skill,
        location=args.location,
        company=args.company,
        job_title=args.job_title,
    )
    if not candidates:
        print("No CVs found.")
        return
    for candidate in candidates:
        print(format_candidate(candidate))
        print("-" * 40)


def handle_search(args: argparse.Namespace) -> None:
    db = build_db(args)
    db.initialize()
    candidates = db.search_candidates([keyword.lower() for keyword in args.keywords])
    if not candidates:
        print("No matching CVs.")
        return
    for candidate in candidates:
        print(format_candidate(candidate))
        print("-" * 40)


def handle_show(args: argparse.Namespace) -> None:
    db = build_db(args)
    db.initialize()
    candidate = db.get_candidate(args.candidate_id)
    if candidate is None:
        print("CV not found.")
        return
    print(format_candidate(candidate, detailed=True))


def handle_delete(args: argparse.Namespace) -> None:
    db = build_db(args)
    db.initialize()
    removed = db.delete_candidate(args.candidate_id)
    if not removed:
        print("CV not found.")
        return
    print(f"Deleted CV #{args.candidate_id}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
