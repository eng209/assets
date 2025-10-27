## ----------------------------------------------------------------------
##              !! DO NOT RUN THIS SCRIPT DIRECTLY !!
## This script must be executed using the *specific* Python interpreter
## that should be embedded in the virtual environment.
## For example:
##   /usr/bin/python3.12 ./setup_env.py
##
## -----
## Sets up a Python virtual environment, installs required packages,
## configures starter files, and manages VSCode extensions.
##
## Intended for use on the ENG209 virtual machine infrastructure.
## It may not work out-of-the-box on personal machines,
## as local VM images might not automatically mount the
## 'myfiles' directory at ~/Desktop/myfiles.
##
## Version: 2025-08-04
## ----------------------------------------------------------------------

import argparse
import glob
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import venv
import zipfile
from datetime import date
from http.client import HTTPSConnection
from urllib.parse import urlparse, urljoin
from pathlib import Path

# === Config ===
PYTHON_VERSION: str = "3.12.2"
DEFAULT_TARGET_FOLDER: str = os.environ.get(
    "DEFAULT_TARGET_FOLDER", str((Path.home() / "Desktop" / "myfiles").resolve())
)
SEMESTER: str = os.environ.get("SEMESTER", str(date.today().year))
GITHUB_PROJECT: str = os.environ.get(
    "GITHUB_PROJECT", f"https://github.com/eng209/eng209_{SEMESTER}"
)
CODE_ARCHIVE: str = f"{GITHUB_PROJECT}/archive/main.zip"
COURSE_NAME: str = os.environ.get("COURSE_NAME", f"eng209_{SEMESTER}")
VENV_DIR: str = "venv"
PACKAGES: list[str] = [
    "ipykernel",
    "ipywidgets",
    "jupyterlab-latex",
    "matplotlib",
    "plotly",
    "numpy",
    "pandas",
    "scikit-learn",
    "func_timeout",
    "bpython",
    "mypy",
    "nbformat",
    "pooch",
    "tqdm",
    "pandas-stubs",
    "scipy-stubs",
    "ipympl",
]
VSCODE_EXTENSIONS: dict = {
    # pinned versions are known to work with code 1.101.2
    "install": [
        "ms-python.python@2025.12.0",
        "ms-python.black-formatter@2025.2.0",
        "ms-python.mypy-type-checker@2025.2.0",
        "ms-toolsai.jupyter@2025.7.0",
        "matangover.mypy@0.4.2",
        "jock.svg@1.5.4",
    ],
    "uninstall": ["formulahendry.code-runner"],
}
# === ===

logger: logging.Logger


class LogFormatter(logging.Formatter):
    SYMBOLS = {
        logging.DEBUG: "?",  # ALT 🪲, 🐛
        logging.INFO: "✓",
        logging.WARNING: "!",  # ALT ⚠
        logging.ERROR: "✗",
        logging.CRITICAL: "✖",  # ALT 💥, 🔥
    }

    COLORS = {
        logging.DEBUG: "\033[1;90m",  # Bright black
        logging.INFO: "\033[1;32m",  # Green
        logging.WARNING: "\033[1;33m",  # Yellow
        logging.ERROR: "\033[1;31m",  # Red
        logging.CRITICAL: "\033[41m\033[97m",  # White on red bg
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record) -> str:
        label = self.SYMBOLS.get(record.levelno, "?")
        message = record.getMessage()
        prefix = ""
        if message.startswith("\r") and sys.stdout.isatty():
            prefix = "\r"
        message = message.lstrip("\r")
        if self.use_color:
            color = self.COLORS.get(record.levelno, "")
            label = color + label + self.RESET
            positions = [message.find(c) for c in "(:" if c in message]
            if not positions:
                message = self.BOLD + message + self.RESET
            else:
                pos = min(positions)
                message = self.BOLD + message[:pos] + self.RESET + message[pos:]
        # record.msg = f"{prefix}{label} {message}"
        # return super().format(record)
        return f"{prefix}{label} {message}"


