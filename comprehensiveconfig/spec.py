from abc import ABC, ABCMeta, abstractmethod
import re
from types import UnionType
import types
from typing import Any, Self, Type, Union
import typing


class _NoDefaultValueT:
    """Represents not having a default value.
    Cannot be instantiated normally"""

    @classmethod
    def __new__(cls, *args, **kwargs):
        raise NotImplementedError()


# instantiate _NoDefaultValueT using object class's __new__ method
NoDefaultValue = object.__new__(_NoDefaultValueT)


class ConfigurationFieldMeta[C](type):
    """Provides custom union logic for configuration fields"""

    @classmethod
    def __new__(cls: Type[C], *args, **kwargs) -> Type[C]:  # type: ignore
        return super().__new__(*args, **kwargs)

    def __or__[S, T](self: S, value: Type[T] | T) -> S | Type[T]:
        """broaden normal"""
        if not isinstance(value, type) and not isinstance(
            value, BaseConfigurationField
        ):
            raise TypeError()
        return Union[self, value]


def fix_unions(union: UnionType | Any) -> "ConfigUnion | BaseConfigurationField":
    if not isinstance(union, (typing._UnionGenericAlias, types.UnionType)):
        return union
    left, *right = union.__args__
    output = left
    for typ in right:
        output = ConfigUnion(output, typ)
    return output


class ConfigurationFieldABCMeta(ABCMeta, ConfigurationFieldMeta):
    pass


class BaseConfigurationField(ABC):
    """The base class for a configuration field"""

    __slots__ = ("_field_variable", "_parent", "_value")

    _parent: Type[Self] | None
    """The parent to this node"""

    _field_variable: None | str
    """The python variable that this field is attached to"""

    def __call__[T](self, value: T) -> T:
        self._validate_value(value)
        return value

    @abstractmethod
    def _validate_value(self, value: Any, name: str | None = None, /):
        raise ValueError(value)


