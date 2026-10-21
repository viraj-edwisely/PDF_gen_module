"""Figure specs rebuilt from the PDFs SMEs reviewed (2026-10-21), where labels overlapped, colours did not match the legend,
or a waveform could not be drawn. Used by test_drawing.py; the comment names the PDF and page."""

SME_FIGURES = [
    ('plate with eccentric hole: three labels at one point (ME screenshot)', 'plot', {
        'equal': True, 'xlabel': 'x (mm)', 'ylabel': 'y (mm)', 'title': 'Plate with eccentric hole',
        'curves': [{'x': [-80, 80, 80, -80, -80], 'y': [-50, -50, 50, 50, -50]},
                   {'param': ['30 + 20*cos(t)', '20*sin(t)'], 'range': [0, 6.2832]}],
        'points': [{'x': 0, 'y': 0, 'label': 'plate centre x=0'}, {'x': -2.56, 'y': 0, 'label': 'remaining centroid x=-2.56'},
                   {'x': 30, 'y': 0, 'label': 'hole centre x=30'}]}),
    ('BFSK decision: label on the boundary line (Digital modulation p.8)', 'plot', {
        'xlabel': 'Correlator 1', 'ylabel': 'Correlator 0', 'curves': [{'expr': 'x', 'range': [-0.5, 3], 'label': 'Boundary x = y'}],
        'points': [{'x': 0, 'y': 2, 'label': 'P0'}, {'x': 2, 'y': 0, 'label': 'P1'}, {'x': 1.2, 'y': 1.5, 'label': 'r: choose P0'}]}),
    ('gate pressure: labels on the line (Hydrostatic p.7)', 'plot', {
        'xlabel': 'Depth below free surface (m)', 'ylabel': 'Gauge pressure (kPa)',
        'curves': [{'x': [0.5, 2.0], 'y': [4.905, 19.62], 'fill': True}],
        'points': [{'x': 0.5, 'y': 4.905, 'label': 'Gate top'}, {'x': 1.25, 'y': 12.26, 'label': 'Centroid'},
                   {'x': 1.4, 'y': 13.73, 'label': 'Centre of pressure'}, {'x': 2.0, 'y': 19.62, 'label': 'Gate bottom'}],
        'annotations': [{'xy': [1.4, 13.73], 'text': 'Resultant acts here', 'xytext': [1.0, 17]}]}),
    ('raised cosine drawn in parts: legend colour must match (Digital modulation p.11)', 'plot', {
        'xlabel': 'Frequency f/Rs', 'ylabel': 'Normalized spectrum',
        'curves': [{'x': [0, 0.45], 'y': [1, 1], 'label': 'α=0.10'},
                   {'expr': '0.5*(1 + cos(pi/0.1*(x - 0.45)))', 'range': [0.45, 0.55], 'label': 'α=0.10'},
                   {'x': [0, 0.375], 'y': [1, 1], 'label': 'α=0.25'},
                   {'expr': '0.5*(1 + cos(pi/0.25*(x - 0.375)))', 'range': [0.375, 0.625], 'label': 'α=0.25'}]}),
    ('AM wave as panels, carrier 20 x message (EC feedback: merged waveforms)', 'plot', {
        'xlabel': 't (ms)', 'size': [6.4, 4.2],
        'panels': [{'ylabel': 'm(t)', 'curves': [{'expr': 'cos(2*pi*x)', 'range': [0, 2]}]},
                   {'ylabel': 'c(t)', 'curves': [{'expr': 'cos(2*pi*20*x)', 'range': [0, 2]}]},
                   {'ylabel': 's(t)', 'curves': [{'expr': '(1 + 0.5*cos(2*pi*x))*cos(2*pi*20*x)', 'range': [0, 2], 'label': 'AM wave, μ = 0.5'},
                                                 {'expr': '1 + 0.5*cos(2*pi*x)', 'range': [0, 2], 'style': '--', 'label': 'envelope'},
                                                 {'expr': '-(1 + 0.5*cos(2*pi*x))', 'range': [0, 2], 'style': '--', 'label': 'envelope'}]}]}),
]

TOO_FAST = ('plot', {'curves': [{'expr': 'cos(2*pi*1e6*x)', 'range': [0, 0.002]}]})      # 2000 carrier cycles: refused, not aliased
