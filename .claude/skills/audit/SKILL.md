---
name: audit
description: Commande d'audit TAQINOR OS v3 (méthode docs/audits/METHODE.md, registre docs/audits/unites.yml, décisions docs/audits/decisions.yml). Invoquer quand Reda tape « audit first », « audit next », « continue audit », « loop audit », « audit status », « audit <mot> [L1|L2|L3] [précisions] » (totaux, facturation, calepinage, acquisition, lead, crm, sécurité, pdf, moteur, chantiers, stock, documents, parametres, générateur, devis, deploy, sav, analyse, performance), « audit parcours <PA1-PA7|PF1-PF3> » ou « vérifie <GROUPE> ». Audite UNE unité ou UN parcours (preuve exécutée par sonde, tâches v3 aux clauses calculées, routées chez le propriétaire des fichiers), met à jour le registre et livre UNE PR docs-only. Ne construit jamais rien.
---

# Audit — mode d'emploi (v3, 2026-10-09)

**Lire `docs/audits/METHODE.md` avant tout run** ; en cas de doute il fait foi, et les SCRIPTS font foi sur le mécanique.
Le registre `docs/audits/unites.yml` se lit TOUJOURS sur `origin/main` après `git fetch origin --prune`. Un audit ne
construit rien : dossier (`docs/audits/GABARIT_DOSSIER.md`) + sondes + tâches v3 + décisions + registre + rapport, UNE PR.

