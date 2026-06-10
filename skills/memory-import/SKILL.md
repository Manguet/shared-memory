---
name: memory-import
description: This skill should be used when the user asks to "importer un doc dans la mémoire", "normaliser ce document en mémoire", "transformer ce doc en faits", "ajouter de la doc au vault", "import doc to memory", or "/memory-import". It normalizes a raw document into atomic memory facts (frontmatter + one fact per file) in the vault working copy, ready for /memory-promote.
argument-hint: "[chemin-du-doc]"
allowed-tools: Bash, Read, Write, Grep, Glob
version: 0.2.0
---

# memory-import — Normaliser un document en faits mémoire

Transforme de la doc brute (fichier ou contenu fourni) en **faits atomiques** au format
mémoire, écrits dans le **clone du vault** (working copy = étage 1, local). Ces faits seront
ensuite proposés à l'équipe via `/memory-promote`. Ce skill **ne pousse rien** lui-même.

## Procédure

1. **Localiser le vault** :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Obtenir la source** : lire le fichier passé en argument, ou utiliser le contenu fourni
   par l'utilisateur.

3. **Découper en faits atomiques** : un fait = une idée durable et autonome. Éviter de
   recopier la doc telle quelle ; en extraire les faits réutilisables.

4. **Choisir le domaine** du fait (→ `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`).
   Déduire le domaine du sujet ; lire la carte `MEMORY.md` et **réutiliser un domaine existant
   proche** plutôt qu'en créer un nouveau (garde-fou anti-prolifération : `mailing` vs `emails` vs
   `mail`). En cas de doute, demander à l'utilisateur.

5. **Écrire un fichier par fait** dans `<domaine>/<fait>.md` du clone, en suivant
   `${CLAUDE_PLUGIN_ROOT}/assets/fact-template.md` :
   - `name` : slug kebab-case unique (vérifier l'absence de collision avec Glob/Grep) ;
   - `description` : une ligne **discriminante** (distingue le fait de ses voisins du même
     domaine) — elle sert au recall **et** alimente directement le sous-index compact (DRY) ;
   - `metadata.type` : `project` ou `reference` (jamais `user`/`feedback` ici) ;
   - corps concis, liens `[[autre-slug]]` vers les faits connexes.

6. **Mettre à jour le sous-index** `index/<domaine>.md` : ajouter **une ligne compacte** pour le
   fait — `` - `<nom>` — <description> · <type> → `<domaine>/<fait>.md` `` (reprendre **telle quelle**
   la `description` du frontmatter, DRY) ; le créer s'il n'existe pas. Si le domaine est **nouveau**,
   ajouter sa ligne dans la carte `MEMORY.md` (section « Domaines »). Si le sous-index approche
   **~150 lignes**, **alerter** et proposer un **découpage en sous-domaines** `index/<domaine>/<sous>.md`
   (semi-auto). Format détaillé : `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`.

7. **Régénérer le viewer** (pour qu'une vue déjà ouverte se mette à jour au rechargement de l'onglet) :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT%/}/scripts/view.sh --build-only
   ```

8. **Confirmer** : lister les faits créés (avec leur domaine) et rappeler que `/memory-promote` poussera la branche de proposition.

## Points d'attention

- **Étage 1 uniquement** : on écrit dans la working copy, pas dans `main`. Rien n'est partagé
  tant que `/memory-promote` n'a pas poussé et fait fusionner une branche.
- **Pas de doublons** : avant de créer un fait, vérifier qu'un fichier ne couvre pas déjà le
  sujet (le mettre à jour plutôt que d'en créer un second).
- **Convention de domaine** : ranger dans `<domaine>/`, tenir à jour `index/<domaine>.md` + la carte.
  Détails dans `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`.
- **Pas de perso** : ne jamais créer de faits `type: user`/`feedback` via l'import.

## Prochaine étape (guider l'utilisateur)

Terminer en disant mot pour mot : « Pour proposer ces faits à l'équipe, lance
`/memory-promote`. » Les faits restent locaux tant que ce n'est pas fait.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — structure shardée, sous-index, seuil.
- **`${CLAUDE_PLUGIN_ROOT}/assets/fact-template.md`** — gabarit d'un fait.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — helpers de localisation du vault.
