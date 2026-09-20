# PLAN_VERTICALS — file de travail parallèle (split de new_tasks_plan.md, 2026-07-10)

> **CONTRAT DE PROPRIÉTÉ (non négociable — c'est lui qui garantit zéro conflit).**
> Une session `work on the plan verticals` ne touche QUE :
> **backend :** nouvelles apps agriculture/hospitality/education/sante/immobilier/btp_chantier/esg (aucune app existante).
> **frontend :** frontend/src/pages|features des verticaux correspondants.
> Tout le reste est INTERDIT en écriture — une autre session peut le posséder.
> Lire une app étrangère = via son `selectors.py`/string-FK uniquement (jamais
> ses models/migrations). Une tâche qui EXIGE d'écrire hors périmètre →
> `[BLOCKED: hors périmètre VERTICALS]` + continuer (elle reviendra au run
> plateforme). Fichiers frontend PARTAGÉS (router/nav/api/ui) : ajouts
> APPEND-ONLY minimaux ; un conflit à l'update-branch se résout en prenant les
> DEUX ajouts. Base de test locale : `DB_NAME=erp_verticals` (jamais la
> DB partagée). Chaque session merge sa propre branche `dev-verticals`
> vers main indépendamment (update-branch → CI ~6 min → auto-merge) ; si
> `docs/CODEMAP.md` (fingerprint structure) conflicte à l'update, prendre
> l'arbre mergé et relancer `python scripts/codemap_fingerprint.py --write`.
> Ce fichier n'est PAS dans la surface du plan-fingerprint (comme WEB_PLAN.md) :
> tick + DONE LOG ici, jamais dans docs/CODEMAP.md §10.
> JAMAIS ré-implémenter localement une primitive plateforme manquante (chatter,
> numérotation, jobs, files, registre…) : si une tâche dépend d'une primitive
> ARC/NT pas encore sur main → `[BLOCKED: attend <ID>]` + continuer. C'est le
> vecteur n°1 de dette constaté (13 chatters artisanaux) — bloquer vaut mieux.
> Groupes : NTAGR, NTCON, NTEDU, NTESG, NTHOT, NTPRO, NTSAN. Règles WOW/CLAUDE.md inchangées
> (lane-draining, revue adversariale, retro, routage modèle via plan_lanes.py).

## DONE LOG (une ligne datée par tâche livrée)


### Groupe NTCON — Vertical BTP/EPC vendable (situations, sous-traitance, RFI/visas, réserves, plans, journal de chantier) — bench: Procore, Fieldwire, Graneet, Vertuoza (audit 2026-07-08)
Existant : `installations` (chantiers solaires, lifecycle CH1-6, PV/parc), `gestion_projet` (Projet/PhaseProjet/BudgetProjet/EVM/plan de charge, XPRJ1-29 socle timesheets+facturation régie+situations de travaux XPRJ4+pénalités marché public XPRJ27), `installations.SousTraitant/OrdreSousTraitance` (FG304-307, registre+ordres+attestations sous-traitant), `contrats` (Avenant CONTRAT24, RegleApprobation/EtapeApprobation, SignatureContrat, VersionContrat), `compta.RetenueGarantie/CautionBancaire` (FG145), `qhse` (NCR/CAPA, ITP, DUER, PermisTravail/LOTO), `ged` (Cabinet/Folder/Document/DocumentVersion/PartageGed/watermark/ACL). Ce groupe généralise à un groupe de construction/EPC vendable : réserves/punch-list visuelles sur plan avec preuve de levée (XFSM18 couvre déjà réserve→devis, PAS la punch-list géo-localisée elle-même), RFI, visas de documents techniques, avenants marché CÔTÉ PROJET/BUDGET (CONTRAT24 gère l'amendement contractuel, pas le chiffrage/impact planning-budget), journal de chantier quotidien, diffusion contrôlée de plans (au-dessus de GED), DGD, planning TCE multi-lots avec pénalités par lot, lien PPSPS↔QHSE. Frontières : NTPRJ (générique, hors scope BTP), NTFSM (interventions ponctuelles SAV/terrain — XFSM* déjà exhaustif), qhse/rh existants (jamais réécrits, seulement liés par string-FK/selectors).


#### Profondeur (round 2) — intégration chatter/audit/notifications, KPI, e2e

- [ ] NTCON35 [BLOCKED: e2e exige ci.yml (hors lane) + BUG PRODUIT découvert : lever une réserve exige une photo 'apres' que ReservesChantier.jsx ne permet pas de téléverser (→ ERROR_PLAN)] — **Test e2e du parcours réserve→levée→export dossier.** Suite Playwright (pattern e2e existant E1-16) : créer un chantier BTP via le wizard (NTCON23) → poser un pin de réserve sur un plan GED → lever la réserve avec photo+signature (NTCON2) → vérifier son passage en « levée » dans le cockpit (NTCON21) → exporter le dossier chantier (NTCON20) et vérifier la présence de la preuve dans le ZIP. **Done =** parcours complet vert en CI, sélecteurs DOM stables (`btp-*` prefix), inclus dans la suite requise. Files: `e2e/btp-chantier.spec.ts` (nouveau), tests. (ROUTINE) «model: sonnet» (@after: NTCON2, NTCON20, NTCON21, NTCON23)


> Groupes NTPRO / NTSAN / NTHOT / NTEDU / NTAGR déménagés le 2026-09-02 vers
> `docs/backlog/FULL_SAAS_PLAN.md` (spécialisation ERP solaire — verticaux non adaptables,
> parqués sans suppression, réactivables). Restent ici : NTCON (BTP/EPC, le chantier sert
> l'installation solaire C&I) et NTESG.

### Groupe NTESG — Reporting ESG/durabilité d'entreprise consolidé — bench: Workiva, EcoVadis, Salesforce Net Zero Cloud (audit 2026-07-07)

**Vérifié dans le code (2026-07-07) : le socle carbone/ESG est DÉJÀ construit dans `apps/qhse`** —
`BilanCarbone`/`LigneBilanCarbone` (QHSE39, scopes 1/2/3 GHG Protocol, `tco2e` dérivé), `IndicateurESG`
(QHSE40, pilier E/S/G, cible/tendance/`atteinte_cible`, sélecteur `export_esg` groupé par pilier),
`ReleveConsommation` + `generer_lignes_bilan` (XQHS21, élec/eau/carburant sites → bilan carbone),
`Dechet`/`BordereauSuiviDechet` (déchets + BSD), `ConformiteEnvironnementale`, `AspectEnvironnemental`
(ISO 14001), coût de la non-qualité (XQHS22). Ce groupe ne reconstruit RIEN de tout ça — il ajoute la
couche **CONSOLIDATION ENTREPRISE** qui manque encore : périodes de reporting figées (snapshot),
agrégation cross-app en LECTURE (flotte carburant, RH social, QHSE environnement/CoQ), objectifs +
trajectoire pluriannuelle, rapport PDF/xlsx GRI-lite avec méthodologie affichée, volet fournisseurs RSE,
et le tableau de bord ESG consolidé qu'aucun écran n'affiche aujourd'hui (les indicateurs QHSE39/40
n'ont même pas encore de cockpit React — FE-XQHS20-21 couvre l'environnement, pas l'ESG consolidé).
Frontières : QHSE garde la SAISIE des données sources (bilan carbone, indicateurs bruts, déchets,
relevés) ; NTESG lit ces sources via `qhse.selectors` et les siennes propres, ne les modifie jamais.
NTNRG garde le carbone de PRODUCTION solaire et les attestations clients. NTLOG garde le CO2 transport
opérationnel (NTESG l'agrège en lecture seule via son sélecteur). NTGRC garde le moteur de
questionnaires générique ; NTESG en réutilise le modèle pour une variante RSE fournisseurs sans
dupliquer le moteur (coordination cross-plan si NTGRC22/23 n'existent pas encore au moment du build —
voir note de coordination sous P1). Règle stricte checked-facts-only : un indicateur sans donnée est
OMIS du rapport (jamais 0, jamais estimé silencieux) ; toute valeur calculée porte un libellé
« estimation » visible ; aucun facteur d'émission n'est présenté comme certifié/audité.

#### P1 — Consolidation & référentiel ESG (bloquants vente grands comptes)

- [ ] NTESG8 [DÉBLOQUÉE: NTGRC22/23 livrées 12/09 — contrat contract_samples/questionnaires_fournisseur.json] — **Coordination cross-plan — variante questionnaire RSE fournisseurs.** Si le moteur générique de questionnaires (référencé dans le brief comme NTGRC22/23) existe déjà au moment du build de cette tâche : ajouter une variante de modèle de questionnaire pré-remplie « RSE fournisseur » (thèmes : conditions de travail, environnement, éthique des affaires, conformité réglementaire — inspiré EcoVadis sans jamais utiliser ce nom commercial) réutilisant TEL QUEL le moteur d'envoi/relance/scoring de NTGRC, avec un score RSE consolidé par fournisseur exposé en lecture par `stock.selectors.fournisseur_score_rse` (fonction fine, appelée par NTESG, jamais l'inverse). Si NTGRC22/23 n'existent PAS encore à ce moment : marquer `[BLOCKED: dépend de NTGRC22/23 — moteur de questionnaires non construit]`, ne rien dupliquer, passer à la tâche suivante. **Critère d'acceptation** : soit le questionnaire RSE fonctionne bout-en-bout en réutilisant le moteur NTGRC existant sans code dupliqué, soit la tâche est marquée bloquée proprement sans stub cassé. Files: `apps/esg/models.py` (+migration, si NTGRC22/23 disponibles), `apps/esg/services.py`, `apps/stock/selectors.py` (fonction `fournisseur_score_rse`, additive), tests. (ROUTINE) «model: sonnet»

#### P3 — Delighters

- [ ] NTESG17 [DÉBLOQUÉE: suit NTESG8] — **Widget « Score ESG fournisseur » sur la fiche fournisseur stock** : si NTESG8 a pu être construit (moteur RSE fournisseur disponible), afficher un badge simple sur `ProduitForm`/fiche fournisseur (lecture seule via `stock.selectors.fournisseur_score_rse`) — sinon `[BLOCKED: dépend de NTESG8]`. **Critère d'acceptation** : le badge s'affiche sans appel bloquant si le score est absent (fournisseur jamais évalué → aucun badge, pas de "0"), tests. Files: `frontend/src/features/stock/ProduitForm.jsx`, tests. (ROUTINE) «model: haiku» (@after: NTESG8)

---

#### Profondeur (round 2) — rapports, wizard, réglages, planifié, permissions, API/webhooks, imports/exports, e2e, chatter, KPI

- [ ] NTESG21 — **Tâche planifiée Celery beat — rappel de clôture de période** : `apps/esg/tasks.py::rappeler_cloture_periode` (pattern `apps/qhse/tasks.py`), exécutée quotidiennement, notifie le `pilote_esg` (NTESG20) via `notifications.notify()` quand une `PeriodeReportingESG` en statut `brouillon` dépasse sa `date_fin` de plus de 15 jours sans être figée. Un seul rappel par période tous les 7 jours (pas de spam quotidien) via un champ `dernier_rappel_le` sur la période. Best-effort, jamais bloquant. **Critère d'acceptation** : la tâche ne renvoie pas de rappel avant 15 jours de retard, puis au maximum un par semaine ensuite, tests avec horloge simulée. Files: `apps/esg/tasks.py` (nouveau), `apps/esg/models.py` (+migration : `dernier_rappel_le`), tests. (ROUTINE) «model: haiku»
- [ ] NTESG22 — **Tâche planifiée Celery beat — recalcul de couverture catalogue** : `apps/esg/tasks.py::recalculer_couverture_catalogue`, exécutée hebdomadairement par société active, rafraîchit un cache léger (`CatalogueIndicateurESG.couverture_cache` JSON par pilier, horodaté) consommé par le cockpit NTESG6 pour éviter un recalcul synchrone coûteux à chaque chargement d'écran quand le nombre d'indicateurs grossit. Le endpoint `catalogue-esg/couverture/` (NTESG3) sert le cache si `<24h`, recalcule en direct sinon (best-effort, jamais bloquant si la tâche a échoué). **Critère d'acceptation** : le cache expire proprement après 24h et retombe sur le calcul synchrone sans erreur si jamais rafraîchi, tests. Files: `apps/esg/tasks.py`, `apps/esg/models.py` (+migration : `couverture_cache`), `apps/esg/views.py`, tests. (ROUTINE) «model: haiku»
- [ ] NTESG23 — **Tâche planifiée Celery beat — purge des brouillons de rapport orphelins** : `apps/esg/tasks.py::purger_rapports_orphelins`, exécutée mensuellement, supprime (soft-delete, jamais hard-delete) les fichiers PDF/xlsx générés en aperçu (NTESG18 étape 3) non rattachés à une période effectivement figée après 30 jours, pour éviter l'accumulation de fichiers MinIO orphelins. Ne touche jamais un fichier attaché à une période figée ou publiée. **Critère d'acceptation** : un aperçu de 40 jours pour une période restée brouillon est purgé, un aperçu attaché à une période figée ne l'est jamais, tests. Files: `apps/esg/tasks.py`, tests. (ROUTINE) «model: haiku»
- [ ] NTESG24 — **Permissions par rôle fines du module ESG** : nouveaux codes de permission ajoutés au JSON `Role.permissions` (`esg.view`, `esg.edit_objectifs`, `esg.figer_periode`, `esg.publier_rapport`, `esg.gerer_parametres`) enregistrés dans `init_roles.py` avec un mapping par défaut raisonnable (ex. rôle « Direction »/« QHSE » = tout, rôle « Commercial » = aucun accès ESG). Le endpoint `figer/` (NTESG1) exige `esg.figer_periode`, la publication d'un rapport exige `esg.publier_rapport` — distinct de la simple lecture du cockpit (`esg.view`). **Critère d'acceptation** : un utilisateur sans `esg.figer_periode` reçoit un 403 explicite sur l'action de figeage même s'il voit le cockpit en lecture, tests. Files: `apps/roles/` (init_roles.py, registre de permissions, additif), `apps/esg/views.py`, tests. (AUTH) «model: sonnet»
- [ ] NTESG25 — **Exposition API publique lecture seule (`publicapi`)** : ajouter `esg.periode_reporting_publiee` et `esg.indicateur_esg` au `EVENT_CHOICES`/registre de ressources exposables de `apps/publicapi` (pattern existant `ApiKey`/scopes), permettant à une clé API scope `esg:read` de lister UNIQUEMENT les `PeriodeReportingESG` en statut `publiee` (jamais brouillon/figée-non-publiée) et leur `SnapshotESG` gelé — utile pour un donneur d'ordre/auditeur externe qui veut tirer les chiffres via API plutôt qu'un PDF. Aucune donnée de prix/commerciale n'est jamais exposée par ce scope. **Critère d'acceptation** : une clé sans le scope `esg:read` reçoit 403, une période non publiée n'apparaît jamais même avec le scope, tests. Files: `apps/publicapi/` (registre de ressources, additif), `apps/esg/views.py`, tests. (ROUTINE) «model: sonnet»
- [ ] NTESG26 — **Webhook sortant `esg.periode_publiee`** : événement publié sur `core/events.py` quand une période passe `figee` → `publiee`, consommé par `publicapi.Webhook` (pattern existant `EVENT_CHOICES`) pour notifier un système externe (ex. plateforme donneur d'ordre grands comptes) qu'un nouveau rapport ESG est disponible, payload minimal (id période, dates, statut, URL de l'export xlsx si publié) — jamais le contenu détaillé des indicateurs dans le payload webhook (l'appelant doit retirer via l'API scope `esg:read`, NTESG25, pour forcer l'authentification sur la donnée fine). **Critère d'acceptation** : publier une période déclenche exactement une livraison webhook par abonnement actif, retry existant de `WebhookDelivery` réutilisé sans code dupliqué, tests. Files: `apps/esg/services.py` (émission d'événement `core/events.py`), `apps/publicapi/` (EVENT_CHOICES, additif), tests. (ROUTINE) «model: sonnet»
- [ ] NTESG27 — **Import CSV en masse — bibliothèque de facteurs d'émission (NTESG16)** : action `facteurs-emission/import/` (multipart CSV, colonnes catégorie/unité/valeur/source/date_maj), réutilise le moteur `dataimport.ImportJob`/`ImportJobRow` existant (jamais un parseur CSV maison) pour prévisualiser, valider (unité cohérente par catégorie, valeur numérique positive) puis importer en masse une mise à jour annuelle de facteurs (ex. nouvelle version ADEME Base Carbone), en créant une nouvelle version historisée par facteur modifié plutôt qu'un écrasement silencieux. **Critère d'acceptation** : un CSV avec une ligne invalide échoue sur cette seule ligne avec message précis, les lignes valides s'importent, l'historique de version se crée, tests. Files: `apps/esg/views.py` (endpoint `facteurs-emission/import/`, réutilise `apps/dataimport`), tests. (ROUTINE) «model: sonnet»
- [ ] NTESG28 — **Export CSV — registre des parties prenantes ESG (NTESG12)** : action `parties-prenantes-esg/export/?format=csv` sur le même modèle que les autres exports CSV de l'app (colonnes nom/catégorie/enjeux/influence/intérêt), utile pour préparer une matrice de matérialité dans un tableur externe lors d'un exercice collaboratif avec la direction. **Critère d'acceptation** : le CSV s'ouvre avec les bons en-têtes et un accent UTF-8 correct (BOM), tests. Files: `apps/esg/views.py`, tests. (ROUTINE) «model: haiku»
- [ ] NTESG29 — **Test e2e — parcours clé « saisir un objectif, figer une période, générer le rapport »** : scénario Playwright (pattern `e2e/`) : se connecter avec un rôle doté de `esg.figer_periode` (NTESG24) → créer un `ObjectifESGTrajectoire` via le wizard (NTESG19) → ouvrir le cockpit (NTESG6), vérifier l'affichage des cartes par pilier avec les vraies données QHSE seed → lancer le wizard de clôture (NTESG18) → figer la période → télécharger le PDF (NTESG4) et vérifier qu'il contient le bandeau méthodologique obligatoire. **Critère d'acceptation** : le scénario passe de bout en bout sur les données de test seed, s'exécute dans la suite e2e existante sans nouvelle infra. Files: `e2e/esg.spec.ts` (nouveau), tests. (ROUTINE) «model: sonnet»
- [ ] NTESG30 — **Intégration chatter/records sur `PeriodeReportingESG`** : chaque `PeriodeReportingESG` s'enregistre comme objet suivable via `records.Follower`/`records.Activity` (pattern déjà utilisé ailleurs dans l'ERP, jamais un chatter maison spécifique à l'app esg) : le figeage (NTESG1), la publication et l'ajout d'un `DocumentPolitiqueESG` (NTESG13) en annexe créent chacun une entrée d'activité horodatée avec l'utilisateur acteur server-side ; `pilote_esg` (NTESG20) suit automatiquement toute période de sa société. **Critère d'acceptation** : figer une période produit une entrée visible dans le fil d'activité du record depuis l'écran générique existant, tests. Files: `apps/esg/models.py`, `apps/esg/services.py`, tests. (ROUTINE) «model: sonnet»
- [ ] NTESG31 — **Notification de publication de rapport** : `notifications.notify()` envoyée à `pilote_esg` + tout utilisateur avec permission `esg.view` de la société (NTESG24) au moment où une période passe en statut `publiee`, avec lien direct vers le cockpit/l'export. Best-effort, une seule notification par transition de statut (jamais à chaque relecture). **Critère d'acceptation** : republier deux fois de suite sans changement de statut ne renvoie pas de second lot de notifications, tests. Files: `apps/esg/services.py`, tests. (ROUTINE) «model: haiku»
- [ ] NTESG32 — **KPI ESG dans le module reporting** : ajout de 3 `Kpi`/tuiles au catalogue `reporting` existant (pattern `reporting.Kpi`/`DashboardConfig`, jamais un nouveau moteur de KPI) : « Couverture catalogue ESG » (% NTESG3), « Écart trajectoire moyen » (moyenne des écarts NTESG7 sur les objectifs actifs), « Intensité carbone (tCO2e/MAD CA) » (NTESG9) — chacun `disponible=false` proprement si la société n'a pas de période figée, jamais un 0 par défaut. Consommable sur un `Dashboard` générique au même titre que les KPI des autres modules. **Critère d'acceptation** : les 3 KPI apparaissent dans le sélecteur de widgets du dashboard générique et rendent une valeur cohérente avec le cockpit NTESG6 pour la même période, tests. Files: `apps/reporting/models.py` (Kpi TextChoices, additif), `apps/esg/selectors.py`, tests. (ROUTINE) «model: sonnet»
- [ ] NTESG33 — **Rapport imprimable — fiche de synthèse fournisseur RSE** : si NTESG8 est construit (score RSE fournisseur), un export PDF simple par fournisseur (WeasyPrint, pattern `qhse` PDF existant, jamais `/proposal`) : identité fournisseur, score RSE consolidé + historique des campagnes de questionnaire, sans aucune donnée d'achat/prix (`stock.ContratPrixFournisseur` jamais référencé). Utile pour un dossier d'audit fournisseur en revue annuelle. Si NTESG8 est bloqué, cette tâche l'est aussi. **Critère d'acceptation** : le PDF omet la section historique si aucune campagne n'a encore été envoyée à ce fournisseur, tests. Files: `apps/esg/pdf.py`, tests. (ROUTINE) «model: haiku»
- [ ] NTESG34 — **Réglage « pilier obligatoire » par société pour la clôture** : extension de `ParametresESG` (NTESG20) : liste des piliers E/S/G que la société juge non-négociables pour publier un rapport externe (ex. un grand groupe industriel veut toujours au moins un indicateur Social renseigné) ; le wizard de clôture (NTESG18) affiche un avertissement bloquant SEULEMENT sur la PUBLICATION (jamais sur le simple figeage interne) si un pilier marqué obligatoire est totalement vide. Reste contournable par un utilisateur avec `esg.publier_rapport` (avertissement, pas un verrou dur — décision founder si un verrou dur est un jour souhaité). **Critère d'acceptation** : publier avec un pilier obligatoire vide affiche l'avertissement mais n'empêche jamais techniquement l'action, tests. Files: `apps/esg/models.py` (+migration), `frontend/src/pages/esg/WizardClotureEsg.jsx`, tests. (ROUTINE) «model: sonnet» (@after: NTESG32)

---

**Notes de vérification** : le socle QHSE39/40/XQHS20-21 (`BilanCarbone`, `LigneBilanCarbone`, `IndicateurESG`,
`ReleveConsommation`, `generer_lignes_bilan`) est déjà marqué `[x]` dans `docs/PLAN.md` et testé
(`apps/qhse/tests/test_bilan_carbone.py`, `test_indicateur_esg.py`) — vérifié en lisant le code
directement, le digest_open fourni ne le mentionnait pas (digest gelé au 2026-06-29, le repo a avancé
depuis). Ce groupe NTESG ne duplique donc AUCUN de ces modèles : il construit exclusivement la couche
consolidation/reporting/objectifs/fournisseurs qui reste absente. `apps/rh` n'a pas de champ
genre/parité aujourd'hui — un indicateur de parité resterait `disponible=false` jusqu'à ce qu'un champ
soit ajouté côté RH (hors périmètre de ce groupe, à signaler si un futur lane RH veut le construire).
NTGRC22/23 (moteur de questionnaires générique) n'existe pas encore dans le repo au moment de cet audit
— NTESG8/17 sont conçues pour se bloquer proprement plutôt que dupliquer si elles arrivent en premier.
14 tâches P1 (bloquants vente), 6 P2, 3 P3 = 17 tâches livrées sur un total honnête : le domaine est
étroit maintenant que le socle de données existe déjà — je n'ai pas gonflé artificiellement pour
atteindre 55-80, la plupart des besoins "ESG" génériques (carbone, indicateurs E/S/G, déchets, conformité
environnementale, coût non-qualité) sont déjà couverts par QHSE39/40/XQHS20-22 et ne devaient pas être
re-proposés.