class ProgressBar:
    __SPINNER = "|/-\\"

    def __init__(self, width: int, fill: str = "*", verbose: bool = False):
        self.width = width
        self.fill = fill
        self.verbose = verbose
        self.position = 0
        self.is_terminal = sys.stdout.isatty()

    def update(self, progress: int):
        if self.verbose or not self.is_terminal:
            return

        spinner_char = self.__SPINNER[progress % len(self.__SPINNER)]
        dots = "." * self.width
        fill = self.fill * self.width

        if progress == 0:
            bar = f"   \033[90m{dots}\033[0m{spinner_char}\033[1D"
            print(bar, end="", flush=True)
        else:
            filled_part = fill[:progress]
            empty_part = dots[progress:]
            bar = f"\r   \033[1;31m{filled_part}\033[0;90m{empty_part}\033[0m{spinner_char}\033[1D"
            print(bar, end="", flush=True)

    def finish(self):
        if not (self.verbose or not self.is_terminal):
            print("\r" + " " * (self.width + 5) + "\r", end="", flush=True)


def setup_logger() -> logging.Logger:
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)  # sys.stderr is default
    formatter = LogFormatter(True)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def run(cmd: list[str], verbose: bool = False, **kwargs):
    check = kwargs.pop("check", True)
    if verbose or kwargs.get("capture_output"):
        return subprocess.run(cmd, check=check, text=True, **kwargs)
    else:
        return subprocess.run(
            cmd,
            check=check,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )


def download_with_etag(url: str) -> Path:
    cache_dir = Path.home() / ".cache" / "eng209"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / hashlib.sha256(url.encode()).hexdigest()
    meta_path = cache_path.with_suffix(".meta.json")

    headers = {"User-Agent": "Client"}
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
            if meta.get("ETag"):
                headers["If-None-Match"] = meta["ETag"]
            if meta.get("Last-Modified"):
                headers["If-Modified-Since"] = meta["Last-Modified"]

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            if response.status == 304:
                logger.debug("Not modified, using cache.")
                return cache_path

            logger.debug(f"Downloading: {url}")
            data = response.read()
            with open(cache_path, "wb") as f:
                f.write(data)

            # Save headers for next time
            response_meta = {
                "Url": url,
                "ETag": response.headers.get("ETag"),
                "Last-Modified": response.headers.get("Last-Modified"),
            }
            with open(meta_path, "w") as f:
                json.dump(response_meta, f)

            return cache_path

    except urllib.error.HTTPError as e:
        if e.code == 304:
            logger.debug("Not modified (304), using cache.")
            return cache_path
        else:
            raise


def download_github_zip(url: str) -> Path:
    logger.info(f"Download archive: {url}")
    try:
        return download_with_etag(url)
    except Exception as e:
        raise RuntimeError(f"Download failed: {url}\n{e}")


def extract_archive(
    path: Path,
    extract_to: Path,
    overwrite: bool = False,
    verbose: bool = False,
    force_overwrite: set[str] = {"update.py"},
):
    logger.info(f"Extract class materials: {extract_to}")
    if extract_to.exists():
        if overwrite:
            logger.warning(f"Overwrite existing files")
        else:
            logger.warning(f"Existing files are not updated (use --force)")

    with zipfile.ZipFile(str(path), "r") as zip_ref:
        members = zip_ref.infolist()
        root_prefix = members[0].filename.split("/")[0] + "/"
        progress = ProgressBar(width=10, fill="*", verbose=verbose)
        progress.update(0)

        for i, member in enumerate(members, 1):
            if member.is_dir():
                continue

            member_relpath = os.path.relpath(member.filename, root_prefix)
            target_path = os.path.join(extract_to, member_relpath)

            if (
                overwrite
                or not os.path.exists(target_path)
                or member_relpath in force_overwrite
            ):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with open(target_path, "wb") as f:
                    f.write(zip_ref.read(member))
            else:
                logger.debug(f"Skipped existing file: {target_path}")

            progress.update(int(10.0 / len(members) * i))

        progress.finish()


def git_clone_with_retries(
    url: str, dest: Path, timeout: int = 15, verbose: bool = False, deep: bool = False
):
    logger.info(f"Cloning project: {url}")
    progress = ProgressBar(width=timeout, fill="X", verbose=verbose)
    start = time.time()
    i = 0
    while time.time() - start < timeout:
        try:
            if deep:
                run(["git", "clone", url, str(dest)], verbose=verbose)
            else:
                run(
                    ["git", "clone", "--depth", "1", "--single-branch", url, str(dest)],
                    verbose=verbose,
                )
            return
        except subprocess.CalledProcessError:
            i += 1
            progress.update(i)
            time.sleep(1)
    progress.finish()
    if not dest.exists():
        raise RuntimeError(f"Failed to clone {url}")


