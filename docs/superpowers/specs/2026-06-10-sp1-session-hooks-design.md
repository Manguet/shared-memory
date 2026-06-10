# Design — SP1 : boucle vivante (hooks de session)

**Date :** 2026-06-10
**Statut :** Design validé, prêt pour le plan
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Programme :** premier des chantiers « faire vivre la mémoire centrale » (SP1).

## Objectif et contrainte

Faire en sorte que la **boucle se referme sans discipline manuelle** — c'est le risque décisif que
nomme `ARCHITECTURE.md §10`. Deux automatismes via des **hooks plugin** :
1. **Synchro au démarrage** : récupérer les faits canoniques de l'équipe pour ne pas travailler sur
   une mémoire périmée (le `git pull` n'a lieu aujourd'hui que dans certains skills).
2. **Rappel de promotion** : signaler les **brouillons locaux non promus** pour qu'ils ne restent
   pas bloqués à l'étage 1.

**Contrainte non négociable — best-effort, jamais bloquant.** Un hook qui ralentit ou casse le
démarrage de session est pire que pas de hook. Tout est **time-boxé**, **silencieux en cas d'échec**
(pas de vault, pas de réseau, pull en échec), et **sort toujours en 0**.

## Décisions (validées en brainstorming)

1. **Synchro : `git pull --ff-only`, auto-protecteur.** Le fast-forward fusionne quand c'est
   possible, sinon il **refuse sans rien écraser** (les brouillons étage 1 restent intacts) ; on
   notifie alors le nombre de faits canoniques restés en avance. Jamais de fusion destructive ni de
   stash. (Pas besoin de tester « working copy propre » au préalable : `--ff-only` est la garantie.)
2. **Deux hooks : `SessionStart` + `SessionEnd`.** Le `SessionStart` est le rappel fiable ; il
   **avertit dès le démarrage de prévoir `/memory-promote` avant de fermer** (pour éviter les
   décalages même si le `SessionEnd` ne se déclenche pas). Le `SessionEnd` est le dernier rappel.
3. **Best-effort** : time-box ~5 s sur les opérations réseau, sorties/erreurs avalées, exit 0.
4. **Réutilise l'existant** : `lib.sh` (`sm_slug`, `sm_vault_clone_for_slug`) + un nouvel helper de
   comptage.

## Architecture

Approche retenue (A) : **deux hooks plugin** pointant un **script paramétré** (le côté DRY de B).

```
.claude-plugin/plugin.json (déclare 2 hooks)
  ├─ SessionStart → scripts/hook-memory.sh start
  └─ SessionEnd   → scripts/hook-memory.sh end
scripts/hook-memory.sh   (source lib.sh ; résout le vault, synchronise, émet le message)
scripts/lib.sh           (+ sm_count_unpromoted <clone>)
```

Le script résout le clone du **projet courant** (`sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}"` →
`sm_vault_clone_for_slug`). Si le projet n'est pas branché → **no-op silencieux** (exit 0, aucune
sortie). Le format exact d'émission du message (sortie que Claude Code injecte en contexte) sera
figé au plan en suivant la convention des hooks plugin Claude Code.

## Comportement

### `hook-memory.sh start` (SessionStart)
1. Résoudre le clone du projet ; absent → exit 0 silencieux.
2. **Synchro time-boxée et non destructive** (`timeout ~5s`, sorties avalées, `|| true`) : tenter
   `git pull --ff-only` — il fusionne en fast-forward si possible, sinon **refuse sans rien écraser**.
   Dans tous les cas il a fait le `fetch`, donc on calcule ensuite le nombre de faits canoniques
   restés en avance : `git rev-list --count HEAD..origin/main` (= 0 si le pull a réussi ; > 0 si le
   fast-forward était impossible → à notifier).
