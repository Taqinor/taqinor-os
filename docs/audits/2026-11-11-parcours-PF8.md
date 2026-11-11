# Audit PF8 « messages envoyés aux clients » — 2026-11-11 — L2
<!-- dossier-v3 | groupe: AMSG | base: 63b1e02 | fraicheur: 3acfee4 | constats: 43 | taches: 64 | decisions: 6 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF8 : tout ce que l'ERP envoie ou prépare pour l'extérieur (e-mail, WhatsApp pré-rempli, relance, rappel, notification, lien, accusé, conversion Meta) ; lu `backend/django_core/apps/**`, `backend/django_core/core/**`, `backend/django_core/erp_agentique/celery.py`, `backend/fastapi_ia/**`, `frontend/src/**` ; aucune table `PF8.json` |
| Niveau | L2 — loi 09-08 (opposition, effacement) et argent (relances), mais e-mail éteint en production ; 4 surfaces indépendantes |
| Données | aucune démo (aucune pile ne servait `main`) ; anon : non requis ; prod : lue le 11/11 en lecture seule, comptages seulement (§2) |
| Critères retenus | C1, C3, C5, C6, C8, C10, C13, C17, C18 |
| Étapes | PF8.1 suivi commercial · PF8.2 envois manuels, opposition, effacement · PF8.3 documents et argent · PF8.4 moteur d'envoi et tâches planifiées · PF8.5 terrain et après-vente · PF8.6 trous de la critique (parcours : PF8) |
| NE PAS REFAIRE | groupes ADRG, ALEC, APUB, ATST ; ADEP31, ADEP34 et D-ADEP-2 (e-mail non opérationnel dit) ; APUB49 (lien de désabonnement), APUB10, APUB39, APUB6, APUB7, APUB35, APUB36, ALEC37, ACVI46 ; APFS103, ADRG76 |
| Non-objectifs | envoi réel ; webhooks sortants et extraits planifiés (pas des messages client) ; factures, relances, chantier, SAV et portail vers un client opposé (contractuels, D-ACVI-10) ; chat public (parqué) |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| suivi commercial | opus | 16 points d'envoi (cadence, Relances du jour, notifications, assistant) + 17 familles de notifications internes | liens nus de la fiche (non relus ligne à ligne) |
| envois manuels, opposition, effacement | opus | 31 points (WhatsApp, e-mail, liens, STOP, effacement, anonymisation, accusé Meta) | portails fournisseur et partenaire |
| documents et argent | opus | 34 points + 3 internes (devis, factures, relances, relevés, quittances, signature, bons fournisseur) | `useEnvoiDevis.js`, `ClientDetailPanel.jsx` |
| moteur d'envoi, terrain, après-vente | opus | 34 points ; 124 tâches planifiées ; automatisations ; notifications ; chantier, livraison, SAV, portail | rattrapage d'un beat manqué au redémarrage |
| vérificateurs frais (5) | opus | un par lecture + un sur les trous de la critique ; fonctions réelles extraites et rejouées avec bouchons | — |
| critique de complétude | opus | 6 points absents des quatre lectures (webhooks, extraits, liens d'intervention, accord image, site public, Relances du jour) | apps `gestion_projet`, `contrats`, `datarooms`, `kb` |
| sondes, rédaction, édition | opus | 12 sondes hôte ; 64 tâches v3 (3 rédacteurs, 1 éditeur) | — |
Détecteurs : aucun détecteur du dépôt exécuté ; inventaires par lecture et scripts hors dépôt @63b1e02 · non exécutés : tests Django (aucune pile).
Live : aucun scénario joué · prévus non joués : le rejeu par l'API des tâches P1 (AMSG83) · sondes : 12 sondes hôte jouées le 11/11 sur 3acfee4 (vrai code, bouchons, sans Django), toutes `repro: True`.
Prod (lue le 11/11, lecture seule) : e-mail en backend console (rien ne part) ; 1 171 leads dont 84 opposés ; 2 numéros portés par une fiche opposée et une non opposée ; 0 règle d'automatisation ;
Prod (suite) : 19 journaux d'e-mail (10 « envoyé », 9 « échec ») ; 12 relances sur 4 factures en retard (3 niveaux consommés) ; 5 clients et 2 fournisseurs du jeu de démo ; assistant allumé, 0 action ; 0 demande de signature ; 36 devis envoyés dont 2 à des leads opposés.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-AMSG-001 | PF8.2 | C8 | S2 | `backend/django_core/apps/crm/leads_views.py::LeadIntakeActionsMixin.questionnaire_lien` | « Envoyer un questionnaire » prépare un WhatsApp pré-rempli vers un lead opposé, perdu ou archivé (rend 200 et le lien) → refus 409 nommé (D-ACVI-7) · réel aujourd'hui · prod : 84 leads opposés | `docs/audits/sondes/AMSG/C-AMSG-001.py` | AMSG1, AMSG83 |
| C-AMSG-002 | PF8.1 | C8 | S2 | `backend/django_core/apps/ventes/selectors_cadence.py::devis_action_requise` | « Relances du jour » sert brouillon WhatsApp et numéros pour le devis d'un lead opposé, perdu ou archivé → ni brouillon ni numéro · réel aujourd'hui · prod : 2 devis envoyés à des opposés | `docs/audits/sondes/AMSG/C-AMSG-002.py` | AMSG2 |
| C-AMSG-003 | PF8.2 | C8 | S2 | `backend/django_core/apps/crm/models.py::Lead.save` | un STOP laisse contactable une autre fiche déjà existante au même numéro → opposition propagée (D-AMSG-2) · réel aujourd'hui · prod : 2 numéros sur une fiche opposée et une non opposée | `docs/audits/sondes/AMSG/C-AMSG-003.py` | AMSG3 |
| C-AMSG-004 | PF8.2 | C8 | S2 | `backend/django_core/apps/crm/clients_views.py::ClientViewSet.anonymize` | « Anonymiser » efface le client mais laisse ses leads contactables (nom, téléphone, relances) → leads liés anonymisés · réel aujourd'hui · prod : non lu | `docs/audits/sondes/AMSG/C-AMSG-004.py` | AMSG4 |
| C-AMSG-005 | PF8.2 | C8 | S2 | `backend/django_core/apps/crm/dsr_provider.py::_matcher` | un effacement demandé par e-mail manque la fiche sœur au seul téléphone, qui reste relancée → recherche par ses autres coordonnées · réel aujourd'hui | `docs/audits/sondes/AMSG/C-AMSG-005.py` | AMSG5 |
| C-AMSG-006 | PF8.3 | C8 | S2 | `backend/django_core/apps/facturation/views/facture_documents.py::FactureDocumentsActionsMixin.whatsapp` | « Relancer par WhatsApp » offert et servi pour une facture contestée → 409, entrée retirée (D-AFAC-89) · réel aujourd'hui · prod : 6 en retard | `docs/audits/sondes/AMSG/C-AMSG-006.py` | AMSG27 |
| C-AMSG-007 | PF8.1 | C10 | S2 | `backend/django_core/apps/crm/agent_actions.py::PREPARER_ENVOI_WHATSAPP` | l'assistant « prépare le WhatsApp du devis » : devis passé « envoyé », relances posées, rien envoyé ni confirmé → aperçu sans effet · réel aujourd'hui · prod : assistant allumé | `docs/audits/sondes/AMSG/C-AMSG-007.py` | AMSG6 |
| C-AMSG-008 | PF8.4 | C18 | S2 | `backend/django_core/apps/ventes/email_service.py::_send` | e-mail éteint : chaque envoi ventes est journalisé « envoyé » et la relance consomme son niveau → « non envoyé », niveau intact · réel aujourd'hui · prod : 12 relances sur 4 factures | `docs/audits/sondes/AMSG/C-AMSG-008.py` | AMSG28, AMSG29, AMSG30 |
| C-AMSG-009 | PF8.5 | C18 | S2 | `backend/django_core/apps/installations/tasks.py::_envoyer_email_client` | rappel J-1, avis de livraison et SAV, identifiants portail dits « envoyés » sans partir, brouillon WhatsApp jeté → vérité, brouillon remis · réel aujourd'hui | `docs/audits/sondes/AMSG/C-AMSG-009.py` | AMSG56, AMSG57, AMSG58, AMSG59 |
| C-AMSG-010 | PF8.4 | C8 | S2 | `backend/django_core/authentication/management/commands/seed_demo.py::Command.handle` | le jeu de démo sème de vraies messageries, aucun envoi bridé hors production → domaines réservés, filtre de destinataires · latent : à corriger avant d'allumer l'e-mail (S1 ce jour-là) · prod : 7 fiches | `docs/audits/sondes/AMSG/C-AMSG-010.py` | AMSG60, AMSG61, AMSG62 |
| C-AMSG-011 | PF8.3 | C8 | S2 | `backend/django_core/apps/facturation/views/facture_lot.py::FactureLotActionsMixin.bulk` | « Tout sélectionner → Envoyer par email » envoie une facture annulée ou brouillon → refus de statut · latent : à corriger avant d'allumer l'e-mail · prod : 7 annulées, 2 brouillons | `docs/audits/sondes/AMSG/C-AMSG-011.py` | AMSG31 |
| C-AMSG-012 | PF8.3 | C8 | S2 | `backend/django_core/apps/ventes/scheduled.py::pre_echeance_reminders` | le rappel avant échéance (et l'automatisation) vise une facture contestée, sous promesse ou en relance manuelle → exclusions de la relance · latent : à corriger avant d'allumer l'e-mail | `docs/audits/sondes/AMSG/C-AMSG-012.py` | AMSG32, AMSG63 |
| C-AMSG-013 | PF8.3 | C3 | S3 | `backend/django_core/apps/ventes/utils/whatsapp.py::devis_recipient_phone` | WhatsApp du devis vers le client d'abord, confirmation vers le lead d'abord → une règle, lead d'abord · réel, effet non reproduit | STATIQUE | AMSG33 |
| C-AMSG-014 | PF8.2 | C5 | S3 | `backend/django_core/apps/adsengine/whatsapp_ack.py::_accuse_du` | sans société désignée, toute société envoie l'accusé depuis l'unique numéro → numéro borné · latent : clés WhatsApp absentes | STATIQUE | AMSG7 |
| C-AMSG-015 | PF8.3 | C10 | S3 | `frontend/src/api/ventesApi.js::envoyerEmailFacture` | l'écran poste `email`, le serveur lit `to_email` → même clé · latent : aucun appelant ne passe d'adresse | STATIQUE | AMSG34 |
| C-AMSG-016 | PF8.1 | C8 | S3 | `backend/django_core/apps/crm/leads_notifications.py::_build_lead_wa_reply_url` | les notifications au commercial portent un WhatsApp pré-rempli vers un opposé → aucun lien · latent : texte du corps, jamais affiché | STATIQUE | AMSG8 |
| C-AMSG-017 | PF8.1 | C8 | S3 | `backend/django_core/apps/crm/management/commands/escalader_premier_contact.py::escalader_premier_contact` | un lead né opposé déclenche l'escalade « X attend » → exclu · réel, interne | STATIQUE | AMSG9 |
| C-AMSG-018 | PF8.2 | C8 | S3 | `backend/django_core/apps/ventes/domain/envoi.py::exiger_contact_permis` | l'envoi de devis ne refuse que l'opposé : perdu ou archivé passent → règle D-ACVI-7 · réel · prod : 1 lead à motif de perte | STATIQUE | AMSG35 |
| C-AMSG-019 | PF8.6 | C8 | S3 | `backend/django_core/apps/adsengine/capi_crm.py::build_stage_event` | conversions Meta avec e-mail et téléphone hachés d'un opposé → à trancher (D-AMSG-3) · latent : porte non lue | STATIQUE | AMSG10, AMSG36 |
| C-AMSG-020 | PF8.6 | C8 | S3 | `scripts/check_garde_contact.py::analyser_source` | la garde ignore les 5 sites d'écran qui assemblent un lien pré-rempli et tolère 9 raisons « A CORRIGER » sans tâche → front balayé, dette gelée · réel | STATIQUE | AMSG64 |
| C-AMSG-021 | PF8.6 | C8 | S3 | `backend/django_core/apps/automation/actions.py::_send_email` | e-mail d'automatisation sans réponse à la société ni sortie pour un lead → les deux · latent : 0 règle | STATIQUE | AMSG65 |
| C-AMSG-022 | PF8.1 | C1 | S3 | `backend/django_core/apps/crm/visites_rdv.py::build_appointment_confirmation_whatsapp` | textes client codés en français, hors gabarit et langue du lead (RDV, relance de devis, sujet J-1) → gabarit + langue · réel | STATIQUE | AMSG11, AMSG37, AMSG66 |
| C-AMSG-023 | PF8.2 | C1 | S3 | `backend/django_core/apps/crm/views.py::LeadViewSet.resume_associe` | un texte personnalisé part avec des accolades brutes → contexte complet · latent : défaut sain | STATIQUE | AMSG12 |
| C-AMSG-024 | PF8.5 | C1 | S3 | `backend/django_core/apps/installations/tasks.py::_rendre_rappel` | sans ponctuation latine, l'omission vide tout le rappel J-1 → seule la phrase du lien omise · latent : à corriger avant d'allumer l'e-mail | STATIQUE | AMSG67 |
| C-AMSG-025 | PF8.4 | C6 | S3 | `backend/django_core/apps/automation/serializers.py::AutomationRuleSerializer.validate` | une règle « envoyer un e-mail » sans corps est acceptée et part vide → corps exigé · latent : 0 règle | STATIQUE | AMSG68 |
| C-AMSG-026 | PF8.2 | C1 | S3 | `backend/django_core/apps/crm/devis_views.py::LeadDevisActionsMixin._whatsapp_devis_message` | version remplacée, devis refusé ou expiré envoyables ; lien d'un devis expiré dans une relance → 409, lien omis · réel | STATIQUE | AMSG13, AMSG38 |
| C-AMSG-027 | PF8.1 | C1 | S3 | `backend/django_core/apps/ventes/domain/recouvrement.py::send_devis_followup_nudges` | brouillon de relance de devis au texte du vendeur, numéro non normalisé → texte client · latent : jamais cliquable | STATIQUE | AMSG39 |
| C-AMSG-028 | PF8.3 | C1 | S3 | `backend/django_core/apps/ventes/views/devis_envoi.py::_envoi_atomique` | identité globale (enveloppe « TAQINOR », PDF sur réglages globaux) → identité de la société · latent : 1 société | STATIQUE | AMSG40, AMSG41 |
| C-AMSG-029 | PF8.6 | C1 | S3 | `backend/django_core/apps/installations/livraison_client_notify.py::_livraison_lien` | liens client sur l'hôte de l'employé (ancien domaine) ou relatifs → base publique unique · latent : réglages non lus | STATIQUE | AMSG69 |
| C-AMSG-030 | PF8.3 | C1 | S3 | `backend/django_core/apps/ventes/email_service.py::send_recu_email` | « ci-joint » sans PDF (quittance, relevé, bon fournisseur) ; heure UTC → refus, heure locale · latent : à corriger avant d'allumer l'e-mail | STATIQUE | AMSG42, AMSG70, AMSG71 |
| C-AMSG-031 | PF8.1 | C1 | S3 | `backend/django_core/apps/crm/cadence_messages.py::_nom_affiche_conseiller` | message signé du prénom d'un responsable désactivé → repli actif · latent · prod : 0 cas | STATIQUE | AMSG14 |
| C-AMSG-032 | PF8.4 | C8 | S3 | `backend/django_core/apps/ventes/domain/recouvrement.py::amorcer_cadence` | 1er niveau de relance un jour non ouvré ; envois planifiés avant 08:30 et le week-end → jour ouvré ; heure : D-AMSG-1 · latent : à corriger avant d'allumer l'e-mail | STATIQUE | AMSG43, AMSG44, AMSG72, AMSG73 |
| C-AMSG-033 | PF8.3 | C17 | S3 | `backend/django_core/apps/ged/services.py::relancer_signataires_dus` | relance de signature après annulation, expiration ou refus → en attente seules · latent : 0 demande | STATIQUE | AMSG74 |
| C-AMSG-034 | PF8.4 | C17 | S3 | `backend/django_core/apps/automation/engine.py::resume_scheduled_step` | la reprise d'un envoi reporté relance une facture payée → état relu · latent : 0 règle | STATIQUE | AMSG75 |
| C-AMSG-035 | PF8.2 | C17 | S3 | `backend/django_core/apps/crm/visites_views.py::AppointmentViewSet.confirmer_whatsapp` | « je confirme notre rendez-vous » pour un RDV annulé, manqué ou passé → refus d'état · réel (API) | STATIQUE | AMSG15 |
| C-AMSG-036 | PF8.5 | C17 | S3 | `backend/django_core/apps/visites/services.py::annuler_visite` | visite annulée, rendez-vous d'agenda gardé : rappel au commercial → annulé aussi · réel, interne | STATIQUE | AMSG16 |
| C-AMSG-037 | PF8.5 | C13 | S3 | `backend/django_core/apps/installations/tasks.py::rappel_rdv_j1` | aucun marqueur « déjà envoyé » : un worker tué renvoie tout le lot → marqueur · latent : à corriger avant d'allumer l'e-mail | STATIQUE | AMSG76 |
| C-AMSG-038 | PF8.4 | C13 | S3 | `backend/django_core/apps/automation/actions.py::_for_each` | boucle + e-mail : N copies au même client, envoi de nuit → élément destinataire · latent : 0 règle | STATIQUE | AMSG77 |
| C-AMSG-039 | PF8.5 | C8 | S3 | `backend/django_core/apps/notifications/services.py::_report_hors_fenetre` | `skip_email` contourne la fenêtre : cloche et push portail la nuit → fenêtre lue · latent : réglage éteint | STATIQUE | AMSG78 |
| C-AMSG-040 | PF8.4 | C5 | S3 | `backend/django_core/apps/automation/beat_tasks.py::process_due_automation_steps` | les reprises d'une société suspendue partent → sociétés actives seules · latent : 0 règle | STATIQUE | AMSG79 |
| C-AMSG-041 | PF8.4 | C18 | S3 | `backend/django_core/apps/ventes/domain/cycle_vie.py::_send_otp_email` | succès annoncé sous le backend console (code de signature, lien de signature) ou échec avalé (rapports) → échec dit · latent : à corriger avant d'allumer l'e-mail | STATIQUE | AMSG45, AMSG80, AMSG81 |
| C-AMSG-042 | PF8.1 | C10 | S3 | `backend/django_core/apps/crm/visites_rdv.py::dispatch_appointment_reminder` | brouillon client écrit au seul journal, numéro en clair → retiré, journal sans numéro · réel | STATIQUE | AMSG17 |
| C-AMSG-043 | PF8.2 | C5 | S3 | `backend/django_core/authentication/services.py::reinitialiser_mot_de_passe` | un gérant réinitialise un mot de passe sans avertir la personne → avertie (NTSEC30) · réel, interne | STATIQUE | AMSG82 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-AMSG-026 | requalifié S2 → S3 | la page publique retire l'offre remplacée (`backend/django_core/apps/crm/devis_views.py`) |
| C-AMSG-033 | requalifié S2 → S3 | 0 demande de signature en production ; cadence posée par l'API seule |
| C-AMSG-011, 012 | requalifiés S2 réel → S2 latent | e-mail en console : rien ne part aujourd'hui (C-AMSG-008 dit le faux « envoyé ») |
| C-AMSG-010 | arbitré S2 latent | un vérificateur disait S1 latent, l'autre S3 ; devient S1 le jour où l'e-mail s'allume |
| C-AMSG-034, 027, 016 | requalifiés S2 → S3 | 0 règle d'automatisation ; brouillon et lien jamais cliquables (la cloche n'affiche pas le corps) |
| C-AMSG-006, 009 | relevés S3 → S2 réel | WhatsApp manuel seul canal de relance qui part ; « envoyé » compté sans envoi |
| C-AMSG-008 | ajouté par un vérificateur, S2 réel | faux « envoyé » sous backend console, lu en production (12 relances) |
| C-AMSG-007 | maintenu S2 | une lecture disait « l'assistant n'envoie rien » : il passe pourtant le devis « envoyé » (`backend/django_core/apps/crm/agent_actions.py`) |
| C-AMSG-001, 007, 010, 012, 016, 022, 026, 028, 029, 030, 032, 035, 041 | fusionnés | une cause par constat ; jusqu'à cinq notes brutes par constat |
Porte : 0 réfuté / 43 retenus · 11 gravités revues · seconde lentille : aucune (aucun S1).

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| injection dans les messages | corps d'e-mail échappé (`backend/django_core/core/selectors.py::wrap_email_html`) ; liens WhatsApp encodés côté serveur et écran ; retour à la ligne d'un objet refusé par Django | le rendu passe par ces fonctions |
| pièces jointes | devis et facture rendus à jour (AFAC42) ; bon fournisseur sans donnée client ; aucun prix d'achat ni marge dans un corps ou une notification | — |
| copie cachée, transfert | aucune copie cachée ni transfert automatique (recherche dans tout le code serveur) | — |
| données client vers un fournisseur | le bon de commande fournisseur ne porte ni adresse ni téléphone du client | — |
| assistant IA | rédige seulement ; règle d'automatisation IA créée éteinte ; seule exception C-AMSG-007 | le catalogue garde le risque |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-AMSG-1 | Les messages clients hors cadence partent-ils à partir de 08:30, jours ouvrés ? | ouverte | AMSG44, AMSG72, AMSG73 |
| D-AMSG-2 | Le STOP s'étend-il aux fiches déjà existantes aux mêmes coordonnées ? | ouverte | AMSG3 |
| D-AMSG-3 | Envoie-t-on à Meta les conversions d'une personne opposée ? | ouverte | AMSG10, AMSG36 |
| D-AMSG-4 | Qui peut décocher « ne plus contacter » hors demande du client ? | ouverte | — |
| D-AMSG-5 | Rend-on leur relance aux 4 factures aux niveaux consommés sans envoi ? | ouverte | AMSG30 |
| D-AMSG-6 | Neutralise-t-on les coordonnées du jeu de démo restées en production ? | ouverte | AMSG62 |

## 7. Optionnel (jamais une tâche)
- Écran d'accord image (`ConsentScreen.jsx`) : texte français codé, sans numéro — mineur.
- Liens nus WhatsApp et e-mail de la fiche : aucun message préparé, non relus ligne à ligne.

## 8. Limites, non couvert, écarts
- Non couvert : aucune pile ne servait `main` : aucun test exécuté, aucun rejeu par l'API, aucun envoi réel ; les 12 sondes sont des sondes hôte (vrai code exécuté avec des bouchons) ; la production n'a été lue qu'en comptages, lecture seule, le 11/11.
- Non vérifié : origine des 9 journaux « échec » ; nombre de factures contestées ; lead à motif de perte bien « perdu » ; poses J-1, livraisons et réglage SAV en production ; téléphones des clients de démo ; réglages `PUBLIC_BASE_URL`, `DEFAULT_FROM_EMAIL` et porte des conversions Meta ; liens de partage de `gestion_projet`, `contrats`, `datarooms`, `kb`.
- Laissés sans tâche : C-AMSG-014 (« STOP » répondu à l'accusé, latent) ; C-AMSG-018 (devis sans lead d'une personne opposée) ; C-AMSG-021 côté devis (« STOP » par e-mail) ; C-AMSG-022 (textes sans clé de gabarit : questionnaire, brouillon d'engagement, parrainage) ; C-AMSG-028 (marque en dur du gabarit d'e-mail et du chat public) ; C-AMSG-032 (jours fériés) ; C-AMSG-035 (trace au chatter).
- Corrections à l'édition : AMSG26 (moitié écran de C-AMSG-002) retirée, l'écran suit sans changement ; AMSG63 ramenée P3 ; AMSG43 et AMSG44 gardées en facturation (entrées de beat de leur propriétaire) ; AMSG2 sans ligne dans `crm/selectors.py` (refus PACT11 évité).
- Écart à la méthode : aucun.
- Incident prod : aucun envoi fautif constaté ; état réel : l'e-mail est éteint et l'ERP journalise des envois (12 relances consignées, 10 e-mails « envoyés », 4 factures aux niveaux consommés) → AMSG28, AMSG29, AMSG30 (GATED D-AMSG-5).

## 9. Coût et routage
Coût : H0 S0 O17 F0 · jetons sous-agents ≈ 5 M · tâches 64 (M0 0 M1 17 M2 0 M3 39 GATED 8).
Routage : LEAD 14 · DEVIS 9 · FACTURATION 9 · PARAMETRES 7 · DOCUMENTS 5 · CHANTIERS 4 · SECURITE 4 · TRANSVERSE 4 · ACQUISITION 2 · STOCK 2 · ANALYSE 1 · DEPLOY 1 · SAV 1 (`docs/plans/PLAN_AUDIT_<X>.md`) · acceptation AMSG83 · PR #1365.
Rapport : aucun défaut grave (S1), 12 défauts sérieux (S2), dont 9 réels aujourd'hui.
- Personnes qui ont dit STOP : l'ERP prépare encore pour elles un WhatsApp (questionnaire, Relances du jour), et un STOP ou un effacement n'atteint pas leurs autres fiches → AMSG1 à AMSG5.
- Messages dits « envoyés » alors que rien ne part (l'e-mail est éteint) : relances de facture consommées, rappels de pose, avis SAV, identifiants portail ; 4 factures ne seront plus relancées → AMSG28 à AMSG30, AMSG56 à AMSG59.
- L'assistant IA marque un devis « envoyé » sans l'envoyer → AMSG6 ; « Relancer par WhatsApp » visible sur une facture contestée → AMSG27.
- À corriger avant d'allumer l'e-mail : adresses réelles du jeu de démo, factures annulées envoyables, rappel avant échéance à un client qui conteste → AMSG31, AMSG32, AMSG60 à AMSG62.
- 31 défauts mineurs (S3). 6 questions au fondateur, toutes ouvertes.
