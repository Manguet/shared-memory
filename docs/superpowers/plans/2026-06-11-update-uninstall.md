# Mise à jour & désinstallation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Débrancher proprement un projet (`/memory-unsetup`) et désinstaller la machine (`uninstall.sh`) — l'inverse exact du setup, en conservant les données (clones) par défaut ; documenter la mise à jour.

**Architecture :** 3 fonctions registre testables dans `lib.sh` (`sm_symlink_for_slug`, `sm_registry_slugs`, `sm_unregister`), réutilisées par `unlink-vault.sh` (un projet) et `uninstall.sh` (machine). Un dossier mémoire n'est retiré que s'il est un symlink. Skill `/memory-unsetup`. Tests bash réels.

**Tech Stack :** bash, Python 3 (heredoc registre, comme l'existant), `unittest` (subprocess bash + vrais symlinks).

**Référence design :** `docs/superpowers/specs/2026-06-11-update-uninstall-design.md`.

**Convention du programme :** doc ET tests à jour à chaque chantier (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/lib.sh` | `sm_symlink_for_slug`, `sm_registry_slugs`, `sm_unregister`. | Modifier |
| `scripts/unlink-vault.sh` | débrancher le projet courant (inverse de `setup-vault.sh`). | Créer |
| `scripts/uninstall.sh` | désinstallation machine. | Créer |
| `skills/memory-unsetup/SKILL.md` | skill de débranchement par projet. | Créer |
| `tests/test_uninstall.py` | unitaires lib + intégration `unlink-vault.sh` + `uninstall.sh`. | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md` | documenter. | Modifier |

**Conventions réutilisées :**
- `lib.sh` : `SM_REGISTRY` (registre JSON `{"projets": [{slug, project_dir, vault, clone, symlink}]}`),
  `sm_slug`, et `sm_vault_clone_for_slug` (modèle pour les nouvelles fonctions — Python heredoc).
- `install.sh` : `DEST="${SHARED_MEMORY_HOME:-$HOME/.shared-memory/plugin}"` (le plugin) ; racine
  standard `~/.shared-memory/{plugin,vaults,models,embeddings}`.
- Tests bash réels : pattern de `tests/test_setup.py` / `tests/test_hooks.py`.

---

## Task 1 : Fonctions registre dans `lib.sh` + tests unitaires

**Files:**
- Modify: `scripts/lib.sh`
- Create: `tests/test_uninstall.py`

- [ ] **Step 1 : Écrire les tests unitaires (`tests/test_uninstall.py`)**

```python
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
LIB = os.path.join(HERE, "..", "scripts", "lib.sh")
UNLINK = os.path.join(HERE, "..", "scripts", "unlink-vault.sh")
UNINSTALL = os.path.join(HERE, "..", "scripts", "uninstall.sh")


def call(reg, *argv):
    """Source lib.sh (avec SM_REGISTRY=reg) puis exécute `argv` (func + args). Renvoie le résultat."""
    env = dict(os.environ, SM_REGISTRY=reg)
    return subprocess.run(["bash", "-c", 'source "$1"; shift; "$@"', "_", LIB, *argv],
                          capture_output=True, text=True, env=env)


def slug_of(path):
    return subprocess.run(["bash", "-c", 'source "$1"; sm_slug "$2"', "_", LIB, path],
                          capture_output=True, text=True).stdout.strip()


class RegistryFnTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.reg = os.path.join(self._t.name, "registry.json")

    def tearDown(self):
        self._t.cleanup()

    def _reg(self, projets):
        with open(self.reg, "w") as f:
            json.dump({"projets": projets}, f)

    def test_symlink_for_slug(self):
        self._reg([{"slug": "-a", "symlink": "/sym/a", "clone": "/cl/a"},
                   {"slug": "-b", "symlink": "/sym/b", "clone": "/cl/b"}])
        self.assertEqual(call(self.reg, "sm_symlink_for_slug", "-b").stdout.strip(), "/sym/b")

    def test_symlink_unknown_slug_empty(self):
        self._reg([{"slug": "-a", "symlink": "/sym/a"}])
        self.assertEqual(call(self.reg, "sm_symlink_for_slug", "-zzz").stdout.strip(), "")

    def test_registry_slugs_lists_all(self):
        self._reg([{"slug": "-a"}, {"slug": "-b"}])
        self.assertEqual(sorted(call(self.reg, "sm_registry_slugs").stdout.split()), ["-a", "-b"])

    def test_unregister_removes_one_keeps_other(self):
        self._reg([{"slug": "-a"}, {"slug": "-b"}])
        call(self.reg, "sm_unregister", "-a")
        with open(self.reg) as f:
            self.assertEqual([p["slug"] for p in json.load(f)["projets"]], ["-b"])

    def test_unregister_idempotent(self):
        self._reg([{"slug": "-b"}])
        call(self.reg, "sm_unregister", "-a")
        call(self.reg, "sm_unregister", "-a")
        with open(self.reg) as f:
            self.assertEqual([p["slug"] for p in json.load(f)["projets"]], ["-b"])

    def test_no_registry_no_error(self):
        missing = os.path.join(self._t.name, "none.json")
        r = call(missing, "sm_registry_slugs")
        self.assertEqual(r.stdout.strip(), "")
        call(missing, "sm_unregister", "-a")   # ne doit pas planter


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_uninstall.RegistryFnTest -v`
Expected : FAIL — les fonctions n'existent pas (sortie vide / non-zéro).

- [ ] **Step 3 : Ajouter les 3 fonctions à `scripts/lib.sh`**

Dans `scripts/lib.sh`, **juste après** la fonction `sm_vault_clone_for_slug` (repérée par sa
dernière ligne `}` suivant son heredoc `PY`), insérer :

```bash
# Chemin du symlink mémoire enregistré pour un slug (vide si absent).
sm_symlink_for_slug() {
  local slug="$1"
  [ -f "$SM_REGISTRY" ] || return 1
  python3 - "$SM_REGISTRY" "$slug" <<'PY'
import json, sys
try:
    reg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
slug = sys.argv[2]
for p in reg.get("projets", []):
    if p.get("slug") == slug:
        print(p.get("symlink", ""))
        break
PY
}

# Liste tous les slugs enregistrés (un par ligne ; vide si pas de registre).
sm_registry_slugs() {
  [ -f "$SM_REGISTRY" ] || return 0
  python3 - "$SM_REGISTRY" <<'PY'
import json, sys
try:
    reg = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
for p in reg.get("projets", []):
    s = p.get("slug")
    if s:
        print(s)
PY
}

# Retire l'entrée de registre d'un slug (idempotent, best-effort).
sm_unregister() {
  local slug="$1"
  [ -f "$SM_REGISTRY" ] || return 0
  python3 - "$SM_REGISTRY" "$slug" <<'PY'
import json, sys
path, slug = sys.argv[1], sys.argv[2]
try:
    reg = json.load(open(path))
except Exception:
    sys.exit(0)
reg["projets"] = [p for p in reg.get("projets", []) if p.get("slug") != slug]
json.dump(reg, open(path, "w"), indent=2, ensure_ascii=False)
PY
}
```

- [ ] **Step 4 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_uninstall.RegistryFnTest -v`
Expected : PASS (6 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/lib.sh tests/test_uninstall.py
git commit -m "feat(lib): sm_symlink_for_slug / sm_registry_slugs / sm_unregister (registre)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : `scripts/unlink-vault.sh` + intégration

**Files:**
- Create: `scripts/unlink-vault.sh`
- Modify: `tests/test_uninstall.py`

- [ ] **Step 1 : Ajouter les tests d'intégration (`tests/test_uninstall.py`)**

Ajouter cette classe **avant** le `if __name__ == "__main__":` final :

```python
class UnlinkVaultTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self.reg = os.path.join(self.d, "registry.json")

    def tearDown(self):
        self._t.cleanup()

    def _run(self, project_dir):
        env = dict(os.environ, SM_REGISTRY=self.reg)
        return subprocess.run(["bash", UNLINK, project_dir],
                              capture_output=True, text=True, env=env)

    def test_removes_symlink_and_entry_keeps_clone(self):
        clone = os.path.join(self.d, "clone")
        os.makedirs(clone)
        sym = os.path.join(self.d, "memlink")
        os.symlink(clone, sym)
        slug = slug_of("/tmp/projX")
        with open(self.reg, "w") as f:
            json.dump({"projets": [{"slug": slug, "symlink": sym, "clone": clone}]}, f)
        r = self._run("/tmp/projX")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.lexists(sym))        # symlink retiré
        self.assertTrue(os.path.isdir(clone))          # clone conservé
        with open(self.reg) as f:
            self.assertEqual(json.load(f)["projets"], [])   # entrée retirée

    def test_does_not_delete_real_dir(self):
        clone = os.path.join(self.d, "clone")
        os.makedirs(clone)
        realdir = os.path.join(self.d, "realmem")       # vrai dossier, PAS un symlink
        os.makedirs(realdir)
        slug = slug_of("/tmp/projY")
        with open(self.reg, "w") as f:
            json.dump({"projets": [{"slug": slug, "symlink": realdir, "clone": clone}]}, f)
        r = self._run("/tmp/projY")
        self.assertEqual(r.returncode, 0)
        self.assertTrue(os.path.isdir(realdir))         # vrai dossier NON supprimé
        self.assertIn("vrai dossier", r.stdout)

    def test_not_branched_is_noop(self):
        with open(self.reg, "w") as f:
            json.dump({"projets": []}, f)
        r = self._run("/tmp/projZ")
        self.assertEqual(r.returncode, 0)
        self.assertIn("non branché", r.stdout)
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_uninstall.UnlinkVaultTest -v`
Expected : ERROR/FAIL — `unlink-vault.sh` n'existe pas.

- [ ] **Step 3 : Écrire `scripts/unlink-vault.sh`**

```bash
#!/usr/bin/env bash
# Débranche la mémoire native du projet courant : retire le symlink + l'entrée de registre.
# GARDE le clone du vault (données). Usage: unlink-vault.sh [project-dir]
# BEST-EFFORT : ne supprime jamais une vraie mémoire locale (uniquement un symlink).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh" 2>/dev/null || exit 0
set +e +u +o pipefail

PROJECT_DIR="${1:-${CLAUDE_PROJECT_DIR:-$PWD}}"
SLUG="$(sm_slug "$PROJECT_DIR")"

clone="$(sm_vault_clone_for_slug "$SLUG" 2>/dev/null)"
sym="$(sm_symlink_for_slug "$SLUG" 2>/dev/null)"

if [ -z "$clone" ] && [ -z "$sym" ]; then
  echo "Projet non branché (slug: $SLUG) — rien à débrancher."
  exit 0
fi

if [ -n "$sym" ] && [ -L "$sym" ]; then
  rm "$sym"
  echo "Symlink mémoire retiré : $sym"
elif [ -n "$sym" ] && [ -e "$sym" ]; then
  echo "Attention : $sym est un vrai dossier (pas un symlink) — laissé intact."
fi

sm_unregister "$SLUG"
echo "Entrée de registre retirée (slug: $SLUG)."
[ -n "$clone" ] && echo "Clone du vault conservé : $clone"
echo "Pour re-brancher : /memory-setup <url-du-vault>."
exit 0
```

- [ ] **Step 4 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_uninstall.UnlinkVaultTest -v`
Expected : PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/unlink-vault.sh tests/test_uninstall.py
git commit -m "feat(unsetup): unlink-vault.sh — débrancher un projet (symlink + registre, clone gardé)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : `scripts/uninstall.sh` + intégration

**Files:**
- Create: `scripts/uninstall.sh`
- Modify: `tests/test_uninstall.py`

- [ ] **Step 1 : Ajouter les tests d'intégration (`tests/test_uninstall.py`)**

Ajouter cette classe **avant** le `if __name__ == "__main__":` final :

```python
class UninstallTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.home = self._t.name
        self.smroot = os.path.join(self.home, ".shared-memory")
        os.makedirs(os.path.join(self.smroot, "plugin"))
        os.makedirs(os.path.join(self.smroot, "models"))
        os.makedirs(os.path.join(self.smroot, "vaults", "v1"))
        self.reg = os.path.join(self.home, "registry.json")
        self.sym = os.path.join(self.home, "memlink")
        os.symlink(os.path.join(self.smroot, "vaults", "v1"), self.sym)
        with open(self.reg, "w") as f:
            json.dump({"projets": [{"slug": "-p", "symlink": self.sym,
                                    "clone": os.path.join(self.smroot, "vaults", "v1")}]}, f)

    def tearDown(self):
        self._t.cleanup()

    def _run(self, *flags):
        env = dict(os.environ, HOME=self.home, SM_REGISTRY=self.reg)
        env.pop("SHARED_MEMORY_HOME", None)
        return subprocess.run(["bash", UNINSTALL, "--yes", *flags],
                              capture_output=True, text=True, env=env)

    def test_removes_plugin_and_caches_keeps_vaults(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.smroot, "plugin")))
        self.assertFalse(os.path.exists(os.path.join(self.smroot, "models")))
        self.assertTrue(os.path.isdir(os.path.join(self.smroot, "vaults", "v1")))   # gardé
        self.assertFalse(os.path.lexists(self.sym))   # débranché
        with open(self.reg) as f:
            self.assertEqual(json.load(f)["projets"], [])

    def test_purge_removes_vaults(self):
        r = self._run("--purge")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.smroot, "vaults")))
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_uninstall.UninstallTest -v`
Expected : ERROR/FAIL — `uninstall.sh` n'existe pas.

- [ ] **Step 3 : Écrire `scripts/uninstall.sh`**

```bash
#!/usr/bin/env bash
# Désinstallation machine de shared-memory : débranche tous les projets, retire le plugin et les
# caches. GARDE les clones de vault (données) sauf --purge.
# Usage: uninstall.sh [--purge] [--yes]
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh" 2>/dev/null || exit 1
set +e +u +o pipefail

SM_ROOT="$HOME/.shared-memory"
PLUGIN_DIR="${SHARED_MEMORY_HOME:-$SM_ROOT/plugin}"
PURGE=0; YES=0
for a in "$@"; do
  case "$a" in
    --purge) PURGE=1 ;;
    --yes)   YES=1 ;;
  esac
done

echo "Désinstallation shared-memory."
echo "  Plugin : $PLUGIN_DIR"
if [ "$PURGE" = 1 ]; then
  echo "  ⚠ --purge : les clones de vault ($SM_ROOT/vaults) seront SUPPRIMÉS"
  echo "    (y compris d'éventuels brouillons NON promus)."
else
  echo "  Clones de vault conservés sous $SM_ROOT/vaults."
fi

if [ "$YES" != 1 ]; then
  printf "Confirmer ? tape 'oui' : "
  read -r ans
  [ "$ans" = "oui" ] || { echo "Annulé."; exit 0; }
fi

# 1. Débrancher tous les projets enregistrés (retirer le symlink si c'en est un).
for slug in $(sm_registry_slugs); do
  sym="$(sm_symlink_for_slug "$slug" 2>/dev/null)"
  if [ -n "$sym" ] && [ -L "$sym" ]; then
    rm "$sym" && echo "  symlink retiré : $sym"
  fi
  sm_unregister "$slug"
done
echo "  projets débranchés."

# 2. Retirer le plugin + caches.
cd "$HOME" 2>/dev/null
rm -rf "$PLUGIN_DIR" && echo "  plugin retiré : $PLUGIN_DIR"
rm -rf "$SM_ROOT/models" "$SM_ROOT/embeddings" && echo "  caches retirés."

# 3. Purge éventuelle (données).
if [ "$PURGE" = 1 ]; then
  rm -rf "$SM_ROOT/vaults" && echo "  clones de vault supprimés."
  rm -f "$SM_REGISTRY"
  rmdir "$SM_ROOT" 2>/dev/null
  echo "  purge complète."
fi

cat <<EOF

Pour finir, dans Claude Code :
  /plugin uninstall shared-memory
  /plugin marketplace remove $PLUGIN_DIR
EOF
exit 0
```

- [ ] **Step 4 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_uninstall.UninstallTest -v`
Expected : PASS (2 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/uninstall.sh tests/test_uninstall.py
git commit -m "feat(uninstall): uninstall.sh — désinstallation machine (clones gardés sauf --purge)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Skill `/memory-unsetup`

**Files:**
- Create: `skills/memory-unsetup/SKILL.md`

- [ ] **Step 1 : Écrire `skills/memory-unsetup/SKILL.md`**

```markdown
---
name: memory-unsetup
description: This skill should be used when the user asks to "débrancher la mémoire", "délier le vault", "déconnecter la mémoire d'équipe", "retirer le symlink mémoire", "unlink memory", "unsetup memory", or "/memory-unsetup". It removes this project's memory symlink and registry entry (the inverse of /memory-setup), keeping the vault clone (your data).
argument-hint: ""
allowed-tools: Bash, AskUserQuestion
version: 0.1.0
---

# memory-unsetup — Débrancher la mémoire du projet

Inverse de `/memory-setup` : retire le **symlink** mémoire et l'**entrée de registre** du projet
courant. **Garde le clone du vault** (tes données, y compris d'éventuels brouillons non promus).
Ne supprime jamais une vraie mémoire locale (uniquement un symlink).

## Procédure

1. **Vérifier que le projet est branché** :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, le dire (« projet non branché ») et s'arrêter.

2. **Confirmer** (AskUserQuestion) : « Débrancher la mémoire de ce projet ? Le clone du vault est
   conservé ; tu pourras re-brancher via `/memory-setup`. » Ne rien faire sans accord.

3. **Débrancher** :

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT%/}/scripts/unlink-vault.sh "${CLAUDE_PROJECT_DIR:-$PWD}"
   ```

4. **Rapporter** : le symlink et l'entrée de registre sont retirés, le clone est conservé (chemin
   affiché par le script). Rappeler `/memory-setup <url>` pour re-brancher, et `uninstall.sh` (en
   terminal) pour retirer complètement le plugin.

## Points d'attention

- **Données conservées** : le clone du vault n'est jamais supprimé par ce skill.
- **Sécurité** : seul un symlink est retiré ; une vraie mémoire locale est laissée intacte.
- **Confirmation obligatoire** avant de débrancher.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/unlink-vault.sh`** — débranchement (symlink + registre).
- **`${CLAUDE_PLUGIN_ROOT}/scripts/uninstall.sh`** — désinstallation machine (terminal).
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault / registre.
```

- [ ] **Step 2 : Vérifier le frontmatter**

Run :
```bash
head -7 skills/memory-unsetup/SKILL.md
grep -c "^name: memory-unsetup" skills/memory-unsetup/SKILL.md
```
Expected : frontmatter présent ; `grep` renvoie `1`.

- [ ] **Step 3 : Commit**

```bash
git add skills/memory-unsetup/SKILL.md
git commit -m "feat(unsetup): skill /memory-unsetup — débrancher un projet (clone gardé)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Documentation

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1 : README — tableau des skills**

Dans `README.md`, dans le tableau « ### Skills », après la ligne `| `/memory-setup` | … |`, insérer :

```markdown
| `/memory-unsetup` | **débrancher** le projet (retire symlink + registre, garde le clone) — inverse de `/memory-setup` |
```

- [ ] **Step 2 : INSTALL — section « Mise à jour »**

Dans `INSTALL.md`, à la **fin du fichier**, ajouter le texte suivant **verbatim** (les lignes
indentées de 4 espaces ci-dessous ne sont là que pour vous montrer le contenu littéral à écrire —
écrivez-les SANS l'indentation de 4 espaces ; les ```` ```bash ```` font partie du texte à écrire
dans `INSTALL.md`) :

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

- [ ] **Step 3 : ARCHITECTURE — nouvelle section §16**

Dans `docs/ARCHITECTURE.md`, à la **fin du fichier** (après §15), ajouter :

```markdown
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
```

- [ ] **Step 4 : Vérifier**

Run : `grep -c "memory-unsetup\|uninstall" README.md INSTALL.md docs/ARCHITECTURE.md`
Expected : chaque fichier ≥ 1.

- [ ] **Step 5 : Commit**

```bash
git add README.md INSTALL.md docs/ARCHITECTURE.md
git commit -m "docs(uninstall): documenter mise à jour & désinstallation (README/INSTALL/ARCHITECTURE)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 : Vérification

- [ ] **Step 1 : Suite complète (non-régression)**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : OK — tous les tests passent (existants + 11 de `test_uninstall`).

- [ ] **Step 2 : Fumée bout-en-bout (débranchement isolé)**

Run :
```bash
TMP=$(mktemp -d); CLONE="$TMP/clone"; mkdir -p "$CLONE"
SYM="$TMP/memlink"; ln -s "$CLONE" "$SYM"
REG="$TMP/registry.json"
SLUG="$(bash -c 'source "$1"; sm_slug "$2"' _ scripts/lib.sh /tmp/projSmoke)"
printf '{"projets":[{"slug":"%s","symlink":"%s","clone":"%s"}]}' "$SLUG" "$SYM" "$CLONE" > "$REG"
echo "=== avant ===" ; ls -la "$SYM" 2>&1 | sed 's/  */ /g'
SM_REGISTRY="$REG" bash scripts/unlink-vault.sh /tmp/projSmoke
echo "=== après : symlink présent ? ===" ; [ -L "$SYM" ] && echo OUI || echo "non (retiré)"
echo "=== clone présent ? ===" ; [ -d "$CLONE" ] && echo "oui (gardé)" || echo NON
echo "=== registre ===" ; cat "$REG"
rm -rf "$TMP"
```
Expected : symlink retiré (« non »), clone gardé (« oui »), registre `{"projets": []}`.

- [ ] **Step 3 : Relecture**

Vérifier de visu : `unlink-vault.sh` et `uninstall.sh` ne retirent un dossier mémoire que s'il est un
symlink (`[ -L ]`) ; `uninstall.sh` garde `vaults/` sauf `--purge` ; le skill `/memory-unsetup`
confirme avant d'agir ; la doc INSTALL/ARCHITECTURE est cohérente (données conservées par défaut).

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| `sm_symlink_for_slug` / `sm_registry_slugs` / `sm_unregister` | Task 1 + tests |
| `unlink-vault.sh` (symlink-only, clone gardé, non-branché = no-op) | Task 2 + tests |
| `uninstall.sh [--purge] [--yes]` (débranche tout, plugin/caches, clones gardés/purge) | Task 3 + tests |
| Skill `/memory-unsetup` (confirme, garde le clone) | Task 4 |
| Mise à jour = relancer install.sh (doc) | Task 5 (INSTALL) |
| Doc (README/INSTALL/ARCHITECTURE §16) | Task 5 |
| Tests (unitaires + intégration symlink/uninstall réels) | Task 1-3, Task 6 |

**Placeholders :** aucun — `lib.sh` (3 fonctions), `unlink-vault.sh`, `uninstall.sh`, `test_uninstall.py`
(3 classes), le `SKILL.md` et les edits doc sont fournis intégralement.

**Cohérence des types/signatures :** `sm_symlink_for_slug <slug>`, `sm_registry_slugs`,
`sm_unregister <slug>` — mêmes noms/usages dans `lib.sh`, `unlink-vault.sh`, `uninstall.sh` et les
tests. Registre `{"projets": [{slug, …, clone, symlink}]}` cohérent avec `setup-vault.sh`.
`PLUGIN_DIR="${SHARED_MEMORY_HOME:-$SM_ROOT/plugin}"` cohérent avec `DEST` d'`install.sh`. Le retrait
conditionnel `[ -L "$sym" ]` est identique dans `unlink-vault.sh` et `uninstall.sh`. Les tests
overrident `HOME`/`SM_REGISTRY` et neutralisent `SHARED_MEMORY_HOME` pour isoler le layout.