3. Compter les **brouillons non promus** via `sm_count_unpromoted` (voir plus bas).
4. **Émettre un message** de contexte (uniquement s'il y a quelque chose à dire) :
   - s'il y a des faits en amont : « N nouveaux faits d'équipe récupérés / disponibles » ;
   - s'il y a M brouillons non promus : « Tu as M faits locaux non promus — **prévois
     `/memory-promote` avant de fermer** pour éviter les décalages. »

### `hook-memory.sh end` (SessionEnd)
1. Résoudre le clone ; absent → exit 0 silencieux.
2. Compter les brouillons non promus (`sm_count_unpromoted`).
3. Si M > 0 → émettre « Avant de partir : M faits locaux non promus, lance `/memory-promote` pour
   les partager. » Sinon, silencieux.

## Compter « non promus » (`sm_count_unpromoted <clone>`)

Nombre de fichiers de **faits `.md`** de la working copy qui diffèrent d'`origin/main`
(ajoutés / modifiés / supprimés / non suivis), en **excluant** :
- `MEMORY.md` et `index/**` (régénérés par `reshard`, ce ne sont pas des faits) ;
- les **faits perso** : fichiers `feedback_*` et faits dont le frontmatter porte
  `metadata.type: user` ou `feedback`.

Le helper lit `git -C <clone> status --porcelain` (couvre modifiés + non suivis), filtre `.md`,
applique les exclusions ci-dessus, et lit le `type:` du frontmatter des candidats restants. Renvoie
un entier sur stdout. C'est le **cœur testable** de SP1.

## Sécurité & robustesse

- **Latence** : `git pull`/`fetch` sous `timeout ~5s`, `>/dev/null 2>&1`, `|| true`. Le hook ne
  bloque jamais le démarrage au-delà du time-box.
- **Échecs** : pas de vault, pas de réseau, auth absente, pull non-ff → **aucune sortie cassante**,
  exit 0. Le pire cas est « le hook n'a rien fait », jamais « le hook a cassé la session ».
- **Pas de fusion destructive** : `--ff-only` (échoue proprement si divergence, capté par `|| true`).
  Les brouillons étage 1 ne sont jamais stashés ni écrasés.
- **Idempotent** : relancer le hook ne fait que re-synchroniser/re-compter.

## Doc & tests (convention du programme — partie de « terminé »)

**Documentation :**
- `README.md` : section « boucle vivante » (auto-sync au démarrage + rappel de promotion).
- `INSTALL.md` : décrire le comportement au démarrage/fin de session.
- `docs/ARCHITECTURE.md` §10 (« Discipline », le risque décisif) : noter qu'il est désormais
  **atténué** par les hooks, avec renvoi vers une entrée §12.

**Tests (`unittest` invoquant le bash via subprocess) :**
- `sm_count_unpromoted` : clone temporaire avec des faits `project`/`reference` (comptés), un
  `feedback_*` et un `type: feedback` (exclus), un `index/x.md` et `MEMORY.md` (exclus) → assert le
  bon compte.
- `hook-memory.sh start|end` : **no-op silencieux** (exit 0, sortie vide) quand le projet n'est pas
  branché (registre absent / slug inconnu) ; émission d'un message contenant `/memory-promote` quand
  il y a des brouillons.
- Le **déclenchement réel** par Claude Code (les events `SessionStart`/`SessionEnd`) se vérifie
  **manuellement** — un hook ne se teste pas en unitaire ; le plan inclut une étape de fumée
  (script lancé directement + vérification que le hook est bien déclaré et tire en session réelle).

## Découpage du plan (≈ 6 tâches)

1. `sm_count_unpromoted` dans `lib.sh` + test unittest.
2. `scripts/hook-memory.sh start` (résolution vault + synchro time-boxée + message) + test (no-op + message).
3. `scripts/hook-memory.sh end` + test.
4. Déclarer les 2 hooks (`SessionStart`, `SessionEnd`) dans `.claude-plugin/plugin.json`.
5. **Doc** : README / INSTALL / ARCHITECTURE.
6. Fumée réelle : lancer `hook-memory.sh start` sur un clone de test ; vérifier la déclaration des
   hooks ; rappel de vérif manuelle du déclenchement en session.

## Hors scope / évolutions

- **Stash automatique des brouillons** pour forcer le pull même non-propre : écarté (risque).
- **Rappel sur `Stop`** (à chaque réponse) : écarté (trop bruyant).
- **Auto-promotion** : exclu — la promotion reste un acte explicite gouverné (`/memory-promote` →
  `/memory-review`).
- **`.gitignore` perso au setup (SP5)** : chantier séparé, même s'il est connexe.

## Décisions clés (récapitulatif)

1. Deux hooks plugin (`SessionStart` + `SessionEnd`) → `scripts/hook-memory.sh start|end`.
2. Synchro : pull `--ff-only` si propre, sinon fetch + notifier ; jamais de fusion destructive.
3. `SessionStart` avertit **dès le démarrage** de prévoir `/memory-promote` avant la fermeture.
4. Best-effort : time-boxé, silencieux en échec, exit 0 — ne bloque jamais la session.
5. `sm_count_unpromoted` (faits partageables modifiés vs `origin/main`, hors `index/`/`MEMORY.md`/perso) = cœur testable.
6. Doc (README/INSTALL/ARCHITECTURE) + tests font partie du « terminé ».
