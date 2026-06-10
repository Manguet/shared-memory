---
name: memory-list
description: This skill should be used when the user asks to "consulter la mémoire", "que sait-on sur X", "chercher dans la mémoire", "qu'y a-t-il en mémoire", "list memory", "search team memory", or "/memory-list". It reads and searches the project's shared memory vault and summarizes matching facts.
argument-hint: "[terme-de-recherche]"
allowed-tools: Bash, Read, Grep, Glob
version: 0.2.0
---

# memory-list — Consulter et chercher dans la mémoire d'équipe

Lit le vault du projet courant et présente les faits pertinents (tous, ou filtrés par un
terme de recherche). Surface conversationnelle de consultation, complémentaire du viewer
visuel `/memory-ui`.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Sans terme de recherche** : lire la carte `MEMORY.md` (les **domaines**), puis, pour le
   détail d'un domaine, son sous-index **compact** `index/<domaine>.md` (une ligne par fait). Si ce
   sous-index pointe vers des **sous-domaines** (`index/<domaine>/<sous>.md`), suivre le pointeur du
   sous-domaine pertinent. Restituer par domaine → faits. Les faits à la racine (« général »)
   figurent dans la section « Général » de la carte.

3. **Avec un terme** : `Grep` **récursif** sur le vault (`.md`, sous-dossiers de domaines inclus)
   pour trouver les faits qui matchent (nom, description, corps), puis lire/résumer les pertinents.

4. **Restituer** chaque fait avec : son `name`, son **domaine** (dossier parent), son `type`
   (`project`/`reference`/…), et un résumé. Citer le fichier source (`<domaine>/<fait>.md`).

## Points d'attention

- **L'index aiguille, le fait est la source** : le sous-index sert à **trouver** ; toute
  affirmation (valeur, citation, ligne de code) provient du **fait lu en entier**, pas de la ligne
  d'index.
- **Fraîcheur** : les faits sont des observations datées. Avant d'**affirmer** qu'un fait est
  vrai (citation de fichier/ligne, comportement du code), le confronter au code actuel.
- **Lecture seule** : ce skill n'écrit jamais. Pour ajouter/normaliser : `/memory-import` ;
  pour partager : `/memory-promote`.

## Prochaine étape (guider l'utilisateur)

Selon le résultat, suggérer la commande suivante mot pour mot : `/memory-import` pour ajouter
un fait manquant, `/memory-ui` pour la vue visuelle, `/memory-promote` pour partager.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — carte des domaines, sous-index, structure.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — `sm_slug`, `sm_vault_clone_for_slug`.
