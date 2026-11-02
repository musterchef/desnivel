"""Misure locali del profilo analizzato, senza interpretazione musicale."""
from bisect import bisect_right
from copy import deepcopy
import math


class LocalProfile:
    def __init__(self, analysis):
        self.total = analysis['total_distance_m']
        if not math.isfinite(self.total) or self.total <= 0:
            raise ValueError('profilo locale con distanza positiva e finita richiesto')
        self.config = deepcopy(analysis['config'])
        self.windows = tuple(deepcopy(analysis['windows']))
        self.zones = {z['index']: deepcopy(z) for z in analysis['zones']}
        previous = 0.
        for w in self.windows:
            low, high, slope = w['start_distance_m'], w['end_distance_m'], w['slope_ratio']
            if (not all(math.isfinite(x) for x in (low, high, slope))
                    or not previous <= low < high <= self.total or w['zone_index'] not in self.zones):
                raise ValueError('finestre locali ordinate, valide e con zona nota richieste')
            previous = high
        self.ends = tuple(w['end_distance_m'] for w in self.windows)

    def _parts(self, low, high):
        parts = []
        for w in self.windows[bisect_right(self.ends, low):]:
            if w['start_distance_m'] >= high:
                break
            length = min(high, w['end_distance_m'])-max(low, w['start_distance_m'])
            if length > 0:
                parts.append((length, w))
        return parts

    def describe(self, low, high):
        if not all(math.isfinite(x) for x in (low, high)) or not 0 <= low <= high <= self.total:
            raise ValueError('intervallo locale fuori dal percorso')
        parts = self._parts(low, high)
        covered = math.fsum(length for length, _ in parts)
        width = high-low
        result = dict(status='available' if width and math.isclose(covered, width) else 'partial' if covered else 'unavailable',
                      covered_distance_m=covered, coverage_ratio=covered/width if width else 0.,
                      slope_ratio=None, mean_absolute_slope_ratio=None, slope_change_ratio=None,
                      slope_change_unavailable_reason='no_previous_interval' if low < width else 'interruption_or_missing_coverage',
                      zone_indices=sorted({w['zone_index'] for _, w in parts}),
                      travel_segment_indices=sorted({w.get('travel_segment_index', 0) for _, w in parts}),
                      zone_persistence_m=None,
                      sample_distance_m=self.config['sample_distance_m'],
                      slope_window_m=self.config['slope_window_m'])
        if not covered:
            result['reason'] = 'no_distance' if not width else 'profile_without_coverage'
            return result
        result['slope_ratio'] = math.fsum(length*w['slope_ratio'] for length, w in parts)/covered
        result['mean_absolute_slope_ratio'] = math.fsum(length*abs(w['slope_ratio']) for length, w in parts)/covered
        # Il confronto usa un intervallo precedente della stessa lunghezza,
        # completamente osservato e appartenente allo stesso tratto registrato.
        before = self._parts(low-width, low) if low >= width else []
        previous_coverage = math.fsum(length for length, _ in before)
        segments = {w.get('travel_segment_index', 0) for _, w in (*before, *parts)}
        if (result['status'] == 'available' and before
                and math.isclose(previous_coverage, width) and len(segments) == 1):
            result['slope_change_ratio'] = result['slope_ratio']-math.fsum(
                length*w['slope_ratio'] for length, w in before)/previous_coverage
            result['slope_change_unavailable_reason'] = None
        middle = (low+high)/2
        for _, w in parts:
            if w['start_distance_m'] <= middle < w['end_distance_m']:
                zone = self.zones[w['zone_index']]
                result['zone_persistence_m'] = middle-zone['start_distance_m']
                break
        return result
