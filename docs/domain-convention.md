# Convention — Mémoire shardée par domaine

Référence commune aux skills `memory-import`, `memory-promote`, `memory-list`, `memory-review`.
Le vault n'est plus plat : les faits sont rangés **par domaine**, et l'index est **hiérarchique**.

## Structure du vault

```
vault/
├── MEMORY.md              # carte des domaines (niveau 0) — chargée au démarrage, garder ≤ ~150 lignes
├── index/
│   └── <domaine>.md       # sous-index (niveau 1) — liste les faits du domaine, lu à la demande
├── <domaine>/
│   └── <fait>.md          # le fait (niveau 2)
└── <fait>.md              # fait à la racine → domaine implicite « général »
```

- **`MEMORY.md` (carte)** : une ligne par domaine, avec un pointeur `→ index/<domaine>.md`, plus une section « Général » pour les faits restés à la racine, plus éventuellement des « Patterns & Conventions » transverses. Ne JAMAIS y lister chaque fait (ce serait revenir à l'index plat).
- **`index/<domaine>.md` (sous-index)** : une **section par fait** — titre + type + 1-3 lignes de résumé + pointeur `→ <domaine>/<fait>.md`.
- **Faits perso** (`metadata.type: user`/`feedback`, fichiers `feedback_*.md`) : **restent à la racine**, jamais rangés en domaine, jamais partagés.

## Ranger un fait dans un domaine

1. **Déduire le domaine** du sujet du fait (ex. emails → `mailing`, fiscalité → `ecommerce`).
2. **Garde-fou anti-prolifération** : lire la carte `MEMORY.md` et, si un domaine existant est proche (`mailing` vs `emails` vs `mail`), **proposer le domaine existant** plutôt que d'en créer un nouveau. Demander à l'utilisateur en cas de doute.
3. Écrire le fait dans `<domaine>/<fait>.md`.
4. **Mettre à jour le sous-index** `index/<domaine>.md` (ajouter la section du fait). Le créer s'il n'existe pas.
5. Si le domaine est **nouveau**, ajouter sa ligne dans la carte `MEMORY.md` (section « Domaines »).

## Seuil de découpage (semi-automatique)

Aucun fichier d'index ne doit dépasser **~150 lignes** (marge sous le plafond dur de `MEMORY.md` = 200 lignes / 25 KB).

- Si un **sous-index** `index/<domaine>.md` approche ~150 lignes → **alerter** l'utilisateur et **proposer** de scinder le domaine en sous-domaines (`index/<domaine>/<sous>.md`). Ne pas scinder sans validation.
- Si la **carte** `MEMORY.md` approche ~150 lignes → proposer de regrouper les domaines en familles.

C'est **semi-automatique** : le skill détecte et propose, l'humain valide.

## Format d'une section de sous-index

```markdown
## <Titre du fait> (<type>) — <date ou état>
<1 à 3 lignes de résumé, l'essentiel pour décider d'ouvrir le fait>
→ `<domaine>/<fait>.md`
```

## Pointeurs

Tous les pointeurs (`→ chemin`) sont **relatifs à la racine du vault** (ex. `mailing/audit.md`), pour que la navigation par `Read` fonctionne quel que soit le fichier d'origine.
