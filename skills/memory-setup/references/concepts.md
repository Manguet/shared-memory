# Modèle de la mémoire partagée

Résumé pour exécuter `/memory-setup` en connaissance de cause. Détail complet :
`docs/ARCHITECTURE.md` du plugin.

## Substrat

La mémoire native de Claude Code = des fichiers `.md` plats (frontmatter + corps +
liens `[[wikilink]]`) dans `~/.claude/projects/<slug>/memory/`. Le `<slug>` est dérivé du
chemin absolu du projet (runs non-alphanumériques → `-`). La mémoire est donc **par-projet**.

## Principe du setup

Remplacer ce dossier local par un **symlink vers un clone d'un vault git privé** :

```
~/.claude/projects/<slug>/memory  ──symlink──►  clone local du vault (git)
```

Dès lors, lecture (index `MEMORY.md` au démarrage, recall en session) et écriture passent
par le vault, partagé avec l'équipe.

## Deux étages

- **Étage 1 — local** : working copy non commitée ; faits `type: user`/`feedback` (perso),
  brouillons. Jamais partagés (gitignore + non promus).
- **Étage 2 — canonique** : branche `main` du vault, faits `type: project`/`reference`
  validés par revue de branche.

## Multi-vault

Un **vault par projet/équipe**, hébergé où l'équipe veut. Le **plugin** est unique et global.
Un **registre JSON local** (`~/.config/shared-memory/registry.json`) relie, pour chaque
projet : slug → URL vault → clone → symlink.

## Sécurité

Le contenu mémoire (vault) est **privé**. Ne jamais committer un vault dans un repo public,
ni dans le repo du plugin.
