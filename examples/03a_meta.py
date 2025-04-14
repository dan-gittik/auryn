from auryn import render, transpile


def hello(junk, target):
    print('hello', target)
    junk.transpile(junk.line.children.align(junk.line.indent))


print(transpile('''
%hello('world')
    !for i in range(n):
        line {i}
''', load={'meta_hello': hello}))
print('=' * 80)

print(render('''
!n = 3
%include 03b_loop.template
'''))
print('=' * 80)

print(render('''
!n = 3
lines:
    %include 03b_loop.template
'''))
print('=' * 80)

print(render('03d_index.template'))