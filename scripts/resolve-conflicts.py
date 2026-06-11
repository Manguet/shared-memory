#!/usr/bin/env python3
"""Résolution des conflits de merge d'un vault mémoire.

`classify_conflicts(paths)` partitionne les chemins en conflit : index/** (dérivé, régénérable),
MEMORY.md (carte curée, humain), autres .md (faits, humain), reste (humain). La CLI résout
automatiquement le cas « uniquement des index/** » en régénérant via reshard.py ; sinon elle
liste ce que l'humain doit arbitrer et s'arrête (le merge n'est jamais complété à l'aveugle).

CLI : python3 resolve-conflicts.py <clone>
  sortie 0 : rien à résoudre, ou index régénérés et stagés (prêt à committer)
  sortie 1 : de vrais conflits (faits/carte/autres) restent — ou reshard a échoué
  sortie 2 : erreur git (ex. <clone> invalide ou pas un dépôt)
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RESHARD = os.path.join(_HERE, "reshard.py")


def classify_conflicts(paths):
    """Partitionne des chemins (relatifs au vault, séparés par '/') en derived/map/facts/other."""
    out = {"derived": [], "map": [], "facts": [], "other": []}
    for p in paths:
        if p.split("/")[0] == "index":
            out["derived"].append(p)
        elif p == "MEMORY.md":
            out["map"].append(p)
        elif p.endswith(".md"):
            out["facts"].append(p)
        else:
            out["other"].append(p)
    return out


def _git(clone, *args):
    return subprocess.run(["git", "-C", clone, *args], capture_output=True, text=True)


def _conflicted_paths(clone):
    r = _git(clone, "diff", "--name-only", "--diff-filter=U")
    if r.returncode != 0:
        sys.stderr.write(r.stderr or "git diff a échoué\n")
        sys.exit(2)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def main(clone):
    paths = _conflicted_paths(clone)
    if not paths:
        print("Aucun conflit à résoudre.")
        return 0
    c = classify_conflicts(paths)
    human = c["facts"] + c["map"] + c["other"]
    if human:
        print("Conflits à arbitrer à la main (%d) :" % len(human))
        if c["facts"]:
            print("\n  Faits (contenu — choisis la bonne version, c'est un jugement) :")
            for p in c["facts"]:
                print("    - %s" % p)
        if c["map"]:
            print("\n  Carte MEMORY.md (garde l'union des domaines ; vérifie les doublons) :")
            for p in c["map"]:
                print("    - %s" % p)
        if c["other"]:
            print("\n  Autres :")
            for p in c["other"]:
                print("    - %s" % p)
        print("\nRésous-les, fais `git -C <clone> add <fichier>`, puis relance cet outil.")
        if c["derived"]:
            print("(%d index/** seront régénérés automatiquement au prochain passage.)"
                  % len(c["derived"]))
        return 1
    # uniquement des index/** -> régénération mécanique
    r = subprocess.run([sys.executable, _RESHARD, clone], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        print("Échec de reshard ; rien n'a été stagé.")
        return 1
    _git(clone, "add", "-A", "index/")
    if _conflicted_paths(clone):
        print("Des conflits subsistent après régénération — à vérifier à la main.")
        return 1
    print("✅ %d index régénéré(s) et résolu(s) — termine par `git commit`." % len(c["derived"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
