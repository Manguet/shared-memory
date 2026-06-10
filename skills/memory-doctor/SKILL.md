---
name: memory-doctor
description: This skill should be used when the user asks to "diagnostiquer la mémoire", "vérifier la recherche mémoire", "activer la recherche sémantique", "pourquoi search_memory est en grep", "memory doctor", or "/memory-doctor". It runs the prerequisites diagnostic for search_memory and proposes the missing installs (the user validates; nothing is installed without consent).
argument-hint: ""
allowed-tools: Bash, Read, AskUserQuestion
version: 0.1.0
---

# memory-doctor — Diagnostiquer la recherche mémoire et proposer les installs

Vérifie les prérequis de `search_memory` (recherche vectorielle locale) et **propose** les
correctifs manquants. **N'installe jamais rien sans l'accord** de l'utilisateur. Sans
prérequis, `search_memory` reste fonctionnel en **fallback grep** — la véracité est garantie
(le fait est toujours lu).

## Procédure

1. **Lancer le diagnostic** :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/doctor.py
   ```

2. **Présenter le rapport** ligne à ligne (OK / manquant). Pour chaque manque, montrer le
   **remède** indiqué par le doctor.

3. **Proposer les installs manquantes** — typiquement `pip install fastembed` (recherche
   sémantique). **Demander l'accord** via AskUserQuestion avant toute commande qui installe ;
   ne rien exécuter sinon. Si l'utilisateur accepte :

   ```bash
   pip install fastembed
   ```

   puis (optionnel) pré-télécharger le modèle (~90 Mo) :

   ```bash
   python3 -c "from fastembed import TextEmbedding; TextEmbedding()"
   ```

4. **Re-vérifier** : relancer `doctor.py` pour confirmer que tout est OK.

## Points d'attention

- **Pas de dégradation silencieuse** : si `search_memory` renvoie `vector_inactive: true`,
  c'est que la sémantique est inactive (fastembed absent) — le signaler et proposer ce skill.
- **Local & privé** : fastembed embedde en local (ONNX), aucun appel réseau aux faits.
- **Consentement** : Claude n'installe rien sans validation explicite de l'utilisateur.

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py`** — diagnostic structuré + remèdes.
- **`${CLAUDE_PLUGIN_ROOT}/docs/superpowers/specs/2026-06-10-v2-token-optimization-design.md`** —
  conception (Volets B & C).
