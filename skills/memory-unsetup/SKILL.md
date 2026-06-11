---
name: memory-unsetup
description: This skill should be used when the user asks to "débrancher la mémoire", "délier le vault", "déconnecter la mémoire d'équipe", "retirer le symlink mémoire", "unlink memory", "unsetup memory", or "/memory-unsetup". It removes this project's memory symlink and registry entry (the inverse of /memory-setup), keeping the vault clone (your data).
argument-hint: ""
allowed-tools: Bash, AskUserQuestion
version: 0.1.0
---

# memory-unsetup — Débrancher la mémoire du projet

Inverse de `/memory-setup` : retire le **symlink** mémoire et l'**entrée de registre** du projet
courant. **Garde le clone du vault** (tes données, y compris d'éventuels brouillons non promus).
Ne supprime jamais une vraie mémoire locale (uniquement un symlink).

## Procédure

1. **Vérifier que le projet est branché** :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, le dire (« projet non branché ») et s'arrêter.

2. **Confirmer** (AskUserQuestion) : « Débrancher la mémoire de ce projet ? Le clone du vault est
   conservé ; tu pourras re-brancher via `/memory-setup`. » Ne rien faire sans accord.

3. **Débrancher** :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT%/}/scripts/unlink-vault.sh "${CLAUDE_PROJECT_DIR:-$PWD}"
   ```

4. **Rapporter** : le symlink et l'entrée de registre sont retirés, le clone est conservé (chemin
   affiché par le script). Rappeler `/memory-setup <url>` pour re-brancher, et `uninstall.sh` (en
   terminal) pour retirer complètement le plugin.

## Points d'attention

- **Données conservées** : le clone du vault n'est jamais supprimé par ce skill.
- **Sécurité** : seul un symlink est retiré ; une vraie mémoire locale est laissée intacte.
- **Confirmation obligatoire** avant de débrancher.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/unlink-vault.sh`** — débranchement (symlink + registre).
- **`${CLAUDE_PLUGIN_ROOT}/scripts/uninstall.sh`** — désinstallation machine (terminal).
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault / registre.
