"""Illustrative design planning using independent SCENES as sample units.

A normal-approximation planning calculation, not a power guarantee. Assumptions
must be justified from pilot independent scenes before registration.
"""
from __future__ import annotations
import argparse
import json
import math
from statistics import NormalDist


def scene_sample_plan(min_detectable_difference, scene_sd, alpha=0.05, power=0.80):
    if not (0<min_detectable_difference<1 and scene_sd>0 and 0<alpha<1 and 0<power<1):
        raise ValueError('must provide positive MDE and scene SD and valid alpha/power')
    normal=NormalDist()
    z_a=normal.inv_cdf(1-alpha/2)
    z_b=normal.inv_cdf(power)
    required=math.ceil(((z_a+z_b)*scene_sd/min_detectable_difference)**2)
    return {'unit':'independently authored scene (not seed/trial)',
      'design':'paired scene-level effect; asymptotic normal approximation',
      'minimum_detectable_difference':min_detectable_difference,
      'assumed_scene_level_sd':scene_sd,'alpha_two_sided':alpha,'power_target':power,
      'estimated_independent_scenes':required,
      'caveat':'Illustrative normal approximation, NOT preregistered or powered without an independent pilot estimate of scene-level variance and test-statistic design.'}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--mde',type=float,required=True)
    p.add_argument('--scene-sd',type=float,required=True)
    p.add_argument('--alpha',type=float,default=.05)
    p.add_argument('--power',type=float,default=.8)
    a=p.parse_args()
    print(json.dumps(scene_sample_plan(a.mde,a.scene_sd,a.alpha,a.power),indent=2))