def verify_python(required_version_str: str):
    required_major, required_minor = map(int, required_version_str.split(".")[:2])
    current_major, current_minor = sys.version_info[:2]

    if (current_major, current_minor) != (required_major, required_minor):
        raise RuntimeError(
            f"Python {required_major}.{required_minor} required, found {current_major}.{current_minor}"
        )

    logger.info(f"Python OK: {current_major}.{current_minor}")


def verify_vscode(verbose: bool = False) -> bool:
    try:
        output = run(["code", "--version"], capture_output=True).stdout.strip()
        logger.info(f"VS Code OK: {output.splitlines()[0]}")
        return True
    except Exception as e:
        logger.warning("VS Code not found (Skipping extension setup)")
        return False


def verify_git(verbose: bool = False) -> bool:
    try:
        output = run(["git", "--version"], capture_output=True).stdout.strip()
        logger.info(f"GIT OK: {output.splitlines()[0]}")
        return True
    except Exception as e:
        logger.warning("Git not found")
        return False


def create_virtualenv(parent_path: Path) -> Path:
    venv_path = parent_path / VENV_DIR
    (venv_path / "lib64").mkdir(parents=True, exist_ok=True)
    builder = venv.EnvBuilder(
        with_pip=True, clear=False, upgrade_deps=True, symlinks=False
    )
    logger.info(f"Creating venv: {venv_path}")
    builder.create(str(venv_path))
    return venv_path


def install_packages(venv_path: Path, verbose: bool = False):
    venv_bin = venv_path / ("Scripts" if os.name == "nt" else "bin")
    pip_path = venv_bin / "pip"
    logger.info(f"Installing Python packages to venv")
    progress = ProgressBar(width=len(PACKAGES), fill="*", verbose=verbose)
    progress.update(0)
    for i, pkg in enumerate(PACKAGES, 1):
        run(
            [str(pip_path), "install", "--require-virtualenv", "--no-input", pkg],
            verbose=verbose,
        )
        progress.update(i)
    # -- Give a custom display name to the python jupyter kernel
    # python_path = venv_bin / "python3.12"
    # run([str(python_path),
    # f"-m", "ipykernel", "install",
    # f"--prefix={venv_path}",
    # f"--name=eng209-venv",
    # f"--display-name=Python3.12 ENG209 venv",
    # ], verbose=verbose)
    progress.finish()


