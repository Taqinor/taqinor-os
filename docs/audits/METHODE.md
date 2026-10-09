# Méthode d'audit TAQINOR OS (v3) — référence de la commande « audit »

*Version 3 du 2026-10-09, base `0e057c417`. Remplace la v2 du 02/10 (`git show 1d08a5bd9:docs/audits/METHODE.md`).
Opérationnel : `.claude/skills/audit/SKILL.md`. Registre : `docs/audits/unites.yml`. Décisions : `docs/audits/decisions.yml`.
Gabarit de dossier : `docs/audits/GABARIT_DOSSIER.md`. Les SCRIPTS font foi sur tout ce qui est mécanique ; ce texte ne
décrit que le jugement. Un script marqué « (AMET, à construire) » est une tâche du groupe AMET de
`docs/plans/PLAN_AUDIT_DEPLOY.md` ; tant qu'il manque, l'orchestrateur applique la règle à la main et le dit.*

**Règle d'entretien.** Un écart à cette méthode constaté dans un dossier est amendé ICI, dans la même PR, ou déclaré
ponctuel avec sa raison (§8 du dossier). La v2 n'a jamais été amendée en 19 runs malgré ≥ 15 déviations : c'est la v2 qui
avait tort. Plafond : 450 lignes (`check_audit_dossier.py --methode`, AMET, à construire).

**Pourquoi une v3 (mesuré du 02 au 09/10/2026 sur 19 unités et ≈ 1 100 tâches construites).** Sur 48 tâches cochées
re-vérifiées, 79 % sont justes sur `main` mais **48 % seulement l'étaient en un coup** ; 2 régressions d'écran ont été
mergées sous CI verte (ATOT2, ATOT9). **0 des 19 tâches d'acceptation live a été jouée**, 0 `vérifie` n'a tourné, le registre
n'a jamais quitté `audité`. Les clauses des tâches étaient AFFIRMÉES, jamais calculées (Appelants / Jumeaux / Listes figées
faux dans ≈ 20 tâches sur 48 ; 75 réparations CI « test périmé » ; 53 % des ancres `fichier:ligne` dérivées). Le code a
grossi de **17 % en 7 jours** (+1 162 fichiers de test, 65 fichiers ≥ 2 000 lignes, 97 groupes de fonctions identiques).
32 % des tâches ont été routées hors de leur unité et TRANSVERSE est devenu un verrou global (une lane de 285 tâches).
Aucun critère ne voyait les PARCOURS : 27 étapes automatiques sur 81, 13 portes de création de lead, 8 écrasements de saisie
manuelle. Dossier complet : `docs/audits/2026-10-09-methode.md`.

---

## §0 Commandes et progression

| Commande | Effet |
|---|---|
| `audit first` | audite l'unité de rang 1 du registre |
| `audit next` | **d'abord tout `vérifie <G>` dû** (§C.4), puis la première unité « à auditer » non réclamée |
| `audit <mot> [L1\|L2\|L3] [précisions]` | audite une unité précise (mots : `unites.yml`, champ `declencheur`) ; les précisions priment |
| `audit parcours <PA>` | audite UN parcours de bout en bout (§D.1 : PA1-PA7, PF1-PF3) |
| `continue audit` | reprend le claim vivant de plus petit rang au point de contrôle (§B.5) ; aucun → `audit next` |
| `loop audit` | `/loop` auto-rythmé : chaque itération = `vérifie` dû sinon `audit next` ; une PR par itération, sans attendre le merge |
| `audit status` | sortie de `scripts/audit_registre.py status` (AMET, à construire) : rang, mot, statut CALCULÉ, claim, groupe, plans alimentés |
| `vérifie <G>` | contre-visite d'un groupe construit (§C.4) ; déclenché à la main ou **dû** (≥ 50 % puis ≥ 95 % des tâches cochées) |

Toute décision à prendre passe par UN lot `AskUserQuestion` (option recommandée en premier) AVANT la rédaction des tâches
(§B.6), jamais par une liste en prose ; la réponse est écrite dans `docs/audits/decisions.yml`.

---

## §A Définition

### A.1 Ce que produit un audit
1. **Un dossier** `docs/audits/<AAAA-MM-JJ>-<mot>.md` au gabarit `GABARIT_DOSSIER.md` (marqueur `dossier-v3`), relu par
   `check_audit_dossier.py` (AMET, à construire) : charte, couverture (lus / NON lus), constats (une ligne par cause racine,
   ancre `fichier::symbole`, sonde), réfutés, non-risques, décisions, optionnel, limites, coût.
2. **Des sondes au dépôt** `docs/audits/sondes/<G>/C-<G>-<NNN>.py` (§B.5) : chaque constat argent / chiffre client /
   persistance / multi-société est prouvé par une sonde exécutable et rejouable.
