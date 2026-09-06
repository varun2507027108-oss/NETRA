package netra.core

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.math.BigInteger
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.util.Date
import javax.security.auth.x500.X500Principal

/**
 * NETRA evidence signing — Android KeyStore, ECDSA P-256 / SHA-256.
 *
 * The payload law is pinned in THREE places that must stay identical:
 *   netra_core/dossier/crypto.py      sign_payload()
 *   core/tests/test_attach_signature.py
 *      test_signature_payload_format_is_pinned
 *      ^NETRA-DOSSIER-v1\|[0-9a-f]{32}\|[0-9a-f]{64}$
 *   and this file.
 *
 * SHA256withECDSA on Android emits a DER-encoded ECDSA-Sig-Value —
 * byte-for-byte what Python `cryptography` verifies in
 * crypto.verify_signature (base64-DER in, pub.verify(..., ECDSA(SHA256))).
 * The private key never leaves the KeyStore (TEE/StrongBacked on modern
 * devices); only the self-signed certificate exports as PEM.
 */
object NetraKeystore {
    private const val KEYSTORE = "AndroidKeyStore"
    private const val ALIAS = "netra_evidence"

    fun payload(scanId: String, pdfSha256Hex: String): String =
        "NETRA-DOSSIER-v1|$scanId|$pdfSha256Hex"

    /** Generate the evidence key once (idempotent). Requires API 23+. */
    fun ensureKey() {
        val ks = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        if (ks.containsAlias(ALIAS)) return
        val spec = KeyGenParameterSpec.Builder(
            ALIAS,
            KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setCertificateSubject(
                X500Principal("CN=NETRA Evidence Key, O=Legal Metrology Field Audit"))
            .setCertificateSerialNumber(BigInteger.valueOf(System.currentTimeMillis()))
            .setCertificateNotBefore(Date(System.currentTimeMillis() - 86_400_000L))
            .setCertificateNotAfter(
                Date(System.currentTimeMillis() + 10L * 365 * 24 * 3600 * 1000))
            .build()
        KeyPairGenerator
            .getInstance(KeyProperties.KEY_ALGORITHM_EC, KEYSTORE)
            .apply { initialize(spec) }
            .generateKeyPair()
    }

    /** Sign the pinned payload; returns base64(DER). */
    fun sign(scanId: String, pdfSha256Hex: String): String {
        ensureKey()
        val key = KeyStore.getInstance(KEYSTORE)
            .apply { load(null) }
            .getKey(ALIAS, null) as PrivateKey
        val signature = Signature.getInstance("SHA256withECDSA")
        signature.initSign(key)
        signature.update(payload(scanId, pdfSha256Hex).toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(signature.sign(), Base64.NO_WRAP)
    }

    /** Self-signed certificate for the evidence key, PEM — what
     * attach_signature expects as cert_pem. */
    fun certPem(): String {
        val cert = KeyStore.getInstance(KEYSTORE).apply { load(null) }
            .getCertificate(ALIAS)
            ?: throw IllegalStateException("ensureKey() not run")
        val b64 = Base64.encodeToString(cert.encoded, Base64.NO_WRAP)
        return "-----BEGIN CERTIFICATE-----\n$b64\n-----END CERTIFICATE-----\n"
    }

    /**
     * Convenience: build the attach_signature request for a completed
     * scan result (contract §8 flow) — the ONLY place Kotlin reads
     * payload fields, and only to feed the signer.
     */
    fun attachRequestFor(scanResultJson: String): String {
        val result = JSONObject(scanResultJson)
        if (result.isNull("dossier")) {
            throw IllegalStateException("scan has no dossier to sign")
        }
        val scanId = result.getString("scan_id")
        val sha = result.getJSONObject("dossier").getString("sha256")
        return JSONObject()
            .put("scan_id", scanId)
            .put("signature", sign(scanId, sha))
            .put("cert_pem", certPem())
            .toString()
    }
}
