# SP1 — Boucle vivante (hooks de session) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deux hooks plugin (`SessionStart` + `SessionEnd`) qui **synchronisent** le vault au démarrage (`git pull --ff-only`, best-effort) et **rappellent** de promouvoir les brouillons locaux non partagés — fermant la boucle sans discipline manuelle.

**Architecture :** Un script bash paramétré `scripts/hook-memory.sh start|end` source `lib.sh` (résolution du vault + nouvel helper `sm_count_unpromoted`), synchronise de façon **time-boxée et non destructive**, et émet un message de contexte. Déclaré dans `.claude-plugin/plugin.json`. Best-effort absolu : silencieux en cas d'échec, **exit 0**, ne bloque jamais la session.

**Tech Stack :** Bash (réutilise `lib.sh`), git, `timeout`. Tests : `unittest` invoquant le bash via `subprocess` (pattern à introduire dans `tests/test_hooks.py`).

**Référence design :** `docs/superpowers/specs/2026-06-10-sp1-session-hooks-design.md`.

**Convention du programme (rappel) :** ce chantier inclut la **mise à jour de la doc ET des tests** dans sa définition de « terminé » (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/lib.sh` | + `sm_count_unpromoted <clone>` : compte les faits partageables modifiés vs `origin/main`, hors `index/`/`MEMORY.md`/perso. | Modifier |
| `scripts/hook-memory.sh` | Hook paramétré `start`/`end` : résout le vault, synchronise (start), compte les non-promus, émet le message. Best-effort. | Créer |
| `.claude-plugin/plugin.json` | Déclare les hooks `SessionStart` et `SessionEnd`. | Modifier |
| `tests/test_hooks.py` | Tests `unittest` (subprocess bash) : comptage + no-op + rappel + déclaration plugin.json. | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md` | Documenter la boucle vivante (auto-sync + rappel). | Modifier |

---

## Task 1 : `sm_count_unpromoted` dans `lib.sh`

**Files:**
- Modify: `scripts/lib.sh`
- Test: `tests/test_hooks.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_hooks.py` :

```python
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
LIB = os.path.join(HERE, "..", "scripts", "lib.sh")
HOOK = os.path.join(HERE, "..", "scripts", "hook-memory.sh")

FACT = "---\nname: %s\ndescription: d\nmetadata:\n  type: %s\n---\nx\n"


def git(clone, *args):
    subprocess.run(["git", "-C", clone, *args], capture_output=True, check=True)


def write(clone, rel, content):
    p = os.path.join(clone, rel)
    os.makedirs(os.path.dirname(p) or clone, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def init_repo(clone):
    git(clone, "init", "-q")
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")


def count_unpromoted(clone):
    r = subprocess.run(["bash", "-c", 'source "$1"; sm_count_unpromoted "$2"', "_", LIB, clone],
                       capture_output=True, text=True)
    return r.stdout.strip()


class CountUnpromotedTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.c = self._t.name
        init_repo(self.c)
        write(self.c, "mailing/a.md", FACT % ("a", "project"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "base")

    def tearDown(self):
        self._t.cleanup()

    def test_counts_new_shareable_fact(self):
        write(self.c, "mailing/b.md", FACT % ("b", "project"))
        self.assertEqual(count_unpromoted(self.c), "1")

    def test_modified_shareable_counts(self):
        write(self.c, "mailing/a.md", FACT % ("a", "project") + "modifié\n")
        self.assertEqual(count_unpromoted(self.c), "1")

    def test_excludes_personal_index_memory(self):
        write(self.c, "feedback_x.md", FACT % ("fx", "feedback"))
        write(self.c, "ui/perso.md", FACT % ("p", "user"))
        write(self.c, "index/mailing.md", "- a\n")
        write(self.c, "MEMORY.md", "# carte\n")
        self.assertEqual(count_unpromoted(self.c), "0")

    def test_no_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(count_unpromoted(d), "0")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_hooks.CountUnpromotedTest -v`
Expected : FAIL — `sm_count_unpromoted: command not found` (ou compte vide).

- [ ] **Step 3 : Ajouter la fonction à `scripts/lib.sh`**

Ajouter à la fin de `scripts/lib.sh` :

```bash
# Compte les faits .md partageables modifiés/ajoutés/supprimés dans la working copy d'un clone,
# hors MEMORY.md, index/**, et faits perso (feedback_* ou frontmatter type: user|feedback).
# Renvoie un entier sur stdout. Best-effort : 0 si le clone n'est pas un dépôt git.
sm_count_unpromoted() {
  local clone="$1" n=0 path type
  [ -d "$clone" ] || { printf '0'; return 0; }
  while IFS= read -r line; do
    path="${line:3}"                          # 'XY <path>'
    case "$path" in *" -> "*) path="${path##* -> }" ;; esac   # renommage -> cible
    case "$path" in *.md) ;; *) continue ;; esac
    case "$path" in
      MEMORY.md|index/*) continue ;;
      feedback_*|*/feedback_*) continue ;;
    esac
    type="$(sed -n 's/^[[:space:]]*type:[[:space:]]*//p' "$clone/$path" 2>/dev/null | head -1)"
    case "$type" in user|feedback) continue ;; esac
    n=$((n + 1))
  done < <(git -C "$clone" status --porcelain 2>/dev/null)
  printf '%s' "$n"
}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_hooks.CountUnpromotedTest -v`
Expected : PASS (4 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/lib.sh tests/test_hooks.py
git commit -m "feat(hooks): sm_count_unpromoted — compte les brouillons partageables non promus

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : `scripts/hook-memory.sh` (start + end)

**Files:**
- Create: `scripts/hook-memory.sh`
- Test: `tests/test_hooks.py`

- [ ] **Step 1 : Ajouter les tests qui échouent**

Ajouter dans `tests/test_hooks.py`, avant `if __name__` :

```python
def run_hook(mode, project_dir, registry):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project_dir, SM_REGISTRY=registry)
    r = subprocess.run(["bash", HOOK, mode], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.strip()


class HookScriptTest(unittest.TestCase):
    def test_noop_when_not_branched(self):
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "registry.json")
            with open(reg, "w") as f:
                f.write('{"projets": []}')
            rc, out = run_hook("start", "/no/such/project", reg)
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")

    def test_end_reminds_when_unpromoted(self):
        with tempfile.TemporaryDirectory() as d:
            clone = os.path.join(d, "clone")
            os.makedirs(clone)
            init_repo(clone)
            write(clone, "mailing/a.md", FACT % ("a", "project"))
            git(clone, "add", "-A")
            git(clone, "commit", "-qm", "base")
            write(clone, "mailing/b.md", FACT % ("b", "project"))    # brouillon non promu
            reg = os.path.join(d, "registry.json")
            with open(reg, "w") as f:
                json.dump({"projets": [{"slug": "-tmp-proj", "clone": clone}]}, f)
            rc, out = run_hook("end", "/tmp/proj", reg)
            self.assertEqual(rc, 0)
            self.assertIn("/memory-promote", out)

    def test_end_silent_when_clean(self):
        with tempfile.TemporaryDirectory() as d:
            clone = os.path.join(d, "clone")
            os.makedirs(clone)
            init_repo(clone)
            write(clone, "mailing/a.md", FACT % ("a", "project"))
            git(clone, "add", "-A")
            git(clone, "commit", "-qm", "base")
            reg = os.path.join(d, "registry.json")
            with open(reg, "w") as f:
                json.dump({"projets": [{"slug": "-tmp-proj", "clone": clone}]}, f)
            rc, out = run_hook("end", "/tmp/proj", reg)
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")
```

(`sm_slug("/tmp/proj")` = `-tmp-proj`, qui correspond au slug du registre.)

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_hooks.HookScriptTest -v`
Expected : FAIL — `scripts/hook-memory.sh` absent (`bash: ... No such file`).

- [ ] **Step 3 : Créer `scripts/hook-memory.sh`**

```bash
#!/usr/bin/env bash
# Hook mémoire shared-memory : synchro au démarrage + rappel de promotion.
# Usage : hook-memory.sh start|end
# BEST-EFFORT : ne bloque jamais la session, silencieux en cas d'échec, sort toujours 0.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/lib.sh" 2>/dev/null || exit 0
set +e +u +o pipefail            # relâche le set -euo de lib.sh : un hook ne doit jamais aborter

MODE="${1:-start}"

clone="$(sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")" 2>/dev/null)"
[ -n "$clone" ] && [ -d "$clone" ] || exit 0

ahead=0
if [ "$MODE" = "start" ]; then
  timeout 5 git -C "$clone" pull --ff-only >/dev/null 2>&1 || true   # non destructif ; refuse si ff impossible
  ahead="$(git -C "$clone" rev-list --count HEAD..origin/main 2>/dev/null || printf 0)"
fi

unpromoted="$(sm_count_unpromoted "$clone")"

msg=""
if [ "$MODE" = "start" ]; then
  [ "${ahead:-0}" -gt 0 ] 2>/dev/null && msg+="📥 ${ahead} nouveau(x) fait(s) d'équipe en amont à récupérer. "
  [ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && msg+="📝 ${unpromoted} fait(s) local(aux) non promu(s) — prévois /memory-promote AVANT de fermer pour éviter les décalages."
else
  [ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && msg+="📝 Avant de partir : ${unpromoted} fait(s) local(aux) non promu(s) — lance /memory-promote pour les partager."
fi

[ -n "$msg" ] && printf '%s\n' "$msg"
exit 0
```

Rendre exécutable :

```bash
chmod +x scripts/hook-memory.sh
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_hooks.HookScriptTest -v`
Expected : PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/hook-memory.sh tests/test_hooks.py
git commit -m "feat(hooks): hook-memory.sh start|end — synchro best-effort + rappel promote

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : Déclarer les hooks dans `plugin.json`

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Test: `tests/test_hooks.py`

- [ ] **Step 1 : Ajouter le test qui échoue**

Ajouter dans `tests/test_hooks.py`, avant `if __name__` :

```python
class PluginHooksTest(unittest.TestCase):
    def test_plugin_declares_session_hooks(self):
        cfg = json.load(open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), encoding="utf-8"))
        hooks = cfg.get("hooks", {})
        start = json.dumps(hooks.get("SessionStart"))
        end = json.dumps(hooks.get("SessionEnd"))
        self.assertIn("hook-memory.sh", start)
        self.assertIn("start", start)
        self.assertIn("hook-memory.sh", end)
        self.assertIn("end", end)
        self.assertIn("CLAUDE_PLUGIN_ROOT", start)
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_hooks.PluginHooksTest -v`
Expected : FAIL — pas de clé `hooks` dans `plugin.json`.

- [ ] **Step 3 : Ajouter le bloc `hooks` à `.claude-plugin/plugin.json`**

Le fichier actuel se termine par `"author": { … }`. Ajouter une clé `"hooks"` au niveau racine de l'objet (après `"author"`, avec une virgule). Le `plugin.json` complet devient :

```json
{
  "name": "shared-memory",
  "version": "0.1.0",
  "description": "Mémoire d'équipe partagée par projet : branche la mémoire native de Claude Code sur un vault git privé (un par équipe), avec gouvernance par Pull Request.",
  "author": {
    "name": "Benjamin Manguet",
    "email": "benjamin.manguet@gmail.com"
  },
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/hook-memory.sh\" start" } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command", "command": "bash \"${CLAUDE_PLUGIN_ROOT}/scripts/hook-memory.sh\" end" } ] }
    ]
  }
}
```

- [ ] **Step 4 : Lancer, vérifier le succès + validité JSON**

Run :
```bash
python3 -c "import json; json.load(open('.claude-plugin/plugin.json')); print('JSON OK')"
python3 -m unittest tests.test_hooks.PluginHooksTest -v
```
Expected : `JSON OK` puis PASS (1 test).

- [ ] **Step 5 : Commit**

```bash
git add .claude-plugin/plugin.json tests/test_hooks.py
git commit -m "feat(hooks): déclare SessionStart/SessionEnd dans plugin.json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Documentation (convention du programme)

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `docs/ARCHITECTURE.md`

