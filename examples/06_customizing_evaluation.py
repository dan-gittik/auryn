from auryn import Junk, render, transpile

print(render('''
this is printed
%stop
this is not
'''))
print('=' * 80)
print(render('''
%param('n', 3)
!for i in range(n):
    line {i}
'''))

junk = Junk.from_string('''
%param n
!for i in range(n):
    line {i}
''')
print(junk.transpile())
print(junk.meta_state.get('parameters'))
print('=' * 80)

template = '''
!for table_name, table in tables.items():
    class {camel_case(table_name)}(Base):
        __tablename__ = '{table_name}'
        !for column_name, column in table['columns'].items():
            %inline
                {column_name} = Column(
                    column['type'], 
                    !if column.get('primary_key'):
                        primary_key=True, 
                    !if column.get('nullable'):
                        nullable=True, 
                    %strip ,
                )
'''
tables = {'user': {
    'columns': {
        'id': {'type': 'Integer', 'primary_key': True},
        'username': {'type': 'String'},
        'password': {'type': 'Integer', 'nullable': True},
    },
}}
print(transpile(template))
print('=' * 80)
print(render(template, tables=tables))
