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

4bis. **Vérifier les quasi-doublons** avant d'écrire chaque fait. Lancer :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/similar.py "<clone>" --text "<nom>. <description>. <corps>"
   ```

   Si la sortie contient des `similar` (cosine ≥ 0.85), **proposer à l'utilisateur de mettre à jour
   le fait existant** (le plus proche) plutôt que d'en créer un nouveau ; ne créer un nouveau fait
   que s'il est réellement distinct. Si `vector_inactive: true` (fastembed absent), le **mentionner**
   (« dédup sémantique inactive — `pip install fastembed` ») et continuer sans bloquer.

5. **Écrire un fichier par fait** dans `<domaine>/<fait>.md` du clone, en suivant
   `${CLAUDE_PLUGIN_ROOT}/assets/fact-template.md` :
   - `name` : slug kebab-case unique (vérifier l'absence de collision avec Glob/Grep) ;
   - `description` : une ligne **discriminante** (distingue le fait de ses voisins du même
     domaine) — elle sert au recall **et** alimente directement le sous-index compact (DRY) ;
   - `metadata.type` : `project` ou `reference` (jamais `user`/`feedback` ici) ;
   - `metadata.reviewed` : la **date du jour** (`AAAA-MM-JJ`) — le fait vient d'être écrit/vérifié.
   - corps concis, liens `[[autre-slug]]` vers les faits connexes.

6. **Régénérer l'index via reshard** (au lieu d'écrire la ligne à la main). Compter d'abord les
   faits du domaine ; s'il **dépasse ~150 faits**, **prévenir l'utilisateur** qu'un découpage en
   sous-domaines (déplacement de faits) va avoir lieu et **demander son accord**. Puis lancer :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

   reshard reconstruit `index/**` au format compact (description reprise du frontmatter, DRY) et
   **préserve la carte `MEMORY.md`** (curée à la main). Si le fait crée un **nouveau domaine**,
   ajouter sa ligne à la section « Domaines » de `MEMORY.md` **à la main** (reshard n'y touche pas).
   Si reshard a créé des sous-domaines `part-xx`, le **signaler** (l'utilisateur pourra les
   renommer). Détails : `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`.

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
- **`${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py`** — régénère les index compacts et découpe les
  domaines trop gros en sous-domaines.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/similar.py`** — détecte les quasi-doublons sémantiques d'un fait
  candidat (réutilise les embeddings).
