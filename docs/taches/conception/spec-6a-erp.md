# Spec 6a — « L'ERP qui me suit » : relier les tâches au reste de l'ERP

Chemins backend relatifs à `backend/django_core/`. Rien exécuté.

## 1. Parcours (gestes)

| Parcours | Bureau | iPhone |
|---|---|---|
| P1 Tâche liée depuis une fiche | `c` `t` → saisie pré-liée (puce « Lead · Karim B. ») → titre → Entrée : 3 + frappe ; ou ⌘K → « Créer une tâche » : 3 + frappe ; ou bouton ✓+ de l'en-tête : 2 + frappe | ✓+ (1) → feuille pré-liée → dicter → « Ajouter » (1) : 2 + dictée |
| P2 Mes tâches liées à l'objet | compte sur ✓+ (0) → clic (1) | 1 |
| P3 Clore une activité ERP | case (1) | 1 |
| P4 Convertir mes à-faire personnels | bandeau → « Convertir » (1) | 1 |
| P5 Suggestion (« Ajouter »/« Pas utile ») ; P6 ouvrir l'objet lié (puce) | 1 | 1 |
| P7 Ma journée en accueil | ⋯ → « En faire mon accueil » (2) | 2 |

## 2. Fonctions classées

Origine « brief » = `brief-r1.md` §2 (synthèse de recherche, preuves faibles).