def setup_vscode(project_path: Path, venv_path: Path):
    logger.info(f"Configuring VS Code for project")
    for workspace_file in glob.glob("*.code-workspace"):
        os.remove(workspace_file)
    vscode_dir = project_path / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    venv_subpath = (
        venv_path.relative_to(project_path)
        if venv_path.is_relative_to(project_path)
        else venv_path
    )
    venv_bin = venv_subpath / ("Scripts" if os.name == "nt" else "bin")

    settings = {
        "workbench.editor.showTabs": "multiple",
        "workbench.tree.indent": 20,
        # -- Specify a different default .env path for env variables
        # "python.envFile": (Path("${workspaceFolder}") / ".env").as_posix(),
        # -- Specify a default python interpreter
        "python.venvFolders": ["venv"],
        # -- Specify a default python interpreter
        "python.defaultInterpreterPath": str(
            Path("${workspaceFolder}") / venv_bin / "python"
        ),
        # -- Include the venv python kernels specs under jupyter kernels, using the custom display name
        #    (Note: even if not set it is listed in python environments as python3..., which less ambiguous).
        # "jupyter.jupyterServerKernelSearchPaths": [
        # "${workspaceFolder}/venv/share/jupyter/kernels",
        # ],
        # -- Limit environments so that it does not include others like global conda etc.
        # -- requires: ms-python.vscode-python-environment-manager
        # "python-envs.pythonProjects": [
        #    { "path": "eng209_2025", "envManager": "ms-python.python:venv", "packageManager": "ms-python.python:pip" }
        # ],
        # -- Experimental vscode A/B testing is enabled by default, turn it off
        "python.experiments.enabled": False,
        # -- Activate environment when terminal is opened, but do not change it in existing terminals
        "python.terminal.activateEnvironment": True,
        "python.terminal.activateEnvInCurrentTerminal": False,
        "[python]": {
            "editor.formatOnSave": True,
            "editor.defaultFormatter": "ms-python.black-formatter",
        },
        "mypy.checkNotebooks": True,
        "mypy.mypyExecutable": str(Path("${workspaceFolder}") / venv_bin / "mypy"),
        "mypy.dmypyExecutable": str(Path("${workspaceFolder}") / venv_bin / "dmypy"),
        # -- Hide thes files in file explorer
        "files.exclude": {
            "**/.env": True,
            "**/.git": True,
            "**/.DS_Store": True,
            "**/venv": True,
            "**/.mypy_cache": True,
            "**/.ipynb_checkpoints": True,
            "**/.__pycache__": True,
            "**/*.pyc": True,
        },
        # -- Ignore changes in these files
        "files.watcherExclude": {
            "**/.env": True,
            "**/.git": True,
            "**/.DS_Store": True,
            "**/venv": True,
            "**/.mypy_cache": True,
            "**/.ipynb_checkpoints": True,
            "**/.__pycache__": True,
            "**/*.pyc": True,
        },
        # -- Do not include these files in search
        "search.exclude": {
            "**/.env": True,
            "**/.git": True,
            "**/.DS_Store": True,
            "**/venv": True,
            "**/.mypy_cache": True,
            "**/.ipynb_checkpoints": True,
            "**/.__pycache__": True,
            "**/*.pyc": True,
        },
    }

    with open(vscode_dir / "settings.json", "w") as f:
        json.dump(settings, f, indent=4)

    command = venv_bin / ("bpython.exe" if os.name == "nt" else "bpython")

    tasks = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "bpython",
                "type": "process",
                "command": str(command),
                "problemMatcher": [],
                "presentation": {
                    "focus": True,
                    "showReuseMessage": True,
                    "echo": False,
                    "panel": "dedicated",
                },
            }
        ],
    }

    with open(vscode_dir / "tasks.json", "w") as f:
        json.dump(tasks, f, indent=4)


def setup_vscode_global(code_user_path: Path):
    if not code_user_path.is_dir():
        return
    logger.info(f"Configuring VS Code key bindings (user level)")
    keybindings_path = code_user_path / "keybindings.json"
    if keybindings_path.exists():
        keybindings_path.unlink()
    keybindings = [
        {"key": "ctrl+j", "command": "-workbench.action.togglePanel"},
        {
            "key": "ctrl+i",
            "command": "workbench.action.tasks.runTask",
            "args": "bpython",
        },
        {
            "key": "ctrl+j",
            "command": "workbench.action.tasks.runTask",
            "args": "jupyter",
        },
    ]
    with open(keybindings_path, "w") as f:
        json.dump(keybindings, f, indent=4)


