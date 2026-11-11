# Audit PF6 « lecture des données sensibles » — 2026-11-11 — L2
<!-- dossier-v3 | groupe: ALEC | base: ae5a7ae | fraicheur: 1ea772d | constats: 35 | taches: 40 | decisions: 5 -->

## 1. Charte
| Champ | Valeur |
|---|---|
| Périmètre | parcours PF6 : chaque route de LECTURE (liste, détail, action GET, sérialiseur imbriqué, recherche, agrégat, journal) qui rend un prix d'achat, une marge, une donnée personnelle, une donnée hors portée ou un secret ; lu `backend/django_core/apps/**`, `backend/django_core/core/**`, `backend/fastapi_ia/**`, `frontend/src/**` ; aucune table `PF6.json` |
| Niveau | L2 — argent, données personnelles et jetons sur toute l'application, mais 5 comptes internes en production ; 4 surfaces indépendantes |
| Données | aucune démo (aucune pile ne servait `main`) ; anon : non requis ; prod : non relue, faits du 10/11 repris (voir §2) |
| Critères retenus | C5, C8 |
| Étapes | PF6.1 prix d'achat côté stock, achats, chantiers · PF6.2 prix d'achat et marges côté ventes, client, agent, journaux · PF6.3 données personnelles · PF6.4 portée, journal, secrets (parcours : PF6) |
| NE PAS REFAIRE | groupe ADRG (PF4 : écritures et exports ; ADRG63, ADRG64, ADRG68 à ADRG74, ADRG100) ; ASTK12 ; ASEC85 à ASEC95 ; APFS118 à APFS124 ; APFS28 (lecture du module, D-APFS-4) ; ADOC202 ; étanchéité entre sociétés (PF1) |
| Non-objectifs | écritures et exports (PF4) ; contenu réel de la production ; comptes hérités sans rôle fin ; apps parquées sans route (cpq, ao, veille_ao, fpa, promotions, contrats, compta, mrp, scm, rh, paie, frais, crédit…) |

## 2. Couverture
| Lane | Modèle/effort | Chemins lus | Chemins NON lus (raison) |
|---|---|---|---|
| lecture : prix d'achat stock, achats, chantiers | opus/high | 178 routes de lecture (stock, achats, installations, outillage, pages publiques) ; masques `MasqueMontantsAchatMixin`, `PeutVoirPrixAchat` | réponses des routes d'écriture (vues par la critique) ; 10 apps parquées sans route |
| lecture : prix d'achat ventes, client, transversal | opus/high | 40 sources de coût ou de marge (devis, moteur PDF, portail, API publique, agent SQL, journal d'audit, recherche, explorateur) | inventaire par source de donnée, pas route par route sur tout `ventes` |
| lecture : données personnelles | opus/high | ≈ 95 routes (crm, visites, sav, installations, documents, ventes, facturation, calepinage, monitoring, GED, records, corbeilles, portail, API publique) | portails fournisseur et partenaire (vus par la critique) ; réponses d'erreur 400/409 balayées par grep seulement |
| lecture : portée, multi-société, journal, secrets | opus/high | ≈ 45 couples route × action ; 51 lectures par identifiant, 24 sélecteurs | dette gelée de la garde multi-société relue par échantillon |
| vérificateurs frais (5) | opus/high | un par lecture + un sur les trous de la critique ; rôles livrés recalculés par un script propre à chacun | — |
| seconde lentille | opus/high | le S1 du lien de signature, maillon par maillon, sonde exécutée | essai complet par l'API (pile requise) |
| critique de complétude | opus/high | journal d'audit générique, réponses d'écriture, erreurs, portails externes, notifications, webhooks, agent d'actions | customfields, entites, onboarding, statuspage, monitoring : non relus |
| sondes, rédaction | sonnet/high, opus/high | 24 sondes hôte ; 40 tâches v3 (2 rédacteurs) | — |
Détecteurs : aucun détecteur du dépôt exécuté ; inventaires par scripts Python hors dépôt (gardes, sérialiseurs, registre vivant `apps/roles/permissions_registre.py`) @ae5a7ae · non exécutés : `tests/test_tenant_sweep.py`, `apps/stock/test_astk_garde_prix_achat.py` (aucune pile).
Live : aucun scénario joué · prévus non joués : le rejeu par l'API des tâches P0 et P1 (ALEC40) · sondes : 24 sondes hôte jouées sur le vrai code (bouchons, sans Django), toutes `repro: True`.
Prod (lue le 10/11, non relue) : 5 comptes internes actifs (2 Directeur, 2 Commercial, 1 Commercial responsable) ; 1 compte du portail client ; aucun import. Portées livrées : Commercial = soi ; Commercial responsable et Technicien responsable = sous-arbre ; Technicien et Viewer = équipe.

