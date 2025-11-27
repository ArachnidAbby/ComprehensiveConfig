import tomllib
from . import configio
from . import spec


def escape(value):
    return value.translate(
        str.maketrans(
            {
                "\n": "\\n",
                "\t": "\\t",
                "\r": "\\r",
                '"': '\\"',
                "'": "\\'",
            }
        )
    )


def full_section_name(node) -> list[str]:
    if node._parent is None:
        return [node._name]
    return [*full_section_name(node._parent), node._name]


class TomlWriter(configio.ConfigurationWriter):
    @classmethod
    def dump_section(cls, node) -> list:
        if " " in node._name:
            raise ValueError(node._name)

        if node._parent is not None:
            base = [f"\n[{'.'.join(full_section_name(node)[1:])}]"]
        else:
            base = []

        if node.__doc__:
            base.append(f"# {node.__doc__}")

        return [
            *base,
            *(
                (
                    "\n".join(cls.dump_section(value))
                    if isinstance(value, spec.Section)
                    else cls.dump_field(node, name, node._FIELD_VAR_MAP[name], value)
                )
                for name, value in node._value.items()
            ),
        ]

    @classmethod
    def format_value(cls, value):
        match value:
            case int() | float():
                return str(value)
            case str():
                return f'"{escape(value)}"'
            case list():
                return f"[{", ".join([str(cls.format_value(inner_val)) for inner_val in value])}]"
            case dict():
                return f"{{ {", ".join([f"{key} = {cls.format_value(inner_val)}" for key, inner_val in value.items()])} }}"
            case _:
                raise ValueError(value)

    @classmethod
    def dump_field(cls, node: spec.AnyConfigField, original_name: str, field_name: str, value) -> str:
        if isinstance(node, spec.Section):
            field = node.get_field(original_name)
        else:
            field = node
        match field:
            case spec.Table(spec.Text(), type() | spec.ConfigUnion()) as table_node:
                for name, val in value.items():
                    if not isinstance(val, spec.Section):
                        continue
                    val._name = name
                    val._parent = table_node
                
                section_name = '.'.join(full_section_name(table_node)[1:])

                return f"\n[{section_name}]\n{"\n".join(cls.dumps(val) if isinstance(val, spec.Section) else cls.dump_field(val, key, key, val) for key, val in value.items())}"
            case spec.Section():
                return "\n".join(cls.dump_section(node))
            case _:
                if isinstance(value, spec.Section):
                    return "\n".join(cls.dump_section(value))
                return f"{field_name} = {cls.format_value(value)}"

    @classmethod
    def dumps(cls, node) -> str:
        match node:
            case spec.Section():
                return "\n".join(cls.dump_section(node))
            
            case _:
                raise ValueError(node)

    @classmethod
    def dump(cls, file, node):
        super().dump(file, node)

    @classmethod
    def load(cls, file):
        if isinstance(file, str):
            with open(file, "rb") as f:
                return tomllib.load(f)
        return tomllib.load(file)

    # just alias the name
    loads = tomllib.loads
