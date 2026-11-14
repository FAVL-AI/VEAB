# VEAP-M3 Replay — Research Slice M3-R0.1

**Scope:** Versioned, read-only ROS 2/MCAP evidence contracts, topic-type and timing checks, a separate-implementation monitor, and synthetic controls. This is an **additive package** for VEAP (Python >=3.10); it does not edit the existing VEAP engine or publish ROS commands.

## A. Run the software-only synthetic controls, without ROS installed

From the VEAP repository root:

```bash
python -m pytest -q tests/test_m3_contract.py
python scripts/generate_m3_fixture_set.py
python scripts/run_m3_controls.py
python -m veap.m3_replay.cli \
  --contract contracts/m3_nav_v1.template.json \
  --jsonl examples/m3/clean.jsonl \
  --out examples/m3/local-audit.json
python external_monitor/m3_record_monitor.py \
  --contract contracts/m3_nav_v1.template.json \
  --jsonl examples/m3/clean.jsonl
```

Reports are explicitly `UNATTESTED`; these synthetic controls are not a validation dataset. Input SHA-256 hashes establish only identity of the bytes examined.

## B. Discover the actual ROS 2 topics first (Ubuntu 22.04 / Humble)

In a NEW terminal, outside the Isaac/MuJoCo virtual environments:

```bash
cd ~/projects/VEAP  # use the actual VEAP checkout path
source /opt/ros/humble/setup.bash
bash scripts/veap_m3_capture_preflight.sh
ros2 topic list -t
```

**Never assume** `/scan`, `/scan0`, `/scan1`, `/odom`, `/odom_raw`, or camera topics exist on this particular robot. The sample topic mapping is NOT frozen hardware truth; edit the JSON contract to exactly match the observed topic names and message types. Also inspect TF frame IDs and publish frequencies to set calibrated gap thresholds before making operational claims.

## C. Audit a recorded MCAP without controlling the robot

Use the ROS 2 system Python (which has `rosbag2_py`) rather than Isaac Python 3.11 or MuJoCo Python 3.13. The MCAP storage plugin is required, as documented by MCAP/rosbag2:

```bash
source /opt/ros/humble/setup.bash
cd /path/to/your/veap-repository
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
/usr/bin/python3 -m veap.m3_replay.cli \
  --contract contracts/m3_nav_v1.template.json \
  --bag /path/to/recorded/bag_or_file.mcap \
  --out m3-audit-report.json
```

For header timestamp and frame-ID extraction (additional CPU cost), add `--decode-headers`. A `--hash-bag` option computes a digest over the entire `.mcap` **file**; bags stored as directories must be hashed externally with an appropriate manifest. The auditor consumes stored bag messages using `rosbag2_py.SequentialReader` and does not create a ROS publisher/subscriber or modify the bag.

**Important caveats:** Bag receive timestamps are not sensor hardware timestamps. A decoded ROS header can be inaccurate or forged, and decoded frames do not establish a correct TF graph. This stage does not reconstruct trajectories, detect real collisions or certify physical safety. Real-world constraints and recovery rules require calibrated sensor data and a separately instrumented reference monitor.

## D. Intended scope and next dependencies

| Workstream | State in this patch | Evidence still missing |
|---|---|---|
| WP1 versioned observation contract | Implemented, tested on synthetic envelopes | Actual M3 topic inventory and calibration |
| WP2 independent-implementation monitor | Implemented, reads only JSONL and contract | Independent ground truth and third-party assessment |
| WP3 MCAP/ROS2 ingestion | Native read-only adapter implemented, not executed here on Humble | Real bag, ROS 2 runtime test, recovered header clocks |
| WP4 faults | Missing-topic/type/time synthetic negative controls | Real captured dropout, delay, odometry drift and recoveries |
| WP5 attribution | Candidate cause triage only | Causal interventions and blinded attribution labels |
| WP6 Isaac/MuJoCo | No modification in this patch | Matched native trajectories and calibration |
| WP7 NemoClaw/Nemotron/VLA | Deliberately not installed | Benchmark and safety review of agent runtime |
| WP8 long-context optimisation | Deferred | Demonstrated retrieval/attention bottleneck |
| WP9 hardware pilot | Not started | Supervised rig, independent E-stop, approved safety case |

## E. Interpret test results accurately

The synthetic control generator creates 11 **constructed** examples: seven invalid and four valid under the sample metadata contract. A record truncated at an unknown time may appear complete when the window is inferred from the recording. This is an intentional epistemic negative control; an explicit expected mission window or independent logger is necessary to detect it.

Never use these results as estimates of unsafe-action detection, a robot safety claim, a production SLA or state-of-the-art performance. Human adjudication, independently authored scenes and physically grounded reference observations are not included.

## F. External agent runtimes

NVIDIA NemoClaw / OpenShell can be evaluated later as a **sandboxed agent executor**, separately from VEAP's verifier and source-of-truth custody. Do not route robot safety-critical control through it or assume runtime sandboxing establishes physical safety. No NemoClaw components or model weights are installed by this patch.

## G. Linux native backend portability note

The base VEAP repository currently tracks prebuilt macOS ARM64 (`Mach-O 64-bit arm64`) executables under `backend/bin/` (`veap-cpp-sim`, `veap-go-orchestrator`, `veap-rust-verifier`). On an x86_64 Linux workstation, `tests/test_native_backends.py` will fail with `OSError: [Errno 8] Exec format error` until those binaries are rebuilt natively (`bash backend/build.sh` with `cargo`, `g++`/`clang++`, and `go` on `PATH`), or ignored via `pytest --ignore=tests/test_native_backends.py`. Do not commit host-compiled binaries into the additive M3 Replay patch.
