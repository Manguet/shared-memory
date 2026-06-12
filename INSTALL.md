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
- Un **compte GitHub** : le plugin est **public** (clone sans auth), mais l'accès au **vault privé** de l'équipe est requis pour `/memory-setup`. Auth : clé SSH ajoutée à GitHub, ou token HTTPS (voir §B.1).
- **Optionnel** : `fastembed` (`pip install fastembed`) pour la **recherche sémantique** de `search_memory` ; sans lui, repli automatique sur grep. `/memory-doctor` le diagnostique et propose l'install.

Vérifie tout d'un coup :

```bash
bash scripts/doctor.sh
```

(Le script dit ce qui manque, sans rien modifier.)

---

## A. Admin — à faire une fois pour l'équipe

### 1. Publier le plugin (repo public)

Créer un repo **public** `shared-memory` sur github.com/Manguet (bouton *New repository*), puis :

```bash
# depuis /var/www/shared-memory
git add -A
git commit -m "shared-memory: plugin initial"
git branch -M main
git remote add origin https://github.com/Manguet/shared-memory.git
git push -u origin main
```

### 2. Créer un vault par projet (repo privé)

Créer un repo **privé** `<projet>-memory` sur github.com/Manguet, puis (exemple negocian) :

```bash
mkdir negocian-memory && cd negocian-memory
git init -b main
printf '# Memory\n' > MEMORY.md
git add -A && git commit -m "vault: init"
git remote add origin git@github.com:Manguet/negocian-memory.git
git push -u origin main
```

Puis donner accès aux membres : repo → Settings → Collaborators.

### 3. Protéger la branche `main` du vault (la barrière de validation)

Sur GitHub : repo du vault → **Settings → Branches → Add branch protection rule** sur `main` :
- **Restrict who can push to matching branches** → seuls les **référents**.

Ainsi un membre ne peut pousser que des branches `promote/*` ; seul un référent fusionne dans
`main` via `/memory-review`. La mémoire ne devient canonique qu'après cette revue.

### 4. (Optionnel) Renseigner le catalogue de vaults

Éditer `skills/memory-setup/references/vaults.md` pour lister les vaults disponibles, puis
commit/push. `/memory-setup` pourra les proposer.

---

## B. Chaque membre — sur sa machine

### 1. S'authentifier à GitHub (une fois)

Le plugin est public (clone sans auth), mais ton **vault d'équipe est privé** → auth requise
pour le cloner à l'étape `/memory-setup`. Au choix :

- **Clé SSH** (recommandé) : ajoute ta clé publique à GitHub (Settings → SSH and GPG keys).
  Si ta clé a une passphrase, charge-la une fois par session : `ssh-add ~/.ssh/id_ed25519`.
- **ou HTTPS + token** : crée un *Personal Access Token* et laisse git le mémoriser via son
  credential helper.

### 2. Installer le plugin

```bash
curl -fsSL https://raw.githubusercontent.com/Manguet/shared-memory/main/install.sh | bash
```

(ou : `git clone https://github.com/Manguet/shared-memory.git && bash shared-memory/install.sh`.)

Le script vérifie les prérequis, clone le plugin dans `~/.shared-memory/plugin`, et affiche
les 3 commandes à coller dans Claude Code :

```
/plugin marketplace add ~/.shared-memory/plugin
/plugin install shared-memory
/reload-plugins
```

> Installation **locale** : ajout par **chemin local**, rien n'est publié dans un catalogue public.

### 3. Brancher la mémoire du projet sur le vault

Ouvrir le projet dans Claude Code, puis :

```
/memory-setup git@github.com:Manguet/<projet>-memory.git
```

C'est tout. À partir de là, la mémoire de ce projet est partagée. (`/memory-setup` configure aussi
un **ignore local** des faits perso `feedback_*` — ils ne sont jamais poussés dans le vault partagé.)
Les commandes utiles :

| Commande | Quand |
|----------|-------|
| `/memory-ui` | voir la mémoire (et le guide visuel) |
| `/memory-lint` | valider et nettoyer le format des faits du vault (rapport + fix opt-in) |
| `/memory-refresh` | re-vérifier les faits périmés contre le code (re-stamp / corrige / retire) |
| `/memory-eval` | mesurer la qualité du rappel (recall@k, MRR) sur des requêtes réalistes |
| `/memory-seed` | amorcer un vault vide depuis CLAUDE.md + la doc (brouillons) |
| `/memory-list <terme>` | chercher |
| `/memory-import` | ajouter de la doc / un fait |
| `/memory-promote` | proposer ses faits à l'équipe (pousse une branche) |
| `/memory-review` | relire / fusionner les propositions (git) |
| `/memory-doctor` | diagnostiquer la recherche sémantique, proposer `fastembed` |

> **Automatique (hooks de session)** : à chaque démarrage de session, le plugin récupère les
> derniers faits de l'équipe (`git pull` best-effort) et te rappelle tes faits locaux non encore
> partagés — pense à `/memory-promote` **avant de fermer** pour éviter les décalages. Rien à
> lancer à la main.

---

## Tester en local (sans rien publier)

```bash
claude --plugin-dir /var/www/shared-memory
# puis /memory-ui, /memory-setup, …
```

---

## Dépannage

- **« Vault introuvable » à `/memory-ui`** → lancer `/memory-setup` d'abord.
- **Le navigateur ne s'ouvre pas tout seul (WSL2)** → cliquer le lien `http://localhost:…` affiché
  par `/memory-ui` (le viewer est servi par un petit serveur local ; tu peux y lire **et gérer**
  les faits — créer/éditer/supprimer — en brouillon local, à partager ensuite via `/memory-promote`).
- **`search_memory` indique « recherche sémantique inactive » (repli grep)** → `fastembed` n'est pas
  installé ; lancer `/memory-doctor`, qui propose `pip install fastembed`.
- **`git clone` du vault refusé** → accès non accordé au repo privé, ou auth git absente
  (clé SSH ajoutée à GitHub, ou token HTTPS).
- **`~/.claude/projects/<slug>/` n'existe pas** → le projet n'a jamais été ouvert dans Claude
  Code à ce chemin. L'ouvrir une fois, puis relancer `/memory-setup`.
- **`/plugin marketplace add` ne répond pas** → le repo plugin n'est pas encore poussé, ou ton
  compte n'y a pas accès.

## Mise à jour

Le plugin se met à jour en **relançant l'installateur** (il fait un `git pull` s'il est déjà cloné) :

```bash
curl -fsSL https://raw.githubusercontent.com/Manguet/shared-memory/main/install.sh | bash
```

Puis, dans Claude Code : `/reload-plugins`.

## Désinstallation

- **Débrancher un projet** (garde le clone du vault) : dans Claude Code, `/memory-unsetup`.
- **Désinstaller la machine** (retire le plugin + caches ; garde les clones) — en terminal :

```bash
bash ~/.shared-memory/plugin/scripts/uninstall.sh          # garde les clones de vault
bash ~/.shared-memory/plugin/scripts/uninstall.sh --purge  # supprime AUSSI les clones (données)
```

  Puis, dans Claude Code : `/plugin uninstall shared-memory`.