class ConfigurationField[T](BaseConfigurationField):
    """The base class for a configuration field"""

    __slots__ = ("_name", "_default_value", "_has_default", "_nullable")

    _name: None | str
    """The actual name used inside the configuration
    This has to be valid for whatever config format you use"""
    _default_value: T | _NoDefaultValueT
    _has_default: bool
    _nullable: bool
    """is this value nullable"""

    _holds: T
    """describes what type this field holds"""

    def __init__(
        self,
        default_value: T | _NoDefaultValueT = NoDefaultValue,
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
    def _validate_value(self, value: Any, name: str | None = None, /):
        if value is None and not self._nullable:
            raise ValueError(f'Field, "{name or self._name}", is not nullable')

    def __or__(self, value: "type | AnyConfigField") -> "ConfigUnion":
        return ConfigUnion(self, value)

    def __set_name__(self, owner, name):
        # Automatically set the internal storage name (e.g., _age)
        self._field_variable = name
        if self._name is None:
            self._name = name

    def __get__(self, instance, owner) -> T:
        if instance is None:
            return self
        # Retrieve the value from the instance's dictionary
        return instance._value[self._field_variable]

    def __set__(self, instance, value: T):
        instance._value[self._field_variable] = value


type AnyConfigField = ConfigurationField | BaseConfigurationField | UnionType | typing._GenericUnionAlias


# TODO: Remove duplication of these kinds of descriptors
class SectionName:
    """Descriptor for section names.
    Chooses between class name and instance name automatically"""

    def __get__(self, instance, owner):
        if instance is None:
            return object.__getattribute__(owner, "_cls_name")
        return object.__getattribute__(instance, "_instance_name")

    def __set__(self, instance, value):
        instance._instance_name = value


class SectionParent:
    """Descriptor for section parents.
    Chooses between class parent and instance parent automatically"""

    def __get__(self, instance, owner):
        if instance is None:
            return object.__getattribute__(owner, "_cls_parent")
        return object.__getattribute__(instance, "_instance_parent")

    def __set__(self, instance, value):
        instance._instance_parent = value


class Section(BaseConfigurationField, metaclass=ConfigurationFieldABCMeta):
    """A baseclass for sections to be defined"""

    __slots__ = "_value"

    _FIELDS: dict[str, AnyConfigField]
    _SECTIONS: dict[str, Type]
    _ALL_FIELDS: dict[str, AnyConfigField | Type]
    _FIELD_NAME_MAP: dict[str, str]
    """Maps config names to their actual variable names"""
    _FIELD_VAR_MAP: dict[str, str]
    """Maps variable names to their actual config names"""
    _name = SectionName()
    """The name in the configuration file (chooses between _real_name and _cls_name)"""
    _cls_name: str
    """The name of the class"""
    _instance_name: str
    """The actual name in the configuration file"""
    _has_default: bool
    _default_value: dict[str, Any] | _NoDefaultValueT
    _parent = SectionParent()
    _instance_parent: AnyConfigField | None
    _cls_parent: AnyConfigField | None


    @classmethod
    def __init_subclass__(cls, name: str | None = None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._cls_parent = None
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
                field._cls_parent = cls
            else:
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

    def __init__(
        self,
        value: dict[str, Any] | _NoDefaultValueT = NoDefaultValue,
        /,
        **kwargs: Any,
    ):
        self._name = self._cls_name
        self._parent = self._cls_parent
        if isinstance(value, _NoDefaultValueT):
            value = {}
        if not isinstance(value, (dict, Section)):
            raise ValueError(value)
        value = value | kwargs
        self._validate_value(value)
        self._value = {
            self._FIELD_NAME_MAP[name]: self._ALL_FIELDS[self._FIELD_NAME_MAP[name]](
                val
            )
            for name, val in value.items()
        }

    def __get__(self, instance, owner):
        if instance is None:
            return self
        # Retrieve the value from the instance's dictionary
        return instance._value[self._field_variable]

    def __call__[T](self, value: T) -> T:
        raise NotImplementedError()

    def get_field(self, name):
        return object.__getattribute__(self.__class__, name)

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

    def __getitem__(self, name):
        return self._value[self._FIELD_VAR_MAP[name]]

    def keys(self):
        return self._value.keys()

    def items(self):
        return self._value.items()

    def values(self):
        return self._value.values()

    def __or__(self, other: dict) -> Self:
        return self.__class__(
            {self._FIELD_NAME_MAP[key]: value for key, value in self._value.items()}
            | other
        )

    @classmethod
    def _validate_value(cls, value: Any, name: str | None = None, /):
        if not isinstance(value, (dict, cls)):
            raise ValueError(value)
        for field in cls._ALL_FIELDS.values():
            if field._name not in value.keys():
                raise KeyError(
                    f'Section, "{name or cls._name}", missing field: {field._name}'
                )  # missing key
            field._validate_value(
                value[field._name], f"{name or cls._name}.{field._name}"
            )

    @property
    def nullable(self):
        return False


class Float(ConfigurationField):
    """Floating point field"""

    __slots__ = ()

    _holds: float

    # @classmethod
    # def __new__(cls, *args, **kwargs) -> float:  # type: ignore
    #     return super().__new__(cls)  # type: ignore

    def __get__(self, instance, owner) -> float:
        return super().__get__(instance, owner)

    def __set__(self, instance, value: float):
        super().__set__(instance, value)

    def _validate_value(self, value: Any, name: str | None = None, /):
        super()._validate_value(value)
        if not isinstance(value, (float, int)):
            raise ValueError(
                f"Field: {name or self._name}\nValue was not a valid number: {repr(value)}"
            )


class List[T](ConfigurationField):
    """List field"""

    __slots__ = "inner_type"

    _holds: list[T]

    # @classmethod
    # def __new__(cls, default_value: list[T] = [], /, *args, **kwargs) -> list[T]:  # type: ignore
    #     return super().__new__(cls)  # type: ignore

    def __init__(
        self,
        default_value: list[T] = [],
        /,
        inner_type: AnyConfigField | None = None,
        *args,
        **kwargs,
    ):
        self.inner_type = fix_unions(inner_type)

        return super().__init__(default_value, *args, **kwargs)
    
    def __call__(self, value: list[T]) -> list[T]:
        return [self.inner_type(val) for val in value]
    
    def __get__(self, instance, owner) -> list[T]:
        return super().__get__(instance, owner)

    def __set__(self, instance, value: list[T]):
        super().__set__(instance, value)

    def _validate_value(self, value: Any, name: str | None = None, /):
        super()._validate_value(value)
        if not isinstance(value, list):
            raise ValueError(
                f"Field: {name or self._name}\nValue was not a valid list: {value}"
            )

        match self.inner_type:
            case None:
                return
            case type():
                raise ValueError(self.inner_type)

            case BaseConfigurationField():
                for c, item in enumerate(value):
                    self.inner_type._validate_value(item, f"{name or self._name}[{c}]")


class TableSpec(ConfigurationField, metaclass=ConfigurationFieldABCMeta):
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

    _holds: dict[str, Any]

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

    def _validate_value(self, value: Any, name: str | None = None, /):
        if not isinstance(value, dict):
            raise ValueError(value)
        for field in self._ALL_FIELDS.values():
            if field._name not in value.keys():
                raise KeyError(
                    f'Table, "{name or self._name}", missing field: {field._name}'
                )  # missing key
            field._validate_value(value[field._name])


class Table[K, V](ConfigurationField):
    """A generic Table"""

    __slots__ = ("key_type", "value_type")
    __match_args__ = ("key_type", "value_type")

    _holds: dict[K, V]

    # @classmethod
    # def __new__(cls, default_value: dict[K, V] | _NoDefaultValueT = NoDefaultValue, /, *args, **kwargs) -> dict[K, V]:  # type: ignore
    #     return super().__new__(cls)  # type: ignore

    def __init__(
        self,
        default_value: Any = NoDefaultValue,
        /,
        key_type: AnyConfigField | None = None,
        value_type: AnyConfigField | None = None,
        *args,
        **kwargs,
    ):
        self.key_type = fix_unions(key_type)
        self.value_type = fix_unions(value_type)

        return super().__init__(default_value, *args, **kwargs)

    def __call__(self, value: dict[K, V]) -> dict[K, V]:
        return {self.key_type(key): self.value_type(val) for key, val in value.items()}
    
    def __get__(self, instance, owner) -> dict[K, V]:
        return super().__get__(instance, owner)

    def __set__(self, instance, value: dict[K, V]):
        super().__set__(instance, value)

    def _validate_value(self, value: Any, name: str | None = None, /):
        super()._validate_value(value)
        if not isinstance(value, dict):
            raise ValueError(
                f"Field: {name or self._name}\nValue was not a valid dict: {value}"
            )

        if self.key_type is not None:
            for c, key in enumerate(value.keys()):
                self.key_type._validate_value(
                    key, f"{name or self._name}[{key}] (keyname)"
                )

        if self.value_type is not None:
            for key, val in value.items():
                self.value_type._validate_value(
                    val, f"{name or self._name}[{key}] (value)"
                )


class Integer(ConfigurationField):
    """integer field"""

    __slots__ = ()

    _holds: int

    def __get__(self, instance, owner) -> int:
        return super().__get__(instance, owner)

    def __set__(self, instance, value: int):
        super().__set__(instance, value)

    def _validate_value(self, value: Any, name: str | None = None, /):
        super()._validate_value(value)
        if not isinstance(value, int):
            raise ValueError(
                f"Field: {name or self._name}\nValue was not a valid integer: {repr(value)}"
            )


type Number = Float
"""More generic number field, just an alias for Float"""


class Text(ConfigurationField):
    """string field (with optional regex validation)"""

    __slots__ = "_regex_pattern"

    _holds: str

    # @classmethod
    # def __new__(cls, *args, **kwargs) -> str:  # type: ignore
    #     return super().__new__(cls)  # type: ignore

    def __init__(
        self,
        default_value: str | _NoDefaultValueT = NoDefaultValue,
        /,
        *args,
        regex: str = r".*",
        **kwargs,
    ):
        super().__init__(default_value, *args, **kwargs)
        self._regex_pattern = regex

    def __get__(self, instance, owner) -> str:
        return super().__get__(instance, owner)

    def __set__(self, instance, value: str):
        super().__set__(instance, value)

    def _validate_value(self, value: Any, name: str | None = None, /):
        super()._validate_value(value)
        if not isinstance(value, str):
            raise ValueError(
                f"Field: {name or self._name}\nValue was not a valid string: {value}"
            )
        if re.fullmatch(self._regex_pattern, value) is None:
            raise ValueError(
                f'Field: {name or self._name}\n"{value}" did not match regex pattern: {self._regex_pattern}'
            )


class ConfigUnion[L, R](ConfigurationField):
    """union field"""

    __slots__ = ("_left_type", "_right_type")

    _holds: L | R

    _left_type: AnyConfigField | Type
    _right_type: AnyConfigField | Type

    # @classmethod
    # def __new__(cls, *args, **kwargs) -> L | R:  # type: ignore
    #     return super().__new__(cls)  # type: ignore

    def __init__(
        self,
        left_type: AnyConfigField | Type,
        right_type: AnyConfigField | Type,
        *args,
        **kwargs,
    ):
        super().__init__(NoDefaultValue, *args, **kwargs)
        self._left_type = fix_unions(left_type)
        self._right_type = fix_unions(right_type)

    def __call__(self, *args, **kwargs):
        try:
            return self._left_type(*args, **kwargs)
        except ValueError:  # if left side fails, try the right
            return self._right_type(*args, **kwargs)
    
    def __get__(self, instance, owner) -> L | R:
        return super().__get__(instance, owner)

    def __set__(self, instance, value: L | R):
        super().__set__(instance, value)

    def _validate_value(self, value: L | R, name: str | None = None, /):
        super()._validate_value(value)
        try:
            self._left_type._validate_value(value, name)
        except ValueError:  # if left side fails, try the right
            self._right_type._validate_value(value, name)


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
