# Design — Lint & normalisation des faits (`/memory-lint`)

**Date :** 2026-06-11
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** « consolider la mémoire centrale » — chantier 1/5 (qualité des données).

## Objectif

Garantir un **format de fait propre et homogène** dans le temps. Le vault réel contient déjà
**deux formats de frontmatter** coexistants (`type:` à plat **et** bloc `metadata:`), et rien ne
**valide** un fait (champs requis, `name` unique, date bien formée). Sans garde-fou, la dérive
s'accumule silencieusement. `/memory-lint` **détecte** les problèmes, **corrige mécaniquement** la
seule dérive sûre (format à plat → bloc `metadata:`), et **signale** le reste pour décision humaine.

## Décisions (validées en brainstorming)

1. **Rapport + fix opt-in** : le lint liste tout, n'applique que les corrections **mécaniques sûres**
   et **seulement après confirmation**. Les manques de jugement restent à l'humain. (Cohérent avec la
   règle « signaler, confirmer avant d'écrire » du projet.)
2. **Skill dédié `/memory-lint`** (surface utilisateur) + **moteur testable `scripts/lint.py`** ; le
   moteur est aussi **réutilisé par `/memory-promote`** (garde-fou avant push).
3. **Format canonique = bloc `metadata:` imbriqué** (conforme à `assets/fact-template.md` et
   `docs/domain-convention.md`). Le `type:`/`reviewed:` à plat est la forme dérivée à rattraper.
4. **Une seule auto-correction** : `flat_frontmatter`. Tout le reste est **signalé**, jamais réécrit.

