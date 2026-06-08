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
