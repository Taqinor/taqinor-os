# Socle validé — gestionnaire de tâches personnel (`apps/taches`)

Référence UNIQUE pour tous les L3 suivants. Issu du L3 n°1 (6 lanes de lecture, 4 conceptions, 3 vérificateurs
contradictoires : réalité du code, vie privée, simulation). Quand une conception de `design-s*.md` contredit ce
fichier, CE FICHIER fait foi. Les rapports de vérification sont dans le même dossier (`verif-*.md`,
`rapport-simulation.md`).

## 0. Décisions fondateur (17/11/2026 — ne jamais reposer ; Reda a demandé de ne plus lui poser de question)

- **D-TCH-1** Espace PRIVÉ par utilisateur. Ni délégation ni projet partagé dans cette construction. Le schéma
  garde la porte ouverte, rien n'est construit.
- **D-TCH-2** iPhone : tout — icône qui ouvre « Ma journée », pastille, notifications, tâches dans le widget
  Calendrier d'Apple (flux abonné), dictée Siri, ET la grande tuile Scriptable (app tierce gratuite acceptée) : v1.
- **D-TCH-3** Sollicitations par défaut : plan du matin + bilan du soir + AU PLUS UNE relance en journée. Réglable.
- **D-TCH-4** Démarrage : il colle ou dicte ses listes, l'IA propose le rangement par projet, il valide. Pas d'import Odoo.
- **D-TCH-5** (message du 17/11) « la meilleure agenda possible » : toutes les fonctions nécessaires et utiles ET
  simple à utiliser. Chaque L3 classe donc chaque fonction : ESSENTIEL (visible d'emblée) / AVANCÉ (présent mais
  replié, découvert au besoin) / ÉCARTÉ (avec la raison). Rien d'utile n'est écarté pour « faire simple » : on le replie.

## 1. Architecture

