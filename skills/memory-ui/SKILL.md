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

1. **Demander confirmation avant de générer la vue.** Indiquer que la commande va générer un
   fichier HTML local (lecture seule) et fournir un **lien cliquable** vers la mémoire, puis
   attendre l'accord. La commande **n'ouvre rien automatiquement** ; elle donne un lien.

2. **Générer la vue** :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT%/}/scripts/view.sh
   ```

   Le script localise le vault, construit le HTML et affiche un lien `file://` cliquable.
   Il **n'ouvre aucun navigateur** (volontaire : sous WSL2 l'ouverture auto casse le lien).

3. **Relayer uniquement le lien** de la ligne « LIEN À COMMUNIQUER », tel quel
   (`file://wsl.localhost/…`), pour que l'utilisateur **clique**. **Ne jamais afficher de chemin
   `/tmp/…`** (Windows ne peut pas l'ouvrir → `ERR_FILE_NOT_FOUND`).

   **Interdiction absolue** : ne lancer AUCUNE commande d'ouverture toi-même (`xdg-open`,
   `wslview`, `open`, `explorer.exe`, `cmd.exe`…). L'ouverture = le clic de l'utilisateur.

## Points d'attention

- **Vault requis** : si le script renvoie « Vault introuvable », lancer `/memory-setup` d'abord.
- **Pas d'ouverture automatique** : le script ne fait que produire un lien `file://` cliquable
  (chemin converti pour Windows sous WSL2). L'utilisateur **clique** le lien — c'est volontaire,
  car toute ouverture auto sous WSL2 produit un lien cassé.
- **Mise à jour** : après un `/memory-import`, le HTML est régénéré automatiquement →
  **recharger l'onglet (F5)** montre les nouveaux faits. `/memory-ui` fait aussi un `git pull`
  pour récupérer les faits arrivés via l'équipe.
- **Lecture seule** : ce viewer n'écrit jamais dans le vault. L'ajout passe par `/memory-import`,
  la proposition/validation par `/memory-promote` et `/memory-review`.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/view.sh`** — build + open.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/build-viewer.py`** — parse le vault, injecte dans le template.
- **`${CLAUDE_PLUGIN_ROOT}/assets/viewer-template.html`** — gabarit HTML autonome.
