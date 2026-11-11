# Audit PF5 « accès publics et à lien » — 2026-11-11 — L2
<!-- dossier-v3 | groupe: APUB | base: ae5a7ae | fraicheur: 1ea772d | constats: 38 | taches: 48 | decisions: 5 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF5 : tout ce qui s'ouvre sans compte interne. 91 vues `AllowAny` relevées par `backend/django_core/core/public_endpoint_scan.py` + les vues à authentification propre (jeton du portail, clé d'API, webhooks, ICS, liens signés), soit ≈ 260 routes publiques ou à jeton ; + 280 routes d'écriture des apps hors PF4 ; aucune table `PF5.json` |
| Apps hors PF4 lues | `adsengine`, `customfields`, `tiers`, `entites`, `adminops`, `accessreview`, `statuspage`, outillage, `onboarding`, explorateur de données, gestion des clés d'API |
| Niveau | L2 — surfaces ouvertes à Internet et données de toute la société, mais 1 société, 5 comptes internes et 1 compte portail en production ; 5 surfaces indépendantes |
| Données | aucune démo (aucune pile ne servait `main`) ; anon : non requis ; prod lecture seule (lue par une autre session) : voir §2 |
| Critères retenus | C4, C5, C6, C8, C12, C13, C17 |
| Étapes | PF5.1 devis public, paiement, signature, interventions, SAV public · PF5.2 portail client et fournisseur, GED à lien, liens signés, ICS, partages · PF5.3 formulaires et chat publics, API publique et clés, webhooks, pages d'état · PF5.4 droits des apps hors PF4 · PF5.5 routage, CORS et site public (parcours : PF5) |
| NE PAS REFAIRE | ADRG (dont ADRG96, ADRG97, ADRG102, ADRG76) ; ASEC85 à ASEC95 ; ADOC202 ; APFS118 à APFS124 (déjà déposées) |
| Non-objectifs | étanchéité entre sociétés (PF1) ; droits de la grille des apps déjà lues par PF4 ; contenu du site public lui-même |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| lecture : devis public, paiement, signature, interventions, SAV | opus/high | vues publiques de `ventes/public/`, `installations/public_views.py`, `sav/public_views.py`, nginx (débits) | ≈ 3 000 lignes de `build_quote_data`, lues seulement par leurs filtres de sortie |
| lecture : portail, GED à lien, liens signés, ICS, partages | opus/high | `portail/`, `ged/` (signature), `core/export_registry.py`, `reporting/diffusion_views.py`, ICS, partages de tableaux | rendu des PDF du portail |
| lecture : formulaires, chat, API publique, webhooks, pages d'état | opus/high | `crm/public_chat_views.py`, `contact`, `publicapi/` (46 routes, OAuth, OpenAPI), webhooks entrants, `statuspage` | en-têtes réels de la prod |
| lecture : droits des apps hors PF4 | opus/high | ≈ 280 routes d'écriture des apps listées au §1 ; rôles livrés recalculés par script sur le registre vivant | — |
| vérificateurs frais (4) | opus/high | un par lecture ; vraies fonctions extraites par `ast` et exécutées avec bouchons | ce qui dépend de l'état de la prod |
| secondes lentilles (2) | opus/high | les deux S1 : export de réversibilité, revue d'accès, maillon par maillon | — |
| critique de complétude + vérificateur de ses trous | opus/high | trous transverses (CORS du site, compte portail fournisseur) | pistes listées au §7 |
| sondes (3 écrivains), rédaction (3), édition | opus/high | 11 sondes hôte ; 47 tâches v3 + l'acceptation | — |
Détecteurs : `backend/django_core/core/public_endpoint_scan.py` (inventaire des 91 vues `AllowAny`) et scripts d'inventaire hors dépôt @ae5a7ae · non exécutés : `core/tests/test_public_endpoint_hardening.py`, tests Django (aucune pile).
Live : aucun scénario joué par l'API · 11 sondes hôte jouées sur le vrai code extrait (toutes `repro: True` sur ae5a7ae) · prévus non joués : le rejeu par l'API des tâches P0 et P1 (APUB74).
Prod (lecture seule, lue le 10/11 par une autre session ; cette session n'a pas lu la prod) : 1 société ; 5 comptes internes actifs (2 Directeur, 2 Commercial, 1 Commercial responsable) ; 1 compte du portail client actif ; 0 entité ; 1 clé d'API (lue le 08/11).

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-APUB-001 | PF5.2 | C5 | S1 | `backend/django_core/core/export_registry.py::ExportReversibiliteHistoriqueView` | l'historique de l'export de réversibilité rend le lien du ZIP de toute la base à 10 rôles sur 12 (3 commerciaux réels) ; lien public de 7 jours sans coupure → historique au Directeur, lien borné et révocable | `docs/audits/sondes/APUB/C-APUB-001.py` | APUB1, APUB2, APUB3, APUB74 |
| C-APUB-002 | PF5.4 | C5 | S1 | `backend/django_core/apps/accessreview/services.py::attester` | « Révoquer » (écran `frontend/src/pages/admin/GouvernanceAccesPage.jsx`, sans confirmation) retire un rôle sans garde de rang ni de propriétaire protégé : plus aucun administrateur → gardes de la fiche utilisateur | `docs/audits/sondes/APUB/C-APUB-002.py` | APUB4, APUB74 |
| C-APUB-003 | PF5.1 | C6 | S2 | `backend/django_core/apps/sav/public_views.py::equipement_public_signaler` | le QR d'un équipement crée ≈ 600 tickets SAV par heure et par IP en variant le texte (numéros et échéances consommés) → plafond par équipement | `docs/audits/sondes/APUB/C-APUB-003.py` | APUB5 |
| C-APUB-004 | PF5.1 | C8 | S2 | `backend/django_core/apps/installations/models_intervention.py::Intervention.lien_rapport_token` | le lien public du compte-rendu d'intervention (photos du domicile, numéros de série) n'expire ni ne se coupe ; le « révocable » du 07/10 était faux → coupure et durée bornée (D-APUB-4) | `docs/audits/sondes/APUB/C-APUB-004.py` | APUB6, APUB7 |
| C-APUB-005 | PF5.1 | C6 | S2 | `backend/django_core/apps/ventes/public/signature_views.py::proposal_contact_request` | « Contacter mon conseiller » : un `canal` libre contourne l'idempotence d'une heure, 30 notes au lead et 30 notifications par minute → seuls les canaux du site | `docs/audits/sondes/APUB/C-APUB-005.py` | APUB8 |
| C-APUB-006 | PF5.2 | C6 | S2 | `backend/django_core/apps/ged/services.py::envoyer_code_otp_signataire` | `envoyer-code` d'une signature envoie un SMS ou un e-mail à chaque appel, sans délai, et remet les essais à zéro (≈ 600 codes par heure et par IP) → 60 secondes entre deux envois | STATIQUE | APUB9, APUB74 |
| C-APUB-007 | PF5.3 | C5 | S2 | `backend/django_core/apps/crm/public_chat_views.py::post_chat_message` | livechat public ouvert sans aucun appelant : un anonyme crée des leads, écrit dans l'historique d'un lead existant (Signé compris) par son téléphone, remplit son e-mail ; transcript lisible sans fin → parqué derrière un drapeau (D-APUB-2) | `docs/audits/sondes/APUB/C-APUB-007.py` | APUB10 |
| C-APUB-008 | PF5.3 | C17 | S2 | `backend/django_core/apps/crm/fiche_api_publique.py::update_lead_from_public_api` | par l'API publique un lead Signé passe Froid sans dés-acceptation : devis « accepté », chantier et commission restent (règle du 08/10) ; latent (API non servie) → dés-acceptation comme à l'écran | `docs/audits/sondes/APUB/C-APUB-008.py` | APUB11 |
| C-APUB-009 | PF5.4 | C5 | S2 | `backend/django_core/apps/adsengine/views.py::FlightPlanViewSet` | plans de vol publicitaires et leurs phases écrits avec `adsengine_manage` seul : Commercial, Technicien, Responsable passent sans `adsengine_flightplan_manage` → code de la grille exigé | `docs/audits/sondes/APUB/C-APUB-009.py` | APUB12 |
| C-APUB-010 | PF5.4 | C5 | S2 | `backend/django_core/apps/tiers/views.py::TiersViewSet` | tiers, requêtes sauvegardées et tableaux de bord écrits par les rôles en lecture seule ; tout compte interne modifie ou supprime le tableau d'un collègue → garde d'écriture et contrôle du propriétaire | `docs/audits/sondes/APUB/C-APUB-010.py` | APUB13, APUB14 |
| C-APUB-011 | PF5.5 | C12 | S2 | `backend/nginx/nginx.conf` | ni nginx ni Caddy ne servent `/api/public/` : l'API publique par clé (46 routes) et deux appels de l'écran Paramètres tombent sur le front (non vérifié en prod) → ouvrir après correctifs (D-APUB-3) | STATIQUE | APUB11, APUB15, APUB47, APUB50, APUB51, APUB74 |
| C-APUB-012 | PF5.1 | C8 | S3 | `backend/django_core/apps/installations/public_views.py::InterventionRapportPhotoPublicView` | la route photo du compte-rendu public sert toute image de l'intervention (plaque comprise) → seulement les photos que la page publie | STATIQUE | APUB30 |
| C-APUB-013 | PF5.1 | C5 | S3 | `backend/django_core/apps/ventes/public_views.py::public_document` | liens publics de facture et de BCF jamais révocables ; facture brouillon ou annulée servie → refus | STATIQUE | APUB31, APUB32 |
| C-APUB-014 | PF5.1 | C8 | S3 | `backend/django_core/apps/ventes/public/paiement_views.py::pay_page` | la page « Payer » rend le nom du client sur un lien expiré ou annulé → page neutre | STATIQUE | APUB33 |
| C-APUB-015 | PF5.1 | C6 | S3 | `backend/django_core/apps/ventes/public/paiement_views.py::proposal_virement_declare` | un virement d'acompte se déclare avant l'acceptation du devis → refus | STATIQUE | APUB34 |
| C-APUB-016 | PF5.1 | C8 | S3 | `backend/django_core/apps/installations/public_views.py::InterventionLienClientPublicView` | le lien « technicien en route » n'expire jamais sans date prévue ; pages publiques sans `noindex` ni `Cache-Control` → expiration et en-têtes | STATIQUE | APUB35, APUB36 |
| C-APUB-017 | PF5.1 | C13 | S3 | `backend/django_core/apps/ventes/public/lecture_views.py::proposal_engagement` | un nombre non fini (`1e400`) dans le corps donne une erreur 500 (engagement, activer-option) → 400 | STATIQUE | APUB37, APUB38 |
| C-APUB-018 | PF5.1 | C6 | S3 | `backend/django_core/apps/sav/public_views.py::ticket_public_satisfaction` | jumeau SAV de C-APUB-017 : corps hostile de la satisfaction → 500 → 400 nommé | STATIQUE | APUB38 |
| C-APUB-019 | PF5.1 | C5 | S3 | `backend/django_core/apps/crm/cadence_signaux.py::_lever_opposition_a_la_demande_du_client` | une demande « rappel » depuis le lien du devis lève l'opposition loi 09-08, inscrite « à la demande du client » sans preuve que c'est elle → levée par le commercial après appel (D-APUB-1) | STATIQUE | APUB39 |
| C-APUB-020 | PF5.2 | C5 | S3 | `backend/django_core/apps/ged/services.py::refuser_signataire` | refuser une signature se fait sans le code OTP que signer exige et clôt la demande pour tous → code exigé | STATIQUE | APUB40 |
| C-APUB-021 | PF5.2 | C5 | S3 | `backend/django_core/apps/reporting/diffusion_views.py::rapport_partage_public` | lien public de rapport : révocation sans écrivain, IP tracée = 1re valeur fournie par l'appelant ; dormant → geste « couper » et IP du relais | STATIQUE | APUB41, APUB42 |
| C-APUB-022 | PF5.2 | C5 | S3 | `backend/django_core/apps/portail/public_views.py::portail_mon_releve` | le jeton permanent du relevé de compte, sur une route sans écran ni appelant → route retirée | STATIQUE | APUB43 |
| C-APUB-023 | PF5.2 | C5 | S3 | `backend/django_core/apps/portail/views_client.py::MesChantiersPortailViewSet` | un membre « lecture seule » du client écrit des relevés de compteur → refus | STATIQUE | APUB44 |
| C-APUB-024 | PF5.2 | C4 | S3 | `scripts/check_portail_surfaces.py` | la garde « portail » ne lit ni les routes publiques ni les tableaux fournisseur et partenaire ni aucune permission → étendue | STATIQUE | APUB45 |
| C-APUB-025 | PF5.2 | C6 | S3 | `backend/django_core/apps/stock/public_views.py::portail_fournisseur_confirmer_bcf_view` | la confirmation d'un BCF par jeton est rejouable (date réécrite, notification à chaque appel) → sans effet si identique | STATIQUE | APUB46 |
| C-APUB-026 | PF5.3 | C8 | S3 | `backend/django_core/apps/publicapi/bulk.py::run_export_job` | exports CSV de l'API publique sans neutralisation des formules (jumeau oublié d'ENF12) ; latent → cellules neutralisées | STATIQUE | APUB47 |
| C-APUB-027 | PF5.3 | C5 | S3 | `backend/django_core/core/views.py::metrics_view` | tout Administrateur de société lit les métriques de toute la plateforme (par id de société) → IP autorisées et superutilisateurs | STATIQUE | APUB48 |
| C-APUB-028 | PF5.3 | C13 | S3 | `backend/django_core/apps/statuspage/receivers.py` | lien de désabonnement des e-mails d'incident relatif, désabonnement sur un simple GET → lien absolu et confirmation | STATIQUE | APUB49 |
| C-APUB-029 | PF5.3 | C8 | S3 | `backend/django_core/apps/publicapi/views.py::portees_non_detenues` | une clé à portée achats s'émet sans `prix_achat_voir` (montant estimé masqué à l'écran) ; `leads:write` avec `crm_creer` seul ; latent → codes exigés à l'émission | STATIQUE | APUB50 |
| C-APUB-030 | PF5.3 | C13 | S3 | `backend/django_core/apps/publicapi/public_changelog_views.py::PublicChangelogView` | `changelog/` et `errors/` : le débit par clé ne limite rien sans clé → débit par IP | STATIQUE | APUB51 |
| C-APUB-031 | PF5.3 | C5 | S3 | `backend/django_core/apps/publicapi/views.py` | modifier un webhook ne compare pas ses événements aux codes de l'acteur (jumeau d'APFS110) → comparaison | STATIQUE | APUB52 |
| C-APUB-032 | PF5.4 | C5 | S3 | `backend/django_core/apps/adminops/config_package_service.py::appliquer_import` | l'import d'un paquet de configuration écrit les permissions d'un rôle sans les validateurs du rôle : des codes hors catalogue entrent → validateurs du rôle | STATIQUE | APUB53 |
| C-APUB-033 | PF5.4 | C13 | S3 | `backend/django_core/apps/customfields/views.py::CustomRecordViewSet` | objets personnalisés inaccessibles à tous les rôles alors que l'écran les propose → codes octroyables | STATIQUE | APUB54 |
| C-APUB-034 | PF5.4 | C13 | S3 | `backend/django_core/core/data_explorer.py` | le catalogue de l'explorateur liste des jeux que la lecture refuse ensuite → catalogue filtré | STATIQUE | APUB55 |
| C-APUB-035 | PF5.4 | C5 | S3 | `backend/django_core/core/dashboard_partage.py::DashboardPartageInterneViewSet` | un compte s'ajoute lui-même au tableau personnel d'un collègue (jumeau interne d'ADRG102) → partage borné aux tableaux de l'acteur | STATIQUE | APUB56 |
| C-APUB-036 | PF5.4 | C5 | S3 | `backend/django_core/apps/onboarding/views.py::OnboardingItemsMasquesViewSet` | masquer un conseil « Premiers pas » pour la société est ouvert au palier responsable (vue dite « admin ») → `parametres_modifier` | STATIQUE | APUB57 |
| C-APUB-037 | PF5.2 | C5 | S2 | `backend/django_core/apps/roles/permissions.py::acces_portail_revoque` | un fournisseur bloqué « total », archivé ou rejeté garde son compte portail : il lit ses BCF et ses factures et confirme un BCF (`/api/django/portail/mes-bons-commande/`) ; liens de BCF non coupés → compte et liens fermés | `docs/audits/sondes/APUB/C-APUB-037.py` | APUB70, APUB71, APUB72 |
| C-APUB-038 | PF5.5 | C5 | S2 | `backend/django_core/erp_agentique/settings/prod.py` | taqinor.ma et www sont des origines CORS à identifiants, cookies de session sans contrôle CSRF : tout script sur le site lit et écrit l'ERP avec la session de l'employé ; le site n'en a aucun besoin → retirer ce droit (D-APUB-5) | `docs/audits/sondes/APUB/C-APUB-038.py` | APUB73 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-APUB-001 | requalifié S2 → S1, élargi | toute la base de la société (11 CSV) obtenue par un rôle sans droit d'export ; la vue publique sert aussi tout autre lien signé, sans contrôler le seau (`backend/django_core/core/export_registry.py::telecharger_export_reversibilite`) ; sonde `docs/audits/sondes/APUB/C-APUB-001.py` |
| C-APUB-002 | requalifié S2 → S1 | perte de contrôle de la société, sans élévation de l'acteur : seule porte qui contourne la garde « compte protégé / dernier propriétaire » (`backend/django_core/apps/roles/services.py::remove_role_from_user`) ; sonde `docs/audits/sondes/APUB/C-APUB-002.py` |
| C-APUB-020 | requalifié S2 → S3 | refuser ne signe rien ; la signature reste au code (`backend/django_core/apps/ged/services.py::refuser_signataire`) |
| C-APUB-036 | requalifié S2 → S3 | réversible, sans données (`backend/django_core/apps/onboarding/views.py::OnboardingItemsMasquesViewSet`) |
| C-APUB-007 | requalifié S1 → S2 | rouvrir un Froid est voulu (D-CADV-12, D-ACVI-5) ; reste l'écriture anonyme sans écran (`backend/django_core/apps/crm/public_chat_views.py::post_chat_message`) |
| C-APUB-008 | requalifié S3 → S2 | contraire à la règle du 08/10 (lead sorti de « Signé » = dés-acceptation) ; latent tant que l'API n'est pas servie (`backend/django_core/apps/crm/fiche_api_publique.py::update_lead_from_public_api`) |
| C-APUB-019 | requalifié S3, question ouverte | un commercial peut déjà lever l'opposition à son nom ; le tort propre est la trace « à la demande du client » sans preuve → D-APUB-1 |
| C-APUB-004 | S4 du 07/10 corrigé en S2 | le lien n'est pas révocable : une seule écriture du jeton, à la pose (`backend/django_core/apps/installations/models_intervention.py::Intervention.lien_rapport_token`) |
| lien de l'export des mouvements de stock | fusionné dans C-APUB-001 | servi par la même vue publique |
| IP du rapport partagé | fusionné dans C-APUB-021 | même vue |
Porte : 0 réfuté en entier / 38 retenus · 7 gravités revues (+ 1 gravité d'un audit antérieur corrigée) · seconde lentille : 2 S1 → maintenus 2, gravité revue 0, élargis 1 ; les 2 trous de la critique (C-APUB-037, C-APUB-038) confirmés S2 par un vérificateur frais.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| explorateur de données | 11 jeux bornés à la société ; prix d'achat, valeur, montant BCF, coût SAV retirés sans `prix_achat_voir` (`backend/django_core/core/data_explorer.py`) | aucun jeu nouveau sans ce filtre |
| émission des clés d'API | seuls Directeur et Administrateur portent `integrations_gerer` et détiennent tous les codes des portées | aucun rôle livré ne reçoit ce code |
| jetons publics ventes, installations, SAV | ≈ 256 bits (`secrets.token_urlsafe(32)`), refus en 404 neutres | la génération reste la même |
| paiement en ligne | `pay_webhook` ne confirme jamais un paiement (passerelles `paid: False`) | aucune passerelle réelle branchée |
| acceptation du devis | gardée par l'empreinte du contenu lu et le verrou du groupe ; V1 révisée refusée | — |
| formulaire de contact, inscription | fermés par drapeau (`CONTACT_FORM_ENABLED`, `TENANT_SIGNUP_ENABLED` à 0) : 404 avant tout envoi | les drapeaux restent à 0 en prod |
| webhooks entrants | Meta, demande de rendez-vous, WhatsApp Cloud et BSP signés, fermés en cas d'échec | — |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-APUB-1 | Un « rappel » demandé par le lien du devis lève-t-il l'opposition loi 09-08 ? | ouverte | APUB39 |
| D-APUB-2 | Fermer par défaut le chat public du site, sans écran ? | ouverte | APUB10 |
| D-APUB-3 | Ouvrir l'API publique par clé en production, après correctifs ? | ouverte | APUB15 |
| D-APUB-4 | Le lien du compte-rendu d'intervention expire-t-il 90 jours après la clôture ? | ouverte | APUB7 |
| D-APUB-5 | Retirer au site public le droit d'appeler l'ERP avec la session de l'employé ? | ouverte | APUB73 |

## 7. Optionnel (jamais une tâche)
- SCIM latent (`identity/scim.py`) — aucun émetteur de jeton SCIM ; déjà S4 au plan sécurité.
- Acquittement de la simulation d'autonomie publicitaire au code `adsengine_manage` — sans effet réel.
- PDF publics re-rendus à chaque ouverture — coût de calcul seulement.
- `attester` accepte une campagne close et re-tranche un compte déjà tranché — hors gravité, à reprendre avec APUB4.
- Même défaut de garde d'écriture possible dans `apps/reporting/classeur.py::ClasseurViewSet` — piste non creusée.

## 8. Limites, non couvert, écarts
- Non couvert : aucune pile ne servait `main` : aucun test Django exécuté, aucun rejeu par l'API. Les 11 sondes sont des sondes HÔTE : le vrai code est extrait par `ast` et exécuté avec des bouchons d'ORM et de DRF ; elles prouvent le mécanisme, pas le comportement d'une pile complète.
- Non couvert : le comportement de `django-cors-headers` est modélisé (bibliothèque absente de l'hôte) ; les en-têtes CORS réels, le routage nginx de la prod pour `/api/public/`, l'existence d'un export de réversibilité récent, la configuration SMS et `RELAIS_API_SECRET` ne sont pas vérifiés en prod.
- Non couvert : ≈ 3 000 lignes de `build_quote_data` lues seulement par leurs filtres de sortie.
- Choix de l'audit (pas une décision du fondateur) : seule la route à jeton sert le relevé de compte, sans écran ni appelant ; APUB43 la retire, comme les routes sans écran retirées en D-ACRM-6.
- Écart à la méthode : C-APUB-006 et C-APUB-011 (S2, critères C6 et C12) sans sonde → ponctuel : critères sans sonde obligatoire ; C-APUB-011 se confirme par un curl en prod.
- Incident prod : aucun constaté ; risques ouverts exploitables aujourd'hui : C-APUB-001 si un export « prêt » de moins de 7 jours existe (non lu) → APUB1, APUB2 ; C-APUB-002 par les 2 comptes Directeur → APUB4.

## 9. Coût et routage
Coût : H0 S0 O19 F0 · jetons sous-agents ≈ 5,4 M · tâches 48 (M0 0 M1 15 M2 0 M3 28 GATED 5).
Routage : `PLAN_AUDIT_SECURITE.md` 11 · `PLAN_AUDIT_ANALYSE.md` 7 · `PLAN_AUDIT_CHANTIERS.md` 5 · `PLAN_AUDIT_DOCUMENTS.md` 4 · `PLAN_AUDIT_STOCK.md` 4 · `PLAN_AUDIT_DEPLOY.md` 3 · `PLAN_AUDIT_DEVIS.md` 3 · `PLAN_AUDIT_LEAD.md` 3 · `PLAN_AUDIT_PARAMETRES.md` 2 · `PLAN_AUDIT_SAV.md` 2 · `PLAN_AUDIT_TRANSVERSE.md` 2 · `PLAN_AUDIT_ACQUISITION.md` 1 · acceptation APUB74 · PR #0.
Rapport : deux défauts graves, chacun prouvé par une sonde sur le vrai code et confirmé par une seconde lecture.
- Export de réversibilité (C-APUB-001) : l'historique de l'export donne à presque tous les comptes internes (dont les 3 commerciaux) le lien du ZIP de toute la base de la société (clients, prospects, factures, paiements, devis). Ce lien s'ouvre sans compte pendant 7 jours et ne se coupe pas. → APUB1, APUB2, APUB3.
- Revue d'accès (C-APUB-002) : un Directeur peut, d'un clic et sans confirmation, retirer le rôle du propriétaire puis le sien ; la société n'a plus d'administrateur, il faut une commande sur le serveur pour s'en sortir. → APUB4.
- Ensuite 11 défauts S2 : des formulaires publics sans plafond (QR SAV, contact du devis, codes de signature), des liens qui ne s'arrêtent jamais, un chat public anonyme sans écran, un compte fournisseur bloqué qui reste ouvert, le site public qui peut parler à l'ERP avec la session de l'employé, l'API publique injoignable. 25 S3. 5 questions au fondateur, toutes ouvertes ; 5 tâches les attendent.
