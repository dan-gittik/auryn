from auryn import render, transpile


print(transpile('''
%interpolate < >
    !for i in range(n):
        line <i>
back to {i}
'''))
print('=' * 80)

print(transpile('''
%interpolate {% %}
!for i in range(n):
     line {% i %}
never {i} again
'''))
print('=' * 80)

print(transpile('''
%raw
    !for i in range(n):
        line {i}
'''))
print('=' * 80)

print(render('''
%raw
!for i in range(n):
    line {i}
'''))