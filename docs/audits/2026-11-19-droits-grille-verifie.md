# Vérifie ADRG — cinquième contre-visite du parcours PF4 « droits de la grille », 19/11/2026

<!-- verifie | groupe: ADRG | pct: 99 | ecarts_s1_s2: 0 | faits: 131 -->

Contre-visite des correctifs du groupe ADRG (audit de parcours PF4 du 10/11, dossier `2026-11-10-parcours-PF4.md`), due à
95 % (`audit_registre.py --du` : 131 tâches cochées sur 132 constructibles, « contre-visite des correctifs, écarts S1-S2 du
2026-11-18 tous cochés »). Elle suit la contre-visite du 18/11 (`2026-11-18-droits-grille-verifie.md`). Son but : dire si
l'écart S2 du 18/11 (ADRG156, rapport programmé d'un propriétaire désactivé) est fermé sur tous les chemins de sortie,
relire la tâche S3 ADRG157 et la tâche de décision ADRG158 (D-ADRG-15 = exiger). Rien n'a été construit ni déployé ;
aucune base, aucun conteneur, aucune production n'a été lu.

## 0. Préconditions

- **SHA.** `origin/main` = `aa6ccb840` (PR #1491). Branche de claim : `verifie-1911`.
- **Registre.** PF4 `droits-grille`, groupe ADRG, 131 tâches cochées sur 132 constructibles (99 %). Restent ouvertes ADRG140
  (bloquée : aucune route ne liste les collègues au palier limité) et la tâche d'acceptation ADRG105.
- **Cochées depuis le 18/11 : 3.** ADRG156 (`6bfce5845`), ADRG157 (`afd93758b`), ADRG158 (`72e826d20`) ; coches
  `f3ec4f2f1` (PR #1469). Aucun commit n'a touché `scheduled_reports.py`, `saved_reports_api.py`, `reports.py` ni
  `diffusion_views.py` depuis `72e826d20`.
- **Échantillon : les 3** (contre-visite des correctifs, METHODE §C.4-6).
- **Méthode.** Un vérificateur frais (opus / high) : lecture des commits, du code servi et des tests nommés ; appelants et
  jumeaux cherchés par grep (`rendre_rapport`, `email_saved_reports`, `_rendre_legacy`, `rendre_dashboard_html`,
  `rapport_partage_public`, `diffuser_whatsapp`, `rendre_abonnement`) ; rôles livrés recalculés en Python pur sur
  `CANONICAL_SYSTEM_ROLES` / `PERMISSION_MODULE` (refait par l'orchestrateur) ; sondes hôte jouées. Aucun test Django ni
  vitest lancé.

## 1. Verdicts

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **3** | ADRG156, ADRG157, ADRG158 |
| partiel / non-fait / faux / régression / déjà-présent | **0** | — |

**Écart S2 d'origine.**
- C-ADRG-VER4-400 (ADRG156) : **fermé.** `scheduled_reports.py::_proprietaire_inactif` est lu par `rendre_rapport` (donc
  par ses deux appelants : le passage `email_saved_reports` et le lien public `diffusion_views.py::rapport_partage_public`,
  qui rend 404) et par la boucle d'`email_saved_reports` AVANT le choix du canal (WhatsApp compris : journal `echec`
  « Propriétaire du rapport désactivé : envoi suspendu. », puis passage au suivant). Aucun autre chemin de rendu ou d'envoi
  (pas d'action « envoyer maintenant » ; `diffuser_whatsapp` n'est appelé que par la boucle). La sonde VER5-500 exécute
  les vraies fonctions : e-mail, WhatsApp et lien d'un propriétaire désactivé tous bloqués.

**ADRG157** : `jeu_du_widget` suit la même priorité que `core/dashboard_data.py::executer_dashboard` (`type == 'metrique'`
ou clé `metrique`, clé lue sur `metrique` ou `cle`, même `get_metric`). Les métriques d'adaptateur (jeu vide) ne passent
par aucun contrôle mais ne sortent rien dans le PDF (seules les `rows` sont imprimées, les adaptateurs n'en rendent pas).

**ADRG158** : les sorties du genre figé « stock » lisent toutes `stock_export` : écriture (création, PUT, PATCH partiel) par
`validate` ; rendu par `_rendre_legacy` au nom du propriétaire (lien public 404) ; boucle d'envoi (WhatsApp compris) avec le
motif « Le propriétaire n'a pas le droit d'export du stock : envoi suspendu. », rien supprimé (D-ADRG-15 respectée) ;
`reports/stock/?export=xlsx|pdf` par `DroitDeLaGrille('stock_export', …)` ; « Exporter Excel » de la carte Stock masqué et
option Stock grisée dans les deux formulaires.

**Les chemins de sortie d'un rapport programmé, après les correctifs :**

| Chemin | Garde | Au nom de | Lit `is_active` | Genre `stock` : lit `stock_export` |
|---|---|---|---|---|
| Création, PUT, PATCH | `validate` | l'acteur | sans objet | oui |
| Passage hebdomadaire, e-mail | boucle (motif) + `rendre_rapport` | le propriétaire | oui | oui |
| Passage hebdomadaire, WhatsApp | boucle, avant le canal ; lien rendu gardé | le propriétaire | oui | oui |
| Lien public | `rendre_rapport` | le propriétaire | oui | oui |
| `reports/stock/?export=xlsx\|pdf` | `DroitDeLaGrille` | le demandeur | sans objet | oui |
| `render_report_xlsx` (tests seulement) | `_rendre_legacy` | le propriétaire | non | oui |
| Propriétaire supprimé (`owner` nul) | `exiger_export_dataset(…, None)` laisse passer | — | non | non (optionnel, §5) |

## 2. Tests nommés

- ADRG156 : `apps/reporting/tests_ntdata37_abonnement_dashboard.py::AbonnementDashboardTests::test_proprietaire_desactive_rien_ne_part`
  — échoue si la garde saute de l'un ou l'autre site (motif exact de l'e-mail, 404 du lien). Le canal WhatsApp n'a pas de
  test Django ; la sonde VER5-500 l'exécute (rien ne part).
- ADRG157 : `…::test_widget_metrique_stock_exige_stock_export` — échoue à `validate` (403) et au rendu (nom du produit dans
  le HTML). L'alias `cle` et un widget à clé `metrique` sans `type` ne sont pas testés ; le code suit `executer_dashboard`.
- ADRG158 : `…::test_rapport_fige_stock_exige_stock_export` — POST, PATCH, e-mail, lien, xlsx. PUT et `?export=pdf` non
  testés, même code.
- Acceptation : `docs/audits/acceptation/ADRG/2026-11-18-00545c3ff.md` (PASS, `couvre:` ADRG156, 157, 158 ; spec
  `frontend/e2e/acceptation/adrg15.spec.js`).

## 3. Sondes

| Sonde | Tâche | Verdict | Observé (hôte, `aa6ccb840`) |
|---|---|---|---|
| `C-ADRG-VER5-500.py` (neuve) | jumeau d'ADRG158 ; contrôle d'ADRG156 et d'ADRG158 | **REPRO** | `sales` du Technicien responsable et `service` de l'Admin Ventes envoyés et servis ; contrôles : propriétaire désactivé bloqué sur e-mail, WhatsApp et lien ; `stock` d'un Commercial responsable bloqué |
| `C-ADRG-VER4-400.py` (18/11) | ADRG156 | **périmée** | `repro: true` faux positif : elle cherche les chaînes `is_active` / `owner` dans le corps de chaque fonction et ne suit pas les fonctions d'aide (`_proprietaire_inactif`, `_export_du_genre_refuse`) ; l'exécution de VER5-500 la réfute |

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Sonde | Tâche |
|---|---|---|---|---|---|
| C-ADRG-VER5-500 | ADRG158 (jumeau) | S3 | Les genres figés `sales` et `service` ne lisent aucun droit, ni à l'écriture (`saved_reports_api.py::SavedReportSerializer.validate` ne garde que les genres à cible et `stock`) ni au rendu (`scheduled_reports.py::_rendre_legacy`, `render_sales`, `render_service`). Leurs jumeaux JSON `reports.py::sales_report` / `service_report` exigent la lecture du module `ventes` / `installations`. Rôles livrés : le Technicien responsable (`reporting_export`, aucun code ventes ni CRM) reçoit le décompte des leads par étape ; l'Admin Ventes (`reporting_export`, aucun code chantiers ni SAV) reçoit le décompte des tickets SAV par statut, chaque semaine, vers des adresses libres et par lien public. | `C-ADRG-VER5-500.py` (REPRO) | ADRG159 |

**Gravité de VER5-500 : S3.** Des comptes agrégés, aucun enregistrement nommé ni montant ; la tâche aligne le rapport figé
sur la LECTURE que son jumeau JSON exige déjà. Exiger l'EXPORT des modules ventes et SAV demanderait une décision du
fondateur comme D-ADRG-15 : non ouverte (S3, aucune urgence).

## 5. Optionnel (non déposé)

- **Sonde VER4-400 périmée** (§3) : à faire suivre les fonctions d'aide ou à remplacer par VER5-500.
- **Propriétaire supprimé (`SET_NULL`).** Le rapport `stock` part encore (sonde : `stock_proprietaire_supprime_parti:
  true`). Latent : `authentication/views.py::_traces_du_compte` refuse la suppression par l'API d'un compte qui possède
  encore un rapport.
- **PDF programmé des métriques d'adaptateur.** « Aucune donnée sur la période. » pour chaque indicateur d'adaptateur
  (`ca_ht`, pipeline…) des tableaux modèles Direction / Finance : défaut fonctionnel, pas de droit (propriétaire analyse).
- **Jumeau interactif, STATIQUE.** `core/views.py::DashboardViewSet.donnees` → branche adaptateur de `resolve_metric`, sans
  contrôle de lecture ; `crm.pipeline_pondere` et `reporting.taux_gain` ignorent l'utilisateur. Ne s'ouvre que si
  `seed_metriques` a tourné en production (absent des scripts de déploiement, non vérifié). Mérite une sonde au prochain
  passage sécurité / analyse.
- **Hypothétique.** `DatasetInconnu` non rattrapé dans `_export_du_genre_refuse` : si le jeu `stock_produits` disparaissait
  du registre, la boucle sauterait sans ligne de journal et le lien rendrait 500.

## 6. Couverture et sortie de cycle

**Couvert.** Les 3 tâches cochées depuis le 18/11, chacune lue sur son commit, le code servi, son test nommé, ses appelants
et jumeaux (grep) et son enregistrement d'acceptation ; les 7 chemins de sortie du §1 ; rôles livrés recalculés ; deux
sondes hôte jouées (une neuve REPRO, une périmée).

**Non couvert.**
- Aucun test Django ni vitest lancé : la preuve des tests reste la CI de `main`.
- Aucun rejeu navigateur ni API sur pile : la preuve en direct reste l'enregistrement cité.
- Les sondes d'origine à contexte Django (`001`, `053`, `054`), toujours non rejouées (ADRG105).

**Sortie de cycle.** L'écart S2 du 18/11 est fermé et aucun écart S1-S2 nouveau n'est déposé (une tâche S3, ADRG159).
Compteur des `vérifie` consécutifs à zéro S1-S2 : **1**. Il en faut un second pour sortir du cycle.

## 7. Coût

H0 S0 O1 F0 · jetons sous-agents ≈ 0,25 M (un vérificateur opus seul). Aucun appel Fable : aucun S1.
