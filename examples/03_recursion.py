import json

import auryn


output = auryn.execute("""
    %include 03a_typechecking.aur
    def validate(
        !for key in model:
            {key},
    ):
        !for key, value in model.items():
            !check_types(key, value)
""", model=json.load(open("03b_model.json")))
print(output)