- Nouvelle app `apps/taches` (clé de module et préfixe d'URL `taches`), front `features/taches` + `pages/taches`,
  plan `docs/plans/PLAN_TACHES.md`, tâches `TCH<n>`. Ne JAMAIS étendre `records.Activity` (triple usage, pas de
  suppression douce, droits `IsResponsableOrAdmin`, appartient à l'unité sécurité) ni restaurer `gestion_projet`.
- UN seul système pour l'utilisateur : (a) une seule saisie — toute capture crée une `Tache` ; (b) « Ma journée »
  liste ses tâches ET ses activités ERP ouvertes (lecture seule, closes par leur endpoint d'origine
  `records/activities/<id>/done/`, indicateur `peut_cloturer`) ; (c) un à-faire personnel existant
  (`Activity.personnelle`) se convertit en tâche ; une activité ERP ne se convertit pas, on lui « lie une tâche ».
- Tout marche SANS clé d'IA : moteur déterministe dans Django (classement, plan proposé, rythme, profil, relances),
  l'assistant n'est qu'une conversation par-dessus. Le modèle de langage ne produit jamais un chiffre : il le lit.
- Aucun événement nouveau sur le bus tant qu'aucun abonné n'existe (garde `core/event_coverage.py`).

## 2. Vie privée — règles non négociables (issues de la vérification V2)

1. Un seul sélecteur `taches_de(user)` (société ET propriétaire) derrière TOUTE lecture. `proprietaire` forcé côté
   serveur. Tout identifiant reçu du client (projet, section, parent, élément de liste, ids de réordonnancement,
   lignes de plan, activité à convertir) est vérifié « même propriétaire » — un test de balayage le prouve.
2. Pas de corbeille commune : `soft_delete(record=False)`, liste privée « Supprimées récemment » + « Annuler »
   propres à `taches`, AUCUN restaurateur dans `apps/trash`, `__str__` neutre (jamais le titre).
3. Étiquettes propres à `taches` (privées) — pas `records.Tag`. Pas de `record_targets` (commentaires, pièces
   jointes) tant qu'un contrôle de propriétaire n'existe pas côté `records` : notes + liste de contrôle suffisent.
4. Pas d'inscription à la recherche globale sans filtre propriétaire ; recherche propre dans l'app.
5. Jetons : UN modèle `JetonAcces` (haché, par utilisateur, par usage `capture` / `flux` / `tuile`, révocable,
   dernier usage, sans expiration silencieuse). Jamais le jeton d'agenda existant (il expire à 180 jours et ouvrirait
   les tâches à quiconque a déjà l'URL d'agenda). Un jeton `capture` ne peut QUE créer une tâche dans la boîte de
   réception. Le flux et la tuile ne servent jamais les notes.
6. Assistant : une liste collée est une DONNÉE, jamais une consigne. Le modèle ne renomme, n'annule ni ne supprime
   seul : ces gestes passent par une carte tapée au doigt, et le serveur garde l'état d'avant pour « Annuler ».
   La question d'un tour `taches.*` est masquée dans le journal de l'assistant lisible par les administrateurs.
7. Dire la vérité à l'utilisateur, dans l'écran Réglages : ce qui part chez le fournisseur d'IA à chaque tour du
   coach ; un drapeau « confidentiel » (tâche ou projet) qui masque titre et notes à l'IA ; qui peut techniquement
   tout lire (accès serveur, sauvegardes, export de la société, super-utilisateur, prise en main du support).
8. Notifications : par défaut des comptes, pas les titres (écran verrouillé) ; titres sur réglage explicite.

## 3. Schéma canonique (vocabulaire imposé — tranche les contradictions entre conceptions)

Bases : `TenantModel` partout ; `SoftDeleteModel` + `VerrouOptimisteMixin` sur `Projet` et `Tache`. Toute
contrainte d'unicité commence par `company` et, sur un modèle à suppression douce, porte `is_deleted=False` dans
sa condition. Noms d'index explicites ≤ 30 caractères. Jours via `timezone.localdate()`.

- `Projet` : proprietaire, nom, objectif, icone, couleur (palette fermée), priorite, statut
  (`actif`/`en_pause`/`termine`/`archive`), date_debut, echeance, termine_le, rang, confidentiel, visibilite (`prive` seul servi).
- `Section` (sert aussi de phase) : projet, nom, rang, date_debut, date_fin.
- `Tache` : proprietaire, projet (nul = Boîte de réception), section, parent (un niveau), titre, notes, statut
  (`a_faire`/`en_attente`/`fait`/`annule`), en_attente_de (texte libre), priorite, jour_prevu, moment
  (''/`matin`/`apres_midi`/`soir`), echeance, echeance_heure, quelque_jour, estimation_minutes,
  duree_reelle_minutes, rang_projet, rang_jour, premier_jour_prevu, reports, source, lien ERP générique
  (content_type + object_id + lien_libelle, validé par `records.serializers.resolve_target`), activite_origine,
  recurrence, occurrence_du, confidentiel, fait_le, annule_le.
- `ElementChecklist`, `Etiquette` (+ lien tâche), `RegleRecurrence` (une seule occurrence ouverte ; la suivante naît
  à la clôture ; calcul pur sans bibliothèque), `PlanJour` (instantané + compteurs du jour), `LignePlanJour`
  (prévue au plan / ajoutée après / faite / reportée / essentielle), `ReglagesRythme`, `Preference` (ce qu'il a DIT :
  clé fermée, valeur, date — prime sur toute inférence), `IncitationCoach` (journal des sollicitations), `JetonAcces`.
- **Priorité** : UNE échelle `0 aucune / 1 basse / 2 moyenne / 3 haute` (3 = la plus forte), la même pour projets et
  tâches. Pas de drapeau « important » séparé : « important » = priorité haute. L'« essentiel du jour » (1 à 3
  tâches choisies au plan du matin) vit sur `LignePlanJour.essentielle`.
- **Ordre manuel** : entiers espacés de 1 024, renumérotation de la seule liste concernée quand l'écart s'épuise.
- Ce schéma est un PLANCHER : les L3 suivants ajoutent des champs (heure de début d'un bloc, rappel, dépendance,
  jalon, modèle de projet…) sans renommer ceux-ci.

## 4. API canonique

- UNE lecture de la journée : `GET taches/aujourdhui/?jour=` (forme de `design-s1-modele.md` §3). Les cartes de
  l'assistant rendent CE corps tel quel.
