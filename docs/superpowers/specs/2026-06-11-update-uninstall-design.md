# Design — Mise à jour & désinstallation du plugin

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** « consolider la mémoire centrale » — chantier 4/5 (maintenance dans la durée).

## Objectif

`install.sh` installe, mais rien ne documente la **mise à jour** ni ne permet une **désinstallation
propre**. Le setup crée par projet un **symlink** (`~/.claude/projects/<slug>/memory → clone`) et une
**entrée de registre** `registry.json` ; par machine, `install.sh` crée `~/.shared-memory/plugin` +
les caches. Ce chantier fournit l'**inverse** : débrancher un projet et désinstaller la machine, en
**conservant les données** (clones de vault) par défaut.

## Décisions (validées en brainstorming)

1. **Deux niveaux** : (a) débranchement par projet — skill `/memory-unsetup` ; (b) désinstallation
   machine — `scripts/uninstall.sh`.
2. **Données conservées par défaut** : le clone du vault (possiblement des brouillons non promus)
   n'est jamais supprimé sans `--purge` explicite.
3. **Sécurité** : ne retirer un dossier mémoire que **si c'est un symlink** (`[ -L ]`) — jamais une
   vraie mémoire locale.
4. **Mise à jour = relancer `install.sh`** (qui fait déjà `git pull`) + `/reload-plugins` :
   documentation, pas de nouveau code.
5. **Fonctions lib testables** réutilisées par les deux scripts (cohérent avec l'existant).

## Architecture / composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/lib.sh` | `sm_symlink_for_slug`, `sm_registry_slugs`, `sm_unregister`. | Modifier |
| `scripts/unlink-vault.sh` | débrancher le projet courant (inverse de `setup-vault.sh`). | Créer |
| `scripts/uninstall.sh` | désinstallation machine (débranche tout + retire plugin/caches). | Créer |
| `skills/memory-unsetup/SKILL.md` | skill de débranchement par projet. | Créer |
| `tests/test_uninstall.py` | unitaires lib + intégration `unlink-vault.sh`. | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md` | documenter. | Modifier |

### `scripts/lib.sh` (3 fonctions)

- `sm_symlink_for_slug <slug>` → imprime le champ `symlink` de l'entrée registre du slug (vide si
  absente) ; renvoie 1 s'il n'y a pas de registre. (Calque `sm_vault_clone_for_slug`.)
- `sm_registry_slugs` → imprime chaque `slug` enregistré, un par ligne (vide si pas de registre).
- `sm_unregister <slug>` → réécrit `registry.json` sans l'entrée du slug. **Idempotent** (no-op si
  absente ou pas de registre), best-effort.

### `scripts/unlink-vault.sh <project-dir>`

1. `slug = sm_slug(project-dir)`. Absent du registre → afficher « projet non branché », exit 0.
2. `sym = sm_symlink_for_slug(slug)` → **retirer uniquement si `[ -L "$sym" ]`** (si c'est un vrai
   dossier : avertir, ne pas toucher).
3. `sm_unregister(slug)`.
4. Récap : symlink retiré, entrée nettoyée, **clone conservé** à `<clone>` (re-brancher via
   `/memory-setup`). Exit 0 (best-effort).

### `skills/memory-unsetup/SKILL.md`

Localise le projet ; non branché → le dire. **Confirme** (AskUserQuestion) → lance
`unlink-vault.sh` → rappelle que le clone est gardé (`/memory-setup` pour re-brancher,
`uninstall.sh` pour tout retirer).

### `scripts/uninstall.sh [--purge] [--yes]` (terminal)

1. **Confirmation** interactive (`read`) sauf `--yes`.
2. **Débrancher tous** : `for slug in $(sm_registry_slugs)` → retirer le symlink si `[ -L ]` +
   `sm_unregister`.
3. Supprimer `~/.shared-memory/plugin` (= `SHARED_MEMORY_HOME`) + caches `models/`, `embeddings/`.
4. **Garder `vaults/` (clones) par défaut.** `--purge` → supprimer aussi `vaults/`, le registre et
   tout `~/.shared-memory`, **après avertissement** « brouillons non promus perdus ».
5. Guide : dans Claude Code, `/plugin uninstall shared-memory` (un script ne peut pas le faire).

### Mise à jour

`install.sh` met **déjà** à jour le plugin (`git -C "$DEST" pull --ff-only` si déjà cloné). « Update »
= relancer `install.sh` + `/reload-plugins`. **Documenté** dans INSTALL ; aucun nouveau code.

## Doc & tests (convention du programme)

**Tests — `tests/test_uninstall.py`** (`unittest`, bash réel comme `tests/test_setup.py`) :
- `sm_unregister` : registre à 2 projets → en retirer un → l'autre reste, la cible disparaît ;
  **idempotent** ; pas de registre → no-op (pas d'erreur).
- `sm_symlink_for_slug` : renvoie le `symlink` du slug ; vide pour un slug inconnu.
- `sm_registry_slugs` : liste tous les slugs enregistrés.
- **Intégration `unlink-vault.sh`** : projet temporaire avec un **vrai symlink** + entrée registre →
  après lancement : symlink retiré, entrée nettoyée, **clone (vrai dossier) intact**. **Sécurité** :
  si le chemin « symlink » est en réalité un **vrai dossier**, il n'est **pas** supprimé.

**Doc :**
- `INSTALL.md` — section **« Mise à jour »** (relancer `install.sh` + `/reload-plugins`) + section
  **« Désinstallation »** (par projet `/memory-unsetup` ; machine `uninstall.sh [--purge]` ; puis
  `/plugin uninstall`).
- `README.md` — ligne `/memory-unsetup` dans le tableau des skills.
- `docs/ARCHITECTURE.md` **§16 (nouvelle)** — « Mise à jour & désinstallation » (inverse exact du
  setup ; symlink + registre défaits ; données conservées par défaut).

## Hors scope / évolutions

- **Suppression des clones sans `--purge`** : exclue (données / brouillons non promus).
- **Désinstallation du plugin dans Claude Code** (`/plugin uninstall`) : un script ne peut pas la
  lancer → on guide l'utilisateur.
- **Restauration d'un dossier mémoire natif** après débranchement : hors scope ; retirer le symlink
  suffit (la mémoire native est recréée à la demande). Une vraie mémoire locale n'est jamais touchée.
- **Migration de données entre versions** : hors scope (les faits sont des `.md` stables).

## Décisions clés (récapitulatif)

1. `lib.sh` : `sm_symlink_for_slug` / `sm_registry_slugs` / `sm_unregister` (testables) ;
   `unlink-vault.sh` + skill `/memory-unsetup` (par projet) ; `uninstall.sh` (machine).
2. Données conservées par défaut ; `--purge` explicite pour tout supprimer ; symlink retiré seulement
   si `[ -L ]`.
3. Mise à jour = relancer `install.sh` (déjà un `git pull`) ; documenté, pas de code.
4. Doc (INSTALL maj/désinstall, README, ARCHITECTURE §16) + tests (`test_uninstall.py`).
