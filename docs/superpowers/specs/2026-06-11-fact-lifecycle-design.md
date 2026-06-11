# Design — Cycle de vie des faits périmés (`stale.py` + `/memory-refresh`)

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** « consolider la mémoire centrale » — chantier 3/5 (fraîcheur active).

## Objectif

La fraîcheur **signale** (`⚠` si `reviewed` ≥ 90 j ou absent) dans le digest et le viewer, mais rien
n'aide à **agir**. Les faits canoniques qui vieillissent dans `main` ne sont jamais re-vérifiés
(`/memory-promote` ne re-stampe que les faits locaux nouveaux/modifiés). Ce chantier **ferme la
boucle** : signaler → **vérifier** → **re-stamper** (ou corriger / retirer).

## Décisions (validées en brainstorming)

1. **File de re-vérification + re-stamp** : un skill liste les périmés et, pour chaque fait
   re-vérifiable, le confronte au code → re-stampe `reviewed` si encore vrai, propose correction ou
   retrait sinon. Brouillons (étage 1) → `/memory-promote`. Pas d'archivage automatique (perte de
   savoir silencieuse exclue).
2. **Moteur centralisé `scripts/stale.py`** = **source unique** de la péremption (STALE_DAYS=90).
   `digest.py` réutilise son `is_stale` au lieu de sa copie locale (DRY ; les tests de digest
   restent verts car ils testent la sortie, pas `_is_stale`).
3. **Re-vérification = project/reference** (confrontables au code). Les faits **perso**
   (`user`/`feedback`) périmés sont **listés à juger** (pas de code à vérifier).

