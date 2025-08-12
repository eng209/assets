#!/bin/bash

# This setups a Python venv, installs some packages,
# setups some start files, and adds VSCode extenstions.
# As is, it is suitable to use on the VM infrastructure used in e.g. ENG209
# It will probably not work right away on local VM
# images may lack automatic mounting of myfiles at ~/Desktop/myfiles.
# Authors: Jean-Philippe Pellet, Matthieu Bovel
# Version: 2025-08-04

PYTHON_VERSION="3.12.2"
PYTHON_EXEC=python${PYTHON_VERSION%.*}
PYTHON_PATH="${PYTHON_PATH-/opt/python${PYTHON_VERSION}}/bin/${PYTHON_EXEC}"
TARGET_FOLDER="${TARGET_FOLDER-${HOME}/Desktop/myfiles}"

SEMESTER="2025"
GITHUB_PROJECT="https://github.com/eng209/eng209_${SEMESTER}.git"
COURSE_NAME="eng209_${SEMESTER}"

logmsg() {
    local -r  mark_color=${1}
    local -r  mark=${2}
    local -r  msg_color=${3}
    local -ir msg_length=${4}
    local -r  message=${5}
    local -r  detail_color=${6-39}
    local     detail=${7-}
    detail=${detail+ ${detail}}
    if (( is_terminal )); then
        printf '\r\033[%sm\033[1m%s \033[%sm\033[1m%-*s\033[0m\033[%sm\033[3m%s\033[0m\n' \
               "${mark_color}" "${mark}" "${msg_color}" "${msg_length}" " ${message}" "${detail_color}" "${detail}" >&3
    else
        printf '%s %-*s%s\n' "${mark}" ${msg_length} " ${message}" "${detail}" >&3
    fi
}

infomsg() {
    logmsg 32 '✓' 39 40 "$1" 90 "${2-}"
}

warnmsg() {
    logmsg 93 '!' 93 40 "$1" 90 "${2-}"
}

errmsg() {
    logmsg 31 '✗' 31 40 "$1" 90 "${2-}"
}

