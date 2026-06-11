---
name: memory-refresh
description: This skill should be used when the user asks to "rafraîchir la mémoire", "re-vérifier les faits périmés", "mettre à jour les faits anciens", "revoir les faits à revérifier", "refresh memory", "re-verify stale facts", or "/memory-refresh". It lists stale facts (reviewed >= 90 days or never), re-verifies each project/reference fact against the current code, and re-stamps / corrects / retires it — drafts for /memory-promote.
argument-hint: ""
allowed-tools: Bash, Read, Grep, Glob, Edit, AskUserQuestion
version: 0.1.0
---

# memory-refresh — Re-vérifier les faits périmés

Ferme la boucle de fraîcheur : **lister** les faits périmés (`reviewed` ≥ 90 j ou jamais), les
**confronter au code actuel**, et **re-stamper** (encore vrais), **corriger** ou **retirer** (faux).
Écrit des **brouillons** (étage 1) ; rien n'est partagé tant que `/memory-promote` n'a pas eu lieu.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Lister les périmés** (lecture seule) :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/stale.py "<clone>"
   ```

   Séparer les faits **project/reference** (re-vérifiables contre le code) des faits **perso**
   (`user`/`feedback`). Si la liste est vide, le dire et s'arrêter.

3. **Si beaucoup de faits**, proposer un **sous-ensemble** (par domaine, ou les N plus vieux) pour
   garder la session focalisée.

4. **Pour chaque fait project/reference** (du plus vieux au plus récent) : le **confronter au code
   actuel** (Read/Grep/Glob) — encore vrai ? non contredit ?
   - **Encore vrai** → re-stamper :

     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/stale.py --restamp "<clone>/<chemin-du-fait>"
     ```

   - **Faux** → proposer au choix : **corriger** (éditer le corps pour coller à la réalité, puis
     re-stamper) ou **retirer** (supprimer le fichier ; la suppression se propage via
     `/memory-promote` → `/memory-review`).

5. **Faits perso périmés** → les **lister à juger** (préférence, pas de code à vérifier) ; ne
   re-stamper que si l'utilisateur confirme qu'ils tiennent encore.

6. **Confirmer le lot** avant d'écrire (AskUserQuestion) : récap « N re-stampés · M corrigés · K
   retirés ». Ne rien écrire sans accord.

7. **Régénérer les index** si des fichiers ont changé, puis guider vers `/memory-promote` :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

## Points d'attention

- **Re-stamper = « j'ai vérifié »**, pas « le fichier existe » : ne jamais re-stamper sans avoir
  confronté le fait au code. Pas de re-stampage en masse à l'aveugle.
- **Confirmation obligatoire** avant écriture ; brouillons (étage 1) → `/memory-promote`.
- **Pas d'archivage automatique** : retirer un fait est une décision humaine explicite.
- **Perso** (`user`/`feedback`) : pas de code à vérifier — l'utilisateur juge.

## Prochaine étape (guider l'utilisateur)

Terminer en disant mot pour mot : « Pour partager ces mises à jour, lance `/memory-promote`. »

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/stale.py`** — liste des périmés + re-stamp.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py`** — régénère `index/**` après changements.
- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — fraîcheur, format d'un fait.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault.
