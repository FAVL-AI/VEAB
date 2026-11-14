# VEAP-M3 — Data preservation and hardware hold addendum

**Evidence date:** 14 November 2026 summary of local workstation and Jetson terminal outputs from 12–13 November. **Data classification:** operator-provided terminal results; no authenticated independent system audit. This supplements—not overwrites—the historical validation register.

## Backup evidence

| Gate | Operator-reported result | Interpretation |
|---|---|---|
| STOR-01 | Four ROS/research directories, approximately 3.4 GB, 3,138 files, zero `rsync -acn --delete --itemize-changes` differences; manifest SHA-256 `f95ae2061354f428f4f937684748ce292a8c2f0b1d91e392c748da436d57446c` | Selected off-device research copies passed checksum comparison |
| STOR-02A | Six additional directories (`MODELS`, `JEP`, `.ros`, `.config`, `Log`, `oled_yahboom`), approximately 12 GB, 35,942 files, zero reported checksum differences; manifest digest `efdf366822b1a3c23b62ae8eb00b9d954f67ae75eeb1ffbaa25156688b3f579a` | Additional preserved data; not a full-disk recovery image |
| STOR-02B | System configuration directory copies made but final checksum verification interrupted by direct-LAN loss. Attempts to fetch `/etc/fstab` and `/etc/nv_tegra_release` over SSH produced empty output files. | **Incomplete:** do not present empty files as valid recovery artifacts |

**Security:** backups may contain recordings, credentials and internal configurations; retain outside public Git and encrypt/protect when stored. No backup artifacts are committed in this addendum.

## Storage and operating-system status

- Platform: NVIDIA Jetson Orin NX Super, Ubuntu 22.04, Jetson Linux `R36.4.7`.
- Root: `/dev/nvme0n1p1` EXT4, approximately 95 GiB allocated, 2.1 GiB available at measurement; approximately 142 GiB NVMe capacity unallocated.
- EXT4 superblock: `clean with errors`; three recorded `EFSBADCRC` errors against inode `335505`, including the most recent kernel report on 12 November 2026.
- NVMe SMART: zero reported critical warnings, zero reported media errors; 55 unsafe shutdowns. **Absence of SMART media errors does not establish filesystem health.**
- Physical sensor state at inspection: no LiDAR, RGB-D, IMU or odometry ROS application topics; a micro-ROS agent process and serial device were present but active client telemetry was unconfirmed.
- MCAP, calibrated digital twin, emergency-stop latency and physical task-success experiments: **not qualified**.

## Corrective sequence (no destructive commands authorised by this addendum)

1. Complete verification of system-level backups, using a currently reachable connection; flag all unreadable files and changing logs.
2. Preserve a recoverable system image to sufficiently large external storage. The selected research backups are not a whole-device image.
3. Select a Jetson Linux R36.4.7-compatible **offline** recovery environment; do not run `e2fsck` repairs on the mounted root device.
4. With the root partition unmounted, inspect filesystem metadata, evaluate repair and verify restoration.
5. Only after recovery qualification, decide whether to extend the root or provision dedicated evidence storage from the unallocated region.
6. Check USB enumeration and sensor-only ROS launch paths, then begin bounded, read-only evidence recording. Motor actuation and autonomous navigation remain separately gated.

**Release claim:** Research data preservation has advanced; the physical robot's evidence acquisition and storage infrastructure are **not production-qualified**.
