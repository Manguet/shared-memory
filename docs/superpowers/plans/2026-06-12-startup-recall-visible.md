# Rappel mémoire visible + nudge santé au démarrage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le rappel mémoire d'équipe visible à l'ouverture (Claude l'affiche en première réponse) et signaler tout souci de configuration via un nudge `/doctor`, sans casser le digest existant ni le hook `SessionEnd`.

**Architecture:** Un hook `SessionStart` ne peut pas imprimer dans le terminal ; sa sortie n'alimente que le contexte du modèle. On reformule donc la sortie de `hook-memory.sh start` en **instruction** (« affiche ce rappel à l'utilisateur ») suivie d'un **rappel compact** (résumé + actions + nudge `/doctor` conditionnel), puis du **digest complet** en contexte silencieux. Une vérif santé légère (`sm_health_issues` dans `lib.sh`) décide du nudge ; `digest.py --summary` fournit la ligne compacte.

**Tech Stack:** Bash (hook + helpers `lib.sh`), Python 3 stdlib (`digest.py`, importlib pour les tests), `unittest` (sous-process pour le bash, isolation `SM_REGISTRY`/`HOME`/vault jetable — jamais le vrai vault).

---

## Contexte pour l'implémenteur (à lire avant de commencer)

- **Best-effort sacré** : `hook-memory.sh` ne doit JAMAIS bloquer la session. Il fait `set +e +u +o pipefail`, time-boxe les commandes réseau/Python, et **sort toujours 0**. Ne change pas ça.
- **Jamais le vrai vault** : tous les tests créent des vaults jetables (`tempfile.TemporaryDirectory`) et passent `SM_REGISTRY` (et parfois `HOME`) en variables d'environnement isolées. N'utilise aucun chemin réel.
- **Compat ascendante** : le mode complet de `digest.py` (sans flag) et le hook `SessionEnd` restent **inchangés**. Les tests existants de `tests/test_digest.py` et `tests/test_hooks.py` doivent rester verts.
- **Gate d'acceptation** (à lancer en fin de chaque tâche après les tests ciblés) :
  `python3 -W error::ResourceWarning -m unittest discover -s tests` → doit afficher `OK`.
