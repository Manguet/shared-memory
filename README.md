# shared-memory

Plugin Claude Code de **mémoire d'équipe partagée par projet**.

Branche la mémoire native de Claude Code (`~/.claude/projects/<slug>/memory/`, locale et non
partagée) sur un **vault git privé** (un par équipe) : devs **et** vibe coders partagent
**une seule source de vérité** par projet — consulter, contribuer, valider par revue de branche git — sans
application séparée.

## Idée en une phrase

Mémoire native = fichiers `.md` locaux → symlink vers un **vault git** géré par le plugin.
Mémoire **shardée par domaine** (carte `MEMORY.md` + sous-index compacts), **recherche sémantique**
optionnelle (outil MCP `search_memory`, repli grep), **viewer web local** (lecture seule), et
**gouvernance par revue de branche git**.

## Distinction essentielle

| Repo | Contenu | Visibilité |
|------|---------|------------|
| **plugin** (ce repo) | l'outil : skills, viewer, scripts | **public** (aucun secret) |
| **vault** (un par équipe) | la mémoire : `MEMORY.md` + faits `.md` | privé à l'équipe |

## Installation

**Guide complet pas-à-pas (devs + non-devs)** : [`INSTALL.md`](INSTALL.md).

Le repo plugin est **public** (l'outil ne contient aucun secret). Installation par script,
**locale**, sans publication dans aucun catalogue :

```
curl -fsSL https://raw.githubusercontent.com/Manguet/shared-memory/main/install.sh | bash
```

Le script vérifie les prérequis, clone le plugin dans `~/.shared-memory/plugin`, et affiche
les commandes `/plugin` à coller dans Claude Code (ajout par **chemin local**, puis `/reload-plugins`). Vérifier
seulement les prérequis : `bash scripts/doctor.sh`.

## Skills

| Skill | Rôle |
|-------|------|
| `/memory-setup` | clone le vault du projet + crée le symlink + écrit le registre local |
| `/memory-list` | consulter / chercher dans la mémoire (conversationnel) |
| `/memory-import` | normaliser un doc brut en faits mémoire (working copy) |
| `/memory-promote` | collecte les faits `project`/`reference`, vérifie contre le code, pousse une branche de proposition |
| `/memory-review` | relire et fusionner les branches de proposition (git seul) |
| `/memory-ui` | ouvre un viewer web local (serveur lecture seule) du vault dans le navigateur |
| `/memory-doctor` | diagnostiquer la recherche mémoire (`search_memory`) et proposer les installs (fastembed) |

## Recherche & passage à l'échelle

- **Sharding par domaine** : la carte `MEMORY.md` (chargée au démarrage) ne liste que des domaines ; chaque domaine a un **sous-index compact** `index/<domaine>.md` (1 ligne/fait), lu à la demande → coût tokens de démarrage borné quelle que soit la taille.
- **`search_memory` (MCP)** : outil que Claude appelle en session ; **recherche vectorielle locale** (fastembed, optionnel) avec **repli grep** si absent. Renvoie des **pointeurs** de faits (jamais le contenu) — *l'index aiguille, le fait est la source*.
- **`reshard.py`** : redécoupe récursivement un domaine trop gros en sous-domaines (`part-xx`) pour qu'aucun index ne dépasse ~150 lignes ; **préserve** la carte `MEMORY.md` curée.
- **`/memory-doctor`** : diagnostique les prérequis de la recherche (fastembed, modèle) et propose les installs — pas de dégradation silencieuse.

## Démarrage

```
# Dans un projet déjà ouvert dans Claude Code :
/memory-setup git@github.com:<org>/<projet>-memory.git
/memory-ui            # visualiser
# … travail … puis en fin de session :
/memory-promote       # proposer ses faits (branche git)
```

## Prérequis

- `git` authentifié (accès au vault privé), `python3`.
- **Optionnel** : `fastembed` (`pip install fastembed`) pour la recherche sémantique de `search_memory` ; sans lui, repli automatique sur grep (`/memory-doctor` propose l'install).

## Structure

```
shared-memory/
├── .claude-plugin/         (plugin.json, marketplace.json)
├── .mcp.json               # déclare le serveur MCP (search_memory)
├── skills/                 (memory-setup, -list, -import, -promote, -review, -ui, -doctor)
├── scripts/
│   ├── lib.sh, setup-vault.sh, view.sh, doctor.sh        # bash : setup, lancement viewer, prérequis install
│   ├── build-viewer.py, serve-viewer.py                  # viewer : lecture du vault + serveur http local
│   ├── sm_paths.py, embed.py, mcp-server.py, doctor.py   # recherche : chemins, embeddings, serveur MCP, diagnostic
│   └── reshard.py, gen-synth-vault.py, verify-scale.py   # redécoupage en sous-domaines + tests d'échelle
├── assets/                 (viewer-template.html, fact-template.md)
├── tests/                  (unittest : viewer, embeddings, MCP, doctor, reshard)
├── docs/                   (ARCHITECTURE.md, domain-convention.md)
└── INSTALL.md
```

Conception complète : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · convention de sharding :
[`docs/domain-convention.md`](docs/domain-convention.md).
