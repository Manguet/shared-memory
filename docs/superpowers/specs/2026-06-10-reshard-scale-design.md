# Design — `reshard.py` : redécoupage automatique en sous-domaines + vérification à l'échelle

**Date :** 2026-06-10
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Prérequis :** Volet A (index compact, livré) + viewer scalable (arbre N-niveaux depuis `path[]`, livré).

## Objectif et contrainte

Rendre **réel et automatique** le « redécoupage en sous-domaines » que la convention ne décrivait
jusqu'ici que comme semi-automatique : quand un domaine contient trop de faits pour qu'un index
tienne dans la capacité de lecture de Claude (~150 lignes), il faut le **scinder récursivement en
sous-domaines** pour que chaque index reste lisible d'un coup. Puis **vérifier à l'échelle** que ça
tient, sur une **copie jetable** du vrai vault `negocian-memory` augmentée de faits synthétiques.

**Contrainte de sûreté :** le vrai vault `negocian-memory` (9 faits réels + une migration en cours
non commitée dans son clone) ne doit **jamais** être touché. Tout le test se fait sur une **copie**.

## Invariant fondateur

> **Aucun dossier ne contient plus de N faits directs, ni plus de N sous-dossiers** (défaut N = 150).

Comme 1 fait = 1 ligne compacte d'index et 1 sous-domaine = 1 ligne de pointeur, cet invariant
garantit que **tout fichier d'index reste ≤ N lignes** — donc lisible d'un seul coup. C'est la seule
règle ; reshard l'applique récursivement, profondeur **émergente sans plafond**.

## Composants

### `scripts/reshard.py` (outil réutilisable, cœur du livrable)

Opère sur l'arborescence de **faits** (la source de vérité sur disque), en deux temps :

1. **Restructure** (déplace des faits uniquement là où l'invariant est violé — idempotent) :
   - dossier avec **> N faits directs** → répartition équilibrée des faits **triés par `name`** en
     sous-dossiers `part-01 … part-k` (`k = ceil(M/N)`, capé à N enfants) ;
   - dossier avec **> N sous-dossiers** → regroupement récursif des sous-dossiers en niveaux
     intermédiaires `part-01 …` ;
   - un sous-arbre **déjà conforme n'est pas re-brassé** → les libellés humains survivent.
2. **Régénère** tout `index/**` + la carte `MEMORY.md` depuis l'arbre de faits résultant (le
   dossier `index/` est **reconstruit** : les fichiers d'index obsolètes — domaine disparu ou nœud
   devenu feuille — sont supprimés ; les noms d'index suivent les **noms de dossiers** courants, donc
   un sous-domaine renommé par un humain est préservé) :
   - **feuille** (dossier de faits) → `index/<chemin>.md` = lignes compactes
     `` - `<nom>` — <description> · <type> → `<chemin>/<fait>.md` `` ;
   - **nœud** (dossier de sous-dossiers) → `index/<chemin>.md` = pointeurs de sous-domaine
     `- <sous> (<n> faits) → index/<chemin>/<sous>.md` ;
   - `MEMORY.md` = un pointeur par domaine de premier niveau.

reshard devient ainsi le **moteur unique** de génération d'index (les skills l'appellent au lieu
d'écrire l'index à la main). Réutilise `collect_facts`/`parse_md` de `build-viewer.py` pour lire les
faits, et la convention de pointeurs (relatifs à la racine du vault).

**CLI :** `reshard.py <vault> [--max-entries N]` (défaut 150). Idempotent : relancer sur un vault
conforme ne déplace rien et régénère des index identiques.

### `scripts/gen-synth-vault.py` (aide au test)

`gen-synth-vault.py <dest> [--source <clone>] [--domains 30] [--min 120] [--max 500] [--seed S]` :

1. **Copie** le contenu du vrai vault source (faits réels, `MEMORY.md`, **sans `.git`**) dans `dest`.
2. Ajoute **30 domaines synthétiques**, chacun de `random(min, max)` faits (seed fixe →
   reproductible). Chaque fait : frontmatter valide (`name` unique
   `synth-d07-f0123`, `description` **discriminante** synthétique, `metadata.type: project`), corps
   de remplissage court.
3. N'écrit **pas** d'index (reshard les régénère). Laisse `dest` prêt pour `reshard.py`.

La source par défaut est le clone `~/.shared-memory/vaults/negocian-memory` ; `dest` est jetable.

## Algorithme de split (déterministe, récursif)

Pour un nœud de `M` faits triés par `name`, paramètre `N` :

