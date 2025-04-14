import pathlib
from auryn import transpile, evaluate


print(transpile('''
%load filesystem
%d dir
''', standalone=True))
print('=' * 80)

print(transpile('''
%load filesystem
%f file
''', standalone=True))
print('=' * 80)

print(transpile('''
%load filesystem
%f file
''', standalone=True))
print('=' * 80)

code = transpile('''
%load filesystem
%d dir
    %f file
''', standalone=True)
print(code)
path = pathlib.Path(__file__).parent /'standalone.py'
with open(path, 'w') as f:
    f.write(code)
print(evaluate(path))


