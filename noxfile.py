from pathlib import Path

import nox


@nox.session(name="refresh-data")
def refresh(session: nox.Session) -> None:
    """Update and regenerate data."""
    try:
        base = Path(session.posargs[0])
    except IndexError:
        session.error("Please specify the /data/ directory")

    session.install("attrs", "click", "colorama", "requests")
    session.run("python", "-m", "scripts.ghstats", "fetch-issue-data", str(base))
    session.run("python", "-m", "scripts.ghstats", "generate-ghstats-data", str(base))


@nox.session(name="run-ghstats")
def run_ghstats(session: nox.Session) -> None:
    """Run scripts.ghstats with arguments."""
    session.install("attrs", "click", "colorama", "jinja2")
    session.run("python", "-m", "scripts.ghstats", *session.posargs)