3. **Des tâches v3 routées par propriétaire** (§C.2, §D.3), chacune sur UNE ligne, clauses calculées, dans
   `docs/plans/PLAN_AUDIT_<UNITE>.md` ; multi-propriétaires → scindées (contrat d'abord), jamais TRANSVERSE sauf
   déplacement SPL atomique.
4. **Les décisions** dans `docs/audits/decisions.yml` (id, question, options, réponse, tâches dépendantes).
5. **Le registre** : `audit_registre.py` calcule les statuts ; l'audit n'écrit que `groupe`, `plans_alimentes`, `pr`, `date`,
   `dossier`.
6. **Un rapport** en français : vérifiés / réfutés / renvoyés, couverture, non couvert, décisions, coût, commande de build.
7. **UNE PR docs-only** en auto-merge depuis la branche de claim `audit-<id>`, `ci_guards.py stage-names` vert en local.

### A.2 Ce qu'un audit ne produit PAS, et la règle PROD
- Aucun code, correctif, migration ni dépendance (`work on the plan audit_<unité>` construit) ; aucun deploy ; jamais
  `seed_demo --force` ; jamais d'envoi réel (le conteneur local peut porter une VRAIE clé SendGrid : toute sonde force un
  backend mail en mémoire et neutralise Celery) ; pas de nouveau nom d'étape (règle #2) ni de chemin PDF devis (règle #4).
- **Production : lecture seule, orchestrateur seul** (accord `docs/claude-memory/prod-read-access.md`) : `manage.py shell`
  en transaction annulée, requêtes de lecture seulement, pour une prévalence, un réglage ou un compte ; jamais une requête
  HTTP (un GET peut écrire), jamais une commande qui écrit, migre ou redémarre ; le dossier ne porte que des comptes agrégés.
  Un défaut ACTIF en prod = **INCIDENT PROD** : première ligne du rapport, tâche P0 en M1 chez le propriétaire, fichier
  `docs/claude-memory/` si l'état persiste ; jamais de réparation dans l'audit (`reconfirm-client-visible-repairs.md`).
- Pas de constat S1-S2 sans sonde exécutée sur les critères à sonde obligatoire (§A.4) ; pas de « Nit » transformé en tâche.

### A.3 Niveaux : voir les recettes mesurées en §B.3. L'auto-pick go-deep (STAKES × BREADTH × UNCERTAINTY) relève le niveau
du registre, ne l'abaisse jamais sous L2 pour un chiffre client ; Reda impose. Escalade annoncée en une ligne.

### A.4 Les critères (liste fermée ; un constat sans critère est OPTIONNEL ; IDs jamais renumérotés)

| ID | Critère | Preuve exigée | Détecteur / garde existant | Sonde obligatoire en S1-S2 ? |
|---|---|---|---|---|
| C1 | Exactitude de ce que le client voit (chiffres, textes, langue, version) | parité écran = serveur = PDF / page publique sur le MÊME enregistrement ; recalcul indépendant | `test_figures_parite.py`, `figures-parite.spec.js`, `manage.py audit_coherence --no-persist` | oui |
| C2 | Modifiable à chaque étape, saisie manuelle jamais écrasée | enregistrer → rouvrir → enregistrer sans toucher ⇒ objet identique ; chatter old→new | `LeadActivity`, tests comportementaux | oui |
| C3 | Une fonction par geste (aucun jumeau écran / serveur / PDF / page publique / apps/web) | inventaire des implémentations avec survivant nommé | `check_duplicats_litteraux.py`, `check_calepinage_actions_consommees.py` | non |
| C4 | Code propre : zéro code mort, résidu parqué, dépendance malsaine | preuve grep « zéro appelant » ; import-linter | `check_ecrans_atteignables.py`, `check_services_appeles.py`, `lint-imports`, `check_parked_apps.py`, `event_coverage.py` | non |
| C5 | Étanchéité multi-société et autorisations (ASVS 8.2.2, 8.2.3, 8.4.1) | rejeu à DEUX comptes, substitution de références ; 404 jamais 403 | `tests/test_tenant_sweep.py`, `check_tenant_isolation.py`, `check_viewset_model_scope.py` | oui |
| C6 | Contrôles d'entrée : validation, anti-doublon, saisie jamais rejetée ni arrondie | tests négatifs scriptés ; `noValidate`, `step="any"` | `apps/ventes/utils/references.py` (jamais count()+1) | non |
| C7 | Contrôles de traitement : UN calcul, rapprochement inter-modules, override tracé | rapprochement lecture seule ; recalcul HT→TVA→TTC | `audit_coherence` (22 règles) | oui |
| C8 | Contrôles de sortie : destinataires autorisés, `prix_achat`/marge jamais côté client | oracles qa-explorer 6-7 | `check_portail_surfaces.py` | oui |
| C9 | Données maîtres : une seule lecture par réglage, version figée sur un document envoyé / signé | table réglage → lecteurs ; document signé insensible au réglage | journal old→new `Produit`, `CompanyProfile` | oui |
| C10 | Coutures : contrat partagé, émetteur ET abonné vivants, tous les appelants, source réelle | contract_samples chargés des deux côtés ; grep des appelants ; aucun mock interne | `check_api_shapes.py`, `check_api_contract.py`, `check_tests_source_regex.py` | non |
| C11 | Règles maison #1-#5 | — | `check_stages.py`, `ci_guards.py stage-names`, `check_odoo_writes.py` | non |
| C12 | Déployable (CI verte ≠ déployable) | `docker compose up -d --build frontend` + `migrate` AVANT le live | `check_dockerfile_context.mjs` | non |
| C13 | Fiabilité d'exécution | aucun 4xx/5xx légitime, `console.error`, dialogue natif | oracles qa-explorer 1-4, 8 | non |
| C14 | Performance (L3 ou PF3) | `assertNumQueries`, N+1 mesuré | `check_query_budgets.py` | non |
| C15 | **Parcours** : chaque étape a UN déclencheur, UNE fonction d'entrée, UN point de contrôle éditable, UNE règle aval déclarée | table de parcours (§D.1) + rejeu | `check_parcours.py`, `rejouer_parcours.py` (AMET, à construire) | oui |
| C16 | **Provenance** : UN marqueur « saisi par un humain » respecté par tout écrivain automatique | tout écrivain auto passe par `ecrire_si_libre` ; sonde « saisir, automatiser, relire » | primitive `apps/records/provenance.py` (AMET, à construire) | oui |
| C17 | **Compensation** : chaque effet automatique déclare et teste ce qui arrive quand sa cause est corrigée, annulée, rouverte | modèle `devis_acceptation_annulee` ; test par effet | `event_coverage.py` | oui |
| C18 | **État visible** : aucun état de parcours en mémoire d'écran, JSON sans écran, drapeau sans réglage | grep des drapeaux → écran | — | non |
| C19 | **Bout en bout** : un rejeu live par parcours sur UN enregistrement à travers ses unités | enregistrement d'acceptation (§C.4) | `check_acceptation.py` (AMET, à construire) | oui |
| C20 | **Code net et portes** : une porte par geste ; un fichier ≥ 2 000 l. ne grossit pas ; fonction neuve ≤ 60 l. logiques ; 0 fichier de test par tâche ; 0 garde hors famille ; baselines qui ne font que rétrécir, jamais par numéro de ligne | diff seul, aucune baseline | `check_forme_code.py`, `check_test_placement.py` (AMET, à construire) | non |

