# Vérifie ADRG — quatrième contre-visite du parcours PF4 « droits de la grille », 18/11/2026

<!-- verifie | groupe: ADRG | pct: 99 | ecarts_s1_s2: 1 | faits: 128 -->

Contre-visite des correctifs du groupe ADRG (audit de parcours PF4 du 10/11, dossier `2026-11-10-parcours-PF4.md`), due à
95 % (`audit_registre.py --du` : 128 tâches cochées sur 129 constructibles, « contre-visite des correctifs, écarts S1-S2 du
2026-11-17 tous cochés »). Elle suit les contre-visites du 13/11, du 14/11 et du 17/11 (`2026-11-17-droits-grille-verifie.md`).
Son but premier : dire si les deux écarts S2 du 17/11 (ADRG146, ADRG147) sont fermés sur TOUS les chemins qui font sortir
une requête enregistrée, puis relire les tâches S3 ADRG148 à 155. Rien n'a été construit ni déployé ; aucune base, aucun
conteneur, aucune production n'a été lu.

## 0. Préconditions

- **SHA.** `origin/main` = `bc1eca567` (PR #1461). Branche de claim : `verifie-1811`.
- **Registre.** PF4 `droits-grille`, groupe ADRG, 128 tâches cochées sur 129 constructibles (99 %). Restent ouvertes ADRG140
  (bloquée : aucune route ne liste les collègues au palier limité) et la tâche d'acceptation ADRG105.
- **Cochées depuis le 17/11 : 10.** ADRG146 et ADRG147 (écarts S2 du 17/11), ADRG148 à ADRG154 (S3 du 17/11) et ADRG155
  (ouverte le 17/11 au rejeu d'ADRG150, écart déclaré). Commits : `4f725d95c` (146), `c33a93316` (147), `c74e14584` (148),
  `d0c1f8310` (149), `4fdb3eb8f` (150), `7e9356b99` (151), `105a54f1e` + `a440a3d58` (152), `bd001a688` (153),
  `63c5d45e7` (154), `c5a0b0705` (155).
- **Échantillon : les 10** (contre-visite des correctifs, METHODE §C.4-6 : toutes les tâches d'écart, S2 d'abord).
- **Méthode.** Lecture des commits, du code servi sur `origin/main` et des tests nommés ; rôles livrés recalculés en Python
  pur sur `CANONICAL_SYSTEM_ROLES` / `PERMISSION_MODULE` ; jumeaux cherchés par grep (appelants de `run_query`,
  `exiger_export_dataset`, `executer_dashboard`, `rendre_rapport`) ; enregistrements d'acceptation rapprochés ; sondes hôte
  jouées. Aucun test Django ni vitest lancé ; `scripts/sonde.py` refuse sans Docker, les sondes ont été jouées en import
  direct de leur `sonde()`.

## 1. Verdicts

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **9** | ADRG147, 148, 149, 150, 151, 152, 153, 154, 155 |
| partiel | **1** | ADRG146 |
| non-fait / faux / régression / déjà-présent | **0** | — |

**Écarts S2 d'origine.**
- C-ADRG-VER3-360 (ADRG146) : **fermé** pour les widgets à jeu. `SavedReportSerializer.validate` exige
  `exiger_export_dataset` pour chaque widget portant `dataset`, à toute écriture ; `rendre_dashboard_html` le rejoue au nom
  du propriétaire et rend le widget refusé en bloc d'erreur. Le jumeau « widget de métrique nommée », que la tâche
  laissait « à vérifier au build », ne l'a pas été (S3, §4) : d'où « partiel » (L6).
- C-ADRG-VER3-361 (ADRG147) : **fermé.** La condition de partialité est retirée ; un PATCH `{"recipients": …}` d'un rapport
  `query` rejoue la garde de l'acteur.

**Les chemins de sortie, un par un** (pour les genres `query` et `dashboard`) :

| Chemin | Garde | Au nom de |
|---|---|---|
| Création d'un envoi programmé | `validate` → `exiger_export_dataset` | l'acteur |
| Modification (PUT, PATCH partiel, changement de cible ou de canal) | idem, à chaque écriture | l'acteur |
| Exécution par la tâche planifiée `reporting.email_saved_reports` | `_rendre_saved_query` / `rendre_dashboard_html` | le propriétaire, rôle relu à l'envoi |
| Lien public (`rapport_partage_public`, lien WhatsApp) | même rendu (`rendre_rapport`) | le propriétaire |
| Téléchargement direct d'un rapport programmé | aucune route (seul le lien public rend un `SavedReport`) | — |
| Partage d'une requête ou d'un tableau à un collègue | lecture seule (`run`, `donnees` : JSON) ; programmer → `validate` | l'acteur |
| Duplication d'un rapport d'autrui | aucune route ; une création sur la cible d'autrui passe par `validate` (cible visible exigée, ADRG124) | l'acteur |
| API v1 (`apps/publicapi`) | n'expose ni requête, ni tableau, ni rapport programmé (grep : 0) | — |
| Export d'une définition de rapport (`rapport-definitions/<id>/export/`) | `exiger_export_dataset` (ADRG76) | le lecteur |
| Extrait planifié (`scheduled-exports`) | `validate_dataset` + `_cause_suspension` (APFS103) | le créateur |

**Par jeu de données.** La garde est générique : le code `*_export` du module du jeu (`codes_du_module`). Les 11 jeux
enregistrés relèvent de 5 modules qui ont chacun un code d'export : `stock_produits`, `stock_mouvements`, `stock_bcf`
(achats fournisseurs) → `stock_export` ; `ventes_devis`, `ventes_factures`, `ventes_paiements` → `ventes_export` ;
`crm_leads`, `crm_clients` (données personnelles) → `crm_export` ; `chantiers` → `installation_export` ; `sav_tickets`,
`sav_contrats` → `sav_export`. Les champs sous permission (prix et valeur d'achat, montant des commandes fournisseurs) sont
retirés en plus par `spec_sans_champs_gated`.
Deux sorties échappent à la règle : le **propriétaire désactivé** (S2, §4) et le **widget de métrique** (S3, §4).

**Rôle changé depuis la création.** Couvert : le rendu relit `report.owner.role.permissions` à chaque envoi. Un Commercial
responsable qui perd `stock_export` ne reçoit plus de fichier (`_rendre_saved_query` → `None`, journal `echec`).

## 2. Tests nommés

- ADRG146 : `apps/reporting/tests_ntdata37_abonnement_dashboard.py::AbonnementDashboardTests::test_dashboard_avec_widget_stock_exige_stock_export`
  — création (403 / 201, compte relu, liste relue) ET rendu (widget ajouté après la création, nom du produit absent, bloc
  d'erreur). Il échoue si l'une des deux gardes saute (mutants déclarés dans le commit, structure du test conforme).
- ADRG147 : `…::test_patch_destinataires_d_une_requete_stock_exige_stock_export` — PATCH refusé, destinataires relus
  inchangés, PATCH du Directeur accepté. Échoue si la condition de partialité revient.
- **Non couverts par un test** (aucun ne casserait si la garde sautait) : le PATCH d'un rapport `dashboard` (le code n'a pas
  de condition de partialité, mais aucun test ne le joue) ; le lien public d'un rapport `query` ou `dashboard` refusé
  (passe par le même rendu, testé au niveau de la fonction seulement) ; le canal WhatsApp.
- ADRG148 à 155 : un test vitest par tâche, rouge d'abord déclaré, store par rôle (`SuiviGpsPage.test.jsx`,
  `ParcInstallePage.droits.test.jsx`, `ListView.acht64.test.jsx`, `InstallationDetail.acht.test.jsx`,
  `PlanificationPage.test.jsx`, `MaJourneePage.test.jsx`, `LeadsPage.droits.test.jsx`, `GedDocumentInsights.test.jsx`,
  `TicketAdvancedPanel.test.jsx`, `TicketCalendarView.test.jsx`, `RecurrencesInterventionSection.test.jsx`).
- Acceptation : `docs/audits/acceptation/ADRG/2026-11-18-ed9668a67.md` et `2026-11-18-d755807e3.md` (PASS, `couvre:`
  ADRG147 à 155, sans écart) ; ADRG146 « API seulement ».

## 3. Sondes

| Sonde | Tâche | Verdict | Observé (hôte, `bc1eca567`) |
|---|---|---|---|
| `C-ADRG-VER2-200.py` (14/11) | ADRG123 | réfutée | `repro: false` (création et rendu `query` lisent le droit d'export) |
| `C-ADRG-VER3-360.py` (17/11) | ADRG146 | **réfutée** | `validate_export_seulement_sous_query: false`, `rendu_dashboard_lit_le_droit_export: true` |
| `C-ADRG-VER3-361.py` (17/11) | ADRG147 | **réfutée** | condition = `kind == SavedReport.TargetKind.QUERY` ; garde jouée sur `patch_recipients: true` |
| `C-ADRG-VER4-400.py` (neuve) | chemin d'ADRG146-147 | **REPRO** | aucun des 11 sites du chemin d'envoi ne lit `is_active` ; garde d'export ignorée au palier administrateur (Directeur, Administrateur) ; témoin `_cause_suspension` : lit `is_active` |
| `C-ADRG-002` à `017`, `021`, `055`, `056` (10/11) | origine | réfutées | `repro: false` (19 sondes) |
| `C-ADRG-001`, `053`, `054` | origine | non jouées | exigent le contexte Django (`ctx`) ou une base |
| `C-ADRG-018`, `019`, `020`, `022` | origine | non concluantes | `NameError` à l'import direct (gardes renommées depuis le 10/11) : périmées, closes par les contre-visites du 13 et du 14/11 |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ADRG-VER4-400 | ADRG146, ADRG147 | **S2** | Un envoi programmé continue de partir, par e-mail et par lien public, après la désactivation de son propriétaire. `scheduled_reports.py::email_saved_reports` et `::rendre_rapport` ne lisent jamais `owner.is_active` ; la revérification au rendu (`data_explorer.py::exiger_export_dataset`) ne lit que les codes du rôle et rend la main sans condition à tout palier administrateur ; les genres figés ne lisent aucun droit. Le jumeau `core/scheduled_export.py::_cause_suspension` (APFS103) suspend l'extrait d'un créateur désactivé. | `C-ADRG-VER4-400.py` (REPRO) | ADRG156 |
| C-ADRG-VER4-401 | ADRG146 | S3 | Un widget de métrique nommée (`{"type": "metrique", "metrique": <clé>, "group_by": […]}`) n'a pas de `dataset` : `validate` et `rendre_dashboard_html` le laissent passer, et `dashboard_data.py::executer_dashboard` exécute le jeu de la définition, regroupé par le `group_by` du widget, au nom du propriétaire, en lecture seule. Aucune métrique livrée n'expose un rôle livré (seule `mrr` porte un jeu, `sav_contrats`, et tous les rôles qui programment ont `sav_export`). | STATIQUE (lecture) | ADRG157 |

**Gravité de VER4-400 : S2.** Les rapports d'un compte parti (adresses saisies librement, lien public de 7 jours relayé par
WhatsApp) partent chaque semaine sans limite de durée, quel que soit le jeu (clients, ventes, stock). Les décisions
fondateur gardent les comptes à traces désactivés et non supprimés (D-ASUP) : la désactivation est LE geste de départ, et
la règle existe déjà pour l'extrait planifié. Ce n'est pas un S1 : les destinataires ont été choisis par le propriétaire
quand il était actif ; l'écart prolonge un envoi, il n'en ouvre pas un nouveau.

**Gravité de VER4-401 : S3.** Latent : il faut qu'un administrateur définisse une métrique sur un jeu dont un rôle
programmeur n'a pas l'export (`semantic` n'est plus écrit par un rôle fin non administrateur, APFS43).

## 5. Optionnel (non déposé)

- **Genre figé `stock` et `stock_report?export=xlsx`** : toujours `reporting_export` seul (troisième contre-visite qui le
  relève, aucune décision dans `decisions.yml`). Le contenu (nom, référence, quantité) est celui que C-ADRG-VER3-360 jugeait
  S2 par la voie du widget : une question au fondateur fermerait l'incohérence.
- **Métrique et champs sous permission.** Le chemin métrique de `rendre_dashboard_html` ne passe pas par
  `spec_sans_champs_gated` (AANA25) : une métrique d'administrateur sur un champ sous permission sortirait ses valeurs dans
  le PDF d'un propriétaire administrateur. Même latence que VER4-401 ; propriétaire analyse (groupe AANA).
- **Propriétaire supprimé.** `SavedReport.owner` est `SET_NULL` ; `exiger_export_dataset(…, None)` laisse passer. Le
  jumeau suspend aussi ce cas (`suspendre_exports_du_createur`, `pre_delete`). Rare (comptes à traces désactivés).
- **Abonnements NTEXT12** (`rapport_abonnements.py::rendre_abonnement`) : rendus au nom de `rapport_def.owner` sans garde
  d'export ni d'activité. Aucune route API ne les crée (admin Django seul).
- **ADRG147, effet de bord.** Un propriétaire qui a perdu l'export ne peut plus PATCHer son propre rapport (`schedule:
  "none"`, `pinned`) : 403. Il peut le supprimer, et le rendu ne lui produit plus rien.
- **ADRG151, comptes hérités.** `permRepliPalier` et `useDroitMetier` ferment `/ma-journee` et `/planification` à un compte
  hérité de palier normal, que `LectureDuModule` accepte. `init_roles` donne un rôle fin à tout compte : sans effet sur les
  comptes livrés.
- **ADRG152, prévision.** Sans `crm_modifier`, la carte se glisse encore d'un mois à l'autre, sans PATCH ni déplacement
  (non optimiste) : geste inerte, pas d'appel refusé.

## 6. Couverture et sortie de cycle

**Couvert.** Les 10 tâches cochées depuis le 17/11, chacune lue sur son commit, le code servi, son test nommé, ses
jumeaux (grep) et son enregistrement d'acceptation ; les 10 chemins de sortie du §1 ; rôles livrés recalculés ; sondes
hôte rejouées (23 avec verdict, dont 1 neuve REPRO ; 7 sans verdict).

**Non couvert.**
- Aucun test Django ni vitest lancé : la preuve des tests reste la CI de `main`.
- Aucun rejeu navigateur ni API sur pile : la preuve en direct reste celle des enregistrements cités.
- Les sondes d'origine à contexte Django (`001`, `053`, `054`) et les 4 sondes périmées.

**Sortie de cycle.** Les deux écarts S2 du 17/11 sont fermés, mais un écart S2 nouveau est déposé (ADRG156) sur le même
chemin d'envoi. Compteur des `vérifie` consécutifs à zéro S1-S2 : **0**. Il faudra une contre-visite d'ADRG156 une fois
cochée, puis deux `vérifie` consécutifs à zéro S1-S2.

## 7. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0 M (un vérificateur opus seul, sans sous-agent). Aucun appel Fable : aucun S1.