Markdown ; vérif par relecture + grep.

- [ ] **Step 1 : README — ajouter à la section « Recherche & passage à l'échelle »**

Dans `README.md`, à la fin de la liste de la section `## Recherche & passage à l'échelle`, ajouter la puce :

```markdown
- **Boucle vivante (hooks)** : au **démarrage de session**, le plugin **synchronise** le vault (`git pull --ff-only`, best-effort) et **rappelle** les faits locaux non promus (« prévois `/memory-promote` avant de fermer ») ; un rappel **en fin de session** clôt la boucle. Tout est silencieux si le projet n'est pas branché.
```

- [ ] **Step 2 : INSTALL — note dans « Chaque membre »**

Dans `INSTALL.md`, juste après le tableau « Commandes utiles » (la dernière ligne du tableau), ajouter :

```markdown
> **Automatique** : à chaque démarrage de session, le plugin récupère les derniers faits de
> l'équipe (`git pull` best-effort) et te rappelle tes faits locaux non encore partagés — pense à
> `/memory-promote` **avant de fermer** pour éviter les décalages. Rien à lancer à la main.
```

- [ ] **Step 3 : ARCHITECTURE — §10 (le risque « Discipline » est atténué) + entrée §12**

Dans `docs/ARCHITECTURE.md`, dans la section `## 10. Risques`, remplacer la puce « Discipline » :

