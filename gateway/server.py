"""Explicit standalone entry point; never imports the terminal orchestrator."""
import argparse
import sys

from .authentication import CredentialStore
from .config import GatewaySettings
from .errors import GatewayError


def main(argv=None):
    parser = argparse.ArgumentParser(description="BlindAssist loopback gateway (optional)")
    parser.add_argument("--settings", help="Gateway-only JSON settings file")
    provisioning = parser.add_mutually_exclusive_group()
    provisioning.add_argument("--init-credentials", action="store_true")
    provisioning.add_argument("--rotate-credentials", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = GatewaySettings.load(args.settings)
        store = CredentialStore(settings.credential_directory)
        if args.init_credentials or args.rotate_credentials:
            store.provision(rotate=args.rotate_credentials)
            print("Local credential provisioned in the configured private directory; no secret printed.")
            return 0
        store._read()  # Fail closed rather than silently generate or run without a credential.
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(settings, store=store), host=settings.host, port=settings.port,
                    access_log=False, proxy_headers=False, server_header=False, ws="none",
                    workers=1, limit_concurrency=settings.max_connections + 2, backlog=16,
                    timeout_keep_alive=2, timeout_graceful_shutdown=5, h11_max_incomplete_event_size=16384)
        return 0
    except GatewayError as error:
        print(error.code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
