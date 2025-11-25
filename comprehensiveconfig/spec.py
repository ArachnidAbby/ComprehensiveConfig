from abc import ABC, abstractmethod
import re
from types import NoneType
from typing import Any, Self, Type, TypedDict


class _NoDefaultValueT:
    """Represents not having a default value.
    Cannot be instantiated normally"""

    @classmethod
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError()


# instantiate _NoDefaultValueT using object class's __new__ method
NoDefaultValue = object.__new__(_NoDefaultValueT)


class BaseConfigurationField(ABC):
    """The base class for a configuration field"""

    __slots__ = (
        "_field_variable",
        "_parent",
    )

    _parent: Type[Self] | None
    """The parent to this node"""

    _field_variable: None | str
    """The python variable that this field is attached to"""

    def __call__[T](self, value: T) -> T:
        self._validate_value(value)
        return value

    @abstractmethod
    def _validate_value(self, value: Any):
        raise ValueError(value)


class ConfigurationField(BaseConfigurationField):
    """The base class for a configuration field"""

    __slots__ = ("_name", "_default_value", "_has_default", "_nullable")

    _name: None | str
    """The actual name used inside the configuration
    This has to be valid for whatever config format you use"""
    _default_value: Any | _NoDefaultValueT
    _has_default: bool
    _nullable: bool
    """is this value nullable"""

    def __init__(
        self,
        default_value: Any = NoDefaultValue,
        /,
        name: str | None = None,
        nullable: bool = False,
    ):
        self._name = name
        self._nullable = nullable
        self._field_variable = None
        self._default_value = default_value
        self._has_default = default_value is not NoDefaultValue

    @abstractmethod
    def _validate_value(self, value: Any):
        if value is None and not self._nullable:
            raise ValueError(f'Field, "{self._name}", is not nullable')


type AnyConfigField = ConfigurationField | BaseConfigurationField


class Section(BaseConfigurationField):
    """A baseclass for sections to be defined"""

    __slots__ = "_value"

    _FIELDS: dict[str, AnyConfigField]
    _SECTIONS: dict[str, Type]
    _ALL_FIELDS: dict[str, AnyConfigField | Type]
    _FIELD_NAME_MAP: dict[str, str]
    """Maps config names to their actual variable names"""
    _FIELD_VAR_MAP: dict[str, str]
    """Maps variable names to their actual config names"""
    _name: str
    """The actual name in the configuration file"""
    _has_default: bool
    _default_value: dict[str, Any] | _NoDefaultValueT
    _parent: AnyConfigField | None

    @classmethod
    def __init_subclass__(cls, name: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._parent = None
        cls._name = name or cls.__name__
        cls._FIELDS = {
            field_name: field
            for field_name, field in cls.__dict__.items()
            if isinstance(field, ConfigurationField)
        }
        cls._SECTIONS = {
            field_name: field
            for field_name, field in cls.__dict__.items()
            if isinstance(field, type) and Section in field.__mro__
        }
        cls._ALL_FIELDS = cls._FIELDS | cls._SECTIONS
        for name, field in cls._ALL_FIELDS.items():
            field._field_variable = name
            if field._name is None:
                field._name = name
            if isinstance(field, type):
                field._parent = cls

        cls._FIELD_NAME_MAP = {
            field._name: variable
            for variable, field in cls._ALL_FIELDS.items()
            if field._name is not None
        }

        cls._FIELD_VAR_MAP = {value: key for key, value in cls._FIELD_NAME_MAP.items()}

        # generate default value
        cls._has_default = all(field._has_default for field in cls._ALL_FIELDS.values())
        if cls._has_default:
            cls._default_value = {
                field._name: field._default_value for field in cls._ALL_FIELDS.values()
            }
        else:
            cls._default_value = NoDefaultValue

    def __init__(self, value: dict[str, Any] | _NoDefaultValueT):
        if value is NoDefaultValue:
            raise ValueError(value)
        self._validate_value(value)
        self._value = {
            self._FIELD_NAME_MAP[name]: self._ALL_FIELDS[self._FIELD_NAME_MAP[name]](
                val
            )
            for name, val in value.items()
        }

    def __call__[T](self, value: T) -> T:
        raise NotImplementedError()

    def __getattribute__(self, name: str) -> Any:
        if name in object.__getattribute__(self, "_ALL_FIELDS").keys():
            return object.__getattribute__(self, "_value")[name]
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value: Any) -> None:
        fields = object.__getattribute__(self, "_ALL_FIELDS")
        if name in fields.keys():
            object.__getattribute__(self, "_value")[name] = fields[name](value)
        else:
            super().__setattr__(name, value)

    @classmethod
    def _validate_value(cls, value: Any):
        if not isinstance(value, dict):
            raise ValueError(value)
        for field in cls._ALL_FIELDS.values():
            if field._name not in value.keys():
                raise KeyError(
                    f'Section, "{cls._name}", missing field: {field._name}'
                )  # missing key
            field._validate_value(value[field._name])

    @property
    def nullable(self):
        return False


