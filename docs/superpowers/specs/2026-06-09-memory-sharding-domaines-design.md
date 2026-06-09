# Design — Mémoire shardée par domaine (index hiérarchique)

**Date :** 2026-06-09
**Statut :** Design validé (V1), prêt pour le plan d'implémentation
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)

## Contexte et problème

La mémoire native de Claude Code fonctionne déjà à deux niveaux :

| Niveau | Quoi | Chargement | Plafond |
|---|---|---|---|
| **Auto** | `MEMORY.md` | injecté à chaque démarrage de session | **200 lignes / 25 KB — dur** |
| **À la demande** | tous les autres `.md` | lus par `Read` quand nécessaire | illimité |

*(Source : doc officielle Claude Code — `MEMORY.md` chargé à hauteur de 200 lignes ou 25 KB, premier atteint ; les autres fichiers lus à la demande via file tools.)*

Le plugin `shared-memory` utilise aujourd'hui `MEMORY.md` comme **catalogue exhaustif** : une entrée par fait (O(N)). Conséquence : l'index sature le plafond vers **~50 faits**, bien avant que git ne pose problème. À cela s'ajoute un point de **conflit git permanent** (tout le monde édite le même `MEMORY.md`).

Faits confirmés écartés comme non pertinents ici : le **recall automatique** (injection de faits dans des `system-reminder`) n'est **pas documenté** et son comportement vis-à-vis des sous-dossiers est incertain ; les **wikilinks `[[ ]]`** n'ont **aucun rôle fonctionnel** confirmé. Le design ne dépend donc d'aucun des deux.

## Principe fondateur

`MEMORY.md` cesse d'être un catalogue (O(N faits)) pour devenir une **table des matières** (O(domaines), ~10-20 lignes stables). La navigation est **explicite et déterministe**, pilotée par l'index via `Read` — sans dépendre du recall automatique.

## Architecture : index à 2 niveaux

| Niveau | Fichier | Rôle | Chargement |
|---|---|---|---|
| 0 | `MEMORY.md` | **carte des domaines** : nom, compte, 1 phrase, pointeur `→ index/<d>.md` | auto (≤ ~150 lignes) |
| 1 | `index/<domaine>.md` | **sous-index** : liste des faits du domaine + pointeurs | à la demande |
| 2 | `<domaine>/<fait>.md` | **le fait** | à la demande |

`MEMORY.md` contient une instruction explicite : *« pour un sujet donné, lis d'abord `index/<domaine>.md` »*.

**Règle de seuil récursive (auto-équilibrage) :** aucun fichier d'index ne dépasse ~150 lignes.
- Un sous-index > ~150 faits → scindé en sous-domaines (`index/<domaine>/<sous>.md`).
- La carte > ~150 domaines → regroupement en familles.

Avec 2 niveaux : ~150 domaines × ~150 faits ≈ **22 000 faits adressables** en ne chargeant que ~20 lignes au démarrage. Le niveau 3 ne sera quasi jamais atteint.

## Structure de fichiers

```
vault/
├── MEMORY.md                    # carte des domaines (niveau 0)
├── index/
│   ├── mailing.md               # sous-index (niveau 1)
│   ├── ui.md
│   └── ecommerce.md
├── mailing/
│   └── audit.md                 # fait (niveau 2)
├── ui/
│   └── ux-audit.md
├── ecommerce/
│   └── tax-forms.md
├── feedback_no_commit.md        # perso : RESTE à la racine (local, recall auto préservé)
└── feedback_no_migrations.md
```

**Décision : les faits perso (`feedback`/`user`) ne sont pas shardés.** Ils restent à la racine, gardent le recall automatique (préférences souvent sollicitées) et leur statut local (gitignore). Le sharding ne concerne que les faits `project`/`reference` partagés.

## Flux de lecture (déterministe)

1. **Démarrage** → la carte (`MEMORY.md`) est injectée : Claude connaît les domaines et où chercher.
2. **Le sujet devient « mailing »** → Claude lit `index/mailing.md`.
3. **Fait pertinent repéré** → Claude lit `mailing/audit.md`.

Aucune dépendance au recall auto : tout passe par `Read` piloté par l'index.

## Taxonomie des domaines

**Domaines libres, créés à la volée** (pas de liste fixe). Garde-fous contre la prolifération :
- À la promotion, le skill **lit la carte existante et suggère un domaine proche** avant d'en créer un nouveau (évite `mailing` vs `emails` vs `mail`).
- Le reviewer (`/memory-review`) voit les nouveaux domaines et peut **fusionner/renommer**.

## Gestion du seuil : semi-automatique

Les skills (`/memory-promote`, `/memory-import`) détectent qu'un index approche ~150 lignes, **alertent et proposent** un découpage en sous-domaines ; **l'humain valide** (cohérent avec la gouvernance par revue existante).