- L'implémenteur **ne commite pas** sans accord explicite : l'utilisateur fait ses commits lui-même. Les étapes « Commit » ci-dessous sont des points de découpage logiques ; **demande avant de lancer `git commit`** (ou regroupe-les si l'utilisateur préfère commiter en une fois).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/digest.py` | ajoute `build_summary()` + flag CLI `--summary` (ligne compacte « N faits (domaines…) »). Mode complet inchangé. | Modifier |
| `scripts/lib.sh` | ajoute `sm_health_issues "<clone>" "<project_dir>" "<pull_failed>"` (libellés de problèmes, un par ligne ; vide si sain). | Modifier |
| `scripts/hook-memory.sh` | `start` : assemble instruction + rappel compact + digest contexte ; ne `pull` que si `origin` existe ; capte l'échec de pull ; appelle la vérif santé. `end` inchangé. | Modifier |
| `tests/test_digest.py` | couvre `build_summary` (et la CLI `--summary`). | Modifier |
| `tests/test_hooks.py` | couvre `sm_health_issues` (KO/sain) et le nouveau `start` (instruction, rappel compact, nudge `/doctor`, digest présent). | Modifier |
| `docs/ARCHITECTURE.md` | documente le rappel visible + la vérif santé. | Modifier |

---

### Task 1: `digest.py --summary` (ligne compacte)

**Files:**
- Modify: `scripts/digest.py`
- Test: `tests/test_digest.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_digest.py`, avant le `if __name__ == "__main__":` final, une nouvelle classe (le module est déjà chargé en `dg`, helpers `write`/`fact_md`/`TODAY` déjà présents en haut du fichier) :

```python
class BuildSummaryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_vault_returns_empty(self):
        self.assertEqual(dg.build_summary(self.vault), "")

    def test_one_line_count_and_domains(self):
        write(os.path.join(self.vault, "mailing", "a.md"), fact_md("a", "desc a"))
        write(os.path.join(self.vault, "facturation", "b.md"), fact_md("b", "desc b"))
        out = dg.build_summary(self.vault)
        # Une seule ligne, le compte total et les domaines.
        self.assertNotIn("\n", out)
        self.assertIn("2 faits", out)
        self.assertIn("mailing", out)
        self.assertIn("facturation", out)

    def test_singular_for_one_fact(self):
        write(os.path.join(self.vault, "mailing", "seul.md"), fact_md("seul", "x"))
        out = dg.build_summary(self.vault)
        self.assertIn("1 fait", out)
        self.assertNotIn("1 faits", out)

    def test_truncates_beyond_max_domains(self):
        for i in range(8):
            write(os.path.join(self.vault, "dom%d" % i, "f.md"), fact_md("f%d" % i, "x"))
        out = dg.build_summary(self.vault, max_domains=6)
        self.assertIn("…", out)        # marqueur de troncature
        self.assertIn("8 faits", out)
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `python3 -m unittest tests.test_digest.BuildSummaryTest -v`
Expected: FAIL — `AttributeError: module 'digest' has no attribute 'build_summary'`.

- [ ] **Step 3: Implémenter `build_summary` + le flag CLI**

Dans `scripts/digest.py`, ajouter la fonction juste après `build_digest` (avant le bloc `if __name__`) :

```python
def build_summary(vault, max_domains=6):
    """Ligne unique « N faits (domaine1, domaine2, …) » pour le rappel compact du hook.

    Réutilise collect_facts ; vault vide -> "". Tronque au-delà de max_domains avec « … »."""
    facts, _ = _bv.collect_facts(vault, include_body=False)
    n = len(facts)
    if n == 0:
        return ""
    domains = sorted({f["domain"] for f in facts})
    shown = domains[:max_domains]
    if len(domains) > max_domains:
        shown = shown + ["…"]
    return "%s (%s)" % (_count(n, "fait"), ", ".join(shown))
```

Puis remplacer le bloc `__main__` existant :

```python
if __name__ == "__main__":
    vault = sys.argv[1] if len(sys.argv) > 1 else "."
    out = build_digest(vault)
    if out:
        print(out)
```

par :

```python
if __name__ == "__main__":
    args = sys.argv[1:]
    summary = "--summary" in args
    rest = [a for a in args if a != "--summary"]
    vault = rest[0] if rest else "."
    out = build_summary(vault) if summary else build_digest(vault)
    if out:
        print(out)
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python3 -m unittest tests.test_digest -v`
Expected: PASS (anciens + `BuildSummaryTest`).

- [ ] **Step 5: Vérifier la CLI `--summary` à la main**

Run:
```bash
d=$(mktemp -d); mkdir -p "$d/mailing"; printf -- '---\nname: a\ndescription: d\nmetadata:\n  type: project\n---\nx\n' > "$d/mailing/a.md"
python3 scripts/digest.py --summary "$d"; rm -rf "$d"
```
Expected: une ligne du type `1 fait (mailing)`.

- [ ] **Step 6: Commit** (demander l'accord avant de lancer)

```bash
git add scripts/digest.py tests/test_digest.py
git commit -m "feat(digest): mode --summary (ligne compacte pour le rappel de démarrage)"
```

---

### Task 2: `sm_health_issues` dans `lib.sh`

**Files:**
- Modify: `scripts/lib.sh`
- Test: `tests/test_hooks.py`

**Interface :** `sm_health_issues "<clone>" "<project_dir>" "<pull_failed:0|1>"` imprime **un libellé de problème par ligne** (rien si tout va bien), sort 0. Vérifie : `git`/`python3` présents, clone existant et dépôt git (`<clone>/.git`), lien mémoire (`sm_memory_dir "<project_dir>"`) présent et résolu **dans** le clone, et `pull_failed=1` signalé par l'appelant.

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_hooks.py`, ajouter un helper près de `count_unpromoted` (qui montre déjà le pattern « sourcer lib.sh et appeler une fonction ») :

```python
def health_issues(clone, project_dir, pull_failed="0", home=None):
    env = dict(os.environ)
    if home:
        env["HOME"] = home
    r = subprocess.run(
        ["bash", "-c", 'source "$1"; sm_health_issues "$2" "$3" "$4"',
         "_", LIB, clone, project_dir, pull_failed],
        capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.strip()
```

Puis une classe de test. Note : le slug de `/tmp/proj` est `-tmp-proj` (runs non-alphanumériques → `-`), donc le lien mémoire attendu est `<HOME>/.claude/projects/-tmp-proj/memory`.

```python
class HealthIssuesTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self.clone = os.path.join(self.d, "clone")
        os.makedirs(self.clone)
        init_repo(self.clone)
        self.home = os.path.join(self.d, "home")
        self.memdir = os.path.join(self.home, ".claude", "projects", "-tmp-proj")
        os.makedirs(self.memdir)

    def tearDown(self):
        self._t.cleanup()

    def _wire_link(self):
        os.symlink(self.clone, os.path.join(self.memdir, "memory"))

    def test_silent_when_healthy(self):
        self._wire_link()
        rc, out = health_issues(self.clone, "/tmp/proj", "0", home=self.home)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_flags_missing_clone(self):
        self._wire_link()
        rc, out = health_issues(os.path.join(self.d, "nope"), "/tmp/proj", "0", home=self.home)
        self.assertNotEqual(out, "")

    def test_flags_unwired_memory_link(self):
        # pas de _wire_link() -> lien mémoire absent
        rc, out = health_issues(self.clone, "/tmp/proj", "0", home=self.home)
        self.assertNotEqual(out, "")

    def test_flags_pull_failure(self):
        self._wire_link()
        rc, out = health_issues(self.clone, "/tmp/proj", "1", home=self.home)
        self.assertNotEqual(out, "")
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `python3 -m unittest tests.test_hooks.HealthIssuesTest -v`
Expected: FAIL — `sm_health_issues: command not found` (donc sortie vide / non vide selon les cas, plusieurs asserts cassent ; notamment `test_flags_missing_clone` échoue car `out == ""`).

- [ ] **Step 3: Implémenter `sm_health_issues`**

Dans `scripts/lib.sh`, ajouter la fonction (par exemple juste après `sm_memory_dir`, dont elle dépend) :

```bash
# Problèmes de configuration d'un projet branché (best-effort, lecture seule).
# Args: $1=clone  $2=project_dir  $3=pull_failed(0|1)
# Imprime un libellé de problème par ligne ; rien si tout va bien. Sort toujours 0.
sm_health_issues() {
  local clone="$1" project_dir="$2" pull_failed="${3:-0}"
  command -v git     >/dev/null 2>&1 || printf '%s\n' "git introuvable dans le PATH"
  command -v python3 >/dev/null 2>&1 || printf '%s\n' "python3 introuvable dans le PATH"

  if [ -z "$clone" ] || [ ! -d "$clone/.git" ]; then
    printf '%s\n' "clone du vault introuvable ou non versionné (git)"
  else
    local mem real_mem real_clone
    mem="$(sm_memory_dir "$project_dir")"
    if [ ! -e "$mem" ]; then
      printf '%s\n' "lien mémoire absent (projet non câblé)"
    else
      real_mem="$(cd "$mem" 2>/dev/null && pwd -P)"
      real_clone="$(cd "$clone" 2>/dev/null && pwd -P)"
      case "$real_mem" in
        "$real_clone"|"$real_clone"/*) : ;;
        *) printf '%s\n' "lien mémoire ne pointe pas vers le clone du vault" ;;
      esac
    fi
  fi

  [ "$pull_failed" = "1" ] && printf '%s\n' "échec de la synchro git (pull)"
  return 0
}
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `python3 -m unittest tests.test_hooks.HealthIssuesTest -v`
Expected: PASS (4/4).

- [ ] **Step 5: Commit** (demander l'accord avant de lancer)

```bash
git add scripts/lib.sh tests/test_hooks.py
git commit -m "feat(lib): sm_health_issues — vérif santé par projet (best-effort)"
```

---

### Task 3: `hook-memory.sh start` — instruction + rappel compact + digest contexte

**Files:**
- Modify: `scripts/hook-memory.sh`
- Test: `tests/test_hooks.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_hooks.py`, le helper `run_hook(mode, project_dir, registry)` existe déjà. Le remplacer pour permettre de surcharger `HOME` (nécessaire pour câbler/décâbler le lien mémoire) :

```python
def run_hook(mode, project_dir, registry, home=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project_dir, SM_REGISTRY=registry)
    if home:
        env["HOME"] = home
    r = subprocess.run(["bash", HOOK, mode], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.strip()
```

Puis ajouter une classe de test (slug de `/tmp/proj` = `-tmp-proj`) :

```python
class StartRecallTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self.clone = os.path.join(self.d, "clone")
        os.makedirs(self.clone)
        init_repo(self.clone)
        write(self.clone, "mailing/relance.md",
              "---\nname: relance\ndescription: Relancer apres trois jours\n"
              "metadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-qm", "base")
        self.reg = os.path.join(self.d, "registry.json")
        with open(self.reg, "w") as f:
            json.dump({"projets": [{"slug": "-tmp-proj", "clone": self.clone}]}, f)
        self.home = os.path.join(self.d, "home")
        self.memdir = os.path.join(self.home, ".claude", "projects", "-tmp-proj")
        os.makedirs(self.memdir)

    def tearDown(self):
        self._t.cleanup()

    def _wire_link(self):
        os.symlink(self.clone, os.path.join(self.memdir, "memory"))

    def test_emits_display_instruction(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertEqual(rc, 0)
        self.assertIn("affiche", out.lower())          # instruction au modèle
        self.assertIn("/memory-promote", out) if "non promu" in out else None

    def test_compact_recall_present(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertIn("Mémoire d'équipe", out)
        self.assertIn("mailing", out)                  # domaine dans la ligne compacte

    def test_full_digest_still_in_context(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertIn("Relancer apres trois jours", out)   # description = digest complet

    def test_doctor_nudge_when_link_broken(self):
        # pas de _wire_link() -> lien mémoire absent -> nudge /doctor
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertEqual(rc, 0)
        self.assertIn("/doctor", out)

    def test_no_doctor_nudge_when_healthy(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertNotIn("/doctor", out)
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `python3 -m unittest tests.test_hooks.StartRecallTest -v`
Expected: FAIL — `test_emits_display_instruction` (pas d'« affiche » dans la sortie actuelle) et `test_doctor_nudge_when_link_broken` (pas de `/doctor`) cassent ; `test_no_doctor_nudge_when_healthy` peut passer par accident.

- [ ] **Step 3: Réécrire `scripts/hook-memory.sh`**

Remplacer **tout** le contenu de `scripts/hook-memory.sh` par :

```bash
#!/usr/bin/env bash
# Hook mémoire shared-memory : synchro au démarrage + rappel visible + rappel de promotion.
# Usage : hook-memory.sh start|end
# BEST-EFFORT : ne bloque jamais la session, silencieux en cas d'échec, sort toujours 0.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$HERE/lib.sh" 2>/dev/null || exit 0
set +e +u +o pipefail            # relâche le set -euo de lib.sh : un hook ne doit jamais aborter

MODE="${1:-start}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

clone="$(sm_vault_clone_for_slug "$(sm_slug "$PROJECT_DIR")" 2>/dev/null)"
[ -n "$clone" ] && [ -d "$clone" ] || exit 0

unpromoted="$(sm_count_unpromoted "$clone")"

# ---------- SessionEnd : dernier rappel de promotion (inchangé) ----------
if [ "$MODE" = "end" ]; then
  [ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && \
    printf '%s\n' "📝 Avant de partir : ${unpromoted} fait(s) local(aux) non promu(s) — lance /memory-promote pour les partager."
  exit 0
fi

# ---------- SessionStart : synchro + rappel visible ----------
pull_failed=0
if git -C "$clone" remote get-url origin >/dev/null 2>&1; then     # ne pull QUE si un remote existe
  GIT_TERMINAL_PROMPT=0 timeout 5 git -C "$clone" pull --ff-only >/dev/null 2>&1 || pull_failed=1
fi
ahead="$(git -C "$clone" rev-list --count HEAD..origin/main 2>/dev/null || printf 0)"

summary="$(timeout 5 python3 "$HERE/digest.py" --summary "$clone" 2>/dev/null)"
digest="$(timeout 5 python3 "$HERE/digest.py" "$clone" 2>/dev/null)"
issues="$(sm_health_issues "$clone" "$PROJECT_DIR" "$pull_failed" 2>/dev/null)"

# Rappel compact (ce que l'utilisateur verra).
recall=""
[ -n "$summary" ] && recall+="🧠 Mémoire d'équipe — ${summary}"$'\n'
recall+="📥 ${ahead:-0} à récupérer · 📝 ${unpromoted:-0} non promu"
[ "${unpromoted:-0}" -gt 0 ] 2>/dev/null && \
  recall+=$'\n'"📝 ${unpromoted} fait(s) non promu(s) — pense à /memory-promote avant de fermer."
[ -n "$issues" ] && recall+=$'\n'"⚠ souci de configuration détecté → lance /doctor"

# Instruction au modèle : afficher le rappel à l'utilisateur, puis le digest en contexte silencieux.
printf '%s\n' "[shared-memory] Au début de ta toute première réponse de cette session, affiche tel quel à l'utilisateur le rappel ci-dessous, puis réponds normalement :"
printf '%s\n' "$recall"

if [ -n "$digest" ]; then
  printf '\n%s\n' "<!-- Contexte mémoire d'équipe (pour ton usage : ne le réaffiche pas, il est déjà résumé ci-dessus) -->"
  printf '%s\n' "$digest"
fi
exit 0
```

- [ ] **Step 4: Lancer les tests ciblés, vérifier le succès**

Run: `python3 -m unittest tests.test_hooks -v`
Expected: PASS — `StartRecallTest` 5/5, et les classes existantes (`CountUnpromotedTest`, `HookScriptTest`, `HealthIssuesTest`, `PluginHooksTest`) restent vertes.

Note : l'ancien `HookScriptTest.test_start_emits_digest_with_fact_description` utilise `run_hook` **sans** `home` (HOME réel, lien mémoire absent) — il assert seulement la présence du digest et de « Mémoire d'équipe », qui restent vrais ; il peut désormais contenir aussi le nudge `/doctor`, ce qu'il n'assert pas. Il doit rester vert. Si ce n'est pas le cas, NE PAS affaiblir l'assertion : relire la sortie réelle et corriger le hook.

- [ ] **Step 5: Vérifier le rappel à la main**

Run:
```bash
d=$(mktemp -d); c="$d/clone"; mkdir -p "$c/mailing"
git -C "$c" init -q; git -C "$c" config user.email t@t; git -C "$c" config user.name t
printf -- '---\nname: a\ndescription: Une convention\nmetadata:\n  type: project\n---\nx\n' > "$c/mailing/a.md"
git -C "$c" add -A; git -C "$c" commit -qm base >/dev/null
printf '{"projets":[{"slug":"-tmp-proj","clone":"%s"}]}' "$c" > "$d/reg.json"
CLAUDE_PROJECT_DIR=/tmp/proj SM_REGISTRY="$d/reg.json" bash scripts/hook-memory.sh start
rm -rf "$d"
```
Expected: une ligne d'instruction « …affiche tel quel… », puis `🧠 Mémoire d'équipe — 1 fait (mailing)`, `📥 0 à récupérer · 📝 0 non promu`, un nudge `→ lance /doctor` (lien mémoire non câblé ici), puis le digest complet sous le commentaire de contexte.

- [ ] **Step 6: Gate complet**

Run: `python3 -W error::ResourceWarning -m unittest discover -s tests`
Expected: `OK` (aucune régression).

- [ ] **Step 7: Commit** (demander l'accord avant de lancer)

```bash
git add scripts/hook-memory.sh tests/test_hooks.py
git commit -m "feat(hook): rappel mémoire visible au démarrage + nudge /doctor"
```

---

### Task 4: Documentation (`ARCHITECTURE.md`)

**Files:**
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Mettre à jour la section « Boucle vivante »**

Dans `docs/ARCHITECTURE.md`, remplacer le paragraphe de la section `### Boucle vivante : hooks de session` (qui commence par « Deux **hooks plugin** referment la boucle… ») par :

```markdown
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
```

- [ ] **Step 2: Vérifier la cohérence du fichier**

Run: `grep -n "sm_health_issues\|--summary\|rappel compact" docs/ARCHITECTURE.md`
Expected: les trois termes apparaissent dans la section mise à jour.

- [ ] **Step 3: Commit** (demander l'accord avant de lancer)

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs(architecture): rappel visible au démarrage + vérif santé"
```

---

## Self-Review (rempli par l'auteur du plan)

**1. Couverture de la spec :**
- Instruction + rappel compact + digest contexte → Task 3 (hook) + Task 1 (`--summary`). ✓
- Rappel compact = nb faits + domaines + amont + non promus + nudge conditionnel → Task 3 (assemblage `recall`). ✓
- Vérif santé rapide, nudge si KO, silencieux si sain → Task 2 (`sm_health_issues`) + Task 3 (tests KO/sain). ✓
- `SessionEnd` inchangé → Task 3 (branche `end` conservée à l'identique). ✓
- `digest.py` mode complet inchangé → Task 1 (ajout seulement, `build_digest` intact ; tests existants verts). ✓
- Doc + tests selon la convention du programme → Task 4 + tests dans chaque tâche. ✓

**2. Placeholders :** aucun « TBD/TODO » ; chaque étape qui modifie du code montre le code complet. ✓

**3. Cohérence des noms :** `build_summary(vault, max_domains=6)`, `sm_health_issues "<clone>" "<project_dir>" "<pull_failed>"`, slug `-tmp-proj`, flag `--summary` — identiques entre tâches et tests. ✓
```
