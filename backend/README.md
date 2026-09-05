# NETRA institutional gateway

    cd core && .venv\Scripts\python -m pip install -e .        # provides netra_core
    cd ../backend && ..\core\.venv\Scripts\python -m pip install -e .
    ..\core\.venv\Scripts\python -m uvicorn netra_backend.app:app --port 8735

Dev/demo: SQLite (`netra_backend.db` in CWD). Production: set
`DATABASE_URL=postgresql+psycopg2://...` **before import** and install
`netra-backend[postgres]` — models gain a PostGIS `location` POINT(4326)
column and ingest populates it; `/heatmap` serves GeoJSON either way.

Field devices sync here: POST /ingest (netra.scan.v1 envelope, idempotent).