```markdown
- **Discipline.** Si personne ne lance `/memory-promote` ni `/memory-review`, le
  canonique se fige et devient obsolète — comme n'importe quelle doc. **À trancher :
  qui est référent, à quelle fréquence valide-t-il, qu'est-ce qui déclenche une promotion ?**
```

par :

```markdown
- **Discipline.** Si personne ne lance `/memory-promote` ni `/memory-review`, le canonique se fige
  et devient obsolète. **Atténué** par les **hooks de session** (§12 « Boucle vivante ») : synchro
  automatique au démarrage + rappel de promotion (début et fin de session). Reste à trancher côté
  équipe : qui est référent, à quelle fréquence valide-t-il.
```

Puis, à la **fin de la section `## 12`**, ajouter la sous-section :

```markdown
### Boucle vivante : hooks de session
Deux **hooks plugin** referment la boucle sans discipline manuelle. `SessionStart` :
`git pull --ff-only` **best-effort** (time-boxé, non destructif — refuse sans écraser les brouillons
étage 1) pour ne pas travailler sur une mémoire périmée, puis rappelle les faits locaux non promus
(« prévois `/memory-promote` avant de fermer »). `SessionEnd` : dernier rappel. Tout est silencieux
si le projet n'est pas branché ou en cas d'échec (jamais bloquant). Script : `scripts/hook-memory.sh`.
```

