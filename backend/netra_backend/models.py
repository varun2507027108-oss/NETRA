from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .db import postgis_enabled


class Base(DeclarativeBase):
    pass


_POSTGIS = postgis_enabled()
if _POSTGIS:
    from geoalchemy2 import Geometry


class ScanRecord(Base):
    """One synced NETRA audit (envelope netra.scan.v1). result_json holds
    the full contract ScanResult. APPEND-ONLY: re-ingesting a scan_id is
    an idempotent no-op."""
    __tablename__ = "scans"

    scan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    verdict: Mapped[str] = mapped_column(String(16))
    created_utc: Mapped[Optional[str]] = mapped_column(String(40))
    received_utc: Mapped[str] = mapped_column(String(40))
    image_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    dossier_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    signature: Mapped[Optional[str]] = mapped_column(Text)
    cert_pem: Mapped[Optional[str]] = mapped_column(Text)
    sig_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    sig_status: Mapped[str] = mapped_column(String(16), default="pending")
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lon: Mapped[Optional[float]] = mapped_column(Float)
    result_json: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(default=0)

    if _POSTGIS:
        location = mapped_column(Geometry(geometry_type="POINT", srid=4326))

    def to_export_row(self) -> dict:
        """Ledger-row-shaped dict for the core exporters."""
        return {"scan_id": self.scan_id, "verdict": self.verdict,
                "created_utc": self.created_utc,
                "image_sha256": self.image_sha256,
                "dossier_sha256": self.dossier_sha256,
                "signature": self.signature, "cert_pem": self.cert_pem,
                "sig_verified": self.sig_verified,
                "sig_status": self.sig_status,
                "result_json": self.result_json}
