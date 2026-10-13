"""Generate synthetic repositories for companion output path controls."""
from pathlib import Path


def output_path_security_case(root):
    root = Path(root)
    identities = {
        "public": "example-owner/public-tool",
        "private": "example-owner/private-companion",
    }
    return {
        "root": root,
        "home": root / "synthetic-home",
        "repositories": {name: root / name for name in identities},
        "identities": identities,
        "origins": {name: "https://github.com/" + identity + ".git"
                    for name, identity in identities.items()},
        "output": Path("reports/smallcap/output.json"),
    }
