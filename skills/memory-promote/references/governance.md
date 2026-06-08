# Gouvernance de la mémoire — règles de PR

La mémoire canonique (branche `main` du vault) ne change **que par Pull Request**.

## Flux

```
/memory-promote  →  branche + commit + PR
                       │
       ┌───────────────┴────────────────┐
       ▼                                 ▼
GitHub web (visuel)              /memory-review (dans Claude, Phase 2)
diff, commentaires, approve      diff + approve/merge via gh
```

## Règle de merge (protection de branche `main` du vault)

- **≥ 1 approbation** d'un autre que l'auteur avant merge.
- **Pas d'auto-merge** de sa propre promotion.
- Passer à 2 approbations si l'équipe veut plus de rigueur.

Configurer côté GitHub : Settings → Branches → Branch protection rule sur `main`
(Require a pull request before merging + Require approvals).

## Ce qui est promu

- **Inclus** : `metadata.type: project` et `reference`.
- **Exclu** : `user`, `feedback`, et tout `feedback_*.md` (perso, restent locaux).

## Vérification sémantique (obligatoire avant la PR)

Chaque fait promu doit être confronté au **code actuel** : encore vrai ? non contredit par
la version déjà dans `main` ? Les faits périmés/contradictoires sont corrigés ou écartés,
pas poussés tels quels. C'est ce qui distingue la promotion d'un simple `git push`.

## Pourquoi cette barrière

Les vibe coders produisent beaucoup de faits, dont des bancals. La PR empêche qu'un fait
erroné devienne canonique pour toute l'équipe sans relecture.