## Architecture / composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/lint.py` | moteur pur (lint + fix), CLI. | Créer |
| `skills/memory-lint/SKILL.md` | surface utilisateur (rapport → confirmation → fix). | Créer |
| `tests/test_lint.py` | tests unitaires du moteur. | Créer |
| `skills/memory-promote/SKILL.md` | appeler `lint_vault`, signaler les erreurs avant push. | Modifier |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md`, `docs/domain-convention.md` | documenter. | Modifier |

**Moteur `scripts/lint.py`** (stdlib seule ; réutilise `parse_md`/`collect_facts` de `build-viewer.py`
via `importlib`, comme `digest.py`/`serve-viewer.py`) :

- `lint_vault(vault) -> list[Finding]` — parcourt les faits, applique le catalogue, renvoie une liste
  de **findings**.
- Un **Finding** est un dict `{file, rule, severity, fixable, message}` :
  - `severity ∈ {"error", "warn"}`,
  - `fixable ∈ {True, False}`,
  - `file` = chemin relatif au vault, `rule` = identifiant de règle, `message` = texte lisible.
- `format_report(findings) -> str` — rapport lisible, **groupé par sévérité** (erreurs avant
  avertissements) puis par fichier ; en-tête avec les comptes (`N erreur(s), M avertissement(s)`).
- `apply_fixes(vault, findings) -> int` — applique **uniquement** les findings `fixable=True`
  (corrections mécaniques), renvoie le nombre de faits corrigés. N'écrit **jamais** pour `fixable=False`.
- CLI : `python3 lint.py <vault>` → imprime le rapport (n'écrit rien) ; `python3 lint.py <vault> --fix`
  → applique les corrections mécaniques puis imprime le bilan.

Le moteur distingue le **placement brut** des clés via `parse_md` : une clé sous le bloc `metadata:`
ressort en `metadata.type` ; une clé de premier niveau ressort en `type`. `flat_frontmatter` se
déclenche quand `type`/`reviewed` existent **à plat** (clé `type`/`reviewed` présente, `metadata.type`
absente) ; dans ce cas `missing_type` ne se déclenche **pas** (le type existe, il est juste mal placé).

## Catalogue de règles

| Règle | Sévérité | Auto-fix | Détail |
|---|---|---|---|
| `frontmatter_invalid` | error | non | pas de bloc `---…---` parsable |
| `missing_name` | error | non | `name` absent ou vide |
| `missing_description` | error | non | `description` absent ou vide |
| `missing_type` | error | non | ni `metadata.type` ni `type` |
| `invalid_type` | error | non | type ∉ {`project`, `reference`, `user`, `feedback`} |
| `duplicate_name` | error | non | même `name` sur ≥2 faits (casse les pointeurs) |
| `flat_frontmatter` | warn | **oui** | `type:`/`reviewed:` à plat → bloc `metadata:` canonique |
| `reviewed_missing` | warn | non | pas de `reviewed` (on n'invente pas la date) |
| `reviewed_malformed` | warn | non | `reviewed` présent mais ≠ `AAAA-MM-JJ` |
| `short_description` | warn | non | description < 5 mots |
| `name_not_slug` | warn | non | `name` non kebab-case (renommer casse les pointeurs) |
| `broken_wikilink` | warn | non | `[[x]]` sans fait `x` existant dans le vault |
| `personal_misplaced` | warn | non | fait `user`/`feedback` (ou `feedback_*.md`) **hors racine** |

Précisions :
- **`flat_frontmatter` = seule correction mécanique.** `apply_fixes` réécrit le frontmatter en
  déplaçant `type`/`reviewed` sous un bloc `metadata:`, en **préservant** `name`, `description`,
  toute autre clé et le corps. **Idempotent** : un re-lint après fix ne re-signale plus la règle.
- **`duplicate_name`** est détecté à l'échelle du vault (deux fichiers, même `name`) ; les deux faits
  sont signalés. Non auto-corrigé (lequel renommer = jugement).
- **`name_not_slug`** : avertissement seulement — renommer casserait les pointeurs (`index/**`,
  wikilinks). La convention recommande un slug kebab-case ; le lint le rappelle sans l'imposer.
- **`personal_misplaced`** : la convention veut les faits perso **à la racine** (jamais dans un
  domaine, jamais partagés). Détecté quand un fait `user`/`feedback` (ou un `feedback_*.md`) se trouve
  dans un sous-dossier. Non auto-déplacé (déplacer touche les index/pointeurs).
- **Faits perso à la racine** : ils sont correctement placés ; ils s'affichent sous « général » dans
  le digest — c'est un sujet **d'affichage**, hors scope de ce chantier (voir Hors scope).

## Flux du skill `/memory-lint`

1. **Localiser le vault** (`lib.sh : sm_vault_clone_for_slug`). Absent → demander `/memory-setup`.
2. **Lancer le lint** : `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint.py "<clone>"`.
3. **Présenter le rapport** (erreurs d'abord, puis avertissements ; comptes en tête).
4. **S'il existe des findings `fixable`** : présenter ce qui sera corrigé (les `flat_frontmatter`) et
   **demander l'accord** (AskUserQuestion, un seul accord groupé façon `/memory-seed`). Sans accord :
   ne rien écrire.
5. **Appliquer** : `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint.py "<clone>" --fix`, puis régénérer
   les index si des fichiers ont changé : `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py "<clone>"`.
6. **Rappeler** que les **avertissements** (description courte, name non-slug, wikilinks cassés,
   perso mal placé) sont à traiter **à la main** (ou via le viewer), et renvoyer vers `/memory-promote`
   quand le vault est propre.

## Intégration `/memory-promote`

Avant le push, `/memory-promote` appelle `lint_vault` sur le clone. **S'il existe des erreurs**
(`severity=error`), les afficher et **demander** s'il faut corriger d'abord — **advisory, pas de
blocage dur** (cohérent avec le ton du projet : signaler, laisser l'humain décider). Les
avertissements sont mentionnés mais ne retardent pas la promotion.

## Doc & tests (convention du programme)

**Tests — `tests/test_lint.py`** (`unittest`, import `importlib`) :
- Chaque règle : un fait fabriqué qui la viole → finding attendu (sévérité/fixable corrects) ; un
  fait **propre** → aucun finding (pas de faux positif).
- `duplicate_name` détecté sur deux fichiers de même `name`.
- `flat_frontmatter` : `apply_fixes` convertit plat → bloc `metadata:`, préserve name/description/
  corps, et un **re-lint est propre** (idempotent).
- `apply_fixes` ne touche **que** les `fixable=True` (un `name_not_slug` reste intact après fix).
- `broken_wikilink` : `[[inconnu]]` → finding ; `[[fait-existant]]` → rien.
- `personal_misplaced` : `feedback` dans `ui/x.md` → finding ; à la racine → rien.
- `format_report` groupe par sévérité.
- CLI : run simple n'écrit rien ; `--fix` applique et rapporte le nombre corrigé.

**Doc :**
- `docs/ARCHITECTURE.md` **§13 (nouvelle)** — « Lint & normalisation des faits » : format canonique,
  rapport + fix opt-in, intégration promote.
- `docs/domain-convention.md` — rendre explicite le **format canonique** (bloc `metadata:`) et la
  note « `name` = slug kebab-case », en pointant `/memory-lint` comme rattrapage.
- `README.md` — ligne `/memory-lint` dans le tableau des skills + une puce « Sous le capot ».
- `INSTALL.md` — `/memory-lint` dans les commandes utiles.

## Hors scope / évolutions

- **Affichage perso séparé** : grouper les faits `user`/`feedback` dans leur propre section du digest
  (au lieu de « général ») — micro-ajustement du digest, chantier séparé si souhaité.
- **Auto-stampage de `reviewed`** : non — dater un fait est un jugement (mtime ≠ vérifié contre le
  code). Le lint **signale** l'absence ; `/memory-promote` stampe `reviewed` quand un fait est
  confirmé vrai (comportement existant).
- **Renommage automatique** (slug, doublons) et **déplacement** des perso : exclus (cassent les
  pointeurs/index ; jugement humain).
- **Blocage dur de la promotion** sur erreur : exclu (advisory uniquement).

## Décisions clés (récapitulatif)

1. `scripts/lint.py` (moteur pur testable) + skill `/memory-lint` + intégration advisory dans promote.
2. Rapport + fix **opt-in** ; **seule** auto-correction = `flat_frontmatter` (plat → `metadata:`).
3. Catalogue de 13 règles (6 erreurs, 7 avertissements dont 1 auto-fixable).
4. Format canonique = bloc `metadata:` ; doc + tests à jour (convention du programme).
