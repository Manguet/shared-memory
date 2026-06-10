#!/usr/bin/env python3
"""Chemins & résolution vault — miroir Python de lib.sh (slug, registre, store d'embeddings)."""
import json
import os
import re


def slug(directory):
    """Runs non-alphanumériques -> '-' (identique à sm_slug de lib.sh)."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", directory)


def config_dir():
    return os.environ.get(
        "SM_CONFIG_DIR",
        os.path.join(os.path.expanduser("~"), ".config", "shared-memory"))


def registry_path():
    return os.environ.get("SM_REGISTRY", os.path.join(config_dir(), "registry.json"))


def vault_clone_for_slug(s, registry=None):
    """Chemin du clone pour un slug, lu dans le registre. None si introuvable."""
    path = registry or registry_path()
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        return None
    for p in reg.get("projets", []):
        if p.get("slug") == s:
            return p.get("clone") or None
    return None


def embeddings_root():
    return os.environ.get(
        "SM_EMBEDDINGS_DIR",
        os.path.join(os.path.expanduser("~"), ".shared-memory", "embeddings"))


def store_path_for_slug(s):
    """Store d'embeddings HORS vault, reconstructible : ~/.shared-memory/embeddings/<slug>/index.json."""
    return os.path.join(embeddings_root(), s, "index.json")
