from auryn import render, transpile


template = '''
%load filesystem
%d {project_name}
    %f pyproject.toml
        [tool.poetry]
        name = "{project_name}"
        version = "0.1.0"
        description = ""
        readme = "README.md"
        [build-system]
        requires = ["poetry-core"]
        build-backend = "poetry.core.masonry.api"
    %f README.md
        # {project_name.title()}
    %d {project_name}
        %f __init__.py
    %d tests
'''
print(transpile(template))
render(template, project_name='proj')
