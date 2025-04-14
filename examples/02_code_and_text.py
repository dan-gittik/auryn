from auryn import render, transpile


model = {
    'n': {
        'type': 'integer',
        'min': 1,
        'max': 10,
    },
    'p': {
        'type': 'object',
        'attributes': {
            'x': {
                'type': 'integer',
            },
            'y': {
                'type': 'integer',
            },
        },
    },
}
template = '''
    !def check_integer(name, min=None, max=None):
        if not isinstance({name}, int):
            raise ValueError(f'expected {{{name}=}} to be an integer')
        !if min is not None:
            if {name} < {min}:
                raise ValueError(f'expected {{{name}=}} >= {min}')
        !if max is not None:
            if {name} > {min}:
                raise ValueError(f'expected {{{name}=}} <= {max}')
    !def check_types(name, config):
        !if config['type'] == 'integer':
            !check_integer(name, config.get('min'), config.get('max'))
        !if config['type'] == 'object':
            if not isinstance({name}, object):
                raise ValueError(f'expected {{{name}=}} to be an object')
            !for key, value in config['attributes'].items():
                !check_types(f'{name}.{key}', value)
    def validate(
        !for key in model:
            {key},
    ):
        !for key, value in model.items():
            !check_types(key, value)
'''
print(transpile(template))
print('=' * 80)
print(render(template, model=model))
