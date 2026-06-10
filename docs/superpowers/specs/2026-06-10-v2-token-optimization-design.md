# Design — V2 optimisation tokens (aiguillage + recherche vectorielle)

**Date :** 2026-06-10
**Statut :** Design validé, prêt pour les plans
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Prérequis :** sharding par domaine (V1) + viewer scalable (Plan A/B) livrés.

## Objectif et contrainte

Réduire les **tokens « non utiles »** que Claude dépense pour *trouver* l'information en mémoire,
**sans jamais nuire à la véracité** de ce qui est remonté.

**Principe fondateur — l'index aiguille, le fait est la source.** Tout index/outil ne fait que
*trouver* des faits ; toute affirmation factuelle (valeur, citation, comportement) provient du
**fait lu en entier**. Rien ne résume à la place de la source. La véracité est donc
structurellement hors d'atteinte de l'optimisation.

Distinction tenue tout au long :
- **Véracité** = ce qui est remonté est exact → garantie (le fait est toujours lu).
- **Exhaustivité** = on remonte tous les faits pertinents → protégée par l'hybride (vectoriel ∪ grep).

## Volet A — Aiguillage par index (léger, zéro dépendance)

1. **Sous-index compact** : `index/<domaine>.md` passe de « section par fait » à **1 ligne/fait** :
   `- <nom> — <description discriminante> · <type> → <domaine>/<fait>.md`, en réutilisant la
   `description` du frontmatter (DRY). ~3× moins de tokens par lecture de sous-index.
2. **Profondeur récursive sans plafond** : un sous-index > ~150 lignes est scindé en sous-domaines
   (`index/<domaine>/<sous>.md`), récursivement. Déjà supporté techniquement (`path[]` + arbre du
   Plan A/B) ; c'est la règle de seuil, sans cap.
3. **Descriptions discriminantes** (convention) : la `description` *est* l'aiguillage → elle doit
   distinguer le fait de ses voisins, pour que Claude ouvre le bon fait du premier coup.

## Volet B — `search_memory` : recherche vectorielle pour Claude

Un **serveur MCP** (stdio, déclaré dans `.mcp.json`) expose l'outil **`search_memory(query, k=8)`**
que Claude appelle en session. Il **court-circuite la lecture des index** et renvoie les
**pointeurs** des top-k faits : `[{file, name, path, score}]` — **jamais** de body ni de résumé.
Claude lit ensuite les faits pointés (source).

- **Embeddings : fastembed** (ONNX, modèle ~90 Mo, 100 % local — confidentialité). La dépendance
  est **optionnelle** : l'`embed_fn` est injectable ; si fastembed est absent, l'outil **retombe
  sur le grep** (réutilise la logique `/search` de `serve-viewer.py`) et signale le mode dégradé.
- **Store hors vault** : `~/.shared-memory/embeddings/<slug>/index.json` mappe `file → {hash, vec}`.
  Pas de binaire dans le vault (git propre), reconstructible.
- **Fraîcheur lazy par hash** : à chaque appel, (ré)embedder uniquement les faits dont le contenu
  (hash) a changé. Pas de pipeline séparé ; premier appel = embedding complet, ensuite incrémental.
- **Recherche** : cosine brute-force en pur Python (rapide pour des milliers de faits × ~384 dims).
- **Hybride exhaustivité** : résultat = union dédupliquée du **top-k sémantique** et des **matches
  exacts grep** → un terme exact présent n'est jamais raté par le sémantique.
- **Véracité** : l'outil ne renvoie que des pointeurs ; sa description impose « lire le fait avant
  d'affirmer ».

## Volet C — Doctor (diagnostic + proposition proactive)

Pas de dégradation **silencieuse**.

- **`scripts/doctor.py`** : vérifie les prérequis et renvoie un rapport structuré —
  Python ; `fastembed` importable ? ; modèle téléchargé ? ; store présent/à jour ? ; `.mcp.json`
  en place ? Chaque manquement est listé **avec sa commande de remède** (ex. `pip install fastembed`).
- **Skill `/memory-doctor`** : lance le doctor, présente le diagnostic et **propose** d'exécuter
  les installs manquantes (l'utilisateur valide ; Claude n'installe rien sans accord).
- **Dégradation explicite** : `search_memory` sans fastembed renvoie un drapeau
  `vector_inactive: true` (+ remède) → Claude le **signale et propose** `pip install fastembed`,
  au lieu de basculer en grep en silence.
- **`memory-setup`** appelle le doctor en fin de configuration pour annoncer d'emblée ce qui manque.

## Ce que ça touche

| Composant | Volet | Changement |
|---|---|---|
| `docs/domain-convention.md` | A | format compact, profondeur sans plafond, descriptions discriminantes, principe véracité |
| `skills/memory-import`, `memory-promote` | A | génèrent des sous-index **compacts** |
| sous-index negocian (4) | A | migration optionnelle section → 1 ligne |
| `scripts/embed.py` (créer) | B | embed_fn injectable, store, fraîcheur hash, cosine, hybride grep |
| `scripts/mcp-server.py` (créer) | B | serveur MCP stdio, outil `search_memory` |
| `.mcp.json` (créer) | B | déclare le serveur MCP du plugin |
| `scripts/doctor.py` (créer) | C | diagnostic des prérequis + remèdes |
| `skills/memory-doctor` (créer) | C | présente le diagnostic, propose les installs |
| `skills/memory-setup` | C | appelle le doctor en fin de configuration |

## Découpage en plans

- **Plan V2-A — Aiguillage** : convention + skills + migration. Rapide, surtout markdown ; vérif par relecture.
- **Plan V2-B — `search_memory` + Doctor** : `embed.py` (cœur testable via `embed_fn` mock) +
  `mcp-server.py` + `.mcp.json` + `doctor.py` + skill `/memory-doctor` + hook `memory-setup`.

Ordre : **A d'abord** (pose la convention compacte, indépendant), **B ensuite**.

## Tests & note d'install

- Volet A : relecture (markdown), + un exemple de sous-index compact vérifié.
- Volet B : `embed.py` couvert par `unittest` avec un `embed_fn` **factice** (vecteurs déterministes)
  → la suite passe **sans installer fastembed**. On teste : store/hash/fraîcheur, cosine/top-k,
  hybride (union grep), et le **fallback grep** quand `embed_fn` est None.
- `doctor.py` : `unittest` sur la détection (simuler présence/absence d'un module).
- **Install réelle** : fastembed est **absent** de la machine aujourd'hui → `search_memory` tourne
  en **fallback grep** dès la livraison ; le vectoriel s'active après `pip install fastembed`
  (que `/memory-doctor` proposera).

## Hors scope / évolutions

- **Ré-embedding distribué / index vectoriel persistant partagé** : le store reste local par-machine.
- **Re-ranking avancé** (cross-encoder) : seulement si la qualité du top-k devient limitante.

## Décisions clés (récapitulatif)

1. Principe : l'index aiguille, le fait est la source — véracité garantie.
2. Sous-index compacts (1 ligne/fait) + profondeur récursive sans plafond.
3. `search_memory` (MCP, vectoriel fastembed local) renvoyant des **pointeurs** ; hybride grep pour l'exhaustivité.
4. fastembed = dépendance **optionnelle**, fallback grep, store hors vault, fraîcheur lazy par hash.
5. Doctor : diagnostic + proposition proactive d'install, jamais de dégradation silencieuse.
6. Découpage : Plan V2-A (aiguillage) puis Plan V2-B (search_memory + doctor).
