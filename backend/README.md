# NETRA institutional gateway

    cd core && .venv\Scripts\python -m pip install -e .        # provides netra_core
    cd ../backend && ..\core\.venv\Scripts\python -m pip install -e .
    ..\core\.venv\Scripts\python -m uvicorn netra_backend.app:app --port 8735

Dev/demo: SQLite (`netra_backend.db` in CWD). Production: set
`DATABASE_URL=postgresql+psycopg2://...` **before import** and install
`netra-backend[postgres]` — models gain a PostGIS `location` POINT(4326)
column and ingest populates it; `/heatmap` serves GeoJSON either way.

Field devices sync here: POST /ingest (netra.scan.v1 envelope, idempotent).

## Evidence-device trust

Before accepting signed field evidence, set `NETRA_TRUSTED_CERT_SHA256S` to a
comma-separated list of SHA-256 fingerprints for certificates enrolled by the
authority. The fingerprint is the SHA-256 digest of the certificate's DER
bytes, not a fingerprint supplied by the device. Signed uploads are rejected
until this list is configured; this prevents an arbitrary self-signed key from
being treated as an official field device.

Certificate enrollment and revocation are an operational responsibility. Keep
the enrollment register with the device/official assignment record and remove
fingerprints immediately when a device is retired or compromised.
