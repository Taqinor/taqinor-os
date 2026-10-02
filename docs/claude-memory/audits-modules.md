---
name: audits-modules
description: Prompts d'audit L3 par module (méthode QJR5) — Reda tape « audit <module> » ou « vérifie <groupe> » ; lire ce fichier et exécuter le prompt correspondant
metadata:
  type: reference
---

# Audits par module — déclencheurs de deux mots (fondateur, 02/10/2026)

**Quand Reda tape un déclencheur ci-dessous** (seul, ou suivi de précisions), exécuter le prompt de ce
module = le **BLOC COMMUN** + le **périmètre** de la ligne. Les précisions qu'il ajoute priment. On
ne construit RIEN : la sortie est un groupe de tâches au plan (un build se lance ensuite par
« work on the plan »). Méthode de référence : l'audit du parcours devis du 30/09 (groupe QJR5).

| Déclencheur | Module / surface |
|---|---|
| `audit leads` | CRM — entrée des leads |
| `audit fiche` | CRM — fiche lead / cockpit / pipeline |
| `audit cadence` | CRM — cadence de suivi commercial |
| `audit clients` | CRM — clients, parrainage, partenaires, pilotage commercial |
| `audit visites` | Visites techniques terrain |
| `audit calepinage` | Calepinage (studio toiture) |
| `audit devis` | Parcours devis (contre-visite après QJR5) |
| `audit facturation` | BC → facture → paiement → avoir → relances |
| `audit stock` | Stock, catalogue, achats fournisseurs |
| `audit chantiers` | Chantiers / installations / interventions |
| `audit sav` | SAV, parc, garanties, maintenance |
| `audit ged` | GED (documents) |
| `audit portail` | Portail client + pages publiques |
| `audit parametres` | Paramètres société + notifications/messages |
| `vérifie <GROUPE>` | Vérification post-construction d'un groupe déjà construit (ex. `vérifie QJR5`) |

## BLOC COMMUN (s'applique à chaque `audit …`)

```text
go extremely deep (go-deep L3) on the surface below. Goals, in this order:
1. EDITABILITY AT EVERY STAGE: every input the client or the team enters can be changed later, the
   change PROPAGATES to every downstream object/document (quote, PDF, chantier, invoice, portal…)
   without silently erasing a manual edit, and a document already SENT/SIGNED follows the founder
   rules (docs/claude-memory/devis-parcours-modifiable-qjr5.md : envoyé corrigé sur place, accepté →
   Réviser V2).
2. ONE FUNCTION PER GESTURE: list every duplicate implementation (screen vs server vs PDF vs public
   page vs apps/web), name the survivor.
3. CLEAN CODE: dead endpoints/screens/functions (grep proof of zero callers), stale texts, parked-module
   leftovers (MVP solaire, core.parked), multi-tenant leaks, STAGES.py rule #2, rule #4.
4. WHAT THE CLIENT SEES is exact (no invented number, no stale text, right language).
Never re-report an OPEN task (grep docs/PLAN2.md, docs/PLAN.md, docs/ERROR_PLAN.md, docs/plans/*) or
something already fixed on origin/main (git log); prior groups of the module are summarised in
docs/done_task.md — re-check them only where a defect is suspected.

MANDATORY: the 7 criteria of docs/claude-memory/lecons-construction-qjr5.md are audit checks AND
acceptance criteria written into every task (persisted round-trip save→reopen→save, real source never
mocked, all call sites, behavioural red-first tests, hunt the twin, deployable not just green, live
proof). LIVE PROOF = Playwright on the LOCAL stack (manage.py migrate + `docker compose up -d --build
frontend` first; demo company; records prefixed QA-<MODULE>); every "bloquant" finding is reproduced
live before it is filed, and the plan ends with a live acceptance task replaying the whole journey.

Method: R1 map (CODEMAP §3/§4 first) → R2 one lane per independent surface (≤10-12, explicit
model+effort on EVERY agent, grounding block) → R3 two independent verifier lenses per finding (Fable
on the critical families) + the live run → R4 drafters per family, a Fable completeness critic, a
Fable review of the assembled group. Founder decisions via interactive questions (AskUserQuestion,
batched, recommended option first), never prose.
Output: ONE new group in docs/PLAN2.md in the QJR5 format (provenance, décisions gravées, séquencement,
NE PAS FAIRE, non couvert, then M0 contracts alone → M1 founder-blocking → M2 → M3 cleanup → GATED);
every task: Files:, @after (front on its back half AND its contract — PACT10/11), @lane, @model,
shared-contract clause when it names back+front (check_taches_cablage). Refresh CODEMAP §10 +
codemap_fingerprint --write; run scripts/ci_guards.py stage-names locally; ONE docs-only PR with
auto-merge (merge commit), session auto-archive OFF; git fetch origin right before pushing.
Do not build anything. Report in plain French: counts verified/refuted, decisions taken, what was NOT covered.
```