def manage_vscode_extensions(verbose: bool = False):
    logger.info(f"Managing VS Code extensions (user-level)")
    progress = ProgressBar(
        width=len(VSCODE_EXTENSIONS["install"]) + len(VSCODE_EXTENSIONS["uninstall"]),
        fill="*",
        verbose=verbose,
    )
    i = 0
    fail_install = []
    progress.update(i)
    for ext in VSCODE_EXTENSIONS["install"]:
        try:
            if "@" in ext:
                run(["code", "--install-extension", ext], verbose=verbose)
            else:
                run(["code", "--install-extension", ext, "--force"], verbose=verbose)
            time.sleep(0.5)
        except subprocess.CalledProcessError:
            fail_install += [ext]
        i += 1
        progress.update(i)
    fail_uninstall = []
    for ext in VSCODE_EXTENSIONS["uninstall"]:
        try:
            run(["code", "--uninstall-extension", ext], verbose=verbose)
            time.sleep(0.5)
        except subprocess.CalledProcessError:
            fail_uninstall += [ext]
        i += 1
        progress.update(i)
    progress.finish()
    for ext in fail_install:
        logger.warning(f"Could not install VS Code extension '{ext}'")
    for ext in fail_uninstall:
        logger.warning(f"Could not uninstall extension '{ext}' (maybe not installed)")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize and configure the ENG209 programming environment"
    )
    parser.add_argument(
        "--base",
        metavar="PATH",
        type=Path,
        help=f"Directory where the class folder will be created (default: {os.environ.get('ENG209_DIR', DEFAULT_TARGET_FOLDER)})",
        default=os.environ.get("ENG209_DIR", DEFAULT_TARGET_FOLDER),
    )
    parser.add_argument(
        "--clone",
        action="store_true",
        help="Shallow clone (main branch). Default is to copy from github archive.",
    )
    parser.add_argument(
        "--deep-clone",
        action="store_true",
        help="Full clone (all branches, full history)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite when copying from archive (ignored with --clone/--deep-clone)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show verbose output of subprocess commands.",
    )
    args = parser.parse_args()

    global logger
    logger = setup_logger()

    verify_python(PYTHON_VERSION)
    has_git = verify_git()
    has_vscode = verify_vscode(verbose=args.verbose)

    if not args.base.exists():
        raise RuntimeError(f"Target folder {args.base} does not exist")
    logger.info(f"Base folder OK: {args.base}")

    course_path = (args.base / COURSE_NAME).resolve()

    if args.clone or args.deep_clone:
        if not (course_path / ".git").is_dir():
            if not has_git:
                raise RuntimeError(f"git command not found, cannot clone project")
            if course_path.exists():
                raise RuntimeError(
                    f"cannot clone ({course_path} exists and is not a git repository)"
                )
            git_clone_with_retries(
                GITHUB_PROJECT + ".git",
                course_path,
                verbose=args.verbose,
                deep=args.deep_clone,
            )
        else:
            logger.info(f"Using existing project: {course_path}")

    if (course_path / ".git").is_dir():
        if has_git:
            os.chdir(course_path)
            logger.info(f"Updating project: {course_path}")
            try:
                # run(["git", "pull"], verbose=args.verbose)
                # 1. Stash local changes if any
                run(
                    ["git", "stash", "push", "-m", "autostash before update"],
                    verbose=args.verbose,
                )
                # 2. Fetch tags (!moved tags are not updated)
                run(["git", "fetch", "--tags"], verbose=args.verbose)
                # 3. Fetch latest from origin
                run(["git", "fetch", "origin"], verbose=args.verbose)
                # 4. Reset current branch to match remote (remote wins)
                current_branch = run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True
                ).stdout.strip()
                run(
                    ["git", "reset", "--hard", f"origin/{current_branch}"],
                    verbose=args.verbose,
                )
                # 5. Apply stashed changes if possible
                stash_result = run(
                    ["git", "stash", "pop"],
                    verbose=args.verbose,
                    capture_output=True,
                    check=False,
                )
                if (
                    "conflict" in stash_result.stdout.lower()
                    or "conflict" in stash_result.stderr.lower()
                ):
                    raise RuntimeError(
                        "Merge conflict occurred while applying stashed changes"
                    )
            except Exception as e:
                logger.error(f"Update failed: {e}")
                logger.error(
                    "Your local changes may still be stashed. Resolve conflicts manually if needed."
                )
        else:
            logger.warning("Git command not found, cannot update existing git project")
    else:
        archive_file = download_github_zip(CODE_ARCHIVE)
        extract_archive(
            archive_file, course_path, overwrite=args.force, verbose=args.verbose
        )
        os.chdir(course_path)

    venv_path = create_virtualenv(course_path)
    install_packages(venv_path, verbose=args.verbose)

    setup_vscode(course_path, venv_path)

    ## - !!! Configuration Path is specific to VDI ENG virtual machine
    setup_vscode_global(Path.home() / ".config" / "Code" / "User")

    if has_vscode:
        manage_vscode_extensions(verbose=args.verbose)

    update_script = course_path / f"update.py"
    if update_script.exists():
        logger.info("Running post-install update")
        python_path = (
            (venv_path / "Scripts" / "python3.exe")
            if os.name == "nt"
            else (venv_path / "bin" / "python3")
        )
        run([python_path, update_script], verbose=args.verbose)

    if has_vscode:
        logger.info("Launching VS Code...")
        run(["code", str(course_path)], verbose=args.verbose)

    logger.info("Project setup complete...")  # ✅
    logger.info("You're ready to start coding! 🚀")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.critical("\rInterrupted")
    except SystemExit as e:
        sys.exit(e.code)
    except Exception as e:
        logger.critical(f"Error: {e}")
        sys.exit(1)
