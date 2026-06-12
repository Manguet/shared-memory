# Design — Sous-domaines sémantiques + formulaire de création amélioré

**Date :** 2026-06-12
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Origine :** retour d'usage réel — le formulaire du viewer ne respectait pas les conventions de slug
et ne gérait pas les sous-domaines ; or les « sous-domaines » actuels sont mécaniques (`part-NN`,
créés par reshard au-delà de 150 faits) et non sémantiques — un fait placé dans `mailing/transactionnel`
était aplati par le `reshard` que `create_fact` déclenche.

## Objectif

1. **Sous-domaines sémantiques** : permettre des dossiers nommés (`mailing/transactionnel`) qui
   **tiennent** dans le temps (reshard les préserve au lieu de les aplatir).
2. **Formulaire de création/édition** du viewer : slug appliqué à la frappe ; champ domaine en
   **combobox autocomplete** (domaines + sous-domaines existants, filtrage, marqueur « (Créer) »).

## Décisions (validées en brainstorming)

1. **Hybride** : les sous-domaines sémantiques sont **toujours préservés** ; dans **chaque dossier**,
   les faits **directs** qui dépassent le seuil (150) sont quand même redécoupés en `part-NN` à
   l'intérieur. On garde la garantie « démarrage borné ».
2. **`part-NN` réservé** à reshard. Tout autre nom de dossier est sémantique et préservé. Un nom de
   domaine `part-NN` saisi par l'utilisateur est **interdit** (validation).
3. **Le chemin de fichier est la vérité**, moins le mécanique : domaine sémantique d'un fait = son
   chemin **privé des segments `part-NN`** (approche A ; pas de champ frontmatter).
4. **Carte `MEMORY.md` (niveau 1) inchangée** : liste les domaines de 1er niveau ; les sous-domaines
   vivent dans l'index du domaine. Créer un sous-domaine ne touche pas la carte ; créer un **nouveau
   domaine de 1er niveau** ajoute une ligne (comme aujourd'hui).

## Modèle

- **Domaine sémantique d'un fait** = `path` (segments de dossiers, déjà fourni par `collect_facts`)
  **après retrait des segments `^part-\d+$`**. Ex. : `mailing/transactionnel/x.md` → `mailing/transactionnel` ;
  `mailing/part-01/x.md` → `mailing` ; `mailing/x.md` → `mailing`.
- Un **dossier** (domaine ou sous-domaine) peut contenir **à la fois** des faits directs et des
  sous-domaines sémantiques. Dans l'hybride, ses faits directs au-delà du seuil sont mis en `part-NN`
  **à côté** des sous-domaines nommés (ex. `mailing/` → `transactionnel/`, `part-01/`, `part-02/`).
- **Faits perso** (`user`/`feedback`) : inchangé — racine, jamais shardés ni en sous-domaine.

## Architecture / composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/reshard.py` | conscience de l'arbre sémantique (préserver / hybride). | Modifier |
| `scripts/serve-viewer.py` | `DOMAIN_RE` multi-segments + interdiction `part-NN`. | Modifier |
| `assets/viewer-template.html` | `slugify()` à la frappe + combobox domaine (autocomplete + « (Créer) »). | Modifier |
| `tests/test_reshard.py`, `tests/test_serve_viewer.py` | couverture du nouveau modèle. | Modifier |
| `docs/domain-convention.md`, `docs/ARCHITECTURE.md` | documenter. | Modifier |

### Refonte `reshard.py`

- **`_semantic_tree(vault)`** (remplace `_domain_facts`) : pour chaque fait, calcule son chemin
  sémantique (path moins `part-NN`) ; bâtit un **arbre imbriqué** de nœuds `{segments, facts (directs,
  triés par name), children: {nom → nœud}}`. Les perso sont mis de côté pour la racine (comme avant).
- **`_materialize_node(node, segments, max_entries)`** (généralise `_materialize`) — renvoie
  `(placements, indexes)` :
  - **faits directs** : si `len ≤ max_entries` → fichiers `<segments>/<name>.md`, listés comme
    **faits** dans l'index du nœud. Sinon → `split_tree(facts, max_entries)` puis matérialisation des
    sous-arbres en `<segments>/part-NN/…`, listés comme **nœuds** (réutilise `balanced_chunks`/`split_tree`).
  - **enfants sémantiques** : chacun récursé ; listé comme **nœud** → `index/<segments>/<child>.md`.
  - L'index `index/<segments>.md` est **mixte** : lignes-faits (faits directs non scindés) +
    lignes-nœuds (part-NN et/ou enfants sémantiques).
- **`_index_relpath_content`** : généralisé pour accepter une liste d'**entrées mixtes** (chaque
  entrée taguée `fact` ou `node`) dans un même fichier index.
- **Compatibilité ascendante** : un vault **plat** (aucun sous-domaine sémantique) → chemin sémantique
  `["domaine"]` → groupement et matérialisation **identiques** à l'actuel (même `part-NN` au-delà du
  seuil). Le comportement et les tests existants ne changent pas.
