<!-- verifie | groupe: ALEC | pct: 98 | ecarts_s1_s2: 0 -->

# Vérifie ALEC — contre-visite des correctifs du parcours PF6 « lecture des données sensibles », 17/11/2026

Commande `vérifie ALEC` (17/11), due au titre de la contre-visite des correctifs : les trois écarts S1-S2 du 14/11 ont
leurs tâches cochées (ALEC41, 42, 43, 45). Troisième contre-visite du groupe, après celles du 13/11 et du 14/11.
Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `0d834aa12f`. Branche de travail : `verifie-1711`, à jour de `origin/main`.
- **Registre.** PF6 `lecture-sensible`, groupe ALEC : `audit_registre.py --du` (garde d'acceptation neutralisée, §C.4.5 f)
  compte 50 tâches cochées sur 51 constructibles (98 %), « vérifie dû, contre-visite des correctifs (écarts S1-S2 du
  2026-11-14 tous cochés) ». Restent ouvertes : ALEC40 (rejeu des sondes par l'orchestrateur) et ALEC50 (sondes
  périmées, code livré, preuve en direct due).
- **Cochées depuis le 14/11.** 19 tâches : ALEC5, 6, 16, 18, 22, 23, 24, 28, 29, 41, 42, 43 (« code livré, preuve en
  direct due » le 14/11, cochées sur les vagues d'acceptation 6 et 8) ; ALEC45, 46, 47 (tâches d'écart du 14/11) ;
  ALEC48, 49, 51, 52 (relevées par la vague d'acceptation 6, ALEC52 cochée sur preuve en direct le 17/11).
- **Échantillon.** Pas de tirage : relecture complète des 16 tâches non encore relues (toutes sauf ALEC41, 42, 43, déjà
  relues le 14/11, dont seule la régression est recherchée).
- **Méthode.** Lecture des commits, du code de `main`, des tests nommés, des appelants et des jumeaux ; codes des rôles
  livrés lus dans le registre exécuté hors Django. Sondes du dossier rejouées sur l'hôte. Aucune pile, aucun conteneur,
  aucune base, aucun test Django ou FastAPI lancé, aucune production consultée.

## 1. Vérificateurs (1 lot, opus, effort élevé, frais, même répertoire + relecture de l'orchestrateur)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **13** | ALEC5, 6, 16, 24, 28, 29, 45, 46, 47, 48, 49, 51, 52 |
| partiel | **3** | ALEC18, ALEC22, ALEC23 (S3, voir §4) |
| non-fait / faux / régression / déjà-présent | **0** | — |
| sans régression (relues le 14/11) | **3** | ALEC41, 42, 43 |

- **ALEC45 — ok, écart d'origine C-ALEC-VER2-201 fermé.** `phone_key` est dans `_SECRET_COLUMNS` et
  `adsengine_metaleadmirror` dans `_TABLES_LIGNE_SECRETE` (`sql_agent_service.py` l. 932 et 938) : nommée, par `*`,
  `alias.*`, référence de ligne (`m::text`) ou en filtre `WHERE`, la colonne est refusée ; `COUNT(*)` reste toléré.
  Le test nommé joue `None`, Commercial et Directeur du registre ; le mutant « retirer `phone_key` » le fait échouer.
  `phone_key` est la seule colonne personnelle du modèle `MetaLeadMirror` (champs relus).
- **ALEC46 — ok, écart C-ALEC-VER2-202 fermé.** Entrée `("adsengine_", ("adsengine_",))` dans `_MODULE_DES_TABLES`
  (l. 1076). Les rôles qui lisent les miroirs ont tous `adsengine_view` au registre (même droit qu'à l'écran).
- **ALEC47 — ok, écart C-ALEC-VER2-203 fermé.** `LeadViewSet.filter_backends` porte `_RechercheSansPii`
  (`crm/views.py` l. 182). Jumeaux relus : recherche du copilote (`views_assistant.py::_leads_trouves`, même règle),
  recherche globale (`reporting/search.py`, téléphone et e-mail réservés à `client_pii_voir`), export des leads
  (colonnes e-mail, téléphone, WhatsApp retirées). L'export des CLIENTS garde la CIN : constat 302.
- **ALEC51 — ok.** `RefusDeDroit` (l. 588) porte les refus de portée, de module, de colonne confidentielle et de donnée
  personnelle ; le motif part au modèle, les SQL illisibles ou d'écriture gardent `_UNSAFE_QUERY_REPLY`. Le test nommé
  joue le Commercial, le Technicien et le Directeur du registre ; aucun SQL exécuté sur refus.
- **ALEC52 — ok.** `_apply_tenant_guc` pose un listener `begin` (`set_config(..., true)`) sur le moteur Postgres, sans
  condition sur `POSTGRES_RLS_ENABLED`, avant l'inspection de `_base_sql` (l. 1531-1535) ; un moteur neuf par question
  (`create_sql_agent_engine`), donc aucun listener d'un autre appelant. Les cinq tests `TenantGucTests` couvrent le
  drapeau absent, la portée transactionnelle, la valeur de l'appelant et l'ordre GUC → inspection → base.
- **ALEC48, ALEC49 — ok.** `useCanLireInterventions` conditionne les appels `bin-locations` (Expéditions, Qualité) et
  le montage des deux sections chantiers d'Avancé ; describes « ALEC48 » et « ALEC49 » présents.
- **ALEC5, 6, 16, 24, 28, 29 — ok.** Code et tests conformes au texte, tests nommés inchangés depuis leur commit.
  ALEC24 laisse un jumeau ouvert (`crm/equipes/statistiques/`, constat 304).
- **ALEC18 — partiel.** `ged/documents/` et ses jumeaux passent sous `LectureDuModule` ; les validations OCR et les
  annotations restent en `IsAnyRole` (constat 305), bornées aux documents visibles.
- **ALEC22, ALEC23 — partiel.** Totaux, montants et classement bornés ; les compteurs et taux d'acceptation de la
  période restent ceux de la société (constat 303).
- **Régression.** Fichiers produits des 19 tâches comparés entre le commit de chaque tâche et `0d834aa12f` : aucun
  changement ne défait une garde (les retouches d'ADRG75, ALEC42 et ALEC48 resserrent).

## 2. Tests nommés

Les tests nommés des 16 tâches relues existent et sont comportementaux : vrais appels HTTP (Django) ou appel direct de
la garde avec les codes du registre livré (FastAPI). Aucun test ALEC affaibli depuis le 14/11. Les tests de
`backend/fastapi_ia` ne tournent pas sur l'hôte (sqlglot absent) : leur preuve est la CI de `main` et les rejeux à
modèle réel des vagues 6 et 8 (runs 43990845499, 44032890904, 44051270319).

## 3. Sondes

- **Rejouées sur l'hôte (27).** Ne reproduisent plus : 004, 006, 011, 013, 014, 016, 020, 024, 025, VER1-102.
  La sonde 003 affiche encore « reproduit » : faux positif déjà relu le 14/11. Plantent à l'extraction ou faute de
  Django : 001, 002, 005, 007 à 010, 012, 017 à 019, 021 à 023.
- **101 et 201 cassées par ALEC51.** Elles injectent `SQLSecurityError` mais pas `RefusDeDroit` dans le corps extrait de
  `_verifier_module_et_portee` (`NameError`). Rejouées avec ce seul nom ajouté au bouchon, sans autre modification :
  101 ne reproduit plus (ALEC41) ; 201 ne reproduit plus (ALEC45, ALEC46 : Commercial terrain, Admin RH et Admin Ventes
  refusés « module », `phone_key` gardée).
- **Sonde nouvelle 301, reproduit (`repro: true`).** Le vrai corps de `_verifier_module_et_portee` laisse l'Utilisateur
  livré (`installation_voir`, aucune portée, aucun code d'écriture) lire `lien_client_token` et `lien_rapport_token`
  sur `installations_intervention`, que l'écran ne sert plus (ALEC37) et que l'action `lien-rapport` lui refuse ;
  `adresse_siege` n'est dans aucune liste gardée alors que l'écran client la masque (ALEC31).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ALEC-VER3-301 | ALEC37, ALEC31, ALEC15 | S3 | `sql_agent_service.py::_references_forbidden_column` ne garde ni `lien_client_token` / `lien_rapport_token` (rôle livré Utilisateur, qui n'obtient pas ces liens par l'écran) ni `adresse_siege` (latent : aucun rôle livré n'a `crm_*` sans `client_pii_voir`) | `docs/audits/sondes/ALEC/C-ALEC-VER3-301.py` | ALEC53 |
| C-ALEC-VER3-302 | ALEC47, ALEC32 | S3 | `crm/exports.py::export_clients_xlsx` retire e-mail, téléphone et adresse sans `client_pii_voir`, pas la CIN (latent : tout porteur livré de `crm_export` a le droit) | STATIQUE (lecture de `CLIENT_EXPORT_PII_HEADERS`) | ALEC54 |
| C-ALEC-VER3-303 | ALEC22, ALEC23 | S3 | `reporting/views.py::dashboard` (taux) et `ventes/dashboard_view.py::dashboard_quote_to_cash` sans `?mine=1` (envoyés, acceptés, taux, conversion) comptent toute la société pour un Commercial ; ni montant ni client | STATIQUE (lecture des appels de `taux_acceptation_periode`) | ALEC55 |
| C-ALEC-VER3-304 | ALEC24 | S3 | `crm/clients_views.py::equipes_statistiques` sert à un Commercial (`IsResponsableOrAdmin` franchi par `crm_creer`) le CA signé, la cible et le pipeline de chaque équipe ; une équipe d'un membre revient au chiffre d'un collègue | STATIQUE (lecture de `stats_equipe`) | ALEC56 |
| C-ALEC-VER3-305 | ALEC18 | S3 | `ged/views.py::ValidationOcrDocumentViewSet` et `AnnotationDocumentViewSet` lisent en `IsAnyRole` : Commercial terrain et Utilisateur, sans code `ged_*`, lisent extractions OCR et annotations des documents internes visibles | STATIQUE (lecture des `get_permissions`) | ALEC57 |

Écarts S1-S2 comptés au marqueur : 0 nouveau ; 0 d'origine ouvert. C-ALEC-VER2-201 (ALEC45), C-ALEC-VER1-101 (ALEC41)
et C-ALEC-VER1-102 (ALEC42, ALEC43) sont fermés et leurs tâches cochées ; les S3 C-ALEC-VER2-202 (ALEC46) et
C-ALEC-VER2-203 (ALEC47) aussi.

## 5. Optionnel (non déposé)

- Rafraîchir les bouchons des sondes 101 et 201 (`RefusDeDroit`) et des sondes qui plantent (extraction, Django) ; la
  sonde 003 reste un faux positif.
- ALEC23 : la cellule « Devis actifs » d'un collègue s'affiche vide au lieu de « — » (`QuoteToCashPage.jsx`).
- ALEC5 : les offres de transport restent triées par coût, l'ordre révèle le classement relatif des tarifs.
- ALEC22 : le rang du classement révèle l'ordre des CA des collègues ; le rapport planifié « sales » et les tickets SAV
  de `field_service_report` ne sont pas bornés à la portée.
- ALEC16 : un rôle fin sans aucun code est traité comme sans restriction ; `authentication_customuser` et
  `ia_ocr_document` n'ont pas de garde de module (annuaire ; prix déjà gardé).
- ALEC18 : les autres lectures rattachées à un document (liens, approbations, partages) restent en `IsAnyRole`,
  bornées par `document_ids_visibles` ; à relire avec ALEC57.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 16 tâches cochées depuis le 14/11 jamais relues ; régression sur ALEC41, 42, 43 ; jumeaux de
  l'assistant SQL (toutes les tables de `_ALLOWED_TABLES` relues champ par champ contre les masques des écrans : données
  personnelles, jetons publics, prix d'achat, coûts, marges, RIB), de la recherche des leads (clients, copilote,
  recherche globale, exports) et des tableaux de bord.
- **Non couvert.** Aucun test Django, FastAPI ou front lancé ; aucun rejeu navigateur ni pile ; le comportement réel de
  sqlglot 30.30 sur les contournements par nom (identifiants `U&"…"`, notations exotiques) n'est pas exécuté, la garde
  est relue sur l'arbre attendu ; la sonde 301 bouchonne le parseur.
- **Statut.** Zéro écart S1-S2 (nouveau ou d'origine ouvert) : premier `vérifie` à zéro du groupe. La sortie du cycle
  exige un second `vérifie` consécutif à zéro S1-S2 ; il contre-visitera ALEC53 à ALEC57 une fois cochées.

## 7. Coût

- 1 vérificateur (opus, effort élevé) et 1 rédacteur ; aucun appel Fable.
