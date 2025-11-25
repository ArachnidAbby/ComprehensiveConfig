import json
from . import configio
from . import spec


class JsonWriter(configio.ConfigurationWriter):
    @classmethod
    def dump_section(cls, node):
        return {
            node._FIELD_VAR_MAP[name]: (
                cls.dump_section(value) if isinstance(value, spec.Section) else value
            )
            for name, value in node._value.items()
        }

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
