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
  • entre via une étape de validation (branche promote/* → fusion dans main)
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

### Skills livrées

**Livré** : 12 skills — setup, unsetup, seed, import, list, ui, promote, review, lint, refresh, eval, doctor.

| Skill | Rôle | Étape |
|-------|------|-------|
| `/memory-setup` | clone le vault du projet + crée le symlink (registre) | install |
| `/memory-unsetup` | débranche le projet (retire symlink + registre, garde le clone) | install |
| `/memory-seed` | amorce un vault vide depuis les sources humaines (CLAUDE.md, doc) | écriture |
| `/memory-import` | **normaliser** un doc brut → faits au format mémoire | écriture |
| `/memory-list` | consulter / chercher dans la mémoire | lecture |
| `/memory-ui` | ouvrir l'interface visuelle (mini-serveur local) | visualisation |
| `/memory-promote` | proposer mes faits locaux → branche `promote/*` (vérif contre le code) | écriture |
| `/memory-review` | un référent **fusionne la branche dans `main`** (canonique) | gouvernance |
| `/memory-lint` | valider / nettoyer le format des faits (rapport + fix opt-in) | qualité |
| `/memory-refresh` | re-vérifier les faits périmés contre le code (re-stamp / corrige / retire) | qualité |
| `/memory-eval` | mesurer la qualité du rappel (recall@k, MRR) | qualité |
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
║  • viewer (mini-serveur local)      • Vault équipe 2 (projet B)        ║
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
- **Catalogue de vaults** = `skills/memory-setup/references/vaults.md` (dans le repo plugin).
- **Déclencheur de promotion** = hook `SessionEnd` (rappel) / `/memory-promote` explicite.

**À décider :**
- Nombre d'approbations requis pour merger (1 par défaut, ou 2 pour plus de rigueur).

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

**Sous-domaines sémantiques** : `reshard` reconnaît les dossiers nommés par l'humain
(`mailing/transactionnel`) et les **préserve** ; il n'applique le découpage mécanique `part-NN` que
sur les **faits directs** d'un dossier qui dépassent le seuil (hybride). `part-NN` est un nom réservé.
Le domaine d'un fait = son chemin moins les segments `part-NN`. Le formulaire du viewer propose les
sous-domaines existants (combobox autocomplete) et permet d'en créer ; un fait homonyme d'un
sous-domaine frère est refusé.

### `/memory-doctor` — pas de dégradation silencieuse
`scripts/doctor.py` diagnostique les prérequis de la recherche (python, `fastembed`, modèle,
`.mcp.json`) avec un **remède** par manque ; le skill présente le diagnostic et **propose** les
installs (l'utilisateur valide). Sans fastembed, la recherche tourne en grep **et le signale** —
jamais de dégradation invisible.

> Note d'échelle : prouvé sur un vault synthétique (9 300 faits) — récupération top-5 = 100 %,
> latence de recherche < 10 ms à taille réelle (≤ 100 faits). Détails dans les specs/plans
> `docs/superpowers/`.

### Boucle vivante : hooks de session
Deux **hooks plugin** referment la boucle sans discipline manuelle. `SessionStart` : `git pull
--ff-only` **best-effort** (time-boxé, non destructif, et **seulement si un remote `origin` existe**)
pour ne pas travailler sur une mémoire périmée. Comme la sortie d'un hook `SessionStart` n'est **pas
affichée** dans le terminal (elle n'alimente que le contexte du modèle), le hook la formule en
**instruction** : Claude **affiche en première réponse** un **rappel compact** — résumé du vault
(`digest.py --summary` : « N faits (domaines…) »), nombre de faits à récupérer / non promus
(« pense à `/memory-promote` »), et un **nudge `/doctor`** si une **vérif santé** légère
(`sm_health_issues` : git/python présents, clone du vault versionné, lien mémoire câblé, pull réussi)
remonte un problème. Le **digest complet** suit en contexte silencieux pour amorcer le modèle.
`SessionEnd` : dernier rappel de promotion. Tout est silencieux si le projet n'est pas branché ou en
cas d'échec (jamais bloquant). Script : `scripts/hook-memory.sh`.

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

### Amorçage à froid (`/memory-seed`)
Un vault vide n'a aucune valeur. `/memory-seed` le **peuple** depuis les sources humaines du projet
(CLAUDE.md, doc) : extraction de faits atomiques (conventions d'import), **dédup** contre l'existant
(`similar.py`), **confirmation** avant écriture, brouillons (étage 1) → `/memory-promote`. Pas de
scan de code (les faits restent humains et vérifiables).

### Digest au démarrage (rappel automatique)

Nativement, seule la **carte** `MEMORY.md` (les domaines) est chargée au `SessionStart` —
**pas le contenu des faits**. Le **digest** comble ce trou : `scripts/digest.py`
(`build_digest(vault, max_lines=120)`) lit le vault (réutilise `collect_facts`) et émet, via
`hook-memory.sh start`, **une description d'une ligne par fait, groupée par domaine**, avant le
rappel synchro/promote. Claude **sait** alors ce qui existe et lit le fait quand le sujet arrive,
**sans qu'on le lui demande** — le rappel devient quasi mains-libres.

C'est **borné** (principe du sharding) : sous `max_lines` (120), digest complet ; un fait périmé
(`reviewed` ≥ 90 j ou absent, cf. fraîcheur SP2) porte un **`⚠`** ; la section
« Patterns & Conventions » de `MEMORY.md` est jointe. Au-dessus du budget → digest **dégradé**
(domaines + comptes + renvoi `search_memory`/`/memory-list`). **Pur lecture de fichiers, aucun
fastembed** : marche toujours, coût borné (~2 k tokens au pire), zéro coût par message.

## 13. Lint & normalisation des faits

Le format d'un fait peut **dériver** dans le temps (frontmatter à plat hérité, champ requis oublié,
date mal formée, `name` en double). `/memory-lint` (moteur `scripts/lint.py`) **détecte** ces
problèmes et **corrige mécaniquement** la seule dérive sûre : un frontmatter à plat
(`type:`/`reviewed:` de premier niveau) est réécrit sous un bloc **`metadata:`** canonique.

- **`lint_vault(vault)`** renvoie une liste de *findings* `{file, rule, severity, fixable, message}`
  (6 règles `error`, 7 `warn` dont une seule `fixable`). **`apply_fixes`** n'applique que les
  findings `fixable=True` (`flat_frontmatter`), de façon **idempotente**.
- **Rapport + fix opt-in** : le skill montre le rapport, applique la correction mécanique **après
  confirmation**, puis régénère les index (`reshard.py`). Le reste (`name` non-slug, doublons,
  description courte, wikilinks cassés, perso mal placé) est **signalé**, jamais réécrit — renommer
  ou déplacer casserait les pointeurs.
- **Garde-fou promote** : `/memory-promote` lance le lint avant le push et signale les erreurs
  (advisory, sans blocage dur).

Le format **canonique** d'un fait est le bloc `metadata:` imbriqué (cf. `assets/fact-template.md`,
`docs/domain-convention.md`). Le lint converge vers ce format ; il n'invente jamais de date
`reviewed` (dater reste un jugement, fait par `/memory-promote` à la vérification).

## 14. Résolution de conflits

La mémoire canonique se met à jour par `git merge` (revue). En concurrence, deux propositions
peuvent entrer en conflit. La clé : `index/**` est **dérivé** (régénérable par `reshard.py`),
`<domaine>/<fait>.md` est la **source**, `MEMORY.md` la **carte curée**.

`scripts/resolve-conflicts.py` (`classify_conflicts` + CLI) partitionne les fichiers en conflit :
- **`index/**`** → régénéré automatiquement (reshard) et stagé ;
- **faits** et **`MEMORY.md`** → arbitrage humain (véracité / doublons de domaine).

**Flux en deux temps** : l'outil ne régénère les index que lorsqu'il ne reste aucun conflit de
fait/carte (reshard ne lit jamais de marqueurs de conflit) ; sinon il les liste et sort en code 1.
Intégré à `/memory-review` (étape de fusion), avec `git merge --abort` comme échappatoire sûr.
Aucune fusion automatique du **contenu** d'un fait : choisir entre deux versions reste un jugement.

## 15. Cycle de vie des faits / re-vérification

La fraîcheur **signale** (`⚠` si `reviewed` ≥ 90 j ou absent), mais signaler ne suffit pas : sans
remédiation, le `⚠` s'accumule. `scripts/stale.py` est la **source unique** de la règle de péremption
(`is_stale`, `days_old`, `STALE_DAYS = 90`) — réutilisée par `digest.py` (DRY) — et liste les faits
périmés (`stale_facts`, triés du plus vieux au plus récent).

`/memory-refresh` **ferme la boucle** : il liste les périmés, **confronte chaque fait
project/reference au code actuel**, puis **re-stampe** (`set_reviewed` → `reviewed = aujourd'hui`)
ceux encore vrais, **corrige** ou **retire** les autres. Les faits perso (`user`/`feedback`) sont
listés à juger (pas de code à vérifier). Tout est **brouillon (étage 1)** → `/memory-promote`.

Principe : **re-stamper signifie « vérifié », pas « existe »** — jamais de re-stampage en masse à
l'aveugle ; pas d'archivage automatique (retirer un fait est une décision humaine).

## 16. Mise à jour & désinstallation

Le **setup** crée, par projet, un **symlink** (`~/.claude/projects/<slug>/memory → clone`) et une
**entrée de registre** ; par machine, l'installateur crée `~/.shared-memory/{plugin,vaults,models,embeddings}`.
La désinstallation en est l'**inverse exact**, en **conservant les données** par défaut :

- **Par projet** — `/memory-unsetup` (→ `scripts/unlink-vault.sh`) : retire le symlink et l'entrée
  de registre, **garde le clone**. Un dossier mémoire n'est retiré que **si c'est un symlink**
  (`[ -L ]`) — jamais une vraie mémoire locale.
- **Machine** — `scripts/uninstall.sh [--purge]` : débranche tous les projets, retire le plugin et
  les caches. Les clones de vault sont **gardés** sauf `--purge` (qui supprime aussi les données et
  d'éventuels brouillons non promus). Un script ne peut pas lancer `/plugin uninstall` → on guide.

**Mise à jour** : `install.sh` fait déjà un `git pull` du plugin s'il est déjà cloné — « update » =
relancer l'installateur + `/reload-plugins`. Les fonctions registre (`sm_symlink_for_slug`,
`sm_registry_slugs`, `sm_unregister`) sont partagées par les deux scripts et testées.

## 17. Évaluation du rappel

Tout vise à ce que **le bon fait remonte au bon moment** ; `scripts/eval-recall.py` le **mesure**.
Pour des cas `{query, expect}`, il interroge le **vrai** chemin de recherche (`embed.search`, comme
`search_memory`) et calcule **`recall@k`** (le fait attendu est-il dans le top-k ?), **`MRR`** (à
quelle hauteur ?) et **`rang #1`** (discriminabilité : un fait souvent masqué par un autre = descriptions
confusables).

- **`auto_cases`** : éval automatique (chaque description sert de requête → son fait doit ressortir)
  — repère la retrievabilité et les doublons.
- **`/memory-eval`** : Claude génère des **requêtes réalistes** par fait (pas la description brute) →
  éval → **ratés** + pistes de remédiation (`/memory-lint` pour les descriptions, dédup pour les
  confusables, `/memory-doctor` pour activer fastembed, `/memory-refresh` pour les faits périmés).

L'éval est **diagnostique** (pas de seuil/gating) et **honnête** : en repli **grep** (sans fastembed),
le recall est un proxy lexical faible, signalé dans le rapport. Le moteur est **lecture seule**.
