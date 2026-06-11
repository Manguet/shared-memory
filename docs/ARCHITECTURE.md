# Mémoire d'équipe partagée — Architecture

> Outil de mémoire centralisée pour équipes utilisant Claude Code.
> Objectif : que chaque membre (dev **et** non-dev / vibe coder) partage **une seule
> source de vérité** par projet, puisse la consulter, y contribuer, et valider
> collectivement ce qui devient canonique.

---

## 1. Le problème

La mémoire native de Claude Code vit dans `~/.claude/projects/<slug>/memory/` :

- **locale à chaque machine** (home de l'utilisateur),
- **hors du dépôt git** du projet,
- donc **jamais synchronisée** entre coéquipiers.

Résultat : chaque Claude construit sa mémoire en silo. Les connaissances vivantes
(chantiers, décisions, conventions découvertes) ne circulent pas dans l'équipe.

Le seul « cerveau commun » existant aujourd'hui est `CLAUDE.md`, parce qu'il est
versionné. Tout le reste est privé à chaque poste.

---

## 2. Faits techniques sur la mémoire native (fondations)

- La mémoire = **des fichiers `.md` plats** (frontmatter YAML + corps + liens `[[wikilink]]`).
  Pas de base de données. **C'est ce qui rend le partage possible.**
- `<slug>` est **dérivé du chemin absolu du projet** (`/var/www/projetA` → `-var-www-projetA`).
  → La mémoire est donc **déjà par-projet**.
- **Lecture** : `MEMORY.md` (l'index) est injecté au démarrage de session ; le contenu
  complet d'un fait est injecté à la demande (recall) quand le sujet devient pertinent.
- **Écriture** : Claude écrit des fichiers (`Write`). Un humain peut éditer les mêmes
  fichiers à la main → **mémoire bidirectionnelle humain ⇄ Claude**.

**Conséquence clé :** le seul verrou pour partager, c'est de faire pointer
`~/.claude/projects/<slug>/memory/` de chaque poste vers une **source commune**.

---

## 3. Principes de conception

1. **Substrat = fichiers + git.** Le stockage et la synchro ne sont **pas** réécrits :
   git fait collecte / comparaison / conflits / historique / redistribution. La source
   de vérité reste des fichiers `.md` (Claude ne sait lire que ça).
2. **Source unique, pas réconciliation de copies.** Tout le monde lit/écrit **une**
   copie partagée → on supprime la divergence à la racine au lieu de la réparer en boucle.
3. **Deux étages.** Mémoire locale libre (brouillon, perso) vs mémoire canonique
   gouvernée (validée, partagée).
4. **Outil ≠ contenu.** Le **plugin** (générique, partageable) est distinct des
   **vaults** (privés, par équipe).
5. **Multi-vault.** Un vault par projet/équipe ; le plugin est unique ; un registre
   par-utilisateur relie les deux.
6. **Léger et sans install.** L'outil vit **dans** Claude Code (que tout le monde a déjà),
   pas dans une application séparée.

---

## 4. Les deux étages de mémoire

```
ÉTAGE 1 — LOCAL (libre, non gouverné)
  • Claude écrit librement, sans friction
  • type: user | feedback  → reste local (préférences perso), jamais partagé
  • brouillons / observations à chaud
  = working copy non commitée + .gitignore sur les fichiers perso

          │  promotion EXPLICITE (fin de session de travail)
          ▼

ÉTAGE 2 — CANONIQUE (gouverné, source de vérité)
  • type: project | reference uniquement
  • entre via une étape de validation (pending → approuvé)
  • main du vault = LA vérité, identique pour tous (git pull)
```

git sépare gratuitement les deux étages :
- **working copy non commitée** = étage 1 (brouillon local) ;
- **branche `main` mergée** = étage 2 (canonique) ;
- `.gitignore` sur `feedback_*.md` / `type: user` → le perso ne fuite jamais.

---

## 5. Multi-vault : « chaque équipe son vault »

La mémoire étant déjà par-projet (slug), chaque projet pointe vers le vault de son équipe.

```
Projet A (équipe 1)  /var/www/projetA   → slug -var-www-projetA  → memory → symlink → Vault A
Projet B (équipe 2)  /home/x/projetB    → slug -home-x-projetB   → memory → symlink → Vault B
```

Trois niveaux distincts :

| Niveau | Cardinalité | Visibilité | Contenu |
|--------|-------------|------------|---------|
| **Plugin (outil)** | 1, global | public (aucun secret) | skills, viewer, scripts |
| **Vault (mémoire)** | N, un par équipe/projet | privé à l'équipe | `MEMORY.md` + faits `.md` |
| **Registre (config)** | 1 par utilisateur | local, non versionné | mapping projet → vault → symlink |

### Registre par-utilisateur : **JSON local** (pas de BDD)

Une BDD centrale réintroduit un serveur à héberger → contraire à « simple, sans install ».
On utilise un **JSON local par machine** (ex. `~/.config/shared-memory/registry.json`),
non versionné, car les chemins/slugs diffèrent sur chaque poste.

```jsonc
// ~/.config/shared-memory/registry.json
{
  "projets": [
    {
      "slug": "-var-www-projetA",
      "vault": "git@github.com:equipe1/projetA-memory.git",
      "clone": "~/vaults/projetA-memory",
      "symlink": "~/.claude/projects/-var-www-projetA/memory"
    }
  ]
}
```

Le registre a **deux moitiés** : la partie **chemins** (locale, par machine — l'utilisateur
clone le vault **où il veut**) et un **catalogue de vaults disponibles** (partagé : nom → URL),
pour qu'un membre n'ait qu'à **choisir** son vault au setup. `/memory-setup` propose le
catalogue et/ou accepte une URL explicite, clone à l'emplacement choisi, crée le symlink,
écrit l'entrée locale.

### Nommage des vaults : `<projet>-memory` (convention recommandée)

Privés. Convention **recommandée** (pas imposée) : `negocian` → `negocian-memory`, rattaché
au **projet** (pas à une personne ni une équipe). L'**emplacement et l'hébergement du vault
sont libres** (chaque équipe le met où elle veut) ; le **catalogue** liste les vaults
disponibles pour le setup.

---

## 6. Le plugin Claude Code

L'outil n'est **pas** une application séparée : c'est un **plugin Claude Code**, installable
depuis un dépôt GitHub (marketplace), donc **zéro install supplémentaire** — tout le monde
a déjà Claude Code (les non-devs vibe codent avec).

**Distribution publique, installation locale.** Le repo plugin est **public**
(`github.com/Manguet/shared-memory`) — il ne contient aucun secret, juste l'outil. Le
`marketplace.json` n'est **pas** un catalogue public : rien n'est listé ni découvrable
ailleurs, c'est seulement le descripteur d'installation. L'install se fait par **script**
(`install.sh`) qui clone le plugin en local puis l'active par **chemin local**
(`/plugin marketplace add ~/.shared-memory/plugin`) — donc jamais référencé comme une
marketplace GitHub publique. Le repo étant public, le `git clone` ne demande **pas** d'auth.

### Pourquoi « dans Claude Code » et pas une app desktop

- **Interface = la conversation**, que les vibe coders maîtrisent déjà.
- **Git invisible** : les skills exécutent `clone`/`pull`/`commit`/`push`.
- **WSL2 neutralisé** : Claude tourne dans WSL2, le vault et le symlink sont dans le
  système de fichiers Linux de WSL2 → **aucune traversée de frontière Windows↔WSL2**
  (la source de galères des apps natives Windows : symlinks instables, git lent sur
  `/mnt/c`, file-watching défaillant).

### Skills prévues

| Skill | Rôle | Étape |
|-------|------|-------|
| `/memory-setup` | clone le vault du projet + crée le symlink (registre) | install |
| `/memory-list` | consulter / chercher dans la mémoire | lecture |
| `/memory-import` | **normaliser** un doc brut → faits au format mémoire | écriture |
| `/memory-promote` | proposer mes faits locaux → `pending` (vérif contre le code) | écriture |
| `/memory-review` | un référent valide `pending → canonique` | gouvernance |
| `/memory-ui` | ouvrir l'interface visuelle (navigateur) | visualisation |
| `/memory-doctor` | diagnostiquer la recherche sémantique + proposer les installs | diagnostic |

> **Normaliser, pas importer-sync.** `/memory-import` transforme de la doc brute en
> faits atomiques (frontmatter + 1 fait/fichier + ligne d'index). Le transport, c'est git.

---

## 7. Gouvernance = revue de branche (git seul)

La validation se fait **en git**, sans `gh`. `/memory-promote` pousse une **branche de
proposition** (`promote/…`) ; un **référent** la relit et la **fusionne dans `main`** via
`/memory-review`. Traçabilité et historique restent assurés par git.

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

### Règle de fusion (barrière)

**Protection de branche** sur `main` du vault (GitHub → Settings → Branches) :
- **Restrict who can push to matching branches** → seuls les **référents** poussent sur `main`.

Ainsi un vibe coder ne pousse que des branches `promote/*` ; seul un référent fusionne. Pas
d'auto-validation (le référent n'est pas l'auteur). La validation compte **plus** avec des
vibe coders (ils produisent beaucoup de faits, dont des bancals).

---

## 8. Interface visuelle (en deux temps)

Claude Code ne **dessine pas** d'UI custom (c'est un terminal). Mais une commande peut
**lancer une interface externe** : ouvrir une page dans le navigateur déjà présent.
Pattern : l'IA **demande confirmation** avant d'ouvrir l'URL.

**Mise en œuvre actuelle : un mini-serveur local.** Le viewer n'est plus un
fichier HTML statique (le mode statique a été **retiré**) mais un petit serveur `serve-viewer.py`
(`http.server`, bind `127.0.0.1`) lancé par `/memory-ui` / `view.sh` :
- l'index envoyé au navigateur ne contient que les **métadonnées** des faits (léger) ; le **corps**
  d'un fait est servi **à la demande** (`GET /fact`) — tient à l'échelle (milliers de faits) ;
- **arbre récursif N-niveaux** dans la sidebar (rendu paresseux) ; **recherche hybride** (filtre
  instantané côté client + plein-texte serveur `GET /search`) ;
- **sécurité** : localhost uniquement, validation anti-traversal (`realpath` dans le vault), ne
  sert que des `.md` ;
- **guidage & édition intégrés** : formulaire de création/édition de faits, guide d'utilisation ;
  chaque skill termine par la **prochaine commande**.

`http://localhost:PORT` est plus fiable que `file://wsl.localhost` sous WSL2.

**Écriture LOCALE (étage 1), jamais vers le canonique.** Le viewer expose un **CRUD local** —
créer / éditer / supprimer / déplacer un fait, renommer un domaine — via des routes `/api/*`
(`POST`/`PUT`/`DELETE`) qui écrivent **uniquement dans le clone** (working copy, brouillons), puis
appellent `reshard`. Sécurité : bind `127.0.0.1`, **jeton same-origin** (`X-SM-Token`) exigé sur
les écritures, anti-traversal. **Rien n'est poussé** : le canonique passe toujours par
`/memory-promote` → `/memory-review` (revue de branche). Donc **aucun git dans l'UI, aucune
écriture vers le canonique** — la barrière de gouvernance tient. Un chat-agent embarqué reste
écarté — le « chat connecté à Claude », c'est Claude Code lui-même.

Ouverture du navigateur cross-platform : `open` (Mac) · `wslview` / `cmd.exe start` (WSL2)
· `xdg-open` (Linux). Un serveur localhost lancé dans WSL2 est joignable depuis le
navigateur Windows (forwarding automatique).

---

## 9. Schéma d'ensemble

```
╔═══════════════════════════════════════════════════════════════════════╗
║  REPO PLUGIN (outil, PUBLIC)        REPOS VAULT (mémoire, privés, N)   ║
║  • skills /memory-*                 • Vault équipe 1 (projet A)        ║
║  • viewer HTML                      • Vault équipe 2 (projet B)        ║
║  • scripts git/symlink/open         • … (MEMORY.md + faits .md)        ║
╚═══════════════════════════════════════════════════════════════════════╝
        │ installé une fois              ▲ pull (lecture) / push validé (écriture)
        ▼                                │
   ┌─────────────────────── poste utilisateur (dans WSL2 / macOS) ──────────────────┐
   │  Claude Code  ──exécute──►  skills mémoire                                      │
   │  registre par-user : slug → vault → clone → symlink                            │
   │  ~/.claude/projects/<slug>/memory  ──symlink──►  clone du vault du projet      │
   └────────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Risques (non techniques, décisifs)

- **Discipline.** Si personne ne lance `/memory-promote` ni `/memory-review`, le canonique se fige
  et devient obsolète. **Atténué** par les **hooks de session** (§12 « Boucle vivante ») : synchro
  automatique au démarrage + rappel de promotion (début et fin de session). Reste à trancher côté
  équipe : qui est référent, à quelle fréquence valide-t-il.
- **Versionnage du plugin.** Une mise à jour de l'outil doit être re-pull par chacun.
- **Confiance.** Le repo plugin est **public** et exécute git, ouvre des navigateurs, lance
  des scripts → garder le code lisible et **sans aucun secret**.
- **Vault privé.** Ne jamais committer le contenu mémoire dans le repo public du plugin.

---

## 11. Décidé / à décider

**Décidé :**
- Substrat = fichiers + git (pas d'outil de sync maison).
- Outil = plugin Claude Code (pas d'app desktop séparée).
- Multi-vault : un vault privé par équipe/projet, plugin unique, registre par-user.
- Deux étages (local libre / canonique gouverné).
- **Gouvernance = revue de branche git** (sans `gh`) : `/memory-promote` pousse une branche,
  `/memory-review` la fusionne ; `main` protégée (push restreint aux référents).
- **Registre = JSON local** par machine (pas de BDD).
- **Nommage vault = `<projet>-memory`**, privé, sous une org GitHub.
- **Distribution du plugin = repo public**, install **locale** par script `install.sh`
  (clone + activation par chemin local). `marketplace.json` ≠ catalogue public (aucun
  listing). Vaults restent privés.
- Interface : **mini-serveur local** (`serve-viewer.py`, `http://localhost`) — le mode HTML statique
  `file://` a été **retiré**. **CRUD local des faits** dans l'UI (créer/éditer/supprimer/déplacer,
  renommer un domaine) écrivant **uniquement dans le clone** (étage 1, jeton same-origin) ; **aucune
  écriture vers le canonique, aucun git dans l'UI** — la promotion reste `/memory-promote` →
  `/memory-review`. Pas de chat embarqué. Voir §8 et §12.
- **Sharding par domaine** (carte + sous-index compacts) + **`reshard.py`** (redécoupage récursif) ;
  **recherche sémantique `search_memory`** (serveur MCP, fastembed optionnel, repli grep) +
  **`/memory-doctor`** pour les prérequis. Voir §12.

- Repo plugin : `github.com/Manguet/shared-memory` (public).
- Vault : emplacement/hébergement libres ; **catalogue de vaults disponibles** pour le setup.
- Promotion = faits `type: project` + `type: reference` (jamais `user`/`feedback`).

**À décider :**
- Nombre d'approbations requis pour merger (1 par défaut, ou 2 pour plus de rigueur).
- Ce qui déclenche une promotion (proposé : fin de session de travail).
- Où vit le catalogue de vaults (dans le repo plugin, ou fichier de config dédié).

---

## 12. Sous-systèmes livrés (sharding, recherche, reshard, doctor)

Ces couches ont été ajoutées **après** la conception initiale ci-dessus ; elles n'en changent pas
les principes (substrat fichiers + git, deux étages, gouvernance par branche). Elles optimisent la
**lecture** et le **passage à l'échelle**.

### Sharding par domaine
Le vault n'est plus plat : `MEMORY.md` est une **carte de domaines** (chargée au démarrage, bornée
en taille) ; chaque domaine a un **sous-index compact** `index/<domaine>.md` (1 ligne/fait, lu à la
demande) ; les faits vivent dans `<domaine>/<fait>.md`. Détail et format :
[`docs/domain-convention.md`](domain-convention.md).