progress() {
    local -ir bar_width=$1
    local -ir position=$2
    if (( debug )) || (( ! is_terminal )); then
        return
    fi
    local bar
    printf -v bar -- '%*s' ${bar_width} ''
    local -r  fill=${bar// /${3-'*'}}
    local -r  dots=${bar// /.}
    local -r  spinner='|/-\'
    local -r  spinner_char=${spinner:position % ${#spinner}:1}
    if (( $2 == 0 )); then
        printf -- '   \033[90m%s\033[0m%s\033[1D' "${dots}" "${spinner_char}" >&3
    else
        printf -- '\r   \033[1;31m%s\033[0;90m%s\033[0m%s\033[1D' "${fill:0:position}" "${dots:position}" "${spinner_char}" >&3
    fi
}

quit() {
    exec 3>&1
    exec 4>&2
    [[ ! -t 1 ]] || printf '\033[0m' >&1
}

sigint() {
    trap - ERR
    errmsg Interrupted "(abort)"
    exit 130
}

err() {
    errmsg 'Installation failed!' 'Please, ask for help...'
}

verify_python() {
    if [[ ! -x "${python_path-x}" ]]; then
        errmsg '..... Error' "Invalid python executable ${PYTHON_PATH}"
        return 1
    fi
    local -r python_expect_regex="^[Pp]ython ${PYTHON_VERSION%.*}.*$"
    local -r python_actual="$(${python_path} --version|head -1)"
    if [[ ! "${python_actual-x}" =~ ${python_expect_regex} ]]; then
        errmsg '..... Error' "Expect python version ${PYTHON_VERSION}, got ${python_actual} ..."
        return 1
    else
        infomsg '..... Python OK' "$(realpath ${python_path}) (${python_actual})"
        return 0
    fi
}

verify_vscode() {
    local -r code="$(command -v code||:)"
    if [[ -z "${code-}" ]]; then
        warnmsg '..... Warning' 'vscode not found, extensions will not be installed...'
        return 1
    else
        infomsg '..... Vscode OK' "$(realpath ${code}) ($(${code} --version|head -1))"
        return 0
    fi
}

copy_project() {
    # Clone the latest commit from the main branch, retrying until successful or 10 seconds elapse.
    # Subsequent pulls replace it with the latest commit (local history depth remains 1).
    if [[ ! -d ${course_path} ]]; then
        infomsg '[2/8] Copying project...' "$(realpath $(pwd))/${course_path}"
        local -r git="$(command -v git||:)"
        if [[ "${git-}" == "" ]]; then
            errmsg 'Error' "Git is required in order to copy project ${GITHUB_PROJECT}"
            return 1
        fi
        local -ir try_until=$(date +%s)+15
        while ! git clone --depth 1 --branch main --single-branch -- "${GITHUB_PROJECT}" "${course_path}" \
              && (( $(date +%s) < try_until )); do
            progress 5 $((5-(try_until-$(date +%s))/3)) X
            sleep 1
        done
        if [[ ! -d "${course_path}" ]]; then
            errmsg 'Error' "Failed to clone project ${GITHUB_PROJECT} to '${course_path}'"
            return 1
        fi
    else
        infomsg '[2/8] Set project location' "$(realpath $(pwd))/${course_path}"
    fi
}

usage() {
    cat <<-EOF
ENG209 Environment Setup Script

This script configures your user environment for the ENG209 course.

By default, it is designed for use on VDI virtual machines.
If you're using a custom installation, set the following environment variables:

  PARENT_DIR   - Parent directory where the ENG209 class folder will be created
  PYTHON_PATH  - Python executable to use for the virtual environment

Options:
  --verbose     Print detailed output during execution
  --parent      Set the parent directory of the project
                (current: ${TARGET_FOLDER:-None})
  --python      Set the Python executable for the virtual environment
                (current: ${PYTHON_PATH:-None})

What this script does:
  - Copies class materials from GitHub into PARENT_DIR (directory must exist)
  - Creates a Python virtual environment inside the class folder
  - Installs required Python packages in the virtual environment
  - Configures VS Code settings for the project
  - Adds/removes VS Code extensions (user-level)
  - Launches VS Code in the class folder

EOF
}

main() {

set -euCo pipefail
local -i debug=0

while (( ${#@} > 0)); do
    case "${1}" in
        --) break ;;
        --trace) set -x; debug=1 ;;
        --verbose) debug=1 ;;
        --parent)  TARGET_FOLDER=$(realpath "${2-}") && shift || return 1;;
        --python)  PYTHON_PATH=$(realpath "${2-}") && shift || return 1;;
        --help)  usage; return 0 ;;
        *) usage; return 1 ;;
    esac
    shift
done

trap err    ERR
trap quit   EXIT
trap sigint SIGINT
exec 3>&1
exec 4>&2

if [[ -t 1 ]]; then
    local -i is_terminal=1
else
    local -i is_terminal=0
fi

if (( ! debug )); then
    exec 1>/dev/null
    exec 2>/dev/null
fi

if (( is_terminal )); then
    tput clear
fi

local -r python_path="${PYTHON_PATH}" 
local -r course_path="eng209_${SEMESTER}"
local -a  pip3_opts=(--require-virtualenv --no-input)

(( debug )) || pip3_opts+=(-q)

infomsg '[1/8] Verifying environment'

if [[ ! -d "${TARGET_FOLDER}" ]]; then
    errmsg '..... Error' "Folder ${TARGET_FOLDER} does not exist (will not create)..."
fi
cd "$(realpath ${TARGET_FOLDER})"

verify_python
if ! verify_vscode; then
    local -ir skip_vscode=1
else
    local -ir skip_vscode=0
fi

copy_project
cd "$course_path"

infomsg '[3/8] Updating project...' "$(realpath $(pwd))"
git pull

infomsg "[4/8] Creating a virtual environment..." "$(pwd)/venv (${PYTHON_EXEC})"

mkdir -p venv/lib64 # needed to avoid symlink creation error on smb share
"$python_path" -m venv --copies --upgrade-deps venv
source venv/bin/activate

infomsg "[5/8] Installing Python packages..." "$(realpath venv)"
# func_timeout for testing harness
# bpython interpreter with completion and syntax highlighting
# mypy
local -ar packages=(ipykernel ipywidgets jupyterlab-latex matplotlib plotly numpy pandas scikit-learn func_timeout bpython mypy nbformat)
local -i  package_num=0

progress ${#packages[@]} 0
for pkg in "${packages[@]}"; do
    pip3 install "${pip3_opts[@]}" "${pkg}"
    package_num+=1
    progress ${#packages[@]} ${package_num}
done

infomsg '[6/8] Finishing setup...'

# This can be of course tweaked to reflect the best initial options for
# the created VS Code workspace. Careful with $, which must be escaped.
mkdir -p .vscode
rm -f *.code-workspace
rm -f .vscode/settings.json
cat > .vscode/settings.json << EOM
// Ce fichier détermine les paramètres de votre workspace.
// Merci de ne pas le modifier à moins que la donnée d'un
// exercice vous demande de le faire.
{
    "workbench.editor.showTabs": "multiple",
    "workbench.tree.indent": 20,
    "python.envFile": "\${workspaceFolder}/venv",
    "python.defaultInterpreterPath": "venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.terminal.activateEnvInCurrentTerminal": true,
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "ms-python.black-formatter"
    },
    "mypy.checkNotebooks": true,
    "mypy.mypyExecutable": "\${workspaceFolder}/venv/bin/mypy",
    "mypy.dmypyExecutable": "\${workspaceFolder}/venv/bin/dmypy",
    "files.watcherExclude": {
        "**/.env/**": true,
        "**/venv/**": true,
        "**/.mypy_cache": true,
        "**/.ipynb_checkpoints": true
    },
    "files.exclude": {
        "**/.env/**": true,
        "**/venv/**": true,
        "**/.mypy_cache": true,
        "**/.ipynb_checkpoints": true
    },
    "python.terminal.activateEnvInCurrentTerminal": false
}
EOM

# Predefined tasks can be provided like this
rm -f .vscode/tasks.json
cat > .vscode/tasks.json << EOM
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "bpython",
            "type": "shell",
            "command": "source venv/bin/activate && venv/bin/bpython",
            "problemMatcher": [],
            "presentation": {
                "focus": true,
                "showReuseMessage": true,
                "echo": false,
                "panel": "dedicated"
            }
        }
    ]
}
EOM

if (( ! skip_vscode )); then
    infomsg '[7/8] Installing VS Code extensions...'
    local -ar add_extensions=(ms-python.python ms-python.black-formatter ms-python.mypy-type-checker matangover.mypy jock.svg)
    local -ar del_extensions=(formulahendry.code-runner)
    local -i  task_num=0
    local -i  num_tasks=${#add_extensions[@]}+${#del_extensions[@]}
    progress ${num_tasks} 0
    for extension in ${add_extensions[@]}; do
        code --install-extension "${extension}" --force
        task_num+=1
        progress ${num_tasks} ${task_num}
    done
    for extension in ${del_extensions[@]}; do
        code --uninstall-extension "${extension}" || true
        task_num+=1
        progress ${num_tasks} ${task_num}
    done

    infomsg '[8/8] Done' "Launching VS Code and opening folder '${course_path}'"
    code $(realpath .)
else
    infomsg '[7/8] Installing VS Code extensions...' 'SKIP'
    infomsg '[8/8] Done'
fi
}

main "$@"
