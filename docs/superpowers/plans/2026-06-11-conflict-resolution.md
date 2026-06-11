# Résolution de conflits du vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un outil `scripts/resolve-conflicts.py` + une procédure dans `/memory-review` qui résout automatiquement les conflits de merge sur les fichiers dérivés (`index/**`, via reshard) et ne laisse à l'humain que les vrais conflits de faits ou de carte.

**Architecture :** Une fonction pure testable `classify_conflicts(paths)` partitionne les chemins en conflit (derived/map/facts/other) ; une CLI orchestre git : cas « uniquement des index/** » → reshard + stage (sortie 0), sinon liste l'arbitrage humain et s'arrête (sortie 1). Flux en deux temps : reshard n'est lancé que quand aucun fait/carte n'est en conflit. Intégré à `/memory-review`.

**Tech Stack :** Python 3 (stdlib : `os`, `subprocess`, `sys`), bash, `unittest` (avec vrais dépôts git pour l'intégration).

**Référence design :** `docs/superpowers/specs/2026-06-11-conflict-resolution-design.md`.

**Convention du programme :** doc ET tests à jour à chaque chantier (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/resolve-conflicts.py` | `classify_conflicts` (pur, testable) + CLI d'orchestration git. | Créer |
| `tests/test_resolve_conflicts.py` | unitaires (classification) + intégration (vrais conflits git). | Créer |
| `skills/memory-review/SKILL.md` | gestion de conflit à l'étape de fusion. | Modifier |
| `skills/memory-promote/references/governance.md` | section « Conflits ». | Modifier |
| `docs/ARCHITECTURE.md` | §14 « Résolution de conflits ». | Modifier |

**Conventions réutilisées :**
- `scripts/reshard.py` : CLI `python3 reshard.py <vault>` régénère `index/**` et **préserve** la carte
  `MEMORY.md` curée (`_ensure_memory` ne la crée que si absente). C'est pourquoi un conflit sur
  `MEMORY.md` reste humain (reshard ne le régénère pas).
- git émet toujours des chemins séparés par `/` (indépendant de l'OS) — `classify_conflicts` découpe
  sur `/`.
- Tests avec vrais dépôts git : pattern de `tests/test_hooks.py` (`init_repo`, `git`, `write`).

---

## Task 1 : `classify_conflicts` + tests unitaires

**Files:**
- Create: `scripts/resolve-conflicts.py`
- Create: `tests/test_resolve_conflicts.py`

- [ ] **Step 1 : Écrire les tests unitaires (`tests/test_resolve_conflicts.py`)**

```python
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "resolve-conflicts.py")
SPEC = importlib.util.spec_from_file_location("resolve_conflicts", SCRIPT)
rc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rc)


class ClassifyConflictsTest(unittest.TestCase):
    def test_index_paths_are_derived(self):
        c = rc.classify_conflicts(["index/mailing.md", "index/mailing/sous.md"])
        self.assertEqual(c["derived"], ["index/mailing.md", "index/mailing/sous.md"])
        self.assertEqual(c["facts"], [])

    def test_memory_is_map(self):
        c = rc.classify_conflicts(["MEMORY.md"])
        self.assertEqual(c["map"], ["MEMORY.md"])

    def test_fact_md_is_fact(self):
        c = rc.classify_conflicts(["mailing/relance.md", "feedback_x.md"])
        self.assertEqual(sorted(c["facts"]), ["feedback_x.md", "mailing/relance.md"])

    def test_non_md_is_other(self):
        c = rc.classify_conflicts(["notes.txt"])
        self.assertEqual(c["other"], ["notes.txt"])

    def test_empty(self):
        c = rc.classify_conflicts([])
        self.assertEqual(c, {"derived": [], "map": [], "facts": [], "other": []})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_resolve_conflicts -v`
Expected : ERROR — `scripts/resolve-conflicts.py` n'existe pas.

- [ ] **Step 3 : Écrire `scripts/resolve-conflicts.py`**

```python
#!/usr/bin/env python3
"""Résolution des conflits de merge d'un vault mémoire.

`classify_conflicts(paths)` partitionne les chemins en conflit : index/** (dérivé, régénérable),
MEMORY.md (carte curée, humain), autres .md (faits, humain), reste (humain). La CLI résout
automatiquement le cas « uniquement des index/** » en régénérant via reshard.py ; sinon elle
liste ce que l'humain doit arbitrer et s'arrête (le merge n'est jamais complété à l'aveugle).

CLI : python3 resolve-conflicts.py <clone>
  sortie 0 : rien à résoudre, ou index régénérés et stagés (prêt à committer)
  sortie 1 : de vrais conflits (faits/carte/autres) restent — ou reshard a échoué
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RESHARD = os.path.join(_HERE, "reshard.py")


def classify_conflicts(paths):
    """Partitionne des chemins (relatifs au vault, séparés par '/') en derived/map/facts/other."""
    out = {"derived": [], "map": [], "facts": [], "other": []}
    for p in paths:
        if p.split("/")[0] == "index":
            out["derived"].append(p)
        elif p == "MEMORY.md":
            out["map"].append(p)
        elif p.endswith(".md"):
            out["facts"].append(p)
        else:
            out["other"].append(p)
    return out


def _git(clone, *args):
    return subprocess.run(["git", "-C", clone, *args], capture_output=True, text=True)


def _conflicted_paths(clone):
    r = _git(clone, "diff", "--name-only", "--diff-filter=U")
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def main(clone):
    paths = _conflicted_paths(clone)
    if not paths:
        print("Aucun conflit à résoudre.")
        return 0
    c = classify_conflicts(paths)
    human = c["facts"] + c["map"] + c["other"]
    if human:
        print("Conflits à arbitrer à la main (%d) :" % len(human))
        if c["facts"]:
            print("\n  Faits (contenu — choisis la bonne version, c'est un jugement) :")
            for p in c["facts"]:
                print("    - %s" % p)
        if c["map"]:
            print("\n  Carte MEMORY.md (garde l'union des domaines ; vérifie les doublons) :")
            for p in c["map"]:
                print("    - %s" % p)
        if c["other"]:
            print("\n  Autres :")
            for p in c["other"]:
                print("    - %s" % p)
        print("\nRésous-les, fais `git -C <clone> add <fichier>`, puis relance cet outil.")
        if c["derived"]:
            print("(%d index/** seront régénérés automatiquement au prochain passage.)"
                  % len(c["derived"]))
        return 1
    # uniquement des index/** -> régénération mécanique
    r = subprocess.run([sys.executable, _RESHARD, clone], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        print("Échec de reshard ; rien n'a été stagé.")
        return 1
    _git(clone, "add", "-A", "index/")
    print("✅ %d index régénéré(s) et résolu(s) — termine par `git commit`." % len(c["derived"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
```

- [ ] **Step 4 : Lancer les unitaires — succès attendu**

Run : `python3 -m unittest tests.test_resolve_conflicts -v`
Expected : PASS (5 tests de `ClassifyConflictsTest`).

- [ ] **Step 5 : Commit**

```bash
git add scripts/resolve-conflicts.py tests/test_resolve_conflicts.py
git commit -m "feat(conflicts): classify_conflicts + CLI de résolution (dérivé auto / faits humain)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : Tests d'intégration (vrais conflits git)

**Files:**
- Modify: `tests/test_resolve_conflicts.py`

- [ ] **Step 1 : Ajouter les helpers git + les tests d'intégration**

Dans `tests/test_resolve_conflicts.py`, ajouter ces helpers et cette classe **avant** le
`if __name__ == "__main__":` final. Le test fabrique un vrai conflit add/add sur `index/mailing.md`
(faits différents) et un vrai conflit modify/modify sur un même fait.

```python
FACT = ("---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\n%s\n")


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


def run_script(clone):
    return subprocess.run([sys.executable, SCRIPT, clone], capture_output=True, text=True)


def conflicted(clone):
    r = subprocess.run(["git", "-C", clone, "diff", "--name-only", "--diff-filter=U"],
                       capture_output=True, text=True)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


class ResolveIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.c = self._t.name
        init_repo(self.c)
        write(self.c, "MEMORY.md", "# Carte\n\n## Domaines\n- mailing\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "base")

    def tearDown(self):
        self._t.cleanup()

    def test_derived_only_conflict_auto_resolved(self):
        # branche A : ajoute fait-a + un index/mailing.md "version A"
        git(self.c, "checkout", "-qb", "a")
        write(self.c, "mailing/fait-a.md", FACT % ("fait-a", "premier fait", "corps a"))
        write(self.c, "index/mailing.md", "- `fait-a` — premier fait · project\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "a")
        # branche B (depuis base) : ajoute fait-b + un index/mailing.md "version B"
        git(self.c, "checkout", "-q", "main")
        git(self.c, "checkout", "-qb", "b")
        write(self.c, "mailing/fait-b.md", FACT % ("fait-b", "second fait", "corps b"))
        write(self.c, "index/mailing.md", "- `fait-b` — second fait · project\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "b")
        # fusion -> conflit sur index/mailing.md uniquement (faits = fichiers séparés)
        git(self.c, "checkout", "-q", "a")
        subprocess.run(["git", "-C", self.c, "merge", "--no-ff", "-m", "merge", "b"],
                       capture_output=True)
        self.assertIn("index/mailing.md", conflicted(self.c))
        # l'outil régénère index/mailing.md depuis les deux faits
        r = run_script(self.c)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(conflicted(self.c), [])     # plus aucun chemin non-mergé
        idx = open(os.path.join(self.c, "index", "mailing.md"), encoding="utf-8").read()
        self.assertIn("fait-a", idx)
        self.assertIn("fait-b", idx)

    def test_real_fact_conflict_needs_human(self):
        # base : un fait partagé
        write(self.c, "mailing/partage.md", FACT % ("partage", "fait partagé", "version base"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "fact")
        # A et B modifient le MÊME fait différemment
        git(self.c, "checkout", "-qb", "va")
        write(self.c, "mailing/partage.md", FACT % ("partage", "fait partagé", "version A"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "va")
        git(self.c, "checkout", "-q", "main")
        git(self.c, "checkout", "-qb", "vb")
        write(self.c, "mailing/partage.md", FACT % ("partage", "fait partagé", "version B"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "vb")
        git(self.c, "checkout", "-q", "va")
        subprocess.run(["git", "-C", self.c, "merge", "--no-ff", "-m", "merge", "vb"],
                       capture_output=True)
        self.assertIn("mailing/partage.md", conflicted(self.c))
        # l'outil signale le fait, ne stage rien, sort 1
        r = run_script(self.c)
        self.assertEqual(r.returncode, 1)
        self.assertIn("partage.md", r.stdout)
        self.assertIn("mailing/partage.md", conflicted(self.c))   # toujours en conflit
```

- [ ] **Step 2 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_resolve_conflicts -v`
Expected : PASS (5 unitaires + 2 intégration = 7).

- [ ] **Step 3 : Commit**

```bash
git add tests/test_resolve_conflicts.py
git commit -m "test(conflicts): intégration git — conflit dérivé auto-résolu, conflit de fait humain

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : Intégration `/memory-review` + governance

**Files:**
- Modify: `skills/memory-review/SKILL.md`
- Modify: `skills/memory-promote/references/governance.md`

- [ ] **Step 1 : `/memory-review` — gestion de conflit à l'étape de fusion**

Dans `skills/memory-review/SKILL.md`, dans l'étape `4. Décision` → sous-puce « **Approuver et
fusionner** », le bloc bash actuel est :

```bash
     git -C "<clone>" checkout main
     git -C "<clone>" pull --ff-only origin main
     git -C "<clone>" merge --no-ff origin/<branche> -m "memory: <résumé>"
     git -C "<clone>" push origin main
     git -C "<clone>" push origin --delete <branche>     # nettoyage de la branche
```

Juste **après ce bloc bash** (avant la sous-puce « **Refuser / demander des corrections** »),
insérer ce paragraphe :

```markdown
     **Si `git merge` signale un conflit**, ne pas pousser. Lancer l'outil de résolution :

     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/resolve-conflicts.py "<clone>"
     ```

     - **Sortie 0** : seuls des `index/**` (dérivés) étaient en conflit ; ils ont été régénérés et
       stagés. Finaliser : `git -C "<clone>" commit -m "memory: <résumé>"` puis
       `git -C "<clone>" push origin main`.
     - **Sortie 1** : de vrais conflits restent (faits à arbitrer, ou carte `MEMORY.md`). Les
       résoudre à la main (choisir la bonne version d'un fait ; garder l'union des domaines dans la
       carte sans doublon), `git -C "<clone>" add <fichier>`, puis **relancer** l'outil.
     - **Échappatoire** : `git -C "<clone>" merge --abort` annule la fusion sans rien pousser ; la
       branche `promote/*` reste intacte pour réessayer.
```

- [ ] **Step 2 : Vérifier l'insertion**

Run : `grep -n "resolve-conflicts\|merge --abort" skills/memory-review/SKILL.md`
Expected : au moins une ligne pour `resolve-conflicts.py` et une pour `merge --abort`.

- [ ] **Step 3 : governance.md — section « Conflits »**

Dans `skills/memory-promote/references/governance.md`, à la **fin du fichier**, ajouter :

```markdown
## Conflits (à la fusion)

`index/**` est **dérivé** (régénéré par `reshard.py`) ; `<domaine>/<fait>.md` est la **source** ;
`MEMORY.md` est la **carte curée**. Un conflit de merge se traite donc selon le fichier :

- **`index/<domaine>.md`** (cas fréquent : deux ajouts de faits au même domaine) → conflit
  **dérivé**, résolu automatiquement en régénérant : `scripts/resolve-conflicts.py` lance reshard
  et stage les index.
- **`<domaine>/<fait>.md`** (deux éditions du même fait) → **humain** : choisir la bonne version
  (véracité), `git add`.
- **`MEMORY.md`** (deux nouveaux domaines) → **humain** : garder l'union des domaines, vérifier
  qu'aucun ne double un domaine proche.

**Flux en deux temps** : `resolve-conflicts.py` ne régénère les index que lorsqu'il ne reste
**aucun** conflit de fait/carte (reshard ne doit jamais lire de marqueurs). Tant qu'il en reste, il
les liste et sort en code 1 ; après résolution humaine + `git add`, relancer (code 0). En dernier
recours, `git merge --abort` annule la fusion sans rien pousser.
```

- [ ] **Step 4 : Vérifier**

Run : `grep -c "Conflits\|resolve-conflicts" skills/memory-promote/references/governance.md`
Expected : ≥ 2.

- [ ] **Step 5 : Commit**

```bash
git add skills/memory-review/SKILL.md skills/memory-promote/references/governance.md
git commit -m "docs(conflicts): procédure de conflit dans /memory-review + governance

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Doc `ARCHITECTURE.md` §14

**Files:**
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1 : Ajouter la section §14**

Dans `docs/ARCHITECTURE.md`, à la **fin du fichier** (après §13), ajouter :

```markdown
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
```

- [ ] **Step 2 : Vérifier**

Run : `grep -n "## 14" docs/ARCHITECTURE.md && grep -c "resolve-conflicts" docs/ARCHITECTURE.md`
Expected : `## 14` présent ; `resolve-conflicts` ≥ 1.

- [ ] **Step 3 : Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs(conflicts): ARCHITECTURE §14 — résolution de conflits du vault

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Vérification

- [ ] **Step 1 : Suite complète (non-régression)**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : OK — tous les tests passent (existants + 7 de `test_resolve_conflicts`).

- [ ] **Step 2 : Fumée bout-en-bout (conflit dérivé réel)**

Run :
```bash
TMP=$(mktemp -d); C="$TMP/clone"; mkdir -p "$C"
git -C "$C" init -q && git -C "$C" config user.email t@t && git -C "$C" config user.name t
printf '# Carte\n\n## Domaines\n- mailing\n' > "$C/MEMORY.md"
git -C "$C" add -A && git -C "$C" commit -qm base
git -C "$C" checkout -qb a
mkdir -p "$C/mailing" "$C/index"
printf -- '---\nname: fait-a\ndescription: premier fait du domaine\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nA\n' > "$C/mailing/fait-a.md"
printf -- '- `fait-a` — premier fait du domaine · project\n' > "$C/index/mailing.md"
git -C "$C" add -A && git -C "$C" commit -qm a
git -C "$C" checkout -q main && git -C "$C" checkout -qb b
mkdir -p "$C/mailing" "$C/index"
printf -- '---\nname: fait-b\ndescription: second fait du domaine\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nB\n' > "$C/mailing/fait-b.md"
printf -- '- `fait-b` — second fait du domaine · project\n' > "$C/index/mailing.md"
git -C "$C" add -A && git -C "$C" commit -qm b
git -C "$C" checkout -q a
git -C "$C" merge --no-ff -m merge b >/dev/null 2>&1
echo "=== conflits avant ===" ; git -C "$C" diff --name-only --diff-filter=U
echo "=== outil ===" ; python3 scripts/resolve-conflicts.py "$C"
echo "=== conflits après ===" ; git -C "$C" diff --name-only --diff-filter=U
echo "=== index régénéré ===" ; cat "$C/index/mailing.md"
rm -rf "$TMP"
```
Expected : conflit sur `index/mailing.md` avant ; l'outil affiche « ✅ 1 index régénéré(s)… » ; aucun
conflit après ; l'index final liste `fait-a` **et** `fait-b`.

- [ ] **Step 3 : Relecture**

Vérifier de visu : `resolve-conflicts.py` n'utilise que la stdlib ; en cas A (faits/carte) il ne
stage **rien** et sort 1 ; reshard n'est lancé qu'au cas B ; la doc `/memory-review`, governance et
§14 sont cohérentes (flux en deux temps, `merge --abort`).

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| `classify_conflicts(paths) -> {derived, map, facts, other}` | Task 1 + unitaires |
| CLI cas A (humain, sortie 1) / cas B (reshard+stage, sortie 0) / cas C (rien, 0) | Task 1 (`main`) |
| Erreur reshard → sortie ≠ 0, pas de staging | Task 1 (`main`, branche `r.returncode != 0`) |
| `index/**` dérivé auto ; faits + `MEMORY.md` humain | Task 1 (`classify_conflicts`) + intégration |
| Flux en deux temps (reshard jamais sur marqueurs) | Task 1 (cas A ne stage rien) + intégration |
| Intégration `/memory-review` + `merge --abort` | Task 3 |
| Section « Conflits » governance | Task 3 |
| ARCHITECTURE §14 | Task 4 |
| Tests unitaires + intégration git | Task 1, Task 2 |
| Vérification (suite + fumée bout-en-bout) | Task 5 |

**Placeholders :** aucun — `resolve-conflicts.py`, les deux blocs de `test_resolve_conflicts.py`, les
insertions doc sont fournis intégralement.

**Cohérence des types/signatures :** `classify_conflicts(paths) -> dict` aux clés
`{"derived","map","facts","other"}` — mêmes clés dans le code, les tests unitaires et `main`. `main(clone) -> int`
(codes 0/1) cohérent avec la CLI (`sys.exit(main(...))`) et les assertions d'intégration
(`returncode`). reshard lancé via `sys.executable` (même interpréteur). Les helpers de test
(`init_repo`, `git`, `write`) calquent `tests/test_hooks.py`.

**Note d'intégration :** les tests d'intégration fabriquent de vrais conflits git (add/add sur
`index/mailing.md`, modify/modify sur un fait) ; ils dépendent de `reshard.py` (présent) qui régénère
`index/mailing.md` à partir des deux faits fusionnés et préserve `MEMORY.md`.
