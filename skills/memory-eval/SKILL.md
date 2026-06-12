---
name: memory-eval
description: This skill should be used when the user asks to "évaluer le rappel", "tester la recherche mémoire", "mesurer la qualité du rappel", "le bon fait remonte-t-il", "evaluate recall", "test memory search quality", or "/memory-eval". It measures whether the right fact surfaces for realistic queries (recall@k, MRR) via the real search path, and points to remediation.
argument-hint: ""
allowed-tools: Bash, Read, Write
version: 0.1.0
---

# memory-eval — Évaluer la qualité du rappel

Mesure si **le bon fait remonte au bon moment** : pour des requêtes réalistes, le fait attendu
ressort-il dans le **top-k** ? Métriques `recall@k`, `MRR`, `rang #1` (discriminabilité), via le
**vrai** chemin de recherche (`search_memory`). **Lecture seule** : diagnostique, n'écrit aucun fait.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Générer des requêtes réalistes** : lire les faits (nom + description) du vault. Pour chaque
   fait, formuler **1-2 requêtes** telles qu'un humain les poserait (questions / mots-clés métier,
   **pas** la description recopiée). Écrire un fichier `cas.json` (dans un tmp) au format
   `[{"query": "<requête>", "expect": "<name-du-fait>"}]` (avec **Write**).

3. **Lancer l'éval** :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/eval-recall.py "<clone>" --cases "<cas.json>"
   ```

4. **Présenter** le rapport : `recall@k`, `MRR`, `rang #1`, et la **liste des ratés** (faits absents
   du top-k). Pour chaque raté ou faiblesse, proposer une **piste** :
   - description peu discriminante → **`/memory-lint`** (signale les descriptions courtes) ;
   - deux faits confusables (l'un masque l'autre) → **dédup** / fusion ;
   - rapport en mode **grep** (fastembed absent) → **`/memory-doctor`** pour l'éval sémantique ;
   - fait douteux/périmé → **`/memory-refresh`**.

5. **Comparaison auto (optionnel)** : `python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/eval-recall.py "<clone>"`
   (sans `--cases`) donne la base « chaque description retrouve-t-elle son fait ? » (retrievabilité /
   confusabilité), utile pour repérer les doublons.

## Points d'attention

- **Lecture seule** : ce skill **mesure**, il ne modifie aucun fait ; la remédiation passe par les
  autres skills.
- **Requêtes réalistes** : ne pas recopier la description (l'éval deviendrait triviale) ; varier les
  formulations comme un vrai utilisateur.
- **Mode grep** : sans fastembed, le recall est un proxy lexical faible — le rapport l'indique.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/eval-recall.py`** — moteur d'éval (recall@k / MRR / ratés).
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault.
- **`/memory-lint`**, **`/memory-doctor`**, **`/memory-refresh`** — remédiations selon le diagnostic.
