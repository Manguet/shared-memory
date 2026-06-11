# Convention — Mémoire shardée par domaine

Référence commune aux skills `memory-import`, `memory-promote`, `memory-list`, `memory-review`.
Le vault n'est plus plat : les faits sont rangés **par domaine**, et l'index est **hiérarchique**.

## Principe fondateur — l'index aiguille, le fait est la source

Tout index (carte `MEMORY.md`, sous-index `index/…`) sert **uniquement à trouver** un fait.
**Toute affirmation factuelle** (valeur, citation, comportement du code) provient du **fait lu en
entier**, jamais de l'index. Conséquence directe : l'index peut être **compact** (optimisé pour
trouver vite, à bas coût en tokens) **sans risque pour la véracité**, puisqu'il ne fait jamais
autorité — il pointe.

## Fraîcheur des faits (`reviewed`)

Chaque fait porte `metadata.reviewed: AAAA-MM-JJ` = **date de dernière vérification contre le code**.
Stampée automatiquement à la **création**, à l'**édition** (viewer CRUD), et au **promote/review**
(qui vérifient le fait). Un fait non vérifié depuis **≥ 90 jours** (ou sans date) est **« à
revérifier »** : la mémoire reste digne de confiance tant que ses faits sont datés et rafraîchis.
Le viewer affiche un badge de fraîcheur et une vue « à revérifier ».

## Format canonique d'un fait

Le frontmatter **canonique** place `type` et `reviewed` sous un bloc **`metadata:`** imbriqué
(cf. `assets/fact-template.md`) :

    ---
    name: <slug-kebab-case>
    description: <résumé discriminant en une ligne>
    metadata:
      type: project        # project | reference | user | feedback
      reviewed: AAAA-MM-JJ
    ---

Le `name` doit être un **slug kebab-case** (il sert de pointeur dans `index/**` et les wikilinks ;
le renommer casse ces liens). Un frontmatter **à plat** (`type:`/`reviewed:` de premier niveau) est
une forme héritée : `/memory-lint` la **détecte** et la **normalise** vers le bloc `metadata:`.

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
- **`index/<domaine>.md` (sous-index)** : **une ligne compacte par fait** — `` - `<nom>` — <description> · <type> → `<domaine>/<fait>.md` ``. La `description` est **reprise telle quelle du frontmatter du fait** (DRY). Un sous-index qui déborde se **scinde en sous-domaines** `index/<domaine>/<sous>.md` (voir « Profondeur récursive »).
- **Faits perso** (`metadata.type: user`/`feedback`, fichiers `feedback_*.md`) : **restent à la racine**, jamais rangés en domaine, jamais partagés.

## Ranger un fait dans un domaine

1. **Déduire le domaine** du sujet du fait (ex. emails → `mailing`, fiscalité → `ecommerce`).
2. **Garde-fou anti-prolifération** : lire la carte `MEMORY.md` et, si un domaine existant est proche (`mailing` vs `emails` vs `mail`), **proposer le domaine existant** plutôt que d'en créer un nouveau. Demander à l'utilisateur en cas de doute.
3bis. **Garde-fou anti-doublon (faits)** : avant d'écrire un fait, vérifier les **quasi-doublons
   sémantiques** (`scripts/similar.py`, cosine ≥ 0.80) — mettre à jour un fait proche existant
   plutôt qu'empiler un doublon. La détection se fait à la création (import + CRUD du viewer).
3. Écrire le fait dans `<domaine>/<fait>.md`.
4. **Mettre à jour le sous-index** `index/<domaine>.md` (ajouter la ligne compacte du fait, cf. « Format d'une ligne de sous-index »). Le créer s'il n'existe pas.
5. Si le domaine est **nouveau**, ajouter sa ligne dans la carte `MEMORY.md` (section « Domaines »).

## Profondeur récursive sans plafond

Aucun fichier d'index ne doit dépasser **~150 lignes** (marge sous le plafond dur de `MEMORY.md` =
200 lignes / 25 KB). Quand un index déborde, on **ajoute un niveau** — il n'y a **aucun plafond de
profondeur**, elle est émergente (1…N).

