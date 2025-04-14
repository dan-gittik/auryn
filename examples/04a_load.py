from auryn import render


def meta_hello(junk):
    print('Hello, world!')


render('''
%load 04b_greetings.py
%hello
''')
print('=' * 80)

render('''
%include 03b_loop.template
%hello
''', load=globals(), n=3)
print('=' * 80)
