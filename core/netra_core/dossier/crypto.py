"""Evidence-chain cryptography.

The chain: image bytes -> SHA-256 -> dossier PDF bytes -> SHA-256 ->
ECDSA P-256 signature over the UTF-8 payload
"NETRA-DOSSIER-v1|<scan_id>|<pdf_sha256_hex>" — affixed by the PLATFORM
(Android KeyStore / iOS Secure Enclave; Kotlin SHA256withECDSA matches
byte-for-byte). The core NEVER holds private keys; it verifies with the
certificate's public key when `cryptography` is available (optional
extra) and otherwise stores the signature marked unverified.
"""
from __future__ import annotations

import base64
import hashlib

SIG_PAYLOAD_PREFIX = "NETRA-DOSSIER-v1"

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    HAVE_CRYPTO = True
except Exception:                                   # pragma: no cover
    HAVE_CRYPTO = False


def sign_payload(scan_id: str, pdf_sha256_hex: str) -> bytes:
    """The exact UTF-8 byte string the platform must sign."""
    return f"{SIG_PAYLOAD_PREFIX}|{scan_id}|{pdf_sha256_hex}".encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


# ------------------------------------------------------------- verification
def verify_signature(scan_id: str, pdf_sha256_hex: str,
                     signature_b64: str, cert_pem: str) -> tuple:
    """-> (verified, error). verified=False + error=None means verification
    UNAVAILABLE (no cryptography). error set means definite failure."""
    if not HAVE_CRYPTO:
        return False, None
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode("ascii"))
        pub = cert.public_key()
        if not isinstance(pub.curve, ec.SECP256R1):
            return False, "signing key is not ECDSA P-256"
        pub.verify(unb64(signature_b64),
                   sign_payload(scan_id, pdf_sha256_hex),
                   ec.ECDSA(hashes.SHA256()))
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# ------------------------------------------------------- dev signing helpers
def make_dev_key():
    """DEV/TEST key only — production keys are hardware-backed, off-core."""
    return ec.generate_private_key(ec.SECP256R1())


def make_dev_cert(key, cn: str = "NETRA Dev Evidence Key") -> str:
    from datetime import datetime, timedelta

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.now(datetime.now().astimezone().tzinfo)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=3650))
            .sign(key, hashes.SHA256()))
    return cert.public_bytes(serialization.Encoding.PEM).decode("ascii")


def dev_sign(key, scan_id: str, pdf_sha256_hex: str) -> str:
    """DEV/TEST signing via the same payload the platform signs."""
    return b64(key.sign(sign_payload(scan_id, pdf_sha256_hex),
                        ec.ECDSA(hashes.SHA256())))