- `M ≤ N` → **feuille** : faits à plat, index = `M` lignes compactes.
- `M > N` → `k = ceil(M / N)` buckets **contigus équilibrés** (préserve l'ordre alphabétique → labels
  ordonnés et lisibles) ; si `k > N`, on **récurse** sur la liste des buckets (niveau intermédiaire).
  Profondeur émergente 1…D, aucun plafond. Faits déplacés en `<domaine>/part-xx/.../<fait>.md`.

Capacité : N=150 → 2 niveaux ≈ 22 500 faits, 3 ≈ 3,4 M. Le test force la récursion avec un N petit.

## Flux de données

```
gen-synth-vault.py  →  copie(negocian-memory) + 30 domaines × 120-500 faits  →  dest/ (faits à plat)
reshard.py dest/    →  déplace les faits des domaines > N en part-xx/ (récursif)
                       régénère index/** + MEMORY.md (tous ≤ N lignes)
vérif               →  assert: chaque index/** ≤ N lignes ; aucun fait perdu ; récursion présente
build-viewer        →  l'arbre N-niveaux s'affiche dans le viewer
```

## Test & vérification

### `tests/test_reshard.py` (unittest, petits cas en tmp)

- domaine de **N+1** faits → split 1 niveau : sous-dossiers `part-xx`, chaque index feuille ≤ N,
  index parent = pointeurs, faits déplacés sur disque ;
- domaine de **N²+1** faits → **2 niveaux** (vérifie la récursion) ;
- domaine **≤ N** → reste plat (aucun sous-dossier créé) ;
- **conservation** : nombre de faits identique avant/après, chaque fait atteignable par exactement
  un pointeur de feuille ;
- **idempotence** : un 2ᵉ run ne déplace rien et produit des index identiques ;
- `MEMORY.md` liste les domaines de premier niveau.

Le `embed_fn`/réseau ne sont pas concernés (reshard est pur fichiers).

### Vérification à l'échelle (script de vérif, hors suite unittest)

Sur la copie générée : reshard `--max-entries 25` (force la récursion multi-niveaux) → **assert**
que tout `index/**` a ≤ 25 lignes et qu'il existe au moins un index de profondeur ≥ 2 ; puis reshard
`--max-entries 150` (réaliste) ; puis `build-viewer` pour confirmer le rendu de l'arbre.

## Câblage skills / convention

- **`docs/domain-convention.md`** : préciser que le redécoupage est porté par `scripts/reshard.py` —
  « le skill **détecte** (index qui approche N) et **propose** `reshard.py` ; l'humain valide le
  déplacement ». reshard = filet de sécurité de lisibilité ; la sémantique des sous-domaines
  (renommage `part-xx` → libellé signifiant) reste humaine.
- **`skills/memory-import`** : après écriture d'un fait, **régénérer les index via `reshard.py`**
  (qui reconstruit l'index compact) ; si un domaine franchit ~N, **proposer** le split (déplacement)
  et l'exécuter sur consentement.
- **`skills/memory-promote`** : avant le commit, lancer `reshard.py` pour tenir les index à jour ;
  inclure les **fichiers déplacés** (faits + `index/**` + `MEMORY.md`) dans le `git add`.

## Décisions clés (récapitulatif)

1. Invariant unique « ≤ N faits directs et ≤ N sous-dossiers par dossier » (N défaut 150) → tout
   index ≤ N lignes.
2. `reshard.py` : restructure (déplace seulement si violation, idempotent) + régénère tous les index
   et `MEMORY.md` ; devient le moteur unique de génération d'index.
3. Split déterministe : buckets contigus équilibrés par `name`, récursif sans plafond, labels
   mécaniques `part-xx` (renommables par l'humain ensuite).
4. `gen-synth-vault.py` : copie du vrai vault (sans `.git`) + 30 domaines × 120-500 faits (seed fixe).
5. Sûreté : le vrai `negocian-memory` n'est jamais touché ; tout se fait sur une copie jetable.
6. Vérif : unittest (récursion, conservation, idempotence) + test à l'échelle (N=25 force la
   récursion, tout index ≤ N) + rendu viewer.
7. Câblage : convention + `memory-import`/`memory-promote` détectent et appellent reshard (split sur
   consentement humain).

## Hors scope / évolutions

- Split **sémantique** (regrouper par sens plutôt que par tranche alphabétique) — reste humain ;
  reshard ne fait que le filet mécanique.
- Restructuration **incrémentale fine** préservant des libellés humains au-delà du « ne pas toucher
  un sous-arbre conforme » — suffisant ici.
- Réécriture des `[[liens]]` : inutile (liens par slug, indépendants du chemin).
