"""Generate a local server certificate; trust installation is a separate step."""

import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

directory = Path(__file__).resolve().parents[1] / ".local-tls"
directory.mkdir(exist_ok=True)
key_path = directory / "localhost-key.pem"
cert_path = directory / "localhost-cert.pem"
der_path = directory / "localhost-cert.cer"
if key_path.exists() or cert_path.exists():
    if not (key_path.exists() and cert_path.exists()):
        raise SystemExit("Incomplete local TLS pair; inspect files before replacing.")
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ) != cert.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ):
        raise SystemExit("Local key and certificate do not match.")
    if cert.not_valid_after_utc <= datetime.now(timezone.utc):
        raise SystemExit(
            "Local certificate expired; explicitly replace and retrust it."
        )
else:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "AUREVON local dashboard")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    x509.IPAddress(ipaddress.ip_address("::1")),
                ]
            ),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    with key_path.open("xb") as output:
        output.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
der_path.write_bytes(cert.public_bytes(serialization.Encoding.DER))
print(f"Certificate: {cert_path}")
print(f"Expires UTC: {cert.not_valid_after_utc.isoformat()}")
print(f"SHA-256: {cert.fingerprint(hashes.SHA256()).hex().upper()}")