Un constat porte **exactement un** critère ; une cause racine = UN constat avec N emplacements. Un critère sans constat sur
10 runs consécutifs est retiré (compte tenu par le lint). Les C15-C20 s'appliquent dans TOUT audit comme lentilles (§D.1).

---

## §B Déroulé

### B.0 Préconditions (orchestrateur)
`git fetch origin --prune` ; registre lu sur `origin/main` ; claim `audit_registre.py claim <id>` (§D.5) ; `check_parked_apps.py`
(les apps parquées sont hors périmètre sauf « code MVP qui référence une parquée ») ; **dédoublonnage AUTORITAIRE par
l'orchestrateur** (grep des tâches ouvertes de tous les plans + `git log origin/main` ; un scout ne fait qu'indiquer — 3 sorties
de scout étaient fausses) ; pile montée par `scripts/pile_locale.ps1` (AMET, à construire : `migrate`, rebuild du front,
`seed_demo`, `seed_demo_company`) à tout niveau dès qu'une étape H×H est jouée ; compte démo par étape H×H.

### B.1 Charte (avant tout constat) — §1 du gabarit
SHA, périmètre possédé / lu, niveau justifié, données (`demo` ; `anon` seulement si une étape H×H n'a aucune donnée démo ET
que la lecture prod ne suffit pas ; sinon « non requis : raison »), critères retenus, étapes `P<n>.<m>` (ou les étapes du
parcours), **NE PAS REFAIRE** (ids ouverts ou cochés qui couvrent déjà le terrain), non-objectifs. Questions fondateur ici
seulement si elles bornent le PÉRIMÈTRE ; les autres attendent §B.6.

### B.2 Spécification
≤ 8 scénarios H×H *stimulus → réponse → mesure* ; détecteurs à lancer (colonne de §A.4) ; seuils S1 argent faux / perte /
fuite / chiffre client faux · S2 saisie effacée, geste cassé sans contournement · S3 contournement · S4 cosmétique (optionnel).
Table « saisie → consommateurs » et chaîne 1:N seulement pour argent / PDF ; sinon la table du parcours (§D.1).

### B.3 Rôles, modèles et recettes (jamais d'héritage du modèle de session ; grounding verbatim de CLAUDE.md dans chaque prompt)

| Rôle | Modèle / effort | Nombre | Exécute |
|---|---|---|---|
| Orchestrateur | modèle de session | 1 | charte, dédoublonnage, pile, live, prod lecture seule, fusion par cause racine, C-id définitifs, gravité, P0-P3, décisions, PR |
| Scout détecteurs | haiku / low | 1-2 | détecteurs (commande + verdict), inventaires |
| Lane de jugement | sonnet / medium (défaut) ; sonnet / high calcul technique ; **opus / high** argent, règle #4, auth / multi-société, `core`, événements inter-apps | une par surface, ≤ 9 | lecture complète + constats bruts + manifeste lu / non lu |
| Vérificateur (sondes) | opus / high, frais, jamais l'auteur | 1 pour 2-3 lanes | sondes au dépôt via `scripts/sonde.py` (AMET, à construire), verdict REPRO / STATIQUE / RÉFUTÉ / PARTIEL |
| Seconde lentille | opus / high, frais | 1-3 **si 0 réfuté sur les S1** | lentilles déjà-planifié / spec / reproduction INDÉPENDANTE, sur les S1 seuls |
| Critique de complétude | L2 opus / high ; L3 **Fable / high, exactement 1** | 1 | « quelle surface, quelle claim, quelle source manque » ; chaque trou est SONDÉ avant d'entrer au tableau |
| Rédacteur de tâches | opus / high, plages d'ID disjointes | 1 par ≈ 40 tâches, max 3 | lignes v3 + générateur de clauses |
| Éditeur | sonnet / medium | 1 | lint, FORME 5, `plan_lanes --check` |