## 3. Constats
| C-id | Étape | Critère | Grav. | fichier::symbole | Observé → attendu | Sonde | Tâche(s) |
|---|---|---|---|---|---|---|---|
| C-ALEC-001 | PF6.4 | C5 | S1 | `backend/django_core/apps/ged/serializers.py::SignataireDemandeSerializer.get_lien_signature` | tout interne lit le jeton de signature du client et signe à sa place ; le jeton global signe tout un circuit sans code SMS → créateur et admin seuls · 12 rôles · prod : 3 comptes | `docs/audits/sondes/ALEC/C-ALEC-001.py` | ALEC1, ALEC2, ALEC40 |
| C-ALEC-002 | PF6.1 | C8 | S2 | `backend/django_core/apps/stock/views/kit.py::KitProduitViewSet.structure` | coût et marge d'un kit au seul palier responsable → `prix_achat_voir` / `marge_voir` · 6 rôles · prod : 3 comptes | `docs/audits/sondes/ALEC/C-ALEC-002.py` | ALEC3 |
| C-ALEC-003 | PF6.1 | C8 | S2 | `backend/django_core/apps/records/views.py::CommentViewSet` | ancien et nouveau prix d'achat d'un bon de commande fournisseur recopiés au fil ; la liste sans cible les rend à tout interne → exclus sans le droit · 10 rôles · prod : 3 (API) | `docs/audits/sondes/ALEC/C-ALEC-003.py` | ALEC4 |
| C-ALEC-004 | PF6.1 | C8 | S2 | `backend/django_core/apps/stock/views/wms.py::ExpeditionTransporteurViewSet.tarifs` | tarifs de transport sans masque, coût réel masqué → à trancher (D-ALEC-1) · 8 rôles · prod : 3 (écran Expéditions) | `docs/audits/sondes/ALEC/C-ALEC-004.py` | ALEC5, ALEC6 |
| C-ALEC-005 | PF6.1 | C8 | S2 | `backend/django_core/apps/stock/views/negoce.py::AccordRFAFournisseurSerializer` | le masque des remises fournisseur laisse le taux → taux masqué · 6 rôles · prod : 3 (écran RFA) | `docs/audits/sondes/ALEC/C-ALEC-005.py` | ALEC7 |
| C-ALEC-006 | PF6.1 | C8 | S2 | `backend/django_core/apps/installations/views/approbation_bcf.py::ApprobationBCFViewSet` | montant d'achat approuvé à la lecture des chantiers → masqué · 5 rôles · prod : 0 | `docs/audits/sondes/ALEC/C-ALEC-006.py` | ALEC8 |
| C-ALEC-007 | PF6.1 | C8 | S2 | `backend/django_core/apps/installations/views/controle_budgetaire.py::ControleBudgetaireCommandeView` | budget d'achat restant d'un programme à tout interne ; synthèse hors masque → masqué · 10 rôles · prod : 3 si un budget existe | `docs/audits/sondes/ALEC/C-ALEC-007.py` | ALEC9 |
| C-ALEC-008 | PF6.1 | C8 | S2 | `backend/django_core/apps/installations/views/kitting.py::OrdreAssemblageViewSet.cout_soustraitance` | coût de sous-traitance au palier ; création depuis un devis sans contexte : coût prévu non masqué (cause d'ADRG100, autres emplacements) · 3 rôles · prod : 0 | `docs/audits/sondes/ALEC/C-ALEC-008.py` | ALEC10 |
| C-ALEC-009 | PF6.1 | C8 | S2 | `backend/django_core/apps/stock/selectors_entrepot.py::cockpit_entrepot` | total du coût réel des expéditions du jour par transporteur, exact pour une seule expédition → masqué · 6 rôles · prod : 3 (API) | `docs/audits/sondes/ALEC/C-ALEC-009.py` | ALEC11 |
| C-ALEC-010 | PF6.4 | C5 | S2 | `backend/django_core/apps/stock/views/fournisseur.py::FournisseurViewSet.portail_tokens` | jetons du portail fournisseur en clair (factures, solde, confirmation de commande) sans `prix_achat_voir` → réservés · 3 rôles · prod : 0 | `docs/audits/sondes/ALEC/C-ALEC-010.py` | ALEC12 |
| C-ALEC-011 | PF6.2 | C8 | S2 | `backend/django_core/apps/notifications/signals.py::demande_achat_post_save` | « Montant estimé » d'une réquisition dans la notification et l'e-mail aux managers (jumeau d'ACHT16) → masqué · 5 rôles · prod : Commercial responsable | `docs/audits/sondes/ALEC/C-ALEC-011.py` | ALEC13 |
| C-ALEC-012 | PF6.2 | C8 | S2 | `backend/django_core/apps/audit/views.py::object_history` | l'historique d'un devis montre au créateur la marge figée (diff générique) → masquée sans `marge_voir` · 4 rôles · prod : 3 (leurs devis) | `docs/audits/sondes/ALEC/C-ALEC-012.py` | ALEC14 |
| C-ALEC-013 | PF6.2 | C8 | S2 | `backend/fastapi_ia/app/services/sql_agent_service.py::_references_forbidden_column` | l'assistant SQL lit le coût des tickets, les extractions des factures fournisseur (toute la société) et les coordonnées client → colonnes interdites · 10 rôles · prod : si l'assistant répond | `docs/audits/sondes/ALEC/C-ALEC-013.py` | ALEC15 |
| C-ALEC-014 | PF6.4 | C5 | S2 | `backend/fastapi_ia/app/services/sql_agent_service.py::_validate_and_secure` | l'assistant SQL ne filtre que par société : ni droit du module (règle APFS4), ni portée → les deux · 12 rôles · prod : si l'assistant répond | `docs/audits/sondes/ALEC/C-ALEC-014.py` | ALEC16 |
| C-ALEC-015 | PF6.2 | C8 | S3 | `backend/django_core/apps/sav/serializers.py::TicketSerializer` | le coût interne d'un ticket est servi à tout lecteur SAV ; plus aucun écrivain depuis ASEC34 → masqué | STATIQUE | ALEC17 |
| C-ALEC-016 | PF6.3 | C5 | S2 | `backend/django_core/apps/ged/views.py::DocumentViewSet.get_permissions` | GED ouverte à tout interne, sans droit ni portée : factures, PV, pièces d'identité, factures d'énergie → droit du module + portée · 7 rôles · prod : 3 comptes | `docs/audits/sondes/ALEC/C-ALEC-016.py` | ALEC18 |
| C-ALEC-017 | PF6.3 | C5 | S2 | `backend/django_core/apps/documents/views.py::_BaseDocumentView` | PV, BL, attestation (nom, téléphone, adresse) sans droit de module (jumeau d'APFS105) → lecture des chantiers · Commercial terrain, Admin RH · prod : 0 | `docs/audits/sondes/ALEC/C-ALEC-017.py` | ALEC19 |
| C-ALEC-018 | PF6.3 | C8 | S2 | `backend/django_core/apps/tiers/views.py::TiersViewSet` | répertoire des tiers lisible par tout interne : CIN, téléphone, e-mail, adresse, RIB recopiés des clients et fournisseurs → droit + masque + portée · 7 rôles · prod : 3 | `docs/audits/sondes/ALEC/C-ALEC-018.py` | ALEC20 |
| C-ALEC-019 | PF6.4 | C5 | S2 | `backend/django_core/apps/offlinesync/views.py::OfflineOperationViewSet` | le journal hors ligne rend les opérations de tous les utilisateurs (mesures de visite) → les siennes · 5 rôles · prod : rare (coupure réseau) | `docs/audits/sondes/ALEC/C-ALEC-019.py` | ALEC21 |
| C-ALEC-020 | PF6.4 | C5 | S2 | `backend/django_core/apps/reporting/views.py::dashboard` | tableaux de bord sans portée : CA, pipeline, objectif de chaque commercial nommé, plus gros débiteurs → à trancher (D-ALEC-2) · 5 rôles · prod : 3 | `docs/audits/sondes/ALEC/C-ALEC-020.py` | ALEC22, ALEC23, ALEC24 |
| C-ALEC-021 | PF6.4 | C5 | S2 | `backend/django_core/apps/facturation/views/ligne_facture.py::LigneFactureViewSet` | lignes de factures des collègues (2 routes) ; la liste des factures est bornée → portée · 3 rôles · prod : 3 | `docs/audits/sondes/ALEC/C-ALEC-021.py` | ALEC25 |
| C-ALEC-022 | PF6.4 | C5 | S2 | `backend/django_core/apps/sav/maintenance.py::tournee_preventive` | tournée préventive hors portée : client, GPS du chantier, technicien → portée · 5 rôles · prod : 3 si tickets préventifs | `docs/audits/sondes/ALEC/C-ALEC-022.py` | ALEC26 |
| C-ALEC-023 | PF6.4 | C5 | S2 | `backend/django_core/apps/reporting/technicien_scorecard.py::technicien_scorecard` | un technicien lit la fiche de performance d'un collègue (« jamais visible par le technicien ») → réservée · Technicien(s) · prod : 0 | `docs/audits/sondes/ALEC/C-ALEC-023.py` | ALEC27 |
| C-ALEC-024 | PF6.4 | C5 | S2 | `backend/django_core/apps/parametres/views_audit.py::settings_audit_log` | journal des réglages au palier responsable, sans le droit du journal d'activité → à trancher (D-ALEC-3) · 5 rôles · prod : Commercial responsable | `docs/audits/sondes/ALEC/C-ALEC-024.py` | ALEC28 |
| C-ALEC-025 | PF6.4 | C5 | S2 | `backend/django_core/apps/calepinage/selectors.py::restreindre_aux_siens` | réglage éteint, calepinages (nom, ville du lead) de tous les collègues → à trancher (D-ALEC-4) · 3 rôles · prod : selon le réglage | `docs/audits/sondes/ALEC/C-ALEC-025.py` | ALEC29 |
| C-ALEC-026 | PF6.1 | C8 | S3 | `backend/django_core/apps/stock/test_astk_garde_prix_achat.py::cles_interdites` | la garde des prix d'achat ignore `cout`, `marge`, `taux_pct`, `reste_categorie` et les routes des constats 002 à 009 → garde étendue | STATIQUE | ALEC30 |
| C-ALEC-027 | PF6.1 | C8 | S3 | `backend/django_core/apps/stock/views/fournisseur.py::FournisseurViewSet` | frais de livraison estimés, économie de regroupement, caution de matériel consigné sans masque → à trancher | STATIQUE | sans tâche : D-ALEC-5 ouverte |
| C-ALEC-028 | PF6.3 | C8 | S3 | `backend/django_core/apps/crm/serializers.py::pii_masquee_pour` | listes de données personnelles incomplètes : e-mail secondaire, e-mail normalisé, adresse du siège, CIN du client → ajoutés | STATIQUE | ALEC31 |
| C-ALEC-029 | PF6.3 | C8 | S3 | `backend/django_core/apps/crm/clients_views.py::ClientViewSet` | la recherche porte sur téléphone, e-mail, CIN masqués : test d'existence d'un numéro → champs retirés sans le droit | STATIQUE | ALEC32 |
| C-ALEC-030 | PF6.3 | C8 | S3 | `backend/django_core/apps/facturation/recouvrement.py::_releve_data` | relevé client sans masque (jumeau d'APFS27) ; factures rendues sans contexte → masque | STATIQUE | ALEC33 |
| C-ALEC-031 | PF6.3 | C8 | S3 | `backend/django_core/apps/records/serializers.py::ActivitySerializer.get_target_phone` | téléphone de la cible d'une activité sans le droit ; latent (activité assignée à un rôle sans données personnelles) → masqué | STATIQUE | ALEC34 |
| C-ALEC-032 | PF6.3 | C8 | S3 | `backend/django_core/apps/crm/dispatch_views.py::dispatch_file` | file d'attribution en clair ; latent (rôle sans données personnelles placé dans une équipe) → masquée | STATIQUE | ALEC35 |
| C-ALEC-033 | PF6.4 | C5 | S3 | `backend/django_core/apps/ged/views.py::DepotPublicViewSet` | jetons de liens publics (dépôt GED, pages client d'intervention) servis à tout lecteur du module → créateur et admin | STATIQUE | ALEC36, ALEC37 |
| C-ALEC-034 | PF6.4 | C5 | S3 | `backend/django_core/apps/automation/serializers.py::IncomingWebhookTriggerSerializer` | secret et jeton d'un déclencheur entrant relus à chaque lecture (admin seul) → écriture seule | STATIQUE | ALEC38 |
| C-ALEC-035 | PF6.4 | C5 | S3 | `backend/django_core/apps/crm/views_visite.py::lead_photo_toit` | identifiant de visite et calage d'un lead hors portée (l'image reste bornée) → 404 | STATIQUE | ALEC39 |

## 4. Réfutés, requalifiés, fusionnés
| Constat | Verdict | Argument (sonde ou fichier::symbole) |
|---|---|---|
| C-ALEC-001 | élargi (seconde lentille) | la route publique simple accepte une demande à destinataires : le jeton global signe le circuit (`backend/django_core/apps/ged/services.py`), sonde B2 |
| C-ALEC-010 | requalifié S1 → S2 | le POST sous la même garde fabrique un jeton neuf ; la vraie fuite est le montant d'achat sans `prix_achat_voir` |
| C-ALEC-009 | requalifié S3 → S2 | total exact quand une seule expédition ; les totaux voisins (pertes, tableau achats) sont masqués |
| C-ALEC-015 | requalifié S2 → S3 | aucun écrivain de `cout` depuis ASEC34 : seules d'anciennes valeurs sortiraient |
| C-ALEC-031, 032 | requalifiés S2 → S3 | latents : il faut assigner une activité ou une équipe à un rôle sans données personnelles |
| recherche de leads du Technicien responsable | requalifié S2 → §7 | portée sous-arbre : quasi rien ; manque seulement l'octroi D-APFS-4 (`backend/django_core/apps/visites/views.py`) |
| C-ALEC-035 | requalifié S2 → S3 | l'image passe par `VisiteViewSet.photo_toit`, bornée |
| C-ALEC-013 | fusionné | coût des tickets, extractions des factures fournisseur et coordonnées client : une cause (liste de colonnes interdites) |
| C-ALEC-008 | fusionné | sérialiseur sans contexte (`depuis_devis`) ajouté au coût de sous-traitance |
Porte : 0 réfuté en entier / 35 retenus · 7 gravités revues · seconde lentille : 1 S1 → maintenu 1, gravité revue 0, élargi 1.

## 5. Non-risques
| Zone | Preuve | Valide tant que |
|---|---|---|
| surfaces client (PDF, page publique, portail, API publique, webhooks) | listes blanches de champs ; aucun prix d'achat ni marge (`backend/django_core/apps/ventes/quote_engine/`) | les listes blanches restent la seule source |
| portail client, fournisseur, partenaire | chaque lecture bornée au compte connecté (`backend/django_core/apps/portail/views_client.py`) | — |
| étanchéité entre sociétés en lecture | 51 lectures par identifiant revérifient la société | PF1 et ses gardes restent vertes |
| explorateur, couche sémantique, recherche globale | champs sous droit masqués | — |
| salaires, paie, RH, frais, crédit | apps parquées, aucune route | une app se rallume |
| secrets Meta, monitoring, webhooks sortants, clés d'API | écriture seule, hachés ou montrés une fois | — |
| agent d'actions | relaie le jeton de l'appelant : mêmes gardes que la route | le relais garde l'en-tête |

## 6. Décisions
| D-id (`docs/audits/decisions.yml`) | Question (une ligne) | Statut | Tâches |
|---|---|---|---|
| D-ALEC-1 | Un tarif de transport est-il un montant d'achat ? | ouverte | ALEC5, ALEC6 |
| D-ALEC-2 | Les tableaux de bord suivent-ils la portée du rôle ? | ouverte | ALEC22, ALEC23, ALEC24 |
| D-ALEC-3 | Le journal des réglages exige-t-il le droit « Journal d'activité » ? | ouverte | ALEC28 |
| D-ALEC-4 | Le calepinage suit-il la portée du rôle ? | ouverte | ALEC29 |
| D-ALEC-5 | Frais de livraison estimés, économie de regroupement, caution : montants d'achat ? | ouverte | — |

## 7. Optionnel (jamais une tâche)
- Gardes « administrateur » à la place de « voir les prix d'achat » ou « voir la marge » (valorisation, rotation, pertes, inventaire, revalorisation, coût d'un chantier, rentabilités des rapports) — aucun rôle livré touché.
- Marge gardée sous deux codes (générateur et serveur) — les deux vont aux mêmes rôles livrés.
- Recherche de leads du Technicien responsable sans l'octroi de lecture du CRM — portée sous-arbre, presque rien.
- RIB des apporteurs — fonction parquée ; noms des leads dans la corbeille commune ; jeton d'un partenaire sans usage public.
- Extraits du journal pour l'Administrateur (événements de sécurité, paquet de support) ; métadonnées d'archives hors portée.
- Recherche des leads sur téléphone et e-mail masqués (`backend/django_core/apps/crm/views.py::LeadViewSet`, propriétaire crm) : même cause que C-ALEC-029, aucun rôle livré touché.
- Contrats de maintenance de toute la société (piste non vérifiée) ; aucun masque de données personnelles dans les chantiers et le calepinage (tous les lecteurs les portent).

## 8. Limites, non couvert, écarts
- Non couvert : aucune pile ne servait `main` : aucun test exécuté, aucun rejeu par l'API ; les 24 sondes exécutent le vrai code avec des bouchons, deux (assistant SQL) par lecture `ast` faute de `sqlglot`.
- Production non relue : demandes de signature en attente, budgets, tiers, état de l'assistant SQL et du réglage du calepinage.
- Hors périmètre signalé : `backend/django_core/apps/tiers/views.py::TiersViewSet` n'a aucune garde d'ÉCRITURE : tout interne peut modifier le RIB d'un fournisseur au répertoire (effet sur les paiements non vérifié) ; exports `tickets_sav` et `clients` (coût, CIN) : domaine de PF4.
- Écart à la méthode : aucun.
- Incident prod : aucun constaté ; risque ouvert exploitable aujourd'hui : C-ALEC-001 (2 Commercial et 1 Commercial responsable lisent le jeton de signature d'un client dès qu'une demande est en attente) → ALEC1, ALEC2 P0.

## 9. Coût et routage
Coût : H0 S2 O14 F0 · jetons sous-agents ≈ 5,9 M · tâches 40 (M0 2 M1 20 M2 0 M3 11 GATED 7).
Routage : PLAN_AUDIT_STOCK.md 6 · PLAN_AUDIT_ANALYSE.md 5 · PLAN_AUDIT_CHANTIERS.md 5 · PLAN_AUDIT_DOCUMENTS.md 5 · PLAN_AUDIT_LEAD.md 4 · PLAN_AUDIT_SECURITE.md 4 · PLAN_AUDIT_PARAMETRES.md 3 · PLAN_AUDIT_SAV.md 2 · PLAN_AUDIT_FACTURATION.md 2 · PLAN_AUDIT_CALEPINAGE.md 2 · PLAN_AUDIT_DEVIS.md 1 · PLAN_AUDIT_DEPLOY.md 1 ·
acceptation ALEC40 · PR #NUM_PR.
Rapport : un défaut grave, confirmé par deux lectures indépendantes et une sonde exécutée.
- Signature électronique (C-ALEC-001), exploitable aujourd'hui : tout employé qui voit un document lit le lien de signature envoyé au client et peut signer à sa place ; le lien global d'une signature à plusieurs personnes signe tout d'un coup, sans le code SMS. Le document devient « signé », avec un certificat au nom du client. → ALEC1, ALEC2 (P0).
- Ensuite 23 défauts S2 : des coûts d'achat et des marges montrés à des rôles qui ne doivent pas les voir (kits, fil des commandes fournisseur, transport, remises, budgets, historique des devis, notification des réquisitions, assistant SQL) ; une GED et un répertoire des tiers ouverts à tous ; des tableaux de bord, lignes de factures et tournées qui ignorent la portée du commercial.
- 11 S3. 5 questions au fondateur, toutes ouvertes.
