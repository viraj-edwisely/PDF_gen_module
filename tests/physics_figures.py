"""One spec per computed figure kind (fig_physics.py), with the textbook values they must show. Used by test_drawing.py
and the stress PDF."""

PHYSICS = [
    ('beam with SFD and BMD: UDL and point load on an overhang', 'beam', {
        'length': 8, 'supports': [{'x': 0, 'type': 'pin'}, {'x': 6, 'type': 'roller'}], 'points': {'A': 0, 'B': 6, 'C': 8},
        'loads': [{'type': 'udl', 'x1': 0, 'x2': 6, 'w': 10}, {'type': 'point', 'x': 8, 'P': 20}], 'diagrams': ['sfd', 'bmd'],
        'dims': [[0, 6, '6 m'], [6, 8, '2 m']]}),
    ("Mohr's circle", 'mohr', {'sx': 80, 'sy': -20, 'txy': 30, 'unit': 'MPa'}),
    ('pressure on a vertical gate (Hydrostatic p.6: h_cp = 1.40 m)', 'pressure', {'top_depth': 0.5, 'length': 1.5, 'angle': 90, 'width': 1.0}),
    ('pressure on an inclined panel (Hydrostatic p.7)', 'pressure', {'top_depth': 0.6, 'length': 1.4, 'angle': 35, 'width': 0.9}),
    ('AM waveforms for three modulation indices', 'waveform', {'type': 'AM', 'mu': [0.5, 1, 1.5], 'fm': 1, 'fc': 15, 'cycles': 2}),
    ('BPSK and FSK for a bit train', 'waveform', {'type': 'FSK', 'bits': '10110', 'f1': 2, 'f2': 4}),
    ('AM spectrum, two tones', 'spectrum', {'type': 'AM', 'fc': 100, 'fm': [5, 8], 'Ac': 10, 'mu': [0.5, 0.3], 'unit': 'kHz'}),
    ('Otto cycle on p-v (ideal gas)', 'cycle', {'fluid': 'air', 'diagram': 'pv', 'states': [
        {'name': '1', 'p': 100, 'T': 300}, {'name': '2', 'v': 0.1076, 'T': 689.2}, {'name': '3', 'v': 0.1076, 'T': 1800}, {'name': '4', 'v': 0.861, 'T': 783.5}],
        'processes': [{'from': '1', 'to': '2', 'type': 'isentropic'}, {'from': '2', 'to': '3', 'type': 'isochoric'},
                      {'from': '3', 'to': '4', 'type': 'isentropic'}, {'from': '4', 'to': '1', 'type': 'isochoric'}]}),
    ('Rankine cycle on T-s (steam)', 'cycle', {'fluid': 'water', 'diagram': 'ts', 'states': [
        {'name': '1', 'p': 10, 'x': 0}, {'name': '2', 'p': 8000, 's': 0.6493}, {'name': '3', 'p': 8000, 'T': 753.15}, {'name': '4', 'p': 10, 's': 6.7357}],
        'processes': [{'from': '1', 'to': '2', 'type': 'isentropic'}, {'from': '2', 'to': '3', 'type': 'isobaric'},
                      {'from': '3', 'to': '4', 'type': 'isentropic'}, {'from': '4', 'to': '1', 'type': 'isobaric'}]}),
    ('vapour-compression cycle on p-h (R134a)', 'cycle', {'fluid': 'R134a', 'diagram': 'ph', 'states': [
        {'name': '1', 'T': 263.15, 'x': 1}, {'name': '2', 'p': 1000, 's': 1.7326}, {'name': '3', 'p': 1000, 'x': 0}, {'name': '4', 'T': 263.15, 'h': 255.48}],
        'processes': [{'from': '1', 'to': '2', 'type': 'isentropic'}, {'from': '2', 'to': '3', 'type': 'isobaric'},
                      {'from': '3', 'to': '4', 'type': 'throttling'}, {'from': '4', 'to': '1', 'type': 'isobaric'}]}),
    ('second-order step response', 'control', {'num': [10], 'den': [1, 2, 10], 'plot': 'step', 'time': 6}),
    ('Bode plot', 'control', {'num': [100], 'den': [1, 11, 10, 0], 'plot': 'bode'}),
    ('root locus', 'control', {'num': [1], 'den': [1, 3, 2, 0], 'plot': 'rootlocus'}),
]