- UN service de création `services.creer_taches()` derrière trois portes : `POST taches/taches/` (structuré),
  `POST taches/saisie-rapide/` (texte, une ou plusieurs lignes, analyse déterministe), `POST taches/capture/`
  (jeton `capture` : Siri, feuille de partage).
- UN seul chemin déplace le jour prévu et compte les reports : `POST taches/<id>/planifier/` (`jour_prevu` en
  lecture seule sur PATCH). L'assistant passe par les mêmes routes que l'écran, jamais par un PATCH brut.
- Droits : `taches_voir`, `taches_gerer`, accordés à tous les rôles système ; les données restent privées quel que soit le rôle.

## 5. Sollicitations (tranche les quatre plafonds contradictoires)

- Au plus 3 notifications par jour : plan du matin, bilan du soir, UNE en journée (priorité : échéance du jour
  non faite > dérive du rythme > projet prioritaire négligé). Le jour de la revue de la semaine, elle remplace le
  bilan du soir, jamais une quatrième. Un rappel que l'utilisateur a lui-même posé sur une tâche (« rappelle-moi
  à 15 h ») n'est pas une sollicitation et ne compte pas dans le plafond.
- Hors fenêtre de la société ou après son heure limite personnelle : la sollicitation est SAUTÉE, jamais différée.
  Rien en congé. Pause d'un type après 14 ignorées de suite, annoncée dans l'app (la simulation a montré qu'une
  pause après 6 coupait à tort le matin de quelqu'un qui ouvre 1 notification sur 3).
- `notifications` ne dépend jamais de `taches` : le compte de la pastille est fourni par l'appelant ou relu par le front.

## 6. Ce que la simulation a invalidé — à reprendre dans le L3 « coach »

- La règle publiée (60e centile de 9 jours) REFLÈTE le niveau (≈ moyenne + 0,3) : elle ne pousse pas, et un
  utilisateur qui fait un peu moins que l'objectif le voit fondre jusqu'à 0. → Piste retenue : une montée par
  PALIERS, proposée et acceptée (« tu as tenu 5 tâches 4 jours sur 5 : on passe à 6 ? »), plancher à 1, baisse d'un
  cran au plus, jours non travaillés jamais pénalisants, démarrage à froid affiché comme valeur par défaut. À re-simuler.
- « Tenir » : moyenne sur 14 jours, silence de 28 jours après « garder », sinon 2,6 fausses alertes par trimestre
  sur un utilisateur régulier.
- Classement : ordre total strict (dernier critère = `id`) ; une corvée en retard sans priorité ne passe jamais
  devant une échéance client proche ; une tâche reportée 3 fois est à trancher (faire / replanifier / abandonner),
  jamais remontée de force.
- Le compte de tâches seul se truque : il s'affiche avec l'essentiel du jour fait et le taux de plan tenu.

## 7. Fichiers hors `taches` (propriétaires étrangers — éditions minimales, en fin de liste, tâches séparées)

`erp_agentique/urls.py` + `settings/base.py` + `celery.py` (deploy ; `base.py` fait 2 139 lignes : chaque tâche qui
y ajoute déclare « Code net : … lignes nettes attendues ≤ N ») ; `apps/roles/permissions_registre.py` ;
`apps/notifications` (types d'événement, carte des modules, migration — unité paramètres) ; `apps/agent/registry.py`
+ `contract_samples/assistant_reponse.json` ; `backend/fastapi_ia` (consignes du coach, contexte) ;
`frontend/src/features/ia/cartes/*` ; `apps/reporting/calendar.py` ; `authentication/selectors.py` (route d'accueil
mobile) ; `frontend/src/sw.js`, `vite.config.js`, `Layout.jsx`, `lib/apps/appSkus.js` ; `docs/ownership.yml` ;
`docs/openapi-schema.yml` (régénéré) ; `docs/CODEMAP.md`. Une autre session tient des réservations sur `agent`,
`crm`, `erp_agentique`, `scripts`, `ventes` : ces éditions attendent leur libération ou se coordonnent.
