---
name: memory-setup
description: This skill should be used when the user asks to "configurer la mémoire partagée", "brancher le vault", "connecter la mémoire d'équipe", "set up shared memory", "/memory-setup", or wants to link this project's Claude memory to a shared team vault. It clones a private git vault and symlinks it into the native memory directory.
argument-hint: "[url-du-vault] [chemin-de-clone]"
allowed-tools: Bash, Read, AskUserQuestion
version: 0.1.0
---

# memory-setup — Brancher la mémoire du projet sur le vault d'équipe

Branche la mémoire native de Claude Code (`~/.claude/projects/<slug>/memory/`) du projet
courant sur un **vault git privé partagé**, via un symlink, et enregistre le mapping dans le
registre local (`~/.config/shared-memory/registry.json`).

## Contexte

La mémoire native est un dossier local par-machine, donc non partagée. Ce skill la remplace
par un **symlink vers un clone d'un vault git** : dès lors, lecture et écriture de mémoire
passent par le vault, partagé avec l'équipe. Voir `references/concepts.md` pour le modèle
complet (deux étages, multi-vault, gouvernance par revue de branche git).

## Procédure

1. **Déterminer le vault.** Si l'utilisateur a fourni une URL en argument, l'utiliser.
   Sinon, lui demander l'URL du vault (convention : `git@github.com:<org>/<projet>-memory.git`),
   ou lui proposer un vault du catalogue `references/vaults.md` s'il existe.

2. **Confirmer l'emplacement du clone** (optionnel). Par défaut le vault est cloné dans
   `~/.shared-memory/vaults/<nom>`. Proposer de changer si l'utilisateur le souhaite —
   l'emplacement est libre.

3. **Lancer le script de setup** depuis la racine du projet courant :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup-vault.sh "<vault-url>" "[clone-path]"
   ```

   Le script : clone (ou pull) le vault, **sauvegarde** toute mémoire locale existante sans
   la détruire, crée le symlink, et met à jour le registre.

4. **Vérifier la sortie.** Confirmer à l'utilisateur que le symlink pointe bien vers le clone
   et que le registre est à jour. Si une sauvegarde `memory.local-backup-*` a été créée,
   prévenir que ses faits utiles devront être promus via `/memory-promote`.

## Points d'attention

- **Ne jamais détruire une mémoire locale existante** : le script la déplace en sauvegarde.
  Si le script signale une sauvegarde, le mentionner explicitement.
- **Slug** = chemin du projet avec runs non-alphanumériques remplacés par `-`. Si le dossier
  `~/.claude/projects/<slug>/` n'existe pas encore, c'est que le projet n'a jamais été ouvert
  dans Claude Code à ce chemin — le vérifier avec l'utilisateur.
- **Prérequis** : `git` authentifié (SSH/token) avec accès au repo privé du vault, et `python3`.

## Prochaine étape (guider l'utilisateur)

Terminer en indiquant explicitement les commandes utiles maintenant que le vault est branché :
`/memory-ui` (visualiser), `/memory-list <terme>` (chercher), `/memory-import` (ajouter).
Donner les commandes mot pour mot — c'est ce qui guide les non-devs.

## Ressources

- **`references/concepts.md`** — modèle architectural (étages, multi-vault, gouvernance).
- **`references/vaults.md`** — catalogue des vaults disponibles (à compléter par l'équipe).
- **`${CLAUDE_PLUGIN_ROOT}/scripts/setup-vault.sh`** — clone + symlink + registre.