- **`_ensure_memory`** : comptes par domaine de 1er niveau (somme de tous les faits sous chaque racine
  sémantique) — inchangé fonctionnellement.
- Le **staging→swap anti-perte de données** (durcissement précédent) est conservé.

### Backend `serve-viewer.py`

- `DOMAIN_RE = re.compile(r"^[a-z0-9-]+(/[a-z0-9-]+)*$")`.
- `_validate` : domaine validé par `DOMAIN_RE` ; **rejet** (400) si un segment matche `^part-\d+$`
  (« nom réservé au découpage automatique »). Le `name` reste un slug simple (`SLUG_RE`).
- `_rel_for(name, domain)` inchangé (joint déjà `domaine/nom.md`). `create_fact`/`update_fact`
  écrivent dans le chemin imbriqué puis appellent `reshard` (refondu) → le sous-domaine **tient**.
  `_safe_path` bloque toute traversée.

### Frontend `viewer-template.html` (créer + éditer)

- **`slugify(s)`** : `s.normalize('NFD')` + retrait des diacritiques, minuscules, `[^a-z0-9]+ → -`,
  compression des `-`, trim des `-` en tête/fin. Variante domaine : applique `slugify` à **chaque
  segment** séparé par `/` (segments vides ignorés).
- **Champ nom** (`d-name`, `e-name`) : `oninput` → `slugify`.
- **Combobox domaine** (`d-domain`, `e-domain`, remplace `<input list>`+`<datalist>`) :
  - `semanticDomains()` : ensemble des chemins sémantiques distincts (faits → path moins `part-NN`,
    joints par `/`) **+ leurs préfixes**, triés.
  - input + panneau déroulant filtré à la frappe (substring, sur la saisie slugifiée) ;
  - si la saisie slugifiée non vide ne correspond à aucun domaine existant → ligne **« (Créer)
    <saisie> »** en tête ;
  - clic = sélection ; navigation clavier basique (↑/↓/Entrée/Échap) ; CSS au thème sombre existant ;
  - chaque segment slugifié `oninput` ; un segment `part-NN` n'est pas bloqué côté client mais
    **refusé par le serveur** avec message clair.

## Doc & tests (convention du programme)

**Tests :**
- `tests/test_reshard.py` : sous-domaine sémantique **préservé** ; **hybride** (part-NN dans un
  sous-domaine qui déborde) ; **mixte** (enfant sémantique + part-NN côte à côte) ; **compat
  ascendante** (vault plat → sortie identique, les 19 existants restent verts) ; **`part-NN`
  ré-dérivé** (fait dans `mailing/part-01/` peu nombreux → collapse à `mailing/`).
- `tests/test_serve_viewer.py` : **créer en sous-domaine** `mailing/transactionnel` → après création
  (qui reshard), le fait **reste** à `mailing/transactionnel/<nom>.md` ; **domaine invalide** (majuscule,
  `..`, segment vide) → 400 ; **segment `part-NN`** → 400.
- Frontend (`slugify`, combobox) : pas de test navigateur (pas de CI navigateur) → **vérification
  visuelle**. Le backend est couvert.

**Doc :**
- `docs/domain-convention.md` : section sharding mise à jour — **sous-domaines sémantiques** (nommés,
  préservés) vs **`part-NN`** (mécanique, automatique, **nom réservé**) ; comportement hybride ;
  domaine = chemin sémantique.
- `docs/ARCHITECTURE.md` : note dans la section sharding (le modèle reconnaît les sous-domaines
  sémantiques ; `part-NN` réservé ; hybride).

## Hors scope / évolutions

- **Champ `metadata.domain`** (approche B) : écarté — le chemin reste la vérité.
- **Renommer/déplacer un sous-domaine entier** depuis le viewer : hors scope (le rename actuel reste
  niveau 1). Évolution possible.
- **Sous-domaines pour les faits perso** : exclu (les perso restent à la racine).
- **Lister les sous-domaines dans `MEMORY.md`** : non — ils vivent dans l'index du domaine.
- **Test navigateur du combobox** : hors scope (pas d'infra navigateur en CI).

## Décisions clés (récapitulatif)

1. Modèle hybride : sous-domaines sémantiques préservés + `part-NN` automatique dans un dossier qui
   déborde ; `part-NN` réservé ; domaine = chemin sémantique (path moins `part-NN`).
2. `reshard` refondu (`_semantic_tree` + `_materialize_node` + index mixte), compat ascendante stricte
   pour les vaults plats, staging→swap conservé.
3. Backend : `DOMAIN_RE` multi-segments + rejet `part-NN`. Frontend : `slugify` à la frappe + combobox
   autocomplete avec « (Créer) ».
4. Doc (convention, ARCHITECTURE) + tests (reshard nouveau modèle + compat ; serve-viewer sous-domaine
   et validations). Frontend vérifié visuellement.
