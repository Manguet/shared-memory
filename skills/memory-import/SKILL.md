---
name: memory-import
description: This skill should be used when the user asks to "importer un doc dans la mémoire", "normaliser ce document en mémoire", "transformer ce doc en faits", "ajouter de la doc au vault", "import doc to memory", or "/memory-import". It normalizes a raw document into atomic memory facts (frontmatter + one fact per file) in the vault working copy, ready for /memory-promote.
argument-hint: "[chemin-du-doc]"
allowed-tools: Bash, Read, Write, Grep, Glob
version: 0.1.0
---

# memory-import — Normaliser un document en faits mémoire

Transforme de la doc brute (fichier ou contenu fourni) en **faits atomiques** au format
mémoire, écrits dans le **clone du vault** (working copy = étage 1, local). Ces faits seront
ensuite proposés à l'équipe via `/memory-promote`. Ce skill **ne pousse rien** lui-même.

## Procédure

1. **Localiser le vault** :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Obtenir la source** : lire le fichier passé en argument, ou utiliser le contenu fourni
   par l'utilisateur.

3. **Découper en faits atomiques** : un fait = une idée durable et autonome. Éviter de
   recopier la doc telle quelle ; en extraire les faits réutilisables.

4. **Écrire un fichier par fait** dans le clone du vault, en suivant
   `${CLAUDE_PLUGIN_ROOT}/assets/fact-template.md` :
   - `name` : slug kebab-case unique (vérifier l'absence de collision avec Glob/Grep) ;
   - `description` : une ligne pour le recall ;
   - `metadata.type` : `project` ou `reference` (jamais `user`/`feedback` ici) ;
   - corps concis, liens `[[autre-slug]]` vers les faits connexes.

5. **Mettre à jour `MEMORY.md`** (l'index) du vault : une ligne par nouveau fait
   (`- [Titre](fichier.md) — accroche`).

6. **Confirmer** : lister les faits créés et rappeler que `/memory-promote` poussera la branche de proposition.

## Points d'attention

- **Étage 1 uniquement** : on écrit dans la working copy, pas dans `main`. Rien n'est partagé
  tant que `/memory-promote` n'a pas poussé et fait fusionner une branche.
- **Pas de doublons** : avant de créer un fait, vérifier qu'un fichier ne couvre pas déjà le
  sujet (le mettre à jour plutôt que d'en créer un second).
- **Pas de perso** : ne jamais créer de faits `type: user`/`feedback` via l'import.

## Prochaine étape (guider l'utilisateur)

Terminer en disant mot pour mot : « Pour proposer ces faits à l'équipe, lance
`/memory-promote`. » Les faits restent locaux tant que ce n'est pas fait.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/assets/fact-template.md`** — gabarit d'un fait.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — helpers de localisation du vault.
