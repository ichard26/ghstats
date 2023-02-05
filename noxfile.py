from pathlib import Path

import nox


@nox.session(name="refresh")
def refresh(session: nox.Session) -> None:
    """Update and regenerate data."""
    try:
        base = Path(session.posargs[0])
    except IndexError:
        base = Path.cwd()

    session.install("attrs", "click", "colorama", "requests")
    session.run("python", "-m", "scripts.download", "update", str(base / "issue-data.json"))

    for name in ("issue-counts", "issue-closers", "issue-deltas", "pull-counts"):
        session.run(
            "python",
            "-m"
            "scripts.generate_data",
            name,
            str(base / "issue-data.json"),
            "-o",
            str(base / f"{name}.json"),
        )
