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
    ('stereo pair: T1/G1 and T2/G2 labels on each other, arrows across the plot (Aerial Survey p.8)', 'plot', {
        'xlabel': 'Flight baseline (m)', 'ylabel': 'Height (m)',
        'curves': [{'x': [0, 5], 'y': [8, 0]}, {'x': [0, 5], 'y': [8, 2]}, {'x': [10, 5], 'y': [8, 2]}, {'x': [10, 5], 'y': [8, 0]}],
        'points': [{'x': 0, 'y': 8, 'label': 'O1'}, {'x': 10, 'y': 8, 'label': 'O2'}, {'x': 5, 'y': 0, 'label': 'G'}, {'x': 5, 'y': 2, 'label': 'T'},
                   {'x': 0.8, 'y': 7.6, 'label': 'T1'}, {'x': 0.8, 'y': 7.2, 'label': 'G1'}, {'x': 9.2, 'y': 7.6, 'label': 'T2'}, {'x': 9.2, 'y': 7.2, 'label': 'G2'}],
        'annotations': [{'xy': [0.8, 7.2], 'text': 'left photo', 'xytext': [0.2, 6]}, {'xy': [9.2, 7.6], 'text': 'right photo', 'xytext': [7, 9]},
                        {'xy': [5, 2], 'text': 'pT = 54.0 mm', 'xytext': [5.4, 2.6]}, {'xy': [5, 0], 'text': 'pG = 52.5 mm', 'xytext': [5.4, -0.3]}]}),
    ('photo overlap: labels on the footprint edges (Aerial Survey p.6)', 'plot', {
        'xlabel': 'Along flight (km)', 'ylabel': 'Across flight (km)', 'grid': True,
        'curves': [{'x': [0, 2.4, 2.4, 0, 0], 'y': [0, 0, 2, 2, 0]}, {'x': [0.96, 3.36, 3.36, 0.96, 0.96], 'y': [0, 0, 2, 2, 0]},
                   {'x': [0, 2.4, 2.4, 0, 0], 'y': [1.4, 1.4, 3.4, 3.4, 1.4]}],
        'annotations': [{'xy': [0.5, 0.2], 'text': 'Usable advance: 0.96 km', 'xytext': [0.1, 0.4]}, {'xy': [1.3, 1.0], 'text': 'Forward overlap: 60%', 'xytext': [1.4, 0.7]},
                        {'xy': [0.2, 1.9], 'text': 'Strip spacing: 1.40 km', 'xytext': [0.15, 2.1]}, {'xy': [1.2, 1.7], 'text': 'Side overlap: 30%', 'xytext': [1.5, 2.5]}]}),
    ('stereo pair as geometry, the way the catalogue asks for it (Aerial Survey p.8)', 'geometry', {'items': [
        {'type': 'segment', 'from': [-1, 0], 'to': [11, 0], 'label': 'datum'}, {'type': 'segment', 'from': [5, 0], 'to': [5, 2], 'lw': 4},
        {'type': 'point', 'at': [0, 8], 'label': 'O1'}, {'type': 'point', 'at': [10, 8], 'label': 'O2'},
        {'type': 'dim', 'from': [0, 9], 'to': [10, 9], 'label': 'B = 620 m'},
        {'type': 'segment', 'from': [-0.8, 7.2], 'to': [0.8, 7.2], 'label': 'left photo'}, {'type': 'segment', 'from': [9.2, 7.2], 'to': [10.8, 7.2], 'label': 'right photo'},
        {'type': 'segment', 'from': [0, 8], 'to': [5, 0], 'style': '--'}, {'type': 'segment', 'from': [0, 8], 'to': [5, 2], 'style': '--'},
        {'type': 'segment', 'from': [10, 8], 'to': [5, 0], 'style': '--'}, {'type': 'segment', 'from': [10, 8], 'to': [5, 2], 'style': '--'},
        {'type': 'point', 'at': [5, 0], 'label': 'G'}, {'type': 'point', 'at': [5, 2], 'label': 'T'},
        {'type': 'dim', 'from': [11.5, 0], 'to': [11.5, 8], 'label': 'H = 1800 m'}]}),
    ('photo overlap as geometry: dims for a and b, translucent footprints (Aerial Survey p.6)', 'geometry', {'items': [
        {'type': 'rect', 'at': [0, 0], 'w': 2.4, 'h': 2.0, 'label': '1'}, {'type': 'rect', 'at': [0.96, 0], 'w': 2.4, 'h': 2.0, 'label': '2'},
        {'type': 'rect', 'at': [0, 1.4], 'w': 2.4, 'h': 2.0, 'label': '3'},
        {'type': 'dim', 'from': [0, -0.4], 'to': [0.96, -0.4], 'label': 'a = 0.96 km'}, {'type': 'dim', 'from': [-0.4, 0], 'to': [-0.4, 1.4], 'label': 'b = 1.40 km'},
        {'type': 'arrow', 'from': [2.6, -0.4], 'to': [3.4, -0.4], 'label': 'flight'}]}),
]

TOO_FAST = ('plot', {'curves': [{'expr': 'cos(2*pi*1e6*x)', 'range': [0, 0.002]}]})      # 2000 carrier cycles: refused, not aliased