## Impact sur les skills

| Skill | Changement |
|---|---|
| `/memory-promote` | Déduit/demande le domaine → suggère un domaine proche (garde-fou) → range dans `<domaine>/`, met à jour `index/<domaine>.md` (**plus `MEMORY.md`**) → crée domaine + ligne de carte si nouveau → vérifie le seuil et propose un découpage. |
| `/memory-review` | Voit les nouveaux domaines → fusion/renommage → valide un découpage proposé. |
| `/memory-import` | Range le fait normalisé dans le bon domaine. |
| `/memory-list` | Lit la carte puis le(s) sous-index pertinent(s). |
| `/memory-setup` | **Inchangé** (le symlink ne dépend pas de la structure interne). |
| `/memory-ui` | Régénère le viewer arborescent. |

**Bénéfice git :** chaque promotion touche `index/<son-domaine>.md` → fin des conflits systématiques sur `MEMORY.md`. La carte ne change qu'à la création d'un domaine (rare).

## Impact sur le viewer (UI — arbre de domaines)

- **`build-viewer.py`** : `os.listdir` → parcours récursif (`os.walk`/`rglob`) ; **domaine déduit du dossier parent** ; champ `domain` ajouté au JSON ; faits à la racine → domaine implicite `« général »`.
- **`viewer-template.html`** : sidebar = **arbre de domaines repliables** (domaine → faits) ; clic fait → détail ; **filtres par type** conservés en secondaire ; **recherche transverse** inchangée.

## Migration des faits existants (vault negocian)

```
mailing-audit.md                 → mailing/audit.md                    + index/mailing.md
tax-forms.md                     → ecommerce/tax-forms.md              + index/ecommerce.md
ui-ux-audit.md                   → ui/ux-audit.md                      + index/ui.md
dynamic-entities-permissions.md  → entites-dynamiques/permissions.md   ┐
champs-dynamiques-rendu-vue.md   → entites-dynamiques/champs-rendu-vue.md ┘ + index/entites-dynamiques.md
MEMORY.md                        → devient la carte des domaines
feedback_*.md                    → restent à la racine (locaux)
```

**Rétrocompatibilité :** viewer et skills gèrent le **mode mixte** (faits à la racine + faits en sous-dossiers). La migration peut être progressive ; rien ne casse si un fait reste à plat.

## Tests

- **`build-viewer.py`** : vault factice avec sous-dossiers → regroupement, comptes par domaine, déduction du domaine, mode mixte.
- **Skills** : `promote` crée `<domaine>/` + `index/<domaine>.md` + ligne de carte ; le seuil ~150 déclenche l'alerte ; la suggestion de domaine proche fonctionne.
- **Lecture pilotée** : la carte pointe vers des chemins `index/*.md` valides.

## Hors scope V1

- Découpage **automatique strict** (on reste en semi-auto avec validation humaine).
- Liste de domaines **fixe/curée** (on reste en domaines libres).
- Tout mécanisme de **recherche externe** (voir évolutions futures).

## Évolutions futures (performance & tokens — post-V1)

Pistes identifiées pour une V2 axée sur la réduction du coût en tokens et la performance, **une fois le sharding en place**. Non engagées ici.

1. **Densification des index** — budget token par ligne de carte/sous-index ; descriptions condensées et discriminantes pour maximiser l'information par token chargé.
2. **Digest par domaine** — un résumé condensé en tête de chaque sous-index, permettant de répondre à certaines questions **sans ouvrir chaque fait** (réduit les `Read` de niveau 2).
3. **Cache de session** — mémoïser les sous-index déjà lus dans une session pour éviter des relectures.
4. **Working set chaud/froid** — prioriser les faits récents/actifs dans la carte ; archiver le froid plus profond.
5. **Compaction périodique** — fusion des faits redondants, péremption des faits datés (on a déjà observé des faits périmés : `mailing-audit`, `tax-forms`).
6. **Recherche externe (MCP / vectoriel)** — cible long terme si le volume dépasse quelques milliers de faits : un outil `search_memory(query)` hors contexte, avec embeddings **locaux** pour préserver la confidentialité des vaults. Romprait le principe « fichiers + git sans infra » — à n'envisager qu'à cette échelle.

## Décisions clés (récapitulatif)

1. `MEMORY.md` = table des matières des domaines, pas catalogue de faits.
2. Lecture **pilotée par l'index** (déterministe), pas de dépendance au recall auto.
3. Faits rangés en **sous-dossiers physiques** par domaine (`Read` suit les chemins).
4. Seuil **semi-auto** à ~150 lignes : alerte + proposition, validation humaine.
5. Domaines **libres à la volée** + garde-fous anti-prolifération.
6. Viewer : **arbre de domaines** en sidebar.
7. Faits perso **non shardés** (restent à la racine).
