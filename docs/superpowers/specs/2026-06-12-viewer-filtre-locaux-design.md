# Design — Filtre « locaux » dans le viewer

**Date :** 2026-06-12
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Origine :** confort d'usage — depuis l'ajout du drapeau `metadata.local: true`, on veut pouvoir
**n'afficher que les faits locaux** dans le viewer (le badge existe déjà, mais pas de filtre).

## Décision (validée en brainstorming)

Un **toggle « locaux »** (filtre sur un axe distinct des types), en **AND** avec le filtre par type.
Pas de troisième état « masquer les locaux » (YAGNI) — juste « locaux seulement » vs « tout ».

## Modèle

- **État** : nouveau booléen `state.localOnly` (défaut `false` → on montre tout, comportement actuel
  inchangé).
- **`visible()`** : aujourd'hui `DATA.facts.filter(f => state.types.has(f.type))`. Devient
  `DATA.facts.filter(f => state.types.has(f.type) && (!state.localOnly || f.local))`. Quand le toggle
  est actif, seuls les faits `local: true` (et dont le type est coché) restent visibles.
- **Chip** : un chip « locaux » ajouté **après** les chips de type dans la barre `.filters`
  (`renderFilters`), visuellement distinct (point de couleur `--faint`, comme le badge `local`). Au
  clic : bascule `state.localOnly`, classe `.off` quand inactif (cohérent avec les chips de type),
  puis `rebuildNav()` + `update()` (comme les chips de type).
- **Arbre & comptes** : `rebuildNav` s'appuie déjà sur `visible()` → l'arbre du sidebar et les
  comptes se restreignent automatiquement aux locaux quand le toggle est actif. Rien à changer.

## Composant

| Fichier | Rôle | Action |
|---|---|---|
| `assets/viewer-template.html` | `state.localOnly`, `visible()`, chip dans `renderFilters`. | Modifier |
| `tests/test_serve_viewer.py` | assertion sur le template rendu (présence du toggle). | Modifier |

## Tests

- **`tests/test_serve_viewer.py`** : assertion que le template contient le marqueur du toggle
  (`localOnly`) — façon `TemplateLocalUITest`. Pas de test navigateur (pas d'infra JS en CI).
- **`node --check`** du JS rendu (placeholder `/*__DATA__*/` → JSON minimal) pour garantir que le
  script reste valide.
- Le reste (rendu visuel du chip, bascule) : **vérification visuelle**.

## Hors scope

- Troisième état « masquer les locaux » : YAGNI.
- Persistance du filtre entre sessions : non (état en mémoire, comme les chips de type).
- Filtre « locaux » dans les résultats de recherche serveur : `visible()` couvre les vues client ;
  la recherche serveur garde son comportement (le badge y est déjà présent).

## Décision clé

Toggle `state.localOnly` en AND avec les types dans `visible()` ; chip distinct dans `renderFilters` ;
l'arbre se restreint automatiquement via `visible()`. Défaut `false` (compat : comportement inchangé).