| | **L1** | **L2** | **L3** |
|---|---|---|---|
| Quand | sans argent, sortie client ni multi-société | chiffre client, saisie propagée, 4-8 surfaces | argent + PDF / portail + multi-société + parcours chaud |
| Lanes / vérificateurs | 4-6 / 1-2 | 5-9 / 2-3 | 8-9 / 3 |
| Live | facultatif (obligatoire dès un chiffre client) | UNE transaction réelle | parcours complet + 2 sociétés |
| Critique | relecture orchestrateur | 1 opus | 1 Fable |
| Agents / jetons / tâches | 6-10 / ≤ 2,5 M / ≤ 50 | 10-16 / 2,5-5 M / 40-100 | 14-20 / 4,7-6,7 M, plafond 8 M / 30-90 |

Anti-exemple interdit (D3, 37 M jetons) : chercheurs de manques en boucle, lentilles sur TOUS les constats, 25 agents
relancés, 10 rédacteurs, 3 Fable. Un audit = UN workflow fan-out même répertoire (cache par répertoire) ; jamais de worktree
pour lire. Si une consigne du fondateur dépasse la recette, l'orchestrateur annonce le coût estimé en une ligne avant.

### B.4 Exécution
Lanes = surfaces indépendantes (points chauds découpés par sous-flux, jamais par nombre de fichiers), lecture complète,
constats bruts avec `fichier::symbole`. En parallèle, l'orchestrateur joue le LIVE : UNE transaction réelle du parcours du
premier clic au dernier artefact client, oracles durs qa-explorer 1-10, étapes négatives à chaque passage de main (éditer
l'amont quand l'aval existe, annuler, rouvrir, changer un réglage en cours de flux) ; ≤ 3 captures probantes ; mesures prod
lecture seule (A.2). Détecteurs : commande + SHA + verdict dans le dossier, sorties brutes hors dépôt.

### B.5 Porte empirique (R3)
- L'agent qui a trouvé ne vérifie jamais. Chaque constat touchant argent / chiffre client / persistance / multi-société /
  parcours reçoit une **sonde** `docs/audits/sondes/<G>/C-<G>-<NNN>.py` (en-tête `SONDE = {constat, sha, attendu}`,
  `def sonde(ctx)`) jouée par `scripts/sonde.py` dans une transaction ANNULÉE (mail en mémoire, Celery coupé, HTTP bloqué),
  avec comptes avant / après. Verdict REPRO (chemin de sonde dans la colonne « Sonde ») ou STATIQUE ; STATIQUE est interdit
  en S1-S2 sur les critères à sonde obligatoire. PLAUSIBLE n'entre jamais au tableau.
- **0 réfuté sur les S1 ⇒ seconde lentille** (11 dossiers v2 sur 19 étaient à 0 réfuté ; la seconde lentille a corrigé
  2/13 chez J5 et 2/4 chez J4). Jamais sur l'ensemble des constats.
- **Fraîcheur** : `git diff <base>..origin/main -- <périmètre>` avant rédaction ; un constat déjà corrigé est retiré.
- **Point de contrôle** : commit + push du tableau vérifié et des sondes sur la branche de claim (c'est ce que reprend
  `continue audit`).

### B.6 Critique → décisions → rédaction → lint
1. Critique de complétude (B.3) ; chaque trou est sondé avant d'entrer au tableau.
2. Décisions : UN lot `AskUserQuestion`, réponses dans `decisions.yml` ; sans réponse → entrée `ouverte` + tâches
   dépendantes en GATED nommant le D-id ; **jamais une tâche « Si (a)/(b) »** (une tâche par option).
3. Rédaction : rédacteurs + `scripts/audit_tache.py` (AMET, à construire : clauses CALCULÉES) + éditeur ; routage par
   `check_ownership.py --owner-of` ; `check_audit_dossier.py`, `check_taches_cablage.py` (FORME 5 v3), `plan_lanes.py --check`,
   `ci_guards.py stage-names` VERTS avant la PR ; écarts à la méthode amendés ici.

### B.7 Clôture du run
Registre (`groupe`, `plans_alimentes`, `pr`, `date`, `dossier`), `git fetch origin` puis push, PR docs-only
`gh pr merge --auto --merge --delete-branch`, rapport = §9 du dossier + `work on the plan audit_<unité>` par fichier alimenté.
La run s'arrête au merge (Deploys : Reda).

---

## §C Formats

### C.1 Le constat = une ligne du tableau §3 du dossier
`C-<G>-<NNN> | étape | critère (un seul) | S1-S4 | fichier::symbole | observé → attendu | sonde (chemin REPRO ou STATIQUE) |
tâche(s)`. Priorité P0-P3 fixée par l'orchestrateur, jamais par la lane. Frères et sœurs (même motif ailleurs) = UN constat,
N emplacements. Le préfixe du C-id désigne son dossier (`C-AMET-…` → `2026-10-09-methode.md`).

