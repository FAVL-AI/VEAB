# VEAP native engine acceptance gates

| Gate | Acceptance evidence | R0.3 status |
|---|---|---|
| G0 First-party UI | Self-contained browser preview, tests, API | Software test coverage provided |
| G1 MCAP source ingest | Hash, manifest, intact original, read-only import | Local code, real MCAP pending |
| G2 ROS2 ROS messages | Decoded topics/types/clock/frame from unmodified MCAP | Decoder mock tests; real bag pending |
| G3 MuJoCo native | `mj_step` completed, output digest, contact events | Worker code, host run pending |
| G4 Isaac native | Physics context stepped, rigid-object poses logged | Worker code, RTX run pending |
| G5 Native discrepancy | Same model/steps/frame, 3D errors, identified solver settings | Comparison code; joint native run pending |
| G6 CAD/scene | Validated XML/SDF; USD stage parsed by real USD | XML tests pass, native USD pending |
| G7 Learning data | Dataset local finalization and Parquet/MP4 content | Worker code, LeRobot runtime pending |
| G8 Digital twin | Calibrated physics/sensors and independently measured target | NOT VALIDATED |
| G9 Physical robot | Qualified Jetson storage, sensors, safe operator supervision | HOLD |
| G10 Enterprise | Tenant IAM, protected blobs, worker isolation, assessment | NOT QUALIFIED |

**Scientific hypothesis:** Controlled, agent-independent process verification identifies independently adjudicated failure classes not captured by credible terminal grading at a predeclared false-rejection rate.

**Proposed KPIs:** true failure detection, false rejection, synchronized evidence completeness, 3D RMSE/p90, trace reproducibility, reviewer time, and runtime/storage resource use. Targets remain prospective, not measured production claims.

## Recorded-contract monitor gate

A separate executable under `external_monitor/` rechecks recorded observations without importing VEAP. It is **agent-independent at the code boundary**, not organisationally independent IV&V. Its acceptance results are constrained by source-trace accuracy and the authored contract's calibration. The synthetic negative-control test set includes valid trajectories, prohibited-region crossings and missing recorded commands. Real robot ground truth is pending.
