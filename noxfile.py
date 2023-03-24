import os
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

python_versions = ["3.6", "3.7", "3.8", "3.9", "3.10"]
args = dict(python=python_versions, reuse_venv=False)


@nox.session(**args)
def test(session):
    # args = [] if session.python.startswith("2") else ["--use-feature=in-tree-build"]
    session.install(".[test]")
    session.run("pytest")


"""
@nox.parametrize(
    "python",
    sum(
        [
            [
                (python, sphinx)
                for sphinx in get_versions("sphinx", "minor", python=python)
            ]
            for python in python_versions
        ],
        [],
    ),
)
def test_full(session):
    # args = [] if session.python.startswith("2") else ["--use-feature=in-tree-build"]
    session.install(".[test]")
    session.run("pytest")


@nox.session(venv_backend="conda", **args)
def test_conda(session):
    # args = [] if session.python.startswith("2") else ["--use-feature=in-tree-build"]
    session.install(".[test]")
    session.run("pytest")
"""