| Fonction | Classe | Origine | Pourquoi |
|---|---|---|---|
| Lien → lead, client, devis, facture, chantier, ticket | ESSENTIEL | brief (to-do Odoo) | l'avantage ERP |
| Lien → 9 autres cibles déclarées (§3.1) | AVANCÉ (« Autre ») | `record_targets` | souvent sans lien profond (`entityRoutes.js:32-35`) |
| Lien → visite, rendez-vous | ÉCARTÉ | | non déclarés (`visites/platform.py:39`) : lier au lead |
| Saisie pré-liée (`c t`, ⌘K, ✓+) | ESSENTIEL | brief (quick add) | un hôte, aucun écran étranger édité |
| Compte de mes tâches liées sur l'objet ouvert | ESSENTIEL | | privé |
| Ligne au chatter de l'objet | ÉCARTÉ | | visible de l'équipe (D-TCH-1) |
| Activités ERP dues ≤ aujourd'hui | ESSENTIEL | socle §1(b) | |
| Visites, interventions du jour/en retard | ESSENTIEL (lignes-liens) | | obligations datées |
| Touches de cadence du jour | ESSENTIEL (une ligne groupée) | | elles s'exécutent dans le script d'appel |
| Chantiers, tickets, DA à commander, leads chauds, rappels, devis expirant, relances | AVANCÉ (« Ailleurs dans l'ERP », replié) | blocs de `ma_file` | non datés |
| Approbations, mentions | AVANCÉ (lues à l'ouverture du repli) | | coût de `_SOURCE_LOADERS` (V1 m11) |
| Lier une tâche à une activité ; convertir un à-faire (tous : bandeau AVANCÉ) | ESSENTIEL | socle §1(c) | |
| Suggestions devis accepté, chantier réceptionné/annulé (allumées) ; visite validée (éteinte) | ESSENTIEL / AVANCÉ | | §3.7 |
| Devis sans réponse, devis expiré, nouveau lead, visite planifiée | ÉCARTÉ | | déjà pris par la cadence (`crm/receivers.py:235`, `:637`) ou la file (`cadence_selectors.py:1356`) |
| Paiement rejeté, facture en retard | ÉCARTÉ | | `paiement_rejete` réservé (`event_coverage.py:141`) ; aucun événement « facture en retard » |
| Suggestions société entière (admin) | AVANCÉ | | sinon déluge |
| Carte « Mes tâches » (cockpit, tableau de bord), accueil, pastille de tuile | ESSENTIEL | D-TCH-2 | |
| Tâches dans « Ma file » | ÉCARTÉ | | §3.6 |
| Export JSON, tout effacer | ESSENTIEL (Réglages) | socle §8 | |

## 3. Règles exactes

**3.1 Lier.** `lien = {cible:'app.model', id}` passe par `records.serializers.resolve_target(cible, id, company, user=request.user, ecriture=False)` (`records/serializers.py:44-107`) : type déclaré (:56), même société (:84), portée lead `portee_leads` + `crm_voir` (:94-102), droit du module (:105). `ecriture=False` : rien n'est écrit sur la cible. Refus et introuvable → même message. Cibles déclarées (15, lues dans les `platform.py`) : crm lead/client (`crm/platform.py:33`), ventes devis/boncommande/regulatorydossier + `facturation.facture` (`ventes/platform.py:42-45`), installations installation/demandeachat (`installations/platform.py:25-28`), `sav.ticket` (`sav/platform.py:34`), stock produit/fournisseur (`stock/platform.py:40`), calepinage, ged.document, entites.entite, outillage. Le « 39 cibles » de `serializers.py:76` est périmé.

**3.2 Libellé et état.** À la liaison : `lien_libelle = str(obj)[:200]`, `lien_etat='ok'`. Revérifié à chaque `GET taches/taches/{id}/` : refus → `inaccessible` ; introuvable → `introuvable` (lien désactivé, tâche JAMAIS supprimée) ; `is_archived`/`is_deleted` → `archive`. Ma journée lit l'état stocké (budget). `lead_erased` (`event_catalog.py:50`, `company`, `crm_lead_id`) → `lien_libelle='Lead effacé'`, `lien_etat='efface'`, suggestions de ce lead supprimées ; le titre tapé reste (dit dans Réglages).

**3.3 URL de l'objet.** `apps/taches/contract_samples/liens_cibles.json` (`{modele: gabarit|null}`), lu par `selectors.url_de_cible()` et par un test front contre `entityRoutes.ROUTE` : `crm.lead`→`/crm/leads?lead={id}`, `crm.client`→`/crm?id={id}`, `ventes.devis`→`/ventes/devis?devis={id}`, `facturation.facture`→`/ventes/factures?id={id}`, `installations.installation`→`/chantiers?id={id}`, `sav.ticket`→`/sav?id={id}`, `calepinage.calepinage`→`/calepinage/{id}` (`entityRoutes.js:24-38`) ; `ventes.boncommande`→`/ventes/bons-commande`, `stock.produit`→`/stock` ; autres → `null`. Une cible absente vaut `null` : une app qui déclare une cible ne casse jamais la CI.

**3.4 Contexte de l'écran.** `features/taches/cibleEcran.js` : `cibleDepuisEcran({pathname, search})` = inverse de 3.3 (`/crm/leads/:id` aussi, route `crm/module.config.jsx:127`).

**3.5 Ma journée — familles ERP.** Chaque source gardée par `module_actif` + droit ; une source en échec = famille absente :
- `activites` : nouveau `records.selectors.activites_ouvertes_pour(user, jusquau=today)` = `company`, `assigned_to=user`, `done=False`, `due_date <= today`, snooze échu (règle de `views.py:470-472`), `sans_cibles_archivees` (`views.py:285-292`), ET exclusion XKB4 (`personnelle` et `created_by != user`, `views.py:392-393`). Sans date : hors journée. `peut_cloturer = records.selectors.peut_cloturer_activites(user)`, la règle même d'`IsResponsableOrAdmin` sur `done/` (`views.py:654-656`, `authentication/permissions.py:160-185`). Clôture par `POST records/activities/{id}/done/` ; `chained` dans la réponse → toast « Suite planifiée ».
- `visites` : `visites.selectors.ma_journee_du_commercial(company, user, aujourdhui=today)` (`visites/selectors.py:1103`), appelé seulement si l'utilisateur a `visites_voir`.
- `interventions` : `installations.selectors.affectations_pour(user)` filtré `kind='intervention_du_jour'`, urgence `today`/`overdue` (`installations/selectors.py:2814-2889`).
- `touches` : `crm.selectors.relance_etapes_dues(company, user, scope='today', owner=user).count()` et `scope='overdue'` (`cadence_selectors.py:608-667`) ; `owner=user`, sinon un admin compte toute l'équipe. Une ligne → `/crm/relances`. Si `crm_voir`.
- `ailleurs` : compteurs par `kind` de `crm.selectors.ma_file_commercial_items` (`cadence_selectors.py:1305`) et `affectations_pour` installations/sav hors `intervention_du_jour` : les blocs 4-5 de `ma_file` (`records/views.py:590-619`), sans copie de règle.

Exemple : 2 tâches du jour + 1 en retard, 2 activités dont 1 en retard, 1 visite du jour, 3 touches du jour + 2 en retard, 1 chantier → `journee` 4 lignes (2 tâches, 1 activité, 1 visite), `en_retard` 2, ligne touches `{nb:5, en_retard:2}`, `ailleurs.chantiers=1`, pastille 2 (tâches du jour, retards exclus, S4).

**3.6 Ma file : NON.** Y verser les tâches créerait un miroir (deux listes, deux gestes de clôture pour la même tâche) et éditerait un fichier `securite` (`views.py:487-652`) pour des rôles qui n'ont pas encore Tâches (socle §8). `ma_file` n'est pas réutilisable telle quelle : c'est une vue, sans exclusion XKB4, avec les relances FG31 au lieu des touches de cadence, et l'agrégat privé des approbations. Ma journée réutilise donc ses SÉLECTEURS publics ; « Ailleurs » renvoie à `/activites` (`crm/module.config.jsx:128`).

**3.7 Suggestions.** Abonnés `@receiver` + `@abonne_best_effort` (`core/events/__init__.py:166`) dans `apps/taches/receivers.py`, connectés dans `apps.py` `ready()`. Aucun nouveau signal ; aucun n'est dans `ALLOWED_UNCONSUMED` (`event_coverage.py:45-166`) : rien à éditer dans `core`.

| Famille | Événement (charge) | Destinataire | Texte | Clé |
|---|---|---|---|---|
| `devis_accepte` (ON) | `devis_accepted` (`devis, user, avenant_de`) ; ignoré si `avenant_de` non nul | responsable du lead (`crm.selectors.lead_du_devis(devis).owner`), sinon `user` | « Appeler {client} : devis {reference} accepté » | `devis_accepte:{devis.pk}` |
| `chantier_receptionne` (ON) | `chantier_receptionne` (`installation, user`) | `installation.lead.owner` | « Demander un avis à {client} : chantier réceptionné » | `chantier_receptionne:{pk}` |
| `chantier_annule` (ON) | `chantier_annule` (`installation, company, user`) | `installation.lead.owner` | « Comprendre l'annulation du chantier de {client} » | `chantier_annule:{pk}` |
| `visite_validee` (OFF) | `visite_validee` (`visite, lead_id`) | responsable du lead | « Préparer le devis de {nom} : visite validée » | `visite_validee:{visite.pk}` |

Conditions : destinataire actif, `taches_voir`, module actif, famille allumée. `get_or_create` sur `(company, destinataire, cle)` : refusée = jamais reproposée. `devis_acceptation_annulee` retire la suggestion encore proposée. Aucun push, hors plafond socle §5. Visible 7 jours, purgée à 30. Accepter → `creer_taches()` (`source='suggestion'`, lien = cible). Interrupteur admin « toute la société » : l'admin reçoit aussi.

## 4. Données (ajouts au socle §3)

- `Tache.lien_etat` Char(12) `''|ok|archive|introuvable|inaccessible|efface` ; `Tache.lien_verifie_le` DateTime null ; `source` + `suggestion`. Index `taches_tache_lien_idx` (company, proprietaire, content_type, object_id).
- `SuggestionTache` (TenantModel) : `destinataire` FK user CASCADE, `famille`, `cle` Char(80), `titre_propose`, `content_type` + `object_id` null, `lien_libelle`, `lead_ref` null, `statut` `proposee|acceptee|refusee|retiree`, `tache` FK SET_NULL, `decidee_le`. `UniqueConstraint(company, destinataire, cle)` `taches_sugg_cle_uniq` ; index `taches_sugg_boite_idx` (company, destinataire, statut, created_at). `__str__` neutre.
- `ReglagesRythme.familles_suggestions` JSON (liste fermée, défaut les 3 ON), `suggestions_societe` Bool défaut False (admin seul), `erp_dans_journee` Bool défaut True.

## 5. API

- `POST taches/taches/` et `POST taches/saisie-rapide/` acceptent `"lien":{"cible":"crm.lead","id":1637}` ; `PATCH` `"lien":null` délie. Réponse : `"lien":{"cible":"crm.lead","id":1637,"libelle":"Karim B.","url":"/crm/leads?lead=1637","etat":"ok"}`. Erreurs 400 : `{"lien":["Élément introuvable ou hors de votre portée."]}`, `{"lien":["Ce type d'élément ne peut pas être lié à une tâche."]}`.
- `GET taches/taches/?cible=crm.lead&cible_id=1637&ouvertes=1` (filtres déclarés OpenAPI) ; `cible` mal formée → 400 `{"cible":[…]}`.
- `GET taches/aujourdhui/` (socle §4) : ITEM `type:"activite"` porte `cible`, `url`, `peut_cloturer` ; ajout `"obligations":[{"famille":"visite","id":88,"titre":"Visite — Karim B.","jour":"2026-11-17","url":"/visites"},{"famille":"touches","nb":5,"en_retard":2,"url":"/crm/relances"}]`, `"ailleurs":{"chantiers":1,"tickets":0,"leads_chauds":3,…,"url":"/activites"}`, `"suggestions":{"nb":2}`, `"a_convertir":{"nb":3}`. Contrat `aujourdhui.json` d'abord (PACT10).
- `GET taches/suggestions/` (≤ 20) ; `POST taches/suggestions/{id}/accepter/` `{"titre"?, "jour_prevu"?}` → 201 tâche ; `POST …/refuser/` → 200. Id d'un autre → 404.
- `POST taches/convertir-activite/` `{"activite_id":12}` ou `{"activite_ids":[…≤200]}` : exige `personnelle=True, created_by=user, done=False` (V2 M1), clôt la source par le nouveau `records.services.cloturer_a_faire_personnel(activite, user)`. Refus → 400 `{"activite_id":["À-faire introuvable."]}`.
- `GET taches/mes-donnees/` : JSON de toutes ses lignes `taches` (supprimées non purgées comprises, jetons sans empreinte). `POST taches/tout-effacer/` `{"confirmation":"EFFACER"}` : suppression DURE des lignes du couple (société, utilisateur), jetons révoqués ; sinon 400 `{"confirmation":["Tapez EFFACER pour confirmer."]}`.

## 6. Écrans

- **Hôte `TachesPresence`** (monté une fois dans `Layout.jsx`) : écoute `taqinor:taches:saisir` (raccourci) et `taqinor:quick-create` `type:'tache'` (palette) ; lit l'écran À L'INSTANT ; ouvre la saisie (Sheet mobile, Dialog bureau), puce de lien retirable. Porte aussi la pastille S4.
- **`BoutonTachesIci`** (en-tête) : icône ✓+, compte des tâches ouvertes liées à l'objet de l'écran (une requête par route d'objet). Clic : liste (cocher = terminer) + « Nouvelle tâche liée ». Masqué sans `taches_voir`.
- **Ma journée** : lignes activité (badge « ERP », case si `peut_cloturer`, sinon « Ouvrir »), visites et interventions (« Ouvrir »), ligne touches ; repli « Ailleurs dans l'ERP » ; bandeau « à convertir » si `a_convertir.nb > 0`.
- **Boîte de réception** : section « Suggéré par l'ERP » en tête, une ligne par suggestion, « Ajouter » / « Pas utile ».
- **`CarteMesTaches`** (cockpit mobile, tableau de bord) : « N à faire aujourd'hui · M faites », 3 lignes (essentiel d'abord), « Ouvrir Ma journée ».
- **Réglages** : « L'ERP me suggère » (4 interrupteurs), « Afficher mes activités ERP », « Exporter mes données », « Tout effacer ».
- États : chargement = squelette ; famille ERP en échec = absente + « Certaines informations de l'ERP n'ont pas pu être lues » ; hors ligne = dernière liste gardée, clôture ERP désactivée ; vide = « Rien de prévu aujourd'hui ». Jamais de liste vidée par un rafraîchissement en échec.

## 7. Assistant

`taches.capturer` reçoit `lien` depuis `contexte.lead_id`/`devis_id` (liste blanche, `copilotMessages.js:89-98`) ; chantier et ticket exigent d'étendre `ContexteEcran` (`apps/agent`, réservé) : L3 n°5. `taches.suggestions.lister` (lecture) ; accepter = carte tapée.

## 8. Critères d'acceptation

1. Étant donné un commercial hors portée du lead 9, quand il POSTe `lien` crm.lead 9, alors 400 `lien`, aucune ligne.
2. Étant donné la cible `visites.visitetechnique`, alors 400 « Ce type d'élément… ».
3. Étant donné une tâche liée au lead 9, quand `anonymiser_lead` s'exécute, alors `lien_etat='efface'`, titre inchangé.
4. Étant donné l'objet lié supprimé, quand `GET taches/taches/{id}/`, alors 200, `lien.etat='introuvable'`.
5. Pour chaque gabarit de `liens_cibles.json`, `cibleDepuisEcran` et `entityRoutes.ROUTE` concordent ; toute clé ∈ `ALLOWED_TARGETS`.
6. Étant donné un à-faire personnel créé par A, assigné à B, alors absent des `activites` de B.
7. Pour chaque rôle système, `peut_cloturer_activites(user)` == (`POST done/` ≠ 403).
8. Étant donné un admin et 4 touches du jour dont 1 à lui, alors `touches.nb == 1`.
9. Étant donné `devis_accepted` émis deux fois, alors une seule suggestion ; refusée puis réémise : rien de nouveau.
10. Quand `devis_acceptation_annulee`, alors la suggestion proposée passe `retiree`.
11. Étant donné B et l'id d'une suggestion de A, accepter/refuser → 404.
12. `orphan_signals()`, `stale_allowlist()`, `uncatalogued_events()` vides.
13. Étant donné un compte avec 40 tâches et rien d'autre, `_traces_du_compte` rend `''`.
14. `tout-effacer` sans « EFFACER » → 400 ; avec → 0 ligne `taches` du couple, aucune d'un autre.
15. `aujourdhui/` sous son plafond (`query-budgets.yml`) avec 3 visites, 5 touches, 10 activités.

## 9. Risques, gardes, fichiers étrangers

Risques : (a) la cadence CRM a déjà des « tâches » (`cadence_selectors.py:625-634`) : la ligne s'appelle « touches de suivi ». (b) `ma_journee_du_commercial` calcule les manquants par visite (`visites/selectors.py:1051`) : mesuré par le critère 15 ; au-delà, sélecteur mince chez `lead`. (c) `CREATE_ACTIONS` ne filtre pas les entrées à `event` (`commandActions.js:27-32`, contrairement à `NAV_ACTIONS` :17) : sans correctif, `c t` casse la section « Créer ». (d) En-tête mobile serré (`.header-cmdk` y est masqué, `styles/deploy/12-progression-mobile.css:171`) : repli = menu utilisateur. Gardes : `check_api_shapes`, couverture d'événements, `check_unique_scoping`, `check_query_budgets`, OpenAPI.

Fichiers hors `taches` (`f/` = `frontend/src/` ; éditions minimales, en fin de liste, une tâche chacun). Aucun sous réservation : `crm.selectors` et `ventes` sont seulement LUS.

| Fichier | Propriétaire (`docs/ownership.yml`) | Édition |
|---|---|---|
| `apps/records/selectors.py` (nouveau) | securite (:482) | `activites_ouvertes_pour`, `nb_a_faire_personnels`, `peut_cloturer_activites` |
| `apps/records/services.py` | securite | `cloturer_a_faire_personnel` |
| `authentication/selectors.py:191` | securite (:486) | `'/taches'` dans `MOBILE_HOME_ALLOWED_ROUTES` |
| `authentication/views.py:1404-1425` | securite | exclure `app_label == 'taches'` du décompte |
| `core/management/commands/seed_registre_traitements.py` | securite (résiduel `core/**`, :509) | entrée `taches_rythme` |
| `f/components/layout/Layout.jsx` | deploy (repli `components/**`, :817) | 1 import + `<TachesPresence />` |
| `f/components/layout/Header.jsx` | deploy | 1 import + `<BoutonTachesIci />` |
| `f/providers/shortcuts.js:96-100` | deploy (append-only :990) | `{ keys:'c t', event:'taqinor:taches:saisir', label:'Créer une tâche' }` |
| `f/providers/commandActions.js:27` | deploy (:801) | `.filter((s) => !!s.to)` |
| `f/lib/search/entityRoutes.js` | deploy (append-only :986) | ligne `tache` (`/taches`) ROUTE/LIST_ROUTE/TYPE_LABEL : masque l'entrée sans module |
| `f/lib/apps/useAppBadges.js` | deploy (repli `lib/**`) | fusionner les `badgePersonnel` des `module.config`, pour TOUT utilisateur |
| `f/pages/Dashboard.jsx` | deploy (:792) | carte lazy |
| `f/features/uxviews/quickcreate/quickCreateEvents.js:14-19` | analyse (repli :877) | `{ id:'tache', label:'Créer une tâche' }` |
| `f/features/offlinesync/mobile/CockpitHome.jsx` | analyse (:868) | carte lazy |
| `docs/query-budgets.yml` | deploy (:741) | entrée `taches/aujourdhui/` |
| `docs/openapi-schema.yml` | régénéré | — |

## 10. Choix par défaut et objections

Choix par défaut : lier = lecture ; libellé figé, revérifié à l'ouverture d'une tâche (jamais dans la liste) ; URL calculée au serveur depuis un contrat partagé (tuile Scriptable, carte assistant) ; pastille = tâches seulement ; 3 familles de suggestions allumées, aucune notification ; Ma file non alimentée ; accueil bureau par la préférence existante `setLandingModule('taches')` (`prefs.js:81`, première entrée de nav `:107`), mobile par `POST auth/mobile-home-route/ {route:'/taches'}` ; client effacé (`anonymiser_client`, sans événement, `crm/dsr_provider.py:370`) : libellé corrigé à la prochaine ouverture, un `client_erased` est AVANCÉ chez crm (réservé).

Objections au socle (conçu en le respectant) :
- « Ma journée » existe déjà deux fois : `/ma-journee` (techniciens, `installations/module.config.jsx:104`) et `/visites` (`visites/module.config.jsx:91`). Route `/taches`, nav « Tâches » ; le nom de l'écran est à trancher au L3 esthétique.
- Constat pour securite : `mine`/`ma_file` montrent à B l'à-faire personnel que A lui a assigné (`views.py:464-466, 517-519`) ; `get_queryset` le cache (:392-393).

Non vérifié : `get_object_for_this_type` voit-il les lignes en suppression douce (Django absent de l'hôte) ? Place réelle dans l'en-tête iPhone ; atterrissage PWA via `/apps` vs Dashboard ; recoupement « visite validée » avec la cadence.

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.
