import json
from . import configio
from . import spec


class JsonWriter(configio.ConfigurationWriter):
    @classmethod
    def dump_section(cls, node: spec.Section):
        return {
            node._FIELD_VAR_MAP[name]: (
                cls.dump_value(node.get_field(name), value)
            )
            for name, value in node._value.items()
        }
    
    @classmethod
    def dump_value(cls, node: spec.AnyConfigField, value):
        match node:
            case type() | spec.Section():
                return cls.dump_section(value)
            case spec.Table(_, type() | spec.Section() | spec.ConfigUnion()):
                return {cls.dump_value(key, key): cls.dump_value(val, val) for key, val in value.items()}
            case _:
                return value

    @classmethod
    def dumps(cls, node) -> str:
        match node:
            case spec.Section():
                return json.dumps(cls.dump_section(node), indent=4)
            case _:
                raise ValueError(node)

    @classmethod
    def dump(cls, file, node):
        super().dump(file, node)

    @classmethod
    def load(cls, file):
        if isinstance(file, str):
            with open(file, "r") as f:
                return json.load(f)
        return json.load(file)

    # just alias the name
    loads = json.loads
