---
name: memory-ui
description: This skill should be used when the user asks to "ouvrir la mémoire", "voir la mémoire d'équipe", "visualiser la mémoire", "afficher le vault", "show team memory", "memory ui", or "/memory-ui". It launches a local read-only server for the project's memory vault and gives an http link to open in the browser, after confirmation.
argument-hint: ""
allowed-tools: Bash
version: 0.2.0
---

# memory-ui — Visualiser la mémoire d'équipe (lecture seule)

Lance un **petit serveur local** (lecture seule) qui sert le viewer du vault du projet courant :
arbre des domaines (N niveaux), contenu d'un fait chargé à la demande, recherche hybride
(métadonnées + plein texte). Le serveur écoute sur `127.0.0.1` uniquement et se **réutilise**
s'il tourne déjà.

## Procédure

1. **Demander confirmation avant de lancer la vue.** Indiquer que la commande démarre un serveur
   local (lecture seule, `127.0.0.1`) et fournit un **lien `http://` cliquable**, puis attendre
   l'accord. La commande **n'ouvre rien automatiquement** ; elle donne un lien.

2. **Lancer la vue** :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT%/}/scripts/view.sh
   ```

   Le script localise le vault, fait un `git pull` best-effort, démarre (ou réutilise) le serveur
   et affiche un lien `http://127.0.0.1:PORT/`. Il **n'ouvre aucun navigateur**.

3. **Relayer uniquement le lien** de la ligne « LIEN À COMMUNIQUER », tel quel
   (`http://127.0.0.1:PORT/`), pour que l'utilisateur **clique**.

   **Interdiction absolue** : ne lancer AUCUNE commande d'ouverture toi-même (`xdg-open`,
   `wslview`, `open`, `explorer.exe`, `cmd.exe`…). L'ouverture = le clic de l'utilisateur.

## Points d'attention

- **Vault requis** : si le script renvoie « Vault introuvable », lancer `/memory-setup` d'abord.
- **`http://` sous WSL2** : `http://127.0.0.1:PORT` est accessible depuis le navigateur Windows
  (forwarding WSL2) — plus fiable que les anciens liens `file://`.
- **Serveur réutilisé** : un seul serveur par vault ; les appels suivants gardent le même port.
  Le serveur lit le vault **à chaque requête**, donc après un `/memory-import` ou un `git pull`,
  **recharger l'onglet (F5)** suffit à voir les changements (rien à régénérer).
- **Lecture seule** : ce viewer n'écrit jamais dans le vault. L'ajout passe par `/memory-import`,
  la proposition/validation par `/memory-promote` et `/memory-review`.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/view.sh`** — lance/réutilise le serveur, donne le lien.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/serve-viewer.py`** — serveur (HTML + `/fact` + `/search`).
- **`${CLAUDE_PLUGIN_ROOT}/assets/viewer-template.html`** — gabarit du viewer (arbre, fetch, recherche).
