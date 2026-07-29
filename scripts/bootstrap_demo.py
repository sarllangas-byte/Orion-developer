"""Crée un dépôt de démonstration local propre dans workspace/geostab."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run_git(workspace: Path, *arguments: str) -> None:
    process = subprocess.run(
        ["git", *arguments],
        cwd=workspace,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or f"git {' '.join(arguments)} a échoué")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    source = root / "examples" / "geostab-demo"
    workspace = root / "workspace" / "geostab"
    if workspace.exists() and any(workspace.iterdir()):
        raise RuntimeError(
            "workspace/geostab existe déjà et n'est pas vide. "
            "Aucune donnée n'a été supprimée."
        )
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, workspace, dirs_exist_ok=True)
    run_git(workspace, "init", "-b", "main")
    run_git(workspace, "config", "user.name", "ORION Demo")
    run_git(workspace, "config", "user.email", "orion-demo@example.invalid")
    run_git(workspace, "add", ".")
    run_git(workspace, "commit", "-m", "Initialiser la démonstration GeoStab")
    print(f"Dépôt de démonstration prêt : {workspace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
