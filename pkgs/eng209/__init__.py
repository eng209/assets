from pathlib import Path
import os
import sysconfig
from collections.abc import Sequence


# Find parent of quiz folder
def __detect_project_root(*markers: str | Sequence[str]) -> Path:
    if len(markers) == 1 and isinstance(markers[0], (list, tuple)):
        _markers = markers[0]
    else:
        _markers = markers

    for file in [__file__, sysconfig.get_paths().get("purelib", "")]:
        path = Path(file).absolute()
        for depth in range(0, 10):
            path = path.parent
            for marker in _markers:
                if (path / marker).exists():
                    return path

    return Path(os.environ.get("QUIZZ_HOME", Path.home()))


_marker = ".qdb"

__project_root: Path = __detect_project_root(_marker)


def get_project_root() -> Path:
    return __project_root


def set_project_root(path: str):
    global __project_root
    _path = Path(path)
    if not _path.is_dir():
        raise ValueError(f"Invalid path: {path}")
    __project_root = _path.absolute()


__all__ = ["get_project_root", "set_project_root", "_marker"]
