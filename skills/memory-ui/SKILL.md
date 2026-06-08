---
name: memory-ui
description: This skill should be used when the user asks to "ouvrir la mémoire", "voir la mémoire d'équipe", "visualiser la mémoire", "afficher le vault", "show team memory", "memory ui", or "/memory-ui". It builds a self-contained read-only HTML viewer of the project's memory vault and opens it in the browser, after confirmation.
allowed-tools: Bash
version: 0.1.0
---

# memory-ui — Visualiser la mémoire d'équipe (lecture seule)

Construit un **fichier HTML autonome** affichant tous les faits du vault du projet courant
(recherche, filtres par type, liens) et l'ouvre dans le navigateur. **Lecture seule, aucun
serveur, aucune écriture** — Phase 1 de l'interface visuelle.

## Procédure

1. **Demander confirmation avant d'ouvrir le navigateur.** Indiquer à l'utilisateur que la
   commande va générer un HTML local et l'ouvrir dans son navigateur, et attendre son accord.

2. **Générer et ouvrir le viewer** :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/scripts/view.sh
   ```

   Le script localise le vault du projet (via le registre, sinon via le symlink mémoire),
   construit `/tmp/shared-memory-view-<slug>.html` et l'ouvre selon l'OS
   (`wslview` sous WSL2, `open` sous macOS, `xdg-open` sous Linux).

3. **Si l'ouverture échoue** (pas de navigateur détecté), communiquer le chemin du fichier
   HTML généré pour que l'utilisateur l'ouvre manuellement.

## Points d'attention

- **Vault requis** : si le script renvoie « Vault introuvable », lancer `/memory-setup` d'abord.
- **WSL2** : l'ouverture auto nécessite `wslview` (paquet `wslu`). Sans lui, le script imprime
  le chemin à ouvrir à la main (le fichier est sous le système Linux de WSL2).
- **Lecture seule** : ce viewer n'écrit jamais dans le vault. L'édition/validation passe par
  `/memory-promote` (Phase 1) ; un backend d'écriture viendra en Phase 2.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/view.sh`** — build + open.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/build-viewer.py`** — parse le vault, injecte dans le template.
- **`${CLAUDE_PLUGIN_ROOT}/assets/viewer-template.html`** — gabarit HTML autonome.
