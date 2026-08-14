# Taqinor OS — Build Plan & Progress (priority queue, PLAN2)

> **This queue is drained BEFORE `docs/PLAN.md`.** A run works every pending `[ ]` task here first, and only falls through to `docs/PLAN.md` once this file has none left.

This is the **priority queue**, worked **before** `docs/PLAN.md`. A run drains every `[ ]` task
in this file FIRST — the same way (verify it isn't already built, build it completely with
tests, obey every STANDING RULE in `PLAN.md`, then commit it to a worktree branch, tick it `[x]`,
and append a DONE LOG line as it lands; **run `python scripts/plan_lanes.py docs/PLAN2.md` to get
the maximally-parallel cross-category wave plan and build those lanes in parallel with concurrent
worktree subagents up to the session ceiling (default 8, raised as high as the session can sustain
via `--max-lanes`), continuously refilled (work-stealing), coupled tasks in sequence inside a
lane**) — and only
once this file has no pending `[ ]` task left does it fall through to `docs/PLAN.md`. Every
worktree branch is folded into one `dev`, CI runs once over the whole batch, and the run
self-merges `dev` → `main` exactly once at the very end — **no per-agent PR, no per-task merge**.
All the HOW TO RUN and STANDING RULES in `docs/PLAN.md` apply here unchanged — including the
default **workflow-with-review engine** (one worktree subagent per task plus a separate
adversarial review agent that must pass before a change is merge-eligible), the
**parallel-subagent fallback** when no workflow engine is available (never a single serial
one-task-at-a-time agent), and the **sync-safe single merge** (integrate the latest
`origin/main` first, re-run CI, push without forcing). This file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

> **Web session note (2026-06-18):** a world-class audit of the public site (`apps/web`) was run and its
> fixes built — **W62–W66 shipped** (social proof scaffold, homepage guarantee band, founder photo-ready
> block, brand strip +Jinko/Huawei/Nexans, « réponse sous 48 h ») and the **W67 EN/AR i18n foundation**
> laid (Astro i18n + dictionary + switcher + RTL/hreflang, FR byte-identical). Full detail in
> `docs/WEB_PLAN.md` + `docs/DONE.md`; web work stays out of this OS queue per the OS/web split. Logged
> here at the founder's request — this note adds no OS task.

## BUILD QUEUE (do top-down — highest value first)

### Groupe QX ROUND 7 — 4 MODÈLES DE DEVIS : split industriel/commercial, 4 renderers, moteur agricole FAO-56, injection 82-21 (QX43-QX52 + QXG6, fondateur 2026-07-16)

