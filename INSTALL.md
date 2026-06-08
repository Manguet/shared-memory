# Installation — shared-memory

Guide pas-à-pas pour **tout le monde**, devs comme non-devs (vibe coders). Deux parties :
**A.** ce que l'admin fait **une fois** pour l'équipe · **B.** ce que **chaque personne** fait
sur sa machine.

> Rappel : le **plugin** (cet outil) et les **vaults** (la mémoire) sont des repos séparés.
> Le plugin = `Manguet/shared-memory`. Un vault = `Manguet/<projet>-memory`, un par projet.

---

## Prérequis (tout le monde)

- **Claude Code** (déjà installé si tu l'utilises pour coder).
- **git**, **python3**.
- **gh** (GitHub CLI) — pour proposer/valider des mémoires.
- **WSL2 uniquement** : `wslu` (commande `wslview`) pour ouvrir le navigateur → `sudo apt install wslu`.
- Un **compte GitHub** : le plugin est **public** (clone sans auth), mais l'accès au **vault privé** de l'équipe est requis pour `/memory-setup`. Auth la plus simple : `gh auth login`.

Vérifie tout d'un coup :

```bash
bash scripts/doctor.sh
```

(Le script dit ce qui manque, sans rien modifier.)

---

## A. Admin — à faire une fois pour l'équipe

### 1. Publier le plugin (repo public)

```bash
# depuis /var/www/shared-memory
git add -A
git commit -m "shared-memory: plugin initial"
gh repo create Manguet/shared-memory --public --source=. --push
```

### 2. Créer un vault par projet (repo privé)

```bash
# exemple pour le projet negocian
gh repo create Manguet/negocian-memory --private --clone
cd negocian-memory
printf '# Memory\n' > MEMORY.md
git add -A && git commit -m "vault: init" && git push
```

Puis donner accès aux membres : repo → Settings → Collaborators.

### 3. Protéger la branche `main` du vault (la barrière de validation)

Sur GitHub : repo du vault → **Settings → Branches → Add branch protection rule** sur `main` :
- Require a pull request before merging
- Require approvals → **1** (ou 2 pour plus de rigueur)

Ainsi une mémoire ne devient canonique qu'après **revue et approbation** par un coéquipier.

### 4. (Optionnel) Renseigner le catalogue de vaults

Éditer `skills/memory-setup/references/vaults.md` pour lister les vaults disponibles, puis
commit/push. `/memory-setup` pourra les proposer.

---

## B. Chaque membre — sur sa machine

### 1. S'authentifier à GitHub (une fois)

Le plugin est public (clone sans auth), mais ton **vault d'équipe est privé** → auth requise
pour le cloner à l'étape `/memory-setup`.

```bash
gh auth login        # choisir GitHub.com → HTTPS → suivre les étapes
```

### 2. Installer le plugin

```bash
curl -fsSL https://raw.githubusercontent.com/Manguet/shared-memory/main/install.sh | bash
```

(ou : `git clone https://github.com/Manguet/shared-memory.git && bash shared-memory/install.sh`.)

Le script vérifie les prérequis, clone le plugin dans `~/.shared-memory/plugin`, et affiche
les 2 commandes à coller dans Claude Code :

```
/plugin marketplace add ~/.shared-memory/plugin
/plugin install shared-memory
```

> Installation **locale** : ajout par **chemin local**, rien n'est publié dans un catalogue public.

### 3. Brancher la mémoire du projet sur le vault

Ouvrir le projet dans Claude Code, puis :

```
/memory-setup git@github.com:Manguet/<projet>-memory.git
```

C'est tout. À partir de là, la mémoire de ce projet est partagée. Les commandes utiles :

| Commande | Quand |
|----------|-------|
| `/memory-ui` | voir la mémoire (et le guide visuel) |
| `/memory-list <terme>` | chercher |
| `/memory-import` | ajouter de la doc / un fait |
| `/memory-promote` | proposer ses faits à l'équipe (ouvre une PR) |
| `/memory-review` | relire / approuver les propositions |

---

## Tester en local (sans rien publier)

```bash
claude --plugin-dir /var/www/shared-memory
# puis /memory-ui, /memory-setup, …
```

---

## Dépannage

- **« Vault introuvable » à `/memory-ui`** → lancer `/memory-setup` d'abord.
- **Le navigateur ne s'ouvre pas (WSL2)** → `sudo apt install wslu` ; sinon, ouvrir à la main
  le chemin `/tmp/shared-memory-view-*.html` affiché.
- **`git clone` du vault refusé** → accès non accordé au repo privé, ou auth GitHub absente
  (`gh auth login`).
- **`~/.claude/projects/<slug>/` n'existe pas** → le projet n'a jamais été ouvert dans Claude
  Code à ce chemin. L'ouvrir une fois, puis relancer `/memory-setup`.
- **`/plugin marketplace add` ne répond pas** → le repo plugin n'est pas encore poussé, ou ton
  compte n'y a pas accès.
