from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from . import spec


class ConfigurationWriter(ABC):
    """simple writer/reader base class that jus
    expects a similar interface to python's builtin json module"""

    @classmethod
    @abstractmethod
    def dumps(cls, node: spec.AnyConfigField) -> str:
        """dump Configuration tree/node as a string"""
        pass

    @classmethod
    @abstractmethod
    def dump(cls, file, node: spec.AnyConfigField):
        if isinstance(file, (str, Path)):
            with open(file, "w") as f:
                f.write(cls.dumps(node))
            return

        file.write(cls.dumps(node))

    @classmethod
    @abstractmethod
    def loads(cls, file) -> dict[str, Any]:
        """load a file by name"""
        pass

    @classmethod
    @abstractmethod
    def load(cls, file) -> dict[str, Any]:
        """load a file by name"""
        if isinstance(file, (str, Path)):
            with open(file, "r") as f:
                return cls.loads(f.read())

        return cls.loads(file.read())
