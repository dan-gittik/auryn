from auryn import render, transpile


print(transpile('''
%load filesystem
%x('grep -rl {directory} {regex} | uniq', into='files')
!for file in files.splitlines():
    %x cp {file} .
'''))