- [ ] **Step 4 : Vérifier**

Run : `grep -c "Boucle vivante\|hook-memory\|hooks de session" README.md INSTALL.md docs/ARCHITECTURE.md`
Expected : chaque fichier renvoie ≥ 1.

- [ ] **Step 5 : Commit**

```bash
git add README.md INSTALL.md docs/ARCHITECTURE.md
git commit -m "docs(hooks): documenter la boucle vivante (README/INSTALL/ARCHITECTURE)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Vérification d'ensemble + fumée réelle

- [ ] **Step 1 : Suite complète**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : tous les tests passent (95 précédents + hooks : count 4 + script 3 + plugin 1 = 103).

- [ ] **Step 2 : Fumée — no-op quand non branché**

Run :
```bash
CLAUDE_PROJECT_DIR=/no/such SM_REGISTRY=/no/registry.json bash scripts/hook-memory.sh start; echo "exit=$?"
```
Expected : aucune sortie, `exit=0`.

- [ ] **Step 3 : Fumée — rappel quand brouillon présent**

Run :
```bash
d=$(mktemp -d); git -C "$d" init -q; git -C "$d" config user.email t@t; git -C "$d" config user.name t
printf '%s' '---
name: a
description: d
metadata:
  type: project
---
x' > "$d/a.md"; git -C "$d" add -A; git -C "$d" commit -qm base
printf '%s' '---
name: b
description: d
metadata:
  type: project
