# -*- coding: utf-8 -*-
"""Launch Streamlit with Windows SSL cert-store workaround."""
from __future__ import annotations

import os
import ssl
import sys


def _patch_ssl() -> None:
    try:
        import certifi

        ca = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)
        os.environ.setdefault("CURL_CA_BUNDLE", ca)
    except Exception:
        ca = None

    _orig = ssl.create_default_context

    def _safe(*args, **kwargs):
        try:
            return _orig(*args, **kwargs)
        except ssl.SSLError:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            if ca:
                ctx.load_verify_locations(cafile=ca)
            return ctx

    ssl.create_default_context = _safe  # type: ignore[assignment]


def main() -> None:
    _patch_ssl()
    from streamlit.web import cli

    root = os.path.dirname(os.path.abspath(__file__))
    app = os.path.join(root, "app.py")
    sys.argv = [
        "streamlit",
        "run",
        app,
        "--server.port",
        "8503",
        "--browser.gatherUsageStats",
        "false",
        *sys.argv[1:],
    ]
    cli.main()


if __name__ == "__main__":
    main()
