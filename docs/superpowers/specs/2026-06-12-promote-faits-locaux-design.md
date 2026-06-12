# Design — Exclure des faits du `/memory-promote` (faits « locaux »)

**Date :** 2026-06-12
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Origine :** retour d'usage — `/memory-promote` est **tout ou rien** : il pousse tous les faits
partageables (`project`/`reference`) nouveaux ou modifiés. On veut pouvoir **garder certains faits
en local** sans les partager, soit **ponctuellement** (ce promote-ci), soit **durablement** (jamais).

## Décisions (validées en brainstorming)

1. **Exclusion ponctuelle ET durable** : à chaque promote on liste les candidats et on choisit ceux
   à exclure ; pour chaque exclu, « cette fois » (réapparaît au prochain promote) ou « toujours »
   (marqué local durablement).
2. **Marqueur durable = drapeau frontmatter** `metadata.local: true` (vit avec le fait, lisible,
   suit le fait s'il est déplacé). Pas de fichier `.promoteignore`, pas de dossier `local/`.
3. **Périmètre** : `/memory-promote` + `sm_count_unpromoted` + `lint` + `reshard` + **viewer**
   (badge + bascule). Pas de badge dans le digest de démarrage.
4. **Construction de la branche : approche A** — worktree git temporaire à `origin/main`, on y copie
   uniquement les faits sélectionnés, reshard + commit + push, puis suppression du worktree. L'index
   poussé ne référence que les faits choisis ; le vault local n'est pas muté par le push (hors pose
   du drapeau « toujours »).

## Modèle : le drapeau `metadata.local`

- Champ **optionnel** dans le frontmatter d'un fait, sous le bloc `metadata:` :
  `metadata.local: true` = « fait local, jamais partagé ». Absent ou `false` = partageable (comportement
  actuel inchangé).
- S'applique à tout fait ; n'a de sens que pour les types partageables (`project`/`reference`), les
  `user`/`feedback` étant déjà toujours locaux.
- **Source de vérité unique** : toutes les surfaces (promote, compteur, reshard, viewer) lisent ce
  drapeau ; aucune autre liste à maintenir.

## Composants

| Composant | Rôle | Action |
|---|---|---|
| `scripts/build-viewer.py` (`collect_facts`) | porte `local` (booléen) dans le dict du fait. | Modifier |
| `scripts/reshard.py` | **ignore** les faits `local` : ni déplacés, ni indexés, ni comptés pour le seuil. | Modifier |
| `scripts/lib.sh` (`sm_count_unpromoted`) | saute les faits `local` (en plus de `user`/`feedback`). | Modifier |
| `scripts/lint.py` | tolère `metadata.local` ; `warn` si la valeur n'est ni `true` ni `false`. | Modifier |
| `scripts/serve-viewer.py` | `_fact_text` écrit `metadata.local: true` quand demandé ; `_validate` accepte le booléen `local`. | Modifier |
| `assets/viewer-template.html` | badge « local » (liste + détail) ; case à cocher dans le formulaire créer/éditer. | Modifier |
| `skills/memory-promote/SKILL.md` | filtre les `local` ; sélection interactive (cette fois / toujours) ; construction worktree A. | Modifier |
| Tests + docs | couverture du nouveau comportement. | Modifier |

### `collect_facts` (build-viewer.py)

Ajouter au dict du fait : `"local": <bool>` dérivé de `fm.get("metadata.local")` (le parseur rend
une **chaîne** ; `local` vrai ssi la valeur, minusculée, vaut `"true"`). Reste rétrocompatible :
absent → `False`. Aucune autre clé du dict ne change.

### `reshard.py`

Au moment de construire l'arbre sémantique (`_semantic_tree`), **écarter** les faits dont
`metadata.local` est vrai : ils ne sont ni placés dans l'arbre, ni listés dans un index, ni comptés
vers le seuil de sharding (150).

**Sûreté anti perte de données (critique).** `reshard()` supprime le dossier de chaque domaine
(`rmtree(vault/<domaine>)`) avant de remettre les faits *placés* depuis le staging. Un fait `local`
simplement « ignoré » serait donc **détruit** s'il vit dans un domaine par ailleurs partagé. Pour
l'éviter, les faits `local` sont traités en **passthrough** : `_semantic_tree` les collecte (chemin
d'origine + contenu brut) et `_plan_layout` les ajoute à la liste `files` à **leur chemin d'origine**
→ ils sont écrits dans le staging puis rebasculés en place comme les autres, mais **n'apparaissent
dans aucun index** et **ne comptent pas** dans `counts`. Résultat : ils **restent physiquement en
place**, hors partage. Un vault sans aucun fait `local` produit une sortie **strictement identique**
à aujourd'hui (compatibilité ascendante, tests existants verts). `_semantic_tree` passe de
`(root, perso)` à `(root, perso, local)` ; seul `_plan_layout` l'appelle.

### `sm_count_unpromoted` (lib.sh)

Après le filtre type (`user`/`feedback` exclus), lire aussi le drapeau `local` du fichier
(ex. `sed -n 's/^[[:space:]]*local:[[:space:]]*//p'`) ; si vrai → `continue` (non compté). Effet : un
fait durablement local ne gonfle plus « N non promu » du rappel de démarrage ; un fait simplement
sauté « cette fois » (sans drapeau) reste compté.

### `lint.py`

Aucune erreur sur la présence de `metadata.local`. Ajouter une règle **douce** : si `metadata.local`
est présent et que sa valeur (minusculée) n'est ni `true` ni `false` → `warn`
(`local_malformed`). Pas de blocage.