### C.2 La tâche v3 (une ligne physique ; `plan_lanes.py` ne lit que la première ligne)

Forme : `- [ ] <ID> — **<Verbe + objet + fin bornée>** : ` puis les 14 clauses enchaînées, chacune ouverte par son libellé exact,
`Files:` en DERNIER puis `(ROUTINE|SCHEMA|ARCH|DECISION|AUTH|COST) (@after: …) (@lane: …) (@model: …)`. Cible ≤ 2 400 caractères (les 57 premières tâches v3 font 2 300-3 100 : le générateur ramène les clauses calculées à leur forme compacte).

| # | Libellé | Contenu exigé | Auteur |
|---|---|---|---|
| 1 | `Constat :` | `C-<G>-<NNN> (C<n>, S<n>) — <mécanisme fautif> à `<fichier>::<symbole>`` | auditeur |
| 2 | `Given … When … Then` | fixtures RÉALISTES (contraintes NOT NULL), UN geste, UNE sortie observable (= PDF / page publique si sortie client) | auditeur |
| 3 | `Persistance :` | « relire / rouvrir ⇒ identique » ; `n/a — lecture \| rendu \| garde : raison` | auditeur |
| 4 | `Emplacement :` | `fichier::symbole` (N l. ; ≥ 2 000 : point d'insertion ou cible d'extraction ; SPL ouvert qui déplace le symbole → `@after`) | GÉNÉRÉ |
| 5 | `Code net :` | supprime X ; réutilise `f::sym` (recherche exécutée : N définitions, survivant) ; aucune seconde implémentation ; lignes nettes attendues ≤ N | GÉNÉRÉ + auditeur |
| 6 | `Appelants :` | RÉSULTAT du grep : appelants Python, références chaîne (beat, settings), routes → wrappers front → écrans comptés ; lecteurs FRONT d'une clé servie ; « 0 écran » explicite | GÉNÉRÉ |
| 7 | `Assertions existantes :` | tests / goldens / e2e / contract_samples qui exercent le symbole ou portent l'ancien littéral → « reste vert » ou « réaligner » (alors dans `Files:`) | GÉNÉRÉ + verdict |
| 8 | `Jumeaux :` | candidats calculés (même nom, corps identique, même URL servie ailleurs, apps/web, PDF) → « traité ici, survivant X » / « autre geste » / « aucun (grep <motif> : 0) » | GÉNÉRÉ + verdict |
| 9 | `Listes figées :` | baselines, goldens, allowlists, `api-contracts.md`, openapi, gardes par numéro de ligne qui citent le fichier → commande de régénération ; « aucune (grep … : 0) » | GÉNÉRÉ |
| 10 | `Contrat partagé :` | contract_samples nommant la route / les clés ; `n/a — backend seul \| front seul` | GÉNÉRÉ |
| 11 | `Test rouge d'abord :` | `<module de test EXISTANT>::<Classe>::<test>`, rouge sur <sha>, observable ; **mutant** (ligne changée ⇒ échec) ; nouveau fichier seulement avec « Nouveau fichier car : » | auditeur, placement GÉNÉRÉ |
| 12 | `Preuve en direct :` | `P<n>.<m>` ou étape de parcours rejouée ; « API seulement — 0 écran » ; `n/a — raison` | auditeur |
| 13 | `Hors périmètre :` | une ligne, ids des tâches sœurs | auditeur |
| 14 | `(gen <sha> …)` puis `Files:` | tampon du générateur (`(gen manuel <sha7>)` tant qu'il n'existe pas) ; chemins complets entre backticks ; tout fichier « réaligner » / « traité ici » / « régénérer » y figure | GÉNÉRÉ / auditeur |

Interdits (FORME 5 v3 de `check_taches_cablage.py`) : un libellé absent ; un `n/a` nu (toujours `n/a — raison`) ; l'absence de
`(@model: haiku|sonnet|opus)` (les clauses calculées contiennent les mots-clés du classifieur de plan_lanes). Interdits par
relecture : une ancre `fichier:ligne` seule ; un nom de fichier de test portant un id de tâche ; un second marqueur
`fichier(s) :` ; « Si (a)/(b) » ; « grep listé dans le commit » ; deux comportements dans une tâche ; `@after` vers une tâche
ouverte d'un autre fichier (sauf moitié de contrat M0). `@model: opus` pour règle #4, argent, auth, `core`. Chaque groupe se
termine par UNE tâche `@acceptation` (§C.4) que les lanes ne construisent jamais.

**Format v2 (13 clauses).** Les tâches ouvertes à la bascule sont gelées par identifiant dans `scripts/taches_audit_v2.txt`
(liste qui ne fait que rétrécir) : valides pour le build, jamais réécrites. Le constructeur lance le générateur de clauses
(ou les greps équivalents) sur une tâche v2 AVANT de coder (CLAUDE.md, étape 2). Une tâche nouvelle pour un ancien groupe
s'écrit sous un en-tête `## Groupe <G> — complément du <date> · format v3` ou `### <G> — ÉCARTS vérifie <date> · format v3`.

