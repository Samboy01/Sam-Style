"""Hjälpfunktioner för Shopify."""

import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    """Kontrollerar att en webhook verkligen kommer från Shopify (IFK4).

    Shopify räknar ut en HMAC-SHA256 av den råa request-bodyn med den delade hemligheten
    och skickar resultatet base64-kodat i headern X-Shopify-Hmac-Sha256. Vi räknar ut
    samma sak och jämför. Bodyn måste vara exakt de bytes som kom in, innan den tolkas
    som JSON, annars stämmer signaturen inte.
    """
    if not secret or not hmac_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    # compare_digest tar lika lång tid oavsett var strängarna skiljer sig,
    # så att en angripare inte kan gissa signaturen tecken för tecken.
    return hmac.compare_digest(expected, hmac_header)
