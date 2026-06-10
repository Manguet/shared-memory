# shared-memory

Plugin Claude Code de **mémoire d'équipe partagée par projet**.

Branche la mémoire native de Claude Code (`~/.claude/projects/<slug>/memory/`, locale et non
partagée) sur un **vault git privé** (un par équipe) : devs **et** vibe coders partagent
**une seule source de vérité** par projet — consulter, contribuer, valider par revue de branche git — sans
application séparée.

## Idée en une phrase

Mémoire native = fichiers `.md` locaux → symlink vers un **vault git** géré par le plugin,
avec **viewer HTML** optionnel et **gouvernance par revue de branche git**.

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
| `/memory-ui` | ouvre un viewer HTML autonome (lecture seule) du vault dans le navigateur |
| `/memory-doctor` | diagnostiquer la recherche mémoire (`search_memory`) et proposer les installs (fastembed) |

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

## Structure

```
shared-memory/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .mcp.json            # déclare le serveur MCP (search_memory)
├── skills/
│   ├── memory-setup/   (SKILL.md + references/)
│   ├── memory-list/    (SKILL.md)
│   ├── memory-import/  (SKILL.md)
│   ├── memory-promote/ (SKILL.md + references/)
│   ├── memory-review/  (SKILL.md)
│   └── memory-ui/      (SKILL.md)
├── scripts/            (lib.sh, setup-vault.sh, build-viewer.py, view.sh, doctor.sh)
├── assets/             (viewer-template.html, fact-template.md)
├── INSTALL.md
└── docs/ARCHITECTURE.md
```

Conception complète : [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
