<!-- verifie | groupe: ASUP | pct: 100 | ecarts_s1_s2: 0 -->
# Vérifie ASUP — contre-visite des correctifs du parcours PF10 « suppression et archivage », 17/11/2026

Commande `loop audit` (17/11). Le registre compte 49 tâches cochées sur 49 constructibles (100 %) et annonce « vérifie dû,
contre-visite des correctifs (écarts S1-S2 du 2026-11-14 tous cochés) ». Périmètre : les correctifs livrés depuis le 14/11
et ce qu'ils ont pu casser. Rien n'a été construit, ni committé, ni déployé ; aucune pile, aucun conteneur, aucune base.

- **Les cinq écarts S1-S2 du 14/11 sont fermés sur `origin/main`**, et leurs tâches (ASUP57 à 63) sont cochées.
- **Question centrale tranchée dans le code** : après « Anonymiser (RGPD) », chaque pièce fiscale ou comptable imprime
  l'acheteur figé à l'émission (§3). Les documents non fiscaux montrent le client anonymisé.
- **Aucun nouvel écart S1-S2.** Un S3 (corbeille : le nom d'un lead anonymisé survit dans deux recoins), un S3 d'outillage
  (sonde VER2-101 toujours aveugle), deux S4 optionnels.
- **Sortie de cycle : premier `vérifie` à zéro S1-S2.** Le prochain `vérifie` à zéro ferme le cycle.

## 0. Préconditions

- **SHA.** Branche `verifie-1711` = `origin/main` = `0d834aa12` (`git fetch` puis `git log HEAD..origin/main` : vide).
- **Registre.** `audit_registre.py` (acceptation neutralisée, §C.4.5 f) : « ASUP : 100 % cochées (49/49) ». ASUP66 reste
  `[BLOCKED: code livré, preuve en direct due]`, hors dénominateur.
- **Échantillon.** Toutes les tâches cochées depuis le 14/11 : ASUP4, 5, 6, 12, 13, 14, 17, 18, 44, 45, 48, 56 à 65 et 67
  (commits `d074883dc`, `1875e95bb`, `2f8bab8f9`, vagues 6 à 8). Toutes les tâches d'écart du 14/11 (ASUP57 à 63) y sont.
- **Acceptation.** `python scripts/check_acceptation.py --groupe ASUP` : « 31 cochée(s) à preuve, 31 couverte(s), 0 non
  couverte(s) (dette 0) ». Enregistrements du 14/11 (`ff2ba7f2d`, ASUP63) et du 17/11 (`00d1e8a37`, `143163b1e`).
- **Méthode.** Commits et tests nommés lus ; `git diff a12f40f82..HEAD` sur les 46 fichiers de code des tâches ASUP4 à 62 ;
  relevé par grep des lecteurs de l'identité client ; sondes hôte rejouées (§4) ; rendu hors dépôt des vrais gabarits.

## 1. Vérificateurs (1 lot, orchestrateur, opus, effort élevé)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **21** | ASUP4, 5, 6, 12, 13, 14, 17, 18, 44, 45, 48, 56, 57, 58, 59, 61, 62, 63, 64, 65, 67 |
| ok, caduque | **1** | ASUP60 : sa route ne sert plus les compteurs (ASUP64, D-ASUP-7 = retirer) |
| partiel / non-fait / faux / régression | **0** | — |

- **ASUP63** (`c4d84ea3e`) : les cinq lectures `getattr(<pièce>.client, 'nom' / 'ice')` de `ventes/exports.py` passent par
  `acheteur_de_la_facture` (avoir et note de débit : la facture d'origine). Test
  `ventes/tests/test_journal.py::TestJournalExport::test_exports_gardent_l_acheteur_fige_apres_anonymisation` : vraie route
  `anonymize`, journal xlsx, export comptable csv, grand livre csv, trois pièces ; échoue si un lecteur revient au client.
- **ASUP57** : gabarits `avoir.html` et `note_debit.html` et générateurs inchangés depuis le 14/11. Rendu des vrais gabarits
  avec le contexte de `generate_*_pdf` après le vrai `anonymiser_client` : nom, ICE, IF, RC et adresse d'origine imprimés,
  jamais « anonymisé » (même résultat pour `facture.html`).
- **ASUP64** (`840ad061d`) : `attention-summary` ne sert plus que `approbations` ; lecteur unique
  `frontend/src/hooks/useApprobationsCount.js` (champ `approbations`). Le test d'ASUP60 est remplacé par
  `test_seules_les_cles_lues_sont_servies`.
- **ASUP65** (`23ba51b21`) : `python -m unittest scripts.tests.test_check_acceptation` → 30 tests OK, dont le refus d'un PASS
  à `corps: FAIL`.
- **ASUP67** (`b12224315`) : `trash.on_lead_erased` caviarde l'entrée ACTIVE du lead ; test
  `trash/tests.py::JournalisationTests::test_lead_anonymise_libelle_caviarde` (voisin non touché, restauration). Jumeaux
  non traités : §4, C-ASUP-VER4-400.
- **ASUP4 à 62 (sauf 57, 60)** : depuis `a12f40f82`, six de leurs fichiers ont bougé : `notifications/views.py` et son
  test (ASUP64), `ventes/utils/pdf.py` (ACEL92 : reprise du routage GED, acheteur intact), `crm/golden/services_split_ast.json`
  (empreintes), et `authentication/views.py::_traces_du_compte` avec son test (TCH18 : les modèles de `taches`, données
  personnelles en CASCADE, ne comptent plus comme traces). Compatible avec D-ASUP-2 : `ReglagesSociete.modifie_par` reste
  SET_NULL ; le test d'ASUP5 est étendu. Aucun ne retire un comportement exigé.
- **ASUP59** : `records/views.py` action `mine` filtrée par `sans_cibles_archivees` ; ses deux lecteurs (page
  `MesActivitesPage.jsx`, widget `ActivityFeedWidget.jsx`) sont couverts — le point « non vérifié » du 14/11 est levé.

## 2. Tests nommés

- Tous les tests cités au §1 existent et sont comportementaux (vraies routes, relecture en base ou du fichier rendu).
- Lancés ici : `scripts.tests.test_check_acceptation` seulement (30 OK). Aucun test Django lancé (pas de pile) ; la seule
  preuve d'un vert Django est la CI de `main` et les runs d'acceptation cités par les enregistrements.

## 3. Question centrale : l'acheteur reste-t-il figé sur chaque pièce ?

Relevé par grep des lecteurs de `client.nom` / `.ice` / `.adresse` (Python et gabarits) dans `apps/ventes`,
`apps/facturation`, `apps/reporting`, `apps/einvoice`, `apps/fiscal` et `templates/pdf` ; `apps/compta` n'a aucun lecteur.

| Document ou export | Lit | Verdict |
|---|---|---|
| Facture, acompte (PDF stocké ou re-rendu) | `acheteur_de_la_facture` (`utils/pdf.py`, `facture.html`) | figé |
| Avoir, note de débit (PDF) | acheteur de la facture d'origine (ASUP57) | figé |
| UBL / export DGI, validateur DGI | `acheteur_de_la_facture(origine or facture)` | figé |
| Journal des ventes, export comptable xlsx/csv, grand livre xlsx/csv | `acheteur_de_la_facture` (ASUP63) | figé |
| Export QuickBooks (.iif) | lignes du grand livre, colonne tiers non exportée | aucun nom imprimé |
| Export xlsx asynchrone (> 2 000 lignes) | mêmes constructeurs (`_XLSX_BUILDERS`) | figé |
| Quittance, relevé de compte, BC client, BL, PV, attestation, dossier de remise | client vivant | « anonymisé » (non fiscal) |
| Lettre de relance, dossier contentieux, balance âgée | client vivant | « anonymisé » — question au fondateur (§5) |
| Listes et fiches facture, recherche, analyses | `client.nom` vivant (`client_nom` des sérialiseurs) | « anonymisé » |
| Métadonnée GED `client` d'un PDF re-rendu | `<pièce>.client.nom` vivant | non fiscal, conforme |

Jumeaux : un **fournisseur** effacé ne perd que son contact (`stock/dsr_provider.py::erase_stock` garde raison sociale et
identifiants légaux) ; un **lead** n'apparaît sur aucune pièce fiscale ; un **utilisateur désactivé** garde son nom (D-ASUP-2).

## 4. Écarts

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâches |
|---|---|---|---|---|---|
| C-ASUP-VER4-400 | ASUP67 | S3 | (C17) Nom d'un lead anonymisé gardé : (a) entrées restaurées (`apps/trash/services.py::caviarder_lead_anonymise`, filtre `restaure_le__isnull=True`), lisibles 30 j dans `/parametres/corbeille` ; (b) `DeletionRecord.label` (`core/models.py::SoftDeleteModel`), servi par `core/views.py::TrashViewSet` | STATIQUE | ASUP68 |
| C-ASUP-VER4-401 | ASUP57 | S3 | (C10) La sonde `docs/audits/sondes/ASUP/C-ASUP-VER2-101.py::sonde` est toujours périmée : elle rend les gabarits sans la clé `acheteur` et ne conclut que sur la présence de cette clé dans le générateur ; un gabarit revenu à `avoir.client.*` laisserait `repro: False` | STATIQUE (rejouée, §4) | ASUP69 |
| C-ASUP-VER3-100 | ASUP63 | S2 | Rappel du 14/11 : **fermé** — sonde `repro: False`, les quatre lecteurs ne lisent plus le client vivant | `C-ASUP-VER3-100.py` | ASUP63 (cochée) |
| C-ASUP-VER2-101 | ASUP57 | S1 | Rappel : **fermé** (rendu des vrais gabarits, §1) | VER2-101 périmée (VER4-401) | ASUP57 (cochée) |
| C-ASUP-VER2-102 | ASUP45 | S2 | Rappel : **fermé** (ASUP59 ; ASUP60 caduque, route retirée par ASUP64) | STATIQUE | ASUP59, 60 (cochées) |
| C-ASUP-VER2-104 | ASUP12 | S2 | Rappel : **fermé** (`Lead.all_objects.filter(client=client)` dans `anonymize`) | STATIQUE | ASUP62 (cochée) |
| C-ASUP-VER2-105 | ASUP42 | S2 | Rappel : **fermé** (code inchangé depuis le 14/11) | STATIQUE | ASUP58 (cochée) |

**Sondes rejouées sur l'hôte (17/11, `0d834aa12`).**
- `C-ASUP-VER3-100.py` : `repro: False` ; après anonymisation, facture, avoir et note de débit portent `SARL Exemple` et
  son ICE ; `fonctions_qui_lisent_le_client_vivant` toutes `False`. Fidèle au code.
- `C-ASUP-VER2-101.py` : `repro: False` mais pour une mauvaise raison (son HTML imprime encore « Client anonymisé #12 »,
  ICE absent) → C-ASUP-VER4-401.

**VER4-400, gravité S3.** Le cas (a) suppose suppression, restauration puis anonymisation dans les 30 jours ; le cas (b)
n'a aucun écran (seul `crmApi.js` appelle `core/corbeille/<id>/restaurer/`). Seul le nom survit : la suppression réelle
d'un lead (`crm/views.py`) ne passe pas de `donnees`. ASUP67 avait classé (b) « autre geste » sans ouvrir de tâche.

**Routage.** `check_ownership.py --owner-of` : `apps/trash/services.py`, `apps/trash/tests.py`, `core/models.py` →
securite (ASUP68 dans `PLAN_AUDIT_SECURITE.md`) ; la sonde n'a pas de propriétaire, ASUP66 (même nature) vit dans
`PLAN_AUDIT_DEPLOY.md` → ASUP69 y va.

## 5. Optionnel (non déposé)

- **S4 — calepinage archivé.** `anonymiser_calepinage` vide `titre`, mais l'entrée de corbeille d'un calepinage archivé
  garde `libelle=str(calepinage)` = l'ancien titre (`calepinage/services/archivage.py`). Seulement pour un titre SAISI avec
  un nom (le défaut est vide depuis ACAL300), et 30 jours au plus.
- **S4 — spec d'acceptation périmée.** `frontend/e2e/acceptation/asup7.spec.js`, étape PF10.2-ASUP60, lit
  `s.en_retard` / `s.aujourdhui`, retirés par ASUP64 : un rejeu échouerait. Signalé « hors Files » par le commit d'ASUP64.
- **Question au fondateur, toujours ouverte** (aucune décision dans `decisions.yml`) : refuser « Anonymiser (RGPD) » tant
  qu'une créance est ouverte ou un dossier contentieux actif ? Sans garde, lettre de relance, dossier contentieux et balance
  âgée impriment « anonymisé », sans adresse. À ouvrir par un audit.
- **Brouillons et remise en brouillon.** `facture_cycle.py` remet `identite_acheteur = None` sur une facture émise jamais
  envoyée ; réémise après anonymisation, elle fige l'identité effacée (refusée en B2B faute d'ICE, CIQ217). Inchangé.
- **`identite_acheteur` servie par l'API facture** (nom, ICE, adresse, e-mail, téléphone d'origine), lue par aucun écran :
  c'est la pièce telle qu'émise ; à noter pour l'export d'accès d'un client effacé.

## 6. Couverture et sortie de cycle

- **Couvert.** Les 22 tâches cochées depuis le 14/11 ; diff de leurs fichiers depuis la base du 14/11 ; relevé des lecteurs
  d'identité client (fiscal et non fiscal) ; corbeilles transverse et `core` ; deux sondes hôte ; un rendu hors dépôt.
- **Non couvert, faute de pile.** Aucun test Django, aucun rejeu navigateur, aucune sonde sous Docker ; la preuve en direct
  d'ASUP66 reste due ; VER4-400 est établi par lecture du code, pas par un rejeu.
- **Statut.** Zéro écart S1-S2 nouveau, zéro écart d'origine dont la tâche reste ouverte : le marqueur porte 0. C'est le
  **premier** `vérifie` consécutif à zéro S1-S2 ; le groupe sort du cycle au prochain `vérifie` à zéro (§C.4.3).
- **Suite.** Construire ASUP68 et ASUP69 (S3, ne retiennent pas le cycle) ; jouer la preuve d'ASUP66 ; poser au fondateur
  la question de la créance ouverte.

## 7. Coût

- 1 orchestrateur (opus, effort élevé), aucun sous-agent. Jetons non mesurés ici.
- Aucun appel Fable.