**En-têtes.** `## Groupe <G> — audit <mot> du <date> (dossier …) · format v3`, puis `### <G> — M0 contrats (seuls sur main
d'abord)` / `M1 bloquant-fondateur` / `M2` / `M3 nettoyage et gardes` / `GATED (ne PAS auto-construire)` (niveau `###`, forme
reconnue par `plan_lanes._NON_QUEUE_SECTION`), inséré juste avant `## DONE LOG`. Append-only : on ne réécrit, ne réordonne ni
ne recoche jamais les tâches d'un autre groupe.

### C.3 Le dossier
Gabarit unique `docs/audits/GABARIT_DOSSIER.md` (9 sections, tableau des constats, commentaire machine `dossier-v3`), lint
`check_audit_dossier.py` : ordre des sections ; lignes ≤ 400 caractères ; ≤ 12 Ko hors tableau + 400 o par constat ; chaque
C-id cité par une tâche existe au §3 ; chaque S1-S2 a une tâche ou « sans tâche : raison » ; ancre `fichier::symbole` ;
colonne « Sonde » = chemin existant ou STATIQUE (interdit en S1-S2 sur critères à sonde) ; D-id présents dans `decisions.yml` ;
interdits : ids de lane, « FABLE § », « lot W », chemins de scratchpad, lignes de tâche, blocs de code > 5 lignes, e-mail /
téléphone ; ligne de coût `H<n> S<n> O<n> F<n> · jetons sous-agents ≈ x M`. Les 19 dossiers v2 restent un historique lecture seule.

### C.4 Boucle de clôture (acceptation, `vérifie`, registre)
1. **Acceptation = couverture par tâche.** Toute tâche cochée à preuve exécutable d'un groupe d'audit est couverte par un
   enregistrement PASS `docs/audits/acceptation/<G>/<date>-<sha9>.md` (`couvre:` = ids cochés, étapes rejouées,
   `results.json`, oracles qa-explorer 1-10) ou figure dans la dette gelée DU GROUPE (`_dette.yml`, qui ne fait que rétrécir).
   Produit par l'ORCHESTRATEUR du plan-run (spec `frontend/e2e/acceptation/<g>.spec.js` quand elle existe, sinon Playwright
   MCP), AVANT le push de toute vague qui coche une tâche du groupe (CLAUDE.md étape 3-bis). Garde `check_acceptation.py`
   (stage-names, sans état, AMET) : dette gelée par groupe ; tâches cochées dans la PR couvertes par un enregistrement ajouté
   dans la PR ; ≥ 1 étape par tâche exécutable ; écart accepté seulement si l'étape échoue aussi à la base ; `results.json`
   fait foi. Un rejeu de PARCOURS (C19) alimente `couvre:` pour toutes les tâches de ses étapes, tous groupes confondus ;
   la tâche `@acceptation` d'un groupe se coche quand ses tâches sont toutes couvertes.
2. **`vérifie <G>` dû** quand `audit_registre.py --du` compte ≥ 50 % (mi-parcours) puis ≥ 95 % (clôture) des tâches
   constructibles cochées ; `audit next` / `loop audit` le jouent AVANT toute nouvelle unité ; le rapport de chaque merge
   l'affiche. Échantillon : toutes les P0 / S1 + 25 % du reste, min 8, max 48, graine = SHA ; vérificateurs frais opus / high
   (≈ 22 k jetons par tâche) : texte ↔ commit(s) ↔ test nommé ↔ 7 leçons de `lecons-construction-qjr5.md`, verdict ok /
   partiel / non-fait / faux / régression / déjà-présent + cause (closed list) ; sondes rejouées ; UNE critique Fable
   seulement si des écarts S1 subsistent. Écarts confirmés = tâches v3 sous `### <G> — ÉCARTS vérifie <date> · format v3`
   dans le fichier du PROPRIÉTAIRE, numérotation du groupe continuée (jamais `ERROR_PLAN.md`).
3. **Registre calculé** par `audit_registre.py` : `audité` ← dossier ; `construit` ← ≥ 95 % cochées ; `accepté` ← couverture
   complète ; `vérifié` ← `vérifie` sans écart S1-S2. Sortie du cycle : deux `vérifie` consécutifs à zéro S1-S2.
4. Une tâche n'est fermée que par un vérificateur frais qui rejoue la reproduction ; preuve que la CAUSE a disparu (test
   rouge-d'abord vert, mutant rouge, frères fermés, garde de classe).

---

## §D Découpage, parcours, propriété

### D.1 Parcours et lentilles (objet d'audit du cycle suivant)
L'ERP est un ensemble de parcours qui tournent seuls et que l'utilisateur corrige à chaque étape. Un audit par unité ne voit
pas les passages de main : les cassures mesurées (27/81 étapes automatiques, 8 écrasements de saisie, 13 portes de lead) sont
entre les unités. Le cycle suivant audite par PARCOURS, les unités ne servant plus qu'à la propriété (§D.3).

