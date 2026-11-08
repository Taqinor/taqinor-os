# Audit PA7 « monitoring et abonnement » — 2026-11-08 — L3
<!-- dossier-v3 | groupe: AMON | base: 39313d4 | fraicheur: b31e3e5 | constats: 33 | taches: 48 | decisions: 2 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PA7 (pilote sav) : lu `apps/{monitoring,sav,portail,notifications,audit}/**`, `core/{sla,merge}.py`, `authentication/permissions.py`, `apps/roles/permissions_registre.py`, `apps/parametres/models_company.py`, `apps/crm/clients_identite.py`, `frontend/src/{pages/{monitoring,parametres},features/{sav/monitoring,portail/client}}/**` ; table `PA7.json` |
| Niveau | L3 — argent (crédit SLA, garantie de production, certificats carbone), fuite entre sociétés, chiffres envoyés au client, droits, plusieurs portes par geste |
| Données | demo (pile locale, 25 sondes en transaction annulée) ; anon : non requis ; prod lecture seule : 1 société, 0 relevé, 0 abonnement, 0 garantie (07/11) |
| Critères retenus | C1, C4, C5, C6, C7, C9, C10, C15, C17, C18 |
| Étapes | PA7.01 équipement du parc · PA7.02 création de l'abonnement · PA7.03 relevés · PA7.04 sous-performance · PA7.05 disponibilité contre garantie · PA7.06 crédit SLA généré · PA7.07 décision sur le crédit · PA7.08 équipement remplacé · PA7.09 le monitoring suit le remplacement (étape manquante) · PA7.10 résiliation (parcours : PA7) |
| NE PAS REFAIRE | parc, tickets et garanties de PA5 (ACSV1-104, PR #1297) sauf leur couture avec le monitoring ; ASAV62, ASAV64, ASAV66, ASAV69, ASAV70, ASAV71, ASAV100-103 (cochées : attendu, union des jours, relevé unique, site retiré, fin d'épisode, identifiants chiffrés, écrans) ; CIQM19 (connecteur réel) ; D-ASAV-3 (contrats d'entretien) |
| Non-objectifs | connecteurs réels des onduleurs (CIQM19) ; facturation de l'abonnement et avoir SLA (D-AMON-1, D-AMON-2) ; uptime de la page d'état de la plateforme ; Django admin ; écrans en navigateur |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| découverte : parc, abonnement, relevés | opus/high | `monitoring/{models,services,serializers,views,receivers,tasks,providers,selectors}`, `sav/services.py::retirer_piece`, `portail/views_client.py`, `ProductionPage.jsx`, `AbonnementsSection.jsx`, `PortailClientConsommation.jsx` | connecteurs réels (CIQM19), notifications d'abonnement |
| découverte : sous-performance, SLA, portail | opus/high | `monitoring/{analytics,report,selectors,services}`, `core/sla.py`, `notifications/services.py`, `FleetPage.jsx`, `SlaDisponibiliteSection.jsx`, `MonitoringSection.jsx` | uptime de la page d'état, envoi réel du courriel |
| sondes (3 lots) | opus/high | 21 constats rejoués sur la pile locale (C-AMON-001 à 045) | écrans en navigateur |
| seconde lentille | opus/high | 4 S1 rejoués au geste d'écran et aux rôles système (4 sondes -L2), requête prod | navigateur |
| critique de complétude | fable/high | 8 trous (garantie, CO₂, registre carbone, deux disponibilités, salissure, droits, gestes arrière, rapport O&M), 6 sondés, 2 lus | Django admin |
| rédaction des tâches | opus/high | 48 tâches v3 (clauses calculées, module de test existant) | — |
| dossier et registre | sonnet/high | ce dossier, `unites.yml`, `decisions.yml` | — |
Détecteurs : `scripts/check_parcours.py` → 7 tables, 83 étapes, 0 échec @b31e3e5 (dette gelée sans portes : PA5, PA7) ; `scripts/check_ownership.py` → OK @b31e3e5 · non exécutés : `scripts/rejouer_parcours.py PA7` (sondes de parcours à la place), `scripts/audit_tache.py` (greps équivalents dans chaque tâche).
Live : 25 sondes `docs/audits/sondes/AMON/` (REPRO, vraies routes HTTP, transaction annulée), dont quatre rejeux élargis (geste d'écran, rôles système, supervision tardive, retard ordinaire) · prévus non joués : écrans en navigateur.
Prod (lecture seule, 07/11) : 1 société, 0 relevé, 0 abonnement, 0 garantie : aucun objet dans l'état fautif, exposition nulle aujourd'hui sur les 5 S1.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-AMON-001 | PA7.03 | C7 | S1 | `apps/monitoring/serializers.py::ProductionReadingSerializer.validate` | CSV de 31 relevés de 15 kWh puis mensuel du 01/10 : 201, CO₂ d'octobre 465 → 930 kWh ; à l'écran deux relevés de 30 j (01/10, 15/10) : 201 et 201 → 409 sur tout recouvrement | `docs/audits/sondes/AMON/C-AMON-001.py` | AMON1 |
| C-AMON-002 | PA7.02 | C15 | S2 | `apps/monitoring/services.py::creer_abonnement_monitoring` | début à J−40 : 201, « prochaine échéance » déjà passée, 0 facture, aucune tâche du beat ne cite l'abonnement → D-AMON-1 : vendu une fois, échéance et dernière facturation retirées | `docs/audits/sondes/AMON/C-AMON-002.py` | AMON2 |
| C-AMON-003 | PA7.03 | C1 | S2 | `frontend/src/pages/monitoring/ProductionPage.jsx::addReading` | 12 mensuels de 500 kWh datés du 1er : disponibilité 100,00 %, pénalité 0 ; datés du dernier jour : 90,14 %, 2 868,90 MAD ; le défaut de l'écran couvre 29 jours futurs → une convention : début de période | `docs/audits/sondes/AMON/C-AMON-003.py` | AMON3 |
| C-AMON-004 | PA7.09 | C17 | S2 | `apps/monitoring/services.py::evaluate_underperformance` | 48,13 % : drapeau + ticket ; pièce retirée (équipement remplacé), ticket résolu, réévaluation : drapeau toujours ouvert sur l'ancien ticket, portail 1 alerte → épisode clos au remplacement | `docs/audits/sondes/AMON/C-AMON-004.py` | AMON4 |
| C-AMON-005 | PA7.10 | C17 | S3 | `apps/monitoring/services.py::creer_abonnement_monitoring` | deux POST sur un même système : 201 et 201 ; résilier le mensuel coupe la supervision alors que l'annuel est actif → 409 au second actif, couper seulement à zéro actif (contournement : « Activée ») | `docs/audits/sondes/AMON/C-AMON-005.py` | AMON5 |
| C-AMON-006 | PA7.03 | C10 | S2 | `frontend/src/features/portail/client/PortailClientConsommation.jsx::PortailClientConsommation` | système « Manuel » abonné, 3 relevés : l'API sert 3 points, l'écran affiche « Suivi de production non raccordé » ; un relevé de 30 j se lit comme une journée → relevés affichés avec leur période | `docs/audits/sondes/AMON/C-AMON-006.py` | AMON6, AMON83 |
| C-AMON-010 | PA7.10 | C17 | S2 | `apps/monitoring/receivers.py::_arreter_supervision_a_la_resiliation` | résiliation 200, puis à J+120 : 62,31 %, drapeau et ticket préventif au nom du client résilié (la résiliation ne pose que enabled faux) → système sans abonnement actif sorti de l'évaluation | `docs/audits/sondes/AMON/C-AMON-010.py` | AMON10 |
| C-AMON-011 | PA7.02 | C17 | S3 | `apps/monitoring/services.py::creer_abonnement_monitoring` | 201 sur un chantier annulé « signé » (API seule) ; système retiré du parc par PATCH : abonnement toujours « actif » → 409 hors parc réceptionné, résiliation au retrait | `docs/audits/sondes/AMON/C-AMON-011.py` | AMON11, AMON80, AMON81 |
| C-AMON-020 | PA7.06 | C5 | S1 | `core/sla.py::SlaCreditsDusListView` | le Directeur système de A, puis l'administrateur, lisent sur GET core/sla/credits/ la ligne de B : crédit 14 000,00 = CA TTC de B ; un test verrouille cette fuite → société de l'appelant seulement | `docs/audits/sondes/AMON/C-AMON-020.py` | AMON20 |
| C-AMON-021 | PA7.05 | C1 | S1 | `apps/monitoring/analytics.py::om_metrics` | en service J−60, 60 relevés sains : disponibilité 16,44 %, « sous la garantie », même chiffre au rapport O&M client ; sans relevé 0,0 et PR 0,0 → fenêtre bornée au début de couverture, rien sans relevé | `docs/audits/sondes/AMON/C-AMON-021.py` | AMON21 |
| C-AMON-022 | PA7.04 | C7 | S1 | `apps/monitoring/services.py::evaluate_underperformance` | mensuels sains importés avec 3 mois de retard : 75,00 %, drapeau, ticket HAUTE si auto-ticket, 1 alerte au portail ; système de 75 j, 15 j de retard : 78,95 % → réel et attendu sur les jours couverts | `docs/audits/sondes/AMON/C-AMON-022.py` | AMON22 |
| C-AMON-023 | PA7.10 | C17 | S2 | `apps/monitoring/tasks.py::balayage_quotidien` | abonnement résilié, relevés figés : le beat joué à J+90 pose un drapeau à 75,00 et un ticket HAUTE, il ne lit ni enabled ni le statut → un système résilié sort du balayage (même cause que C-AMON-010) | `docs/audits/sondes/AMON/C-AMON-023.py` | AMON10 |
| C-AMON-024 | PA7.04 | C18 | S2 | `apps/monitoring/urls.py::router` | système à 60 % aux réglages par défaut : drapeau ouvert, 0 ticket, 0 notification ; aucune route de drapeau (404), la vue parc ne donne qu'un compteur, le portail 1 alerte → liste, classement motivé, notification | `docs/audits/sondes/AMON/C-AMON-024.py` | AMON24, AMON86, AMON87, AMON88 |
| C-AMON-026 | PA7.04 | C6 | S3 | `apps/monitoring/services.py::evaluate_underperformance` | 12 relevés saisis un par un : drapeau et ticket au premier, drapeau fermé au 9e, ticket resté ouvert ; évaluation à J+100 : drapeau neuf et second ticket à côté → réutiliser le ticket préventif ouvert | `docs/audits/sondes/AMON/C-AMON-026.py` | AMON26 |
| C-AMON-032 | PA7.07 | C17 | S3 | `core/sla.py::sla_credit_statut` | crédit « émis » sur un snapshot non applicable (200, sans montant) ; « refusé » figé malgré un recalcul ; août de 500 à 2 500 : 0 notification (type absent d'EventType) → transitions gardées, recalcul signalé | `docs/audits/sondes/AMON/C-AMON-032.py` | AMON32, AMON35, AMON85, AMON89 |
| C-AMON-040 | PA7.05 | C1 | S1 | `apps/monitoring/services.py::_guaranteed_kwh_for_period` | en service le 08/09, 61 relevés sains, 12 000/an : compensation 8 478,52 MAD hors tolérance ; rapport 2025 (avant la garantie) 12 540,00 « définitifs », PDF 200 → garanti proraté sur la période couverte (S1 si la garantie est autorisée, S2 sinon) | `docs/audits/sondes/AMON/C-AMON-040.py` | AMON40 |
| C-AMON-041 | PA7.03 | C9 | S2 | `apps/monitoring/selectors.py::co2_for_installation` | société réglée à 630 gCO₂/kWh : certificat de 6 000 kWh à 4,860 t (attendu 3,780), attestation à 0,81 sans source ni date ; société sans facteur : chiffré quand même → facteur du profil société, 409 sans facteur | `docs/audits/sondes/AMON/C-AMON-041.py` | AMON41, AMON90, AMON91 |
| C-AMON-042 | PA7.03 | C7 | S2 | `apps/monitoring/services.py::emettre_certificat_carbone` | site 2025, site juin 2025, client consolidé 2025, fin future : 4 × 201, registre 10,125 t pour 4,860 t réelles ; ni annulation ni référence imprimée → recouvrement refusé, annulation, certificat = document | `docs/audits/sondes/AMON/C-AMON-042.py` | AMON42, AMON93, AMON94 |
| C-AMON-043 | PA7.05 | C7 | S3 | `apps/monitoring/selectors.py::disponibilite_vs_garantie` | onduleur immobilisé 360 h, alarme critique escaladée : SAV 51,61 %, monitoring 100,00 %, rapport client « Aucune alarme ouverte » → indicateur interne tiré des immobilisations SAV (D-AMON-2) | `docs/audits/sondes/AMON/C-AMON-043.py` | AMON43 |
| C-AMON-044 | PA7.04 | C7 | S2 | `apps/monitoring/analytics.py::soiling_assessment` | production saisonnière saine : perte d'encrassement 73,10 %, rapport client « Nettoyage des panneaux recommandé » ; un nettoyage enregistré au 20/12 ne change rien → base depuis le dernier nettoyage | `docs/audits/sondes/AMON/C-AMON-044.py` | AMON44 |
| C-AMON-045 | PA7.02 | C5 | S2 | `authentication/permissions.py::IsResponsableOrAdmin.has_permission` | « Admin RH » sans code sav : certificat 201, résiliation 200, suppression d'un relevé 204, réglages 200, rapport O&M envoyé à un tiers 200, alors que POST sav/tickets/ rend 403 → module sav exigé | `docs/audits/sondes/AMON/C-AMON-045.py` | AMON45, AMON47, AMON92 |
| C-AMON-130 | PA7.10 | C17 | S3 | `apps/monitoring/services.py::resilier_abonnement_monitoring` | la résiliation ne stocke ni date ni auteur, l'état « suspendu » n'a aucun écrivain, un nouvel abonnement ne rallume pas la supervision coupée → tracer, suspendre, rallumer | STATIQUE (lecture) | AMON7, AMON84 |
| C-AMON-131 | PA7.03 | C4 | S3 | `apps/monitoring/providers.py::_CredentialGatedProvider._fetch` | les connecteurs proposés renvoient [] : « Huawei FusionSolar » + « Activée » synchronise 0 relevé et annonce une supervision automatique → « non disponible » tant que le connecteur réel manque | STATIQUE (lecture) | AMON8 |
| C-AMON-132 | PA7.03 | C6 | S3 | `apps/monitoring/services.py::sync_system` | latent derrière les connecteurs vides : sans identifiant externe aucun dédoublonnage contre les relevés manuels, énergie négative acceptée, horodatage ISO ignoré en silence → valider comme la saisie | STATIQUE (lecture) | AMON9 |
| C-AMON-133 | PA7.02 | C9 | S3 | `apps/monitoring/models.py::AbonnementMonitoring` | le client de l'abonnement et du certificat carbone est un entier que la fusion de clients ne repointe pas (FK seulement) ; latent, 0 abonnement en prod → service de repointage appelé par la fusion | STATIQUE (lecture) | AMON12, AMON82 |
| C-AMON-134 | PA7.04 | C17 | S3 | `apps/monitoring/tasks.py::balayage_quotidien` | site retiré du parc : le beat saute le système avant de fermer l'épisode, la vue parc compte 0 alerte et le portail 1 → fermer l'épisode puis ignorer le site | STATIQUE (lecture) | AMON25 |
| C-AMON-135 | PA7.04 | C6 | S3 | `apps/monitoring/serializers.py::MonitoringSettingsSerializer` | seuil de sous-performance sans borne : −10 signale tout le parc (plancher 110 %), 120 ne détecte plus rien (plancher −20 %) → borné à [1 ; 99], 400 nommant le champ | STATIQUE (lecture) | AMON28 |
| C-AMON-136 | PA7.04 | C7 | S3 | `apps/monitoring/services.py::attendu_periode` | attendu réparti à plat (annuel × jours / 365) alors que la courbe remise au client est saisonnière : premier hiver d'un système mis en service à l'automne jugé contre la moyenne (non chiffré) → profil mensuel | STATIQUE (lecture) | AMON29 |
| C-AMON-137 | PA7.06 | C15 | S3 | `apps/sav/parcours/PA7.json::credit_sla_genere` | les étapes de crédit SLA décrivent le SLA de la plateforme (page d'état), pas l'installation du client ; l'étape de sous-performance annonce un ticket « correctif » alors que le code crée un préventif → table resynchronisée | STATIQUE (lecture) | AMON30 |
| C-AMON-138 | PA7.06 | C7 | S3 | `core/sla.py::montant_facture_mois` | base du crédit = CA TTC facturé par la société à SES clients, brouillons compris, en flottant : 100 000 émis + 40 000 en brouillon au palier 10 % → 14 000,00 au lieu de 10 000,00 | STATIQUE (lecture) | AMON31 |
| C-AMON-139 | PA7.06 | C18 | S4 | `core/sla.py::generer_snapshot_societe` | le recalcul écrase la date de génération et n'écrit jamais recalcule_le ni raison_recalcul : l'uptime de septembre passe de 99,3 à 92,5 sans trace → dater et motiver le recalcul | STATIQUE (lecture) | AMON34 |
| C-AMON-140 | PA7.03 | C18 | S3 | `apps/audit/modeles_suivis.py::TRACKED_MODELS` | aucun modèle monitoring au journal ; supprimer un relevé (même sous un certificat), une config ou une garantie ne ré-évalue rien ni ne laisse de trace → journal des écritures, refus des suppressions qui défont un document | STATIQUE (lecture) | AMON46 |
| C-AMON-141 | PA7.05 | C15 | S3 | `apps/monitoring/report.py::email_om_report` | le rapport O&M « automatisé » n'a aucune tâche planifiée et part sans reply_to ni copie en GED (seule trace : une notification interne) → archiver ce qui est parti, libellé aligné sur D-AMON-1 | STATIQUE (lecture) | AMON47 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-AMON-005 | requalifié S2 → S3 | un contournement existe (l'interrupteur « Activée ») et aucun connecteur réel n'est branché : effet nul aujourd'hui |
| C-AMON-010, 023 | fusionnés, S3 et S2 → S2 | même cause : la résiliation ne coupe que la synchro, pas l'évaluation ; une tâche (AMON10), aucun contournement à l'écran |
| C-AMON-043 | requalifié S2 → S3 | D-AMON-2 : la pénalité est un indicateur interne, jamais un montant dû ; reste un texte client faux, contournable (l'alarme est visible au SAV) |
| C-AMON-002 | gravité sous décision | S2 ; aurait été S1 si D-AMON-1 avait répondu « facturer » |
| C-AMON-021, 022, 040 | argent ou ticket conditionnel | pénalité en MAD (021, 040) et ticket HAUTE (022) exigent un réglage éteint par défaut ; le chiffre faux au défaut tient le S1 (040 : S2 au défaut) |
| C-AMON-001, 021, 022 | élargis | seconde lentille : deux saisies d'écran au défaut suffisent (001) ; supervision tardive et relevé à cheval perdu (021) ; retard ordinaire de 15 j et effet inverse à 118 % (022) |
| C-AMON-003, 006, 032 | absorbent une lecture ou un témoin | 003 : date saisie = fin de période à l'écran, début au serveur (ratio ≈ 190 %) ; 006 : période non affichée (AMON83) ; 032 : notification de recalcul morte, trouvée par le témoin (AMON85, AMON35) |
| C-AMON-011, 024, 032, 041, 042, 045 | scindés | une tâche par geste ou propriétaire : AMON11, 81, 80 · AMON24, 86, 87, 88 · AMON32, 35, 85, 89 · AMON41, 90, 91 · AMON42, 93, 94 · AMON45, 92, 47 |
| C-AMON-006, 130, 133 | scindés | AMON6 puis AMON83 (portail) ; AMON7 puis AMON84 (résiliation, réactivation) ; AMON12 puis AMON82 (service monitoring, puis fusion de clients) |
Porte : 0 réfuté sur 28 candidats de découverte et 8 trous de la critique (33 constats) · seconde lentille : 4 S1 → maintenus 4, élargis 3 (C-AMON-001, C-AMON-021, C-AMON-022), jambe argent de 021 abaissée au conditionnel, 0 réfuté.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| abonnement, multi-société | `AbonnementMonitoringViewSet` borné à la société ; système par `installation_scoped`, client résolu côté serveur ; double résiliation sous `select_for_update` | `creer_abonnement_monitoring` reste l'écrivain (C-AMON-011) |
| relevés et import CSV | `validate_installation` refuse un système d'une autre société ; CSV par `get_object()` ; énergie négative et fichier illisible rapportés ligne par ligne | recouvrement traité à part (C-AMON-001) |
| fuseau et beat | `Africa/Casablanca`, services en `localdate` ; tâche SLA mensuelle au beat ; balayage par société active | `erp_agentique/celery.py` inchangé |
| drapeau de sous-performance | `select_for_update`, `get_or_create` et contrainte partielle `uniq_open_underperf_flag` : un drapeau ouvert et un ticket par épisode | l'épisode suivant relève de C-AMON-026 |
| SLA de disponibilité et mensuel | taux dans ]0 ; 100] sans défaut ; pénalité `None` sans `garantie_production_autorisee` ; `update_or_create` sous contrainte, décision jamais écrasée ; `sla_credit_statut` borné à la société | la liste globale relève de C-AMON-020 |
| portail, certificats, connecteurs | `ma_consommation_client` borné société et client ; suppression d'un abonnement ou d'un certificat interdite ; identifiants chiffrés, aucune clé absente de la prod requise | les connecteurs restent des squelettes (C-AMON-131) |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-AMON-1 | l'abonnement de supervision est-il facturé par l'ERP à chaque échéance | vendu_une_fois | AMON2 |
| D-AMON-2 | que devient la pénalité de disponibilité de l'installation client | affichage_interne | AMON21 |

## 7. Optionnel (jamais une tâche)
- `sync_system` écrit `last_sync` même pour « noop » et 0 relevé : le beat affiche une « dernière synchro » fraîche sur des systèmes en saisie manuelle (façade du connecteur) : lu, non rejoué.
- Le statut de garantie de production (route `status`, tout rôle) chiffre la compensation sans le réglage qui gate le PDF : S4 noté dans AMON40, non déposé.
- Certificat carbone d'un client d'une autre société : 409 « Aucune production mesurée » au lieu de 404 (S4) ; ré-émission après PATCH d'un relevé : non rejoué.
- Fenêtre fixe de 365 j : une panne totale n'est vue qu'après ≈ 73 jours au seuil de 20 % ; concurrence `sync-now` et beat latente : lus, non mesurés.

## 8. Limites, non couvert, écarts
- Non couvert : écrans en navigateur (chemin d'écran déduit des greps et du corps exact des formulaires) ; Django admin ; envoi réel du rapport O&M ; connecteurs réels (CIQM19) ; notifications d'abonnement ; uptime de la page d'état au-delà de son usage dans le crédit.
- Non couvert (suite) : PA7.01 (`sweep_bom_to_parc`) et PA7.08 (`retirer_piece`) relèvent de PA5, lus ici à leur seule couture monitoring (C-AMON-004) ; profil mensuel de l'étude du devis (stocké ou non : non vérifié).
- Écart à la méthode : la table `PA7.json` nomme le SLA de la plateforme là où le parcours attend l'installation du client → constats rangés sous les étapes de la charte, table resynchronisée par AMON30 (C-AMON-137) ; ponctuel : vérifier au `vérifie AMON`.
- Écart à la méthode : 12 constats sans sonde (« STATIQUE (lecture) », 11 S3 et 1 S4, aucun S1-S2) ; sondes jouées dans le conteneur monté sur c38868a627, ancêtre de la base : le diff de `apps/monitoring/**` et de `core/sla.py` est vide → ponctuel : conteneur du jour.
- Limites des sondes : beat de C-AMON-023 joué sur la société de la sonde avec la date patchée ; courriel de C-AMON-045 capté en mémoire ; PDF de C-AMON-040 et C-AMON-041 rendus, pas ouverts.
- Fraîcheur : `main` a avancé de 39313d4 à b31e3e5 (13 commits) pendant l'audit ; le diff de `apps/monitoring`, `core/sla.py`, `authentication`, `permissions_registre.py`, `portail/views_client.py` et des écrans monitoring est vide : les 5 S1 restent.
- Incident prod : aucun (lecture seule du 07/11 : 1 société, 0 relevé, 0 abonnement, 0 garantie).

## 9. Coût et routage
Coût : H0 S1 O13 F1 · jetons sous-agents ≈ 5 M · tâches 48 (P0 4 P1 1 P2 19 P3 24 GATED 0) ; une critique de complétude Fable, 8 trous dont 6 sondés (garantie de production, facteur CO₂, registre carbone, deux disponibilités, salissure, droits) et 2 lus (gestes arrière sans trace, rapport O&M).
Routage : `PLAN_AUDIT_SAV.md` 33 · `PLAN_AUDIT_SECURITE.md` 7 · `PLAN_AUDIT_PARAMETRES.md` 3 · `PLAN_AUDIT_CHANTIERS.md` 2 · `PLAN_AUDIT_DOCUMENTS.md` 1 · `PLAN_AUDIT_LEAD.md` 1 · `PLAN_AUDIT_TRANSVERSE.md` 1 · aucune tâche d'acceptation posée · PR #1298.