## 1. Déclencheurs
| Reda tape | Action |
|---|---|
| `audit first` | unité de rang 1 |
| `audit next` | d'abord tout `vérifie <G>` dû (`scripts/audit_registre.py --du`), puis plus petit rang « à auditer » non réclamé |
| `continue audit` | claim vivant de plus petit rang, repris au point de contrôle (tableau vérifié + sondes poussés) ; aucun → `audit next` |
| `loop audit` | `/loop` sans intervalle : chaque itération = `vérifie` dû sinon `audit next` ; une PR par itération, sans attendre le merge ; PR rouge réparée d'abord |
| `audit status` | `python scripts/audit_registre.py status` (lecture seule ; tant qu'il manque : tableau à la main, statut = dossier / % cochées / acceptation / vérifie) |
| `audit <mot> [Ln] [précisions]` | l'unité nommée, hors ordre ; les précisions priment (périmètre, `anon`, persona, décision) |
| `audit parcours <PA>` | un parcours de METHODE §D.1 (PA1 contact→visite … PA7 monitoring ; PF1-PF3 plateformes) |
| `vérifie <G>` | contre-visite d'un groupe (§5) |
Mots v1 (`leads`, `fiche`, `cadence`, `clients`, `visites`, `ged`, `portail`) → l'unité v2 correspondante (acquisition / lead / documents) ;
mot inconnu → `AskUserQuestion`, option recommandée d'abord.

## 2. Procédure (ce qu'aucun script n'impose encore)
1. `git fetch origin --prune` ; `python scripts/audit_registre.py claim <id>` (refus = unité prise → suivante ; tant qu'il
   manque : branche `audit-<id>` + commit vide poussé). `check_parked_apps.py`. Si un `vérifie` est dû, il passe d'abord.
2. **Dédoublonner SOI-MÊME** (grep des tâches ouvertes de tous les plans + `git log origin/main`) ; charte = §1 du gabarit,
   « NE PAS REFAIRE » inclus ; questions de PÉRIMÈTRE seulement.
3. Niveau → recette METHODE §B.3 ; coût estimé annoncé en une ligne ; chaque agent avec `model:` + effort + le bloc de
   grounding verbatim de CLAUDE.md ; UN workflow fan-out même répertoire, jamais de worktree pour lire.
4. Pile locale (`scripts/pile_locale.ps1`, sinon `migrate` + rebuild du front + `seed_demo` + `seed_demo_company`) ; live
   par l'orchestrateur seul : UNE transaction réelle du parcours, oracles qa-explorer 1-10, étapes négatives aux passages
   de main ; prod en lecture seule, orchestrateur seul, dit dans le chat (METHODE §A.2).
5. Vérificateurs frais : une sonde par constat argent / chiffre client / persistance / multi-société / parcours, écrite au
   dépôt `docs/audits/sondes/<G>/C-<G>-<NNN>.py`, jouée par `scripts/sonde.py` en transaction annulée (mail en mémoire,
   Celery coupé) ; verdict REPRO / STATIQUE / RÉFUTÉ ; STATIQUE interdit en S1-S2 sur critères à sonde. Point de contrôle poussé.
6. 0 réfuté sur les S1 ⇒ seconde lentille sur les S1 seuls (METHODE §B.5) ; fraîcheur `git diff <base>..origin/main`.
7. Critique de complétude (L2 opus / high ; L3 Fable / high, exactement 1) ; chaque trou est sondé avant d'entrer au tableau.
8. Décisions : UN lot `AskUserQuestion` → `docs/audits/decisions.yml` AVANT la rédaction ; sans réponse → GATED sur le D-id.
9. Rédaction : rédacteurs opus / high (plages d'ID disjointes) + `scripts/audit_tache.py` (sinon les greps équivalents, résultats
   collés dans la tâche) + éditeur sonnet ; routage `check_ownership.py --owner-of` ; multi-propriétaires → scindée, contrat d'abord ;
   `check_audit_dossier.py`, `check_taches_cablage.py` (FORME 5 v3), `plan_lanes.py --check`, `ci_guards.py stage-names` VERTS.
   Écart à la méthode → METHODE amendée dans la même PR.
10. Registre (`groupe`, `plans_alimentes`, `pr`, `date`, `dossier`) ; `git fetch origin` puis push ; PR docs-only
    `gh pr merge --auto --merge --delete-branch` ; rapport = §9 du dossier + `work on the plan audit_<unité>` par fichier.

## 3. Modèles (CLAUDE.md : jamais d'héritage du modèle de session ; `@model` obligatoire sur chaque tâche v3)
| Rôle | Modèle / effort |
|---|---|
| Orchestrateur (charte, live, prod, fusion, décisions, PR) | modèle de session |
| Scouts (détecteurs, inventaires) | haiku / low |
| Lanes de jugement | sonnet / medium ; sonnet / high calcul technique ; opus / high argent, règle #4, auth, `core`, événements |
| Vérificateurs, seconde lentille | opus / high, contexte frais, jamais l'auteur |
| Critique de complétude | L2 opus / high ; L3 Fable / high ×1 (ligne DONE LOG) |
| Rédacteurs / éditeur | opus / high (≤ 3) / sonnet / medium |

## 4. `loop audit`
Skill `loop` sans intervalle ; itération = `vérifie` dû sinon `audit next` complet → PR auto-merge → suivante sans attendre
le merge (le claim de la précédente reste vivant jusqu'au merge). Une décision non tranchée devient une entrée `ouverte` +
tâches GATED ; l'audit continue. Arrêt : plus rien de dû ni « à auditer », ou Reda dit stop.

## 5. `vérifie <GROUPE>` (METHODE §C.4)
Dû à ≥ 50 % puis ≥ 95 % de tâches cochées. Sur `origin/main` : échantillon = toutes P0 / S1 + 25 % du reste (min 8, max 48,
graine = SHA) ; vérificateurs frais opus / high : texte ↔ commit(s) ↔ test nommé ↔ 7 leçons de `lecons-construction-qjr5.md`,
sondes rejouées, verdict ok / partiel / non-fait / faux / régression / déjà-présent + cause ; UNE critique Fable seulement si
des S1 subsistent. Écarts confirmés = tâches v3 sous `### <G> — ÉCARTS vérifie <date> · format v3` dans le fichier du
PROPRIÉTAIRE (numérotation du groupe continuée ; jamais `ERROR_PLAN.md`). PR docs-only.

## 6. Interdits
Jamais de constat S1-S2 sans sonde exécutée sur les critères à sonde ; jamais l'auteur comme vérificateur ; jamais plus de
lanes ni de lentilles sur tous les constats ; jamais un id de lane, « FABLE § », « lot W » ou un chemin de scratchpad dans un
dossier ; jamais une tâche « Si (a)/(b) », un `n/a` nu, une ancre `fichier:ligne` seule, un nouveau fichier de test par tâche
quand le module en a un ; jamais une tâche chez un autre propriétaire ni la réécriture d'un autre groupe ; TRANSVERSE n'accepte
que les déplacements SPL `(@atomique: …)` et ne tourne jamais avec un plan dont il touche un propriétaire ; jamais la prod en
écriture, `seed_demo --force`, un envoi réel, un deploy.