## Architecture / composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/stale.py` | moteur péremption (`is_stale`, `days_old`, `stale_facts`, `set_reviewed`) + CLI. | Créer |
| `tests/test_stale.py` | unitaires du moteur. | Créer |
| `scripts/digest.py` | réutiliser `stale.is_stale` (DRY). | Modifier |
| `skills/memory-refresh/SKILL.md` | le skill de re-vérification. | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md`, `docs/domain-convention.md` | documenter. | Modifier |

**`scripts/stale.py`** (stdlib seule ; réutilise `collect_facts`/`parse_md` de `build-viewer.py` via
`importlib`, comme `digest.py`) :

- `STALE_DAYS = 90`.
- `is_stale(reviewed, today) -> bool` — `True` si `reviewed` absent/illisible OU
  `(today - reviewed).days >= STALE_DAYS`. (Déplacé depuis `digest._is_stale`.)
- `days_old(reviewed, today) -> int` — ancienneté en jours ; **sentinelle haute** (ex. `10**9`) si
  `reviewed` absent/illisible, pour que les non-datés trient en tête.
- `stale_facts(vault, today=None) -> list` — via `collect_facts`, filtre les faits `is_stale` et les
  renvoie **triés par `days_old` décroissant** (plus vieux / non-datés d'abord). Chaque entrée est le
  dict du fait (file/name/description/type/reviewed/domain) enrichi de `days_old`.
- `set_reviewed(text, date) -> str` — réécrit le frontmatter pour fixer `reviewed=date` sous le bloc
  `metadata:` canonique : met à jour la ligne `reviewed:` existante, ou l'ajoute sous `metadata:` si
  absente. Préserve name/description/autres clés/corps. **Testable**.
- CLI :
  - `python3 stale.py <vault>` → liste lisible des périmés (ancienneté + nom + domaine + type).
  - `python3 stale.py --restamp <fichier> [date]` → applique `set_reviewed` au fichier (date = jour
    courant par défaut), écrit le fichier.

**DRY `digest.py`** : charger `stale.py` via importlib et remplacer le corps de `_is_stale` par un
appel à `stale.is_stale` (ou appeler `stale.is_stale` directement). Comportement inchangé.

## Flux du skill `/memory-refresh`

1. **Localiser le vault** (`lib.sh : sm_vault_clone_for_slug`). Absent → demander `/memory-setup`.
2. **Lister les périmés** : `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/stale.py "<clone>"`. Séparer
   **project/reference** (re-vérifiables) des **perso** (`user`/`feedback`, à juger).
3. **Rien de périmé** → le dire et s'arrêter.
4. **Pour chaque fait project/reference périmé** (plus vieux d'abord ; si beaucoup, proposer un
   **sous-ensemble** — par domaine ou les N plus vieux — pour garder la session focalisée) :
   - le **confronter au code actuel** (Read/Grep/Glob) : encore vrai ? non contredit ?
   - **encore vrai** → `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/stale.py --restamp "<fichier>"` ;
   - **faux** → proposer **corriger** (éditer le corps + re-stamper) ou **retirer** (supprimer le
     fichier ; une suppression se propage via `/memory-promote` → `/memory-review`).
5. **Faits perso périmés** → les **lister à juger** (préférence, pas de code à vérifier) ; re-stamper
   seulement sur confirmation qu'ils tiennent encore.
6. **Confirmer le lot** avant d'écrire (AskUserQuestion) : récap « N re-stampés · M corrigés · K
   retirés ». Rien sans accord.
7. **Appliquer**, puis `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py "<clone>"` si des fichiers
   ont changé, et **renvoyer vers `/memory-promote`** (les changements sont des brouillons étage 1).

## Doc & tests (convention du programme)

**Tests — `tests/test_stale.py`** (`unittest`) :
- `is_stale` : absent → vrai ; récent (< 90 j) → faux ; **frontière 89 j faux / 90 j vrai** ;
  date illisible → vrai.
- `days_old` : récent → bon nombre de jours ; absent/illisible → sentinelle haute.
- `stale_facts` : vault mixte → ne renvoie que les périmés, **triés du plus vieux au plus récent**
  (non-datés en tête) ; un fait frais est exclu.
- `set_reviewed` : `reviewed` existant sous `metadata:` → **valeur mise à jour** ; `metadata:` sans
  `reviewed` → **ajouté** ; name/description/corps **préservés**.
- CLI `--restamp <fichier>` : réécrit le fichier avec la nouvelle date (vérifier le contenu).
- **DRY** : la suite `test_digest` existante reste verte (digest réutilise `stale.is_stale`).

**Doc :**
- `docs/ARCHITECTURE.md` **§15 (nouvelle)** — « Cycle de vie des faits / re-vérification » (boucle
  signaler → vérifier → re-stamper/retirer ; `stale.py` + `/memory-refresh`).
- `docs/domain-convention.md` — dans « Fraîcheur des faits », une ligne renvoyant à `/memory-refresh`.
- `README.md` — ligne `/memory-refresh` (tableau des skills) + une puce « Sous le capot ».
- `INSTALL.md` — `/memory-refresh` dans les commandes utiles.

## Hors scope / évolutions

- **Archivage / suppression automatique** des vieux faits : exclu (perte de savoir silencieuse).
- **Re-vérification automatique sans humain** : exclue ; confronter un fait au code et décider
  corriger/retirer est un **jugement** (le skill propose, l'humain valide).
- **Auto-stampage en masse à aujourd'hui** : exclu — re-stamper signifie « j'ai vérifié », pas « le
  fichier existe ». On ne re-stampe qu'après confrontation au code.
- **Seuil configurable** (autre que 90 j) : hors scope ; `STALE_DAYS` reste une constante unique.

## Décisions clés (récapitulatif)

1. `scripts/stale.py` (source unique : `is_stale`/`days_old`/`stale_facts`/`set_reviewed` + CLI
   liste/`--restamp`) ; `digest.py` réutilise `is_stale` (DRY).
2. Skill `/memory-refresh` : liste les périmés → confronte project/reference au code → re-stampe /
   corrige / retire ; perso listés à juger ; confirmation avant écriture ; brouillons → promote.
3. Pas d'archivage auto, pas de re-stampage sans vérification.
4. Doc (ARCHITECTURE §15, convention, README, INSTALL) + tests (`test_stale.py`, digest reste vert).