---
y' > "$d/b.md"
reg=$(mktemp); printf '{"projets":[{"slug":"%s","clone":"%s"}]}' "$(printf '%s' "$d" | sed -E 's#[^a-zA-Z0-9]+#-#g')" "$d" > "$reg"
CLAUDE_PROJECT_DIR="$d" SM_REGISTRY="$reg" bash scripts/hook-memory.sh end
rm -rf "$d" "$reg"
```
Expected : une ligne contenant `📝 Avant de partir : 1 fait(s) … /memory-promote`.

- [ ] **Step 4 : Rappel de vérification manuelle (déclenchement réel)**

Le déclenchement effectif des events `SessionStart`/`SessionEnd` par Claude Code ne se teste pas en
unitaire. Après `chmod +x` et un `/reload-plugins` (ou redémarrage de session) sur un projet branché,
confirmer de visu que le message de synchro/rappel apparaît bien au démarrage. **(Pas de commit.)**

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| `sm_count_unpromoted` (partageables vs origin/main, hors index/MEMORY/perso) | Task 1 |
| `hook-memory.sh start` : pull --ff-only best-effort + ahead + message | Task 2 |
| `hook-memory.sh end` : rappel si non-promus, silencieux sinon | Task 2 |
| Best-effort : time-box, silencieux, exit 0, relâche set -euo de lib.sh | Task 2 (Step 3) |
| no-op silencieux si projet non branché | Task 2 (`test_noop_when_not_branched`) |
| SessionStart avertit « avant de fermer » | Task 2 (Step 3, message start) |
| Déclaration des 2 hooks dans plugin.json | Task 3 |
| Doc (README/INSTALL/ARCHITECTURE §10+§12) | Task 4 |
| Tests + fumée + rappel vérif manuelle | Tasks 1-3, 5 |

**Cohérence des types/noms :**
- `sm_count_unpromoted <clone> -> entier` : définie Task 1, appelée par `hook-memory.sh` (Task 2) et testée Tasks 1-2.
- `hook-memory.sh <start|end>` : même contrat dans le script (Task 2), plugin.json (Task 3) et tests (Task 2).
- Slug : `sm_slug` (lib.sh existant) ; le test calcule le slug avec la même règle `sed -E 's#[^a-zA-Z0-9]+#-#g'`.
- Résolution vault : `sm_vault_clone_for_slug` (lib.sh existant, lit `SM_REGISTRY`).

**Placeholders :** aucun — bash et tests complets, commandes et sorties attendues explicites.

**Note (non bloquante) — format des hooks plugin :** le bloc `hooks` est placé dans `plugin.json`
selon la convention Claude Code (`SessionStart`/`SessionEnd` → `{hooks:[{type:command,command}]}`).
Si l'environnement attend plutôt un fichier `hooks/hooks.json` séparé, déplacer le même bloc ; la
**Task 5 Step 4** (vérif manuelle du déclenchement) le confirme. Le `set +e +u +o pipefail` après le
`source lib.sh` est essentiel : sans lui, le `set -euo pipefail` de `lib.sh` ferait aborter le hook.
