from comprehensiveconfig import ConfigSpec
from comprehensiveconfig.json import JsonWriter
from comprehensiveconfig.spec import (
    Table,
    TableSpec,
    Section,
    Integer,
    Float,
    Text,
    List,
)
from comprehensiveconfig.toml import TomlWriter


class Example(TableSpec):
    x = Integer(10)


class MyConfigSpec(ConfigSpec,
                   default_file="test.toml",
                   writer=TomlWriter,
                   create_file=True):
    class MySection(Section, name="Funny_Section"):
        """Example comment under section"""

        some_field = Integer(10)
        other_field = Text("Some Default Text")

        class SubSection(Section):
            x = Integer(10)

    class Credentials(Section, name="Credentials"):
        email = Text(
            "example@email.com",
            regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        )
        password = Text("MyPassword")

    some_field = Float(6.9)
    example_list_field = List(
        ["12", "13", "14", 22], inner_type=Text(regex=r"[0-9]*") | Integer()
    )
    model_example = Example()
    list_of_models = List([{"x": 12}, {"x": 12}], inner_type=Example())
    list_of_sections: Table[str, Credentials | int] = Table(
        {"google_creds": Credentials(email="example@email.com", password="passwd")},
        key_type=Text(),
        value_type=Credentials | Integer(),
    )


print(MyConfigSpec.some_field)
print(MyConfigSpec.MySection.other_field)
MyConfigSpec.some_field = 12.2
print(MyConfigSpec.some_field)
print(MyConfigSpec.MySection.other_field)

# print(MyConfigSpec.list_of_sections)

x = MyConfigSpec.load("test.toml", TomlWriter)
print(x.MySection.some_field)

x.some_field = 12
p = x.some_field
j = x.MySection.other_field

# MyConfigSpec.reset_global()
print(MyConfigSpec.some_field)
print(MyConfigSpec.MySection.other_field)
MyConfigSpec._INST.save("test.toml", TomlWriter)
MyConfigSpec._INST.save("test.json", JsonWriter)