- **Sous-index** `index/<domaine>.md` qui approche ~150 lignes → **alerter** l'utilisateur et
  **proposer** de scinder le domaine en sous-domaines `index/<domaine>/<sous>.md`. Récursivement :
  un sous-domaine qui déborde se scinde à son tour (`index/<domaine>/<sous>/<sous2>.md`).
- Une fois scindé, `index/<domaine>.md` ne liste plus des faits mais des **pointeurs de
  sous-domaine**, une ligne chacun :

  ```markdown
  - transactionnel (12 faits) → `index/mailing/transactionnel.md`
  - cycle-de-vie (9 faits) → `index/mailing/cycle-de-vie.md`
  ```

  Les faits déménagent alors dans `<domaine>/<sous>/<fait>.md` et leurs pointeurs (dans le
  sous-index feuille) restent relatifs à la racine : `` → `mailing/transactionnel/relance-j3.md` ``.
- **Carte** `MEMORY.md` qui approche ~150 lignes → proposer de regrouper les domaines en familles.

C'est **semi-automatique** : le skill détecte et propose, l'humain valide. La profondeur ne se crée
que quand un index parent déborde (cf. capacité : 2 niveaux ≈ 22 500 faits, 3 ≈ 3,4 M).

### Moteur du redécoupage : `reshard.py`

Le redécoupage est porté par **`scripts/reshard.py`** (invariant : *aucun dossier ne dépasse
~150 faits directs ni ~150 sous-dossiers*). Il **restructure** les faits sur disque (déplacement
en sous-domaines `part-xx` seulement là où le seuil est franchi, donc **idempotent** et
sans toucher un sous-arbre déjà conforme) puis **régénère tout `index/**`** au format
compact. Il **préserve** la carte `MEMORY.md` (curée à la main : intro, « Patterns & Conventions »,
« Général », descriptions de domaines) — il ne la crée que si elle est **absente** ; la carte des
domaines reste maintenue par l'humain/les skills (elle ne change qu'à la **création** d'un domaine).
Les skills l'appellent au lieu d'écrire les sous-index à la main :

```bash
python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<vault>" [--max-entries 150]
```

Les sous-domaines créés portent des labels mécaniques (`part-01`…) ; **un humain peut les renommer**
en libellés signifiants ensuite (reshard ne re-brasse pas un sous-arbre resté sous le seuil).

## Format d'une ligne de sous-index

Une ligne par fait, dans `index/<domaine>.md` :

```markdown
- `<nom>` — <description discriminante> · <type> → `<domaine>/<fait>.md`
```

- `<nom>` = le slug `name` du frontmatter du fait.
- `<description>` = la `description` du frontmatter, **copiée telle quelle** (DRY : une seule source de vérité, déjà affichée par le viewer).
- `<type>` = `metadata.type` (`project` / `reference`).
- Le pointeur est **relatif à la racine du vault**.

Exemple (`index/mailing.md`) :

```markdown
# mailing

- `relance-j3` — délai de relance des paniers abandonnés fixé à 72 h · project → `mailing/relance-j3.md`
- `objet-ab-test` — gabarit d'A/B testing des objets d'email transactionnel · reference → `mailing/objet-ab-test.md`
```

~3× moins de tokens par lecture de sous-index qu'avec l'ancien format multi-lignes, à information de tri équivalente.

### Descriptions discriminantes (convention)

Comme la `description` du frontmatter **est** l'aiguillage (elle alimente directement le sous-index),
elle doit **distinguer le fait de ses voisins du même domaine**, pour que Claude ouvre le bon fait
**du premier coup**. Écrire « délai de relance des paniers abandonnés fixé à 72 h », pas « infos sur
les relances ». Ceci se joue **à la création du fait** (skills `memory-import` / `memory-promote`).

## Pointeurs

Tous les pointeurs (`→ chemin`) sont **relatifs à la racine du vault** (ex. `mailing/audit.md`), pour que la navigation par `Read` fonctionne quel que soit le fichier d'origine.
