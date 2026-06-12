# Onboarding équipe — shared-memory

Bienvenue. Ce guide d'une page te met en route en 10 minutes. Pour l'installation détaillée
(devs **et** non-devs), voir [`INSTALL.md`](INSTALL.md) ; pour le « pourquoi », le
[`README`](README.md).

> **L'idée en une phrase** : ce que tu apprends à Claude Code devient une **mémoire d'équipe
> partagée par projet** (des fichiers `.md` dans un dépôt git privé), au lieu de rester sur ta
> machine. Git fait la synchro ; une **revue** garde la qualité.

---

## Deux rôles

- **Référent** (une personne par équipe) : crée le **vault** (un dépôt git privé `…-memory`),
  protège sa branche `main` (seuls les référents y poussent), et **valide** les propositions
  (`/memory-review`). C'est le garde-fou qualité.
- **Membre** (toi, sans doute) : branche ton projet sur le vault, écris/utilises la mémoire au
  quotidien, et **proposes** tes faits (`/memory-promote`). Tu ne pousses jamais sur `main`
  directement.

---

## Démarrage membre (5 étapes)

1. **Installer le plugin** (une fois par machine) :
   ```bash
   curl -fsSL https://raw.githubusercontent.com/Manguet/shared-memory/main/install.sh | bash
   ```
   Puis, dans Claude Code, colle les 3 commandes `/plugin …` affichées + `/reload-plugins`.

2. **Brancher ton projet** sur le vault de l'équipe (dans le projet ouvert dans Claude Code) :
   ```
   /memory-setup git@github.com:<org>/<projet>-memory.git
   ```

3. **Vérifier la recherche** : `/memory-doctor`. Il propose `pip install fastembed` (recherche
   sémantique = bien meilleur rappel). Sans lui, repli automatique sur grep — ça marche quand même.

4. **C'est branché.** Au prochain démarrage de session, Claude reçoit automatiquement un **digest**
   de la mémoire d'équipe (rien à faire). Pour explorer/éditer à la main : `/memory-ui`.

5. **En fin de session**, propose tes nouveaux faits à l'équipe : `/memory-promote`. Un **référent**
   les relira via `/memory-review` avant qu'ils deviennent canoniques.

---

## Le quotidien : ce qui est automatique vs ce que tu fais

**Automatique (zéro effort)** : au démarrage de session → digest de la mémoire + `git pull` du
vault + rappel des faits non promus. En fin de session → rappel de promotion. Fraîcheur signalée
(`⚠` sur les faits ≥ 90 j).

**Toi, quand c'est utile** :

| Skill | Quand l'utiliser |
|---|---|
| `/memory-setup` · `/memory-unsetup` | brancher / débrancher un projet sur un vault |
| `/memory-seed` · `/memory-import` | amorcer un vault vide (CLAUDE.md, doc) / importer un doc en faits |
| `/memory-list` · `/memory-ui` | consulter / explorer + éditer (CRUD) dans le navigateur |
| `/memory-promote` · `/memory-review` | proposer ses faits / les valider (rôle référent) |
| `/memory-lint` | nettoyer le format des faits (rapport + fix opt-in) |
| `/memory-refresh` | re-vérifier les faits périmés contre le code, re-stamper |
| `/memory-eval` | mesurer la qualité du rappel (le bon fait remonte-t-il ?) |
| `/memory-doctor` | diagnostiquer la recherche sémantique |

Bon réflexe d'hygiène, de temps en temps : `/memory-lint` → `/memory-refresh` → `/memory-eval`.

---

## La règle d'or (gouvernance)

Rien ne devient **officiel** sans une **revue par un référent** (≠ l'auteur). Tu écris librement en
local (étage 1) ; `/memory-promote` pousse une **branche** ; `/memory-review` la **fusionne** dans
`main`. C'est ce qui empêche un fait bancal de devenir vérité partagée.

**Faits perso** (`type: user`/`feedback`, fichiers `feedback_*.md`) : restent **locaux**, jamais
partagés.

---

## En cas de conflit (rare)

Si deux personnes touchent le même domaine, la fusion peut entrer en conflit. Le référent lance
`scripts/resolve-conflicts.py` (intégré à `/memory-review`) : les **index** (dérivés) sont
régénérés automatiquement ; seuls de **vrais** conflits de faits demandent un arbitrage humain.

---

## Pour aller plus loin

- 🚀 [`INSTALL.md`](INSTALL.md) — installation pas-à-pas (référent + chaque membre), mise à jour,
  désinstallation.
- 📐 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — la conception complète.
- 🗂️ [`docs/domain-convention.md`](docs/domain-convention.md) — comment un fait est structuré et rangé.