| Id | Parcours | De → à | Pilote (propriétaire de la table) |
|---|---|---|---|
| PA1 | Contact → visite | formulaire / `/crm/leads` → `/visites/revue` (sous-table `parcours_suivi.json`) | lead |
| PA2 | Conception | `/calepinage/nouveau` → `/calepinage/:id/dossiers` (+ sous-parcours 82-21) | calepinage |
| PA3 | Devis → signature | `/ventes/devis/nouveau` → `/proposition/<token>` (moteur : lanes opus, règle #4) | devis |
| PA4 | Argent | « Convertir en BC » → paiements / relances / avoirs / DGI-UBL / RAS / mandat / pro-forma | facturation |
| PA5 | Chantier → SAV | `/chantiers` → réception → parc → ticket | chantiers |
| PA6 | Approvisionnement | fiche chantier « Matériel & BC » → réception fournisseur → paiements fournisseur | stock |
| PA7 | Monitoring et abonnement | parc SAV → abonnement → SLA → crédit | sav |
| PF1 | Sécurité / multi-société | rôles × toutes les portes, 2 sociétés | sécurité |
| PF2 | Socle | paramètres, événements, notifications, GED / portail, analyse, parrainage, RGPD, salle de vente | parametres |
| PF3 | Deploy / CI / gardes / budgets de performance | — | deploy |

**Table de parcours** `backend/django_core/apps/<pilote>/parcours/<PA>.json` (un fichier, un propriétaire ; absent de
`frontend/` : le serveur ne lirait pas, l'image prod ne l'aurait pas) — par étape : `id`, `nom`, `proprietaire`,
`declencheur{type: clic|evenement|beat|manuel, source: fichier::symbole}`, `ecran{route, composant, action}`, `fonction_entree`,
`checkpoint{modifiable, champs, persistance}`, `regle_aval[]` (recalcul | preserve_manuel | fige | reference | choix_explicite |
refus_409 | ecrase | non_propage), `provenance{marqueur, ecrivains_auto}`, `compensation`, `portes[]`, `suite`, `negatifs[]`,
`test_nomme`, `taches[]`, `constats[]`. Trois consommateurs : garde CI statique `check_parcours.py` (symboles résolus, 1
déclencheur / 1 entrée / 1 checkpoint / 1 règle aval), rejeu live `rejouer_parcours.py` (walkthrough d'audit ET enregistrement
d'acceptation), panneau d'écran par API (tous AMET, à construire). Modèle : `parcours_suivi.json` (écran + garde + guide).

**Lentilles obligatoires dans chaque audit** : argent (HT→TTC au centime), sorties client (chemin unique, figé, envoyé,
archivé, sans `prix_achat`), performance (points chauds + beats), sécurité (rôles × portes, 2 sociétés), forme (C20).

**Procédure d'un `audit parcours`** : charte (parcours, unités traversées, UN enregistrement à suivre) → table d'abord
(remplie / rafraîchie depuis le code : c'est le manifeste de couverture) → walkthrough sur UN enregistrement du premier clic
au dernier artefact client, étapes négatives à chaque passage de main → sondes d'écrasement / non-propagation à chaque
checkpoint (C16, C17) → inventaire des portes (C20) → constats → tâches routées aux propriétaires. Lanes = grappes de
passages de main, pas unités. Dédoublonnage sur (symbole modifié, mécanisme) ; une étape qui a une tâche ouverte est
« couverte, en attente » ; une étape à tâches cochées est re-prouvée par le rejeu.

### D.2 Rang et statuts
Rang = probabilité (churn, défauts récents, signaux morts, pas d'audit antérieur) × impact (argent, sortie client, fuite,
perte ⇒ 5) ; à égalité l'argent puis la sortie client d'abord. Les statuts sont CALCULÉS (§C.4.3) ; `audit status` les affiche.

### D.3 Propriété et routage (un fichier de plan par propriétaire)
1. **Table de propriété** : `docs/ownership.yml` (garde `check_ownership.py`) ; le chemin le plus spécifique gagne ; un test
   et une garde appartiennent au propriétaire du code qu'ils testent ; un fichier neuf est revendiqué dans le même commit.
2. **Un seul propriétaire** pour tous les `Files:` → `docs/plans/PLAN_AUDIT_<UNITE>.md`.
3. **Plusieurs propriétaires** → la tâche est SCINDÉE en moitiés mono-propriétaire : contrat / M0 d'abord (seul sur `main`),
   l'autre moitié `@after`. `PLAN_AUDIT_TRANSVERSE.md` n'accepte que les déplacements SPL atomiques tagués
   `(@atomique: <propriétaires>)` (règle (d) de `check_ownership.py`, AMET) ; il ne tourne jamais en parallèle d'un plan dont
   il touche un propriétaire. Transition : jusqu'à la PR 2 de fusion (D-OWN-FUSION), les tâches
   {crm, lead} y restent admises (règle (d) en mode rapport) et y portent la mention de leur destination.
4. **Chemin sans propriétaire** → corriger le registre dans la PR ; app parquée → pas de tâche.
5. Les pistes sans fichiers (totaux, pdf, performance) sont des LENTILLES (§D.1), pas des unités.
6. Les tâches d'un groupe gardent le **préfixe de l'unité auditée**, quel que soit le fichier où elles atterrissent ; le registre
   liste les fichiers alimentés (`plans_alimentes`).
7. **Append-only** : nouveau groupe ou section ÉCARTS inséré juste avant `## DONE LOG` ; on ne réécrit, ne réordonne ni ne
   recoche jamais les tâches d'un autre groupe. Exception unique : la migration de propriété du 2026-10-09 (D-OWN-FUSION :
   crm → lead, générateur → devis, 111 tâches TRANSVERSE déplacées verbatim, 43 scindées), PR dédiée.
8. **Ordre correctifs-d'abord** : sur un fichier-dieu, les correctifs ouverts précèdent le bloc golden + déplacements SPL
   (`@after` posés sur SPL1 / SPL70) ; tout ce qui est écrit après la migration passe après le dernier déplacement.
Gabarit d'un `PLAN_AUDIT_<UNITE>.md` : contrat de propriété (écrit seulement dans ses chemins ; lecture étrangère par
`selectors.py` / `services.py` / FK chaîne ; `DB_NAME=erp_audit_<unite>` ; branche `dev-audit_<unite>` ; hors surface du
plan-fingerprint ; leçons QJR5 = critères d'acceptation), puis les groupes, puis `## DONE LOG`.

### D.4 Fiches d'unité : à migrer dans `docs/audits/unites.yml` (champ `fiche:`, tâche AMET91) ; jusque-là `git show 1d08a5bd9:docs/audits/METHODE.md` §D.6.

### D.5 Claim et sélection
`audit_registre.py claim <id>` : depuis `origin/main`, branche `audit-<id>` + commit vide poussé (une branche vivante non
ancêtre de `main` = unité prise ; push refusé = prise ailleurs) ; le merge `--delete-branch` libère ; claim périmé > 48 h
signalé ; seul `continue audit` reprend un claim. Sélection : `vérifie` dû, puis plus petit rang « à auditer » non réclamé.

### D.6 Fiches §D.6 v2 : texte d'origine `git show 1d08a5bd9:docs/audits/METHODE.md` (106 lignes, 7 dossiers le citent) ; destination `unites.yml` `fiche:` (AMET91).

---

## §E Anti-patterns rencontrés et limites

| # | Anti-pattern | Rencontré (preuve) |
|---|---|---|
| 1 | Plus de lanes ou de lentilles pour « aller plus loin » ; lentilles sur tous les constats ; boucle « jusqu'à sec » | D3 : 375 constats × 2-3 lentilles, 0 réfuté, ≈ 37 M jetons |
| 2 | Verdict sans preuve exécutée ; accord de relecteurs pris pour preuve | 15 réfutations sur ≈ 956 constats ; 72/72 « reproduits » chez J5 |
| 3 | Celui qui trouve vérifie ; le constructeur certifie | 2 régressions sous tâches cochées (ATOT2, ATOT9) ; 23/48 one-shot |
| 4 | CI verte prise pour « livré » ; acceptation live non jouée | 0/19 acceptations jouées ; ADOC171 (seule jouée) = 2 FAIL réels |
| 5 | Test affaibli ou épinglé sur l'ancien comportement | ACAL30 ; 75 réparations « test périmé » |
| 6 | Un nouveau fichier de test par tâche | 31/48 tâches ; 39 % des 5 401 fichiers de test |
| 7 | Sonde hors transaction ; GET qui écrit ; mail réel | un GET de liste a prolongé 14 liens ; clé SendGrid réelle en local |
| 8 | Sortie de scout prise comme autorité (dédoublonnage) | 3 sorties fausses (J5, J3, X3) |
| 9 | Ids de lane ou renvois au scratchpad dans un dossier | 174/935 C-id introuvables ; 48 % des tâches citent une sonde disparue |
| 10 | Décision posée APRÈS la rédaction (« Si (a)/(b) ») | 9/10 réponses non propagées ; 12 décisions ouvertes bloquent 27 tâches |
| 11 | Ancre `fichier:ligne` ; baseline par numéro de ligne | 53 % des ancres dérivées ; gardes réparées en boucle (16-24 % des réparations) |
| 12 | Live sur données démo vides présenté comme couvert | J2 sans intervention, J4 parc vide, J1b 0/3 devis géoréférencés |
| 13 | Écrire chez un autre propriétaire ; tâche multi-propriétaires en TRANSVERSE | 32 % des tâches hors unité ; lane de 285 ; ping-pong @after 43/30 |
| 14 | Clause affirmée au lieu de calculée (« Appelants : n/a », « Listes figées : n/a ») | 4 565 `n/a` sur 1 609 tâches ; ≈ 20/48 clauses fausses |
| 15 | Une garde par constat ; baseline qui grossit | 70 gardes, 4 176 entrées gelées (+79 % en 7 j) ; 35 % des réparations CI |

Limites : un audit est un indicateur corrélé, jamais une preuve d'absence ; la réfutation reste basse tant que les sondes
ne sont pas systématiques ; les personas « comptable », « magasinier », « bureau d'études » n'ont pas de rôle réel ; une
étape jouée sur démo vide est NON couverte ; un audit d'unité ne voit pas les passages de main hors de son parcours.

## §F Sources
Les 60 sources de la v2 et leur lecture : `git show 1d08a5bd9:docs/audits/METHODE.md` (§F). Mesures de la v3 :
`docs/audits/2026-10-09-methode.md`.
