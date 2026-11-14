"""Named and limited comparator graders; NOT reproductions of EAI, Foxglove or ROS2."""
from __future__ import annotations
import math


def _distance(point, z):
    x,y=point
    return math.hypot(max(z[0]-x,0,x-z[2]),max(z[1]-y,0,y-z[3]))


def grade(c, trace, method):
    poses=[s for s in trace['samples'] if 'x' in s and 'y' in s and 't_s' in s]
    if not poses:
        return 'INCONCLUSIVE'
    end=poses[-1]
    goal=c['goal'];err=c['position_uncertainty_m'];v=c['max_speed_mps']
    dist=math.hypot(end['x']-goal['x'],end['y']-goal['y'])
    reach=err+v*(c['mission_end_s']-end['t_s'])
    if dist-reach>goal['tolerance_m']:
        return 'VIOLATING'
    if dist+reach>goal['tolerance_m']:
        return 'INCONCLUSIVE'
    if method=='goal_only':
        return 'COMPLIANT'
    if method=='terminal_safety':
        return 'VIOLATING' if _distance((end['x'],end['y']),c['keepout'])<c['robot_radius_m'] else 'COMPLIANT'
    if any(_distance((p['x'],p['y']),c['keepout'])<c['robot_radius_m'] for p in poses):
        return 'VIOLATING'
    if method=='sampled_safety':
        return 'COMPLIANT'
    if method=='gap_aware':
        # Credible abstaining comparator: trajectory frame/clock, essential channels and gaps.
        if any(p.get('sensor_healthy') is not True or p.get('frame_id') != c['frame_id'] or
               set(c['required_topics'])-set(p.get('topics',[])) for p in poses):
            return 'INCONCLUSIVE'
        if abs(poses[0]['t_s']-c['mission_start_s'])>1e-9 or abs(poses[-1]['t_s']-c['mission_end_s'])>1e-9:
            return 'INCONCLUSIVE'
        if any(p1['t_s']<=p0['t_s'] or p1['t_s']-p0['t_s']>c['max_gap_s'] for p0,p1 in zip(poses,poses[1:])):
            return 'INCONCLUSIVE'
        return 'COMPLIANT'
    raise ValueError('Invalid comparator')
