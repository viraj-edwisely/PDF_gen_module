"""The ME figures SMEs found unreadable or technically wrong (2026-10-21), redrawn with the geometry kind. Used by
test_drawing.py and the stress PDF."""
import math

_tilt = 10                                             # floating body heeled by 10 degrees about its waterline centre
SME_GEOMETRY = [
    ('traverse with bearings (ME screenshot: nodes on top of each other)', 'geometry', {
        'north': True, 'items': [
            {'type': 'point', 'at': [0, 0], 'label': 'A'},
            {'type': 'bearing', 'from': [0, 0], 'bearing': 30, 'length': 100, 'label': 'P1: 100 m, 030°', 'to_label': 'B'},
            {'type': 'bearing', 'from': [50, 86.6], 'bearing': 210, 'length': 80, 'label': 'P2: 80 m, 210°', 'to_label': 'C'},
            {'type': 'bearing', 'from': [10, 17.3], 'bearing': 120, 'length': 60, 'label': 'P3: 60 m, 120°', 'to_label': 'D'}]}),
    ('plate with an eccentric hole (ME screenshot: labels piled up, circle drawn as an ellipse)', 'geometry', {
        'axes': True, 'xlabel': 'x (mm)', 'ylabel': 'y (mm)', 'items': [
            {'type': 'rect', 'at': [-80, -50], 'w': 160, 'h': 100, 'fill': 'lav', 'holes': [[[30 + 20 * math.cos(t / 20 * 2 * math.pi), 20 * math.sin(t / 20 * 2 * math.pi)] for t in range(20)]]},
            {'type': 'point', 'at': [0, 0], 'label': 'plate centre, x = 0'},
            {'type': 'point', 'at': [-2.56, 0], 'label': 'remaining centroid, x = −2.56'},
            {'type': 'point', 'at': [30, 0], 'label': 'hole centre, x = 30'}]}),
    ('floating body heeled (Buoyancy p.9: unreadable)', 'geometry', {
        'items': [
            {'type': 'surface', 'y': 0, 'x': [-3, 3], 'label': 'waterline'},
            {'type': 'rect', 'at': [-1.5, -1.0], 'w': 3, 'h': 2, 'rotate': _tilt, 'about': [0, 0], 'fill': 'lav'},
            {'type': 'point', 'at': [0.17, 0.5], 'label': 'G'},
            {'type': 'point', 'at': [0.35, -0.5], 'label': "B′"},
            {'type': 'point', 'at': [0, 1.4], 'label': 'M'},
            {'type': 'arrow', 'from': [0.17, 0.5], 'to': [0.17, -0.6], 'label': 'W'},
            {'type': 'arrow', 'from': [0.35, -0.5], 'to': [0.35, 0.6], 'label': 'F_B'},
            {'type': 'segment', 'from': [0.35, -0.5], 'to': [0, 1.4], 'style': '--', 'color': 'grey'},
            {'type': 'angle', 'center': [0, 0], 'from_deg': 90, 'to_deg': 90 + _tilt, 'r': 0.9, 'label': 'θ'}]}),
    ('inclined plate in water (Hydrostatic Q6: plate drawn rising)', 'geometry', {
        'depth_down': True, 'items': [
            {'type': 'surface', 'y': 0, 'x': [-0.2, 3.0], 'label': 'free surface'},
            {'type': 'segment', 'from': [0, 1.0], 'to': [2.598, 2.5], 'lw': 4, 'label': 'plate, 3.0 m along the slope'},
            {'type': 'dim', 'from': [0, 0], 'to': [0, 1.0], 'label': '1.0 m', 'offset': 0.35},
            {'type': 'angle', 'center': [0, 1.0], 'from_deg': 0, 'to_deg': 30, 'r': 0.6, 'label': '30°'},
            {'type': 'point', 'at': [1.299, 1.75], 'label': 'G'}]}),
]
