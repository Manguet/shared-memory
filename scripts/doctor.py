#!/usr/bin/env python3
"""Diagnostic des prérequis de la recherche mémoire. N'INSTALLE rien.

`diagnose(probes=None)` -> liste de checks {name, ok, remedy}. Sondes injectables (tests).
CLI : impression lisible + exit code (1 si manque)."""
import importlib.util
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))


def _model_roots():
    """Dossiers candidats où le modèle d'embeddings peut être caché."""
    home = os.path.expanduser("~")
    return [
        os.path.join(home, ".shared-memory", "models"),         # cache persistant du plugin
        os.path.join(tempfile.gettempdir(), "fastembed_cache"),  # défaut fastembed (éphémère)
        os.path.join(home, ".cache", "fastembed"),               # ancien emplacement
    ]


def _has_onnx(roots):
    """True si un fichier modèle (.onnx) est présent dans l'un des dossiers candidats."""
    for root in roots:
        if not os.path.isdir(root):
            continue
        for _d, _sub, files in os.walk(root):
            if any(f.endswith(".onnx") for f in files):
                return True
    return False


def _default_probes():
    def has_fastembed():
        return importlib.util.find_spec("fastembed") is not None

    def model_cached():
        return _has_onnx(_model_roots())

    def mcp_json_present():
        return os.path.isfile(os.path.join(_HERE, "..", ".mcp.json"))

    return {
        "python_ok": lambda: sys.version_info >= (3, 8),
        "has_fastembed": has_fastembed,
        "model_cached": model_cached,
        "mcp_json_present": mcp_json_present,
    }


def diagnose(probes=None):
    p = dict(_default_probes())
    if probes:
        p.update(probes)
    fe = p["has_fastembed"]()
    return [
        {"name": "python3 ≥ 3.8", "ok": p["python_ok"](),
         "remedy": "Installer Python 3.8+ (indispensable)."},
        {"name": "fastembed importable (recherche sémantique)", "ok": fe,
         "remedy": "pip install fastembed  — active la recherche vectorielle locale."},
        {"name": "modèle d'embeddings téléchargé", "ok": bool(fe and p["model_cached"]()),
         "remedy": "Au 1er appel search_memory le modèle (~90 Mo) se télécharge ; "
                   "ou pré-charger : python3 -c \"from fastembed import TextEmbedding; TextEmbedding()\""},
        {"name": ".mcp.json en place", "ok": p["mcp_json_present"](),
         "remedy": "Fichier .mcp.json manquant — réinstaller/mettre à jour le plugin."},
    ]


def main():
    checks = diagnose()
    miss = 0
    for c in checks:
        print("  [%s] %s" % ("OK" if c["ok"] else "X", c["name"]))
        if not c["ok"]:
            miss += 1
            print("       -> %s" % c["remedy"])
    if miss:
        print("\n%d prérequis manquant(s). search_memory tourne en fallback grep "
              "en attendant (la véracité reste garantie : le fait est lu)." % miss)
        sys.exit(1)
    print("\nTout est prêt : recherche sémantique active.")


if __name__ == "__main__":
    main()
