from comprehensiveconfig import ConfigSpec
from comprehensiveconfig.spec import TableSpec, Section, Integer, Float, Text, List
from comprehensiveconfig.json import JsonWriter
from comprehensiveconfig.toml import TomlWriter


class Example(TableSpec):
    x = Integer(10)

class MyConfigSpec(ConfigSpec,
                   default_file="test.toml",
                   writer=TomlWriter,
                   create_file=True):
    class MySection(Section, name="Funny_Section"):
        some_field = Integer(10)
        other_field = Text("Some Default Text")

        class SubSection(Section):
            x = Integer(10)

    class Credentials(Section):
        email = Text("example@email.com", regex=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
        password = Text("MyPassword")

    some_field = Float(6.9)
    example_list_field = List(["12", "13", "14"], inner_type=Text())
    model_example = Example()
    list_of_models = List([{"x": 12}, {"x": 12}], inner_type=Example())


print(MyConfigSpec.some_field)
print(MyConfigSpec.MySection.other_field)

MyConfigSpec.some_field = 12.2
print(MyConfigSpec.some_field)
print(MyConfigSpec.MySection.other_field)


# MyConfigSpec.reset_global()
print(MyConfigSpec.some_field)
print(MyConfigSpec.MySection.other_field)