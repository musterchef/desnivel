"""Corrispondenza fra finestra da pianificare e dati osservati del viaggio."""
import math

import numpy as np

from desnivel.trip.local_context import LocalProfile


class WindowContext:
    def __init__(self, track, analysis=None):
        self.track = track
        self.distances = np.asarray(track.samples['cum_dist_m'])-track.samples['cum_dist_m'][0]
        self.profile = LocalProfile(analysis) if analysis is not None else None

    def _parts(self, low, high, axis):
        parts = []
        segments = [(i, s.start, s.stop, s.source_start_unix)
                    for i, s in enumerate(self.track.segments)] or [(None, 0, len(self.track.t), None)]
        for index, start, stop, source_start in segments:
            times, distances = self.track.t[start:stop], self.distances[start:stop]
            coordinates = distances if axis == 'distance' else times
            a, b = max(low, float(coordinates[0])), min(high, float(coordinates[-1]))
            if b <= a:
                continue
            t0, t1 = np.interp([a, b], coordinates, times)
            d0, d1 = np.interp([a, b], coordinates, distances)
            parts.append(dict(travel_segment_index=index, start_active_s=float(t0), end_active_s=float(t1),
                              start_distance_m=float(d0), end_distance_m=float(d1),
                              source_start_unix=None if source_start is None else float(source_start+t0-times[0]),
                              source_end_unix=None if source_start is None else float(source_start+t1-times[0])))
        return parts

    def _describe(self, mode, parts, **position):
        result = dict(mode=mode, status='available' if parts else 'unavailable', parts=parts, **position)
        if not parts:
            result['reason'] = 'outside_observed_trip'
        if self.profile is None:
            result['profile'] = dict(status='unavailable', reason='analysis_not_configured')
        elif not parts:
            result['profile'] = dict(status='unavailable', reason='outside_observed_trip')
        else:
            result['profile'] = self.profile.describe(parts[0]['start_distance_m'], parts[-1]['end_distance_m'])
        return result

    def allocated(self, timeline, sections, window_index):
        index, fraction = timeline.position(window_index)
        _, end_fraction = timeline.position(window_index, 1.)
        section = sections[index]
        low, high = section['start_distance_m'], section['end_distance_m']
        start, end = low+(high-low)*fraction, low+(high-low)*end_fraction
        return self._describe('allocated', self._parts(start, end, 'distance'),
                              window_index=window_index, source_index=index,
                              start_distance_m=start, end_distance_m=end)

    def linear(self, *, elapsed_s, live_beat, start_beat, length_beats, bpm, speed):
        if bpm is None:
            return dict(mode='linear', status='unavailable', reason='tempo_unavailable')
        if (any(type(x) not in (int, float) or not math.isfinite(x)
                for x in (elapsed_s, live_beat, start_beat, length_beats, bpm, speed))
                or elapsed_s < 0 or live_beat < 0 or start_beat < live_beat
                or min(length_beats, bpm, speed) <= 0):
            raise ValueError('tempo, velocità e intervallo di proiezione non validi')
        start = self.track.t[0]+elapsed_s+(start_beat-live_beat)*60/bpm*speed
        end = start+length_beats*60/bpm*speed
        return self._describe('linear', self._parts(start, end, 'time'),
                              start_active_s=float(start), end_active_s=float(end),
                              bpm=bpm, speed=speed, truncated_at_finish=bool(end > self.track.t[-1]))