### `serve-viewer.py`

- `_fact_text(name, description, type_, body, reviewed=None, local=False)` : émet une ligne
  `  local: true` **sous le bloc `metadata:`** uniquement quand `local` est vrai (sinon champ absent,
  pour ne pas alourdir les faits partagés).
- `_validate` : accepte un champ `local` (booléen) dans le payload ; coercition souple
  (`data.get("local") is True or str(...).lower() == "true"`). Les `user`/`feedback` n'ont pas besoin
  du drapeau (déjà locaux) mais l'accepter ne nuit pas.
- `create_fact`/`update_fact` passent `local` à `_fact_text`. `reshard` est appelé comme aujourd'hui
  (et ignore désormais les faits `local`).

### `viewer-template.html`

- **Badge « local »** rendu sur les faits dont `f.local` est vrai (liste + vue détail), style discret
  (réutiliser le style des badges existants, ex. `fresh-badge`).
- **Case à cocher** « fait local (ne pas partager) » dans le formulaire créer (`d-…`) et éditer
  (`e-…`) ; sa valeur est envoyée dans le payload `local`. À l'édition, pré-cochée selon `f.local`.
- Pas de nouvel endpoint : l'update existant porte le drapeau.

### `skills/memory-promote/SKILL.md`

Réviser la procédure :
1. **Filtre candidats** : exclure `user`/`feedback`, `feedback_*`, **et** les faits `metadata.local:
   true`.
2. **Sélection interactive** : présenter la liste des candidats ; l'utilisateur exclut ceux qu'il
   veut. Pour chaque exclu, demander **« cette fois »** ou **« toujours »** :
   - *toujours* → poser `metadata.local: true` sur le fait **dans le vault** (persiste ; il sort des
     candidats et du compteur).
   - *cette fois* → ne pas l'inclure dans cette proposition (aucun drapeau ; reste candidat au
     prochain promote).
3. **Vérif sémantique + re-stamp `reviewed`** des faits **sélectionnés** dans le vault (inchangé sur
   le principe).
4. **Construction (approche A)** :
   - `tmp="$(mktemp -d)"` ; `git -C "<clone>" worktree add --detach "$tmp" origin/main`.
   - Copier dans `$tmp` **uniquement les faits sélectionnés** (à leur chemin relatif).
   - `python3 scripts/reshard.py "$tmp"` (index propre, sans exclus ni `local`) ; ajouter à la main
     une ligne `MEMORY.md` si un **nouveau domaine** apparaît.
   - `lint.py "$tmp"` (advisory).
   - `git -C "$tmp" checkout -b promote/<slug>-<court>` ; `git -C "$tmp" add -A` ;
     `commit -m "memory: <résumé>"` ; `push -u origin HEAD`.
   - `git -C "<clone>" worktree remove "$tmp"` (et `worktree prune`).
5. **Confirmer** : nom de la branche + rappel `/memory-review` par un référent (inchangé).

## Tests (convention doc/tests du programme)

- **`tests/test_reshard.py`** : un fait `metadata.local: true` est **préservé en place**, **absent de
  tout index**, et **non compté** pour le seuil de sharding ; un vault sans fait `local` → sortie
  identique (compat).
- **`tests/test_build_viewer.py`** : `collect_facts` renvoie `local: True` pour un fait marqué,
  `False` sinon (et pour frontmatter sans le champ).
- **`tests/test_hooks.py`** (`CountUnpromotedTest`) : un fait `project` marqué `local: true` n'est
  **pas** compté ; un fait `project` non marqué l'est.
- **`tests/test_lint.py`** : `metadata.local: true`/`false` → aucune erreur ; valeur autre → `warn`
  `local_malformed`.
- **`tests/test_serve_viewer.py`** : créer un fait avec `local: true` écrit bien `metadata.local:
  true` ; éditer pour (dé)cocher bascule le drapeau ; un fait `local` créé via le viewer **n'apparaît
  pas** dans l'index après reshard.
- **Skill promote** (sélection interactive, worktree, push réseau) : pas de test automatisé (réseau /
  interactif) → **vérification manuelle** documentée.

## Doc

- `docs/domain-convention.md` : section sur `metadata.local` (fait local, hors index, hors partage).
- `docs/ARCHITECTURE.md` : mention dans la section gouvernance/promote (exclusion ponctuelle/durable,
  approche worktree).
- `skills/memory-promote/SKILL.md` : procédure révisée (ci-dessus).

## Hors scope / évolutions

- **Badge `local` dans le digest de démarrage** : écarté (Q3).
- **Bascule en masse / dossier entier en local** : non — un drapeau par fait.
- **Exclusion par règle/glob** (`.promoteignore`) : écartée au profit du drapeau.
- **Migration des faits existants** : aucun n'est `local` aujourd'hui ; rien à migrer.

## Décisions clés (récapitulatif)

1. Drapeau `metadata.local: true` = fait jamais partagé ; source de vérité unique.
2. `reshard` ignore les `local` (préservés, hors index, hors seuil) ; compat ascendante stricte.
3. `sm_count_unpromoted` et le filtre promote sautent les `local`. Le digest est inchangé.
4. promote : sélection interactive (cette fois / toujours) + construction en **worktree propre depuis
   `origin/main`** (l'index poussé ne contient que les faits choisis).
5. Viewer : badge + case à cocher (via l'update existant). lint tolère + valide. Tests + doc selon la
   convention du programme.