*Commande fondateur 2026-07-16 : séparer industriel et commercial (4 modes réels avec
résidentiel/agricole), UN moteur de devis (règle #4) avec 4 rendus distincts visibles sur la
page proposition ET les PDF, questions par catégorie commerciale, moteur agricole eau→pompe
mondial-best-practice. Recherche 5 volets 2026-07-16 (commercial 9 catégories, industriel
MT/82-21, agricole FAO-56, courbes de charge MA + batteries, audit codebase) — constats clés :
`Lead.TypeInstallation.COMMERCIAL` et l'alias webhook `commercial` EXISTENT déjà
(crm/models.py:296-300, webhooks.py:185-196) ; le trou est côté Devis/moteur/web. Le décret
82-21 (2-25-100, BO 9 mars 2026, en vigueur 9 juin 2026) rend l'injection MT/HT RÉELLE :
tarif ANRE 0,21/0,18 DH/kWh (mars 2026-févr 2027), plafond 20 % de la production (en
révision), frais réseau ≈6,07+6,38 c/kWh à déduire.*

> Contraintes (toutes tâches) : règle #4 — le moteur RE ND seulement, jamais de statut ;
> nouveaux renderers DANS apps/ventes/quote_engine/ ; migrations additives ; zéro chiffre
> inventé — chaque constante tarifaire/Kc porte sa source en commentaire + flag « à vérifier
> fondateur » quand estimée ; prix_achat jamais client-facing.


GATED (fondateur — vérifications avant durcissement des constantes) :
- [ ] QXG6 — **[GATED: vérifs fondateur avant hard-coding]** (a) tarifs MT ONEE exacts
  (pointe/pleines/creuses TTC) contre le simulateur one.org.ma ; (b) bande prix/kWc C&I
  >100 kWc contre les vraies offres fournisseurs (l'estimation recherche = 6 000-9 000
  DH/kWc HT) ; (c) seuil déclaration/autorisation 82-21 (5 MW vs 1 MW selon sources) ;
  (d) statut du plafond d'injection 20 % (décret en révision). Chaque valeur validée
  remplace le flag « à vérifier » dans constants_82_21.py / la table day-share QX44.
  (@blocked: vérifs fondateur tarifs/seuils) (@lane: founder-verify)

*Notes de cohérence : dépendances QX44/QX46/QX49/QX50/QX52 → QX43 ; QX47 → QX48 ; aucune
circularité. QXG3 (prix des 11 pompes à courbe) reste LE gate du devis agricole chiffré ;
QXG1 (BSP WhatsApp) gate l'envoi automatisé ; QXG4 (contenu confiance réel) vaudra pour les
3 nouveaux renderers. Les moitiés web (WJ117-WJ126) vivent dans docs/WEB_PLAN.md.*

---

### Groupe PV — Toiture 3D + Outil de calepinage : direction PVsyst, départ du DEVIS, édition manuelle, schéma électrique (PV1-PV83 + PVG1-4, fondateur 2026-08-14)

*Commande fondateur 2026-08-14 : garder LES DEUX outils (la Toiture 3D roofPro11 côté ventes/CRM
ET l'outil de calepinage AO) et les rendre tous deux très forts, direction PVsyst jusqu'au schéma
électrique ; la 3D du CRM doit partir des ÉLÉMENTS DU DEVIS (le générateur part déjà de la facture)
et le générer s'il n'existe pas ; enrichir fortement le layout automatique et ajouter l'édition
manuelle des panneaux posés. Conception : 4 recons + 8 approfondissements parallèles + recherche
web PVsyst/Aurora/OpenSolar/NF C 15-100, synthèse Fable (session). Constats-clés vérifiés :
`serializeLayout` n'émet jamais `result/scenario/panelWatt/battery` (le devis généré prend le
panneau le moins cher et n'a jamais de batterie) ; `replace-lines` sans garde de statut ; les
placements manuels roofPro11 sont EFFACÉS sur 3 chemins (export tranche contiguë) ; les 5 tiroirs
AO + suggestions + marges = contrat jamais publié ; `core/calepinage/electrique.py`,
`solar_design.py` (16 fonctions) et le schéma unifilaire existant = code mort non branché ;
`calepinage_io.py:330` durcit `zones=[]` ; l'anti-ombrage villa fige 21,0° quelle que soit la
latitude ; le test d'obstacle roofPro11 ne teste que le CENTRE du panneau.*

> **Contraintes (toutes tâches PV).** Règle #4 intouchée : le moteur de devis REND seulement,
> `/proposal` reste le seul chemin PDF client, aucun statut jamais écrit par ces chemins.
> `prix_achat`/marge jamais client-facing (ni SLD, ni BOQ, ni proposal). Cross-app via
> `selectors.py`/`services.py`/string-FK ; `core/` pur (import-linter) ; PDF via `core.pdf.render_pdf`
> (ARC11) ; pièces jointes via `records.Attachment` (ARC26, jamais un FileField) ; migrations
> additives revertables ; chaînes de migrations MONO-ÉCRIVAIN par app (stock, ventes, ao,
> installations : séquencer dans une seule lane par app). Front : jamais un chiffre métier inventé
> (AOF94) ; entrées numériques `noValidate` + `step="any"`, jamais happées/rejetées. UI en français.
> **EXCEPTION DE ROUTAGE (fondateur 2026-08-14) : ce groupe inclut les moitiés `apps/web` du
> builder roofPro11 (Files: `apps/web/...`) DANS PLAN2 — une seule file, un seul drain, un seul
> merge ; ne pas les re-router vers WEB_PLAN.md.** Chemins backend en forme courte relative à
> `backend/django_core/` (`apps/...`, `core/...`) — convention plan_lanes. Les 4 contrats PACT10
> (PV1-PV4) se construisent EN PREMIER et sont repliés dans `dev` avant toute lane consommatrice.
> Zéro nouvelle dépendance npm (three + maplibre-gl déjà présents) ; zéro nouvelle dépendance
> Python hors gate (ezdxf = PVG1). Aucun chiffre inventé : toute constante électrique porte sa
> source normative (NF C 15-100 / UTE C 15-712-1 / IEC 62548) en commentaire ; toute donnée
> datasheet non confirmée reste NULL + flag « à vérifier fondateur ».

**CONTRATS D'ABORD (PACT10) :**
- [x] PV1 — **Contrat du contexte de conception 3D d'un devis** : déposer `apps/ventes/contract_samples/devis_design_context.json` — les DEUX variantes (modifiable + lecture_seule : devis/geometrie/cible/carte/modifiable/raison_lecture_seule/avertissements ; cible = {panneaux, kwc, panel_watt, scenario, batterie, bill_kwh} dérivée des LIGNES) + ligne README. La vue consommatrice devra faire UN SEUL return portant toutes les clés. **Done =** JSON déposé, `python scripts/check_api_shapes.py` vert. Files: `apps/ventes/contract_samples/devis_design_context.json`. (ROUTINE) (@lane: contrats) (@model: sonnet)
- [x] PV2 — **Contrat de la conception électrique d'un devis** : déposer `apps/ventes/contract_samples/conception_electrique.json` — forme de `GET/POST /ventes/devis/<id>/conception-electrique/` : chaines[] (par MPPT/par pan), conformite{conforme,bloquants[],alertes[]}, protections[], cables[] + table de chute de tension, bom[], note[]. **Done =** JSON déposé, check_api_shapes vert. Files: `apps/ventes/contract_samples/conception_electrique.json`. (ROUTINE) (@lane: contrats) (@model: sonnet)
- [x] PV3 — **Contrats AO : tiroirs + marges + suggestions + plan imposé** : déposer `apps/ao/contract_samples/calepinage_tiroirs.json` (les 5 tiroirs, `electrique` portant les 12 clés exactes lues par TiroirElectrique.jsx:93-125, + exemple_vide), `calepinage_marges.json` ({troncon_min_cm,bande_min_cm,rangee_critique,obstacle_critique} — non mesuré = null jamais 0), `calepinage_suggestions.json` (action DISCRIMINÉE {type:"parametres",patch}|{type:"obstacle",obstacle,provenance}), `calepinage_impose_utilisateur.json` (requête mode_pose='rangees_imposees_utilisateur' + rangees_imposees[[y0,kit]] et réponse avec preuve.methode=IMPOSE_UTILISATEUR + ecart_a_l_optimum). **Done =** 4 JSON déposés, check_api_shapes vert. Files: `apps/ao/contract_samples/calepinage_tiroirs.json`, `apps/ao/contract_samples/calepinage_marges.json`, `apps/ao/contract_samples/calepinage_suggestions.json`, `apps/ao/contract_samples/calepinage_impose_utilisateur.json`. (ROUTINE) (@lane: contrats) (@model: sonnet)
- [x] PV4 — **Contrat de l'étude bancable (simulation)** : déposer `apps/ventes/contract_samples/simulation.json` — le bloc `etude_params['simulation']` v1 : {version, computed_at, source pvgis|manual, zones[], pr{performance_ratio,loss_breakdown,p50_kwh,p90_kwh,p75_kwh,...}, self_consumption{}, net_metering{}, subscribed_power{}, degradation{}, projection_25y{npv,irr,payback_year}, warnings[]} — ADDITIF : les clés historiques (production_annuelle, economies, payback) restent intouchées à côté. **Done =** JSON déposé, check_api_shapes vert. Files: `apps/ventes/contract_samples/simulation.json`. (ROUTINE) (@lane: contrats) (@model: sonnet)

**SOCLE SPECS PRODUITS (la datasheet que tout le reste consomme) :**
- [x] PV5 — **FicheTechnique étendue : la datasheet PVsyst-grade** : `type_fiche` (module|onduleur|batterie|autre, choisi explicitement, suggestion par les classifieurs mots-clés existants — jamais inféré silencieusement) + champs module (longueur_mm, largeur_mm, epaisseur_mm, poids_kg, techno_cellule, bifacial, temp_coeff_voc_pct_c, temp_coeff_pmax_pct_c) + onduleur (ond_n_mppt, ond_mppt_v_min/max, ond_v_max_abs, ond_i_max_mppt_a, ond_ac_kw, ond_phases 1|3, ond_rendement_euro_pct) + batterie (bat_kwh_nominal, bat_kwh_usable, bat_dod_pct, bat_v_nominal, bat_max_charge_kw) — tous null=True additifs ; serializer mis à jour. **Done =** migration stock/0086 additive, serializer expose les champs, tests. Files: `apps/stock/models.py`, `apps/stock/migrations/`, `apps/stock/serializers.py`, tests stock. (SCHEMA) (@lane: backend/stock-specs) (@model: sonnet)
- [x] PV6 — **Sélecteurs stock : la datasheet lisible cross-app** : `apps/stock/selectors.py` gagne `specs_for_produit(produit)` (dict par type_fiche : module→{vmp,voc,isc,imp,temp_coeff_*,dims}, onduleur→{n_mppt,fenêtre,v_max,i_max,ac_kw,phases}, batterie→{...} ; fiche absente/champs null → dict VIDE = fallback octet-identique aux défauts) et `kit_from_produit(produit)` (construit un `core.calepinage.types.Kit` depuis longueur_mm/largeur_mm/pmax_wc ; incomplet → None). **Done =** les deux fonctions pures testées, fallback vide prouvé. Files: `apps/stock/selectors.py`, tests stock. (ROUTINE) (@after: PV5) (@lane: backend/stock-specs) (@model: sonnet)
- [x] PV7 — **Écran Fiches techniques complet** : le screen Paramètres→Données (DonneesSection.jsx:294) ne sait que créer+supprimer — ajouter sélecteur `type_fiche` + groupes de champs conditionnels (module/onduleur/batterie), upload du PDF constructeur (champ modèle existant), ÉDITION via `stockApi.updateFicheTechnique` (existe déjà, inutilisé). **Done =** créer/éditer/uploader chaque type, tests vitest. Files: `frontend/src/pages/parametres/DonneesSection.jsx`, `frontend/src/api/stockApi.js`, tests. (ROUTINE) (@after: PV5, PV6) (@lane: frontend/parametres) (@model: sonnet)
- [x] PV8 — **Badge « complétude datasheet »** : sur le catalogue et l'onglet fiche de ProduitDetail, un badge complet/partiel/absent selon les champs requis du type_fiche (module : dims+coeffs+électrique ; onduleur : fenêtre+MPPT) — les produits utilisés par le designer 3D/SLD montrent d'un coup d'œil ce qui manque. **Done =** badge visible avec états distincts, tests. Files: `frontend/src/pages/stock/ProduitDetail.jsx`, `frontend/src/pages/stock/CatalogueTable.jsx`, `frontend/src/pages/stock/StockList.jsx`, tests. (ROUTINE) (@after: PV5, PV6) (@lane: frontend/stock) (@model: sonnet)
- [x] PV9 — **Seed des datasheets RÉELLES (jamais inventées)** : étendre le seeder (idempotent, additif, skip si fiche existante) — PAN-CS-710 : dims 2384×1303×33 mm + temp_coeff_pmax −0,29 %/°C (sources distributeurs convergentes TOPBiHiKu7, en commentaire) ; PAN-JK-710 : coeffs −0,29/−0,25/+0,045 (datasheet JKM710-735N-66HL5-BDV) mais PAS les dims (la valeur trouvée appartient à une autre famille) ; Voc/Isc/Vmp/Imp + toutes fenêtres onduleur/batterie restent NULL (PVG4). **Done =** seed rejouable, valeurs sourcées en commentaire, aucun chiffre non sourcé. Files: `apps/stock/management/commands/seed_catalogue.py`, tests. (ROUTINE) (@after: PV5) (@lane: backend/stock-specs) (@model: sonnet)
- [x] PV10 — **solar_design branché sur la datasheet** : les appelants de `string_design`/`match_inverter` passent `module=`/`inverter_window=` construits par `specs_for_produit` (la fusion {**DEFAULT, **override} existe déjà — aucun changement de signature) ; sans fiche → comportement octet-identique. **Done =** avec fiche les fenêtres réelles s'appliquent (test), sans fiche golden inchangé. Files: `apps/ventes/solar_design.py`, tests ventes. (ROUTINE) (@after: PV6) (@lane: backend/ventes-solar) (@model: sonnet)
- [x] PV11 — **Wattage du PDF : la fiche avant la regex** : les appelants de `_parse_watt` dans le moteur premium préfèrent `FicheTechnique.pmax_wc` (via sélecteur stock) avant la regex sur le nom — surface règle #4 : nombre de pages, totaux et chaîne de statuts verrouillés par tests. **Done =** wattage exact depuis la fiche quand elle existe, regex fallback sinon, pages/totaux inchangés. Files: `apps/ventes/quote_engine/builder.py`, `apps/ventes/tests/test_quote_engine.py`. (ARCH) (@after: PV6) (@lane: backend/ventes-solar) (@model: opus)
- [ ] PV12 — **Kit villa depuis le produit devisé (côté AO)** : `apps/ao/selectors.py::calepinage_villa` et `apps/ao/services.py::calepiner_villa` acceptent un `produit_panneau`/kit construit par `kit_from_produit` (le paramètre kit=None existe déjà à chaque étage — risque zéro) ; dims incomplètes → KIT_VILLA_720 inchangé. L'appelant ventes (`compte_moteur_du_layout`) est branché par PV42. **Done =** calepinage_villa avec kit-produit 2384×1303 utilise SES dimensions (test), fallback prouvé. Files: `apps/ao/selectors.py`, `apps/ao/services.py`, tests ao. (ROUTINE) (@after: PV6) (@lane: backend/ao) (@model: sonnet)

**BOUCLE DEVIS ↔ 3D (le cœur de la commande — la 3D part du devis) :**
- [ ] PV13 — **Layout sérialisé v2 : émettre enfin result/scenario/panelWatt/battery** : `serializeLayout(ctx, billKwh, meta)` agrège les `zone.geometry` posées → `{version:2, result:{panels,kwc,annualKwh,savings|null}, scenario:"reseau"|"avec_batterie"|"hybride", panelWatt, battery, source:"devis"|"lead", devisId|null}` — ADDITIF PUR (tout champ v1 conservé octet pour octet, v1 toléré pour toujours) ; result dérivé des MÊMES geometry qui servent à l'export (jamais une autre source). **Done =** round-trip identité, test « aucun champ v1 perdu », les champs v2 présents. Files: `apps/web/src/scripts/roofPro11/prefill.ts`, `apps/web/src/scripts/roofPro11/types.ts`, `apps/web/src/scripts/roof-tool-pro11.ts`, tests apps/web. (ARCH) (@after: PV1) (@lane: appsweb/builder-core) (@model: opus)
- [x] PV14 — **`extract_roof_config` lit la géométrie par pan** : kWc/compte depuis `zone.geometry.{kwc,count}` quand `result` absent (répare AUSSI les blobs v1 stockés) — le devis cesse de citer « le panneau le moins cher » ; `_pick_product` reçoit enfin un watt. **Done =** blob v1 réel → kwc correct + panneau au bon wattage (tests). Files: `apps/ventes/services.py`, tests ventes. (ROUTINE) (@lane: backend/ventes-devis3d) (@model: sonnet)
- [x] PV15 — **Garde de statut sur `replace-lines` + produits globaux** : l'endpoint remplace aujourd'hui les lignes d'un devis ACCEPTÉ sans un mot et refuse les produits `company__isnull=True` que `_pick_product` accepte — refuser hors brouillon/envoyé (409 FR nommant le statut), accepter les produits globaux. **Done =** accepté → 409 ; brouillon → OK ; produit global accepté ; tests. Files: `apps/ventes/views/devis.py`, tests ventes. (ARCH) (@lane: backend/ventes-devis3d) (@model: opus)
- [x] PV16 — **`cible_depuis_lignes(devis)` — lire le devis, pas la facture** : compte panneaux (Σ quantités lignes panneau), kWc, wattage dominant (fiche PV6 puis parse_watt puis kwc×1000/n puis 550), scénario batterie/réseau par la classification partagée ; avertissements FR (0 panneau, wattage illisible, 2 modèles → delta appliqué à la plus grosse ligne seulement). **Done =** fonction pure testée sur les 4 cas d'avertissement. Files: `apps/ventes/services.py`, tests ventes. (ROUTINE) (@after: PV14) (@lane: backend/ventes-devis3d) (@model: sonnet)
- [x] PV17 — **`GET /ventes/devis/{id}/design-context/`** : sélecteur agrégé `contexte_conception_devis` + vue à UN SEUL return portant TOUTES les clés du contrat PV1 ; geometrie = roof_layout du devis sinon pin/outline du lead sinon null ; modifiable=false + raison FR pour statut figé / agricole / multi-villa (groupe_index) ; carte = roof-config. **Done =** contrat PV1 respecté clé pour clé (check_api_shapes vert), les 3 raisons de lecture seule testées. Files: `apps/ventes/selectors.py`, `apps/ventes/views/devis.py`, tests ventes. (ARCH) (@after: PV1, PV16) (@lane: backend/ventes-devis3d) (@model: opus)
- [x] PV18 — **`POST /ventes/devis/{id}/sync-layout/` — synchro chirurgicale** : `sync_devis_from_layout` sous `select_for_update` : brouillon → MAJ quantité des lignes panneau + batterie ajoutée/retirée selon scenario (prix/remises/sections/ordre/groupe INTACTS, jamais un produit re-choisi ; 0 ligne panneau → création via _pick_product) + roof_layout/layout_hash/etude_params (puissance_kwc/production_annuelle/economies/toiture SEULEMENT) ré-enregistrés ; hash identique → 200 {"inchange":true} ; envoyé → 409 + {revision_possible:true} ; figé → 409 lecture seule. AUCUN statut jamais écrit. **Done =** les 4 statuts testés, double-clic gratuit, produits globaux OK. Files: `apps/ventes/services.py`, `apps/ventes/views/devis.py`, tests ventes. (ARCH) (@after: PV16) (@lane: backend/ventes-devis3d) (@model: opus)
- [ ] PV19 — **`hydrateFromDevis` + boot `hydrate.devis`** : fonction pure à côté de `hydrateFromLead` ; `applyDevisHydration` sème les zones via `deserializeLayout` ET impose `neededPanels = cible.panneaux ; neededAuto = false` — le chaînon qui fait « partir des éléments du devis » (l'optimiseur pose LE NOMBRE DEVISÉ, il ne le redérive plus de la facture) ; wattage/scénario épinglés depuis la cible ; boot lead strictement inchangé sans `hydrate.devis`. **Done =** hydratation devis testée (zones + cible imposée), mode lead golden inchangé. Files: `apps/web/src/scripts/roofPro11/prefill.ts`, `apps/web/src/scripts/roofPro11/types.ts`, `apps/web/src/scripts/roof-tool-pro11.ts`, tests apps/web. (ARCH) (@after: PV13) (@lane: appsweb/builder-core) (@model: opus)
- [ ] PV20 — **Route `/ventes/devis/:id/design` + mode devis de ToitureDesign** : frère de `/ventes/devis/:id/3d` (le viewer reste) ; boot sur design-context (UN appel), `hydrate.devis`, bandeau lecture seule renvoyant vers /3d quand modifiable=false ; mode lead `/devis-design/:id` STRICTEMENT inchangé ; test vitest important la fixture de contrat (PACT13, `reponseContrat('ventes','devis_design_context')` — jamais un PAYLOAD tapé main). **Done =** les deux modes bootent, lecture seule testée. Files: `frontend/src/router/index.jsx`, `frontend/src/pages/ventes/ToitureDesign.jsx`, `frontend/src/api/ventesApi.js`, tests. (ARCH) (@after: PV17, PV19, PV78) (@lane: frontend/ventes-design) (@model: opus)
- [ ] PV21 — **Boucle de finalisation mode devis** : bouton « Enregistrer la conception » → sync-layout + snapshot 3D → roof-image ; 409 revision_possible → encart « Réviser (v2) » appelant `/reviser/` puis rouvrant le designer sur la nouvelle version ; succès → liens proposition/WhatsApp comme en mode lead. **Done =** cycle complet brouillon, cycle réviser sur envoyé, e2e-hooks préservés. Files: `frontend/src/pages/ventes/ToitureDesign.jsx`, `frontend/src/api/ventesApi.js`, tests. (ARCH) (@after: PV17, PV18, PV20, PV78) (@lane: frontend/ventes-design) (@model: opus)
- [ ] PV22 — **Générer-si-absent + chip conception sur le lead** : l'action `toiture-3d` du workspace lead RÉSOUT au lieu de naviguer en dur — GET devis?lead=&statut=brouillon : 1 → /design ; ≥2 → sélecteur (référence · kWc · date) ; 0 → POST devis/auto (build_devis_auto), 422 → message FR serveur + bouton « Ouvrir le générateur » (/ventes/devis/nouveau?lead=) ; ET la chip « kWc conçu » + vignette roof_image sur IdentityRail (données PV78). **Done =** les 4 branches testées + chip conditionnelle testée. Files: `frontend/src/features/crm/workspace/IdentityRail.jsx`, `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `frontend/src/features/ventes/ChoisirDevisPourDesign.jsx`, `frontend/src/api/ventesApi.js`, tests. (ROUTINE) (@after: PV17, PV20, PV78) (@lane: frontend/crm-entrees) (@model: sonnet)
- [ ] PV23 — **Entrées « Concevoir en 3D » côté ventes** : action de ligne DevisList + panneau détail : brouillon/envoyé → /design, figé → /3d ; le raccourci de DevisGenerator pointe sur le devis en cours plutôt que sur le lead. **Done =** entrées visibles par statut, navigation testée. Files: `frontend/src/pages/ventes/DevisList.jsx`, `frontend/src/pages/ventes/DevisGenerator.jsx`, tests. (ROUTINE) (@after: PV17, PV20, PV78) (@lane: frontend/ventes-liste) (@model: sonnet)
- [ ] PV24 — **Gardes règle #4 : la v2 n'altère ni PDF ni page publique** : builder.py:728-736 écrase puissance_kwc depuis result.kwc (chemin mort qui S'ALLUME avec la v2) — verrouiller nombre de pages, totaux, chaîne de statuts ; vérifier `_safe_roof_layout` (aucun prix/savings ne fuit par result vers le public). **Done =** tests golden pages/totaux + liste blanche publique. Files: `apps/ventes/tests/test_quote_engine.py`, `apps/ventes/tests/test_qx41_public_hardening.py`. (ARCH) (@after: PV13, PV14) (@lane: backend/ventes-devis3d) (@model: opus)

**ÉDITION MANUELLE — roofPro11 :**
- [ ] PV25 — **Multi-sélection + rangées + azimut** : marquee shift-drag (rectangle ENU via screenToENU, 2D map — JAMAIS un raycast three.js parallèle), mode sélection tactile ; déplacement de groupe tout-ou-rien (movePanelToPoint par membre) ; drag de rangée (cellules même cy±ε, delta contraint à l'axe) ; contrôle « nudge azimut » du panneau layout → recompute existant + re-snap `reenterCustomLayout` (gratuit). **Done =** marquee/groupe/rangée/azimut testés, mode 1-panneau inchangé. Files: `apps/web/src/scripts/roofPro11/layoutEditor.ts`, `apps/web/src/lib/layoutVariability.ts`, `apps/web/src/pages/preview/toiture-3d-pro-11.astro`, tests apps/web. (ROUTINE) (@lane: appsweb/editor) (@model: sonnet)
- [ ] PV26 — **Undo/redo + nudge clavier** : pile de commandes PAR INSTANTANÉS (copie du Set occupied — jamais des inverses manuscrits), profondeur ~50 en anneau, redo purgé sur action neuve, Ctrl+Z/Y + boutons + flèches = nudge ; branché aux call-sites existants (renderCustomLayout/renderLayoutPanel). **Done =** séquences undo/redo testées y compris après group-move. Files: `apps/web/src/scripts/roofPro11/layoutEditor.ts`, `apps/web/src/scripts/roofPro11/layoutHistory.ts`, `apps/web/src/pages/preview/toiture-3d-pro-11.astro`, tests. (ROUTINE) (@after: PV25) (@lane: appsweb/editor) (@model: sonnet)
- [ ] PV27 — **FIX perte des placements manuels (3 chemins prouvés)** : `SerializedZoneGeometry.panels` exporte `grid.panels.slice(0, count)` — une tranche contiguë naïve, PAS le vrai Set occupied (un toit éclairci à la main part au devis/PDF comme un remplissage bête) ; `deserializeLayout` nullifie result/renderPlan ; `setLayoutMode(true)` repart de l'optimum. Exporter la VRAIE liste de cellules occupées dans geometry.panels, hydrater `ctx.layoutState` au boot par le re-snap `nearestEmptyCell` existant, préserver l'état à la réouverture du mode. **Done =** test round-trip identité sur un motif NON contigu (panneau 12 retiré, 47 gardé), export = état réel. Files: `apps/web/src/scripts/roofPro11/prefill.ts`, `apps/web/src/scripts/roofPro11/layoutEditor.ts`, `apps/web/src/scripts/roofPro11/types.ts`, tests apps/web. (ARCH) (@after: PV13, PV26) (@lane: appsweb/builder-core) (@model: opus)
- [ ] PV28 — **Avertir avant d'écraser l'édition manuelle** : `hasManualEdits()` (divergence occupied vs resetToOptimal) ; toute relance d'auto-layout/changement d'axe qui purgerait l'édition → confirmation FR AVANT commit — pas de concept « panneaux verrouillés » (sur-ingénierie). **Done =** confirm affiché seulement si divergence, refus = état intact. Files: `apps/web/src/scripts/roof-tool-pro11.ts`, `apps/web/src/scripts/roofPro11/layoutEditor.ts`, tests. (ROUTINE) (@after: PV26) (@lane: appsweb/editor) (@model: sonnet)

**ÉDITION MANUELLE — studio AO (plan imposé, rangée par rangée, serveur juge) :**
- [x] PV29 — **Mode `rangees_imposees_utilisateur` dans le moteur** : `ModePose.RANGEES_IMPOSEES_UTILISATEUR` + `Parametres.rangees_imposees: Optional[Tuple[Tuple[float,str],...]]` ; `optimum.calculer()` 3e branche → `evaluer_plan_impose` EXISTANT (optimum.py:163-185 — mêmes contraintes compter_plan, preuve.methode=IMPOSE_UTILISATEUR, optimal=False, ecart honnête) ; refus `EntreeInvalide` si vide ; round-trip serialisation additive (~4 lignes). Granularité RANGÉE assumée (y0+kit) ; le drag par table individuelle = Phase 2 nommée hors périmètre. **Done =** plan imposé évalué avec preuve honnête, vocabulaire de preuve testé, serialisation round-trip. Files: `core/calepinage/types.py`, `core/calepinage/optimum.py`, `core/calepinage/serialisation.py`, tests core. (ARCH) (@after: PV3) (@lane: backend/core-calepinage) (@model: opus)
- [ ] PV30 — **Passage `rangees_imposees` + `phase_forcee_m` dans l'API AO** : `parametres_vers_document` passe les deux clés ; vérifier (pas supposer) que les serializers de demande acceptent le dict params opaque ; AUCUN nouveau endpoint — calculer/lancer réutilisés ; persistance = `lancer(persister:true, role:'ALTERNATIVE')` (la garde `raisons_de_non_publiabilite` refuse déjà publiable quand total<optimal = LE verdict rouge, réutilisé tel quel). **Done =** un POST calculer en mode imposé rend le plan évalué + phase forcée transmise, tests API. Files: `apps/ao/calepinage_io.py`, tests ao. (ROUTINE) (@after: PV29, PV52) (@lane: backend/ao) (@model: sonnet)
- [ ] PV31 — **Édition de rangées dans le studio (drag/ajout/suppression, serveur juge)** : affordances interactives sur PlanLayer (aujourd'hui rects morts) — brouillon local `rangeesImposees` semé de `resultat.plans[].rangees` au premier geste, l'overlay ne montre que la LIGNE proposée (AOF92/94 : jamais une table inventée côté front) ; chaque geste → majParametres({mode_pose, rangees_imposees}) → debounce 350 ms → recalcul serveur → PlanLayer redessine les VRAIES tables ; pile undo/redo locale (instantanés du brouillon) ; `perime` couvre le grisé. **Done =** drag/ajout/suppression de rangée round-trip serveur testés, aucun chiffre front. Files: `frontend/src/features/ao/calepinage/PlanLayer.jsx`, `frontend/src/features/ao/calepinage/CalepinageStudio.jsx`, `frontend/src/features/ao/calepinage/useCalepinageImpose.js`, tests. (ARCH) (@after: PV12, PV30, PV54, PV68) (@lane: frontend/ao-calepinage) (@model: sonnet)
- [ ] PV32 — **Violations en rouge + « Enregistrer comme variante »** : motifs FR du serveur verbatim, rangée/obstacle fautif surligné ; bouton → lancer(persister:true, role:'ALTERNATIVE') puis promotion via `retenir` existant ; avertissement avant qu'un changement de tiroir ne purge un brouillon divergent (isDraftDirty). **Done =** violation visible et nommée, variante persistée, garde anti-écrasement testée. Files: `frontend/src/features/ao/calepinage/VerdictBar.jsx`, `frontend/src/features/ao/calepinage/CalepinageStudio.jsx`, tests. (ROUTINE) (@after: PV12, PV31, PV54, PV68) (@lane: frontend/ao-calepinage) (@model: sonnet)

**CHAÎNE ÉLECTRIQUE + SCHÉMA UNIFILAIRE (noyau pur `core/electrique/`) :**
- [x] PV33 — **Squelette du noyau électrique pur** : `core/electrique/{__init__,types,version}.py` — dataclasses gelées (SpecModule, SpecOnduleur, EntreeElectrique, Chaine, Protection, Cable, ResultatElectrique), SCHEMA_VERSION/VERSION_MOTEUR (miroir calepinage) ; contrat import-linter `electrique-est-un-noyau-pur` + test de pureté AST (miroir test_calepinage_purete) — stdlib seulement, zéro Django, zéro I/O. **Done =** lint-imports vert, pureté testée. Files: `core/electrique/__init__.py`, `core/electrique/types.py`, `core/electrique/version.py`, `core/tests/test_electrique_purete.py`, `.importlinter`. (ARCH) (@lane: backend/core-electrique) (@model: opus)
- [x] PV34 — **chaines.py + onduleurs.py : physique + politique réconciliées** : logique `string_design` déplacée verbatim (fenêtre Voc@froid < Vmax / Vmp@chaud > MPPT min, répartition MPPT) + groupement par orientation ; hook « longueur forcée » : la physique calcule [min,max] admissible, une politique (ex. 16 modules, convention dossier) ne peut forcer QUE dedans, refus motivé sinon ; LA contradiction ratio réglée : UNE SEULE computation publie `ratio_dc_ac` ET `ratio_ac_dc`, chacun avec ses bornes nommées. Le shim `solar_design.string_design` vit dans PV83 (côté ventes). **Done =** logique portée à l'identique (mêmes cas de test que string_design), ratio double publié, tests fenêtre froid/chaud. Files: `core/electrique/chaines.py`, `core/electrique/onduleurs.py`, tests core. (ARCH) (@after: PV33) (@lane: backend/core-electrique) (@model: opus)
- [x] PV35 — **protections.py : le règlement encodé** : fusibles de chaîne (requis si ≥3 strings parallèles ; In ∈ [1,5 ; 2,4]×Isc et ≥1,25×Isc), parafoudre DC type 2 (liaison >10 m ou zone kéraunique), sectionneur DC, disjoncteur AC (calibre depuis Ib), parafoudre AC, DDR type A 300 mA (régime TT défaut), mise à la terre — CHAQUE constante porte sa source (NF C 15-100 / UTE C 15-712-1 / IEC 62548) en commentaire, zéro chiffre inventé. **Done =** chaque règle testée aux bornes (2 vs 3 strings, 9 vs 11 m). Files: `core/electrique/protections.py`, tests core. (ROUTINE) (@after: PV33) (@lane: backend/core-electrique) (@model: sonnet)
- [x] PV36 — **cables.py : ampacité + chute de tension** : table Iz (H1Z2Z2-K côté DC), solveur de chute (≤3 % DC — cible 1,5 % —, 1-2 % AC), vérification Ib ≤ In ≤ Iz, proposition de section par liaison (montée en section jusqu'à respect de la cible). **Done =** solveur testé (section proposée croît avec la longueur), sources en commentaire. Files: `core/electrique/cables.py`, tests core. (ROUTINE) (@after: PV33) (@lane: backend/core-electrique) (@model: sonnet)
- [x] PV37 — **nomenclature.py : le BOQ nourri par le vrai design** : logique `generate_boq` portée et re-nourrie par protections+cables (calibres de fusibles réels, sections réelles) ; quantités + specs SEULEMENT — jamais un prix, jamais `prix_achat`. Le shim `solar_design.generate_boq` vit dans PV83. **Done =** BOQ reflète protections/câbles calculés, tests core. Files: `core/electrique/nomenclature.py`, tests core. (ROUTINE) (@after: PV34, PV35, PV36) (@lane: backend/core-electrique) (@model: sonnet)
- [x] PV38 — **`concevoir()` + note de calcul FR** : l'orchestrateur unique — entrée (specs module/onduleur, groupes par pan, longueurs dc_m/ac_m, phases, régime, batterie, températures −5/70 °C défauts, contraintes) → ResultatElectrique complet {chaines, conformite, protections, cables, bom, note, projection `tiroirs` aux 12 clés AO verbatim} ; note.py = une ligne générée par nombre, zéro littéral (style note_de_calcul calepinage). **Done =** design complet golden sur 3 cas (mono réseau / tri / hybride batterie), projection tiroirs conforme au contrat PV3. Files: `core/electrique/__init__.py`, `core/electrique/note.py`, tests core. (ARCH) (@after: PV37) (@lane: backend/core-electrique) (@model: opus)
- [x] PV39 — **schema.py : le schéma unifilaire v2** : rendu SVG paramétrique de la chaîne canonique complète (fusibles conditionnels, SPD DC selon règle 10 m, sectionneur, MPPT multiples, branche batterie, DDR, compteurs, terre), tableau « nomenclature » à côté du schéma (généré des MÊMES listes protections/cables — schéma et table ne peuvent pas diverger), cartouche (client, réf devis, kWc, date, indice), mono/tri, A4/A3 paysage, override optionnel {x,y} par composant (~30 lignes — pas d'éditeur libre). Le shim `single_line_diagram.py` vit dans PV83. **Done =** SVG golden 3 cas, table=schéma prouvé. Files: `core/electrique/schema.py`, tests core. (ROUTINE) (@after: PV38) (@lane: backend/core-electrique) (@model: sonnet)
- [ ] PV83 — **Shims de ré-export ventes (précédent ARC6)** : `solar_design.string_design`/`generate_boq` et `single_line_diagram.py` deviennent des shims bit-identiques sur `core.electrique` — leurs ~20 tests existants restent verts SANS modification ; les endpoints schéma existants inchangés. **Done =** tests existants verts sans édition, imports core prouvés (lint-imports vert). Files: `apps/ventes/solar_design.py`, `apps/ventes/single_line_diagram.py`, tests ventes. (ARCH) (@after: PV34, PV37, PV39) (@lane: backend/ventes-electrique) (@model: opus)
- [ ] PV40 — **SLD en PDF** : `?format=pdf` sur les deux endpoints schéma existants, rendu via `core.pdf.render_pdf` (ARC11 — jamais un import weasyprint direct ; vérifier `python scripts/check_platform.py`). **Done =** PDF A4/A3 téléchargeable, check_platform vert. Files: `apps/ventes/diagram_views.py`, tests ventes. (ROUTINE) (@after: PV83) (@lane: backend/ventes-electrique) (@model: sonnet)
- [ ] PV41 — **`Devis.electrical_design` + endpoints conception électrique** : migration additive `electrical_design` (JSONField null) + `electrical_design_hash` (CharField 64 indexé — SHA-256 de layout_hash+specs+longueurs+phases, régénération idempotente pattern QJ17) ; `apps/ventes/electrical_service.py` + `GET/POST /ventes/devis/<id>/conception-electrique/` (POST = recalcul avec overrides), company-scoped, contrat PV2 clé pour clé (@action du DevisViewSet — aucun changement d'urls.py). **Done =** contrat vert, idempotence par hash testée, migration revertable. Files: `apps/ventes/electrical_service.py`, `apps/ventes/models.py`, `apps/ventes/migrations/`, `apps/ventes/views/devis.py`, tests. (SCHEMA) (@after: PV2, PV6, PV38) (@lane: backend/ventes-electrique) (@model: sonnet)
- [ ] PV42 — **Finalisation 3D → design électrique par pan + kit-produit villa** : dans `build_devis_from_layout`/`sync_devis_from_layout`, dériver les groupes de strings PAR PAN depuis `_pans_geometry` (JAMAIS deux orientations sur un même MPPT — faute de conception réelle) → `concevoir()` → persister ; layout sans géométrie → comportement historique strictement inchangé ; AUSSI : `compte_moteur_du_layout` résout le produit panneau du devis et le passe à `calepinage_villa` (paramètre livré par PV12). **Done =** devis 2 pans → 2 groupes jamais mélangés (test), sans géométrie inchangé, kit-produit transmis (test). Files: `apps/ventes/services.py`, tests ventes. (ARCH) (@after: PV12, PV18, PV41) (@lane: backend/ventes-devis3d) (@model: opus)
- [ ] PV43 — **Panneau électrique du devis (front)** : sur le panneau détail devis : résumé de conformité (vert/bloquants FR), table des strings par MPPT, aperçu SLD + téléchargement PDF, overrides paramètres + les DEUX longueurs de câble (`step="any"`, `noValidate`, défauts dc_m = max(10, n_strings×20) / ac_m = 15, jamais happées), « Recalculer » → POST conception-electrique ; test vitest sur la fixture de contrat PV2. **Done =** panneau monté et joignable (fichier de montage nommé), overrides round-trip. Files: `frontend/src/features/ventes/ConceptionElectrique.jsx`, `frontend/src/pages/ventes/DevisList.jsx`, `frontend/src/api/ventesApi.js`, tests. (ROUTINE) (@after: PV17, PV41, PV78) (@lane: frontend/ventes-electrique) (@model: sonnet)
- [ ] PV44 — **Le tiroir Électrique AO s'allume** : publier `tiroirs.electrique` (12 clés du contrat PV3) depuis `calepinage_service` — `core.electrique` pour la physique + le plafond 60 kWc de `core/calepinage/electrique.py` EXISTANT (qui reste tel quel, golden FRDISI épinglé) ; `conformite.repartition_proposee.patch` = un patch_entree que majParametres REJOUE (le moteur re-vérifie, jamais confiance aveugle). ZÉRO changement frontend (TiroirElectrique.jsx s'allume seul). **Done =** calculer publie tiroirs.electrique conforme au contrat, patch rejouable testé. Files: `apps/ao/calepinage_service.py`, `apps/ao/calepinage_serializers.py`, tests ao. (ARCH) (@after: PV3, PV38) (@lane: backend/ao) (@model: opus)
- [ ] PV45 — **Schéma unifilaire → dossier réglementaire** : `regulatory_docs.py:30` déclare DÉJÀ la pièce `schema_unifilaire` (générée par generer-checklist, jamais fournie) — action `POST /dossiers-reglementaires/<id>/generer-schema/` : rendre le SLD PDF → MinIO `ventes/{company_id}/{uuid}.pdf` (SCA42) → attacher via `records.Attachment` (ARC26) → basculer l'item checklist à `fourni` ; idempotent (@action du ViewSet dossiers — aucun changement d'urls.py). **Done =** pièce fournie + attachée, re-run sans doublon, scoping société testé. Files: `apps/ventes/views/regulatory.py`, tests. (ROUTINE) (@after: PV40, PV41) (@lane: backend/ventes-electrique) (@model: sonnet)
- [ ] PV46 — **PDF premium : annexe technique optionnelle (photo toit + SLD)** : flag `include_annexe_technique` dans DEFAULT_PDF_OPTIONS + liste blanche clean_pdf_options, défaut OFF ; page annexe (photo `roof_image` + schéma unifilaire + table nomenclature) splicée comme la page étude (INCLUDE_ETUDE, PAGES_TOTAL, build_html) ; design/image absents → page omise, PDF octet-identique (dégradation 4→3 du précédent include_etude) ; le moteur REND seulement (règle #4). **Done =** assertions de nombre de pages ON/OFF/dégradé, totaux inchangés. Files: `apps/ventes/quote_engine/builder.py`, `apps/ventes/quote_engine/generate_devis_premium.py`, `apps/ventes/tests/test_quote_engine.py`. (ARCH) (@after: PV41) (@lane: backend/ventes-quotepdf) (@model: opus)
- [ ] PV47 — **BOQ électrique → lignes annexes du devis (opt-in)** : action explicite « Ajouter le BOQ électrique » : mappe la nomenclature PV37 sur le catalogue (catégories Câbles / Protection & accessoires) → LigneDevis créées EXPLICITEMENT (jamais silencieux) ; aucun SKU correspondant → ligne annexe « à chiffrer » SANS prix inventé (précédent pompes OSP) + flag de trou catalogue remonté. **Done =** lignes créées sur clic seulement, à-chiffrer sans prix, tests. Files: `apps/ventes/services.py`, `apps/ventes/views/devis.py`, tests. (ROUTINE) (@after: PV41) (@lane: backend/ventes-electrique) (@model: sonnet)

**STUDIO AO COMPLET (tiroirs, suggestions, persistance, zones, carte, liste) :**
- [x] PV48 — **`core/calepinage/tiroirs.py` : les 4 tiroirs calculés** : `donnees_tiroirs(entree, resultat, catalogue)` pur — kits (catalogue + granularité `site` seule — le moteur n'a pas de kit-par-segment, ne pas l'inventer ; contre-épreuve via optimiser_economique par kit candidat ; approvisionnement.confirme=false, aucun signal n'existe), allées (presets de chercher_allee_gratuite + graphe aux clés qu'AlleeGratuiteChart consomme — vérifier son contrat), rives (impacts à ancres PLAFONNÉES : courant, ±0,05, ±0,10 ; variante conservatrice 1,50/0,50/0,50 recalculée), orientation (verifier_kit par Axe × kit, ErreurOrientation → disponible=false + motif_orientation verbatim). **Done =** conforme au contrat PV3, coût borné testé. Files: `core/calepinage/tiroirs.py`, tests core. (ROUTINE) (@after: PV3) (@lane: backend/core-calepinage) (@model: sonnet)
- [ ] PV49 — **Publier tiroirs + marges + garde de coût** : `calepiner()` attache `sortie['tiroirs']` (PV48) et `sortie['marges']` ({troncon_min_cm, bande_min_cm, rangee_critique, obstacle_critique} depuis marges_globales DÉJÀ calculé — non mesuré = null jamais 0) ; serializers imbriqués (PACT7 honnêteté de schéma) ; GARDE DE COÛT : le pré-vol `cout_estime()` intègre le multiplicateur tiroirs OU les tiroirs dégradent à null au-delà d'un seuil de taille — la promesse synchrone/202 jamais cassée en silence. **Done =** RobustesseBadges et 4 tiroirs s'allument sur données réelles, budget 202 testé. Files: `apps/ao/calepinage_service.py`, `apps/ao/calepinage_io.py`, `apps/ao/calepinage_serializers.py`, tests ao. (ROUTINE) (@after: PV48) (@lane: backend/ao) (@model: sonnet)
- [ ] PV50 — **Publier les suggestions (action discriminée)** : `proposer()` (recommandations.py, réel, jamais routé) plié dans `calepiner()` par surface, fusion/plafond global ; `recommandations_vers_json` émet l'action DISCRIMINÉE du contrat PV3 — {type:"parametres", patch en vocabulaire PARAMS (allee_min_m…)} vs {type:"obstacle", provenance} (ecarter/confirmer = mutation de provenance via le CRUD obstacles, PAS un param) ; la suppression de l'entrée `nonConstruit` d'aoApi vit dans PV51. **Done =** suggestions publiées aux deux types, traduction vocabulaire testée. Files: `apps/ao/calepinage_service.py`, `apps/ao/calepinage_io.py`, `apps/ao/calepinage_serializers.py`, tests ao. (ROUTINE) (@after: PV49) (@lane: backend/ao) (@model: sonnet)
- [ ] PV51 — **Le studio consomme tout** : retirer le bandeau « tiroirs absents » (CalepinageStudio.jsx:233-238) ; `appliquerSuggestion` branche sur action.type (parametres → majParametres ; obstacle → aoApi.obstacles.update puis recalcul) ; suppression de l'entrée nonConstruit dans aoApi.js ; côté ModeExpert : le champ phase_m agit enfin (PV52) et le champ mort `rangee_forcee` (zéro référence backend) est SUPPRIMÉ avec son test (AOF94) ; bouton « Générer des variantes » appelant l'endpoint PV67 (l'UI de comparaison EXISTE, PACT171/172). **Done =** 5 tiroirs + badges + suggestions vivants sur fixture de contrat (PACT13), les deux types d'action appliqués, champ mort retiré, bouton variantes testé. Files: `frontend/src/features/ao/calepinage/CalepinageStudio.jsx`, `frontend/src/features/ao/calepinage/ModeExpert.jsx`, `frontend/src/api/aoApi.js`, tests. (ROUTINE) (@after: PV12, PV44, PV50, PV52, PV54, PV67, PV68) (@lane: frontend/ao-calepinage) (@model: sonnet)
- [x] PV52 — **`phase_forcee_m` réel côté moteur** : `Parametres.phase_forcee_m` + `balayer_phase` évalue SEULEMENT cette phase quand posée (aujourd'hui il balaie toujours) + serialisation round-trip. Le passage API (`parametres_vers_document`) vit dans PV30 ; le nettoyage front (ModeExpert) vit dans PV51. **Done =** phase forcée respectée (test moteur), serialisation round-trip. Files: `core/calepinage/types.py`, `core/calepinage/pose_uniforme.py`, `core/calepinage/serialisation.py`, tests core. (ROUTINE) (@after: PV29) (@lane: backend/core-calepinage) (@model: sonnet)
- [ ] PV53 — **L'atelier de traçage PERSISTE enfin obstacles + chaînes** : sur « Enregistrer », diff de l'état local contre `aoApi.obstacles.list({toiture})`/`aoApi.chaines.list({toiture})` → create/update/delete dans LA MÊME action que l'écriture du contour (un Enregistrer = une sauvegarde cohérente, jamais partielle silencieuse) ; mapping exact rectX0M/sommets → rect_x0_m/polygone_local_m (vérifier les listes de champs serializer avant d'implémenter). **Done =** fermer/rouvrir l'atelier conserve tout, test du diff 3 voies. Files: `frontend/src/features/ao/toiture/ToituresPage.jsx`, tests. (ROUTINE) (@after: PV12, PV54, PV68) (@lane: frontend/ao-toiture) (@model: sonnet)
- [ ] PV54 — **`ZoneAO` : les zones ont enfin un modèle** : company FK, toiture FK, repere, nature (miroir de core NatureZone : ENVELOPPE/INTERDITE/RESERVEE/PREFEREE), sommets JSON, hauteur_m null, retrait_m défaut 0 ; serializer + ViewSet scopé (AO_VOIR/AO_GERER) + url. Le client `aoApi.zones` vit dans PV56. **Done =** CRUD scoping société testé, migration additive. Files: `apps/ao/models.py`, `apps/ao/migrations/`, `apps/ao/serializers.py`, `apps/ao/views.py`, `apps/ao/urls.py`, tests. (SCHEMA) (@lane: backend/ao) (@model: sonnet)
- [ ] PV55 — **Les zones atteignent le moteur** : `zones_vers_document(toiture)` remplace le `document['zones'] = []` durci de calepinage_io.py:330 — INTERDITE/RESERVEE = intervalles bloqués (chemin obstacles identique), PREFEREE = tie-break jamais compteur (propriété déjà prouvée moteur). **Done =** une zone interdite réduit le compte (test), une préférée ne le change jamais. Files: `apps/ao/calepinage_io.py`, tests ao. (ROUTINE) (@after: PV54) (@lane: backend/ao) (@model: sonnet)
- [ ] PV56 — **Zones persistées depuis l'atelier** : `aoApi.zones` créé (remplacer la note « retiré ») et OutilsZones cesse d'être orphelin — même pattern de diff-save que PV53 ; les zones sauvées arrivent au studio de calepinage via le recalcul serveur. **Done =** zone tracée → persistée → compte modifié au studio, tests. Files: `frontend/src/features/ao/toiture/OutilsZones.jsx`, `frontend/src/features/ao/toiture/ToituresPage.jsx`, `frontend/src/api/aoApi.js`, tests. (ROUTINE) (@after: PV12, PV54, PV68) (@lane: frontend/ao-toiture) (@model: sonnet)
- [ ] PV57 — **Origine géographique de la toiture** : champs additifs `ToitureAO.origine_lat/origine_lng` (Decimal null) + serializer — le repère qui manquait pour appliquer un contour carte. **Done =** migration additive, champs exposés, tests. Files: `apps/ao/models.py`, `apps/ao/migrations/`, `apps/ao/serializers.py`, tests. (SCHEMA) (@lane: backend/ao) (@model: sonnet)
- [ ] PV58 — **La reprise carte s'applique enfin** : `repere.js` (AOF83) implémente DÉJÀ WGS84→ENU (creerRepere/lngLatVersMetres/contourVersSommetsM) — implémenter `onContour` de RepriseCarte dans l'onglet Import : repère depuis repere_latlng (sinon 1er sommet) + azimut = angle_nord_deg existant → majPoints(contour converti) ; persister origine_lat/lng avec le contour. **Done =** contour dessiné sur carte → tracé métrique dans l'atelier (test), origine persistée. Files: `frontend/src/features/ao/toiture/ToituresPage.jsx`, `frontend/src/features/ao/toiture/RepriseCarte.jsx`, tests. (ROUTINE) (@after: PV12, PV54, PV57, PV68) (@lane: frontend/ao-toiture) (@model: sonnet)
- [ ] PV59 — **Vraie liste des calepinages** : `/ao/calepinages` cesse d'être un EmptyState — `VariantesListPage` sur `aoApi.variantes.list()` (filtres ?appel_offre/?toiture/?statut/?role, badges statut_display, raisons de non-publiabilité visibles), clic → studio de la toiture ; ET la ligne « Synthèse » multi-toitures dans l'onglet Calepinages d'AffaireDetail (données PV68). **Done =** liste filtrable + synthèse affichée, tests navigation. Et l'écran est ATTEIGNABLE : route déclarée + entrée de nav (ou onglet monté dans son écran parent). Files: `frontend/src/features/ao/calepinage/VariantesListPage.jsx`, `frontend/src/features/ao/AffaireDetail.jsx`, `frontend/src/features/ao/module.config.jsx`, tests. (ROUTINE) (@after: PV12, PV54, PV68) (@lane: frontend/ao-calepinage) (@model: sonnet)

**AUTO-LAYOUT PLUS FORT (les deux moteurs) :**
- [ ] PV60 — **FIX : l'obstacle testé au centre du panneau seulement** : estimatorBrainV2:1045 / V3:593 ne testent que le CENTRE — un coin peut mordre l'obstacle ou sa marge. Tester les 4 coins (ou distance signée min du rect tourné). Changement de comptes en production non flaggée (/devis-design + capture publique) : produire un diff avant/après sur un jeu de fixtures, pas seulement des tests unitaires. **Done =** coin mordant détecté (test), diff de fixtures documenté au DONE LOG. Files: `apps/web/src/lib/estimatorBrainV2.ts`, `apps/web/src/lib/estimatorBrainV3.ts`, tests apps/web. (ARCH) (@lane: appsweb/optimizer) (@model: sonnet)
- [ ] PV61 — **Dégagement par TYPE d'obstacle (roofPro11)** : l'obstacle gagne un `type` (sous-ensemble des 13 types AO : cheminée, ventilation, chien-assis, édicule, antenne…) + sélecteur dans obstaclesUi ; packers : clearanceByType[type] ?? OBSTACLE_CLEARANCE_M. **Done =** deux types → deux dégagements distincts (test). Files: `apps/web/src/scripts/roofPro11/types.ts`, `apps/web/src/scripts/roofPro11/obstaclesUi.ts`, `apps/web/src/lib/estimatorBrainV2.ts`, `apps/web/src/lib/estimatorBrainV3.ts`, tests. (ROUTINE) (@after: PV60) (@lane: appsweb/optimizer) (@model: sonnet)
- [ ] PV62 — **Mix portrait/paysage par bande de rangée (roofPro11)** : `packMixed()` — remplissage normal puis, par bande x libre contiguë de chaque rangée, essai local portrait vs paysage (primitive packCells restreinte au rectangle de bande), garde le plus dense ; 3e valeur d'axe `layout:'mixed'` + puce UI. Le cas marocain type : parapet/obstacle mange une rangée mais pas la suivante. **Done =** toiture-fixture où le mix bat les deux uniformes (test), axe exposé. Files: `apps/web/src/lib/estimatorBrainV2.ts`, `apps/web/src/scripts/roofPro11/optimizer.ts`, `apps/web/src/scripts/roof-tool-pro11.ts`, tests. (ARCH) (@after: PV60) (@lane: appsweb/optimizer) (@model: opus)
- [ ] PV63 — **Retraits de rive configurables (roofPro11)** : PERIMETER_SETBACK_M=0,5 durci + toggle binaire → entrées numériques latérale/extrémité/acrotère (discipline TiroirRives : avertir, JAMAIS rejeter/arrondir ; noValidate step=any). **Done =** 3 retraits distincts appliqués (test), entrée libre jamais happée. Files: `apps/web/src/lib/roofPro2.ts`, `apps/web/src/lib/estimatorBrainV2.ts`, `apps/web/src/lib/estimatorBrainV3.ts`, `apps/web/src/scripts/roof-tool-pro11.ts`, tests. (ROUTINE) (@after: PV60) (@lane: appsweb/optimizer) (@model: sonnet)
- [ ] PV64 — **3 cartes de variantes (roofPro11)** : au-dessus du canvas, 3 cartes sélectionnables issues du balayage fineGridMatrixV6 DÉJÀ calculé (sud max-densité / est-ouest / azimut aligné toit) — compte/kWc/kWh chacune ; clic → AxisLocks + re-rendu par le chemin solveLive existant. Une couche d'AFFICHAGE sur des données déjà produites, pas un nouveau solve. **Done =** 3 cartes cohérentes avec la matrice, sélection re-rend (test). Files: `apps/web/src/scripts/roofPro11/optimizer.ts`, `apps/web/src/lib/estimatorBrainV6.ts`, tests. (ROUTINE) (@lane: appsweb/optimizer) (@model: sonnet)
- [x] PV65 — **Anti-ombrage à la vraie latitude (moteur calepinage)** : `AntiOmbrage.elevation_deg` fige 21,0° (« la valeur du cerveau TS ») — porter la formule TS (déclinaison −23,44°, heure de design 10 h, latitude du site) en Python pur stdlib ; CHANGE LES COMPTES PUBLIÉS → bump MAJEUR de version.py + re-VÉRIFICATION (jamais remplacement silencieux) de chaque golden villa. **Done =** élévation varie avec la latitude (test), goldens re-vérifiés et notés au DONE LOG. Files: `core/calepinage/politique_pas.py`, `core/calepinage/version.py`, `core/calepinage/golden/villa/`, tests core. (ARCH) (@lane: backend/core-calepinage) (@model: opus)
- [ ] PV66 — **Kit villa Est-Ouest dos-à-dos** : `KIT_VILLA_EW` (modules_par_table=2, géométrie chevron miroir roofPro11) — AUCUN champ de dataclass nouveau (dos_a_dos/axe_rangee existent, la DP reste exacte) ; `adaptateurs/villa.py` gagne le choix de kit (composable avec le kit-produit PV12). **Done =** villa comparée S vs E-O par le moteur (test), défaut inchangé. Files: `core/calepinage/types.py`, `core/calepinage/adaptateurs/villa.py`, tests core. (ROUTINE) (@after: PV12) (@lane: backend/core-calepinage) (@model: sonnet)
- [ ] PV67 — **Variantes d'orientation auto-générées (AO, endpoint)** : `generer_variantes_orientation(toiture)` — 2-4 patchs (flip axe_rangee si verifier_kit l'autorise, swap kit dos-à-dos, kits mixtes) rejoués par `calculer_variante(role=ALTERNATIVE, parent=retenue)` — tous les comptes REJOUÉS par le vrai moteur, jamais estimés (discipline recommandations.py) ; endpoint d'action. Le bouton studio vit dans PV51. **Done =** appel → 2-4 ALTERNATIVE persistées visibles via comparer_variantes (test API). Files: `apps/ao/calepinage_service.py`, `apps/ao/calepinage_views.py`, tests. (ROUTINE) (@after: PV66) (@lane: backend/ao) (@model: sonnet)
- [ ] PV68 — **Vue agrégée multi-toitures d'une affaire (AO)** : sélecteur d'agrégat par affaire (Σ modules/kWc des variantes retenues par toiture, pattern anti-double-comptage des économies prouvé zones.ts:84-88) + ligne « Synthèse » dans l'onglet Calepinages d'AffaireDetail. PAS d'extension 2-D de la DP (l'optimalité cesserait d'être démontrée — optimum.py:17-24) : agrégat organisationnel seulement (sélecteur + exposition sur l'endpoint affaire). La ligne « Synthèse » UI vit dans PV59. **Done =** affaire 2 toitures → synthèse juste (test API). Files: `apps/ao/selectors.py`, tests ao. (ROUTINE) (@after: PV12, PV54) (@lane: backend/ao) (@model: sonnet)

**SIMULATION PVSYST-GRADE (étude bancable ancrée sur le DEVIS) :**
- [ ] PV69 — **`apps/ventes/etude.py` : le cœur P50/P90** : orchestrateur `run_bankable_study(devis, zones, load_curve, force_refresh)` — v1 : irradiance par zone (fetch_productible/fetch_irradiance_tmy, offline-safe hérité) → arbre de pertes → `simulate_bankable_yield` (PR, P50/P90/P75) mono-zone ; N'ÉCRASE JAMAIS production_annuelle/economies (la table 5 villes QX38 reste CANONIQUE pour l'écran/PDF — le bloc `simulation` est additif à côté) ; hors de quote_engine (règle #4). **Done =** simulation v1 conforme au contrat PV4 (clés pr.*), défauts de pertes documentés avec flags « à vérifier » existants. Files: `apps/ventes/etude.py`, tests ventes. (ROUTINE) (@after: PV4) (@lane: backend/ventes-etude) (@model: sonnet)
- [ ] PV70 — **Multi-zones + pont matrice d'ombrage** : agrégation multi-pans (Σ zones, chaque pan à son tilt/azimut) ; la matrice 12×24 de shadingUi (quand présente dans le layout) → scalaire de perte PONDÉRÉ par la production (jamais une moyenne plate) pour l'arbre + dérate horaire (tuiles mois×24 h AVANT hourly_self_consumption) ; sans matrice → `shading_analysis` en repli ; PVGIS printhorizon EXPLICITEMENT hors v1 (forme non vérifiée). **Done =** matrice réelle → perte pondérée + horaire (tests), repli testé. Files: `apps/ventes/etude.py`, tests ventes. (ROUTINE) (@after: PV69) (@lane: backend/ventes-etude) (@model: sonnet)
- [ ] PV71 — **La matrice d'ombrage voyage dans le layout v2** : sérialiser la matrice 12×24 de `ctx` (shadingUi) dans le layout (clé additive par zone `shading12x24` ou globale — suivre l'endroit où l'ombrage vit dans ctx) pour que le backend (PV70) la lise depuis `Devis.roof_layout` — PAS de modèle RoofLayout ressuscité, l'étude s'ancre sur le DEVIS. **Done =** round-trip sérialisation testé, taille bornée. Files: `apps/web/src/scripts/roofPro11/prefill.ts`, `apps/web/src/scripts/roofPro11/types.ts`, tests apps/web. (ROUTINE) (@after: PV13) (@lane: appsweb/builder-core) (@model: sonnet)
- [ ] PV72 — **Autoconso horaire → net-metering → projection 25 ans** : brancher hourly_self_consumption (courbe facture ou raffinée), net_metering_savings (tarifs tranches DÉJÀ flagués « à confirmer » — ne pas durcir), optimize_subscribed_power (industriel/commercial seulement), module_degradation_curve, tariff_escalation_projection (VAN/TRI) — le bloc `simulation` complet du contrat PV4. **Done =** schéma complet golden, clés historiques intactes. Files: `apps/ventes/etude.py`, tests ventes. (ROUTINE) (@after: PV69) (@lane: backend/ventes-etude) (@model: sonnet)
- [ ] PV73 — **Cache PVGIS système** : `core/cache.py` scope système (company None) — clé `pvgis:{lat,3}:{lon,3}:{tilt}:{az}` TTL 6 h ; TMY séparé TTL long (climatologie) ; aligner la précision d'arrondi sur prodPlaneKeyOf côté web pour ne pas dupliquer les entrées ; invalidation = force_refresh seulement (la physique ne change pas). **Done =** 2e appel même plan = zéro fetch (test), scope système prouvé. Files: `apps/ventes/etude.py`, tests ventes. (ROUTINE) (@after: PV69) (@lane: backend/ventes-etude) (@model: sonnet)
- [ ] PV74 — **`POST /ventes/devis/{id}/simuler/` async** : tâche Celery `ventes.simulate_bankable_study` (même forme que generate_devis_pdf : bind, retries, acks_late) ; l'action DevisViewSet rend 202 + job à sonder (pattern SCA41 existant) ; résultat persisté dans `etude_params['simulation']` ; recalcul explicite force_refresh (@action du DevisViewSet — aucun changement d'urls.py). **Done =** 202 → poll → simulation présente, idempotence cache. Files: `apps/ventes/tasks.py`, `apps/ventes/views/devis.py`, tests. (ROUTINE) (@after: PV72, PV73) (@lane: backend/ventes-etude) (@model: sonnet)
- [ ] PV75 — **Fenêtre de production : P50/P90 + cascade de pertes** : prodWindow affiche la ligne P50/P90 à côté du titre + mini-cascade des pertes (barres graphs.ts) quand une simulation existe — proxifiée (le navigateur n'appelle jamais Django-sim en direct, discipline roof-production). **Done =** affichage conditionnel testé, sans simulation inchangé. Files: `apps/web/src/scripts/roofPro11/prodWindow.ts`, `apps/web/src/scripts/roofPro11/graphs.ts`, tests apps/web. (ROUTINE) (@after: PV74) (@lane: appsweb/prod) (@model: sonnet)
- [ ] PV76 — **Carte « Étude bancable » du devis** : dans le panneau devis (DevisList inline — il n'existe PAS de DevisDetail séparé), carte lecture seule gated sur la présence de `simulation` : P50/P90, PR, cascade, payback rigoureux, VAN/TRI + bouton « Recalculer l'étude » (→ PV74) ; fixture de contrat PV4 (PACT13). **Done =** carte conditionnelle + recalcul round-trip testés. Files: `frontend/src/pages/ventes/DevisList.jsx`, `frontend/src/api/ventesApi.js`, tests. (ROUTINE) (@after: PV4, PV17, PV74, PV78) (@lane: frontend/ventes-liste) (@model: sonnet)
- [ ] PV77 — **PDF étude enrichi + P50 public** : builder.py fusionne `etude_params['simulation']` sous `etude['bankable']` SEULEMENT quand présent (absent → octet-identique, règle #4) + rendu template (ligne P50/P90, cascade) ; page publique /proposition : P50 seul (JAMAIS P90/P75 côté client — lecture assurantielle) + tendance 25 ans, jamais les internes de pertes ni VAN/TRI. **Done =** PDF ON/OFF octet-testé, liste blanche publique testée. Files: `apps/ventes/quote_engine/builder.py`, `apps/ventes/public_views.py`, `apps/ventes/tests/test_quote_engine.py`. (ARCH) (@after: PV72) (@lane: backend/ventes-quotepdf) (@model: opus)

**CÂBLAGE CRM/ERP (les artefacts irriguent tout l'outil) :**
- [ ] PV78 — **Le lead expose sa conception (backend)** : `apps/crm/selectors.py` gagne la donnée « conception du lead » (kWc conçu + clé roof_image du dernier devis à layout) via un sélecteur ventes (jamais ventes.models), exposée sur l'endpoint lead existant. La chip UI vit dans PV22. **Done =** sélecteur company-scoped testé, cross-app propre (lint-imports vert). Files: `apps/crm/selectors.py`, `apps/ventes/selectors.py`, tests. (ROUTINE) (@after: PV18) (@lane: backend/crm-wiring) (@model: sonnet)
- [ ] PV79 — **Événement `layout_finalise` + chatter lead** : signal core.events (devis, user) émis à la fin de from-layout ET sync-layout ; `crm/receivers.py` s'abonne → LeadActivity « Conception 3D finalisée — X kWc » (pattern devis_sent exact ; garde event_coverage : un signal = un abonné réel ET catalogué dans core/event_catalog.py — NTPLT12, sinon uncatalogued_events() rougit). **Done =** finalisation → note au chatter (test), coverage + catalogue verts. Files: `core/events.py`, `core/event_catalog.py`, `apps/ventes/views/devis.py`, `apps/crm/receivers.py`, tests. (ROUTINE) (@after: PV18) (@lane: backend/crm-wiring) (@model: sonnet)
- [ ] PV80 — **Le chantier hérite du schéma** : sur la création auto chantier-depuis-devis (devis_accepted), créer/rafraîchir le `DocumentProjet(type_doc='schema_unifilaire')` référencé — `assemble_handover_pieces()` le cherche DÉJÀ (toujours absent aujourd'hui) ; + étape seedée « Schéma électrique validé » au template checklist par défaut. **Done =** chantier créé → pièce handover présente + étape checklist visible, tests. Files: `apps/installations/services.py`, `apps/installations/migrations/`, tests installations. (ROUTINE) (@after: PV40) (@lane: backend/installations-wiring) (@model: sonnet)
- [ ] PV81 — **Schéma unifilaire client-safe sur la proposition** : bloc SLD (SVG géométrie seule, zéro prix — même discipline _safe_roof_layout) sur la page publique /proposition — l'élément de confiance technique que les concurrents montrent. **Done =** SVG servi par token, aucun prix dans le DOM (test). Files: `apps/ventes/public_views.py`, tests. (ROUTINE) (@after: PV39, PV41) (@lane: backend/ventes-electrique) (@model: sonnet)
- [x] PV82 — **KPI « conçu vs vendu »** : premier `kpi_providers` de `apps/ventes/platform.py` (aujourd'hui []) — kWc conçus (devis à layout), kWc signés, taux de conversion des leads conçus ; agrégat pur consommé par le fédéré ARC40 existant, aucun écran neuf. **Done =** KPI visibles dans kpi-federes (test). Files: `apps/ventes/platform.py`, `apps/ventes/reports.py`, tests. (ROUTINE) (@lane: backend/ventes-kpi) (@model: sonnet)

**DÉGATÉES (fondateur 2026-08-14 — « ungate all » : l'accord vaut pour la dépendance ezdxf, les SKUs, et le seed datasheet à modèle supposé) :**
- [ ] PVG1 — **Import DXF réel (dépendance `ezdxf` approuvée fondateur 2026-08-14)** : ajouter `ezdxf` (MIT, pur Python) aux requirements ; endpoint `POST /ao/toitures/dxf/analyser/` (multipart) → {calques:[{nom, entites, sommets}], unite} au format exact qu'ImportDxf.jsx attend (LWPOLYLINE/POLYLINE/LINE par calque) + câblage front de la prop analyserDxf ; enregistrement de la route dans le urls AO (chaîne mono-écrivain ao : séquencer après PV54). Fichier DXF hostile → 400 FR, jamais un 500. **Done =** un DXF de fixture rend ses calques et sommets, ImportDxf propose le mapping, dépendance NOTÉE au DONE LOG. Files: `apps/ao/dxf.py`, `frontend/src/features/ao/toiture/ToituresPage.jsx`, requirements, tests. (@after: PV12, PV54, PV68) (DEP) (@model: sonnet)
- [ ] PVG2 — **Garde de tolérance sur l'arbitrage A/B calepinage villa (décision rendue : sécurité par défaut)** : aujourd'hui, flag ON, le compte moteur ÉCRASE silencieusement le compte TS (services.py:606-611) — et PV65/PV66 changeront les comptes moteur. Coder la garde : |écart| > seuil (défaut 2 modules OU 5 %, constantes nommées) → GARDER le compte TS historique + journaliser un avertissement structuré portant les deux comptes et le motif (jamais un écrasement silencieux au-delà du seuil) ; sous le seuil → comportement actuel (moteur gagne, écart journalisé). Flag OFF → byte-identique. **Done =** les 3 régimes testés (OFF inchangé ; ON petit écart → moteur ; ON gros écart → TS + avertissement), seuils nommés ajustables. Files: `apps/ventes/services.py`, tests ventes. (ARCH) (@after: PV42) (@lane: backend/ventes-devis3d) (@model: opus)
- [x] PVG3 — **SKUs câbles/protections prix vides (création approuvée fondateur 2026-08-14)** : seeder (idempotent, additif) les références que le BOQ PV47 chiffrera : câble H1Z2Z2-K 4/6/10/16 mm² (au mètre), fusibles gPV 1000 VDC 15/20 A + porte-fusibles, parafoudre DC type 2 1000 V, parafoudre AC type 2, sectionneur DC 1000 V, disjoncteurs AC courbe C 16/20/25/32 A (mono + tétra), DDR type A 300 mA 40/63 A, coffret DC/AC vides — TOUS à `prix_vente=0`/`prix_achat=0` « prix à renseigner », EXCLUS de l'auto-fill (précédent pompes OSP : la garde produit-sans-prix existe déjà). **Done =** seed rejouable, SKUs visibles au catalogue avec le flag prix-à-renseigner, jamais cités par l'auto-fill (test). Files: `apps/stock/management/commands/seed_catalogue.py`, tests stock. (ROUTINE) (@after: PV9) (@lane: backend/stock-specs) (@model: sonnet)
- [x] PVG4 — **Datasheets onduleurs/batteries : modèles supposés sourcés (accord fondateur 2026-08-14)** : le catalogue nomme des paliers génériques (« Onduleur réseau Huawei 5kW Monophasé ») sans modèle constructeur — pour chaque palier onduleur/batterie seedé : associer le modèle constructeur LE PLUS PROBABLE de la gamme courante (Huawei SUN2000 L1/M1/M5, Deye SUN-…SG0…LP1/LP3, batteries LiFePO4 48-51,2 V), seeder la FicheTechnique (fenêtre MPPT v_min/v_max, v_max_abs, i_max par MPPT, phases, ac_kw ; batteries kWh nominal/utile, DoD, V nominal) avec CHAQUE valeur tirée d'une datasheet constructeur réelle (source en commentaire) et la mention « modèle supposé : <X> — à confirmer fondateur » ; un palier sans modèle raisonnablement sûr reste NULL (jamais un chiffre inventé). **Done =** fiches seedées sourcées + mention modèle-supposé, paliers incertains restés NULL et listés au DONE LOG. Files: `apps/stock/management/commands/seed_catalogue.py`, tests stock. (ROUTINE) (@after: PV5, PV9) (@lane: backend/stock-specs) (@model: sonnet)

#### DONE LOG — Groupe PV
- 2026-08-14 : PV7/PV8 (ecran Fiches techniques complet — type_fiche + groupes conditionnels + upload PDF + edition ; badge completude datasheet catalogue/detail), PV33-PV39 (noyau pur core/electrique COMPLET : types geles, chaines/onduleurs avec double ratio nomme, protections NF C 15-100/UTE C 15-712-1/IEC 62548 sourcees, cables Iz+chute de tension, nomenclature, concevoir()+note FR zero litteral, schema unifilaire v2 avec table d'appareillage derivee des memes listes — 157 tests unitaires purs verts, import-linter electrique-est-un-noyau-pur), PVG3 (22 SKUs cables/protections prix vides, garde _has_price veriee), PVG4 (15 fiches onduleurs/batteries a modele suppose sourcees, NULLs honnetes sur Huawei mono 10/12kW inexistants + divergences ; incompatibilite Deye tri 15-20kW HV vs batteries 51,2V documentee en commentaire — dependance ezdxf N'EST PAS encore consommee, elle arrive avec PVG1) — 11 taches, 3 lanes.
- 2026-08-14 : PV10/PV11 (solar_design + wattage PDF branches sur la fiche — pont canonique specs_module_pour_produit, ordre fiche→regex→defaut, pages/totaux verrouilles), PV14-PV18 (boucle devis-3D backend : geometry par pan lue — le devis cite enfin le bon panneau —, garde 409 sur replace-lines + produits globaux, cible_depuis_lignes, design-context a retour unique, sync-layout chirurgical sous select_for_update statut structurellement inaccessible), PV29/PV52/PV48/PV65 (moteur : plan impose avec preuve honnete optimal=False, phase forcee, les 4 tiroirs calcules purs sous budget 12 appels, elevation solaire par latitude portee du cerveau TS — fallback bit-identique, VERSION_MOTEUR 2.0.0, goldens FRDISI re-verifies jamais regeneres) — 11 taches, 3 lanes.
- 2026-08-14 : PV1-PV4 (4 contrats PACT10 ventes+ao+simulation, check_api_shapes vert 472 endpoints), PV5 (FicheTechnique +21 champs, migration stock/0086), PV6 (selecteurs specs_for_produit/kit_from_produit, fallback dict-vide prouve), PV9 (datasheets reelles CS-710 dims+coeff / JK-710 coeffs, sources en commentaire), PV82 (provider KPI concu-vs-vendu branche au hub ARC40) — 8 taches, 3 lanes worktree, foldees apres integration sync-safe d'origin/main (PR #518, CODEMAP regenere sur l'arbre fusionne).

*Notes de cohérence PV : chaînes de migrations MONO-ÉCRIVAIN — stock (PV5), ventes (PV41), ao (PV54, PV57 : même lane backend/ao), installations (PV80) ; les lanes `appsweb/*` partagent prefill.ts/layoutEditor.ts/estimatorBrain*.ts → plan_lanes les unionnera, c'est attendu ; PV42 touche services.py comme PV14/16/18, et views/devis.py (PV15/17/18/47/74/79), selectors.py (PV17/78), builder.py+test_quote_engine.py (PV11/24/46/77) fusionnent ventes-devis3d + ventes-electrique + ventes-etude + ventes-quotepdf + ventes-solar + crm-wiring en UNE lane ventes séquentielle (~17-24 tâches) — attendu par la machinerie, ne pas le « réparer ». Dédoublonnages actés à la synthèse : le dossier réglementaire (PV45) absorbe l'ancienne idée WIRE5, l'annexe PDF (PV46) absorbe WIRE8, le P50 public vit dans PV77 (pas de tâche séparée), les sélecteurs stock (PV6) servent solar_design + SLD + kits. Préfixes PV/PVG déclarés `unmapped_ok` dans BUILD_ORDER.yml dans le commit d'insertion. Dégate fondateur 2026-08-14 : PVG1-4 sont CONSTRUCTIBLES (ezdxf approuvé — à noter au DONE LOG ; PVG2 = garde de tolérance codée ; PVG4 = valeurs sourcées à modèle supposé, jamais inventées).*

---

### GATED — Groupe PUB (ne PAS auto-construire — chaque item attend sa porte fondateur)

- [ ] PUB107 — **[GATED: décision WhatsApp Cloud API (même porte qu'ADSENG34)] Boîte de réception WhatsApp d'équipe** : conversations CTWA assignables, notes internes, SLA par conversation, funnel conversation→qualifié→devis→signature — le standard Wati/Trengo. Ne se construit qu'à la levée de la porte Cloud API. Files: `apps/adsengine/`+front. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: opus)
- [ ] PUB108 — **[GATED: décision WhatsApp Cloud API] Réponse instantanée + qualification WhatsApp Flows** : auto-réponse <1 min sur lead Meta/CTWA (gabarits approuvés), formulaire Flows structuré (type toiture/facture/ville) alimentant le Lead et un brouillon de Devis. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: opus)
- [ ] PUB109 — **[GATED: décision WhatsApp Cloud API] Relances drip marketing WhatsApp** : cadences 1h/1j/3j pour FOLLOW_UP/COLD et devis expirés (opt-out géré, fenêtres de coût 2026 respectées) — distinct des relances transactionnelles existantes. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: sonnet)
- [ ] PUB110 — **[GATED: clé LLM + revue anti-hallucination (même porte que le commentaire LLM des briefs)] Stratège conversationnel sur données pub** : chat « pourquoi cette ad gagne ? que tester ensuite ? » au-dessus des métriques internes — réponses citant les chiffres réels uniquement (pattern FactTable). (@blocked: clé LLM + revue anti-hallucination fondateur) (DEP) (@model: opus)
- [ ] PUB111 — **[GATED: budget fondateur — dépendance payante] Tier vidéo AI-UGC (Arcads/Creatify-style)** : adaptateur `creative_factory` supplémentaire pour avatars parlants + speech-to-speech (voix réelle Darija du fondateur sur acteur IA — aucun outil n'a de Darija natif) ; nés en backlog, jamais publiés sans approbation. (@blocked: budget fondateur dépendance payante) (DEP) (@model: sonnet)
- [ ] PUB112 — **[GATED: décision fondateur — touche le cœur décisionnel] Bandit « toujours actif » au niveau adset** : étendre la logique Thompson hors des expériences déclarées pour réallouer en continu le budget entre adsets vivants (propose-only au début). À n'ouvrir qu'après PUB15/PUB18 en production et un historique de regret (PUB86) propre. (@after: PUB15, PUB18, PUB86) (@blocked: décision fondateur cœur décisionnel) (DECISION) (@model: opus)
- [ ] PUB113 — **[GATED: vertical SK Paysages — décision produit fondateur] Généraliser le moteur multi-vertical** : FactTable/seeds/mots-clés de classification/saisonnalité par tenant-vertical (paysagisme ≠ solaire) — le mémo marketing exige SK Paysages d'abord or tout est câblé solaire. Cadrage L, à ne lancer que sur décision explicite. (@blocked: décision produit fondateur SK Paysages) (DECISION) (@model: opus)
- [ ] PUB114 — **[GATED: numéro dédié + coût télécom] Suivi d'appels par annonce + rappel SMS d'appel manqué** : numéros de suivi par source, missed-call-textback — une partie des leads marocains arrive encore par téléphone. Dépendance opérateur/API télécom payante à choisir avec le fondateur. (@blocked: dépendance télécom payante fondateur) (DEP) (@model: sonnet)

#### PUB-P8 — Le moteur AGIT : multiplication des gagnants, chaîne de création réelle, portes d'autonomie (synthèse décisive 2026-07-20 — 5 enquêtes vérifiées adversarialement)

> **Doctrine.** Le moteur OBSERVE (4 448 snapshots, connexion réelle, beats vivants) mais n'a JAMAIS
> agi : EngineAction=0, RulePolicy=0, Experiment=0, FlightPlan=0, WeeklyBrief=0, AssumptionNode=0,
> FactTable=0, CreativeAsset=0. Ce groupe COMPOSE la machinerie existante (jamais de reconstruction)
> pour fermer les 7 maillons manquants vérifiés dans le code : (1) aucun upload adimages/advideos dans
> `meta_client.py` ; (2) aucun pont CreativeAsset→créatif Meta ; (3) `run_weekly` JETTE les décisions
> de rotation (flightrunner.py:550-557 ne fait que les compter) ; (4) FlightRunner crée des coquilles
> campagne+adset sans jamais d'ad ; (5) le payload ROTATE_CREATIVE est CREUX (rules_engine.py:728-734
> → services.py:1182-1185 appelle create_ad sans name/adset_id/creative — même le chemin APPROUVÉ par
> l'humain échouerait sur le vrai Meta) ; (6) `generation._default_generator` est délibérément inerte
> MÊME AVEC sa clé (generation.py:78-92 : « aucun backend LLM câblé ») ; (7) `policy_lint`/`tier_router`
> ne sont PAS insérés dans le chemin réel (`tasks._run_grounded_generation` = generation→claim_check→
> groundedness→audit seulement ; tier_router n'a d'appelant que simulator.py — le libellé de PUB16 [x]
> surestimait, les tâches ici COMPLÈTENT PUB16, ne le dupliquent pas).
> **Invariants absolus :** règle #3 naissance PAUSED (aucun chemin d'unpause, jamais) ; approbation
> humaine avant toute dépense (propose→approve→apply, l'IA produit des ASSETS jamais des décisions) ;
> génération checked-facts-only (FactTable publiée + claim_check dur) ; migrations additives ;
> cross-app par selectors/string-FK. **Dédupe :** ne pas re-proposer PUB16 (point d'entrée génération),
> PUB110 (stratège LLM gated), PUB111 (AI-UGC gated), ADSENG34/porte CAPI-WhatsApp, XMKT36.
> **Ordre de drain :** A) multiplication zéro-clé des gagnants (PUB116-121) → B) fabrique de génération
> réelle (PUB122-126, PUB130) → C) portes d'autonomie (PUB127-129) → D) harnais (PUB131). Vidéo/CAPI
> restent derrière leurs portes.
>
> **[EXEC-NOW] — actions serveur ce soir (orchestrateur, ZÉRO armement, zéro dépense) — pas des
> tâches de build :** (1) `manage.py seed_adsengine` (RulePolicy par template, dry_run par défaut →
> propositions [Simulation] seulement) ; (2) `manage.py seed_fact_table` (table de faits en brouillon —
> le fondateur publie via l'écran PUB6) ; (3) `manage.py seed_creative_calendar` ; (4) déclencher
> `adsengine.generate_weekly_brief` et diagnostiquer pourquoi WeeklyBrief=0 malgré le beat (si cause =
> aucune expérience/plan → PUB130 la corrige) ; (5) vérifier l'écran wiring-health (PUB29) après seeds ;
> (6) NE RIEN armer, NE PAS activer l'autonomie, NE PAS créer de campagne.
>
> **[FOUNDER] — décisions/portes avec coûts :** (a) génération de copie ancrée via GROQ_API_KEY déjà
> sur le serveur (0 MAD, free tier — PUB124 la câble en fallback ; poser ADSENGINE_GEN_API_KEY dédiée
> plus tard si souhaité) ; (b) images fal.ai ~50-150 MAD/mois (PUB132 gated) ; (c) vidéo template
> json2video/Bannerbear ~200-500 MAD/mois (PUB133 gated) ; (d) vidéo AI-UGC ~500-4000 MAD/mois (PUB111
> existant, différer) ; (e) autoriser les micro-tests terrain FT1-7 (≤30 MAD/jour par test, ~200-500 MAD
> une fois — débloque la porte préflight via PUB128) ; (f) valider le YAML de l'arbre solaire (PUB127,
> session 30-60 min) puis publier la FactTable seedée ; (g) enveloppe du premier FlightPlan
> (300-1000 MAD/jour) ; (h) portes CAPI dataset / WhatsApp Cloud API : inchangées, déjà gated.

- [ ] PUB116 — **Le moteur propose lui-même « multiplier le gagnant »** : `rule_templates.py` déclare les évaluateurs v2 (ADSDEEP40) mais le hint d'action reste `'action': None` (~ligne 456) — aucun template ne route jamais vers `_propose_v2_action` (rules_engine.py:629, qui gère déjà `budget_scale_up` ET `duplicate` → `services.propose_duplicate`, lui-même branché sur `duplicate_adset_with_ad` + `AdCreativeMirror.creative_meta_id`) : la seule multiplication aujourd'hui est le duplicate manuel 3-clics. Poser `v2['action']='budget_scale_up'` sur le template surf-scaling + ajouter un template `winner_duplicate` (`v2['action']='duplicate'`, seuils honnêtes : p_best/volume plancher, cooldown `_recently_acted` déjà couvert rules_engine.py:707-725). Les policies restent dry_run par défaut (seed → propositions [Simulation]) ; l'armement reste l'acte UI PUB23. **Done =** gagnant net sur fixtures → propositions duplicate + budget-up dans Approbations ([Simulation] en dry-run) ; jamais d'auto-application ; test invariant PAUSED sur le chemin duplicate. Files: `apps/adsengine/{rule_templates.py,rules_engine.py}`, tests. (ARCH) (@lane: backend/adsengine-loop) (@model: opus)
- [ ] PUB117 — **MetaClient : écriture de créatifs (adcreatives + asset_feed_spec)** : le client lit `object_story_spec`/`asset_feed_spec` (meta_client.py:561-570) mais ne sait PAS écrire un créatif — aucune méthode `act_<id>/adcreatives`, aucune création d'ad à spec dynamique. Ajouter `create_adcreative(name, object_story_spec=None, asset_feed_spec=None, extra_fields=None)` + `create_ad_with_asset_feed_spec(name, adset_id, asset_feed_spec, extra_fields=None)` — même mécanique d'encodage JSON des objets imbriqués (déjà en place, meta_client.py:~901), même défense `_forced_status_payload` pour toute création d'AD (un adcreative seul ne diffuse rien sans ad ; aucun chemin n'accepte `status`, TypeError sinon — invariant règle #3 identique aux méthodes existantes). **Done =** tests client : specs imbriquées encodées JSON, ad né PAUSED forcé, passer `status` lève ; adcreative sans ad = inerte. Files: `apps/adsengine/meta_client.py`, tests. (ARCH) (@lane: backend/adsengine-create) (@model: opus)
- [ ] PUB118 — **Recombinaison DCO zéro-clé depuis les miroirs — le premier « mes pubs créent des pubs »** : `sync.py:132-167` mirrore déjà `asset_feed_spec` sur `AdCreativeMirror` et `dco.py` (validateurs prêts, ZÉRO appelant) plafonne 10 visuels × 5 titres × 5 textes — Meta recombine et auto-teste par impression, sans aucune clé externe. Service de moisson : collecter image_hashes/video_ids/titres/bodies des créatifs mirrorés GAGNANTS de la société (pool conditionné à la perf — le remix superficiel ne gagne rien, preuve recherche), composer une spec plafonnée via `dco.validate_dco_asset_spec` + `validate_mutual_exclusion` (adset DCO = 1 ad, bootstrap cold-start uniquement — le STATUT de dco.py attend exactement cet appelant), proposer une EngineAction create_ad à spec inline (PUB117) via la boîte d'approbation. Entrée : bouton « Recombiner (DCO) » sur le cockpit/détail adset — jamais d'automatisme sans armement. **Done =** fixtures : la proposition porte une spec valide plafonnée construite UNIQUEMENT d'assets mirrorés existants ; violation d'exclusion mutuelle → refus FR ; application (mock) → ad née PAUSED. Files: `apps/adsengine/{dco.py,services.py,views.py}`, front cockpit, tests. (@after: PUB117) (ARCH) (@lane: backend/adsengine-create) (@model: opus)
- [ ] PUB119 — **Fin du payload ROTATE_CREATIVE creux** : rules_engine.py:728-734 construit le payload sans name/adset_id/creative et `_dispatch` (services.py:1179-1185) appelle `create_ad(name='', adset_id='')` — le vrai Meta rejette, y compris après approbation humaine. Corriger à la PROPOSITION : résoudre l'adset cible, le nom (`naming.py`), et la source créative — (a) tête du backlog approuvé portant un créatif Meta (pont PUB123) sinon (b) meilleur `creative_meta_id` vivant de l'adset (`AdCreativeMirror`) ; si AUCUN créatif prêt → alerte explicite « aucun créatif prêt pour la rotation », JAMAIS une action creuse. `_dispatch` valide la complétude fail-fast (raison FR → action `echouee`, rien d'envoyé). **Done =** finding frequency_high sur fixtures → payload complet (adset_id+name+creative) OU alerte explicite ; payload creux forcé → echouee FR sans appel réseau ; naissance PAUSED intacte. Files: `apps/adsengine/{rules_engine.py,services.py}`, tests. (@after: PUB117) (ARCH) (@lane: backend/adsengine-loop) (@model: opus)
- [ ] PUB120 — **`run_weekly` matérialise les décisions de rotation** : flightrunner.py:535-557 calcule `plan_rotation` (exits/reviews/entries) puis ne fait que les COMPTER — le backlog ne devient jamais des ads. Matérialiser chaque décision en propositions : exits → PAUSE (garde `enforce_paused_only` existante), reviews → alerte/annotation, entries → ROTATE_CREATIVE à payload complet (PUB119) depuis l'item de backlog (statut de l'item avancé EN_FILE→proposé, idempotence par dédup type `_recently_acted` — un re-run la même semaine ne duplique rien). Tout propose-only, le retour `rotations` (compteurs) reste identique. **Done =** expérience sur fixtures avec 1 exit + 1 entry → 2 propositions dans Approbations, liées à l'expérience ; re-run → zéro doublon ; kill-switch → NO-OP inchangé. Files: `apps/adsengine/{flightrunner.py,services.py}`, tests. (@after: PUB119) (ARCH) (@lane: backend/adsengine-loop) (@model: opus)
- [ ] PUB121 — **FlightRunner remplit les slots créatifs au lancement** : le runner ne crée que des coquilles campagne+adset — jamais une ad : un plan lancé ne peut pas diffuser même tout-approuvé. Au lancement de phase : pour chaque adset, proposer les create_ad depuis (a) les items de backlog approuvés de la file campagne (`backlog_mod.queue_for_campaign`) sinon (b) le créatif du gagnant (chemin duplicate) ; consulter l'arbitre `dco.py` au cold-start (aucun signal → bootstrap DCO PUB118, sinon rotation multi-ads — exclusion mutuelle validée). Chaque ad = proposition née PAUSED ; un adset qui resterait sans candidat → alerte explicite, jamais une coquille silencieuse. **Done =** lancement d'un plan sur fixtures → propositions d'ads par adset (ou alerte « aucun créatif ») ; exclusion DCO↔rotation respectée (test) ; zéro création directe. Files: `apps/adsengine/{flightrunner.py,services.py}`, tests. (@after: PUB119) (ARCH) (@lane: backend/adsengine-loop) (@model: opus)
- [ ] PUB122 — **Upload d'assets au compte : adimages/advideos** : `meta_client.py` n'a que les edges de Page (upload_page_photo/video, :1035-1066) — un `CreativeAsset.file_key` (MinIO) ne peut jamais devenir `image_hash`/`video_id` de compte. Ajouter `upload_ad_image` (`act_<id>/adimages`, bytes ou URL → hash) + `upload_ad_video` (`act_<id>/advideos`, `file_url` simple d'abord — URL présignée MinIO — fallback chunké documenté) + champs additifs `CreativeAsset.meta_image_hash`/`meta_video_id` + service d'upload idempotent (hash déjà présent → skip). Aucun `status` nulle part (un asset uploadé ne diffuse rien). **Done =** asset uploadé (mock) → hash/id persistés ; re-run → zéro re-upload ; erreur Graph → asset intact + raison FR. Files: `apps/adsengine/{meta_client.py,models.py,creative_factory.py}`, migration additive, tests. (SCHEMA) (@lane: backend/adsengine-create) (@model: sonnet)
- [ ] PUB123 — **Pont CreativeAsset → créatif Meta** : le maillon central du mur — un asset approuvé (policy PASS + consentement OK) devient un payload `creative` consommable par les dispatchs (PUB119/120/121) : construire l'`object_story_spec` (page_id de la connexion ; champ additif sur `MetaConnection` si absent) avec link/photo/video_data depuis `meta_image_hash`/`meta_video_id` (PUB122) + hook_text/primary_text/cta de l'asset + étiquette IA (PUB126) ; provenance `generation_audit` reliée à l'ad résultante. Refus explicite pour un asset non approuvé, policy FAIL, consentement manquant (registre PUB75) ou sans média uploadé. **Done =** golden test par asset_type : asset approuvé → payload créatif complet ; asset non conforme → refus FR ; la chaîne provenance asset→fait→version FactTable survit jusqu'à l'ad. Files: `apps/adsengine/` (nouveau `creative_bridge.py`), `services.py`, tests. (@after: PUB122) (ARCH) (@lane: backend/adsengine-create) (@model: opus)
- [ ] PUB124 — **Backend LLM réel pour `generation.py` (Groq/OpenAI-compatible)** : `_default_generator` (generation.py:78-92) reste inerte MÊME avec la clé (« aucun backend LLM câblé ») — le pipeline PUB16 tourne à vide. Implémenter le générateur ancré : endpoint chat-completions OpenAI-compatible (Groq), clé résolue `ADSENGINE_GEN_API_KEY` sinon fallback `GROQ_API_KEY` (déjà sur le serveur), modèle configurable env ; prompt = UNIQUEMENT les faits de la FactTable PUBLIÉE + seed_brief + slots de composants (pattern hook-first 3-3-3) ; sortie JSON parsée en composants → chaque variante passe le claim_check/groundedness EXISTANT (chiffre invérifiable → variante rejetée + audit) ; sans aucune clé → NO-OP byte-identique. La sortie n'est QUE des `CreativeBacklogItem` en attente d'approbation — jamais une dépense, jamais une publication (distinct de la porte PUB110 stratège conversationnel). **Done =** backend mocké → variantes ancrées avec `claim_verdicts` persistés ; chiffre inventé dans la sortie mock → variante rejetée ; sans clé → NO-OP inchangé (golden). Files: `apps/adsengine/{generation.py,tasks.py}`, tests. (ARCH) (@lane: backend/adsengine-gen) (@model: opus)
- [ ] PUB125 — **Insérer `policy_lint` + `tier_router` dans le chemin RÉEL** : `policy_lint_config.py` l'écrit noir sur blanc (« EN ATTENTE DE : l'insertion de policy_lint dans le pipeline ») et `tier_router` n'a d'appelant que `simulator.py` — le chemin de production (`tasks._run_grounded_generation`, tasks.py:1519-1560) saute les deux. Insérer : lint de chaque variante (verdicts → `generation_audit` + policy_stamp, FAIL → jamais en backlog), routage de palier (`route_tier` : A → backlog direct, B → flag « revue humaine » sur l'item), `record_clean_week` alimenté par les lots validés (la graduation B→A devient réelle). Simulator intouché. **Done =** variante à superlatif interdit → FAIL persisté, absente du backlog ; item palier B flaggé revue ; gabarit gradué sur fixtures → palier A (test) ; chemin simulator byte-identique. Files: `apps/adsengine/{tasks.py,generation_audit.py}` (+flag additif si besoin), tests. (@after: PUB124) (ROUTINE) (@lane: backend/adsengine-gen) (@model: sonnet)
- [ ] PUB126 — **Étiquette « généré par IA » par asset (obligation Meta 2026 — 14 % des rejets)** : aucun champ ne porte la divulgation IA exigée par asset. Champ additif `CreativeAsset.ai_generated` (défaut par lane : génération/recombinaison/fal → true ; chantier/ugc réel → false), posé par toutes les lanes de fabrique, PROPAGÉ dans chaque payload de création de créatif (PUB118/123 — vérifier à la construction le champ API exact de divulgation côté Graph et le documenter en commentaire sourcé) ; la checklist policy BLOQUE un asset IA sans étiquette. **Done =** asset généré → flag posé ; payload créatif porte la divulgation ; checklist rouge sans elle (test) ; assets chantier réels non sur-étiquetés. Files: `apps/adsengine/{models.py,generation.py,creative_factory.py,policy.py}`, migration additive, tests. (SCHEMA) (@lane: backend/adsengine-gen) (@model: sonnet)
- [ ] PUB127 — **Commande de semis de l'arbre + YAML solaire v1** : `seeding.py` (import YAML validé, idempotent, testé — ASG5) n'a AUCUNE commande (« EN ATTENTE DE : la commande de semis jour-0 ») → AssumptionNode=0 pour toujours. Ajouter `manage.py seed_assumption_tree --file <yml> [--dry-run]` (refus FR sur YAML invalide, dry-run imprime le plan de semis) + RÉDIGER le brouillon d'arbre solaire `docs/engine/solar-tree-seed.yml` (nœuds économie/cible/angle/canal, priors en pseudo-comptes honnêtes marqués `assumed`, liens d'invalidation) depuis la connaissance réelle du repo (playbook marketing, seed FactTable, recherche QX) — le FONDATEUR valide le contenu avant l'import prod ([EXEC-NOW] ensuite). **Done =** double import du brouillon sur fixtures = même état (idempotence) ; YAML commité + lisible fondateur ; dry-run n'écrit rien. Files: `apps/adsengine/management/commands/seed_assumption_tree.py`, `docs/engine/solar-tree-seed.yml`, tests. (ROUTINE) (@lane: backend/adsengine-autonomy) (@model: sonnet)
- [ ] PUB128 — **Harnais des tests terrain FT1-7** : `field_tests.py` = 7 constantes `SOURCE_RESEARCH` et la porte préflight `field_tests_complete()` reste rouge tant que TOUT n'est pas tranché — or seul un edit de code peut les basculer aujourd'hui. Modèle `FieldTestResult` (company, clé FT, valeur mesurée, preuve, date) ; `field_tests.pending_keys()` consulte la DB d'abord (constantes = fallback) ; écran « Tests terrain » : protocole par FT depuis le runbook `docs/engine/field-tests.md`, plafond 30 MAD affiché (`MICRO_TEST_MAX_DAILY_BUDGET_MAD`), structures de test proposées via le circuit propose→approve normal (PAUSED), saisie du résultat mesuré. Les RUNS réels restent [FOUNDER] (micro-budgets autorisés). **Done =** enregistrer les 7 résultats → porte préflight verte (test) ; UI liste chaque FT avec statut/protocole ; aucune valeur en dur modifiée ailleurs. Files: `apps/adsengine/{models.py,field_tests.py,preflight.py,views.py,serializers.py}`, migration additive, front écran, tests. (SCHEMA) (@lane: backend/adsengine-autonomy) (@model: sonnet)
- [ ] PUB129 — **Cockpit d'autonomie : les 8 portes + cérémonie d'activation** : `preflight.status(company)` agrège les 8 portes (ADSENG38) mais AUCUNE UI ne les montre — l'autonomie est invisible et inactivable depuis la console. Section/écran : chaque porte avec état + remédiation FR cliquable (semis arbre → PUB127, tests terrain → PUB128, acquittement simulation, etc.), bouton « Activer l'autonomie » → `preflight.activate` (refus `AutonomyNotReady` affiché tel quel), désactivation toujours libre en un clic (aucune porte requise — sécurité), tout journalisé. **Done =** portes visibles en direct sur fixtures ; activation refusée tant qu'UNE porte est rouge (e2e) ; désactivation immédiate. Files: `apps/adsengine/views.py` (vue mince sur preflight), `frontend/src/features/adsengine/` (section ConnectionScreen ou écran), tests. (@after: PUB127, PUB128) (ROUTINE) (@lane: backend/adsengine-autonomy) (@model: sonnet)
- [ ] PUB130 — **Brief hebdo en mode observation (avant tout plan de vol)** : WeeklyBrief=0 en prod malgré le beat `adsengine.generate_weekly_brief` (tasks.py:1053) — diagnostiquer, puis faire produire à `build_brief` un brief UTILE sans FlightPlan ni expérience : sections observation depuis les données déjà synchronisées (top/flop ads, fatigue, fréquence, junk par ad, candidats à dupliquer/pauser en LECTURE — jamais une action), périmètre honnête (aucune recommandation sans données suffisantes, il le dit). Société avec expériences → brief actuel inchangé. **Done =** société observe-only avec snapshots sur fixtures → brief non vide en sections observation ; société avec expériences → golden inchangé ; le beat produit enfin une ligne WeeklyBrief. Files: `apps/adsengine/{brief.py,tasks.py}`, tests. (ROUTINE) (@lane: backend/adsengine-gen) (@model: sonnet)
- [ ] PUB131 — **Harnais d'intégration « première chaîne de création »** : toute la classe de défauts de ce groupe = une chaîne jamais exercée bout-en-bout. UN test d'intégration (transport Meta mocké) qui déroule les 3 chemins réels : (a) duplicate gagnant (PUB116 → propose_duplicate → duplicate_adset_with_ad), (b) rotation depuis le backlog (fait publié → variante ancrée mock → approbation → PUB119/120 → dispatch), (c) DCO recombiné (PUB118) — et asserte les payloads Graph FINAUX complets (adset_id/name/creative présents, `status=PAUSED` forcé partout) + grep-garde « aucun chemin d'unpause ». Toute rupture future d'un maillon (payload creux, méthode retirée, champ renommé) = rouge CI. **Done =** 3 chaînes vertes bout-en-bout ; suppression volontaire d'un maillon sur branche de test → rouge. Files: `apps/adsengine/tests/test_creation_chain.py`. (@after: PUB118, PUB120, PUB121, PUB123) (ROUTINE) (@lane: backend/adsengine-loop) (@model: opus)

### GATED — ajouts Groupe PUB-P8 (ne PAS auto-construire — chaque item attend sa porte fondateur)

- [ ] PUB132 — **[GATED: budget fondateur fal.ai ~50-150 MAD/mois] Adaptateur images fal.ai dans la fabrique** : lane `fal` de `creative_factory` (FLUX schnell/dev, ~$0.003-0.05/image) pour visuels statiques ancrés (composés avec les textes PUB124), coût tracé `cost_cents` (le ROI par lane PUB81 le lit déjà), étiquette IA PUB126 automatique, sortie = assets en attente d'approbation, key-gated NO-OP propre sans `FAL_API_KEY`. **Done =** clé posée → asset image généré + coûté + étiqueté, en approbation ; sans clé → NO-OP FR. Files: `apps/adsengine/creative_factory.py`, tests. (@blocked: budget fondateur fal.ai) (DEP) (@model: sonnet)
- [ ] PUB133 — **[GATED: budget fondateur json2video/Bannerbear ~200-500 MAD/mois] Pont template-vidéo** : rendre les scripts ancrés EXISTANTS (`video_queue.build_grounded_script`, beats persistés PUB82) en vidéos template (slideshow photos chantier + textes — PAS d'avatar : distinct de la porte AI-UGC PUB111), lane dédiée coûtée, étiquette IA, sortie en backlog d'approbation, key-gated NO-OP. **Done =** clé posée → script mock rendu (mock API) en asset vidéo étiqueté en approbation ; mapping beat↔scène conservé pour la rétention PUB82. Files: `apps/adsengine/{creative_factory.py,video_queue.py}`, tests. (@blocked: budget fondateur template-vidéo) (DEP) (@model: sonnet)
- [ ] PUB134 — **Devise du compte dans les textes de décision.** Les `reason_fr` composés par `rules_engine.py`/`anomaly.py` écrivent « X MAD » en dur alors que le compte facture en USD (vu en production sur la première proposition du moteur : « a dépensé 17.60 MAD »). Injecter la devise de la `MetaConnection` dans chaque texte de proposition/alerte composé côté moteur. **Done =** une proposition sur compte USD dit « USD » ; test. Files: `apps/adsengine/{rules_engine.py,anomaly.py}`, tests. (ROUTINE) (@lane: backend/adsengine-decisions) (@model: sonnet)
- [ ] PUB135 — **Rationale de décision à deux fenêtres + signal leads réel.** La première proposition production jugeait « 0 résultat cette semaine » sur le champ results Meta seul — aveugle aux leads Odoo/WhatsApp (la vérité du fondateur) et sans contexte historique. Chaque proposition pause/rotate/rebalance doit citer : fenêtre récente ET vie entière, results Meta ET `leads_odoo` de l'ad (via `odoo_leads`), et s'abstenir (ou le dire) quand les deux signaux divergent. **Done =** le texte de proposition montre les 2 fenêtres × 2 signaux ; divergence → mention explicite ; tests. Files: `apps/adsengine/{rules_engine.py,odoo_leads.py}`, tests. (@after: PUB116) (ROUTINE) (@lane: backend/adsengine-decisions) (@model: opus)

---

#### DONE LOG — Vague 3 lane frontend/data (2026-07-12)

- 2026-07-12 — VX203 **[BLOCKED: partiel]** : `lib/apiError.js` (b) et la délégation `toast.js→apiError.js` étaient déjà construites (vagues précédentes). Fait cette session : (c) `api/iaApi.js` aligné sur le contrat (a) d'`axios.js` — toute erreur ≠401 hors annulation/`suppressErrorToast` surface désormais un toast FR via `getApiError` (un 403 du catalogue d'actions agentiques n'est plus muet). PAS FAIT (hors budget d'une session sans `eslint`/`vitest`/`vite build` disponibles dans ce worktree) : le scan réel des pages fautives donne ~104 fichiers (catch + `toastError`/`toast.error` direct), très au-delà des « ~35 » du texte — un codemod à l'aveugle sur ce volume, sans aucun moyen de vérifier une régression de build, est un risque disproportionné ; `scripts/check_double_toast.mjs` non créé pour la même raison (il casserait frontend-lint immédiatement tant que les ~104 fichiers ne sont pas corrigés). Laissé en BLOCKED pour une session avec outillage complet (build/lint) qui peut vérifier le codemod page par page.

---

### Groupe QX — Quote journey best-in-world ROUND 6: verified defects + conversion loop (2 audit rounds × 24 agents, adversarially verified + Fable design pass, 2026-07-10)

*A 2-round deep audit of the whole web→ERP quote journey (10 code lanes + 4 researchers, then 10
adversarial verifiers + Fable completeness critic + Fable target-state designer). 52 of 53 round-1
findings were CONFIRMED or PARTIAL under adversarial re-verification against real code; every task
below carries a verified fix spec. Three cross-cutting truths the whole group serves: (1) there is
NO single owner of the money number — six independent computations of a quote's value coexist and
three ignore `remise_globale`; (2) the dominant failure mode is UNWIRED features — built, tested,
then never scheduled/routed/linked; (3) client-facing URLs are minted ad hoc with two confirmed
404s at moments of maximum client intent. Rule #4 intact throughout: PDF fixes go INSIDE the
vendored engine; the engine only renders. Research anchors: Storydoc 1.3M sessions (82% of opens
happen <1h; 46% of signers sign <48h of open; losing proposals get viewed 3.5×), Proposify 2025
(e-sign path = 4× close, images +72%), MIT/Oldroyd speed-to-lead (21× qualification <5 min).
E-signature legal basis: cite **Law 43-20 (2020, BO n°6970 2021)** which superseded loi 53-05.*

**A — ONE MONEY MODEL (the critical: client sees discounted TTC, is billed full price)**

**B — THE CLIENT PDF (rule #4 — all fixes INSIDE the vendored engine)**

**C — E-SIGN & ACCEPTANCE (the decision moment)**

**D — WIRE THE DEAD AUTOMATION (built, tested, never scheduled/linked)**

**E — WEBHOOK & CRM INTAKE FIDELITY**

**F — SELLER QUOTE CREATION (the generator)**

**G — SELLER DAY-IN-THE-LIFE**

**H — THE CONVERSION LOOP (research-anchored)**

**I — ONE TRUE MATH (screen == PDF == proposal)**

**J — PUBLIC SURFACE HARDENING & RETENTION**

**GATED — founder decisions/accounts/data (queue, do NOT build the gated part)**
- [ ] QXG1 — **[GATED: founder account]** WhatsApp BSP evaluation, 360dialog-first (flat $59/€49/mo, zero markup on Meta per-template pricing — 2026 model is per-template-message, the old free tier is gone). Needs Meta Business verification + Morocco rate confirmation from the dashboard (not blogs). Unlocks: automated template sends for QX30's nudges, real OTP channel (QX10), proposal delivery. Until then everything ships degraded via wa.me drafts. (@blocked: founder account WhatsApp BSP) (@lane: whatsapp-bsp)
- [ ] QXG2 — **[GATED: founder account]** PayZone-first merchant onboarding (reported 5-10 day onboarding, no deposit, ~2-3% fees — verify primary-source), CMI later if volume justifies. Activates QX33's card-payment slot + facture PaymentLinks with a REAL provider (QX3 keeps everything fail-closed meanwhile). (@blocked: founder account PayZone/CMI) (@lane: ventes-pay)
- [ ] QXG3 — **[GATED: founder data]** Price the 11 OSP 30-series curve pumps (today ALL curve pumps are seeded price=0, so the intended HMT+débit agricole flow can never quote a buyable pump — the highest-impact single data entry in the journey) + verify/correct the suspicious HMT seeds (7.5CV@220m, 10CV@250m must be nominal duty points, not shutoff head) + confirm/replace the archived estimated coffrets. Land QX40's phase check first. (@blocked: founder data pump prices) (@lane: backend/stock)
- [ ] QXG4 — **[GATED: founder content]** Real proof pack for the trust page: selected installation photos, named testimonials, certifications (checked-facts-only rule — omit what doesn't exist). Proposify 2025: images +72% close rate, testimonials near the price +73% win probability. Lands inline in `residential/trust.py` after QX4. (@blocked: founder content proof pack) (@lane: quote-engine)
- [ ] QXG5 — **[GATED: founder ops check, 10 minutes]** Production env sanity: confirm `WEBSITE_LEADS_COMPANY_ID` is set (else `_resolve_company()` falls back to first Company by pk — silent misrouting risk if a second Company row ever exists); confirm the outbound email backend keys (`EMAIL_BACKEND`/`SENDGRID_API_KEY` vs `SENDINBLUE_API_KEY`) so QW8/QX13's email legs are live; confirm `PUBLIC_MAPTILER_KEY` naming on Cloudflare. (@blocked: founder ops env check) (@lane: ops-config) [2026-07-13 code guard added: both `_resolve_company()` copies (`apps/crm/webhooks.py`, `apps/crm/public_chat_views.py`) now `logger.error` LOUDLY when `WEBSITE_LEADS_COMPANY_ID` is unset AND 2+ Company rows exist, or when it's set to a non-existent pk — safe fallback preserved (never breaks the public endpoint), misconfiguration is now visible in logs. Still `[ ]`: the founder ops confirmation (var actually set in prod) is unbuilt/unverifiable here.]

---

### Group S — Internal team chat ("Discuss") (founder request 2026-06-21)

*Goal: a best-in-class INTERNAL team chat inside the ERP — staff message each other
1-to-1 (DMs) and in named channels, with file/image/voice attachments, @mentions,
reactions, pinned messages, message search, edit/delete, and the ERP superpower of
dropping a record (lead/devis/chantier) into a conversation as a rich clickable card.
New messages arrive by smart polling while a conversation is open and by the existing
Web Push (iPhone/Windows) when the app is backgrounded; per-conversation mute is
supported. Voice memos are transcribed (FR/Arabic/Darija best-effort) by a self-hosted
faster-whisper model in the FastAPI AI service, degrading gracefully when disabled.
Approved in the 2026-06-21 brainstorm with Reda. Full design in
`docs/superpowers/specs/2026-06-21-internal-team-chat-module-design.md`.*

> **Safety model (applies to the whole group).** Strict multi-tenant isolation: every
> model carries a `company` FK forced server-side (never from the body), and every viewset
> is company-scoped AND membership-checked (a user can only read/post in conversations they
> belong to — non-member 403, cross-tenant 404). All migrations additive/nullable. Cross-app
> reads (lead/devis/chantier labels for the share-a-record card) go through the target app's
> `selectors.py` — never importing its models/views (CI import contract). Attachments reuse
> `apps/records/storage.py` (MinIO, type-validated, 10 MB). Notifications reuse the existing
> `notify()` entry point + Web Push. STAGES.py is not involved.

> **Real-time stays polling for v1 (founder choice 2026-06-21).** No WebSocket/Channels in
> v1 — new messages arrive by short-polling the open conversation (~3 s) plus the existing
> Web Push when backgrounded. Typing indicators + live presence + instant delivery are
> deferred to the GATED **S21** WebSocket upgrade (brand-new ASGI/Channels infra), which a
> plan-run must NOT build until the founder provisions it.

> **One founder-approved backend dependency.** S10 adds `faster-whisper` (self-hosted,
> CPU-efficient, no paid service) + a lazily-downloaded model to the FastAPI AI service,
> behind a `CHAT_TRANSCRIPTION_ENABLED` flag so existing deploys are unaffected when off.
> This single dependency is pre-approved (2026-06-21 brainstorm); no other new dependency
> (backend or frontend npm) is authorized — the frontend reuses the existing Radix / lucide /
> sonner / @dnd-kit kit and the browser `MediaRecorder` for voice.

- [BLOCKED: waits on founder-provisioned WS infra (ASGI server process + Redis channel layer + nginx WebSocket proxy) — a real external prerequisite a run can't satisfy] S21 — **Real-time WebSocket upgrade (Django Channels).** Instant message delivery, typing indicators and live presence via Django Channels + a Redis channel layer + an ASGI server (daphne/uvicorn) + an nginx WebSocket proxy, authenticated with the same JWT. (UNGATED from category-gating 2026-06-21; held only by the infra prerequisite. **MY RECOMMENDATION: DEFER — "Discuss" chat already works via 3 s short-polling (`useChatPolling.js`); the WS stack adds real ops complexity (sticky sessions, connection draining on deploy) for a marginal gain on a small internal team. Build it only on a concrete need (live dispatch / many concurrent users).** Files: `erp_agentique/asgi.py`, `apps/chat/consumers.py` (new), settings `CHANNEL_LAYERS`, nginx config, frontend socket client.) (ARCH) (@lane: realtime)

# Taqinor OS — UI/UX overhaul ("prettier than Odoo")

*Goal: a calm, premium, data-first ERP — Linear/Stripe-tier polish, brand-matched to Taqinor, denser and cleaner than Odoo. Built on the existing React 19 + Vite + Tailwind 4 + recharts stack. Positioned ahead of Groups A–D so feature work inherits the new design language. Constraints: do NOT touch the devis/facture PDF templates, the public PDF pages, or the PdfCanvas PDF content (client-facing, gated separately); do NOT touch the apps/web marketing site; STAGES.py stays a fixed CI contract; schema changes additive/nullable only, every new value seeded from current in-code defaults.*

> **Renumbered on intake (2026-06-18):** the source proposal lettered these groups E–O, but `docs/PLAN2.md` already has a **Group E** (the E2E browser-test suite, tasks E1–E16). To keep every group/task id unique, the UI/UX-overhaul groups were shifted one letter to **F–P** (and their task ids re-prefixed to match) before being inserted here. Titles, content, and the running task numbers (14–69) are otherwise verbatim.

> **World-class look-and-feel wave (queued 2026-06-21, founder request "best-looking ERP in the world").**
> The design *foundation* already shipped (tokens.css, ~45 `src/ui` primitives, the hand-rolled
> `DataTable`, the app shell with sidebar/global-search/breadcrumbs/bottom-tab-bar) — so this wave is
> **adoption + refinement to Linear/Stripe/Vercel tier**, grounded in a fresh world-class audit (OKLCH
> tokens, premium tables, ⌘K command palette, restrained charts, tasteful motion, mobile/PWA polish,
> WCAG 2.2 AA). Tasks **F120–P171** fill the previously-empty Group F–P headers (the original 14–69
> series shipped/archived in `docs/DONE.md`; these continue the running number at 120 to stay unique).
> Hard constraints (unchanged): NEVER touch the devis/facture PDF templates, the public PDF pages, the
> `PdfCanvas` content, or the `apps/web` marketing site; import stage names from `STAGES.py` (never
> hardcode); schema changes additive/nullable seeded from current defaults; **no new npm dependency**
> (build on the already-installed Radix / recharts / @tanstack/react-table / @dnd-kit / sonner / lucide
> — anything else is gated). New user-facing text in French.

### Groupe VX — « Le plus bel ERP du monde » : signature visuelle, expérience Apps & craft + perfection technique (audits 16+11 agents, 2026-07-07/08)

*Provenance : demande du fondateur (2026-07-07) « make my ERP the best looking in the world + les modules
sont-ils mieux découpés façon Odoo ? ». Audit multi-agents à modèles étagés : 9 lanes de lecture du repo
(design-core, shell-nav, écrans CRM/ventes/ops/insight/fondation, mobile-PWA, scan de cohérence) + 5
recherches web best-in-class (Odoo 18/19, Linear/Attio/Stripe/Notion, data-viz, délice/motion,
field-service) + une carte anti-duplication sur TOUS les plans, puis synthèse Fable. Chaque constat est
vérifié dans le code (fichier:ligne) et re-vérifié par l'orchestrateur avant intégration.*

**VERDICT MODULES — la réponse à la question du fondateur.** Le découpage façon Odoo est le BON choix et il
est déjà à moitié fait : GARDER et TERMINER le plan ODX tel que queued (PLAN.md ODX1–23 — manifests, catalogue
+ fermeture de dépendances et enforcement déjà livrés ; les moves restants facturation/achats/ao/portail/frais
sont des migrations state-only, sûres et révertables) — ne jamais re-fusionner, revenir en arrière coûterait
plus cher que finir. MAIS le découpage backend seul ne donnera jamais l'effet « apps » perçu : ce que
l'utilisateur ressent comme des modules est une expérience de NAVIGATION. Aujourd'hui la sidebar empile ~106
destinations plates (45 codées en dur + 61 items de 16 `module.config.jsx`) toutes du même gris avec le même
accent — Compta, RH, QHSE et Litiges sont visuellement interchangeables. Ce groupe construit la couche
frontend manquante (accent par module, lanceur d'apps, favoris épinglés, breadcrumb→cockpit) en s'ADOSSANT à
ODX5/6/7 (queued), jamais en les dupliquant.

**Vision « Lumière sur Nuit ».** Un fond calme bleu nuit ; la lumière (brass) dépensée avec parcimonie
exactement là où l'énergie circule. Diagnostic central vérifié : la fondation de tokens (F120–P171) est
world-class sur le papier, mais l'app RENDUE est une installation shadcn slate générique — ~604 hex codés en
dur dans `index.css` (top : la palette slate par défaut de Tailwind, pas la marque), coquille Sidebar/Header
100 % figée hors tokens, QUATRE « ors » et TROIS « navys » concurrents, `<body>` en system-ui + `#f1f5f9`,
dark mode à moitié réel. Cette vague est de l'ADOPTION et de la SIGNATURE, pas une refonte de la fondation.

> **Contraintes (chaque tâche VX).** Zéro nouvelle dépendance npm (Radix / Tailwind 4 / recharts /
> @tanstack / @dnd-kit / sonner / lucide déjà installés suffisent — sinon flag [GATED: new dep]). Ne JAMAIS
> toucher les templates PDF devis/facture, les pages PDF publiques, PdfCanvas, `/proposal` (règle #4) ni
> `apps/web`. Clés de stage importées de STAGES.py, jamais codées (règle #2 — seules des COULEURS peuvent
> être tokenisées). UI en français ; hooks e2e (`ap-*`, `att-*`, `pp-*`) préservés et déplacés AVEC leurs
> éléments ; garde `noValidate`/`step="any"` du générateur intacte ; `prix_achat`/marge JAMAIS client-facing.
> Frontend-only — DEUX exceptions round 2, flaggées dans leur tâche : VX61 (endpoint de collecte web-vitals
> dans l'app `reporting` existante) et VX76 (templates d'email HTML, zéro logique) ; `prefers-reduced-motion` respecté partout ;
> contraste AA en clair ET en sombre. Le modèle conseillé par tâche est indicatif (l'orchestrateur arbitre).
> **Coordination inter-plans :** `docs/FRONTEND_GAP_PLAN.md` (câblage fonctionnel des backends X*/Z*, ajouté
> 2026-07-07 via fe-dev) partage trois fichiers avec ce groupe — `GedNavigator.jsx` (FE-XGED14 ↔ VX38),
> `TicketsPage.jsx` (FE-XSAV5/21/28 ↔ VX31), `DevisList.jsx` (FE-ZSAL8/XSAL16 ↔ VX7/20/40/44). Le run qui
> passe en second rebase sur le premier ; les deux plans sont complémentaires (câblage vs design), jamais
> en conflit d'intention.

**A — La signature : la coquille devient TAQINOR (le meilleur ratio qualité perçue ÷ effort de la vague) :**

**B — L'expérience « Apps » (la réponse frontend au verdict module-split ; s'adosse à ODX5/6/7, ne les duplique pas) :**

**C — Le chemin de l'argent (générateur, devis, factures — l'écran le plus stratégique doit être le plus soigné) :**

**D — CRM niveau Attio :**

**E — Cockpits & monitoring vivants :**

**F — Opérations (les îlots non migrés) :**

**G — Fondation, délice, mobile, voix :**

**H — Compléments (critique de complétude Fable, 2026-07-07 — deux espaces blancs confirmés absents de TOUS les plans) :**

---

**ROUND 2 (2026-07-08) — « le meilleur dans TOUS les aspects » : perfection appareils, vitesse, résilience, locale, portes CI.**
*Le fondateur a challengé : « êtes-vous sûrs qu'avec ces tâches ce sera le meilleur ? je veux le meilleur dans TOUS
les aspects, y compris marcher parfaitement sur téléphones et ordinateurs ». Réponse honnête : VX1-47 rend l'app la
plus belle et la mieux organisée — mais « belle » et « marche parfaitement partout » sont deux chantiers. Un second
balayage (11 agents : matrice appareils/Safari, performance réelle, résilience, locale, surfaces secondaires, portes
CI + recherche best-practices + carte anti-duplication + synthèse Fable) a trouvé des CASSES réelles prouvées dans le
code : sur iPhone Safari AUCUN PDF ne s'ouvre (window.open après un await = bloqué en silence, ~10 écrans) et la CI
mobile ne teste que Chrome donc ne peut pas l'attraper ; au-delà de 100 lignes les listes stock/devis/factures/clients
et les KPI du Dashboard MENTENT (troncature silencieuse page 1 DRF) ; le formulaire de devis (20 min de saisie) n'a
ni brouillon ni garde de sortie ; la liste factures sur téléphone empile des valeurs SANS étiquettes ; le sélecteur
de langue promet EN/AR mais ~2 % de l'app est traduite ; les emails partent en texte brut sans logo ; zéro style
d'impression. VX48-82 répare tout cela ET installe les portes CI (WebKit/iPad/zoom/régression visuelle/axe dynamique)
pour que « parfait » le RESTE. Dédupliqué contre YHARD7/8, YTEST, YAPIC, YDATA, FG386, QPERF1 (chacun cité là où on
s'y adosse). Les vérifs de l'orchestrateur ont corrigé les chemins des slices (`features/*/store/*Slice.js`).*

*Coordination avec le **Groupe ARC** (PLAN.md, ajouté 2026-07-08 via PR #333 — socle plateforme) : ARC a dédupliqué
contre VX1-47 nommément ; les points de contact round 2 sont (a) **ARC49/ARC53** (DevisList/FactureList → moteur
DataTable) possèdent désormais la migration que le NE PAS FAIRE round 1 différait — elles doivent atterrir APRÈS
les tâches VX touchant ces fichiers (VX7/20/21/40/44/48/50/52/63/79/80) et préserver leurs comportements ;
(b) **ARC45** (`useResource` fetch/état mutualisé) est la généralisation architecturale des fixes ciblés VX54/55/67 —
les fixes passent d'abord, ARC45 les absorbe ; (c) **ARC39** (plus d'email brut interne, routage notifications) est
complémentaire de VX76 (le TEMPLATE que les deux goulots rendent).*

**I — Cassé AUJOURD'HUI sur téléphone / Safari / tactile :**

**J — Vitesse réelle sur 3G/4G marocaine (et chiffres JUSTES) :**

**K — Ne JAMAIS perdre le travail :**

**L — Les portes CI qui verrouillent tout pour toujours (WORTH-IT uniquement, per recherche) :**

**M — Honnêteté de la langue et de la locale :**

**N — Surfaces secondaires (emails, impression, chrome navigateur, liens, fichiers) :**

---

**ROUND 3 (2026-07-09) — « le meilleur outil avec lequel un employé ait travaillé » : ergonomie par métier, vitesse de saisie, file de travail, droit à l'erreur, interop.**
*Le fondateur a re-challengé : « êtes-vous sûrs ? je veux que les EMPLOYÉS le classent comme le meilleur outil — couvrez TOUS les angles et pour chacun la MEILLEURE solution ». Rounds 1-2 = beau + techniquement parfait ; round 3 = au service de l'employé. Sweep 12 agents (journées du technicien/commercial/directeur/comptable ; vitesse de saisie ; file de travail personnelle ; droit à l'erreur ; interop Excel/WhatsApp/téléphone ; 2 recherches externes G2/Capterra/NN-g/Odoo/Linear/Superhuman ; carte anti-duplication) + synthèse Fable + dédup adversariale contre les 2 084 tâches NT (`docs/new_tasks_plan.md`, PR #345), VX1-82, ARC, FE-*. **L'insight n°1, tracé dans le code : l'intelligence déjà construite et payée n'atteint jamais un écran qui dit « fais ça maintenant »** — la tournée géo-optimisée (endpoint complet, jamais appelée par l'écran du technicien), la signature client (modèle+endpoint+offline construits, zéro UI), le journal d'appel typé du commercial (backend livré, zéro site d'appel), la file de relances FG31, le toast « Annuler » `toastWithUndo` (0 appelant), la délégation d'absence — tous orphelins côté écran. La majorité du round 3 est donc du CÂBLAGE, pas de la construction : le meilleur ratio valeur/effort des trois rounds. Dédup NT appliquée : 5 seeds réécrites/abandonnées (voir NE PAS FAIRE round 3). **Ce qu'aucun audit ne remplace — noté pour Reda, PAS une tâche : une vraie boucle de retour employés** (3 chiffres mesurés avant/après : temps « nouveau lead → 1er appel », taps pour clôturer une intervention, minutes de patrouille matinale ; 30 min d'observation/persona/mois ; un canal « signaler une friction » à un tap + les web-vitals réels de VX61).*

**O1 — La file, la confiance, les gestes quotidiens (tous les employés, plusieurs fois/jour) :**

**O2 — La vitesse de saisie (commerciaux + comptable, dizaines de fois/jour) :**

**O3 — Le droit à l'erreur (tous, la confiance au quotidien) :**

**O4 — Le directeur décide vite et juste (Reda + Meryem, quotidien) :**

**O5 — Le technicien finit sa boucle (1-3 employés, chaque intervention) :**

**O6 — L'harmonie avec le monde extérieur (Excel / WhatsApp / téléphone) :**

**O7 — Le comptable reste dans l'app (persona finance, wiring polish) :**

**NE PAS FAIRE (rejets délibérés de l'audit — ne pas re-proposer sans nouveau contexte) :**
- Ne pas rebâtir la fondation design (F120–P171 livrés et bons) — cette vague est de l'ADOPTION et de la signature.
- Ne pas dupliquer ODX5/6/7 (écran Applications, nav filtrée, extraction registre) — queued ; VX8/9/13 s'y adossent.
- Ne pas remettre en cause le découpage backend ODX ni re-fusionner des modules (verdict : continuer tel que planifié).
- ~~Pas de grille d'apps pleine page à la Odoo comme navigation obligatoire~~ — **INVERSÉ le 2026-08-01 par directive fondateur (« comme Odoo : je rentre, je vois mes apps, je clique, j'y suis, je dois sortir pour changer ») → Groupe ODY (ce fichier).** Le lanceur VX9 reste l'overlay de switch rapide ; les antidotes aux critiques d'origine (mono-app direct, transitions légères) sont ODY3/ODY11/ODY12.
- Aucune nouvelle dépendance npm : pas de framer-motion (CSS + Radix suffisent), pas de cmdk (palette maison livrée), pas de lib confetti (CSS-only), pas de leaflet-markercluster.
- Ne jamais toucher les templates PDF devis/facture, PdfCanvas, `/proposal`, `apps/web` (règle #4).
- Pas de funnel-chart branché sur un modèle de pipeline (règle #2 : le funnel STAGES.py n'a pas encore de modèle Lead/Opportunity backing) — seules les COULEURS de stage sont tokenisées (VX26).
- Pas de migration DevisList/FactureList vers le moteur `ui/datatable` dans cette vague (1 720/1 195 lignes, hooks e2e `ap-*` massivement accrochés au DOM actuel ; le gain ne vaut pas le risque sur le chemin de l'argent) — **désormais possédée par ARC49/ARC53 (PLAN.md, 2026-07-08)** : elles s'exécutent APRÈS les tâches VX touchant ces fichiers et en préservent les comportements.
- Pas de son (le silence est le bon choix pour un back-office partagé) ; l'haptique mobile (VX42) tient ce rôle.
- Pas de moteur de theming par tenant (coût élevé, un seul tenant dominant) ; le nom de société au login (VX34) suffit.
- Pas de WebSockets/indicateurs de frappe (précédent S21 [BLOCKED] — infra fondateur) ; le polling 3 s suffit.
- Pas de badges compteurs sur la BottomTabBar (exige un agrégat backend nouveau) — le bandeau « aujourd'hui » (VX27) couvre le besoin.
- Pas de refonte de Landing.jsx (page vitrine interne à faible trafic — la vraie vitrine est `apps/web`, intouchable).
- Pas de photo produit sur le catalogue dans cette vague (exige champ modèle + migration + pipeline d'upload — candidat à une future tâche BACKEND+UI dédiée). **AUTORISÉE par le fondateur le 2026-08-01 (« photos ok ») → la tâche dédiée est APX18.**
- Pas de clustering cartographique fait main ni d'endpoint de données de démo (hors périmètre frontend-first).

*Rejets round 2 (2026-07-08) :*
- Verrou optimiste Devis/Lead (409 concurrent) — vrai besoin mais exige modèle+serializer backend : territoire YDATA (PLAN.md), pas de doublon ici.
- Lighthouse CI sur le SPA authentifié — OVERKILL (personne ne « bounce » sur un outil interne) ; YHARD7 l'a déjà volontairement laissé optionnel ; VX61 (vitals RÉELS terrain) répond mieux.
- Second gate de budget bundle (BundleMon/size-limit) — YHARD7 possède déjà `check_bundle_budget.mjs` dans le job frontend-perf.
- Matrice Firefox toujours-active — aucun utilisateur Firefox connu ; VX68 = Chromium+WebKit PR-only, le bon ratio.
- Snapshots dark/RTL en matrice dédiée — OVERKILL tant que VX74 n'a pas tranché l'arabe ; si l'AR UI devient réel, ÉTENDRE VX70.
- Serveur de feature-flags + dashboard qualité BI — OVERKILL à 2-5 utilisateurs ; les toggles env existants suffisent.
- Couverture screenshot exhaustive — la taxe de baselines dépasse la valeur ; VX70 reste à 6-8 écrans.
- `useTransition`/virtualisation supplémentaire — aucun long-task MESURÉ ne le justifie (les gels prouvés sont réseau-sériels → VX54/55) ; attendre les données RUM de VX61.
- Service worker de cache API — interdit sur données authentifiées (fuite inter-sessions) ; le precache d'app-shell existe déjà.
- File offline nouvelle — N91/F21 livrés, FG386 possède l'extension ; jamais un second outbox. Snapshot visuel du PDF devis — YTEST10. N+1 devis — QPERF1. Enveloppe d'erreur API/X-Request-Id/429 — YAPIC.

*Rejets round 3 (2026-07-09 — dédup contre les 2 084 tâches NT `docs/new_tasks_plan.md`) :*
- **2FA « se souvenir de cet appareil »** — ABANDONNÉ : `NTSEC14` (« Device trust ») construit la MÊME feature avec un design STRICTEMENT MEILLEUR (modèle `TrustedDevice` révocable + gate société `allow_device_trust` + audit) ; bâtir une version cookie-only ici créerait un 2ᵉ mécanisme parallèle. Attendre/construire NTSEC14.
- **Composant Corbeille générique `<CorbeillePanel>` + écran `/parametres/corbeille`** — possédé par `NTUX7` (app `apps/trash`, `ElementSupprime`, hook event-bus, purge/permissions/audit) ; VX96 ne fait que rendre `Lead` premier adoptant du soft-delete + l'undo-toast.
- **Formulaire de saisie DemandeAchat avec recherche-catalogue** — possédé par `NTP2P3` ; VX102 se limite aux points de montage mobile.
- **Refonte du chatter / 14ᵉ classe `*Activity`** — VX23 (ChatterTimeline) + ARC8/ARC9 ; VX97/VX111 ne font que consommer/monter.
- **Unifier le moteur d'approbation / matrice objet×montant×département** — ARC10 + `NTWFL1` ; VX86/99/100/101/103 câblent l'inbox/signaux AU-DESSUS des 5 sources actuelles et se ré-évaluent si le moteur unifié passe d'abord.
- **Page « Ma journée commerciale » dédiée / bandeau SLA séparé** — 6ᵉ silo ; VX83 « Ma file » absorbe ces sources (relances FG31, leads chauds/SLA, devis expirants).
- **Inbox mentions dédiée `/mentions`** — `NTCOL17` ; VX85 ne fait que réparer le `link` manquant que NTCOL17 exige.
- **Optimiseur de tournée 2-opt avancé** — `NTFSM3` ; VX88 ne fait que consommer l'endpoint `ma-tournee` déjà livré.
- **Undo de l'édition en masse** — `NTUX6` ; VX95 câble `toastWithUndo` sur archive/kanban seulement.
- **Paste-grid Excel (coller 5 lignes)** — différé : à 2-10 employés, l'import fichier (VX109) + « Copier » TSV (VX110) couvrent le volume réel.
- **KPI perso « mes-stats » pour le rôle normal, classement inter-pairs** — différé : vraie motivation mais exige endpoint + RBAC ; re-proposer une fois « Ma file » prouvée, jamais de classement au rôle normal.
- **Correction de ligne de paiement / suppression** — DECISION fondateur (implications GL sous le verrou de période FG115) : logguer la décision (immutable-par-avoir vs endpoint de correction) avant tout build ; détail dans `persona-finance.md`.
- **Client-360 complet, import relevé bancaire OCR, recompute TVA depuis le GL** — logés dans `persona-finance.md`, différés : croisent NTFIN/NTTRE/NTCRD (146 tâches finance NT) → passer une dédup dédiée avant de construire.
- **Re-surfacer l'abonnement iCal (FG6)** — une ligne dans VX46 « Mes préférences » (extension par référence), pas une tâche : le feed + le bouton « Copier » existent déjà sur CalendarPage.
- **Attention fold cross-lane (critic Fable)** — `FactureList.jsx` (VX92/93/97/114), `NotificationBell.jsx` (VX84/86 + VX14/56), `Dashboard.jsx` (VX86/VX27) sont édités par plusieurs lanes : rebaser en séquence (les `@after`/`@coord` posés) ou fusionner par fichier au build — jamais deux lanes concurrentes sur le même fichier.

### Groupe VXD — approfondissement forensique (rework 3 axes, 2026-07-10)

Provenance : rework forensique en 3 axes (beauté / robustesse / amour-employé), ~30 lanes
d'audit + synthèses Fable par axe + une méta-critique Fable finale (`grand-verdict.md`) qui a
contre-vérifié ~20 claims dans le code réel, tué/fusionné/rogné les seeds en collision avec
VX1-116, et corrigé les constats survendus avant transcription. Verdict honnête du méta-critique :
cette passe ne « rapetisse » pas les 3 rounds précédents en VOLUME, mais l'axe robustesse (VXD-A/B)
trouve des bugs d'une gravité qu'aucun round n'avait atteinte — doublon fiscal au retry, paie qui
valide une période avec des bulletins avalés, signature client hors-ligne qui s'évapore, deux
intercepteurs de refresh concurrents qui déconnectent des sessions valides — et la famille
« surfaces fantômes » (VXD-D) prouve que deux features entières (chat Discuss, LeadExpressModal)
rendent sans un seul octet de CSS, qu'un kiosque TV affiche du JSON brut, et qu'un token de focus
soigné est du code mort — des angles morts qu'une lecture JSX-only ne peut pas voir. Axes 2 et 3
ont été livrés partiellement au premier passage (21/45 puis 11/45) et complétés après le
grand-verdict depuis les rapports de lane bruts (`r2-*`, `r3-*`) ; ce qui suit est l'état complet
tel que livré, corrections du grand-verdict déjà appliquées seed par seed. Contraintes héritées à
l'identique du bloc VX : frontend-first, aucune dépendance npm nouvelle sauf tâche taguée
[GATED], ne jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas ni `apps/web`
(règle #4), toute clé de stage vient de `STAGES.py`/`features/crm/stages.js`, jamais un littéral
(règle #2), UI française partout, hooks e2e `ap-*/att-*/pp-*` préservés, `prix_achat`/marge jamais
client-facing, tout scoping multi-tenant côté serveur (`request.user.company`, `perform_create`
force `company`).

---

## AXE 2 — ROBUSTESSE (VX160–VX208, 49 tâches survivantes sur 49 seeds ; 0 tuée, 2 rognées —
SEED-14 re-scopé/SEED-17 rogné, corrections déjà appliquées dans le texte transcrit ci-dessous)

**Sous-groupe VXD-A — Intégrité des mutations & résilience réseau (le niveau sous la
présentation d'erreur)**

*Note : VX117 (au sommet de ce document) EST la transcription de SEED-01 de cette section — ne
pas la dupliquer ici, la numérotation continue directement à SEED-02.*







**Sous-groupe VXD-B — Formulaires : ne jamais perdre une saisie**







**Sous-groupe VXD-C — iOS Safari / WebKit / PWA (la longue traîne au-delà de VX48-53/68)**









**Sous-groupe VXD-C (suite) — Viewport & performance réelle**












**Sous-groupe VXD-C (suite) — Accessibilité forensique (WCAG 2.2 prouvée file:line)**

*Acquis vérifiés à NE PAS refaire : Radix (focus-trap/Échap/flèches), sonner déjà
`aria-live=polite`, anneau `:focus-visible` global + `scroll-margin` (`index.css:89-132`),
reduced-motion (`:67-87`), cibles 44px `pointer:coarse` (`:156-173`), DataTable exemplaire
(`aria-sort`/`scope`/live).*








- [BLOCKED: dev-dep manquante, npm install impossible dans ce worktree — `eslint-plugin-jsx-a11y` absent de package.json/eslint.config.js ; la tâche elle-même se marque [GATED si dev-dep à ajouter]] VX198 — **[GATED si dev-dep à ajouter] Garde statique jsx-a11y ciblée : empêcher d'ÉCRIRE (@lane: frontend/ios)
  la régression (complément build du scan runtime VX71).** Rien n'empêche la réintroduction des
  trous ci-dessus (label sans contrôle, rôle sans props ARIA requises, interactif non
  focalisable) — `eslint-plugin-jsx-a11y` absent de la config (à confirmer ; sinon [GATED]
  dev-dep). Fix : sous-ensemble ciblé en warn→error : `label-has-associated-control`,
  `role-has-required-aria-props`, `interactive-supports-focus`, `click-events-have-key-events`,
  `img-redundant-alt`. Files : `frontend/eslint.config.js` (aucun code métier). DoD : `npm run
  lint` signale un `<label>` sans contrôle associé ; `frontend-lint` échoue sur une régression
  neuve ; le build actuel reste vert. (T2 — S, sonnet) (@lane: frontend/ios)

**Sous-groupe VXD-A (suite) — Sécurité frontend & observabilité (les échecs que personne ne
voit)**

*Non-défauts vérifiés à NE PAS re-signaler : auth par cookie httpOnly (aucun jeton en
localStorage, `AUTH_LOCALSTORAGE_KEYS=[]`), rendus chat/KB/copilote en arbres React (pas
d'injection), `rel=noopener` présent (faux positif multi-ligne), `prix_achat` correctement masqué
partout côté client.*

*Note : la graine TOTP 2FA exfiltrée vers `api.qrserver.com` (SEED-41) est déjà transcrite en
détail en tête de document — voir **VX120**. Ne pas la reconstruire ici.*





- [BLOCKED: partiel — voir DONE LOG 2026-07-12 ; codemod ~104 fichiers + garde CI restent hors budget d'une session sans build/lint] VX203 — **Contrat d'erreur UNIQUE : fin du double-toast (35 pages), `getApiError` (@lane: frontend/data)
  canonique (259 clones), `iaApi` aligné (le 403 IA n'est plus muet).** Trois moitiés du même
  contrat, explicitement renvoyées à l'axe robustesse par la synthèse beauté : (a)
  `api/axios.js:63-70` toaste DÉJÀ toute erreur ≠401/404, mais ~35 pages re-toastent dans leur
  `catch` (3 fichiers seulement posent `suppressErrorToast`) → DOUBLE toast sur des centaines de
  chemins. Contrat : l'intercepteur est la source par défaut ; tout `catch` qui gère INLINE passe
  `{suppressErrorToast:true}` ; garde grep `scripts/check_double_toast.mjs` dans frontend-lint.
  (b) 259 extractions inline `.response?.data?.detail` ré-implémentent une version PARTIELLE du
  helper existant (`lib/toast.js:92-107`) — promouvoir `lib/apiError.js` (`{message,
  fieldErrors}`, cas `non_field_errors`/tableaux/429/500 HTML/timeout), codemod des sites vers
  l'import unique (VX171 en consomme `fieldErrors`). (c) `iaApi.js` ne toaste RIEN globalement
  hors 401 : un 403 du catalogue d'actions agentiques ou un 500 FastAPI est INVISIBLE — aligner
  sur le contrat (a) en préservant les dégradations volontaires (`available:false`) via
  `suppressErrorToast`. Files : `api/axios.js`, `api/iaApi.js`, `lib/apiError.js` (extrait de
  toast.js), les ~35 pages fautives, `scripts/check_double_toast.mjs` (nouveau). DoD : un 500
  forcé = EXACTEMENT un toast (test) ; grep `.response?.data?.detail` hors helper = 0 ; un 403 IA
  surface un toast FR ; tests des formes DRF. (T2 — M/L, sonnet) (@lane: frontend/data)




---

## AXE 3 — AMOUR-EMPLOYÉ (VX207–VX252, 46 tâches survivantes sur 47 seeds ; 1 tuée par le
grand-verdict — SEED-03 — dont le delta est reporté en note sur VX56/VX86, jamais transcrit
comme tâche)

**Sous-groupe VXD-I — Attention & handoffs (le badge redevient CROYABLE). @after
VX83-86/99-101 (round 3, non construit) — transcrire chaque @after tel quel.**







**Sous-groupe VXD-I (suite) — Handoffs cross-persona (la main gauche apprend ce que fait la
droite)**







**Sous-groupe VXD-K — Le commercial : chaque job compté en clics**







**Sous-groupe VXD-L — Le technicien terrain**




**Sous-groupe VXD-M — Le comptable : le mois compté en clics**






**Sous-groupe VXD-N — Le directeur/admin : contrôle et supervision**





**Sous-groupe VXD-O — La vélocité de saisie**





**Sous-groupe VXD-P — Forgiveness / historique / confiance**





**Sous-groupe VXD-Q — Interop & onboarding→maîtrise**




**Sous-groupe VXD-R — L'âme au quotidien**





- [BLOCKED: attend VX156 — celebrate.js non construit] VX252 — **[BACKEND additif léger] Maîtrise personnelle : milestones non comparatifs, KPI
  d'adoption clavier, garde anti-backfire de la gamification. @after VX156 (célébration devis
  signé), @coord NTCRM23/24/28, NTUX40.** Recherche 2026 (Trophy.so, Carnegie Mellon) : ~10 % des
  employés sont motivés par la compétition ; les 90 % restants sont ACTIVEMENT démotivés par un
  classement. Trois pièces : (a) étendre `celebrate.js` (VX156, CSS-only) d'un déclencheur
  « milestone personnel » à seuils déterministes et espacés (50ᵉ intervention signée, 25ᵉ devis
  signé) — célébré UNE fois, jamais visible d'un collègue/manager, reduced-motion → toast simple ;
  (b) KPI interne d'adoption clavier (« % actifs ayant utilisé ⌘K 1×/semaine », signal `POST
  /ux/usage-signal/` best-effort jamais bloquant) — gate Directeur/Admin, JAMAIS montré au
  commercial (@coord NTUX40 — métriques disjointes, vérifier) ; (c) garde anti-backfire à
  INSCRIRE sur NTCRM23/24 avant leur build : `metrique_qualite_associee` affichée à côté du score
  brut + participation réellement opt-in invisible — jamais un score de vitesse seul. Files :
  `ui/celebrate.js`, points d'appel `MaJourneePage.jsx`/`SigneDialog`, `apps/reporting/models.py`
  + endpoint léger, `providers/CommandPalette.jsx` (compteur), note sur NTCRM23/24. DoD : la 50ᵉ
  intervention signée célèbre une fois (pas au 51ᵉ, pas au reload) ; le KPI calcule un % réel et
  échoue gracieusement à 0 ; la note NTCRM est posée dans le plan ; tests. (T3 — M, sonnet)
  (@lane: backend/notify — @after VX156)

---

## NE PAS FAIRE (Groupe VXD) — fusion dédupliquée des trois axes

**Déjà possédé par VX1-116 (couches design/coquille/cockpits) :**
- Re-signature coquille/marque, accents module, lanceur, cockpits → VX1-8, VX9-12/ODX5-7,
  VX15/27/29-34. Couleurs de stage StatusPill → VX26 (règle #2).
- Palette catégorielle data-viz + annotations → VX41 (danger zone) ; la rampe « solaire »
  d'un rapport source est versée comme INPUT à VX41, jamais re-proposée.
- Illustrations SVG d'états vides + confetti générique → VX40 (« délice mesuré ») ; VX156 (axe1
  S40b, ex-« signé célébré ») ne câble QUE le moment signé, jamais le système d'illustration.
- Theming par tenant, refonte Landing → rejets fondateur explicites (la « photo produit
  catalogue », durcie ici en rejet, a été AUTORISÉE par mot fondateur le 2026-08-01 → APX18)
  (rounds 1-3, PLAN2 NE PAS FAIRE). La « grille d'apps pleine page à la Odoo », rejetée à ces
  mêmes rounds, a été INVERSÉE par directive fondateur du 2026-08-01 → Groupe ODY (les trois
  autres rejets restent en vigueur).
- Grain `feTurbulence` sur la sidebar, `@starting-style` (pattern de référence, pas un défaut),
  `content-visibility` sur les listes non virtualisées (territoire perf, pas beauté) → rejetés/
  hors-axe, non repris.
- Badge persistant d'échec PDF sur la ligne, identifiant support dans ErrorBoundary → possédés
  par VX172 / VX206 respectivement.

**Déjà possédé par VX48-72 (appareils/Safari/perf nommés) :**
- PDF iOS (onglet pré-ouvert), popup-block detection, `data-label` tables, clavier iOS
  VisualViewport, `title=` tactile, balayage compat → VX48/49/50/51/52/53.
- Troncature 100 lignes + pagination parallèle, timeout axios + annulation, poll onglet caché,
  cold-path, préchargement, chunk-name, e2e comptes-justes, Web Vitals → VX54-VX61.
- Brouillon auto DevisGenerator + garde de sortie → VX62 ; JSON brut DevisList → VX63 ; error
  boundaries routes nues → VX64 ; `?next=` login → VX65 ; anti-double-submit Button → VX66.
- Safari/iPad/zoom/visual-regression/axe/Sentry e2e → VX68/69/70/71/72.
- `.agent-sql` momentum-scroll → CSS mort (0 consommateur), retiré de VX175 ; sa suppression
  appartient à VX121.
- Rejets round 2 toujours en vigueur : verrou optimiste 409 (→YDATA), Lighthouse-CI sur le SPA
  authentifié, BundleMon 2ᵉ gate, Firefox en matrice, service-worker cache des RÉPONSES API, 2ᵉ
  outbox offline, virtualisation sans mesure. VX187/VX188 sont les seules exceptions MESURÉES
  (DoD Profiler à l'appui) ; VX179 cache des ASSETS/médias en lecture, jamais des réponses API.
  `animation-timeline: scroll()` non confirmé dans le code → ne pas construire spéculativement ;
  attribution LoAF dans le beacon → amendement du build de VX61 (même fichier `vitals.js`), pas
  une tâche séparée ; note HMR du singleton `fieldOutbox` → un commentaire de code, pas une
  tâche ; moteur de conflit offline / CRDT → le signal de conflit EST le message serveur par op de
  VX119.
- Gate visuel bloquant par PR → contredit la décision LIVRÉE de VX70, jamais un amendement sans
  raison.

**Déjà possédé par VX73-116 (locale, files, saisie, argent, amour-employé) :**
- Sélecteur de langue menteur + `Ctrl K` → VX73 ; arabe RTL décision → VX74 ; format
  argent/date + garde CI → VX75 (VX143 en est l'annexe d'exécution, pas un doublon) ; compression
  photo → VX77 ; 404 branché → VX78.
- « Ma file » unique + cloche AUTRES + plomberie records + signaux approbation → VX83-86,
  VX99-101 ; jamais un 2ᵉ agrégateur ni une 2ᵉ boîte de réception parallèle (VX214 l'atteste par
  reshape) ; jamais de hook de polling séparé pour la cloche (VX56 possède
  `useVisibilityAwarePolling`, cloche incluse).
- Journal d'appel un-geste + tournée géo + délégation absence + technicien + signature client +
  résumé client → VX87/88/103/105/106/107.
- LeadForm Escape/autofocus, « Ajouter ligne » focus, convergence FactureForm, « enregistrer et
  créer un autre », défauts intelligents, Enter-pour-ajouter → VX89-94.
- `toastWithUndo` câblé (archive/kanban), soft-delete Lead, « qui a fait quoi », lien Historique,
  `tel:`/`wa.me`, import fournisseurs, « Copier » TSV, pièce jointe note chatter → VX95-98,
  VX108-111.
- Drill-down relances, exercice fiscal, sélecteur dates export, KPI compta, relance en lot →
  VX112-116.
- « Mes préférences » (thème/densité/module d'atterrissage/mouvement) → VX46 ; HelpTip
  contextuel → VX47 ; emails de marque wrapper → VX76 ; export XLSX horodaté → VX81 ; liens
  partageables `?id=` → VX79 ; impression → VX80 ; chrome onglet + non-lus → VX82.
- Rejets round 3 : 2FA remember-device (→NTSEC14), Corbeille générique (→NTUX7), formulaire
  DemandeAchat catalogue (→NTP2P3), refonte chatter (→VX23/ARC8-9), moteur d'approbation unifié
  (→ARC10/NTWFL1), « Ma journée commerciale » silo (→VX83 absorbe), inbox mentions dédiée
  (→NTCOL17), optimiseur 2-opt (→NTFSM3), undo bulk-edit (→NTUX6), paste-grid Excel multi-cellules
  (différé — VX237 est le collage UNITAIRE), KPI perso PUBLIC/classement (différé — VX219 est
  privé, VX252 non-comparatif), correction de ligne de paiement (DECISION), iCal abonnement
  (VX46), Client-360/OCR relevé (persona-finance).

**Frontières NT/ARC intouchables (les trois axes) :**
- Vues serveur partagées / FilterBuilder ET/OU / bulk-edit preview-undo / corbeille transverse
  (`apps/trash`) / quick-create palette générique / favoris / peek-hover de LIGNE / densité par
  vue → NTUX (frontière explicite « pas de changement visuel/shell (Groupe VX) »,
  `new_tasks_plan.md:2436`).
- Boîte email par user / RDV Calendly / boîte partagée / inbox mentions `/mentions` / digest
  personnel → NTCOL.
- Offline multi-module / accueils mobiles par rôle / géofence / scan QR / onboarding mobile
  « Ma journée » → NTMOB, NTMOB33.
- i18n/RTL/langue par user/polices arabes → NTI18N (attention : NTI18N5/17/30 touchent le moteur
  `/proposal` — règle #4, ne jamais y toucher côté client).
- Leaderboard/défis d'équipe → NTCRM23/24 (seul le garde-fou de VX252 s'y greffe, jamais le
  système lui-même).
- Moteur d'approbation unifié → ARC10/NTWFL1 ; migration DataTable DevisList/FactureList →
  ARC49/53 (VX180/VX178/VX184 se corrigent AVANT que la migration n'hérite du défaut) ;
  `useResource` → ARC44/45 ; RecordShell → ARC46 (VX159/VX250 construits indépendants, migrables
  dedans ensuite) ; politique magasin-unique → ARC26.
- Verrou optimiste backend 409 → YDATA ; file photo binaire offline → FG386 (« jamais un 2ᵉ
  outbox », VX119 ne construit PAS de moteur CRDT).

**Mécanique transversale (toujours vraie, tous les VXD) :**
- Frontend-first ; aucune dépendance npm nouvelle sauf tâche taguée [GATED] (VX120 QR 2FA,
  VX198 jsx-a11y, VX247(e) seed_demo — tous soumis au fondateur avant tout build).
- Jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas, `apps/web` (règle #4) — le
  moteur RESTITUE, ne change jamais un statut (VX250(a) est une LECTURE) ; les PDF
  d'intervention/contrat (WeasyPrint) sont hors règle #4 mais on n'y crée jamais un 2ᵉ mécanisme
  concurrent (VX246(b)).
- Toute clé de stage vient de `STAGES.py`/`features/crm/stages.js` (règle #2) — jamais un
  littéral (VX224, VX248 raccourcis `1..4`, VX211 `queueViews`).
- `prix_achat`/marge jamais client-facing ni dans un peek/notification/WhatsApp/milestone
  (VX213 montants DA, VX217 AttentionPeek, VX156 messages — tous montants client-safe).
- Jamais d'envoi WhatsApp/email automatique — aperçu-puis-clic partout (règle manuel-wa.me
  fondateur, VX222/VX245/VX252) ; jamais de mutation via lien email non authentifié (VX212).
  `api.qrserver.com` et tout rendu tiers de secrets sont interdits (VX120).
- Ne pas dé-gater `/reporting/commercial` (VX219 ajoute une carte personnelle, le reporting
  manager reste manager) ; ne pas élargir le Journal global (VX243 = lecture record-scopée,
  jamais un grant company-wide) ; ne JAMAIS déverrouiller un accès nav/rôle sans décision
  fondateur.
- Hooks e2e `ap-*/att-*/pp-*` préservés partout ; UN seul Toaster ; scoping tenant TOUJOURS
  serveur (`request.user.company`, `perform_create` force `company`) ; jamais `count()+1` pour
  une référence ; migrations additives/révertables ; noter AUTH au DONE LOG pour
  VX235/VX242/VX243 ; FR partout.

### Group QC — Moroccan company autocomplete on client creation (founder request 2026-07-01)

*From Reda: « in Odoo I can easily find Moroccan companies when I start typing their name as new clients — add this to my ERP. » Research verdict: Odoo's Partner Autocomplete is a paid IAP service backed by Clearbit WEB data — it does NOT return ICE/RC/IF for Morocco (Moroccan Odoo integrators install manual `partner_ice`/`l10n_ma_legal` field modules). There is NO free official API or open dataset (OMPIC DirectInfo has no API and its legal notice bans data reproduction; ice.gov.ma is CAPTCHA-gated; data.gov.ma has no company register). The ONLY compliant registry-backed API with Morocco depth is the paid Inforisk/Charika offer (~950k companies, licensed OMPIC data, quote-only pricing). Scraping any of these violates their ToS → rule #5 (risk file + founder approval) and is NOT pursued. Code side is ready: `Client` already has `ice`/`if_fiscal`/`rc` (and `Fournisseur` the identical trio — no migration), the generic async `Combobox` (`frontend/src/ui/Combobox.jsx`) is the typeahead, and the PVGIS proxy (`apps/parametres/pvgis.py`) is the cached-external-lookup pattern for the gated provider.*

- [BLOCKED: paid — needs founder-provisioned Inforisk/Charika account] QC2 — **[GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style experience).** Behind a flag (default OFF), plug a licensed Moroccan-registry provider into the QC1 seam: type a name → provider suggestions (ICE/RC/IF/adresse from licensed OMPIC data) → pick → auto-fill, with server-side caching (24 h, PVGIS-proxy pattern), rate limiting, and a clean no-key degrade to QC1's own-data mode. NEEDS FOUNDER: an Inforisk/Charika account + contract/budget (pricing is quote-only) — OR a founder-led OMPIC licensed-feed inquiry. Never scrape OMPIC/ice.gov.ma/Charika (ToS-prohibited; rule #5). **Done =** with a provider key the autocomplete returns registry-backed Moroccan companies and fills the legal IDs; without it, behaviour is exactly QC1; tests cover the provider seam + the degrade + the never-leak of the key client-side. Files: a provider client in `apps/crm/` (or `apps/parametres/` beside pvgis), `apps/crm/views.py`, settings flag, tests. (DEP/COST — needs founder-provisioned Inforisk/Charika account; note in DONE LOG) (@lane: backend/crm) (@after: QC1)

### Groupe ODY — L'ERP-Apps : j'ouvre → MES apps ; j'entre → je suis DANS l'app ; je sors → j'en choisis une autre (paradigme Odoo assumé, en mieux — fondateur 2026-08-01)

*Provenance : directive fondateur 2026-08-01 (« comme Odoo : quand je rentre je vois des apps, je
clique sur une et j'y rentre, je dois sortir pour avoir l'autre — et je veux le plus bel ERP »).
Cette directive INVERSE deux rejets antérieurs, amendés chirurgicalement dans le commit d'insertion :
le NE PAS FAIRE VX (« pas de grille pleine page… ») et la ligne correspondante du NE PAS FAIRE VXD
(les rejets voisins — theming par tenant, refonte Landing — restent en vigueur ; la photo
produit a été autorisée le 2026-08-01 → APX18).
Le même commit ajoute `ODY` à `unmapped_ok` de `docs/BUILD_ORDER.yml` et re-tamponne le fingerprint
CODEMAP. Conception : 4 éclaireurs (balayage anti-duplication de tous les plans, état réel du code
fichier par fichier, recherche web Odoo 17/18 + SaaS best-in-class, contraintes CI machine) + critique
adversariale Opus (15 défauts corrigés, 5 manques comblés) + synthèse Fable.*

**LE PARADIGME (3 phrases).** (1) À l'ouverture de l'ERP on atterrit sur le **Menu d'accueil** :
une grille plein écran qui ne montre QUE les apps installées par la société (ModuleToggle) ET
autorisées pour le rôle — rien d'autre, pas de sidebar générale. (2) Cliquer une app = y **entrer
complètement** : toute la coquille devient celle de l'app (identité, accent, nav de SES écrans
uniquement — les autres apps n'existent plus à l'écran). (3) Pour changer d'app on **sort**
(bouton ⊞ / logo → Menu d'accueil) — exactement Odoo ; les raccourcis power-user (⌘K, launcher
overlay VX9, `g`+lettre) restent par-dessus comme « mieux qu'Odoo », jamais comme substitut du
paradigme.

**CE QUI EXISTE DÉJÀ (s'adosser, ne JAMAIS dupliquer).** Toute la tuyauterie est livrée : manifests
+ catalogue + fermeture de dépendances (ODX2/3, `core/modules.py`), écran Paramètres→Applications
fonctionnel (ODX5, `pages/parametres/ApplicationsSection.jsx`), `modules_desactives` au bootstrap
`/auth/me/` + nav filtrée + garde de route (ODX6, `router/moduleGating.js` + `moduleLoader`),
registre `module.config.jsx` de 41 modules + Sidebar générique partielle (ODX7/ARC48/ARC54 — les
routes sont migrées, la Sidebar garde des sections en dur : tête Dashboard/Ma file/Messages,
DOCUMENTS/ged, INTELLIGENCE, ADMINISTRATION, `Sidebar.jsx:150-208`), gating transversal par société
(ODX23 + ARC28/29/33 via `core/platform.py`), KPI fédérés (ARC40, `GET /reporting/reports/kpi-federes/`),
accents par module (VX8), launcher overlay (VX9), épinglés (VX10), breadcrumb→cockpit + dernier
module (VX11), grille mobile « Plus » (VX12), préférence module d'atterrissage (VX46,
`pages/preferences/prefs.js`), thème white-label société (SCA24), prefetch au survol
(`router/prefetchMap.js`), scaffold de module (`scripts/scaffold-module.mjs` — doit rester
compatible). ODY est la couche PARADIGME + BEAUTÉ posée sur ce socle : essentiellement
frontend/shell, zéro nouveau modèle backend (exceptions signalées tâche par tâche).

**Contraintes (chaque tâche ODY).** Celles du Groupe VX s'appliquent intégralement : zéro nouvelle
dépendance npm (sinon [GATED: new dep] — `@dnd-kit/sortable` N'EST PAS installé, seul `core` l'est),
règles #2 (STAGES.py) et #4 (/proposal) intouchées, jamais `apps/web`, hooks DOM e2e
(`.header-title`, `ap-*`/`att-*`/`pp-*`) préservés ou déplacés AVEC leurs éléments, garde
`noValidate`/`step="any"` du générateur, `prix_achat` jamais client-facing, UN seul Toaster,
contraste AA clair ET sombre, `prefers-reduced-motion` partout. En plus, propres à ODY :
**jamais un 2ᵉ registre** (l'unique source des apps = registre ODX moduleConfigs ∩ modules actifs ∩
rôles — toute tâche qui liste des apps consomme ODY1) ; **toute tâche qui change un comportement
asserté par un test (vitest OU spec Playwright) adapte ce test DANS la même tâche** — jamais une
spec cassée léguée à la suivante ; chaque piège Odoo documenté a son antidote nommé (grille = clic
en plus → ODY3 ; breadcrumb pile-vs-hiérarchie → ODY5 ; menus profonds → vague C ≤2 niveaux ;
lenteur perçue → ODY11/12 ; incohérence inter-apps → ODY9 un composant, quatre surfaces).

**A — LE PARADIGME (la coquille bascule) :**

**B — LE PLUS BEL ÉCRAN D'ACCUEIL (la signature) :**

**C — CHAQUE APP DEVIENT UN MONDE COMPLET (passes app par app — l'immersion n'est belle que si l'intérieur est complet).**
*Checklist commune : module.config COMPLET (tous les écrans de l'app accessibles depuis SA nav —
croiser avec `router/index.jsx`, zéro route orpheline), cockpit d'app digne d'une porte d'entrée
(ModuleHero VX15 + actions rapides + KPI), icône/accent/description FR justes dans le manifest ET
le config, sous-menus ≤2 niveaux, liens croisés conformes ODY7, hooks e2e intacts. Dashboard
devient l'app « Tableau de bord », le chat l'app « Messages ». Lanes disjointes par app.*

**D — L'APP STORE INTERNE (installer une app doit donner envie) :**

**E — LE TRANSVERSE : ce qui échappe à l'immersion (le systray, mieux qu'Odoo) :**

**F — QUALITÉ, BASCULE, RETRAIT DU LEGACY (« parfait » doit le rester) :**
- [ ] ODY33 — **Retrait du legacy : à la fin, UN seul shell dans le code.** Une fois ODY31/32 verts ET le paradigme validé par le fondateur en prod : retirer le chemin de rendu « sidebar globale » legacy, le flag ODY30 (et son triplet env) et le CSS mort ; noter l'allègement du bundle. **Done =** grep du chemin legacy vide, e2e complètes vertes, chiffre bundle au DONE LOG. Files: frontend/src/components/layout/Sidebar.jsx, frontend/src/components/layout/Layout.jsx, frontend/src/components/layout/Header.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/shell-ody) (@after: ODY31, ODY32) [GATED: validation fondateur du mode Apps en prod]

**NE PAS FAIRE (Groupe ODY) — anti-duplication vérifiée (aucun doublon sur 6 fichiers de plan) :**
- Ne PAS re-bâtir : le launcher overlay (VX9 — devient le switch rapide), l'écran Applications
  (ODX5 — ODY24 l'habille), le registre de modules (ODX2/3/7 + ARC28 — ODY1 n'est qu'une VUE
  croisée dessus), le gating backend (ODX6/23, ARC29/33/40), les accents (VX8), le breadcrumb
  cockpit (VX11), la préférence d'atterrissage (VX46), le thème par société (SCA24).
- Ne PAS maintenir deux UX en parallèle : le flag ODY30 est un kill-switch temporaire (chemin OFF
  = smoke d'urgence, non testé unitairement) dont le retrait est queued (ODY33).
- Ne PAS toucher : PDF/`/proposal` (règle #4), STAGES.py (règle #2), `apps/web`, le contrat DOM
  e2e (`ap-*`/`att-*`/`pp-*`/`.header-title`) autrement qu'en déplaçant hooks + specs ensemble.
- Ne PAS créer : de sous-menus > 2 niveaux, de 2ᵉ Toaster, de 2ᵉ clé localStorage de favoris,
  de liste d'apps locale hors ODY1, de tuile « Frais »/« Portail » (frais = section Compta ;
  portail = route publique à jeton), ni confondre la boutique ODY24 avec la marketplace
  d'extensions NTEXT14.

### Groupe EZ — L'ERP le plus FACILE : les 5 trajets quotidiens au budget de clics, gardés en CI (fondateur 2026-08-01 — « the easiest to use for employees »)

*Provenance : challenge fondateur 2026-08-01 (« are you sure it's the prettiest AND the easiest
for employees? look at what the best do and what users prefer, go extremely deep »). Réponse
honnête : le BEAU est couvert (VX livré, ODY/APX en file) et la FACILITÉ l'est largement (axe
amour-employé VX83-116 + VX207-252 livré : Ma file, défauts intelligents, raccourcis, undo
ponctuels, brouillon devis, quick-create, HelpTip…) — mais un audit Opus des 5 TRAJETS QUOTIDIENS
comptés en clics dans le code réel + 4 recherches web (plaintes G2/Capterra des utilisateurs
d'ERP, patterns des outils aimés Linear/Superhuman/Attio, recherche saisie NN/g-Baymard-Fiori,
terrain Jobber/ServiceTitan/Scandit) ont trouvé des frictions qu'AUCUN plan n'adresse et 2
capacités absentes de TOUT plan (undo universel, dictée inline). EZ = uniquement ces manques,
puis VÉRIFIÉ par une critique adversariale Opus (10 corrections bloquantes appliquées — dont 3
tâches rétrécies parce que l'infra existait déjà, et 1 fausse prémisse tuée). Chiffres d'audit :
appel+note+rappel = 5-7 clics ; devis 3 kWc→WhatsApp = 8-9 clics dont un ABANDON post-création ;
clôture intervention = 40-45 taps dont 10 de pure paperasse de statut ; réception+rangement = 2
modules non reliés (le flux scan construit-testé-jamais-monté appartient à NTWMS5) ; encaissement
= 3 clics (excellent) mais sans suite offerte. Le commit d'insertion ajoute `EZ` à `unmapped_ok`
de `docs/BUILD_ORDER.yml`, pose la frontière EZ15↔NTMOB30 dans new_tasks_plan.md, et régénère
CODEMAP §10 + fingerprints.*

**LA DOCTRINE (issue des recherches).** (1) Agir puis pouvoir ANNULER bat confirmer puis agir
(NN/g) — l'undo devient la règle, la confirmation l'exception réservée à l'argent, aux envois et
au destructif. (2) Le système fait la paperasse, jamais l'employé — un horodatage connu ne se
re-saisit pas. (3) Après chaque action, l'action SUIVANTE évidente est offerte (créer → envoyer ;
recevoir → ranger ; encaisser → voir l'encaissement). (4) Le travail n'est JAMAIS perdu
(brouillons, photos, files visibles). (5) Chaque budget de clics est un TEST CI, pas une intention.

**Contraintes (chaque tâche EZ).** Celles de VX/ODY/APX s'appliquent intégralement (zéro dep npm,
règles #2/#4, hooks e2e + specs dans la même tâche, `noValidate`/`step="any"`, prix_achat, UN
Toaster, AA, reduced-motion, tactile ≥44 px). En plus : l'undo ne s'applique JAMAIS aux actions
d'argent, aux suppressions dures ni aux envois (AlertDialog reste) ; la garde serveur
`transition_block_reason` n'est JAMAIS dupliquée côté client (décision VX105) ; JAMAIS un 2ᵉ
outbox (décision VX105 ×3 — on ÉTEND `features/installations/offline/*`) ; aucun backend nouveau
sauf mention explicite. Propriété : EZ7 touche `apps/installations` (PLAN_SERVICE) et EZ10/EZ11
`pages/stock`+`features/magasin` (PLAN_SUPPLY) — conflits de CODE possibles si une session
domaine tourne en parallèle, aucune migration dans leurs apps (celle d'EZ7 va dans `parametres`).

**A — LE TRAJET DU COMMERCIAL (chemin rapide ≤4, chemin daté libre ≤6) :**

**B — LE TRAJET DU DEVIS (plus jamais d'abandon après 20 min de saisie) :**

**C — LE TRAJET DU TECHNICIEN (40-45 taps → ≤15 hors photos, zéro photo perdue) :**

**D — LE TRAJET DU MAGASINIER (deux modules enfin reliés — le montage du scan appartient à NTWMS5) :**

**E — LE TRAJET DU COMPTABLE (le meilleur parcours de l'app, terminé jusqu'au bout) :**

**F — LES DEUX ABSENTS SYSTÉMIQUES + LES GARDES :**
- [x] (déjà présent — origin/main@6773842e) EZ17 — **La gate des trajets : les budgets de clics deviennent des specs CI (méthode de comptage ÉCRITE).** Nouvelle spec `frontend/e2e/parcours-budget.spec.js` : rejoue les 5 trajets sur `manage.py seed_demo` (identifiants `e2e/helpers.js`) et COMPTE les interactions. MÉTHODE (imposée par la critique) : état de DÉPART et d'ARRIVÉE déclarés par trajet ; unité = 1 par `fill()` et 1 par « choisir une option » quel que soit le widget ; comptage par compteur d'événements `isTrusted` injecté via `page.addInitScript` CROISÉ avec un helper de test qui incrémente à chaque action (échec si divergence) ; le nudge 45 s d'EZ2 avancé par `page.clock` (Playwright ≥1.45, jamais `waitForTimeout`) ; projet/viewport DÉCLARÉS + `testIgnore` sur les autres projets ; mesure avec réglage signature OFF (EZ7). BUDGETS : appel+note+rappel — chemin rapide (chip) ≤4, chemin daté libre ≤6 ; création devis (formulaire déjà saisi) → WhatsApp prêt ≤6 ; clôture intervention ≤15 hors prises de photo ; réception ≤3 + 1/ligne d'écart ; encaissement ≤3 puis suite en +1. **Done =** 5 parcours verts et stables (2 runs), rouge si un clic superflu s'ajoute (test du test), méthode documentée en tête de spec. Files: frontend/e2e/parcours-budget.spec.js (nouveau). (ROUTINE — L, sonnet) (@lane: ez-gardes) (@after: EZ2, EZ3, EZ6, EZ7, EZ10, EZ13)

**NE PAS FAIRE (Groupe EZ) — la carte de couverture + la critique font foi :**
- Ne RIEN re-construire de LIVRÉ : Ma file (VX83), défauts intelligents (VX93), quick-create
  (VX91/NTUX10), brouillon devis (VX62 — EZ4 corrige son angle mort), HelpTip (VX47), erreurs
  françaises DevisList (VX63), densité globale + par vue (NTUX17), recherche globale (VX13),
  inline edit DataTable (NTUX8), surlignage `?devis=` (déjà livré — EZ3 le consomme), conversion
  kWc (déjà écrite — EZ5 la réutilise), API casier effectif (déjà prête — EZ11 la branche).
- Ne PAS monter le flux scan (NTWMS5) ; ne PAS bâtir le moteur offline générique (NTMOB1/2/3 —
  EZ8 étend l'outbox EXISTANT aux binaires, jamais une 2ᵉ pile ni un 2ᵉ badge, et ne touche pas
  `frontend/src/lib/offlineOutbox.js` réservé par NTMOB1) ; ne PAS dupliquer
  `transition_block_reason` côté client (VX105) ; ne PAS trancher le contrat d'erreur unique
  (VX203, gaté — EZ16 est une garde mécanique) ; la dictée TERRAIN appartient à NTMOB30.
- Avant TOUT travail SavedView futur : réconcilier NTUX1 `[ ]` avec `crm.SavedView` (LB48 livré)
  — incohérence relevée (NTUX2/3/4 `[x]` référencent NTUX1 `[ ]`).
- Le paste-grid Excel reste rejeté (VXD) ; l'undo EZ14 jamais sur l'argent/suppressions/envois ;
  pas d'heure sur les relances sans tâche SCHEMA dédiée (DateField partout aujourd'hui).

### Groupe VAO — « Veille appels d'offres » : voir TOUS les avis du Maroc, une porte automatique + une porte manuelle (fondateur 2026-08-01 — « comment trouver les AO sans qu'on me les signale ? »)

*Provenance : question fondateur 2026-08-01 après le dépôt de l'AO FRDISI (« je n'ai jamais vu cet
appel d'offres, il a fallu qu'Accordia Tech me le dise »). Réponse produite par 13 agents de
recherche en 3 rondes (portail officiel, accès technique vérifié en main, agrégateurs privés,
portails sectoriels, cadre légal, open data, agrégateurs internationaux, traque de l'avis FRDISI),
puis vérification hands-on de la recette d'accès et synthèse Opus.*

> **LA DÉCOUVERTE QUI CHANGE LE PRODUIT : l'AO FRDISI n'a JAMAIS été publié.** La FRDISI
> (Fondation de Recherche, de Développement et d'Innovation en Sciences et Ingénierie, campus
> SupTech de Mohammedia) est une **fondation de droit privé** : elle n'est pas soumise au décret
> 2-22-431 et n'a aucune obligation de publier. Zéro trace sur `marchespublics.gov.ma`, zéro
> rubrique « appels d'offres » sur `frdisi.ma`, zéro trace en presse FR/AR ni chez aucun
> agrégateur. Les marqueurs internes du dossier convergent (le mot « Consultation » partout et
> jamais « AOO », prorogation annoncée par SMS depuis un mobile, dépôt physique en 2 exemplaires
> papier, visite de site organisée) : **c'était une consultation privée restreinte**, envoyée
> directement à une liste d'invités dont ACCORDIA TECH. **Aucun dispositif de veille, gratuit ou
> payant, ne l'aurait fait remonter.** Conséquence de conception, non négociable : ce groupe ne
> promet JAMAIS l'exhaustivité, et il livre DEUX portes — l'automatique (le portail public) ET la
> manuelle (le tuyau partenaire), la seconde étant la seule qui aurait capté FRDISI.
> **La carte des sources (5 couches, couverture estimée du gisement adressable par un EPC solaire) :**
> (1) **portail officiel PMMP** `marchespublics.gov.ma` — État, **toutes** les collectivités
> territoriales, établissements publics + bons de commande + ONEE Branche Eau ; ~**40 000 avis/an**,
> **3 380 ouverts** à l'instant de la mesure : **~65-75 % du NOMBRE** d'opportunités réellement
> adressables (>95 % des AO *publics* y sont, source Banque mondiale) ; (2) **portails sectoriels
> propres** (ONEE-Élec, MASEN `etendering.masen.ma`, OCP, ADM, Marsa Maroc, ONDA, ONCF, CDG
> `safakat.cdg.ma`, SRM) — les EEP sous loi 69-00, **hors décret** : **~10 % du nombre mais la
> majorité de la VALEUR** (Noor Midelt III, 400 MW Drâa-Tafilalet, BESS 1,6 GWh), dont 4 tournent
> le MÊME logiciel Atexo que le PMMP ; (3) **presse** (2 journaux, ≥21 j, dont un en arabe) —
> obligation légale *en plus* du portail, donc **~0 % d'unique** ; (4) **le privé, le restreint et
> le gré à gré — la classe FRDISI** (consultations sur invitation, AO restreints, marchés
> négociés, PPP) : **~15-25 % du flux réel de Taqinor et 0 % sur le portail** — un agrégateur en
> récupère peut-être la moitié, les invitations directes personne ; (5) **bailleurs
> internationaux** — **~2-3 %**, quasi toujours redondants ; (6) **agrégateurs commerciaux**
> (Datao ~9 480 MAD/an HT, lesoffres.ma 990 DH/an, Marché Facile gratuit, Sodipress, Aljady…) —
> leur valeur unique est **le privé** et la recherche **au niveau des lignes de bordereau** (un lot
> PV enfoui dans un marché de bâtiment). **Ce que ce groupe couvrira : ~70-75 % dès le premier
> jour ; ~80-85 % avec les alertes officielles par domaine d'activité + une revue manuelle
> mensuelle des 4 portails sectoriels utiles ; ~90 % avec un abonnement privé. Les ~10 % restants
> sont un problème de RELATIONS, pas de logiciel** — c'est VAO29 et VAO36, pas le collecteur.
> **CE QUI A ÉTÉ VÉRIFIÉ EN MAIN LE 2026-08-01 (ne pas re-chercher, c'est mesuré) :** le portail
> n'a **ni API, ni flux RSS public, ni jeu open-data** (`data.gov.ma` : rien ; tous les candidats
> RSS renvoient 404) et **pas de `robots.txt`** (l'URL sert la page d'accueil). La recherche
> publique est accessible sans compte et **la recette HTTP complète fonctionne sans navigateur** :
> `GET index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&searchAnnCons&keyWord=K`
> puis, pour dépasser le plafond de 10 lignes, un **POST rejouant le postback PRADO**
> (`PRADO_PAGESTATE` ~87 Ko + `PRADO_POSTBACK_TARGET=ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop`
> + `…$listePageSizeTop=500`) sur la MÊME URL et la MÊME jarre de cookies. Trois contraintes
> apprises en dur : **User-Agent de navigateur obligatoire** (un UA de script = 403 par le
> pare-feu), **une seule jarre de cookies** sur la paire GET→POST (PHPSESSID + SERVERID collant),
> **`page=entreprise.` en minuscules** (la majuscule = 404). Résultats réels du jour :
> `solaire` → **34 avis en cours**, `photovolta` → **11**, dont des cibles exactement dans le
> métier (équipement de puits en plaques solaires à Chichaoua ; pompage solaire pour abreuvement
> du cheptel à Figuig ; luminaires solaires ONEE-Eau ; panneaux PV Forces Auxiliaires Rabat).
> La **date de publication est sur la ligne de résultat** (« Publié le ») — inutile de se battre
> avec le filtre de dates du formulaire, mesuré peu fiable.
> **RÈGLE #5 — LE GATE EST RÉEL, ET UNE REVUE ADVERSARIALE A REFUSÉ LA PREMIÈRE VERSION DE CE
> PLAN. Lire ce paragraphe avant d'écrire une ligne du collecteur.** La version initiale prévoyait
> « une lecture polie avec un User-Agent identifié ». Un examen critique indépendant l'a **refusée
> comme non défendable**, pour deux raisons internes au plan, avant tout argument juridique :
> **(1) elle ne peut pas tenir sa propre promesse.** Le pare-feu du portail refuse les clients
> scriptés (`curl`/`python-requests` → **403 « Interdit »** avec identifiant de refus) et ne sert
> que les User-Agent de navigateur. Un UA descriptif honnête du type `TaqinorBot/1.0` est
> exactement la forme qui se fait bloquer. Donc « poliment identifié » et « réponse 200 » sont
> **mutuellement exclusifs** ici : le plan ne fonctionnait qu'en **maquillant le client pour
> contourner un contrôle qui nous a refusés**. Classer cela en « friction technique » était
> l'erreur d'analyse centrale : **en l'absence de conditions d'utilisation, la règle de refus du
> pare-feu est l'expression la plus probante de la volonté de l'exploitant** — c'est une preuve
> EN FAVEUR d'une restriction, pas un obstacle neutre. **(2) la prémisse de volume était fausse** :
> un balayage complet quotidien des **3 380 avis ouverts** représente ~**338 requêtes POST**, pas
> « quelques requêtes » — précisément la forme de trafic qu'un pare-feu est réglé pour attraper.
> **LES DEUX CORRECTIFS, QUI SONT LA CONDITION DE CONSTRUCTION DU COLLECTEUR :** (a) **restreindre
> la requête côté serveur** (mots-clés métier : `solaire`, `photovolta`, `pompage`) pour que le
> résultat tienne en **1 à 3 pages, soit moins de 10 requêtes/jour** — alors « quelques requêtes »
> devient vrai ; (b) **envoyer un User-Agent HONNÊTE qui déclare Taqinor et une adresse de contact,
> et SI IL EST REFUSÉ (403), S'ARRÊTER — ne jamais maquiller.** Le repli est alors la porte des
> alertes officielles (VAO44), pas le contournement. **Ce qui reste vrai du cadre favorable** :
> pas de `robots.txt`, conditions d'utilisation purement techniques et muettes sur l'accès
> automatisé, **loi 31-13 art. 6** autorisant la réutilisation d'informations publiées par un
> organisme public, et un écosystème d'agrégateurs marocains qui exploite cette donnée depuis
> 1984. Ce qui reste à écrire sans enjoliver dans le fichier de risque : la clause « InfoSite »
> (reproduction des pages soumise à autorisation), neutralisée en **ne republiant rien** — usage
> interne strict, on ne stocke que des FAITS (référence, objet, acheteur, dates, montants), et les
> faits ne sont pas protégés. Le collecteur naît **désarmé** (`VEILLE_AO_COLLECTE_ACTIVE=0`,
> entrée beat inerte) ; son armement est une tâche `[GATED]` distincte (VAO4).
> **DEUX ACTIONS GRATUITES PASSENT AVANT TOUT CODE — elles peuvent rendre le collecteur INUTILE.**
> (1) **Le flux RSS authentifié existe — c'est CONFIRMÉ, plus une hypothèse.** Le portail annonce
> sur sa page d'accueil entreprise « un service d'abonnement aux flux RSS de la plate-forme »
> **réservé aux inscrits**, en plus d'alertes e-mail quotidiennes ou hebdomadaires construites à
> partir de recherches sauvegardées (critères **Domaines d'activité** + **Lieu d'exécution**) et
> d'une liste de suivi « Mon panier ». Les quatre adresses de flux publiques testées renvoient 404 :
> **s'il existe, il est derrière la connexion.** L'inscription est GRATUITE. **Si ce flux existe,
> c'est LE tuyau : canal officiel fourni par l'exploitant, aucun risque juridique, aucune règle #5
> à activer, aucun pare-feu à contourner — et VAO15-VAO20 ne sont jamais construites.** ⚠️ **Une
> seule précaution, sérieuse : LIRE les CGU du compte AVANT de les accepter** — c'est le seul
> chemin qui pourrait **CRÉER** une restriction contractuelle qui n'existe pas aujourd'hui.
> (2) **Écrire au TGR** (`marchespublics@tgr.gov.ma`, 05 37 57 88 15) pour demander s'il existe un
> flux/export et si une lecture automatisée quotidienne est acceptable. **Sous la loi 31-13
> l'administration doit une réponse**, et une réponse écrite fait passer le dispositif de
> « défendable » à « AUTORISÉ ». Aucune des deux analyses initiales n'avait envisagé de
> simplement demander.
> **DÉCISION D'ARCHITECTURE — une app NEUVE `apps/veille_ao`, surtout PAS `apps/ao` (raison
> mécanique, ne pas la « corriger ») :** `apps/ao` a **194 tâches AOF en attente dans
> `docs/PLAN.md`** avec **6-8 migrations déjà nommées** (`0002_tenantmodel` … `0009_administratif`)
> et sa chaîne de migrations est **mono-écrivain**. Or PLAN2 se draine AVANT PLAN.md : une
> migration VAO dans `apps/ao` prendrait le numéro `0002` et **décalerait toute la chaîne AOF
> déclarée**. Effet de bord heureux : le critère d'acceptation d'AOF169 (« aucun appel réseau vers
> un portail public dans le code — test de grep », portée `apps/ao`) **reste littéralement
> satisfait**, puisque tout le réseau vit dans `apps/veille_ao`. Même raisonnement côté écran :
> `frontend/src/features/ao/**` est **réservé au groupe AOF** (AOF7 y pose la nav, AOF8 y fige les
> hooks e2e) — la veille prend son propre dossier `frontend/src/features/veille_ao/`. **UN SEUL
> point de contact cross-app dans tout le groupe** : VAO30 ajoute UNE fonction en fin de
> `apps/ao/services.py` (écriture cross-app par le `services.py` de l'app cible, conforme à la
> règle de frontière). **AOF1 relogera le corps de ce fichier depuis `compta` : cette fonction est
> un AJOUT PUR en fin de fichier et doit VOYAGER avec le relogement — ne jamais la réécrire, ne
> jamais la perdre** (AOF1 est annoté en ce sens dans `docs/PLAN.md`).
> **Primitives plateforme JAMAIS recodées :** chatter et pièces jointes = `records` (jamais une
> classe `*Activity` maison — 13 chatters hand-rollés sont le premier poste de dette mesuré du
> dépôt) ; références = `core.numbering.create_with_reference` (jamais `count()+1`) ; jobs =
> `core.jobs.submit` + `BackgroundJob` (jamais une file maison) ; import de fichiers =
> `apps.dataimport.parsing.iter_rows` + `FIELD_MAPS` ; notifications = `apps.notifications` ;
> multi-tenant = `core.models.TenantModel` + `core.viewsets.CompanyScopedModelViewSet` (sinon
> `scripts/check_platform.py` casse la CI) ; aucun NOUVEAU `FileField` (tout artefact passe par
> `records.Attachment`). Le scaffolder du dépôt fait le squelette et imprime la checklist de
> câblage : `python manage.py startapp_erp veille_ao` — l'utiliser, ne pas recopier une app à la
> main. **Dépendance nouvelle :** `httpx` est **déjà en production** (`requirements.txt`), mais
> **aucun parseur HTML n'est installé** (ni `beautifulsoup4`, ni `lxml`, ni `feedparser`) — VAO17
> est donc `(DEP)` et doit ajouter `beautifulsoup4` (licence MIT, gratuit) en le signalant au
> fondateur dans le DONE LOG.
> **Contraintes héritées par CHAQUE tâche VAO :** FK `company` + viewsets scopés ; cross-app en
> lecture via `selectors.py` uniquement ; UI en français ; migrations additives et revertables ;
> **aucun compte personnel n'est utilisé nulle part** (règle #5) ; **aucun avis ne devient
> automatiquement un `AppelOffre`** (le portail contient beaucoup de bruit — c'est un SAS, et
> c'est un humain qui décide) ; **les pages de détail et les DCE ne sont téléchargés que sur clic**
> (deux délais de 110 s observés sur ce point de terminaison — jamais en masse) ; **l'UI ne
> promet jamais l'exhaustivité** et affiche ce qu'elle NE couvre pas.

#### VAO W0 — Décisions fondateur & gouvernance (VAO1-VAO5, VAO43-VAO44)

- [ ] VAO2 — **[GATED : action fondateur, ~30 minutes, À FAIRE AVANT TOUT CODE DE COLLECTE — c'est la tâche qui décide si les 6 tâches du collecteur existent] Ouvrir le compte entreprise gratuit et ALLER VOIR le flux RSS authentifié + les alertes.** Constat **confirmé** (et non plus supposé) : le portail annonce sur sa page d'accueil entreprise **« un service d'abonnement aux flux RSS de la plate-forme » réservé aux inscrits**, ainsi qu'un service d'**alertes e-mail quotidiennes ou hebdomadaires** construit en sauvegardant une recherche avancée sur **Domaines d'activité** + **Lieu d'exécution**, plus une liste de suivi « Mon panier ». Les 4 adresses de flux publiques testées renvoient 404 : s'il existe, il est **derrière la connexion**. **Enjeu maximal : si le flux authentifié existe, c'est LE tuyau — canal officiel de l'exploitant, zéro risque juridique, zéro règle #5, zéro pare-feu à contourner — et VAO15 à VAO20 ne sont JAMAIS construites.** L'inscription est gratuite et Taqinor doit de toute façon détenir ce compte (dépôt électronique obligatoire depuis le 01/09/2023). ⚠️ **UNE PRÉCAUTION SÉRIEUSE : lire les CGU du compte AVANT de les accepter et en garder une copie** — c'est le seul chemin capable de **CRÉER** une restriction contractuelle sur l'accès automatisé qui n'existe pas aujourd'hui ; si les CGU interdisent l'automatisation, elles priment sur toute l'analyse de VAO3 et le collecteur est abandonné au profit des alertes. **Done =** compte créé au nom de la société (jamais un compte personnel), copie des CGU archivée, et 4 réponses écrites dans le DONE LOG (flux RSS authentifié oui/non + URL ; alertes e-mail oui/non + granularité réelle des filtres ; CGU : automatisation interdite oui/non ; dépôt électronique possible ou non). Si RSS = oui → VAO15-VAO20 retaggées `[SUPERSEDED par le flux RSS officiel]` et une tâche de lecture du flux les remplace. Files: aucun (action fondateur ; consigner dans le DONE LOG de `docs/PLAN2.md`). (DECISION) (@lane: gov/veille-ao)
- [ ] VAO43 — **[GATED : action fondateur, gratuite, 15 minutes — À FAIRE EN MÊME TEMPS QUE VAO2] Écrire au TGR pour demander un flux et l'autorisation de lecture automatisée.** Constat : la revue adversariale a relevé que **ni l'analyse juridique ni l'analyse technique n'avaient envisagé de simplement DEMANDER**. Courrier ou e-mail à `marchespublics@tgr.gov.ma` (05 37 57 88 15), en tant que fournisseur marocain inscrit : « existe-t-il un flux, un export ou une interface de programmation pour consulter les avis ouverts ? une lecture automatisée quotidienne, à faible cadence, pour notre propre veille, est-elle acceptable ? ». **Sous la loi 31-13, l'administration doit une réponse** — et une réponse écrite fait passer tout le dispositif de « défendable » à « **autorisé** », ce qui vaut infiniment mieux que la meilleure analyse de risque. Une réponse négative est tout aussi utile : elle clôt le sujet et bascule définitivement sur les alertes officielles (VAO44). **Done =** courrier envoyé et daté, réponse (ou absence de réponse après relance) consignée dans le DONE LOG **et recopiée dans `tos_risk/marchespublics_gov_ma.md`** — c'est la pièce la plus forte que ce fichier puisse contenir. Files: `tos_risk/marchespublics_gov_ma.md` (section « Réponse de l'exploitant »). (DECISION) (@lane: gov/veille-ao)
- [ ] VAO44 — **[GATED : ne se construit QUE si VAO2 dit « pas de flux RSS » ET que l'UA honnête est refusé] La porte e-mail : ingérer les alertes officielles du portail.** Constat : c'est le **repli obligatoire** du plan corrigé — si le User-Agent honnête est refusé en 403, **on s'arrête et on ne maquille rien** (VAO16/VAO19), et les alertes e-mail officielles deviennent le canal principal. Elles sont un canal 100 % autorisé, quotidien, filtrable par domaine d'activité et par région — et ce filtre attrape des avis que les mots-clés ratent. Voie d'entrée : **réutiliser la porte manuelle et l'import (VAO27/VAO28)** plutôt qu'inventer une pile d'ingestion e-mail ; n'ouvrir une ingestion automatisée (boîte dédiée + analyse du corps) que si le volume quotidien la justifie, jamais par principe. **Done =** un e-mail d'alerte officiel devient des `AvisMarche` dans le sas avec la source `portail_officiel`, dédoublonnés contre les avis déjà connus (VAO11), sans aucun accès automatisé au portail. Files: `apps/veille_ao/imports.py`, `apps/veille_ao/tests/test_porte_email.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO2, VAO28)
- [x] VAO3 — **Fichier de risque `tos_risk/marchespublics_gov_ma.md` (règle #5 volet (a)).** Écrire le fichier de risque au format imposé par `tos_risk/README.md` — **écrire ce fichier n'exécute aucun scraper, la tâche est donc constructible**. Contenu obligatoire, sans enjolivement : **cible** (pages de recherche publiques non authentifiées, **requête RESTREINTE par mots-clés donnant 1 à 3 pages, < 10 requêtes/jour**, endpoints nommés — surtout PAS un balayage des 3 380 avis ouverts, qui ferait ~338 POST/jour et que ce fichier doit explicitement exclure) ; **compte utilisé** (aucun — accès anonyme ; jamais un compte personnel) ; **résumé des conditions** (pas de `robots.txt` ; conditions d'utilisation purement techniques et muettes sur l'accès automatisé ; loi 31-13 art. 6 favorable à la réutilisation ; **MAIS** clause « InfoSite » de reproduction, neutralisée par le non-republiage et le stockage de faits seuls) ; **risque** (faible : blocage IP, dérive HTML ; aucun précédent connu d'action contre les agrégateurs marocains qui exploitent cette donnée depuis 1984) ; **le point dur, écrit tel quel et non minimisé** : le pare-feu du portail **refuse déjà les clients scriptés (403 « Interdit »)**, et **en l'absence de conditions d'utilisation cette règle de refus est l'expression la plus probante de la volonté de l'exploitant** — d'où la règle de conduite du dispositif : **User-Agent HONNÊTE déclarant Taqinor + une adresse de contact, et arrêt définitif si ce UA est refusé ; jamais de maquillage** ; **mitigations** (≤1 requête/2 s, < 10/jour, requête restreinte, aucune page authentifiée, aucun téléchargement de DCE en masse, interrupteur d'arrêt, journal d'exécution auditable) ; **section « Réponse de l'exploitant »** destinée à recevoir la réponse du TGR (VAO43) ; **ligne d'approbation fondateur laissée VIDE** (c'est VAO4 qui la remplit). **Done =** fichier committé et conforme au gabarit du README, la règle « UA honnête, arrêt si refus, jamais de maquillage » y figure noir sur blanc, ligne d'approbation vide, aucun code de collecte exécuté. Files: `tos_risk/marchespublics_gov_ma.md`. (ROUTINE) (@lane: gov/veille-ao) (@model: sonnet) (@after: VAO2, VAO43)
- [ ] VAO4 — **[GATED : accord écrit du fondateur — règle #5 volet (b)] Armer la collecte automatique.** Constat : la règle #5 exige l'accord explicite du fondateur **avant la première exécution**, et VAO22 livre délibérément le collecteur désarmé (`VEILLE_AO_COLLECTE_ACTIVE=0`). Cette tâche est l'acte d'armement et **ne peut être exécutée par aucun agent de sa propre initiative** : elle consiste à (i) obtenir et dater l'accord du fondateur, (ii) le consigner dans la ligne « Founder approval » de `tos_risk/marchespublics_gov_ma.md`, (iii) passer le drapeau à `1` en production. Un agent qui rencontre cette tâche sans accord daté la laisse `[GATED]` et poursuit la lane. **Done =** ligne d'approbation datée dans le fichier de risque, drapeau à `1`, première exécution réelle observée dans le journal d'exécution (VAO24) avec son décompte d'avis. Files: `tos_risk/marchespublics_gov_ma.md`, `.env.example`. (DECISION) (@lane: gov/veille-ao) (@after: VAO3, VAO22)
- [ ] VAO5 — **[GATED : dépense fondateur, hors code] Certificat électronique classe 3 + ICE — le prérequis pour DÉPOSER (à ne pas confondre avec VOIR).** Constat vérifié : depuis le **1er septembre 2023 la soumission électronique est obligatoire** sur le PMMP, chaque pièce étant signée avec un **certificat classe 3** (Barid eSign ≈ **1 512,50 MAD** avec jeton USB). Sans lui, Taqinor peut voir tous les avis publics du pays **et n'en déposer aucun en son nom propre** — ce qui explique en partie le montage FRDISI où ACCORDIA TECH porte l'offre. **C'est la dépense n° 0 du dossier, antérieure à toute ligne de code**, et elle ne relève pas de la règle #5 (aucun scraping) mais d'un arbitrage budgétaire. **Done =** décision fondateur consignée (acquis / différé / porté par un partenaire), et si acquis, la référence du certificat rangée dans les paramètres société. Files: aucun (décision fondateur ; consigner dans le DONE LOG). (COST) (@lane: gov/veille-ao)

#### VAO W1 — Socle : l'app neuve et le SAS des avis (VAO6-VAO14)

- [x] VAO6 — **Créer l'app `apps/veille_ao` avec le scaffolder du dépôt + câblage complet.** Constat : le dépôt fournit `python manage.py startapp_erp veille_ao`, qui génère le squelette conforme (13 gabarits : `apps.py`, `models.py`, `viewsets.py`, `serializers.py`, `selectors.py`, `services.py`, `receivers.py`, `urls.py`, `platform.py`, `admin.py`, `migrations/`, `tests/`) **et imprime la checklist de câblage en 8 points** — l'utiliser plutôt que recopier une app à la main. Câbler : `'apps.veille_ao'` dans `INSTALLED_APPS`, `path('veille_ao/', include('apps.veille_ao.urls'))` dans `_APP_URLS` (**segment d'URL identique à la clé de manifeste** — sinon il faut une entrée dans `core/permissions.PREFIX_TO_MODULE`), et le `module_manifest` sur l'`AppConfig` (`key: 'veille_ao'`, `categorie: 'Commercial'`, `depends: ['ao']`, libellé « Veille appels d'offres »). **Done =** `check_modules.py` vert (clé unique, corrélation front↔back), l'app apparaît dans le registre de modules, `/api/django/veille_ao/` répond, un module désactivé par `ModuleToggle` rend bien 404 (middleware générique déjà en place). Files: `apps/veille_ao/apps.py`, `apps/veille_ao/urls.py`, `erp_agentique/settings/base.py`, `erp_agentique/urls.py`, `apps/veille_ao/tests/test_smoke.py`. (ARCH) (@lane: backend/veille-ao) (@model: sonnet)
- [x] VAO7 — **`SourceVeille` : le catalogue des sources, aucune source en dur dans le code.** Modèle : code, libellé FR, type (`portail_officiel` / `saisie_manuelle` / `import_csv` / `portail_sectoriel` / `agregateur` / `tuyau_partenaire`), URL de base, actif, cadence, dernière collecte réussie, notes. Constat de conception : la carte des sources compte 5 couches et va grandir (bons de commande, MASEN, CDG, ADM, Marsa tournent le MÊME logiciel Atexo) — coder « le portail » en dur condamnerait chaque extension à toucher le collecteur. Seed idempotent des sources connues, celles de la phase 2 créées **inactives**. **Done =** seed rejouable sans doublon, une source désactivée n'est jamais collectée, aucun littéral d'URL de portail hors de cette table (test de grep sur le collecteur). Files: `apps/veille_ao/models.py`, `apps/veille_ao/migrations/0001_initial.py`, `apps/veille_ao/management/commands/seed_veille_sources.py`, `apps/veille_ao/tests/test_sources.py`. (SCHEMA) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO6)
- [x] VAO8 — **`AvisMarche` : le SAS — la table où atterrissent TOUS les avis, quelle que soit la porte.** Champs : société, `source` FK, identifiants d'origine (`ref_consultation`, `org_acronyme`, `reference_avis`), objet, acheteur, lieu/région, procédure, catégorie (travaux/fournitures/services), **date de publication** (lue sur la ligne de résultat), date limite de remise, date d'ouverture, montant estimé, caution provisoire, lot, URL de détail, mots-clés déclenchés, score, `statut ∈ {nouveau, retenu, ignore, converti, expire}`, `appel_offre_id` (**entier opaque, jamais une FK vers `apps.ao`** — c'est ce qui garde les deux apps découplées), horodatages, `donnees_brutes` JSON. **JAMAIS de création automatique d'`AppelOffre`** : le portail contient beaucoup de bruit, un humain tranche (VAO30). **Done =** modèle sur `TenantModel`, un avis expiré bascule seul en `expire` (date limite dépassée), aucun champ de coût/marge, `check_platform.py` vert. Files: `apps/veille_ao/models.py`, `apps/veille_ao/migrations/0001_initial.py`, `apps/veille_ao/serializers.py`, `apps/veille_ao/tests/test_avis_marche.py`. (SCHEMA) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO7)
- [x] VAO9 — **`MotCleVeille` + score : les mots-clés sont de la DONNÉE, jamais une constante.** Deux niveaux mesurés sur le portail réel : **noyau** (précision haute) `solaire`, `photovolta`, `pompage solaire`, `kwc`, `chauffe-eau solaire` ; **large** (bruit accepté, score plus bas) `photovoltaïque`, `énergie renouvelable`, `éclairage public solaire`, `onduleur`, `batterie`, `stockage`, `électrification`. Modèle : libellé, niveau, poids, actif, société ; score d'un avis = somme pondérée des mots-clés déclenchés (objet + acheteur), borné, **avec la liste des mots déclenchés stockée** pour que l'utilisateur voie POURQUOI l'avis est remonté. **Done =** seed des deux niveaux, un mot-clé ajouté par l'écran change le score des collectes suivantes sans redéploiement, un avis affiche ses mots déclencheurs, aucun mot-clé littéral hors table (test de grep). Files: `apps/veille_ao/models.py`, `apps/veille_ao/scoring.py`, `apps/veille_ao/tests/test_scoring.py`. (SCHEMA) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO8)
- [x] VAO10 — **`RegleExclusion` : « Ignorer » doit APPRENDRE, sinon l'écran se remplit de bruit.** Constat : un avis ignoré qui remonte à chaque collecte tue l'usage de l'écran en deux semaines. Modèle : société, portée (acheteur / mot du libellé / catégorie / région), motif FR, actif, compteur d'application. Le service de collecte marque automatiquement `ignore` tout nouvel avis capté par une règle, **en écrivant quelle règle l'a filtré** (jamais un filtrage muet). **Done =** ignorer un avis propose la règle correspondante sans jamais la créer en douce, un avis auto-ignoré affiche sa règle, une règle désactivée fait réapparaître les avis suivants, compteur d'application testé. Files: `apps/veille_ao/models.py`, `apps/veille_ao/services.py`, `apps/veille_ao/tests/test_exclusions.py`. (SCHEMA) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO9)
- [x] VAO11 — **Dédoublonnage à DEUX niveaux — le cœur de fiabilité du groupe.** Niveau 1 (identité) : contrainte d'unicité `(société, source, ref_consultation, org_acronyme)` — c'est l'identifiant propre du portail, stable, lu directement dans l'URL de détail. Niveau 2 (filet) : empreinte SHA-256 de `(référence normalisée + acheteur normalisé + date limite)` sur le patron éprouvé `ventes.services.layout_hash` — **parce qu'un avis rectifié peut ressortir avec un NOUVEL identifiant** et qu'un import CSV ou une saisie manuelle n'a aucun identifiant de portail. Une collision de niveau 2 sans collision de niveau 1 ne crée pas de doublon : elle **met à jour** l'avis existant et journalise la rectification. **Done =** rejouer deux fois la même collecte ne crée aucun doublon (test), un avis rectifié met à jour sans dupliquer, un même avis saisi à la main puis collecté automatiquement fusionne au lieu de doubler, la normalisation (casse, accents, espaces) est testée. Files: `apps/veille_ao/hashing.py`, `apps/veille_ao/services.py`, `apps/veille_ao/tests/test_dedoublonnage.py`. (ARCH) (@lane: backend/veille-ao) (@model: opus) (@after: VAO8)
- [x] VAO12 — **Permissions `veille_ao_voir` / `veille_ao_gerer` + viewsets sur le socle conforme.** Déclarer les 2 codes dans `apps/roles/models.ALL_PERMISSIONS`, mapper `veille_ao_voir` largement (un commercial doit voir les avis) et `veille_ao_gerer` au palier Responsable/Directeur (modifier mots-clés, sources, règles, armer la collecte) ; tous les viewsets héritent de `core.viewsets.CompanyScopedModelViewSet` avec `read_permission`/`write_permission` — `scripts/check_platform.py` refuse tout NOUVEAU `ModelViewSet` hors de ce socle. **Done =** matrice 403 testée (Commercial/Technicien/Responsable/Directeur), isolation multi-tenant détectée par le sweep générique, aucun accès élargi par rapport à aujourd'hui. Files: `apps/roles/models.py`, `apps/veille_ao/viewsets.py`, `apps/veille_ao/urls.py`, `apps/veille_ao/tests/test_permissions.py`. (AUTH) (@lane: backend/veille-ao) (@model: opus) (@after: VAO8)
- [x] VAO13 — **Manifeste plateforme `apps/veille_ao/platform.py` — ne déclarer QUE ce qui est câblé.** Constat : `core/platform_coverage.py` (règle d'honnêteté ARC41) fait rougir la CI sur toute surface déclarée non câblée. Déclarer `searchable_models` (l'avis, pour que la recherche globale le trouve), `record_targets` (chatter `records` sur l'avis — **jamais une classe `*Activity` maison**), et `import_specs` **seulement quand VAO28 les aura câblés**. **Done =** recherche globale et chatter opérationnels sans toucher aux surfaces transverses, `platform_coverage` vert, une déclaration non câblée fait rougir le test. Files: `apps/veille_ao/platform.py`, `apps/veille_ao/tests/test_platform.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO12)
- [x] VAO14 — **Service unique de changement de statut + journal au chatter.** `changer_statut_avis(avis, nouveau, user, motif)` est le SEUL point de mutation du statut (nouveau → retenu | ignore ; retenu → converti ; tout → expire), avec table de transitions déclarative et refus en 400 message FR. Chaque transition écrit une activité `records` (qui, quand, pourquoi). **Ne déclarer AUCUN nouveau signal `core/events.py`** : le dépôt fait rougir la CI sur tout signal sans abonné réel, et rien ici n'a besoin d'un abonné cross-app — la notification passe par l'appel direct au service de notifications (VAO25). **Done =** statut jamais muté hors service (test d'introspection), transition interdite → 400 FR, historique lisible au chatter, `core/event_coverage.py` inchangé. Files: `apps/veille_ao/services.py`, `apps/veille_ao/tests/test_statuts.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO10)

#### VAO W2 — Le collecteur portail : un module PUR, testable hors ligne (VAO15-VAO20)

*Lane strictement file-disjointe de W1 (`apps/veille_ao/portail/**` contre `apps/veille_ao/models.py`)
— elle démarre EN MÊME TEMPS, dès la première heure, et ne touche jamais la base.*

- [ ] VAO15 — **Squelette `apps/veille_ao/portail/` + contrat de pureté + fixtures HTML committées.** Créer le paquet dont le **parseur ne fait AUCUNE E/S** (stdlib + `beautifulsoup4` seulement : zéro Django, zéro `apps.*`, zéro accès réseau) et dont le **client HTTP est la seule frontière réseau**. Committer des fixtures HTML réelles capturées le 2026-08-01 (une page de résultats `solaire` à 10 lignes, une réponse POST à 500 lignes, une page de détail, une page d'erreur/403, une page vide) : **elles rendent tout le collecteur testable sans réseau et sans base**, donc hors du gate migrations qui est le poste de coût CI dominant. **Done =** test de pureté ROUGE si le parseur importe `httpx` ou `django`, fixtures committées et documentées (date de capture + URL d'origine), aucun test du groupe n'appelle le réseau. Files: `apps/veille_ao/portail/__init__.py`, `apps/veille_ao/portail/fixtures/`, `apps/veille_ao/tests/test_purete_portail.py`. (ARCH) (@lane: backend/veille-ao-collecteur) (@model: sonnet)
- [ ] VAO16 — **Client HTTP PRADO : la recette vérifiée en main, et rien d'autre.** Implémenter exactement la séquence mesurée : (1) `GET index.php?page=entreprise.EntrepriseAdvancedSearch&AllCons&EnCours&searchAnnCons&keyWord=K` → lire le total dans `<span id="ctl0_CONTENU_PAGE_resultSearch_nombreElement">`, extraire le champ caché `PRADO_PAGESTATE` (~87 Ko, **déséchapper le HTML**) et les 10 premières lignes ; (2) si total > 10, **POST sur la MÊME URL et la MÊME jarre de cookies** avec `PRADO_PAGESTATE`, `PRADO_POSTBACK_TARGET=ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop`, `PRADO_POSTBACK_PARAMETER` vide et `ctl0$CONTENU_PAGE$resultSearch$listePageSizeTop=500` → toutes les lignes en une réponse (vérifié : les 34 résultats `solaire`) ; (3) si total > 500, re-POST avec le NOUVEAU pagestate + `…$numPageTop=N` (mécanisme de page 2 vérifié). **LA RÈGLE DE CONDUITE QUI PRIME SUR TOUT LE RESTE (revue adversariale — ne pas la contourner « pour que ça marche ») : le client envoie un User-Agent HONNÊTE déclarant Taqinor et une adresse de contact. Si ce User-Agent est refusé (403), le client S'ARRÊTE définitivement et remonte l'échec — il ne réessaie JAMAIS avec un User-Agent de navigateur.** Le pare-feu refuse les clients scriptés, et maquiller l'identité pour contourner un contrôle qui nous a refusés est hors périmètre de ce plan : le repli est VAO44 (alertes officielles), jamais le déguisement. **Deuxième règle de proportion : la requête est TOUJOURS restreinte par mots-clés** (1 à 3 pages, **< 10 requêtes/jour**) — un balayage des 3 380 avis ouverts (~338 POST/jour) est interdit et doit être impossible par construction (garde de VAO19). Deux contraintes techniques restantes, mesurées : **une seule jarre de cookies** sur la paire GET→POST (PHPSESSID + SERVERID collant) et `page=entreprise.` **en minuscules** (majuscule = 404). Ne PAS utiliser les paramètres de date en GET (ignorés) ni le filtrage de dates par formulaire (mesuré peu fiable) — la date de publication est sur la ligne. Sur `httpx`, déjà en production. **Done =** les 3 étapes testées contre les fixtures + un test d'intégration réseau marqué `skip` par défaut ; **un test prouve qu'un 403 arrête le client sans aucune tentative de repli sur un UA de navigateur** ; un test prouve qu'une requête sans mot-clé restrictif est refusée ; le client refuse de partir si la source est inactive ; aucune URL en dur (elle vient de `SourceVeille`). Files: `apps/veille_ao/portail/client.py`, `apps/veille_ao/tests/test_client_portail.py`. (ARCH) (@lane: backend/veille-ao-collecteur) (@model: opus) (@after: VAO15)
- [ ] VAO17 — **(DEP) Parseur de ligne de résultat — et l'ajout de `beautifulsoup4`.** Constat vérifié : **aucun parseur HTML n'est installé** dans `backend/django_core/requirements.txt` (ni `beautifulsoup4`, ni `lxml`, ni `feedparser`) — seul `httpx` l'est. Ajouter `beautifulsoup4` (MIT, gratuit, sans service tiers) et **le signaler au fondateur dans le DONE LOG** (règle : toute nouvelle dépendance est notée). Extraire par ligne : référence (`<span class="ref">`), objet (après `<strong> Objet : </strong>`), acheteur (après `Acheteur public :`), lieu, procédure, catégorie, **date de publication** (le `<div> jj/mm/aaaa </div>` de la première cellule, en-tête « Publié le »), date limite (`jj/mm/aaaa hh:mm`), et l'URL de détail portant `refConsultation=<n>&orgAcronyme=<code>`. Décodage UTF-8. **Done =** les 5 fixtures parsées avec les valeurs attendues figées dans le test, une ligne malformée est ignorée avec un motif journalisé **sans faire tomber la collecte entière**, dépendance ajoutée et notée. Files: `apps/veille_ao/portail/parser.py`, `backend/django_core/requirements.txt`, `apps/veille_ao/tests/test_parser_portail.py`. (DEP) (@lane: backend/veille-ao-collecteur) (@model: sonnet) (@after: VAO15)
- [ ] VAO18 — **Enrichissement du détail À LA DEMANDE — jamais en masse.** `GET index.php?page=entreprise.EntrepriseDetailConsultation&refConsultation=<id>&orgAcronyme=<code>` rend l'estimation (MAD TTC), la caution provisoire, les lots, le marqueur PME et le lien du DCE avec sa taille. Constat mesuré : **ce point de terminaison se bloque par intermittence (deux délais de 110 s observés)** — il est donc appelé **uniquement sur clic utilisateur**, avec délai d'attente 30-60 s, 2-3 tentatives à repli exponentiel, et un échec propre qui n'efface jamais les données déjà connues de l'avis. **Le téléchargement du DCE n'est PAS dans le périmètre** (flux ATEXO multi-étapes, probablement une étape d'identification — non vérifié) : afficher le lien, laisser l'humain cliquer. **Done =** enrichissement testé sur fixture, un délai dépassé laisse l'avis intact et affiche « détail indisponible, réessayer », aucun appel de détail depuis la tâche planifiée (test d'introspection). Files: `apps/veille_ao/portail/detail.py`, `apps/veille_ao/tests/test_detail_portail.py`. (ROUTINE) (@lane: backend/veille-ao-collecteur) (@model: sonnet) (@after: VAO16, VAO17)
- [ ] VAO19 — **Garde-fous du client : cadence, quota, interrupteur — les mitigations promises au fichier de risque.** Ce que VAO3 promet doit être CODÉ, pas seulement écrit : ≤1 requête / 2 s ; **quota quotidien dur de 10 requêtes** (et non 20 — c'est le chiffre que le fichier de risque promet), refus au-delà avec journalisation ; délais d'attente partout ; jamais plus d'un collecteur simultané pour une même société (verrou) ; **interrupteur d'arrêt** (`VEILLE_AO_COLLECTE_ACTIVE=0` court-circuite tout appel réseau, y compris le déclenchement manuel) ; **aucun accès à une page authentifiée ni à un compte** (test de grep : aucun identifiant, aucun cookie de session utilisateur dans le code). **Et les deux gardes issues de la revue adversariale, qui sont la raison d'être de cette tâche : (a) l'UA honnête est la SEULE valeur possible — un test échoue si une chaîne d'UA de navigateur (`Mozilla`, `Chrome`, `Safari`…) apparaît où que ce soit dans le module `portail/` ; (b) une recherche sans mot-clé restrictif est refusée par construction**, de sorte qu'un balayage complet ne puisse pas être écrit par accident. **Done =** chaque mitigation du fichier de risque a un test qui la prouve, dépasser le quota lève une erreur explicite au lieu de continuer, le drapeau à `0` rend le collecteur inerte, le test anti-maquillage et le test anti-balayage sont verts. Files: `apps/veille_ao/portail/garde_fous.py`, `apps/veille_ao/tests/test_garde_fous.py`. (ARCH) (@lane: backend/veille-ao-collecteur) (@model: opus) (@after: VAO16)
- [ ] VAO20 — **Échouer FORT, jamais « 0 résultat » en silence.** Constat : la pagination dépend d'un champ d'état interne PRADO de 87 Ko et le portail est un logiciel tiers (Atexo) qui peut changer du jour au lendemain ; **un collecteur qui casse sans le dire est pire que pas de collecteur** — c'est ainsi qu'on rate un AO en se croyant couvert. Distinguer trois cas et ne JAMAIS les confondre : « collecte réussie, 0 nouveauté » (normal), « collecte réussie, structure inattendue » (parse partiel → alerte), « collecte échouée » (403, délai, pagestate absent, total introuvable → erreur remontée). Le compteur `nombreElement` sert de **contrôle croisé** : si le nombre de lignes parsées diffère du total annoncé, c'est une anomalie, pas un résultat. **Done =** les 3 cas testés sur fixtures (dont la fixture 403 et la fixture vide), un HTML dérivé produit une erreur nommée et non un tableau vide, l'écart lignes/total déclenche l'anomalie. Files: `apps/veille_ao/portail/resultats.py`, `apps/veille_ao/tests/test_echec_franc.py`. (ARCH) (@lane: backend/veille-ao-collecteur) (@model: opus) (@after: VAO17)

#### VAO W3 — Collecte, planification, alarme (VAO21-VAO26)

- [x] VAO21 — **Service de collecte : l'orchestration, seule à toucher la base.** `collecter(source, company)` enchaîne mots-clés actifs → client → parseur → dédoublonnage (VAO11) → règles d'exclusion (VAO10) → scoring (VAO9) → écriture des `AvisMarche`, en une transaction par avis (un avis fautif ne perd pas la collecte). Retourne un compte-rendu structuré (examinés, nouveaux, mis à jour, auto-ignorés, erreurs). **Done =** collecte rejouée = 0 nouveau (idempotence), un mot-clé désactivé n'est plus interrogé, un avis fautif est journalisé et les autres passent, aucune écriture hors service. Files: `apps/veille_ao/services.py`, `apps/veille_ao/tests/test_collecte.py`. (ARCH) (@lane: backend/veille-ao) (@model: opus) (@after: VAO11, VAO16, VAO17, VAO20)
- [x] VAO22 — **Tâche planifiée 06:00 Casablanca — livrée DÉSARMÉE.** `@shared_task(name='veille_ao.collecte_quotidienne')` + entrée `beat_schedule` dans `erp_agentique/celery.py` (**obligatoire** : `apps/ventes/tests/test_qx11_beat_reachability.py` fait rougir la CI sur toute tâche planifiée absente du beat ou de l'allowlist ; le fuseau du beat est déjà `Africa/Casablanca`). **06:00 parce que les remises de plis sont à 10 h-11 h : l'information du matin est actionnable le jour même.** La tâche **sort immédiatement sans aucun appel réseau tant que `VEILLE_AO_COLLECTE_ACTIVE=0`** (défaut) — VAO4 est l'acte d'armement. **Done =** entrée beat présente et test de portée verte, la tâche est inerte drapeau à `0` (test), elle apparaît seule dans l'écran « Tâches planifiées » (`core.jobs.list_jobs` la lit gratuitement), aucune exécution réelle avant VAO4. Files: `apps/veille_ao/tasks.py`, `erp_agentique/celery.py`, `.env.example`, `apps/veille_ao/tests/test_tache_planifiee.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO21)
- [x] VAO23 — **Le BOUTON « Rafraîchir maintenant » lance EXACTEMENT le même job que la nuit.** Endpoint `POST /api/django/veille_ao/collecter/` gated `veille_ao_gerer`, passant par `core.jobs.submit(kind, task, company=…, user=…)` → `BackgroundJob` avec progression et résultat consultable. **Une seule mécanique, deux déclencheurs** — jamais un second chemin de collecte « pour le bouton » (c'est ainsi qu'on obtient deux comportements divergents). Le drapeau désarmé s'applique aussi ici. **Done =** le bouton et le beat appellent la même fonction (test d'identité), progression visible, double clic ne lance pas deux collectes concurrentes (verrou VAO19), 403 pour un rôle non habilité. Files: `apps/veille_ao/views.py`, `apps/veille_ao/urls.py`, `apps/veille_ao/tests/test_declenchement_manuel.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO22)
- [x] VAO24 — **`ExecutionCollecte` + ALARME de collecte silencieuse — la tâche la plus importante du groupe.** Journal par exécution : source, début/fin, mots-clés interrogés, examinés/nouveaux/ignorés, erreurs, verdict. **Alarme : 0 résultat sur TOUS les mots-clés deux jours consécutifs, ou 2 échecs consécutifs → notification au directeur « la veille ne ramène plus rien, vérifiez ».** Constat : c'est le seul garde-fou contre le scénario réel — le portail change, la collecte renvoie vide, l'écran reste calme et on croit être couvert pendant des semaines. **Done =** journal écrit à chaque exécution (même échouée), alarme déclenchée sur les deux conditions (test), l'écran affiche la date de dernière collecte réussie **et son âge**, une alarme active est visible sans aller la chercher. Files: `apps/veille_ao/models.py`, `apps/veille_ao/services.py`, `apps/veille_ao/tests/test_alarme_silence.py`. (SCHEMA) (@lane: backend/veille-ao) (@model: opus) (@after: VAO21)
- [x] VAO25 — **Notification quotidienne en français, utile et non bruyante.** Après une collecte du matin qui ramène du nouveau : « 3 nouveaux avis solaires — dont 1 à échéance J-12 », lien direct vers la liste filtrée sur les nouveaux. Via `apps.notifications` (jamais un envoi réseau depuis le service de collecte). **Rien à dire = rien à envoyer** — une notification quotidienne vide apprend à ignorer les notifications. **Done =** notification envoyée seulement s'il y a du nouveau, destinataires = porteurs de `veille_ao_voir` (paramétrable), texte FR testé, aucun envoi depuis le service de collecte lui-même. Files: `apps/veille_ao/services.py`, `apps/veille_ao/tests/test_notification.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO24)
- [x] VAO26 — **Rétention et purge des avis non retenus.** Un avis `nouveau`/`ignore` dont la date limite est dépassée depuis N mois (paramétrable, défaut 12) est purgé ; **un avis `retenu` ou `converti` n'est JAMAIS purgé** (il porte l'historique commercial et la mesure d'attribution de VAO31). Politique déclarée sur le patron `apps/crm/apps.py ready()`. **Done =** purge idempotente et testée sur les deux catégories, aucun avis converti supprimé (test explicite), politique de rétention déclarée. Files: `apps/veille_ao/retention.py`, `apps/veille_ao/apps.py`, `apps/veille_ao/tests/test_retention.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: haiku) (@after: VAO24)

#### VAO W4 — La porte MANUELLE : la leçon FRDISI (VAO27-VAO31)

- [x] VAO27 — **« Ajouter un avis » : capter en 30 secondes un AO reçu par WhatsApp, SMS ou appel — avec sa SOURCE.** Constat fondateur : l'AO qui a réellement occupé Reda (FRDISI) n'est passé par aucun portail — il est arrivé par un partenaire. Endpoint + service de création manuelle d'`AvisMarche` avec **champ `informateur` OBLIGATOIRE** (qui me l'a signalé : partenaire, client, employé, presse, autre) et `source` = `tuyau_partenaire` ou `portail_sectoriel`. Le minimum vital seulement : objet, acheteur, date limite, informateur — tout le reste facultatif, **aucune validation qui bloque une saisie faite depuis un chantier**. **Done =** création manuelle en 4 champs, informateur obligatoire (400 FR sinon), l'avis manuel entre dans le MÊME sas et suit le MÊME cycle que les avis collectés, dédoublonnage de niveau 2 appliqué (VAO11). Files: `apps/veille_ao/services.py`, `apps/veille_ao/views.py`, `apps/veille_ao/tests/test_saisie_manuelle.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO14)
- [x] VAO28 — **Import CSV d'avis (coordonné avec AOF169, jamais en double).** Spec d'import sur `apps.dataimport.parsing.iter_rows` + `FIELD_MAPS` (référence, acheteur, objet, montant estimé, dates de remise et d'ouverture, lot, source), aperçu avant validation, rejets ligne à ligne avec motif FR, idempotence par empreinte (VAO11). **Coordination explicite : AOF169 (`docs/PLAN.md`) prévoit l'import CSV d'avis créant directement des `AppelOffre`** — les deux ne font PAS la même chose et ne doivent pas fusionner : VAO28 alimente le **sas** (un humain trie), AOF169 crée des **affaires**. Au moment de construire AOF169, l'annoter pour qu'il consomme le sas plutôt que de refaire un parseur CSV. **Done =** un CSV d'agrégateur ou de portail sectoriel s'importe dans le sas, ré-import idempotent, rejets lisibles, `import_specs` déclarés dans `platform.py` **seulement une fois câblés** (VAO13). Files: `apps/veille_ao/imports.py`, `apps/veille_ao/platform.py`, `apps/veille_ao/tests/test_import_avis.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO13, VAO27)
- [x] VAO29 — **`AcheteurCible` : le carnet des acheteurs à DÉMARCHER — la vraie contre-mesure FRDISI.** Constat : ce marché-là ne se surveille pas, il se démarche ; la seule façon de recevoir la prochaine consultation FRDISI est **d'être sur la liste d'invitation**. Modèle : nom, type (fondation, université privée, clinique, groupe hôtelier, industriel, coopérative agricole, promoteur, collectivité), contact, dernier contact, prochaine relance, statut de relation, `lead_id` opaque vers le CRM, notes. Seed d'amorçage avec les catégories (jamais des noms inventés). **Done =** carnet CRUD scopé société, une relance due remonte dans le centre d'échéances, lien vers le lead CRM par identifiant opaque (aucun import de `apps.crm.models`, `lint-imports` vert), aucun nom d'organisme inventé dans le seed. Files: `apps/veille_ao/models.py`, `apps/veille_ao/selectors.py`, `apps/veille_ao/tests/test_acheteurs_cibles.py`. (SCHEMA) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO14)
- [x] VAO30 — **« Retenir » → créer l'`AppelOffre` : l'UNIQUE point de contact cross-app du groupe.** Ajouter **UNE fonction en fin de `apps/ao/services.py`** — `creer_appel_offre_depuis_avis(company, user, donnees)` — qui crée l'`AppelOffre` au statut `identifie` avec sa référence via `core.numbering.create_with_reference` (**jamais `count()+1`** : le dépôt a déjà payé une collision de production), et l'appeler depuis `apps/veille_ao/services.py`. L'avis passe `converti` et stocke l'identifiant créé dans `appel_offre_id` (**entier opaque, jamais une FK** — c'est ce qui garde les apps découplées et le contrat import-linter vert). **AOF1 relogera le corps d'`apps/ao/services.py` depuis `compta` : cette fonction est un AJOUT PUR en fin de fichier et doit VOYAGER avec le relogement** (AOF1 est annoté en ce sens) ; si AOF1 est déjà passé au moment de construire, l'ajouter dans le corps relogé — dans les deux cas c'est un ajout, jamais une réécriture. **Done =** retenir un avis crée exactement un `AppelOffre` référencé et ouvre sa fiche, re-cliquer ne crée pas de doublon (le lien existe déjà), aucun import de `apps.ao.models` depuis `veille_ao` (`lint-imports` vert), aucune régression sur les 8 viewsets AO existants. Files: `apps/ao/services.py`, `apps/veille_ao/services.py`, `apps/veille_ao/tests/test_conversion_ao.py`. (ARCH) (@lane: backend/veille-ao) (@model: opus) (@after: VAO14, VAO27)
- [x] VAO31 — **Attribution : d'où vient réellement le chiffre d'affaires.** Constat central de l'étude : l'AO qui a occupé Reda n'aurait été capté par AUCUN dispositif automatique — **il faut donc MESURER, sur 12 mois, quel canal rapporte**, au lieu de le supposer. Selector d'agrégation par `source` et par `informateur` : avis reçus → retenus → convertis en `AppelOffre` → gagnés (l'issue vient d'`apps.ao` via son `selectors.py`, **jamais par import de modèle**). **Done =** un tableau « canal → avis → affaires → gagnés » calculé (jamais saisi), lecture cross-app par selector uniquement, le canal `tuyau_partenaire` apparaît à égalité avec le portail (c'est tout l'intérêt de la mesure). Files: `apps/veille_ao/selectors.py`, `apps/veille_ao/kpis.py`, `apps/veille_ao/tests/test_attribution.py`. (ROUTINE) (@lane: backend/veille-ao) (@model: sonnet) (@after: VAO30)

#### VAO W5 — Les écrans (VAO32-VAO38)

- [x] VAO32 — **Module frontend `veille_ao` + client API sur la factory partagée.** `frontend/src/features/veille_ao/module.config.jsx` (clé `veille_ao` **identique au manifeste backend** — `check_modules.py` le vérifie ; `order` libre et non déjà pris ; en-tête `eslint-disable react-refresh/only-export-components` **obligatoire**), nav « Veille AO » (items Avis · Acheteurs cibles · Paramètres de veille), routes lazy. Client API via `makeResourceFactory` (`frontend/src/api/resource.js`) — **aucun `axios` direct dans le module**. **Ne toucher AUCUN fichier de `frontend/src/features/ao/**` (réservé au groupe AOF)** ; le rapprochement des deux sections sera une tâche AOF ultérieure, pas d'ici. **Done =** la section apparaît au bon rang et seulement si le toggle `veille_ao` est actif, chaque route rend un squelette sans erreur, `check_modules.py` + eslint + `vite build` verts, aucun appel HTTP direct. Files: `frontend/src/features/veille_ao/module.config.jsx`, `frontend/src/api/veilleAoApi.js`, `frontend/src/api/veilleAoApi.test.mjs`. (ROUTINE) (@lane: frontend/veille-ao) (@model: sonnet)
- [x] VAO33 — **La liste des avis (`ListShell`) : la page qu'on ouvre le matin.** Colonnes objet · acheteur · lieu · date limite avec urgence (`urgency.js`, jamais un seuil local) · montant estimé · score · mots déclencheurs · statut ; **pastille « N nouveaux depuis hier »** ; filtres (statut, source, mot-clé, acheteur, région, échéance, montant) persistés en URL ; vues sauvegardées ; export. Données via `useResource` + le client API — **zéro `useState`/`useEffect` de fetch**, zéro calcul de KPI côté front. **Done =** tri/filtre persistés en URL, la pastille compte juste (test), un avis auto-ignoré affiche la règle qui l'a filtré, la liste reste lisible à 500 lignes. Files: `frontend/src/features/veille_ao/AvisList.jsx`, `frontend/src/features/veille_ao/AvisList.test.jsx`. (ROUTINE) (@lane: frontend/veille-ao) (@model: sonnet) (@after: VAO32)
- [x] VAO34 — **Fiche avis + les deux gestes qui comptent : « Retenir » et « Ignorer ».** Détail complet, bouton « Charger le détail » (enrichissement à la demande VAO18, avec état de chargement et échec propre), lien sortant vers l'avis d'origine, chatter `records` (**jamais une timeline maison**). « Retenir » crée l'affaire et navigue vers elle ; « Ignorer » demande le motif et **propose** la règle d'exclusion sans jamais la créer en douce. **Done =** les deux actions appellent un service serveur réel (aucune action de façade), le détail indisponible affiche un message FR et laisse l'avis intact, le chatter est celui de `records`. Files: `frontend/src/features/veille_ao/AvisDetail.jsx`, `frontend/src/features/veille_ao/AvisDetail.test.jsx`. (ROUTINE) (@lane: frontend/veille-ao) (@model: sonnet) (@after: VAO33)
- [x] VAO35 — **Écran « Paramètres de veille » (Directeur) : mots-clés, sources, exclusions, cadence — et le BOUTON.** Édition des `MotCleVeille` (deux niveaux, poids), activation/désactivation des `SourceVeille`, gestion des `RegleExclusion` avec leur compteur d'application, et le bouton **« Rafraîchir maintenant »** (VAO23) avec sa barre de progression. **L'état d'armement de la collecte est AFFICHÉ explicitement** (« collecte automatique : désarmée — accord fondateur requis ») : personne ne doit croire que ça tourne alors que non. **Done =** gated `veille_ao_gerer` (403 propre sinon), un mot-clé ajouté est pris en compte à la collecte suivante, l'état désarmé est impossible à confondre avec l'état armé, double clic sur le bouton ne lance pas deux collectes. Files: `frontend/src/features/veille_ao/ParametresVeille.jsx`, `frontend/src/features/veille_ao/ParametresVeille.test.jsx`. (ROUTINE) (@lane: frontend/veille-ao) (@model: sonnet) (@after: VAO33)
- [x] VAO36 — **Écran « Acheteurs cibles » + relances — la prospection qui capte les FRDISI suivants.** Liste du carnet (VAO29) avec type, dernier contact, prochaine relance, statut de relation ; création rapide ; lien vers le lead CRM quand il existe ; relances dues en tête. **Done =** une relance due est visible sans la chercher, le lien CRM ouvre le lead existant sans en créer un second, aucune donnée d'organisme pré-remplie inventée. Files: `frontend/src/features/veille_ao/AcheteursCibles.jsx`, `frontend/src/features/veille_ao/AcheteursCibles.test.jsx`. (ROUTINE) (@lane: frontend/veille-ao) (@model: sonnet) (@after: VAO33)
- [x] VAO37 — **Bandeau de santé de la collecte + la carte d'honnêteté « ce que la veille NE voit pas ».** Deux blocs indissociables : (1) santé — dernière collecte réussie **et son âge**, alarme de silence (VAO24) en évidence, nombre d'avis examinés hier ; (2) **honnêteté** — une carte permanente qui énonce, en français simple, que la veille automatique couvre le portail public (**~65-75 % des opportunités adressables**) et **PAS** les consultations privées type FRDISI (**~15-25 % du flux réel, 0 % détectable**), ni ONEE-Élec/MASEN/OCP (~10 % du nombre mais la majorité de la valeur), avec le rappel « un AO reçu par WhatsApp ? → bouton Ajouter un avis ». Constat : promettre l'exhaustivité serait faux dès le premier jour, et c'est exactement l'erreur qui a coûté un AO. **Done =** l'âge de la dernière collecte est visible sans clic, une alarme active est impossible à manquer, le texte d'honnêteté est présent et testé (un test échoue s'il disparaît). Files: `frontend/src/features/veille_ao/SanteVeille.jsx`, `frontend/src/features/veille_ao/SanteVeille.test.jsx`. (ROUTINE) (@lane: frontend/veille-ao) (@model: sonnet) (@after: VAO33)
- [x] VAO38 — **Guide utilisateur FR de la veille (4 pages max).** Ajouter au guide existant : où regarder le matin, ce que « nouveau/retenu/ignoré/converti » veut dire, comment ajouter un avis reçu par WhatsApp, comment régler ses mots-clés, ce que la veille ne voit pas et pourquoi, quoi faire quand l'alarme de silence sonne. **Done =** section ajoutée au guide, aucune capture d'écran inventée, relue pour un lecteur non technique. Files: `docs/GUIDE_UTILISATEUR_ERP.md`. (ROUTINE) (@lane: gov/veille-ao) (@model: haiku) (@after: VAO37)

#### VAO W6 — Extensions phase 2, toutes GATÉES (VAO39-VAO42)

- [ ] VAO39 — **[GATED : après une phase 1 armée et stable ≥ 1 mois] Bons de commande (« avis d'achat en cours ») — le gisement le mieux dimensionné pour Taqinor.** Constat : le portail publie aussi les bons de commande (préavis 48 h) — petits chantiers, gros volume, **exactement la taille d'affaire d'un EPC de la taille de Taqinor**. Même client, même parseur, autre point d'entrée de recherche ; le préavis de 48 h impose une collecte quotidienne fiable, d'où le gate sur une phase 1 stable. **Done =** source dédiée activable, avis de bon de commande distingués dans la liste, aucune régression sur la collecte d'appels d'offres. Files: `apps/veille_ao/portail/bons_commande.py`, `apps/veille_ao/tests/`. (ROUTINE) (@lane: backend/veille-ao-collecteur) (@after: VAO24)
- [ ] VAO40 — **[GATED : décision fondateur + un fichier `tos_risk/` PAR portail] Portails sectoriels Atexo — MASEN, CDG, ADM, Marsa Maroc.** Constat vérifié : **quatre portails sectoriels tournent le MÊME logiciel Atexo que le PMMP**, donc la recette technique de VAO16 s'y applique presque telle quelle — et c'est là que vivent les gros MW solaires (MASEN Noor Midelt III/Noor Atlas, BESS 1,6 GWh). **Chaque portail est une cible distincte : la règle #5 exige un fichier de risque ET un accord PAR cible** — approuver le PMMP n'approuve rien d'autre. **Done =** un portail supplémentaire = une ligne `SourceVeille` + un fichier de risque + un accord, sans modification du collecteur (test : le collecteur ne connaît aucune URL en dur). Files: `tos_risk/`, `apps/veille_ao/management/commands/seed_veille_sources.py`. (DECISION) (@lane: gov/veille-ao) (@after: VAO39)
- [ ] VAO41 — **[GATED : dépense fondateur] Abonnement agrégateur pour la couche privée — et la limite juridique à respecter.** Options relevées : **Datao** (datao.ma, ~490/790 MAD/mois, ~300 sources, essai 7 jours, seul à annoncer une intégration MCP exploitable par machine) ; **lesoffres.ma** (990 DH/12 mois, alertes e-mail illimitées, public + privé + bons de commande, garantie 30 jours) ; **Marché Facile** (gratuit, indexe ONEE/ONDA/Marsa/ADM/ANP/CDG). **Limite dure : les CGU de Datao interdisent l'extraction substantielle** — un abonnement donne des ALERTES, pas le droit de miroiter leur base dans l'ERP ; l'intégration légitime est la saisie/l'import (VAO27/VAO28) depuis leurs e-mails, pas un second scraper. **Done =** décision fondateur consignée (lequel, ou aucun), et si souscrit, la source créée en `agregateur` avec la voie d'entrée import/manuelle — jamais de collecte automatique chez eux. Files: aucun (décision ; consigner dans le DONE LOG). (COST) (@lane: gov/veille-ao) (@after: VAO28)
- [ ] VAO42 — **[GATED : nécessite un compte fournisseur par organisme] ONEE-Électricité et OCP — les deux plus gros acheteurs hors portée.** Constat : ONEE-Élec et OCP publient sur leurs propres plateformes, **OCP exigeant un compte fournisseur** (`supplier.ocpgroup.ma`) — donc hors de portée d'une collecte anonyme et **hors du périmètre de la règle #5 telle qu'écrite** (un accès authentifié est un tout autre régime : il engage un compte société et les conditions acceptées à l'inscription). Tant que ces comptes n'existent pas, ces deux acheteurs restent couverts par la **porte manuelle**. **Done =** décision fondateur sur l'ouverture des comptes fournisseurs ; si ouverts, ces sources restent en saisie/import **et ne sont jamais collectées automatiquement sans une relecture explicite des conditions acceptées**. Files: aucun (décision ; consigner dans le DONE LOG). (DECISION) (@lane: gov/veille-ao) (@after: VAO41)

#### NE PAS FAIRE (Groupe VAO)

- **Ne PAS créer les modèles de veille dans `apps/ao`** : sa chaîne de migrations est mono-écrivain et réservée aux 6-8 migrations déjà nommées du groupe AOF (`docs/PLAN.md`). Même raison côté écran : **ne toucher aucun fichier de `frontend/src/features/ao/**`**.
- **Ne JAMAIS maquiller le User-Agent** pour contourner le 403 du pare-feu. UA honnête déclarant Taqinor ; refusé → on s'arrête et on bascule sur les alertes officielles (VAO44). C'est la conclusion explicite de la revue adversariale qui a refusé la première version de ce plan : en l'absence de conditions d'utilisation, **la règle de refus du pare-feu EST l'expression de la volonté de l'exploitant**, pas une friction technique à contourner.
- **Ne PAS balayer les 3 380 avis ouverts** (~338 POST/jour). La requête est toujours restreinte par mots-clés : 1 à 3 pages, moins de 10 requêtes/jour — la garde de VAO19 doit rendre l'inverse impossible à écrire.
- **Ne PAS construire VAO15-VAO20 avant que VAO2 ait répondu** : si le flux RSS authentifié existe, ces 6 tâches n'ont aucune raison d'exister et tout le débat règle #5 disparaît.
- **Ne PAS accepter les CGU du compte entreprise sans les lire** (VAO2) : c'est le seul chemin capable de créer une restriction contractuelle qui n'existe pas aujourd'hui — et elle primerait sur toute l'analyse de VAO3.
- **Ne PAS exécuter le collecteur avant VAO4** (accord écrit du fondateur + fichier de risque committé) — et **jamais depuis un compte personnel**, ni depuis un compte tout court : la collecte est anonyme par conception.
- **Ne PAS créer automatiquement un `AppelOffre` depuis un avis.** Le portail contient beaucoup de bruit ; le sas et la décision humaine sont le produit.
- **Ne PAS télécharger les DCE ni les pages de détail en masse** (délais de 110 s mesurés) — uniquement sur clic.
- **Ne PAS scraper un agrégateur payant** : leurs CGU interdisent l'extraction substantielle. Un abonnement se consomme par alerte e-mail → saisie/import.
- **Ne PAS promettre l'exhaustivité dans l'UI** ni retirer la carte d'honnêteté de VAO37. L'AO FRDISI n'aurait été capté par aucun de ces dispositifs, et l'utilisateur doit le savoir.
- **Ne PAS déclarer de nouveau signal `core/events.py`** pour ce groupe (aucun besoin cross-app réel ; un seam sans abonné fait rougir la CI).
- **Ne PAS re-coder** un chatter, une numérotation, une file de jobs, un parseur CSV ou un client HTTP maison : `records`, `core.numbering`, `core.jobs`, `dataimport`, `httpx` sont déjà là.
- **Ne PAS fusionner VAO28 et AOF169** : l'un alimente le sas, l'autre crée des affaires.
- **Ne PAS ré-explorer le portail** : la recette HTTP, l'absence d'API/RSS/robots.txt et les mots-clés productifs ont été vérifiés en main le 2026-08-01 et sont écrits dans l'en-tête de ce groupe.

## Pending Reda (carry these in the plan)
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

## DONE LOG (agent appends one plain-language line per completed task)
- 2026-08-07 — **Groupe VAO — la veille appels d'offres, socle + portes manuelles (27 tâches, 1 merge).** L'app NEUVE `apps/veille_ao` (jamais `apps/ao`, dont la chaîne de migrations est réservée au groupe AOF) : VAO3 fichier de risque `tos_risk/marchespublics_gov_ma.md` écrit SANS enjoliver (le refus 403 du pare-feu lu comme l'expression de la volonté de l'exploitant, « UA honnête, arrêt sur 403, jamais de maquillage », balayage 338-POST explicitement exclu, clause InfoSite neutralisée en ne republiant rien) ; VAO6-14 le socle (catalogue de SOURCES en base — aucune URL de portail en dur —, le SAS `AvisMarche`, mots-clés et score en DONNÉE, règles d'exclusion qui APPRENNENT, dédoublonnage à deux niveaux, permissions voir/gérer, manifeste ne déclarant QUE le câblé, service unique de changement de statut gardé par introspection AST) ; VAO21-31 la collecte et les portes manuelles (orchestration par REGISTRE de lecteurs — le collecteur du portail se branchera sans réécriture —, tâche 06:00 livrée **DÉSARMÉE** (`VEILLE_AO_COLLECTE_ACTIVE=0`), bouton « Rafraîchir maintenant » lançant EXACTEMENT le même job que la nuit, `ExecutionCollecte` + **alarme de collecte silencieuse**, notification FR seulement quand il y a à dire, rétention, saisie manuelle 30 s avec informateur OBLIGATOIRE, import CSV, carnet `AcheteurCible` livré VIDE (aucun nom d'organisation inventé), « Retenir » → `AppelOffre` via la fonction que AOF169 avait écrite pour ça, attribution du CA par source et par informateur) ; VAO32-37 les écrans (liste du matin, fiche + Retenir/Ignorer, paramètres, acheteurs cibles, bandeau de santé + **carte d'honnêteté « ce que la veille NE voit pas »**). **VAO15-VAO20 (le collecteur HTTP) NON CONSTRUITS** — gardés par un test AST qui échoue si un module importe `httpx`/`requests`/`urllib` : ils attendent VAO2 (le fondateur ouvre le compte gratuit et va VOIR si le flux RSS authentifié existe — s'il existe, ils ne seront JAMAIS construits) et VAO43 (courrier au TGR). VAO4/VAO5/VAO39-44 restent `[ ]`, portes fondateur. Migrations : veille_ao 0001-0007. Aucune dépendance payante ; aucun appel réseau vers un portail public dans tout le dépôt.
- 2026-07-11 — **PLAN2 clean-lane wave (8 time-balanced lane-drainers) — 17 tasks folded onto batch.** VX65 lien profond survit à la connexion (`?next=` sûr) ; VX78 vraie page 404 (ui/NotFound) ; VX57 CopilotPanel/Sora paresseux hors chemin froid ; VX58 préchargement au survol des destinations chaudes ; VX37 AgentChat reveal incrémental + mini-tableaux ; VX39 OCR source+extraction côte à côte, édition inline ; VX73 notice i18n honnête (chrome-only) + ⌘/Ctrl K réel ; VX74 [DECISION] note AR = documents-seulement (pas d'UI RTL) ; VX85 file records : snooze non destructif + notifs mentions/réassignation avec deep-link ; **VX101 [AUTH] seul Responsable/Admin décide une approbation installations/contrats (corrige un trou : un rôle normal pouvait décider)** ; **VX72 [DEP/DECISION] Sentry frontend no-op DSN-gaté — AUCUNE dépendance ajoutée (import à specifier variable, activé seulement si Reda installe @sentry/react + pose VITE_SENTRY_DSN)** ; VX115 KPI cockpit → écrans d'action + index des exports ; VX48 [BUG iOS] tous les PDF via onglet pré-ouvert (Safari) ; VX49 détection réelle du blocage popup + gestion d'erreur ; VX30 mur de flotte vivant (statut PR 3 paliers, pouls temps réel visibility-aware) ; VX84 cloche bornée à mes retards (assigned_to=moi) ; VX95 toastWithUndo câblé (archivage leads/stock, drop kanban). Fold-time (orchestrateur) : 5 lints react-hooks corrigés (setState-en-effet→phase de rendu sur Layout/AgentChat/OcrUpload, écriture de ref→effet sur FleetPage/Co2Page) ; **VX72 réparé** (le bare `import('@sentry/react')` cassait le build+6 suites → specifier variable) ; conflits imports LeadsPage/StockList/FactureList résolus en gardant les deux côtés. RE-MIS EN FILE (rebuild propre sur la base fusionnée) : VX97 (conflit massif avec la refonte menu VX20 de DevisList), VX114 (ma résolution take-ours a laissé tomber sa modale d'export → revert), VX116 (bug réel : annuler un aperçu WhatsApp le déclenchait quand même → revert). VX246 [BLOCKED: mal étiqueté @lane apps/records — c'est du frontend/iOS]. VX98 (agent mort erreur API) à reprendre.
- 2026-07-11 — **PLAN2 lane-drain wave (8 time-balanced agents) + tooling — folded onto accumulating batch (target ~60/merge, no per-wave merge).** `plan_lanes.py` gained LPT time-balancing across N workers (task `— S/M/L/XL` size → cost, whole lanes bin-packed so the 8 agents finish together; `--workers` flag; +8 tests). Then 17 tasks recovered from the lane-drainers (a mid-run Claude Code process restart killed the live agents; their COMMITTED work survived on the worktree branches and was cherry-picked): VX213 handoffs AVAL notifiés ; VX195 MapView role=application+liste clavier ; VX234 audit rôles au grain permission + garde réassignation ; VX242 ChangePassword révoque les autres sessions ; VX108 `lib/contactLinks` partagé (tel/wa) + câblage ; VX109 Importer/ExcelImport fournisseurs/équipements ; VX51 champ focalisé au-dessus du clavier iOS (VisualViewport) ; VX92 « Créer un autre » + mort du window.alert paiement ; VX183 densité kb-col iPad ; VX145 header CRM en menu d'actions + SavedViewsBar partagé ; VX218 badge « Nouveau » réception + escalade demandeur ; VX15 ModuleHero+sparklines ; VX137 table de lignes générateur en `ui/Input` ; VX139 `QuoteTotalsSummary` partagé (une seule devise MAD) ; VX20 menus Plus DevisList/RelancesPage/BulkActionBar ; VX21 squelette+cockpit trésorerie FactureList ; VX50 `data-label` FactureList/RelancesPage + garde CI. Fold-time (orchestrateur) : conflits FournisseurFiche360 (VX108↔VX149) et FactureList imports (VX21↔VX184) résolus en gardant les deux ; corrigé le test VX137 (assertion `12.` = artefact jsdom de `type=number`, remis sur le vrai contrat step="any" anti-arrondi) + polyfill ResizeObserver au test VX15. VX252 [BLOCKED: attend VX156 celebrate.js]. VX183 note : part agenda-view reste bloquée sur VX147 (MonthGrid). Reliquats de lanes (tâche en cours à la mort de chaque agent + non démarrées) re-dispatchés.