class Float(ConfigurationField):
    """Floating point field"""

    __slots__ = ()

    @classmethod
    def __new__(cls, *args, **kwargs) -> float:  # type: ignore
        return super().__new__(cls)  # type: ignore

    def _validate_value(self, value: Any):
        super()._validate_value(value)
        if not isinstance(value, (float, int)):
            raise ValueError(
                f"Field: {self._name}\nValue was not a valid number: {value}"
            )


class List[T](ConfigurationField):
    """List field"""

    __slots__ = "inner_type"

    @classmethod
    def __new__(cls, default_value: list[T] = [], /, *args, **kwargs) -> list[T]:  # type: ignore
        return super().__new__(cls)  # type: ignore

    def __init__(
        self,
        default_value: list[T] = [],
        /,
        inner_type: ConfigurationField | None | Any = None,
        *args,
        **kwargs,
    ):
        self.inner_type = inner_type

        return super().__init__(default_value, *args, **kwargs)

    def _validate_value(self, value: Any):
        super()._validate_value(value)
        if not isinstance(value, list):
            raise ValueError(
                f"Field: {self._name}\nValue was not a valid list: {value}"
            )

        match self.inner_type:
            case None:
                return
            case type():
                raise ValueError(self.inner_type)

            case BaseConfigurationField():
                for c, item in enumerate(value):
                    self.inner_type._name = f"{self._name}[{c}]"
                    self.inner_type._validate_value(item)


