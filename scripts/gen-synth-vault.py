#!/usr/bin/env python3
"""Génère un vault synthétique jetable : copie d'un vault source (sans .git) + N domaines factices.

Aide à tester reshard.py à l'échelle. N'écrit pas d'index (reshard les régénère)."""
import argparse
import os
import random
import shutil

FACT_TMPL = ("---\nname: %(name)s\ndescription: %(desc)s\nmetadata:\n  type: project\n---\n"
             "Fait synthétique %(i)d du domaine %(d)d. Remplissage pour le test à l'échelle.\n")


def generate(dest, source=None, domains=30, fmin=120, fmax=500, seed=0):
    """Copie `source` (hors .git) dans `dest` puis ajoute `domains` domaines synthétiques.
    Renvoie {domaine_synth: nb_faits}. Déterministe via `seed`."""
    rng = random.Random(seed)
    if source:
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True)
    else:
        os.makedirs(dest, exist_ok=True)
    counts = {}
    for d in range(1, domains + 1):
        dom = "synthdom-%02d" % d
        nfacts = rng.randint(fmin, fmax)
        ddir = os.path.join(dest, dom)
        os.makedirs(ddir, exist_ok=True)
        for i in range(nfacts):
            name = "synth-d%02d-f%04d" % (d, i)
            desc = "fait synthétique %d du domaine %d — variante %d" % (i, d, i % 7)
            with open(os.path.join(ddir, name + ".md"), "w", encoding="utf-8") as f:
                f.write(FACT_TMPL % {"name": name, "desc": desc, "i": i, "d": d})
        counts[dom] = nfacts
    return counts


def main():
    ap = argparse.ArgumentParser(description="Génère un vault synthétique pour tester reshard.")
    ap.add_argument("dest")
    ap.add_argument("--source", default=None)
    ap.add_argument("--domains", type=int, default=30)
    ap.add_argument("--min", dest="fmin", type=int, default=120)
    ap.add_argument("--max", dest="fmax", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    counts = generate(args.dest, args.source, args.domains, args.fmin, args.fmax, args.seed)
    print("gen: %d domaines synthétiques, %d faits -> %s"
          % (len(counts), sum(counts.values()), args.dest))


if __name__ == "__main__":
    main()
