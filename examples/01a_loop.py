from auryn import render, transpile


template = '''
!for i in range(n):
    line {i}
'''
print(transpile(template))
print('=' * 80)
print(render(template, n=3))
print('=' * 80)
print(transpile('01b_loop.template'))
print('=' * 80)
print(render('01b_loop.template', n=3))
