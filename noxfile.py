import os
from pathlib import Path
import sys
import nox

# from nox_poetry import session

sys.path.append(".")
# from noxutils import get_versions

# Do not use anything installed in the site local directory (~/.local for example) which
# might have been installed by pip install --user.  These can prevent the install here
# from pulling in the correct packages, thereby mucking up tests later on.
# See https://stackoverflow.com/a/51640558/1088938
os.environ["PYTHONNOUSERSITE"] = "1"
os.environ["PY_IGNORE_IMPORTMISMATCH"] = "1"  # To avoid ImportMismatchError

# By default, we only execute the conda tests because the others required various python
# interpreters to be installed.  The other tests can be run, e.g., with `nox -s test` if
# desired.
nox.options.sessions = ["test"]

DEV_PY = os.environ.get("DEV_PY", "3.10")
python_versions = ["3.11", "3.10", "3.9", "3.8", "3.7", "3.6"]
args = dict(python=python_versions, reuse_venv=True)


@nox.session(**args)
def test(session):
    # args = [] if session.python.startswith("2") else ["--use-feature=in-tree-build"]
    session.install(".[test]")
    try:
        session.run("coverage", "run", "--parallel", "-m", "pytest", *session.posargs)
    finally:
        if session.interactive:
            session.notify("coverage", posargs=[])


# https://github.com/cjolowicz/cookiecutter-hypermodern-python/blob/main/%7B%7Bcookiecutter.project_name%7D%7D/noxfile.py
@nox.session(python=DEV_PY)
def coverage(session):
    """Produce the coverage report."""
    args = session.posargs or ["report"]

    # Install the full package for HTML reports.
    session.install(".[test]")

    if not session.posargs and any(Path().glob(".coverage.*")):
        session.run("coverage", "combine")

    session.run("coverage", *args)


@nox.session(venv_backend="conda", **args)
def test_conda(session):
    # args = [] if session.python.startswith("2") else ["--use-feature=in-tree-build"]
    session.install(".[test]")
    session.run("pytest")