### `search_memory` — recherche sémantique (MCP)
Un **serveur MCP** (`scripts/mcp-server.py`, déclaré dans `.mcp.json`) expose l'outil
`search_memory(query, k)` que Claude appelle en session. **Embeddings locaux optionnels** (fastembed,
modèle **multilingue**) avec **store hors vault** (`~/.shared-memory/embeddings/`) à fraîcheur lazy
par hash ; **repli grep** automatique si fastembed est absent (drapeau `vector_inactive`). L'outil
renvoie des **pointeurs** `{file, name, path, score}`, **jamais le corps** : *l'index aiguille, le
fait reste la source* — Claude relit le fait avant d'affirmer.

### `reshard.py` — redécoupage récursif
Maintient l'invariant « ≤ ~150 faits directs et ≤ ~150 sous-dossiers par dossier » : un domaine trop
gros est scindé récursivement en sous-domaines (`part-xx`), tous les `index/**` sont régénérés.
**Idempotent** et **préserve** la carte `MEMORY.md` curée (intro, « Patterns & Conventions »).
Appelé par `/memory-import` et `/memory-promote` (filet de sécurité de lisibilité).

### `/memory-doctor` — pas de dégradation silencieuse
`scripts/doctor.py` diagnostique les prérequis de la recherche (python, `fastembed`, modèle,
`.mcp.json`) avec un **remède** par manque ; le skill présente le diagnostic et **propose** les
installs (l'utilisateur valide). Sans fastembed, la recherche tourne en grep **et le signale** —
jamais de dégradation invisible.

> Note d'échelle : prouvé sur un vault synthétique (9 300 faits) — récupération top-5 = 100 %,
> latence de recherche < 10 ms à taille réelle (≤ 100 faits). Détails dans les specs/plans
> `docs/superpowers/`.

### Boucle vivante : hooks de session
Deux **hooks plugin** referment la boucle sans discipline manuelle. `SessionStart` :
`git pull --ff-only` **best-effort** (time-boxé, non destructif — refuse sans écraser les brouillons
étage 1) pour ne pas travailler sur une mémoire périmée, puis rappelle les faits locaux non promus
(« prévois `/memory-promote` avant de fermer »). `SessionEnd` : dernier rappel. Tout est silencieux
si le projet n'est pas branché ou en cas d'échec (jamais bloquant). Script : `scripts/hook-memory.sh`.

### Fraîcheur (anti-péremption)
Chaque fait porte `metadata.reviewed` (date de dernière vérification). Stampée à la création /
édition / promote-review ; un fait non vérifié depuis ≥ 90 j (ou sans date) est signalé « à
revérifier » (badge + vue dédiée dans le viewer, surface dans `/memory-list`). Le but : la confiance
ne s'érode pas en silence — un fait périmé est visible.

### Dédup sémantique (anti-doublon)
À la création d'un fait (`/memory-import`, CRUD du viewer), `embed.find_similar` signale les
quasi-doublons (cosine ≥ 0.80, fastembed optionnel) → l'humain met à jour le fait existant plutôt
que d'empiler. On **signale, jamais on ne fusionne** (gouvernance). Scan global d'un vault déjà
peuplé : hors scope (évolution).