## PÉRIMÈTRES

**`audit leads`** — CRM, ENTRÉE DES LEADS. Site (apps/web tunnel + mon-toit, `apps/web/src/lib/lead.ts`,
lettre morte `LEADS_DLQ`), Meta Lead Ads, saisie manuelle, import, questionnaire public
(`crm/public_questionnaire_views.py`, `questionnaire.py`, `apps/web/src/pages/questionnaire`) →
`crm/webhooks.py` (mapping, `web_questionnaire` bag vs colonnes, rejeu), dédoublonnage, attribution
(round-robin, territoires), score, premier contact. Vérifier : ce que le client a saisi est
corrigeable par l'équipe sans être réécrasé par une nouvelle soumission ; aucune donnée perdue entre
site → CRM ; une seule normalisation téléphone / ville / factures. Groupes antérieurs : CRX, QJR5 (intake).

**`audit fiche`** — CRM, FICHE LEAD. `/crm/leads/:id` : `features/crm/workspace/**` (LeadWorkspace,
draftCore, useLeadDraft, sections/*, IdentityRail, ContextRail, DevisTab, VisiteTab, TimelineTab,
StageControl), chatter `LeadActivity`, pipeline STAGES.py, liste/kanban/carte/calendrier/activités,
`crm/views.py` + `serializers.py` (LeadViewSet), propagation lead → client → devis → visite →
calepinage. Vérifier : chaque champ modifiable et suivi au chatter, l'autosave ne perd rien, une
correction atteint les documents en aval (dérive signalée, « reprendre »), un seul chemin par geste
(changer d'étape, marquer perdu, assigner).

**`audit cadence`** — CRM, CADENCE DE SUIVI COMMERCIAL. Table unique
`features/crm/relances/parcours_suivi.json` (+ parcours.js, RelanceEtapeRow.jsx, CadenceFrise,
JournalRelance, SectionPipeline), `crm/cadence_temps.py`, `panneau_appel.py`, `receivers.py`,
`tests_parcours_suivi.py`, cockpit `controle_suivi.json`, relances ventes automatiques (NudgeLog,
`ventes/domain/recouvrement.py`), messages WhatsApp/e-mail (`notifications`), guide PDF
`scripts/generer_guide_suivi.py`. Règles fondateur : `suivi-commercial-table-parcours.md`,
`cockpit-controle-suivi.md`, QJR660 (cadence d'origine gardée après correction). Vérifier : chaque
réponse mène au bon résultat (étape suivante, date en jours ouvrés, étape funnel, message) ou est
juste stockée, et se corrige après coup ; la table est LA seule source ; ce que le client reçoit
(texte, langue FR/AR/darija, lien, horaire) est ce que l'étape promet. Live : rejouer une cadence
complète sur un lead, corriger une mauvaise réponse, envoyer/corriger/réviser un devis au milieu.
Groupes antérieurs : CAD, MRY, QJR5.

**`audit clients`** — CRM, CLIENTS & PILOTAGE. Clients/contacts (`resolve_client_for_lead`,
synchronisation identité lead → client, doublons tiers), parrainage, partenaires & commissions
(`CommissionPartenaire`), salle de vente, forecast, défis, concurrents/motifs de perte, cockpit
`/crm/cockpit`, visiteurs du site. Vérifier : un client corrigé une fois l'est partout (devis, PDF,
factures, portail) ; les chiffres de pilotage se recalculent depuis UNE source.

**`audit visites`** — VISITES TECHNIQUES. `apps/visites` (VisiteTerrain, VisiteMedia), `/visites/*`
(planifier, revue, calage), app terrain autonome (le technicien n'a pas accès au CRM), checklist
photos/mesures, feu vert bureau d'études, liens vers lead / calepinage / devis. Vérifier : une
visite se corrige après coup (photos, mesures, réponses), ses résultats alimentent le calepinage et
le devis sans re-saisie et sans écraser une correction ; caméra/géoloc en prod. Groupes : VT, VTA.

**`audit calepinage`** — CALEPINAGE. Parcours lead/visite → nouveau calepinage → capture toit/site
(photos, pente, terrain, plan importé, relevé, horizon, obstacles/allées, ombrière) → atelier 3D
(panneaux, rangées, fixation/lestage, séries, batterie, schéma unifilaire) → simulation (chaîne de
pertes, production) → variantes/versions/approbation → publication vers un devis (BoutonDevis,
`roof_layout_v2`, resync devis↔layout, D-QJR5-5 sur un devis envoyé) → livrables / dossiers
réglementaires → pose réelle. Code : `apps/calepinage/**`, `features/calepinage/**`,
`api/calepinageApi.js` + TOUT autre endroit qui dessine ou stocke un toit (ventes Conception3D /
ToitureDesign / RoofViewer, apps/web roofPro11, crm traceToit / roof_point / roof_outline,
`ventes/domain/geometrie.py`, `resynchronisation.py`). Groupes : CAL, CALX.

**`audit devis`** — PARCOURS DEVIS, contre-visite. Même périmètre que QJR5 (création, Édition
complète, calculateur, envoi, correction d'un envoyé, Réviser, PDF /proposal, page publique,
signature) : vérifier que les 171 tâches QJR5 + les 14 ERR-QJR5 + #772 tiennent EN DIRECT, chercher
ce qui a régressé depuis. Groupes : QJR…QJR5.

**`audit facturation`** — DEVIS ACCEPTÉ → ARGENT. BonCommande, factures (acompte / situation /
solde, échéancier du devis D-QJR5-10), paiements (lien de paiement, import relevé, mandats,
remises), avoirs, notes de débit, relances de paiement, aval d'une V2 (D-QJR5-11). Code :
`apps/facturation`, `ventes/domain/{facturation_ops,encaissements,recouvrement,argent}.py`,
`/ventes/factures|avoirs|paiements|relances`, PDF facture (legacy, séparé de la règle #4). Vérifier :
chaque montant suit UNE chaîne (`_canonical_totaux`), une facture se corrige par avoir (jamais en
place), le client voit des totaux qui somment au centime.

**`audit stock`** — STOCK & ACHATS. Catalogue (`Produit`, marques, catégories, kits, courbe pompe,
`role_devis`, fiches produit), prix (vente TTC / `prix_achat` jamais client), mouvements, lots,
inventaires, fournisseurs, BCF → réception → facture fournisseur → paiement, OCR import,
`seed_catalogue`. Vérifier : un prix ou une fiche corrigé se propage aux devis non figés (règle
« prix négocié intouchable »), réservations/décréments cohérents avec chantiers et BC. Groupe : STKCAT.

**`audit chantiers`** — CHANTIERS. `apps/installations` : création depuis le devis (`bom` gelée),
planning, interventions, checklists, documents terrain, demandes d'achat, kitting, livraisons,
`/ma-journee`, GPS, production/parc. Vérifier : un devis révisé (V2) met à jour le chantier comme
décidé, une intervention se corrige après coup, une seule source pour la nomenclature. Groupe : CHT.

**`audit sav`** — SAV. Équipements (horloge de garantie), tickets + SLA, contrats de maintenance,
fiches d'intervention, problèmes, KB, alarmes onduleur, réclamations garantie. Vérifier : un ticket
se corrige/réouvre, la garantie part de la bonne date, SLA calculé d'une seule façon.

**`audit ged`** — GED. Cabinets/dossiers/documents/versions, ACL, rétention/legal hold, signatures,
dépôts publics, coffres, guides publiés (`publier_documents_meryem`), liens depuis devis/chantiers/
portail. Vérifier : une version remplace sans perdre l'historique, ACL multi-société étanches, un
document client = la bonne version.

**`audit portail`** — CLIENT EN LIGNE. `apps/portail` + `/portail/*`, pages publiques apps/web
(`/proposition/[...token]`, questionnaire), signature électronique, paiement en ligne, timeline
chantier, OTP. Vérifier : le client voit toujours la version en vigueur (jamais une V1 remplacée,
« mis à jour le … » après correction), rien au-delà de son périmètre (NTPRT14), même texte/CGV que le
PDF. Groupe : NTPRT.

**`audit parametres`** — PARAMÈTRES & MESSAGES. `apps/parametres` (CompanyProfile, textes documents
dont CGV, modèles WhatsApp/e-mail, TVA, conditions de paiement, barèmes transport, gammes) +
`apps/notifications` (routage, fenêtres horaires, modèles WA, journaux). Vérifier : un réglage
modifié s'applique partout où il est lu (une seule lecture par réglage), les documents déjà
envoyés/signés gardent leur version figée, aucun texte client codé en dur ailleurs.

## `vérifie <GROUPE>` — vérification post-construction

```text
Verify the build of plan group <GROUPE> the way QJR5 was verified on 01/10/2026: (1) on origin/main,
list every <GROUPE> task ticked [x] and the PRs that landed them, check their CI and the server
deploy state read-only (docs/claude-memory/prod-read-access.md); (2) one verifier lane per surface
(≤10, explicit model+effort, grounding block) compares each task TEXT with the merged commit(s) and
the named red-first test (verdict ok/partial/not_done/wrong/regression with evidence), applying the 7
criteria of lecons-construction-qjr5.md; (3) a live Playwright run of the journey on the local stack
(migrate + rebuild frontend image first); (4) one Fable final critic re-verifies every bloquant/majeur
gap. Then file the confirmed gaps as ERR-<GROUPE>-* lines in docs/ERROR_PLAN.md (title, file:line,
fix, red-first test, Files:) — and BEFORE building them, git fetch origin and check no parallel
"work on error plan" session already took them. Report in plain French.
```
