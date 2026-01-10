import json
from pathlib import Path
import re
from typing import Literal
from src import utilities

BASE_DIR = Path(__file__).parent.parent
app_path_pattern = r"^(dir:|file:)(.*)$"


def fpath(p: str) -> AppPath:
    return AppPath(f"file:{p}")


def dpath(p: str) -> AppPath:
    return AppPath(f"dir:{p}")


class AppPathError(Exception):
    """Custom exception for AppPath errors."""

    def __init__(
        self,
        message: str,
        path: AppPath | None = None,
        type: Literal["not_found", "wrong_type", "uncaught"] = "uncaught",
    ):
        self.path = path
        self.type = type
        super().__init__(message)


class AppPath:

    type: Literal["file", "dir"]

    def __init__(self, path: str):
        if path is None:
            raise AppPathError(f"Path cannot be None", path=None, type="uncaught")
        else:
            pattern = re.compile(app_path_pattern)
            match = pattern.match(path)
            if not match:
                raise AppPathError(
                    f"Invalid AppPath format: {path}", path=None, type="uncaught"
                )
            p = Path(match.group(2))
            self.type = match.group(1)[:-1]
            self.path = BASE_DIR / p if not p.is_absolute() else p
            self.path = self.path.resolve()

    def to_dict(self) -> dict:
        return {"type": self.type, "path": self.path}

    def __str__(self):
        return f"{self.type}:{self.path}"

    def __repr__(self):
        return self.__str__()

    def glob(self, pattern: str) -> list[AppPath]:
        return [
            fpath(str(p)) if p.is_file() else dpath(str(p))
            for p in self.path.glob(pattern)
        ]

    def read_json(self) -> dict:
        try:
            read_dict = {}
            with open(self.path, "r", encoding="utf-8") as f:
                read_dict = json.load(f)
            return read_dict
        except Exception as e:
            raise AppPathError(f"{e}", path=self, type="uncaught")

    def write_json(self, dict: dict, merge: bool = True) -> None:
        if merge:
            write_dict = utilities.deep_merge_dicts(self.read_json(), dict)
        else:
            write_dict = dict

        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(write_dict, f, indent=4)
        except Exception as e:
            raise AppPathError(f"{e}", path=self, type="uncaught")

    def validate(
        self,
        action: Literal["r", "w"] = "r",
        allow_create: bool = True,
    ) -> Path:
        if self.path is None:
            raise AppPathError("Path is None", path=self, type="not_found")

        if self.path.exists():
            if self.type == "file" and not self.path.is_file():
                raise AppPathError(
                    f"{self.path} is not a file", path=self, type="wrong_type"
                )
            elif self.type == "dir" and not self.path.is_dir():
                raise AppPathError(
                    f"{self.path} is not a directory", path=self, type="wrong_type"
                )
        else:
            if action == "r" or not allow_create:
                raise AppPathError(
                    f"{self.path} does not exist", path=self, type="not_found"
                )
            elif action == "w":
                directory = self.path if self.type == "dir" else self.path.parent
                if not directory.exists():
                    directory.mkdir(parents=True, exist_ok=True)
                if self.type == "file":
                    self.path.touch(exist_ok=True)

        return self.path
