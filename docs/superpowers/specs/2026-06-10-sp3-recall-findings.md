# SP3 — Constats : validation du rappel

**Date :** 2026-06-10
**Type :** rapport d'investigation (pas un build)
**Vault testé :** `negocian-memory` (9 faits réels, dont 6 partageables).

## Résumé exécutif

- **L'outil de récupération marche très bien** sur du contenu réel : `search_memory` (vectoriel FR)
  sort le **bon fait en #1 à 6/6** (100 %) sur des requêtes paraphrasées.
- **Le câblage est en place** : symlink mémoire → vault, `MEMORY.md` chargé au démarrage, serveur MCP
  `search_memory` déclaré.
- **Le maillon non garanti est comportemental** : aucun des deux chemins de rappel n'est *automatique*
  — ils dépendent tous deux de **Claude qui décide d'engager** (suivre la carte, ou appeler l'outil).
  Le contenu des faits n'est **pas** poussé en contexte au démarrage (seule la **carte** l'est).
- **Verdict** : la valeur *peut* se produire et la qualité est là ; reste à **mesurer en session
  réelle** si Claude engage le rappel (Sonde 3, manuelle).

## Sonde 1 — Qualité de récupération (vrai vault, automatable)

6 requêtes **paraphrasées en français** (peu de mots en commun → 100 % sémantique, le grep ne matche
pas), modèle multilingue FR, `k=6` :

| Rang du bon fait | Fait attendu | Requête |
|---|---|---|
| **#1** | `mailing/audit.md` | « état, bugs et dette du système d'envoi de courriels » |
| **#1** | `ui/ux-audit.md` | « qualité de l'interface et du design system de l'application » |
| **#1** | `ecommerce/tax-forms.md` | « comment sont gérés les formulaires de taxes de la boutique » |
| **#1** | `entites-dynamiques/permissions.md` | « droits d'accès et autorisations sur les entités étendues » |
| **#1** | `entites-dynamiques/champs-rendu-vue.md` | « affichage des champs personnalisés placés dans une page » |
| **#1** | `shared-memory-plugin.md` | « l'outil de mémoire d'équipe partagée pour l'assistant de code » |

**top-1 = 6/6 (100 %) · top-3 = 6/6 (100 %) · `vector_inactive=False`.** Meilleur que le synthétique
(les vrais faits sont sémantiquement distincts). **Conclusion : quand l'outil est appelé, il rend le
bon fait.** La récupération n'est pas le problème.

## Sonde 2 — Diagnostic du câblage : rappel natif vs sharding

**Ce qui est vérifié en place :**
- Symlink `~/.claude/projects/-var-www-newnegocian-workspace/memory` → clone du vault ✓
- `MEMORY.md` (21 lignes) chargé au démarrage : **carte des domaines avec descriptions**
  (« mailing — emails, MailingBundle (audit) »), section « Général », et **« Patterns & Conventions »**.
- Serveur MCP `search_memory` déclaré dans `.mcp.json` ✓ (et fonctionnel, cf. Sonde 1).

**Le mécanisme réel :**
- Au démarrage, le natif charge **la carte** (`MEMORY.md`) — pas le **contenu** des faits.
- Le contenu d'un fait est à **deux sauts** : `MEMORY.md` → `index/<domaine>.md` → `<domaine>/<fait>.md`.
- Il existe donc **deux chemins de rappel**, tous deux **décidés par Claude** :
  1. **Natif, piloté par la carte** : `MEMORY.md` indique les domaines + une description courte → si
     pertinent, Claude **suit le pointeur** jusqu'au fait. Dépend de Claude qui remarque et suit.
  2. **`search_memory` (MCP)** : Claude **appelle l'outil** → obtient le bon fait (prouvé Sonde 1).
     Dépend de Claude qui décide d'appeler.

**Le risque (confirmé) :** le sharding a borné le coût **tokens de démarrage** au prix de la
**visibilité directe du contenu des faits** au rappel. Aucun fait n'est poussé en contexte
automatiquement ; le rappel repose sur l'**initiative de Claude** (suivre la carte ou appeler
l'outil). Donc la **qualité** est acquise, mais le **déclenchement** ne l'est pas — et c'est
exactement ce que le sharding a déplacé.

**Levier le moins cher identifié :** la **carte `MEMORY.md`** est le déclencheur du rappel natif —
ses **descriptions de domaines doivent rester riches et discriminantes** (un bon « sommaire » incite
Claude à creuser le bon domaine). C'est déjà le cas ici et la convention pousse dans ce sens.

## Sonde 3 — Protocole comportemental (à lancer manuellement)

À exécuter dans **`newnegocian-workspace`** (projet réellement branché), session interactive normale.

**Scénarios** (un fait connu *devrait* être rappelé sans qu'on le demande explicitement) :
1. Demander une tâche **liée au MailingBundle** (ex. « ajoute un template d'email transactionnel »)
   → le fait `mailing/audit.md` (bugs/dette connus) devrait remonter.
2. Tâche sur les **permissions d'entités dynamiques** → `entites-dynamiques/permissions.md`.
3. Tâche sur un **formulaire de taxe e-commerce** → `ecommerce/tax-forms.md`.
4. Tâche **UI/design system** → `ui/ux-audit.md`.

**Grille d'observation** (pour chaque scénario) :
| Le fait a-t-il été rappelé ? | Par quel chemin ? |
|---|---|
| Oui, spontanément | natif (carte→fait) / `search_memory` / lecture directe |
| Oui, mais seulement après une question explicite | — |
| Non | — |

**Critère de succès** proposé : rappel spontané (sans question explicite) sur **≥ 3/4** scénarios.
Si < 3/4 → le déclenchement est le vrai goulot, et on traite les correctifs ci-dessous.

## Correctifs recommandés (priorisés — chacun = chantier potentiel)

1. **Lancer la Sonde 3 pour de vrai** (manuel) — c'est la seule inconnue restante ; tout le reste en
   découle. **Priorité 1.**
2. **Garder/renforcer les descriptions de domaines dans `MEMORY.md`** — c'est le déclencheur du
   rappel natif, le levier le moins cher. (Déjà poussé par la convention ; à surveiller à l'écriture.)
3. **Rendre explicite « quand consulter la mémoire »** — p. ex. une consigne (CLAUDE.md du projet, ou
   description d'outil) invitant Claude à consulter la mémoire en début de tâche. **À décider après
   la Sonde 3** (n'agir que si le déclenchement s'avère faible).
4. **(Spéculatif) Digest mémoire au démarrage** — étendre le hook `SessionStart` (SP1) pour injecter
   un court rappel des domaines/faits pertinents. À n'envisager que si la Sonde 3 montre un déficit
   net de déclenchement ; sinon c'est de la sur-ingénierie.

## Hors scope (rappel)

SP3 **constate**, ne corrige pas. Les correctifs 2-4 sont des chantiers ultérieurs, à n'ouvrir
qu'au vu des résultats de la Sonde 3.