class TableSpec(ConfigurationField):
    """A model/Table"""

    __slots__ = ()

    _FIELDS: dict[str, AnyConfigField]
    _SECTIONS: dict[str, Type]
    _ALL_FIELDS: dict[str, AnyConfigField | Type]
    _FIELD_NAME_MAP: dict[str, str]
    """Maps config names to their actual variable names"""
    _FIELD_VAR_MAP: dict[str, str]
    """Maps variable names to their actual config names"""
    _cls_name: str
    """The actual name in the configuration file"""
    _cls_has_default: bool
    _cls_default_value: dict[str, Any] | _NoDefaultValueT
    _default_value: dict[str, Any] | _NoDefaultValueT

    @classmethod
    def __init_subclass__(cls, name: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._cls_name = name or cls.__name__
        cls._FIELDS = {
            field_name: field
            for field_name, field in cls.__dict__.items()
            if isinstance(field, ConfigurationField)
        }
        cls._SECTIONS = {
            field_name: field
            for field_name, field in cls.__dict__.items()
            if isinstance(field, type) and Section in field.__mro__
        }
        cls._ALL_FIELDS = cls._FIELDS | cls._SECTIONS
        for name, field in cls._ALL_FIELDS.items():
            field._field_variable = name
            if field._name is None:
                field._name = name
            if isinstance(field, type):
                field._parent = cls

        cls._FIELD_NAME_MAP = {
            field._name: variable
            for variable, field in cls._ALL_FIELDS.items()
            if field._name is not None
        }

        cls._FIELD_VAR_MAP = {value: key for key, value in cls._FIELD_NAME_MAP.items()}

        # generate default value
        cls._cls_has_default = all(
            field._has_default for field in cls._ALL_FIELDS.values()
        )
        if cls._cls_has_default:
            cls._cls_default_value = {
                field._name: field._default_value for field in cls._ALL_FIELDS.values()
            }
        else:
            cls._cls_default_value = NoDefaultValue

    @classmethod
    def __new__(cls, default_value: dict[str, Any] | _NoDefaultValueT = NoDefaultValue, /, *args, **kwargs) -> dict[str, Any]:  # type: ignore
        return super().__new__(cls)  # type: ignore

    def __init__(
        self,
        default_value: dict[str, Any] | _NoDefaultValueT = NoDefaultValue,
        /,
        *args,
        **kwargs,
    ):
        if default_value is NoDefaultValue:
            default_value = self._cls_default_value
        super().__init__(default_value, *args, **kwargs)

    def _validate_value(self, value: Any):
        if not isinstance(value, dict):
            raise ValueError(value)
        for field in self._ALL_FIELDS.values():
            if field._name not in value.keys():
                raise KeyError(
                    f'Section, "{self._name}", missing field: {field._name}'
                )  # missing key
            field._validate_value(value[field._name])


class Table[K, V](ConfigurationField):
    """A generic Table"""

    __slots__ = ("key_type", "value_type")

    @classmethod
    def __new__(cls, default_value: dict[K, V] | _NoDefaultValueT = NoDefaultValue, /, *args, **kwargs) -> dict[K, V]:  # type: ignore
        return super().__new__(cls)  # type: ignore

    def __init__(
        self,
        default_value: Any = NoDefaultValue,
        /,
        key_type: AnyConfigField | None | Any = None,
        value_type: AnyConfigField | None | Any = None,
        *args,
        **kwargs,
    ):
        self.key_type = key_type
        self.value_type = value_type

        return super().__init__(default_value, *args, **kwargs)

    def _validate_value(self, value: Any):
        super()._validate_value(value)
        if not isinstance(value, dict):
            raise ValueError(
                f"Field: {self._name}\nValue was not a valid dict: {value}"
            )

        if self.key_type is not None:
            for c, key in enumerate(value.keys()):
                self.key_type._name = f"{self._name}[{key}] (keyname)"
                self.key_type._validate_value(key)

        if self.value_type is not None:
            for key, val in value.items():
                self.value_type._name = f"{self._name}[{key}] (value)"
                self.value_type._validate_value(val)


class Integer(ConfigurationField):
    """integer field"""

    __slots__ = ()

    @classmethod
    def __new__(cls, *args, **kwargs) -> float:  # type: ignore
        return super().__new__(cls)  # type: ignore

    def _validate_value(self, value: Any):
        super()._validate_value(value)
        if not isinstance(value, int):
            raise ValueError(
                f"Field: {self._name}\nValue was not a valid integer: {value}"
            )


type Number = Float
"""More generic number field, just an alias for Float"""


class Text(ConfigurationField):
    """string field (with optional regex validation)"""

    __slots__ = "_regex_pattern"

    @classmethod
    def __new__(cls, *args, **kwargs) -> str:  # type: ignore
        return super().__new__(cls)  # type: ignore

    def __init__(
        self, default_value=NoDefaultValue, /, *args, regex: str = r".*", **kwargs
    ):
        super().__init__(default_value, *args, **kwargs)
        self._regex_pattern = regex

    def _validate_value(self, value: Any):
        super()._validate_value(value)
        if not isinstance(value, str):
            raise ValueError(
                f"Field: {self._name}\nValue was not a valid string: {value}"
            )
        if re.fullmatch(self._regex_pattern, value) is None:
            raise ValueError(
                f'Field: {self._name}\n"{value}" did not match regex pattern: {self._regex_pattern}'
            )


__all__ = [
    "ConfigurationField",
    "NoDefaultValue",
    "_NoDefaultValueT",
    "Section",
    "Float",
    "Integer",
    "Number",
    "Text",
    "Table",
    "TableSpec",
    "List",
]
