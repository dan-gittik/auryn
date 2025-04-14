from auryn import render, transpile


template = '''
%load filesystem
%d('{project_name}', source='08b_project-template', render=True)
    %d {project_name}
        %f __init__.py
    %d tests
'''
print(transpile(template))
render(template, project_name='proj')
print('=' * 80)

print(transpile('''
%load filesystem
%d static_name
    %d {dynamic_name}
        %f {dynamic}-{name}.py
            {dynamic} {content}!
'''))