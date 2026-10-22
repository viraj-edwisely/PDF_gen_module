"""Flowsheets for the process figure kind (fig_process.py): the ones that were drawn badly as signal chains, and a few more
shapes (recycle, a stream round the outside, a pump). Used by test_physics.py and the stress PDF."""

DISTILLATION = {'nodes': [
    {'id': 'F', 'type': 'terminal', 'label': 'Feed F', 'at': [0, 1]},
    {'id': 'col', 'type': 'column', 'label': 'Distillation column', 'at': [1, 1]},
    {'id': 'cond', 'type': 'exchanger', 'label': 'Condenser', 'at': [2, 0]},
    {'id': 'drum', 'type': 'drum', 'label': 'Reflux drum', 'at': [3, 0]},
    {'id': 'D', 'type': 'terminal', 'label': 'Distillate D', 'at': [4, 0]},
    {'id': 'reb', 'type': 'exchanger', 'label': 'Reboiler', 'at': [2, 2]},
    {'id': 'B', 'type': 'terminal', 'label': 'Bottoms B', 'at': [3, 2]}],
    'streams': [
    {'from': 'F', 'to': 'col'},
    {'from': 'col', 'to': 'cond', 'label': 'Overhead vapour', 'from_side': 'N', 'to_side': 'W'},
    {'from': 'cond', 'to': 'drum', 'label': 'Condensate'},
    {'from': 'drum', 'to': 'D'},
    {'from': 'drum', 'to': 'col', 'label': 'Reflux L', 'from_side': 'S', 'to_side': 'E'},
    {'from': 'col', 'to': 'reb', 'label': 'Liquid', 'from_side': 'S', 'to_side': 'W'},
    {'from': 'reb', 'to': 'col', 'label': 'Boil-up V', 'from_side': 'N', 'to_side': 'E'},
    {'from': 'reb', 'to': 'B'}]}

PROCESS = [
    ('distillation column with condenser, reflux drum and reboiler', 'process', DISTILLATION),
    ('extractive distillation: solvent recovered and recycled', 'process', {'nodes': [
        {'id': 'F', 'type': 'terminal', 'label': 'A + B feed', 'at': [0, 1]},
        {'id': 'S', 'type': 'terminal', 'label': 'Solvent', 'at': [1, 0]},
        {'id': 'c1', 'type': 'column', 'label': 'Extractive column', 'at': [1, 1]},
        {'id': 'A', 'type': 'terminal', 'label': 'Product A', 'at': [2, 0]},
        {'id': 'c2', 'type': 'column', 'label': 'Solvent recovery', 'at': [3, 1]},
        {'id': 'Bp', 'type': 'terminal', 'label': 'Product B', 'at': [4, 0]}],
        'streams': [
        {'from': 'F', 'to': 'c1'},
        {'from': 'S', 'to': 'c1', 'to_side': 'N', 'label': 'Make-up'},
        {'from': 'c1', 'to': 'A', 'from_side': 'N', 'to_side': 'W'},
        {'from': 'c1', 'to': 'c2', 'label': 'B + solvent'},
        {'from': 'c2', 'to': 'Bp', 'from_side': 'N', 'to_side': 'W'},
        {'from': 'c2', 'to': 'c1', 'from_side': 'S', 'to_side': 'S', 'label': 'Recycled solvent'}]}),
    ('steam distillation: still, condenser, receiver', 'process', {'nodes': [
        {'id': 'S', 'type': 'terminal', 'label': 'Steam', 'at': [0, 0]},
        {'id': 'still', 'type': 'vessel', 'label': 'Still', 'at': [1, 0]},
        {'id': 'O', 'type': 'terminal', 'label': 'Organic feed', 'at': [1, 1]},
        {'id': 'cond', 'type': 'exchanger', 'label': 'Condenser', 'at': [2, 0]},
        {'id': 'rec', 'type': 'vessel', 'label': 'Receiver', 'at': [3, 0]}],
        'streams': [
        {'from': 'S', 'to': 'still'},
        {'from': 'O', 'to': 'still', 'from_side': 'N', 'to_side': 'S'},
        {'from': 'still', 'to': 'cond', 'label': 'Vapour'},
        {'from': 'cond', 'to': 'rec', 'label': 'Water + oil'}]}),
    ('reactor with a recycle round the top', 'process', {'nodes': [
        {'id': 'F', 'type': 'terminal', 'label': 'Feed', 'at': [0, 1]},
        {'id': 'p', 'type': 'pump', 'label': 'Pump', 'at': [1, 1]},
        {'id': 'rx', 'type': 'reactor', 'label': 'Reactor', 'at': [2, 1]},
        {'id': 'sep', 'type': 'drum', 'label': 'Separator', 'at': [3, 1]},
        {'id': 'P', 'type': 'terminal', 'label': 'Product', 'at': [4, 1]}],
        'streams': [
        {'from': 'F', 'to': 'p'}, {'from': 'p', 'to': 'rx', 'label': 'Pumped'}, {'from': 'rx', 'to': 'sep', 'label': 'Mixture'},
        {'from': 'sep', 'to': 'P'}, {'from': 'sep', 'to': 'p', 'from_side': 'N', 'to_side': 'N', 'label': 'Recycle', 'style': 'dashed'}]}),
]
