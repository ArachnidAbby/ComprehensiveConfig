from abc import ABCMeta
import os
from typing import Any, Self, Type, Union

from . import configio
from . import spec
from .json import JsonWriter
from .toml import TomlWriter


class _ConfigSpecMeta(type):
    """handles getting of attributes"""

    _WRITER: Type[configio.ConfigurationWriter] | None
    _DEFAULT_FILE: str | None
    _AUTO_LOAD: bool
    _CREATE_FILE: bool
    _INST: Union["ConfigSpec", None]

    def __new__(
        cls,
        name,
        bases,
        attrs,
        default_file: str | None = None,  # automatically load a specific file
        writer=None,
        create_file: bool = False,  # create the default file if not exists
        auto_load: bool = True,
        **kwargs,
    ):
        cls._DEFAULT_FILE = default_file
        cls._WRITER = writer
        cls._INST = None
        cls._CREATE_FILE = create_file
        cls._AUTO_LOAD = auto_load
        return super().__new__(cls, name, bases, attrs)

    def __get__(self, instance, owner):
        if self._INST is None:
            return self
        return self._INST

    def __getattribute__(self, name):
        """get attributes from active instance if available"""
        inst = object.__getattribute__(self, "_INST")
        if inst is not None and name in inst._ALL_FIELDS.keys():
            return inst.__getattribute__(name)

        return super().__getattribute__(name)

    def __setattribute__(self, name, value):
        """set attributes from active instance if available"""
        inst = object.__getattribute__(self, "_INST")
        if inst is not None and name in inst._ALL_FIELDS.keys():
            return inst.__setattribute__(name, value)

        return super().__setattr__(name, value)


class _ConfigSpecABCMeta(spec.ConfigurationFieldABCMeta, _ConfigSpecMeta):
    """A combination of ABCMeta and config spec meta"""


class ConfigSpec(spec.Section, metaclass=_ConfigSpecABCMeta):

    @classmethod
    def __init_subclass__(
        cls,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        if not cls._AUTO_LOAD:
            return

        if cls._WRITER is None or cls._DEFAULT_FILE is None:
            raise ValueError("config writer is not specified")

        exists = os.path.exists(cls._DEFAULT_FILE)
        if exists and not os.path.isfile(cls._DEFAULT_FILE):
            raise Exception(f"configuration file: {cls._DEFAULT_FILE} is not a file")

        if exists:
            cls._INST = cls(cls._WRITER.load(cls._DEFAULT_FILE))
        if not exists and cls._CREATE_FILE:
            default = cls()
            cls._WRITER.dump(cls._DEFAULT_FILE, default)
            cls._INST = default
        if not exists and not cls._CREATE_FILE:
            raise FileNotFoundError(cls._DEFAULT_FILE)

    def __init__(self, value: dict[str, Any] | None = None, /):
        if value is None and not self._has_default:
            raise Exception("Configuration does not have a full default value")

        super().__init__(value or self._default_value)

    @classmethod
    def load(cls, file=None, writer=None, /) -> Self:
        file = file or cls._DEFAULT_FILE
        writer = writer or cls._WRITER

        if writer is None:
            raise ValueError("no writer specified")
        if file is None:
            raise Exception("No file specified")

        return cls(writer.load(file))

    def save(self, file=None, writer=None, /):
        file = file or self._DEFAULT_FILE
        writer = writer or self._WRITER

        if writer is None:
            raise ValueError("no writer specified")
        if file is None:
            raise Exception("No file specified")

        writer.dump(file, self)

    def reset(self):
        """This does not work on auto loaded config"""
        if not self._has_default:
            raise Exception("Configuration does not have a full default value")
        self._value = {
            self._FIELD_NAME_MAP[name]: self._ALL_FIELDS[self._FIELD_NAME_MAP[name]](
                val
            )
            for name, val in self._default_value.items()
        }

    @classmethod
    def reset_global(cls):
        """reset config on auto loaded config"""
        if cls._INST is None:
            return

        if not cls._has_default:
            raise Exception("Configuration does not have a full default value")
        cls._INST._value = {
            cls._FIELD_NAME_MAP[name]: cls._ALL_FIELDS[cls._FIELD_NAME_MAP[name]](val)
            for name, val in cls._default_value.items()
        }


__all__ = [
    "ConfigSpec",
    "_ConfigSpecMeta",
    "_ConfigSpecABCMeta",
    "spec",
    "configio",
    "JsonWriter",
    "TomlWriter",
]
