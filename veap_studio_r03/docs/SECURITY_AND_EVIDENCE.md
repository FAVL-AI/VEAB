# Evidence Security and Local Host Boundary

The service is for a **single trusted operator bound to 127.0.0.1**. No general internet exposure, OIDC, production isolation or professional safety certification is claimed. An optional `VEAP_STUDIO_TOKEN` provides a local test barrier, not enterprise IAM.

All uploads are bounded and copied into a local vault with SHA-256. Large MCAP files may be staged in an administrator-chosen local inbox, protected by symlink/basename checks and free-space requirements. Uploaded bytes remain unauthenticated even after hashing. Derived datasets must carry source identifiers.

The native job worker uses a fixed allowlist of scripts and a single-thread queue with process-level timeouts. It does not accept arbitrary shell commands from web clients. Generated physics evidence reports actual measurements but not independent sensor truth.

Robot actuators and network-control endpoints are intentionally excluded. The recovery-hold Yahboom M3 Pro may be used only for separately supervised, documented hardware procedures after storage and sensor qualification.

For production, implement OIDC/SAML, tenant-scoped authorisation, PostgreSQL, isolated workers, protected retention keys, signed builds/SBOM, independent security review, incident response and restore testing. Do not expose this R0.3 development server to untrusted networks.
