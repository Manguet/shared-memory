# Gouvernance de la mémoire — revue de branche (git seul)

La mémoire canonique (`main` du vault) ne change **que par revue d'une branche de proposition**,
entièrement en **git** (sans `gh`).

## Flux

```
/memory-promote  →  branche promote/<…> + commit + push
                       │
                       ▼
   Un RÉFÉRENT (≠ auteur) relit via /memory-review :
     git diff origin/main...origin/<branche>
                       │
              approuve │ refuse
                       ▼
     git merge --no-ff + git push origin main   →  canonique pour tous
```

## Règle de fusion (protection de `main`)

Côté GitHub : repo du vault → Settings → Branches → règle sur `main` :
- **Restrict who can push to matching branches** → uniquement les **référents**.

Ainsi un vibe coder ne peut pousser que des branches `promote/*` ; seul un référent fusionne
vers `main`. Pas d'auto-validation (le référent n'est pas l'auteur).

## Ce qui est promu

- **Inclus** : `metadata.type: project` et `reference`.
- **Exclu** : `user`, `feedback`, et tout `feedback_*.md` (perso, restent locaux).

## Vérification sémantique (obligatoire avant la fusion)

Chaque fait doit être confronté au **code actuel** : encore vrai ? non contredit par la version
déjà dans `main` ? Les faits périmés/contradictoires sont corrigés ou écartés, pas fusionnés.

## Pourquoi cette barrière

Les vibe coders produisent beaucoup de faits, dont des bancals. La revue par un référent
empêche qu'un fait erroné devienne canonique pour toute l'équipe.

## Conflits (à la fusion)

`index/**` est **dérivé** (régénéré par `reshard.py`) ; `<domaine>/<fait>.md` est la **source** ;
`MEMORY.md` est la **carte curée**. Un conflit de merge se traite donc selon le fichier :

- **`index/<domaine>.md`** (cas fréquent : deux ajouts de faits au même domaine) → conflit
  **dérivé**, résolu automatiquement en régénérant : `scripts/resolve-conflicts.py` lance reshard
  et stage les index.
- **`<domaine>/<fait>.md`** (deux éditions du même fait) → **humain** : choisir la bonne version
  (véracité), `git add`.
- **`MEMORY.md`** (deux nouveaux domaines) → **humain** : garder l'union des domaines, vérifier
  qu'aucun ne double un domaine proche.

**Flux en deux temps** : `resolve-conflicts.py` ne régénère les index que lorsqu'il ne reste
**aucun** conflit de fait/carte (reshard ne doit jamais lire de marqueurs). Tant qu'il en reste, il
les liste et sort en code 1 ; après résolution humaine + `git add`, relancer (code 0). En dernier
recours, `git merge --abort` annule la fusion sans rien pousser.
