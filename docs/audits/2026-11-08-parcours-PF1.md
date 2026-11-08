# Audit PF1 « sécurité / multi-société » — 2026-11-08 — L3
<!-- dossier-v3 | groupe: APFS | base: 57d3fd3 | fraicheur: 31a4bce | constats: 30 | taches: 49 | decisions: 4 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF1 (rôles × toutes les portes, deux sociétés) : lu `authentication/`, `core/{views,data_explorer,scheduled_export,mixins,dsr}.py`, `apps/{roles,records,reporting,dataimport,publicapi,automation,adminops,identity,portail,crm,installations,stock,sav,ventes,parametres,ged}`, `backend/fastapi_ia/app`, gardes `scripts/check_*` ; aucune table `PF1.json` |
| Niveau | L3 — compte externe et rôles internes lisant données personnelles, prix d'achat et argent hors droit, palier « responsable », superutilisateur, multi-société, services IA ; on cherche la CLASSE et sa porte commune |
| Données | demo (27 sondes en transaction annulée, sociétés A et B, rôles système canoniques, connexion par la vraie route) ; anon : non requis ; prod lecture seule le 08/11 : 1 société, 5 comptes internes, 0 portail, 0 superutilisateur, 0 support, 1 clé d'API → exposition nulle |
| Critères retenus | C5, C6, C8, C9, C11 |
| Étapes | PF1.1 portail et services IA · PF1.2 identité, session, réseau · PF1.3 moteur de données, exports, extraits · PF1.4 lectures transverses · PF1.5 lecture des objets métier · PF1.6 palier « responsable » · PF1.7 corbeille et loi 09-08 · PF1.8 superutilisateur et support · PF1.9 multi-société · PF1.10 gardes de CI (parcours : PF1) |
| NE PAS REFAIRE | groupe ASEC (vérifié le 04/11) ; AARG52, AARG65-67 ; AAPV32-36, AAPV51-52, AAPV67-68 ; AMON20, AMON45, AMON92 ; ACSV62, ACSV54 ; ACON3 ; ACVI6, ACVI105, ACVI106 ; ACAL296 ; AARG66 (factures-lignes fermées) |
| Non-objectifs | écrans en navigateur ; Django admin ; secrets, chiffrement, en-têtes HTTP (ASEC) ; coût des services payants hors compte externe ; webhooks entrants signés (lus seulement) |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| découverte : cadre de permissions | opus/high | 630 classes de vues DRF par AST, gardes effectives simulées par action, `permissions_registre.py` | frontend |
| découverte : isolation multi-société | opus/high | balayages AST des ids, `get_queryset`, `perform_create`, références entières, `@api_view`, beats | usage prod |
| découverte : surfaces publiques et portail | opus/high | 9 035 routes, 91 vues `AllowAny`, `portail`, `publicapi`, `identity` | webhook d'automatisation |
| découverte : données personnelles, IA | opus/high | `records`, `reporting`, `dataimport`, `fastapi_ia/app`, `core/dsr.py` | journal WhatsApp |
| sondes (5 lots) | opus/high | 26 constats rejoués, vraies routes, jetons réels | rendu PDF des gabarits (double) |
| seconde lentille | opus/high | compte portail sur 3 979 couples route × méthode, FastAPI en conteneur jetable | production, écrans |
| critique de complétude | fable/high | 3 trous : 2 sondés, 1 lu | frontend |
| rédaction des tâches | opus/high | 49 tâches v3 (3 rédacteurs) | — |
| dossier et registre | sonnet/high | ce dossier, `unites.yml`, `decisions.yml`, 4 clauses « Constat » de lecture | — |
Détecteurs : `scripts/check_tenant_isolation.py`, `check_viewset_model_scope.py`, `check_portail_surfaces.py`, `check_fk_scoping.py`, `check_ownership.py` → OK @31a4bce, tous verts alors que chaque classe existe ; `check_parcours.py` : 7 tables, 0 échec · non exécutés : `rejouer_parcours.py` (pas de table PF1), `audit_tache.py` (greps équivalents).
Live : 27 sondes `docs/audits/sondes/APFS/` (REPRO, jetons réels, transaction annulée), dont le rejeu du compte portail sur toutes les routes (-L2) et FastAPI en conteneur jetable (limiteur Redis, relais `/auth/me/` et appels payants bouchonnés) · prévus non joués : écrans en navigateur.
Prod (lecture seule, 08/11) : 1 société, 5 comptes internes, 0 portail, 0 superutilisateur, 0 support, 1 clé d'API → aucun objet exposé ; le premier compte portail provisionné (un clic de l'Administrateur) ouvrirait la porte du S1.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-APFS-001 | PF1.1 | C8 | S1 | `authentication/permissions.py::IsAuthenticatedInterne` | compte portail client : requêtes sauvegardées 200 (prospects, clients, factures), 89 vues `IsAuthenticated` le laissent passer dont 31 internes ; agent SQL FastAPI : 139 clients, 7 factures, OCR payant → 403 partout | `docs/audits/sondes/APFS/C-APFS-001.py` | APFS1, APFS2, APFS100, APFS101 |
| C-APFS-002 | PF1.2 | C6 | S3 | `authentication/cookie_auth.py::CookieJWTAuthentication.authenticate` | Commercial au mot de passe expiré ou réinitialisé : connexion 200, `must_change_password` vrai, `GET` 200 et `POST crm/leads/` 201 ; seul le portail est refusé → 403 `mot_de_passe_a_changer` hors /auth/me, logout, change-password | `docs/audits/sondes/APFS/C-APFS-002.py` | APFS3, APFS102 |
| C-APFS-020 | PF1.3 | C5 | S2 | `core/data_explorer.py::run_query` | Commercial terrain, Admin RH, Technicien (403 sur `crm/leads/`, `ventes/factures/`) : 200 + 4 leads et la facture par les 5 portes du moteur ; Commercial « soi » : écran 1 lead, moteur 4 → droit du module du jeu + portée | `docs/audits/sondes/APFS/C-APFS-020.py` | APFS4, APFS103, APFS104 |
| C-APFS-021 | PF1.4 | C8 | S3 | `apps/parametres/views_gabarits.py::GabaritDocumentCustomViewSet.rendre` | gabarit personnalisé rendu (API seule) : Admin RH, Commercial terrain, Technicien reçoivent téléphone, ICE et adresse du client de A (fiche en 403/404) → droit de lecture du module de la cible, coordonnées masquées sans `client_pii_voir` | `docs/audits/sondes/APFS/C-APFS-021.py` | APFS22 |
| C-APFS-022 | PF1.4 | C5 | S2 | `apps/records/serializers.py::resolve_target` | Admin RH, Commercial terrain, Technicien (403 sur facture et devis) : listent et téléchargent la pièce de la facture, lisent la remise négociée, déposent un commentaire (201) → droit + portée pour TOUTE cible, pas seulement les leads | `docs/audits/sondes/APFS/C-APFS-022.py` | APFS20 |
| C-APFS-023 | PF1.4 | C5 | S3 | `apps/records/views.py::attachments_all` | Commercial « soi », Admin RH, Commercial terrain : pièce du lead d'un collègue listée (nom, auteur, url) alors que `records/attachments/` l'exclut → même filtre `pieces_visibles` | `docs/audits/sondes/APFS/C-APFS-023.py` | APFS21 |
| C-APFS-024 | PF1.3 | C8 | S2 | `apps/dataimport/exports_view.py::export_list` | Commercial terrain, Admin RH, Viewer sans `ventes_export` : XLSX des factures avec le client (200) ; Commercial « soi » exporte le devis d'un collègue par `ids` → code `<module>_export` + portée | `docs/audits/sondes/APFS/C-APFS-024.py` | APFS23 |
| C-APFS-025 | PF1.4 | C8 | S2 | `apps/reporting/search.py::global_search` | recherche d'un numéro : Admin RH, Commercial terrain, Commercial « soi » → groupe `lead` avec le téléphone en `sublabel`, e-mail client en clair sans `client_pii_voir` ; cloche : factures impayées sans `ventes_voir` → droit, portée, masque | `docs/audits/sondes/APFS/C-APFS-025.py` | APFS24 |
| C-APFS-026 | PF1.4 | C8 | S2 | `apps/reporting/geo.py::geo_points` | Admin RH, Commercial terrain, Technicien, « soi » et rôle sans `client_pii_voir` reçoivent le point du lead (latitude, longitude) ; lead de B absent → `crm_voir`, portée, coordonnées masquées | `docs/audits/sondes/APFS/C-APFS-026.py` | APFS25 |
| C-APFS-027 | PF1.4 | C8 | S2 | `apps/reporting/approbations.py::_installations_items` | demande d'achat 10 × 750 : Technicien, Commercial, Admin RH (sans prix d'achat) reçoivent `montant = 7500.0` et le tri par montant, la fiche le masque → montant absent sans `prix_achat_voir` | `docs/audits/sondes/APFS/C-APFS-027.py` | APFS26 |
| C-APFS-028 | PF1.4 | C8 | S2 | `apps/sav/serializers.py::TicketSerializer.get_client_telephone` | rôle personnalisé sans `client_pii_voir` : `crm/clients/<id>/` masque le téléphone, ticket SAV (fiche et liste) et facture le rendent en clair → même règle partout, une garde qui recense tout `client_telephone` | `docs/audits/sondes/APFS/C-APFS-028.py` | APFS27 |
| C-APFS-040 | PF1.6 | C5 | S2 | `authentication/permissions.py::IsAdminOrResponsableTier` | Admin RH, Technicien responsable (palier via `users_voir`) : clé d'API `read:leads` + `read:factures` (201), module coupé, quotas, demande de palier admin approuvée → code dédié ou du domaine (D-APFS-1) | `docs/audits/sondes/APFS/C-APFS-040.py` | APFS40, APFS41, APFS46, APFS110, APFS111, APFS112 |
| C-APFS-041 | PF1.7 | C5 | S2 | `core/views.py::TrashViewSet.restaurer` | lead supprimé : Admin RH, Technicien, Commercial terrain 403 sur la corbeille transverse mais 200 sur `core/corbeille/<id>/restaurer/`, lead rétabli → même garde que la corbeille transverse | `docs/audits/sondes/APFS/C-APFS-041.py` | APFS42, APFS43 |
| C-APFS-042 | PF1.7 | C8 | S2 | `core/views.py::DataSubjectRequestViewSet` | Admin RH, Technicien responsable, Admin Ventes sans code CRM : demande 09-08 créée (201) et traitée (200) : export du téléphone et de l'e-mail, client anonymisé → code dédié `dsr_traiter` (D-APFS-1) | `docs/audits/sondes/APFS/C-APFS-042.py` | APFS45 |
| C-APFS-043 | PF1.6 | C11 | S3 | `apps/automation/views.py::ApprovalRequestViewSet` | demande approuvée : `PATCH` refusé (409) mais `DELETE` par le demandeur 204, demande et décision effacées ; demande en attente : `PATCH {payload: {}}` vide un champ requis → 409 si décidée, validation rejouée | `docs/audits/sondes/APFS/C-APFS-043.py` | APFS44, APFS113 |
| C-APFS-044 | PF1.2 | C8 | S3 | `authentication/models.py::CustomUser.can_view_buy_prices` | compte provisionné SCIM sans rôle, ou Commercial dont on retire le rôle : `stock/produits/` sert `prix_achat` et `marge_pct` (témoin avec rôle : absents) → rôle « Utilisateur » posé, jamais « aucun rôle » | `docs/audits/sondes/APFS/C-APFS-044.py` | APFS47 |
| C-APFS-060 | PF1.8 | C5 | S2 | `apps/adminops/impersonation_service.py::donner_consentement` | superutilisateur rattaché à A : demande sur un compte de B, consent lui-même (200), démarre, jeton valable ; un support gagne les pouvoirs plateforme via un superutilisateur cible → consentement d'un Administrateur de la société de la demande | `docs/audits/sondes/APFS/C-APFS-060.py` | APFS60 |
| C-APFS-061 | PF1.8 | C5 | S3 | `authentication/views.py::EstSaPropreSocieteOuOperateurPlateforme.has_object_permission` | superutilisateur rattaché à A : `GET companies/` rend B, `PATCH` la renomme et `{actif: false}` la suspend ; sur `crm/leads/` il ne voit que A, un `is_staff` est refusé (403) → borné à sa société (D-APFS-2) | `docs/audits/sondes/APFS/C-APFS-061.py` | APFS61, APFS114 |
| C-APFS-062 | PF1.9 | C5 | S3 | `apps/ventes/serializers.py::TiersPayeurValidationMixin.validate_tiers_payeur` | id de la société B : 400 « introuvable dans votre société » contre 404 pour un id absent, sur 3 champs (témoin `client` : 404/404) → même réponse, queryset borné à la société | `docs/audits/sondes/APFS/C-APFS-062.py` | APFS62 |
| C-APFS-063 | PF1.9 | C9 | S3 | `apps/reporting/scheduled_reports.py::email_saved_reports` | société B suspendue (`actif=False`) : `email_saved_reports()` envoie 2 mails à un destinataire externe, `last_sent_at` posé ; société A envoyée aussi → itérer `active_companies()` | `docs/audits/sondes/APFS/C-APFS-063.py` | APFS63 |
| C-APFS-064 | PF1.9 | C5 | S3 | `authentication/cookie_auth.py::CookieJWTAuthentication.authenticate` | Administrateur de A membre de B sans rôle dans B : bascule 200, `GET users/` 200 (comptes de B), `POST crm/leads/` 201 dans B, B ne le voit pas → un rôle par appartenance (D-APFS-3) | `docs/audits/sondes/APFS/C-APFS-064.py` | APFS66 |
| C-APFS-065 | PF1.2 | C5 | S3 | `apps/identity/middleware.py::_is_public_path` | société en ENFORCE, IP hors plage : `crm/leads/` 403 mais `ventes/devis/<id>/proposal/` répond (409 métier) et `publicapi/webhooks/` 200 : le chemin est testé par sous-chaîne → préfixes exacts | `docs/audits/sondes/APFS/C-APFS-065.py` | APFS67 |
| C-APFS-066 | PF1.9 | C5 | S3 | `apps/crm/public_views.py::public_apporteur_mes_deals` | réglage « apporteurs » éteint : interne 404 mais portail anonyme `mes-deals/` 200 (nom du client, ville, commission) → 404 réglage éteint, comme le portail des salles de vente | `docs/audits/sondes/APFS/C-APFS-066.py` | APFS68 |
| C-APFS-080 | PF1.5 | C5 | S2 | `authentication/permissions.py::IsAnyRole` | 160 routes `list` sur 200 ouvertes à Admin RH et Commercial terrain sans code du module (installations 63/70, stock 45/55, sav 14/17, ventes 16/26, crm 22/32) → `LectureDuModule` + octrois (D-APFS-4) | `docs/audits/sondes/APFS/C-APFS-080.py` | APFS28, APFS105, APFS106, APFS107, APFS108, APFS109, APFS115, APFS116 |
| C-APFS-081 | PF1.5 | C8 | S2 | `apps/installations/serializers.py::InstallationSerializer` | Admin RH et Commercial terrain lisent chantier (adresse, GPS, contact), fournisseur (RIB, ICE), ligne de devis (P.U.), remise d'encaissement (+ PDF), garantie, contrat de maintenance ; B jamais listée → même garde | `docs/audits/sondes/APFS/C-APFS-081.py` | APFS105, APFS106, APFS107, APFS108, APFS115 |
| C-APFS-082 | PF1.5 | C8 | S2 | `apps/installations/views/contrat_prix.py::ContratPrixLigneViewSet` | Commercial, Viewer, Technicien sans `prix_achat_voir` : 9 routes d'achat de `installations` rendent prix convenu, négocié, FOB (le BCF masque) ; Technicien responsable crée contrat et commande cadre → masque + `achats_commander` | `docs/audits/sondes/APFS/C-APFS-082.py` | APFS29, APFS117 |
| C-APFS-130 | PF1.6 | C5 | S3 | `authentication/permissions.py::IsResponsableOrAdmin.has_permission` | `semantic` figure dans `APPS_SANS_MODULE` : tout rôle fin à un code d'écriture crée, modifie et importe des métriques (même porte prouvée pour `core` par C-APFS-041) ; l'inventaire ne lit que `permission_classes` de classe → retirer `semantic` | STATIQUE (lecture) | APFS43 |
| C-APFS-131 | PF1.10 | C5 | S3 | `scripts/check_tenant_isolation.py::check_view_file` | aucune des 292 fonctions `@api_view` (109 fichiers) n'est lue par la garde d'isolement, qui accepte le mot « company » n'importe où dans `get_queryset` (même dans une branche `all()`) → vues fonction + filtre effectif | STATIQUE (lecture) | APFS64 |
| C-APFS-132 | PF1.10 | C5 | S3 | `apps/sav/serializers.py::TicketSerializer` | quatre références entières (devis, facture, lead, intervention d'origine) écrivables ; une facture non annulée de la société vaut « déjà générée » (autre société ignorée) → lecture seule + garde sur les références entières | STATIQUE (lecture) | APFS65 |
| C-APFS-133 | PF1.3 | C5 | S3 | `core/scheduled_export.py::rendre_extrait_detaille` | extrait planifié exécuté sans identité (`run_query(…, None, …)`), aucun créateur stocké, création au palier seul : toute garde par lecteur serait contournée la nuit, un créateur désactivé exporte encore → créateur, droits, suspension | STATIQUE (lecture) | APFS103 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-APFS-001 | requalifié S2 → S1 | un compte EXTERNE lit prospects, clients et factures : fuite pour ce tiers, l'isolement par société tenant (barème strict : S2) |
| C-APFS-001 | élargi | seconde lentille : 89 vues `IsAuthenticated` sur 96 laissent passer le portail, 31 servent l'interne, 24 ne sont gardées que dans le corps ; FastAPI (statique → REPRO) : 139 clients, 7 factures, OCR payant, aucune trace au journal |
| C-APFS-001 | fusionné | « le portail atteint l'explorateur » et « `IsAuthenticated` écrase le défaut » : `IsAuthenticatedInterne` n'est que le défaut DRF, la garde ASEC51 ne voit que les vues sans `permission_classes` |
| C-APFS-022 | fusionné | pièces, commentaires, activités : un mécanisme (`resolve_target` ne garde que les leads) |
| C-APFS-040 | fusionné | clés d'API, webhooks, modules, workflows, quotas, décision des demandes, historique OCR : une cause, le palier lit `users_voir` sans le code du domaine ; quotas S3 et OCR (moitié FastAPI lue) en facettes |
| C-APFS-043 | requalifié | « `PATCH` d'une demande décidée » réfuté (ASEC30, ASEC69 : 409) ; restent `DELETE` et `PATCH` en attente, S3 |
| C-APFS-028 | requalifié | S2 maintenu, rôles personnalisés seulement : aucun rôle système n'a `sav_voir` ou `ventes_voir` sans `client_pii_voir` |
| C-APFS-063 | requalifié | les quatre recopies de `actif=True` valent `active_companies()` (duplication) ; restent trois balayages de `reporting` |
| C-APFS-080, 081 | scindés | la classe (160 routes sur 200 en balayage dynamique, la lecture statique en donnait 154 sur 173) et l'échantillon par objet ; une garde `LectureDuModule` + octrois (D-APFS-4), une tâche par propriétaire |
| C-APFS-082 | fusionné | lecture S2 (prix d'achat hors garde ASTK14) et écriture S3 (contrats sans `achats_commander`) : un constat, deux tâches |
| C-APFS-133 | requalifié | lu : la nuit ne lit pas plus que l'explorateur aujourd'hui ; le trou est l'absence d'identité, qui contournerait la garde de C-APFS-020 |
Porte : 0 constat réfuté sur 37 candidats bruts (36 jugés, 1 non vérifié, §7) ; 30 constats : 26 prouvés par sonde, 4 lus (S3) · seconde lentille : 1 S1 → maintenu 1, élargi 1, gravité revue 1 (S2 → S1), 0 réfuté.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| isolement entre sociétés | aucune ligne de B dans les 27 sondes ; `TenantMixin` force `company` ; 11 sérialiseurs à `company` écrivable, tous hors écriture | `DevisSerializer` et `FactureSerializer` ne servent que la lecture (§7) |
| portail self-service | `portal_scope_id` fixe le client et la société ; invitation à jeton expirant, jamais rattachée à un compte existant ; `check_portail_surfaces` vert | les gardes `IsAuthenticated` explicites restent comptées (C-APFS-001) |
| jetons et sessions | `cookie_auth.py` refuse `is_active=False` à chaque requête, sessions révoquées ; access 30 min, refresh 7 j avec rotation et liste noire ; `ApiKey` = clé de société | la désactivation reste lue à chaque requête |
| surfaces publiques | 91 vues `AllowAny`, 88 avec throttle (les 3 autres ne lisent rien) ; webhooks Meta, WhatsApp SAV, rendez-vous signés par HMAC ; API publique : société prise sur la clé | préfixes publics exacts (C-APFS-065) |
| fichiers et GED | nginx ne sert que `/static/` ; dépôt PDF, PNG, JPEG, WebP par signature ; GED : `document_ids_visibles`, `PartageGed` à jeton, expiration, quota | commentaires GED via `records` à confirmer (§8) |
| assignation et approbations | `validate_owner` exige `crm_reassign` ; `decider_approval` : palier et non-demandeur ; l'agent relaie ses écritures à Django (droit + société) | `decide_request` reste à corriger (APFS111) |
| écritures et journaux | `check_action_permission_override` vert ; `RoleViewSet` borné (ASEC55) ; historique d'objet : société + propriétaire ; exports comptables et CRM sous `*_export` | `export_list` reste ouvert (C-APFS-024) |
| temps réel et tâches | aucun SSE ni WebSocket ; `core/jobs.py::submit` force société et utilisateur ; GPS des techniciens par `scope_queryset` | aucun canal ajouté sans garde |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-APFS-1 | palier « responsable » (`users_voir`) : clés d'API, modules, demandes 09-08, matrices, approbations — quelle garde | code_dedie_ou_domaine | APFS40 |
| D-APFS-2 | un superutilisateur rattaché à A peut renommer ou suspendre B : quelle règle | borne_a_sa_societe | APFS61 |
| D-APFS-3 | un membre de plusieurs sociétés garde-t-il le rôle de sa société d'origine après bascule | role_par_societe | APFS66 |
| D-APFS-4 | 160 vues de lecture sans droit du module : exiger le droit et octroyer les lectures croisées nécessaires | droit_du_module_et_octrois | APFS28 |

## 7. Optionnel (jamais une tâche)
- Journal WhatsApp (numéro et corps) ni exporté ni effacé par une demande 09-08 : candidat lu, aucun abonné d'effacement dans `notifications`, non vérifié ; à instruire avec APFS45.
- `reporting/classeur.py::_resolve_linked_range` ignore un agrégat décimal : `=SOMME(A1)` rend 0 au lieu de 12 000 pour tout interne ; vu en passant, S3 à confirmer.
- `DevisSerializer` et `FactureSerializer` gardent `company` écrivable (lecture seule par convention) : deux lignes `read_only_fields`.
- Lus au palier seul, non rejoués : `ApprovalRequestTypeViewSet`, `ConsentRecordViewSet`, `RegistreTraitementViewSet`, `OcrToCrmView` ; corbeille `core` : un Commercial restaure le lead d'un autre propriétaire ; `ApiKey` sans expiration par défaut.

## 8. Limites, non couvert, écarts
- Non couvert : écrans en navigateur ; config prod (politique réseau ENFORCE, `SQL_AGENT_DB_USER`) ; lectures croisées Technicien sur ventes et crm, Commercial sur installations (les octrois de D-APFS-4) ; `@action` GET des PDF de chantier ; `retrieve` rejoué sur 7 objets ; commentaires GED via `records` contre l'ACL ADOC3.
- Écart à la méthode : 4 constats sans sonde (S3 lus : porte d'écriture sans module, garde de CI, références entières, extrait planifié), aucun S1-S2 ; la moitié FastAPI de l'historique OCR (APFS46) est lue → ponctuel : conteneur FastAPI à la pile de sondes.
- Écart à la méthode : sondes jouées dans le conteneur monté sur c38868a62 (04/11), ancêtre de la base ; diff des mécanismes vide hors un message de refus, un en-tête vide, des champs sans effet → ponctuel : conteneur du jour.
- Écart à la méthode : pas de table `PF1.json` ni de rejeu de parcours (étapes = portes) → ponctuel : les rattacher au `vérifie APFS`.
- Limites des sondes : rendu PDF des gabarits remplacé par un double (021) ; FastAPI : appels payants et limiteur bouchonnés, couche SQL lue sur la base de dev (001-L2).
- Fraîcheur : `main` a avancé de 57d3fd3 à 31a4bce (4 commits, docs seulement) pendant l'audit ; aucun fichier ancré modifié, aucun correctif mergé.
- Incident prod : aucun incident ouvert ni exposition aujourd'hui ; avant de merger APFS103, compter les extraits planifiés actifs.

## 9. Coût et routage
Coût : H0 S1 O16 F1 · jetons sous-agents ≈ 6 M · tâches 49 (P0 4 P2 25 P3 20 GATED 0) · constats S1 1 S2 14 S3 15.
Fable : une critique de complétude, 3 trous (2 S2 sondés, 1 S3 lu) ; elle a trouvé la classe la plus large, laissée de côté par quatre lanes : 160 routes de lecture sur 200 ouvertes sans droit du module (C-APFS-080) et les prix d'achat de `installations` hors garde ASTK14 (C-APFS-082).
Routage : `PLAN_AUDIT_*.md` SECURITE 18 · ANALYSE 8 · TRANSVERSE 6 · PARAMETRES 4 · CHANTIERS 2 · DEPLOY 2 · DEVIS 2 · DOCUMENTS 2 · CALEPINAGE 1 · FACTURATION 1 · LEAD 1 · SAV 1 · STOCK 1 · aucune tâche d'acceptation posée · PR #1302.
