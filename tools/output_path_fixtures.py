"""Generate synthetic repositories and receipts for PRIVATE output controls."""
from datetime import datetime, timezone
from pathlib import Path


def visibility_receipt(states):
    """Create a fresh receipt containing only caller-supplied synthetic identities."""
    return {"_refreshed": datetime.now(timezone.utc).isoformat(), **states}


def output_path_security_case(root):
    root = Path(root)
    identities = {
        "public": "example-owner/public-tool",
        "private": "example-owner/private-companion",
        "unknown": "example-owner/unknown-companion",
    }
    return {
        "root": root,
        "home": root / "synthetic-home",
        "repositories": {name: root / name for name in identities},
        "identities": identities,
        "origins": {name: "https://github.com/" + identity + ".git"
                    for name, identity in identities.items()},
        "visibility": {identities["public"]: "PUBLIC", identities["private"]: "PRIVATE"},
        "output": Path("reports/output.json"),
        "incompatible_api": "def prove_private_companion(destination):\n    return None\n",
        "changed_signature": "synthetic-changed-configuration",
    }
