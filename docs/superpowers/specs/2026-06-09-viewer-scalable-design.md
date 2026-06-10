# Design — Viewer scalable (serveur + arbre récursif)

**Date :** 2026-06-09
**Statut :** Design validé, prêt pour les plans d'implémentation
**Projet :** plugin `shared-memory` (`/var/www/shared-memory`)
**Prérequis :** sharding par domaine déjà livré (viewer groupé par domaine, `build-viewer` récursif, skills adaptés).

## Contexte et problème

Mesuré sur un vault synthétique de **50 domaines × 120 faits = 6000 faits** :

| Métrique | Valeur | Problème |
|---|---|---|
| Carte `MEMORY.md` (démarrage Claude) | 51 lignes / 2,4 KB | 🟢 OK — le sharding a réglé le coût tokens de démarrage |
| HTML du viewer généré | **9,4 Mo** | 🔴 tous les `body` inlinés dans le JSON |
| Nav (`renderNav`) | 6000 boutons DOM créés d'un coup | 🔴 même dans les groupes repliés |
| Animation | `animationDelay = idx*12ms` → 72 s sur le 6000ᵉ | 🔴 cassée à l'échelle |

Le **coût tokens de Claude est déjà maîtrisé** par le sharding (démarrage ≈ 700 tokens quelle que soit la taille). Le goulot à grande échelle est **l'UI** : taille du fichier, DOM massif, animation. À 60 000 faits, le viewer ferait ~94 Mo — intenable.

## Décisions (validées)

1. **Abandon de l'autonomie `file://`** au profit d'un **mini-serveur local** : l'index ne contient plus que les **métadonnées** (léger), les `body` sont servis **à la demande**.
2. **Recherche hybride** : filtrage instantané sur name/description côté client + **full-text serveur** (grep) sur demande.
3. **Arbre récursif de profondeur arbitraire** (N niveaux, émergente) — pas de plafond codé.
4. **Lazy-render** : les enfants d'un nœud ne sont rendus qu'à son ouverture.
5. **Zéro dépendance** : serveur en `http.server` (stdlib Python).

## Architecture

```
build-viewer.py   →  index MÉTADONNÉES seules : {name, description, type, path[], file}
                     ~1 Mo pour 6000 faits (zéro body)
serve-viewer.py   →  http.server stdlib, bind 127.0.0.1 :
                     • GET /            → HTML du viewer + index métadonnées
                     • GET /fact?f=…    → body d'UN fait (chemin validé dans le vault)
                     • GET /search?q=…  → grep récursif full-text sur les .md du vault
                     • auto-stop après inactivité (~30 min)
viewer-template   →  arbre récursif + lazy-render + fetch body au clic + recherche hybride
view.sh / memory-ui → lancent le serveur en arrière-plan, donnent http://localhost:PORT
```

`http://localhost:PORT` est plus fiable que `file://wsl.localhost` sous WSL2.

## Flux de données

1. **Ouverture** → HTML + index métadonnées (~1 Mo). Sidebar (arbre) construite, **tout replié** → DOM quasi vide.
2. **Déplier un nœud** → ses enfants (sous-nœuds + faits) rendus à ce moment (lazy, event `toggle`).
3. **Clic sur un fait** → `fetch('/fact?f=<path>/<fait>.md')` → body rendu en markdown ; un seul body en mémoire à la fois.
4. **Recherche** → instantané sur name/description (client) ; bouton « dans le contenu » → `fetch('/search?q=…')` → grep serveur → faits matchants.

## Arbre récursif N-niveaux

- `build-viewer` : remplace `domain` (un segment) par **`path` = liste des segments du dossier**. Ex. `mailing/transactionnel/relances/fait.md` → `path = ["mailing","transactionnel","relances"]`. Fait à la racine → `path = []` → groupe « général ».
- Le JS construit un **arbre** depuis les `path` de tous les faits (un nœud par segment).
- `renderNav` **récursif** : un nœud = `<details>` (libellé du segment + compte des descendants) → enfants (sous-nœuds + faits feuilles), rendus à l'ouverture.
- Profondeur **émergente** (1…N), aucun plafond. « général » (`path` vide) en tête.

Capacité (seuil ~150 entrées/index) : 2 niveaux ≈ 22 500 faits, 3 ≈ 3,4 M, 4 ≈ 506 M. La profondeur ne se crée que quand un index parent déborde.

## Sécurité & cycle de vie du serveur

- **Bind `127.0.0.1` uniquement.**
- `/fact?f=…` et `/search` : **résoudre le chemin et vérifier qu'il reste dans le vault** (`os.path.realpath` commençant par le vault) → rejet du path-traversal (`../`, chemins absolus). Ne servir que des `.md`.
- **Auto-stop** après ~30 min d'inactivité ; le serveur écrit son port (fichier d'état) pour que `memory-ui` réutilise une instance vivante au lieu d'en empiler.
- **Une instance par vault.**

## Testing

- **`build-viewer`** (`unittest`) : `path` récursif multi-niveaux ; racine → « général » ; `index/` ignoré ; **aucun `body`** dans l'index généré (vérifier la légèreté) ; `MEMORY.md` toujours l'index.
- **`serve-viewer`** (`unittest`) : `/fact` renvoie le bon body **et rejette** `../etc/passwd` & chemins hors vault ; `/search` renvoie les faits dont le contenu matche ; 404 sur fichier absent. Testable via `http.server` en thread + `urllib`.
- **Viewer JS** : vérif manuelle (arbre récursif, lazy, fetch body, recherche hybride) + génération.

## Découpage en plans

Deux plans séquentiels, chacun produit du logiciel testable :

- **Plan A — Backend** : `build-viewer` produit le **nouvel index métadonnées + `path`** (via un mode/flag dédié, ex. `--metadata-only`) **sans retirer** le comportement actuel, et `serve-viewer.py` (endpoints + sécurité). Entièrement couvert par `unittest`. → Le viewer actuel continue de fonctionner pendant ce plan.
- **Plan B — Frontend & intégration** : refonte du `viewer-template` (arbre récursif, lazy-render, fetch body, recherche hybride) + bascule de `view.sh`/`memory-ui` sur le serveur + le nouveau format. L'ancien mode statique de `build-viewer` est retiré **à la fin** de ce plan, une fois le nouveau viewer fonctionnel.

**Transition sans casse** : tant que le Plan B n'a pas basculé `view.sh`, le viewer statique actuel reste opérationnel ; le nouveau format et le serveur cohabitent sans le remplacer.

## Hors scope / évolutions futures

- **Export statique autonome** (`file://`) pour partage ponctuel — possible plus tard en option (réinjecter les body).
- **Optimisations tokens** (sous-index compact 1 ligne/fait, 3ᵉ/4ᵉ niveau, digest par domaine) — traitées après l'UI, dans un cycle séparé.
- **Index full-text persistant** (au lieu d'un grep à chaud) — seulement si le grep devient lent à très grande échelle.

## Décisions clés (récapitulatif)

1. Mini-serveur local (`http.server` stdlib, `127.0.0.1`) ; fin du `file://`.
2. Index = métadonnées seules ; `body` servi à la demande via `/fact`.
3. Recherche hybride : métadonnées client + full-text serveur.
4. Arbre récursif de profondeur arbitraire (`path[]`), lazy-render.
5. Sécurité : validation anti-traversal ; bind localhost ; auto-stop.
6. Découpage : Plan A (backend) puis Plan B (frontend).
