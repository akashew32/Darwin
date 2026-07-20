import base64
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from darwin.config import ExchangeConfig
from darwin.exchanges.kalshi.exceptions import KalshiAuthenticationError


def load_private_key(config: ExchangeConfig) -> rsa.RSAPrivateKey:
    if config.private_key:
        raw = config.private_key.get_secret_value().encode()
    elif config.private_key_path:
        raw = Path(config.private_key_path).read_bytes()
    else:
        raise KalshiAuthenticationError("Kalshi private key is required for authenticated features")
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise KalshiAuthenticationError("Kalshi private key must be an RSA private key")
    return key


class KalshiAuth:
    """Kalshi RSA-PSS request signer.

    Official V2 docs specify signing timestamp + method + path without query string.
    """

    def __init__(self, key_id: str, private_key: rsa.RSAPrivateKey) -> None:
        self.key_id = key_id
        self.private_key = private_key

    @classmethod
    def from_config(cls, config: ExchangeConfig) -> "KalshiAuth":
        if not config.api_key_id:
            raise KalshiAuthenticationError("KALSHI_API_KEY_ID is required")
        return cls(config.api_key_id.get_secret_value(), load_private_key(config))

    def sign(self, timestamp_ms: str, method: str, path_without_query: str) -> str:
        message = f"{timestamp_ms}{method.upper()}{path_without_query}".encode()
        signature = self.private_key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def headers(self, timestamp_ms: str, method: str, path_without_query: str) -> dict[str, str]:
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": self.sign(timestamp_ms, method, path_without_query),
        }
