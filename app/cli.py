#!/usr/bin/env python3
"""FastStarter project CLI — stdlib argparse (no extra CLI library).

From the project root (venv active, deps installed; ``.env`` optional — falls back to ``.env.example``):

    python manage.py init
    python manage.py run
    python manage.py users
    python manage.py report --name "Student Name" --id "816000000"
    python manage.py usecase
    python manage.py skills-verify
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_models_loaded() -> None:
    import app.models  # noqa: F401


def cmd_init(args: argparse.Namespace) -> None:
    """Create database tables (drops existing by default) and seed demo users."""
    from app.config import get_settings
    from app.database import drop_all, ensure_db_and_tables

    _ensure_models_loaded()
    if args.drop:
        print("Dropping all tables…")
        # Drop can fail on a brand-new empty DB; create path still retries.
        try:
            drop_all()
        except Exception as exc:  # noqa: BLE001
            from app.database import is_db_not_ready_error

            if not is_db_not_ready_error(exc):
                raise
            print(f"Database not ready yet while dropping ({exc}); continuing…")
    print("Creating tables…")
    ensure_db_and_tables()
    print(f"Database ready ({get_settings().database_uri}).")
    if getattr(args, "seed", True):
        cmd_seed(args)


def _seed_myadvisor() -> None:
    """Insert the MyAdvisor demo catalogue: degree, courses, profiles, transcript."""
    from app.database import get_cli_session

    with get_cli_session() as session:
        _seed_myadvisor_data(session)


def _seed_myadvisor_data(session) -> None:
    from app.models.planning import SemesterPlan
    from app.models.progress import Advisor, Course, Degree, Student
    from app.models.review import Notification
    from app.repositories.planning import PlanningRepository
    from app.repositories.progress import ProgressRepository
    from app.repositories.review import ReviewRepository
    from app.repositories.user import UserRepository

    repo = ProgressRepository(session)
    planning_repo = PlanningRepository(session)
    review_repo = ReviewRepository(session)

    degree = repo.get_degree_by_name("BSc Computer Science")
    if degree is None:
        degree = repo.create_degree(
            Degree(
                degreeName="BSc Computer Science",
                faculty="Science and Technology",
                totalCredits=120,
            )
        )
        print("  create degree BSc Computer Science")

    # (code, title, credits) — the catalogue the demo student draws plans from.
    catalogue = [
        ("COMP6021", "Software Programming I", 3),
        ("COMP6026", "Operating Systems", 3),
        ("INF08208", "Programming and Technologies I", 3),
        ("COMP6031", "Human-Computer Interaction", 3),
        ("COMP6033", "Object-Oriented Programming II", 3),
        ("COMP6083", "Software Engineering II", 3),
        ("COMP4995", "Applied Mathematics for Scientific Computing", 3),
        ("INF08206", "Information System Security", 3),
        ("COMP6032", "Data Structures and Algorithms", 4),
        ("COMP6034", "Software Engineering I", 3),
        ("COMP6035", "Computer Networks", 3),
        ("COMP6036", "Database Systems", 4),
        ("COMP6037", "Artificial Intelligence", 3),
        ("COMP6038", "Software Quality Assurance", 3),
        ("COMP6039", "Web and Mobile Systems", 3),
        ("COMP6040", "Formal Methods", 4),
        ("COMP6041", "Computer Graphics", 3),
        ("COMP6042", "Compilers", 4),
        ("COMP6043", "Computer Networks II", 3),
        ("COMP6044", "Operating Systems II", 3),
        ("COMP6045", "Software Architecture", 3),
        ("COMP6046", "Machine Learning", 4),
        ("COMP6047", "Cryptography", 3),
        ("INF08207", "Programming and Technologies II", 3),
        ("INF08205", "Information Systems Analysis", 4),
        ("INF08204", "Database Design", 3),
        ("INF08203", "Software Project Management", 3),
        ("INF08202", "Professional Practice", 3),
        ("INF08201", "Discrete Mathematics", 4),
        ("COMP6048", "Mobile Application Development", 3),
        ("COMP6049", "Parallel and Distributed Systems", 3),
    ]
    courses = {}
    for code, title, credits in catalogue:
        course = repo.get_course_by_code(code)
        if course is None:
            course = repo.create_course(Course(code=code, courseName=title, credits=credits))
        courses[code] = course
        repo.require_course(degree.id, course.id)

    # bob's transcript: 18 completed courses worth 59 credits.
    completed = [
        "COMP6021", "COMP6026", "INF08208", "COMP6033", "COMP6083",
        "COMP6034", "COMP6035", "COMP6038", "COMP6041", "COMP6043",
        "COMP6044", "INF08204", "INF08203",
        "COMP6032", "COMP6036", "COMP6040", "COMP6046", "INF08205",
    ]
    outcomes = {code: "completed" for code in completed}
    outcomes["COMP6039"] = "in_progress"
    outcomes["INF08201"] = "failed"

    advisor = repo.get_advisor_by_name("Dr. Hosain")
    if advisor is None:
        admin_user = UserRepository(session).get_by_username("admin")
        advisor = repo.create_advisor(
            Advisor(
                userID=admin_user.id if admin_user else None,
                name="Dr. Hosain",
                faculty="Science and Technology",
            )
        )
        print("  create advisor Dr. Hosain")

    student = repo.get_student_by_name("Bob")
    if student is None:
        bob_user = UserRepository(session).get_by_username("bob")
        student = repo.create_student(
            Student(
                userID=bob_user.id if bob_user else None,
                studentNumber="349836161",
                name="Bob",
                currentAcademicYear="2026-2027",
                degreeID=degree.id,
                advisorID=advisor.id,
            )
        )
        print("  create student Bob")

    for code, status in outcomes.items():
        repo.record_transcript(student.id, courses[code].id, status)

    # Prerequisites — later courses depend on earlier ones, so selecting one
    # without the other completed is refused by the planning service.
    #
    # INF08206 is gated on INF08201, which Bob failed rather than completed.
    # That is the only course in his seeded rejected plan that the rule can
    # catch, which is what makes its "Prerequisite not completed" feedback
    # truthful. INF08207 and COMP6047 chain behind INF08206, and COMP6045
    # behind COMP6037 — three more courses Bob is blocked from.
    prerequisites = [
        ("COMP6031", "COMP6021"),
        ("COMP6033", "COMP6032"),
        ("COMP6034", "COMP6021"),
        ("COMP6036", "COMP6032"),
        ("COMP6040", "COMP6032"),
        ("COMP6041", "COMP6032"),
        ("COMP6042", "COMP6033"),
        ("COMP6044", "COMP6026"),
        ("COMP6046", "COMP6032"),
        ("COMP6049", "COMP6043"),
        ("INF08207", "INF08208"),
        ("INF08206", "INF08201"),
        ("INF08207", "INF08206"),
        ("COMP6047", "INF08206"),
        ("COMP6045", "COMP6037"),
    ]
    for course_code, prereq_code in prerequisites:
        planning_repo.add_prerequisite(courses[course_code].id, courses[prereq_code].id)

    # Bob's existing plans, matching the states the wireframe shows.
    existing_plans = [
        ("1", "2025/2026", "submitted", ["COMP6031", "COMP6026"], {}),
        (
            "2",
            "2026/2027",
            "rejected",
            ["COMP6031", "COMP6026", "INF08206", "COMP6033", "INF08208"],
            {"INF08206": ("rejected", "Prerequisite not completed")},
        ),
        ("1", "2024/2025", "approved", ["COMP6032", "COMP6034"], {}),
        ("2", "2024/2025", "approved", ["COMP6036", "COMP6040"], {}),
    ]
    for semester, academic_year, plan_status, codes, decisions in existing_plans:
        plan = planning_repo.find_plan(student.id, semester, academic_year)
        if plan is None:
            plan = planning_repo.create_plan(
                SemesterPlan(
                    studentID=student.id,
                    semester=semester,
                    academicYear=academic_year,
                    status=plan_status,
                ),
                [courses[code].id for code in codes],
            )
            for code, (decision, feedback) in decisions.items():
                planning_repo.set_course_decision(plan.id, courses[code].id, decision, feedback)
        else:
            planning_repo.set_plan_status(plan.id, plan_status)

    # Other advisees of Dr. Hosain, so the advisor's Pending and Reviewed tabs
    # are not just one student's plan. These carry plans only — no transcript,
    # so the advisor screens have realistic volume without touching Bob's data.
    other_students = [
        ("326249340", "Priya Williams", "1", "2026/2027", "submitted", ["COMP6031", "COMP6033"]),
        ("852495128", "Lucy Roberts", "1", "2026/2027", "submitted", ["COMP6041", "COMP6038"]),
        ("960500621", "Brian Thomas", "2", "2026/2027", "submitted", ["INF08207", "COMP6049"]),
        ("741852963", "Amara Lewis", "2", "2025/2026", "approved", ["COMP6042", "COMP6047"]),
        ("552014770", "Devon Clarke", "1", "2025/2026", "rejected", ["COMP6045", "COMP6048"]),
    ]
    for number, full_name, semester, academic_year, plan_status, codes in other_students:
        peer = repo.get_student_by_name(full_name)
        if peer is None:
            peer = repo.create_student(
                Student(
                    studentNumber=number,
                    name=full_name,
                    currentAcademicYear="2026-2027",
                    degreeID=degree.id,
                    advisorID=advisor.id,
                )
            )
        if planning_repo.find_plan(peer.id, semester, academic_year) is None:
            planning_repo.create_plan(
                SemesterPlan(
                    studentID=peer.id,
                    semester=semester,
                    academicYear=academic_year,
                    status=plan_status,
                ),
                [courses[code].id for code in codes],
            )

    # Notifications for the advisor, as drawn on their dashboard.
    for peer_name, message in [
        ("Priya Williams", "Priya Williams submitted their Semester Plan."),
        ("Lucy Roberts", "Lucy Roberts submitted their Semester Plan."),
        ("Brian Thomas", "Brian Thomas submitted their Semester Plan."),
    ]:
        if review_repo.list_notifications_for_advisor(advisor.id):
            break
        peer = repo.get_student_by_name(peer_name)
        review_repo.add_notification(
            Notification(advisorID=advisor.id, message=message)
        )

    print(
        f"  MyAdvisor demo data ready — {len(catalogue)} courses required, "
        f"{len(completed)} completed ({sum(c[2] for c in catalogue if c[0] in completed)} credits), "
        f"{len(existing_plans) + len(other_students)} semester plans, "
        f"{len(other_students) + 1} students"
    )


def cmd_seed(args: argparse.Namespace) -> None:
    """Insert demo users.

    bob / bobpass       (regular_user)
    admin / adminpass   (admin)
    """
    from app.database import ensure_db_and_tables, get_cli_session
    from app.repositories.user import UserRepository
    from app.schemas.user import AdminCreate, RegularUserCreate
    from app.utilities.security import encrypt_password

    _ensure_models_loaded()
    ensure_db_and_tables()

    demo_users = [
        ("bob", "bob@example.com", "bobpass", "regular_user"),
        ("admin", "admin@example.com", "adminpass", "admin"),
    ]

    created = 0
    skipped = 0
    with get_cli_session() as session:
        repo = UserRepository(session)
        for username, email, password, role in demo_users:
            if repo.get_by_username(username):
                print(f"  skip  {username} (already exists)")
                skipped += 1
                continue
            payload_cls = AdminCreate if role == "admin" else RegularUserCreate
            repo.create(
                payload_cls(
                    username=username,
                    email=email,
                    password=encrypt_password(password),
                    role=role,
                )
            )
            print(f"  create {username} ({role})")
            created += 1

    print(f"Seed done — created {created}, skipped {skipped}.")
    _seed_myadvisor()
    print("Login with bob/bobpass (student) or admin/adminpass (advisor)")


def cmd_run(args: argparse.Namespace) -> None:
    """Start the FastAPI app with Uvicorn."""
    import uvicorn

    from app.config import get_settings

    settings = get_settings()
    bind_host = args.host or settings.app_host
    bind_port = args.port or settings.app_port
    if args.reload is None:
        use_reload = settings.env.lower() != "production"
    else:
        use_reload = args.reload
    print(f"Starting FastStarter on http://{bind_host}:{bind_port} (reload={use_reload})")
    uvicorn.run(
        "app.main:app",
        host=bind_host,
        port=bind_port,
        reload=use_reload,
    )


def cmd_report(args: argparse.Namespace) -> None:
    """Build the submission package: merge judge, package transcripts, write PDF.

    Guide must (1) write ``docs/judge.md`` and (2) pull every Guide chat into
    ``docs/transcripts/*.md`` before this command. Report only packages those files.
    """
    from app.report_pdf import export_report
    from app.skill_integrity import format_report, verify

    result = export_report(
        name=args.name,
        student_id=args.student_id,
        source=None if args.src is None else Path(args.src),
        output=None if args.output is None else Path(args.output),
    )
    print()
    print("Report package:")
    print(
        f"  Judge:       {'merged docs/judge.md' if result.judge_merged else 'MISSING - Guide must run student-judge first'}"
    )
    print(
        f"  Transcripts: {result.transcript_count} chat(s) in docs/transcripts/"
        + (
            ""
            if result.transcript_count
            else " (EMPTY - Guide must pull Copilot/Cursor/OpenCode chats first)"
        )
    )
    if result.transcript_zip:
        print(f"  Zip:         {result.transcript_zip.as_posix()}")
    print(f"  PDF:         {result.pdf_path.as_posix()}")
    print(format_report(verify()))


def cmd_transcripts(args: argparse.Namespace) -> None:
    """Package agent-written markdown under docs/transcripts/ (+ zip)."""
    from app.transcript_export import package_transcripts

    result = package_transcripts(make_zip=not args.no_zip)
    if result.found == 0:
        print(
            "Warning: no chat markdown in docs/transcripts/. "
            "The Guide agent must pull every Guide chat for this project "
            "(Copilot Agent, Cursor, or OpenCode) into docs/transcripts/<slug>.md first."
        )
        raise SystemExit(2)
    print(f"Submission package ready: {result.out_dir}")
    if result.zip_path:
        print(f"Zip for submission: {result.zip_path}")


def cmd_skills_verify(args: argparse.Namespace) -> None:
    """Check course skill files against .agents/skills.lock.json."""
    from app.skill_integrity import format_report, verify

    result = verify()
    print(format_report(result))
    if not result.ok:
        raise SystemExit(1)


def cmd_usecase(args: argparse.Namespace) -> None:
    """Render docs/diagrams/use-case.json to a UML use-case PNG."""
    from app.usecase_diagram import render_usecase_png

    dest = render_usecase_png(
        spec_path=None if args.spec is None else Path(args.spec),
        output=None if args.output is None else Path(args.output),
    )
    print(f"Wrote {dest}")


def cmd_skills_lock(args: argparse.Namespace) -> None:
    """Rewrite the skill lockfile (course authors only)."""
    from app.skill_integrity import write_lock

    dest = write_lock()
    print(f"Wrote {dest}")


def cmd_users(args: argparse.Namespace) -> None:
    """List users currently in the database."""
    from sqlmodel import select

    from app.database import get_cli_session
    from app.models.user import User

    _ensure_models_loaded()
    with get_cli_session() as session:
        users = session.exec(select(User)).all()
        if not users:
            print("No users found. Run: python manage.py init")
            return
        for user in users:
            print(
                f"  id={user.id}  username={user.username}  "
                f"role={user.role}  email={user.email}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python manage.py",
        description="FastStarter Python CLI — init database, seed demo data, run the app.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init",
        help="Create DB tables and seed demo users (drops existing tables by default)",
    )
    p_init.add_argument(
        "--no-drop",
        dest="drop",
        action="store_false",
        help="Create tables without dropping existing ones",
    )
    p_init.add_argument(
        "--no-seed",
        dest="seed",
        action="store_false",
        help="Skip demo user seed after creating tables",
    )
    p_init.set_defaults(drop=True, seed=True, func=cmd_init)

    p_seed = sub.add_parser(
        "seed",
        help="Insert demo users only (idempotent; also runs as part of init)",
    )
    p_seed.set_defaults(func=cmd_seed)

    p_run = sub.add_parser("run", help="Start the web app (uvicorn)")
    p_run.add_argument("--host", default=None, help="Bind host")
    p_run.add_argument("--port", type=int, default=None, help="Bind port")
    reload_group = p_run.add_mutually_exclusive_group()
    reload_group.add_argument(
        "--reload", dest="reload", action="store_true", default=None, help="Enable auto-reload"
    )
    reload_group.add_argument(
        "--no-reload", dest="reload", action="store_false", help="Disable auto-reload"
    )
    p_run.set_defaults(func=cmd_run, reload=None)

    p_users = sub.add_parser("users", help="List users in the database")
    p_users.set_defaults(func=cmd_users)

    p_report = sub.add_parser(
        "report",
        help=(
            "Build submission package: merge docs/judge.md, package docs/transcripts/, "
            "write docs/report.pdf (Guide pulls chats + runs student-judge first)"
        ),
    )
    p_report.add_argument("--name", required=True, help="Student name (printed on the PDF cover)")
    p_report.add_argument("--id", dest="student_id", required=True, help="Student ID (PDF only)")
    p_report.add_argument("--src", default=None, help="Markdown path (default: docs/report.md)")
    p_report.add_argument("--output", default=None, help="PDF path (default: docs/report.pdf)")
    p_report.set_defaults(func=cmd_report)

    p_transcripts = sub.add_parser(
        "transcripts",
        help="Package agent-written docs/transcripts/*.md into INDEX + zip (no IDE scrape)",
    )
    p_transcripts.add_argument(
        "--no-zip",
        action="store_true",
        help="Skip writing docs/transcripts.zip",
    )
    p_transcripts.set_defaults(func=cmd_transcripts)

    p_usecase = sub.add_parser(
        "usecase",
        help="Render docs/diagrams/use-case.json to a UML use-case PNG",
    )
    p_usecase.add_argument("--spec", default=None, help="JSON spec (default: docs/diagrams/use-case.json)")
    p_usecase.add_argument("--output", default=None, help="PNG path (default: docs/diagrams/use-case.png)")
    p_usecase.set_defaults(func=cmd_usecase)

    p_skills_verify = sub.add_parser(
        "skills-verify",
        help="Check course skills against .agents/skills.lock.json",
    )
    p_skills_verify.set_defaults(func=cmd_skills_verify)

    p_skills_lock = sub.add_parser(
        "skills-lock",
        help="Rewrite .agents/skills.lock.json (course authors; needs FASTSTARTER_SKILLS_LOCK=1)",
    )
    p_skills_lock.set_defaults(func=cmd_skills_lock)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
