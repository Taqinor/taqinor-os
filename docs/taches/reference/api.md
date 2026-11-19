# Référence de l'API — `apps/taches` (révision 3)

Référence UNIQUE des routes, corps et contrats. Noms des champs et des valeurs : `donnees.md` ; algorithmes :
`regles.md` ; mots : `textes.md` ; ordre de construction : `docs/plans/PLAN_TACHES.md`. Primauté : socle §0/§8 →
A1-A18 → spec-7 révision 3 (mots, routes du front) → `critique-finale.md`, `verif-plan-a-blanc.md`,
`verif-reference.md` et les autres vérifications → specs → design-s1. Les exemples de réponse COMPLETS, recopiables
mot pour mot dans `apps/taches/contract_samples/*.json`, sont dans l'**annexe A** (générés par un seul script, sans
aucun marqueur).

## 0. Conventions

- **Préfixe unique** (C26) : `path('taches/', include('apps.taches.urls'))` AJOUTÉ EN FIN de la liste `_APP_URLS`
  (`erp_agentique/urls.py:28`, montée sous `api/django/`), jamais dans `urlpatterns`. Chaque chemin est écrit EN
  ENTIER ; les actions d'une tâche vivent sous le viewset (`/api/django/taches/taches/{id}/…`). Routes étrangères
  consommées telles quelles : `POST /api/django/records/activities/{id}/done/` et
  `POST /api/django/auth/mobile-home-route/` (`authentication/urls.py:52`).
- **Authentification** : « S » = authentification par défaut (cookie JWT, ou JWT relayé en `Authorization: Bearer`) +
  `taches_voir` (`read_permission = write_permission = 'taches_voir'`, activation par étapes : `donnees.md` inv. 28).
  « J:x » = `JetonAccesAuthentication(x)` SEULE + `IsAuthenticatedInterne` (`authentication/permissions.py:4`) : jeton
  actif de cet usage, compte actif interne, `user_can_operate(user, jeton.company_id)`
  (`authentication/active_company.py:76`), `taches_voir`, module actif, puis `user.company = jeton.company` en mémoire.
  Échec : 401 neutre (404 pour le flux) ; l'authentificateur définit `authenticate_header` (sinon DRF rendrait 403) ;
  tant que `JetonAccesAuthentication` n'est pas livrée, les trois vues à jeton portent un BOUCHON qui refuse tout en
  401 avec `authenticate_header`. `?reponse=texte` → corps `text/plain` (`textes.md` §7). Débits : `throttles.py`
  (capture 60/h et 200/j, flux 60/h, tuile 120/h ; 429).
- **Verrou 409** (colonne « 409 » = oui) : `lock_version` obligatoire (absent → 400 `{"lock_version":["Requis."]}`) ;
  périmé → 409 forme `erreurs.json`.`conflit_version` (`actuel` = TACHE complète). Routes d'action : comparaison
  `version_envoyee()` sous `select_for_update()` dans `planifier(version=…)`. Le front garde la saisie en cours et
  propose « Garder la mienne » (renvoi avec `actuel.lock_version`) ou « Prendre l'autre » (A16-N8). Services partagés
  (lot, rituels, alléger, retour) : `select_for_update()` sans version.
- **Autres 409** (toujours un `code`) : `nom_pris`, `proposition_expiree`, `autre_compte`, `deja_lie`,
  `effacement_occupe` (`tout-effacer/` : une ligne du compte était verrouillée par une autre écriture plus de
  5 s — `lock_timeout` posé dans la transaction —, ou la suppression a dépassé le `statement_timeout` : la
  transaction est défaite en entier, RIEN n'est effacé ; jamais un 500) (`erreurs.json`).
- **Refus d'ÉTAT = 409 `state_conflict`** (r2 CI api-fuzz, L2 r3) : un refus qui dépend de l'état lu en base et que le
  schéma ne peut pas dire — nom de projet, d'étape, d'étiquette ou de vue déjà pris, série déjà ouverte, rappel sur une
  date absente ou sur une tâche close, plafond de rappels, `sauter` une tâche qui ne se répète pas, voisin hors de la
  liste ordonnée, boucle de blocage, « Déjà « X » cette semaine » (revue), heure ou ★ déjà posées (`journee/`) —
  répond 409, corps `{"<champ>":["…"],"detail":"…","code":"state_conflict"}` (le champ fautif ET la forme `{detail,
  code}` ; `entrees.refus_etat`, `core.conflit_etat.ConflitEtat`). Un identifiant BIEN FORMÉ du corps d'une action
  (`projet_id`, `projet_cible_id`…) qui ne désigne rien du compte répond 404 au même corps `{"<champ>":["…"],"detail"}`
  (`entrees.introuvable`). Restent 400 : les erreurs de forme et de borne, et « Projet inexistant. » d'une ligne de
  saisie ou du PATCH d'une tâche. L'écran dit un 409 `state_conflict` ou un 404 qui nomme un champ SOUS le champ : avec
  `{ erreurSousLeChamp: true }`, `tachesApi.js` le rend à l'appelant en 400 de champ (`response.statutServeur` garde le
  vrai statut), sans toast ni annonce.
- **Idempotence** : `client_id` (par tâche, `:<n>` par ligne d'un texte multi-lignes) ; `Idempotency-Key` : chaque vue
  qui la porte MÉLANGE `IdempotentCreateMixin` (`core/idempotency.py:202`) et appelle sa méthode
  `_avec_idempotence(request, creer, suffixe=f'u{user.pk}')` (`:234`), sinon deux collègues rejoueraient la réponse de
  l'autre ; « N » = naturelle.
- **`geste_id`** rendu par toute écriture SAUF : jetons, `vu/`, `tout-effacer/`, `PATCH reglages/`,
  `reglages-societe/`, `agendas-externes/`, `reordonner/`, `projets/trier-par-priorite/`.
- **Erreurs** (une forme, tutoiement, A17) : 400 `{"<champ>":["message"]}` ; par ligne ou id
  `{"lignes":{"3":{"titre":["…"]}}}`, `{"choix":{"53":["…"]}}` ; 401/404/429 `{"detail":"…"}`. L'id d'un autre
  propriétaire répond comme un id inconnu. Textes : `textes.md` §2.16. Échantillon : `erreurs.json`.
- **Création validée au doigt sur une carte du Copilote** : le front pose `X-Taqinor-Carte-Assistant: 1` sur
  `POST taches/` et `POST saisie-rapide/` (option `carteAssistant` de `tachesApi.js`) ; la tâche créée porte
  `source = 'assistant'` (A5). La porte reste l'écran : ses validations, sa réponse en clair, aucun masquage,
  aucun 403 ; toute autre valeur de l'en-tête est ignorée ; avec `X-Taqinor-Assistant`, le mode assistant
  l'emporte. Même origine que la page (nginx) : aucun réglage CORS n'en dépend.
- **Secret porté par une adresse** : le jeton du flux est DANS l'adresse (`…/taches/flux/<jeton>.ics`, imposé par
  l'iPhone). L'app déclare ses motifs à `core.chemins_sensibles` (`auth_jeton.CHEMINS_SENSIBLES`, à `ready()`) :
  les journaux de Django (JSON, accès, requêtes lentes, piles) et Sentry (erreurs et transactions) ne voient que
  `…/flux/<masqué>.ics`. Le journal d'accès de nginx, lui, écrit encore l'adresse entière (réglage du serveur).
- **Requête « assistant » — échec FERMÉ (A18, verif-plan B9)**. QUI pose l'en-tête : le relais du service IA,
  `backend/fastapi_ia/app/services/action_tools.py` `_django_call(…, headers={"X-Taqinor-Assistant": "1"})` (paramètre
  `headers=` de la fonction, `:151`) pour TOUT appel d'une action `taches.*` ; `internal_headers()` reste inchangé ; un
  test côté `fastapi_ia` le garde. CE QUE FAIT DJANGO : une requête `taches` est traitée comme « assistant » si elle
  porte l'en-tête OU si elle est authentifiée par `Authorization: Bearer <JWT>` (le relais relaie toujours le JWT ainsi,
  `action_tools.py:173-178` ; le navigateur n'envoie que le cookie). En mode assistant : titres et noms par
  `nom_pour(…,'assistant')`, `notes` jamais servies, `filtrer_q(assistant=True)`, rendez-vous externes titrés
  « Rendez-vous », 403 sur `reglages/`, `reglages-societe/`, `jetons/`, `mes-donnees/`, `tout-effacer/`,
  `agendas-externes/` et sur `planification/apercu/` d'un projet confidentiel. Un en-tête absent ne sert donc jamais
  du clair au relais. Sous l'en-tête assistant, un modèle confidentiel est absent de `modeles/` et son id répond 404
  « Introuvable. » (fiche, renommer, supprimer, instancier) ; les notes des tâches d'un modèle ne sont jamais servies à
  l'assistant.
- **OpenAPI** : `@extend_schema(request=, responses=, parameters=)` partout ; paramètres de requête déclarés ; types
  `text/calendar` (flux) et `text/plain` (capture) déclarés.
- **Pagination** : `StandardPagination` (50, enveloppe `{"count","next","previous","results"}`, lue avec
  `fetchAllPages`) pour `taches/`, `projets/`, `etiquettes/`, `modeles/`. Les listes à plafond renvoient un OBJET
  `{"results":[…]}` non paginé (`pagination_class = None`) : `suggestions/` (≤ 20), `vues/` (≤ 30), `gestes/` (7
  jours, ≤ 200), `jetons/` (≤ 20), `agendas-externes/` (≤ 3). Aucune route ne renvoie un tableau nu
  (`check_api_shapes.py:1162` exige un objet).
- **Réglages déclarés dès l'échafaudage de l'app** (`settings/base.py`, même tâche que `INSTALLED_APPS`) :
  `TACHES_RACCOURCI_SIRI_URL = os.environ.get('TACHES_RACCOURCI_SIRI_URL', '')` ; le coupe-circuit est une donnée
  (`ReglagesSociete.balayage_actif`, `donnees.md` §2.21), pas un réglage d'environnement.

## 1. Formes partagées (une seule chacune ; échantillons complets en annexe A)

**ITEM**
```json
{
 "type": "tache",
 "id": 20,
 "titre": "Devis Settat",
 "statut": "a_faire",
 "projet": {
  "id": 3,
  "nom": "Ventes",
  "couleur": "vert",
  "priorite": 3
 },
 "section": null,
 "parent_id": null,
 "priorite": 2,
 "jour_prevu": "2026-11-17",
 "moment": "matin",
 "heure_debut": "10:00",
 "echeance": "2026-11-19",
 "echeance_heure": null,
 "quelque_jour": false,
 "estimation_minutes": 60,
 "reports": 0,
 "rang": 1024,
 "motif": null,
 "raison": null,
 "explication": "échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes",
 "rappel": null,
 "lien": null,
 "checklist": null,
 "sous_taches": null,
 "recurrente": false,
 "routine": false,
 "jalon": false,
 "bloquee_par": null,
 "en_attente_de": "",
 "essentielle": true,
 "prevue_au_plan": true,
 "confidentiel": false,
 "confidentielle": false,
 "source": "rapide",
 "peut_cloturer": true,
 "a_notes": true,
 "fait_le": null,
 "lock_version": 4
}
```

**TACHE**
```json
{
 "type": "tache",
 "id": 20,
 "titre": "Devis Settat",
 "statut": "a_faire",
 "projet": {
  "id": 3,
  "nom": "Ventes",
  "couleur": "vert",
  "priorite": 3
 },
 "section": null,
 "parent_id": null,
 "priorite": 2,
 "jour_prevu": "2026-11-17",
 "moment": "matin",
 "heure_debut": "10:00",
 "echeance": "2026-11-19",
 "echeance_heure": null,
 "quelque_jour": false,
 "estimation_minutes": 60,
 "reports": 0,
 "rang": 1024,
 "motif": null,
 "raison": null,
 "explication": "échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes",
 "rappel": {
  "jour": "2026-11-17",
  "heure": "09:45"
 },
 "lien": {
  "cible": "ventes.devis",
  "id": 512,
  "libelle": "DEV-2026-11-0042",
  "url": "/ventes/devis?devis=512",
  "etat": "ok"
 },
 "checklist": {
  "faits": 1,
  "total": 1
 },
 "sous_taches": {
  "faites": 0,
  "total": 1
 },
 "recurrente": false,
 "routine": false,
 "jalon": false,
 "bloquee_par": null,
 "en_attente_de": "",
 "essentielle": true,
 "prevue_au_plan": true,
 "confidentiel": false,
 "confidentielle": false,
 "source": "rapide",
 "peut_cloturer": true,
 "a_notes": true,
 "fait_le": null,
 "lock_version": 4,
 "notes": "Appeler avant 11 h.",
 "etiquettes": [
  {
   "id": 2,
   "nom": "magasin",
   "couleur": "ciel"
  }
 ],
 "elements_checklist": [
  {
   "id": 71,
   "libelle": "Prix",
   "fait": true,
   "rang": 1024
  }
 ],
 "enfants": [
  {
   "type": "tache",
   "id": 22,
   "titre": "Relire les quantités",
   "statut": "a_faire",
   "projet": {
    "id": 3,
    "nom": "Ventes",
    "couleur": "vert",
    "priorite": 3
   },
   "section": null,
   "parent_id": 20,
   "priorite": 0,
   "jour_prevu": null,
   "moment": "",
   "heure_debut": null,
   "echeance": null,
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": null,
   "reports": 0,
   "rang": 1024,
   "motif": null,
   "raison": null,
   "explication": "dans Ventes",
   "rappel": null,
   "lien": null,
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "",
   "essentielle": false,
   "prevue_au_plan": false,
   "confidentiel": false,
   "confidentielle": false,
   "source": "rapide",
   "peut_cloturer": true,
   "a_notes": false,
   "fait_le": null,
   "lock_version": 0
  }
 ],
 "recurrence": null,
 "rappels": [
  {
   "id": 31,
   "jour": "2026-11-17",
   "heure": "09:45",
   "ancre": "",
   "decalage_jours": 0,
   "statut": "en_attente"
  }
 ],
 "triee_le": "2026-11-16T18:02:00+01:00",
 "premier_jour_prevu": "2026-11-17",
 "reports_tranches": 0,
 "duree_reelle_minutes": null,
 "annule_le": null,
 "occurrence_du": null,
 "activite_origine_id": null,
 "lien_verifie_le": "2026-11-17T09:12:00+01:00",
 "created_at": "2026-11-16T18:02:00+01:00",
 "updated_at": "2026-11-17T10:42:00+01:00"
}
```

**TACHE_ECRITE**
```json
{
 "tache": {
  "type": "tache",
  "id": 20,
  "titre": "Devis Settat",
  "statut": "a_faire",
  "projet": {
   "id": 3,
   "nom": "Ventes",
   "couleur": "vert",
   "priorite": 3
  },
  "section": null,
  "parent_id": null,
  "priorite": 2,
  "jour_prevu": "2026-11-17",
  "moment": "matin",
  "heure_debut": "10:00",
  "echeance": "2026-11-19",
  "echeance_heure": null,
  "quelque_jour": false,
  "estimation_minutes": 60,
  "reports": 0,
  "rang": 1024,
  "motif": null,
  "raison": null,
  "explication": "échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes",
  "rappel": {
   "jour": "2026-11-17",
   "heure": "09:45"
  },
  "lien": {
   "cible": "ventes.devis",
   "id": 512,
   "libelle": "DEV-2026-11-0042",
   "url": "/ventes/devis?devis=512",
   "etat": "ok"
  },
  "checklist": {
   "faits": 1,
   "total": 1
  },
  "sous_taches": {
   "faites": 0,
   "total": 1
  },
  "recurrente": false,
  "routine": false,
  "jalon": false,
  "bloquee_par": null,
  "en_attente_de": "",
  "essentielle": true,
  "prevue_au_plan": true,
  "confidentiel": false,
  "confidentielle": false,
  "source": "rapide",
  "peut_cloturer": true,
  "a_notes": true,
  "fait_le": null,
  "lock_version": 4,
  "notes": "Appeler avant 11 h.",
  "etiquettes": [
   {
    "id": 2,
    "nom": "magasin",
    "couleur": "ciel"
   }
  ],
  "elements_checklist": [
   {
    "id": 71,
    "libelle": "Prix",
    "fait": true,
    "rang": 1024
   }
  ],
  "enfants": [
   {
    "type": "tache",
    "id": 22,
    "titre": "Relire les quantités",
    "statut": "a_faire",
    "projet": {
     "id": 3,
     "nom": "Ventes",
     "couleur": "vert",
     "priorite": 3
    },
    "section": null,
    "parent_id": 20,
    "priorite": 0,
    "jour_prevu": null,
    "moment": "",
    "heure_debut": null,
    "echeance": null,
    "echeance_heure": null,
    "quelque_jour": false,
    "estimation_minutes": null,
    "reports": 0,
    "rang": 1024,
    "motif": null,
    "raison": null,
    "explication": "dans Ventes",
    "rappel": null,
    "lien": null,
    "checklist": null,
    "sous_taches": null,
    "recurrente": false,
    "routine": false,
    "jalon": false,
    "bloquee_par": null,
    "en_attente_de": "",
    "essentielle": false,
    "prevue_au_plan": false,
    "confidentiel": false,
    "confidentielle": false,
    "source": "rapide",
    "peut_cloturer": true,
    "a_notes": false,
    "fait_le": null,
    "lock_version": 0
   }
  ],
  "recurrence": null,
  "rappels": [
   {
    "id": 31,
    "jour": "2026-11-17",
    "heure": "09:45",
    "ancre": "",
    "decalage_jours": 0,
    "statut": "en_attente"
   }
  ],
  "triee_le": "2026-11-16T18:02:00+01:00",
  "premier_jour_prevu": "2026-11-17",
  "reports_tranches": 0,
  "duree_reelle_minutes": null,
  "annule_le": null,
  "occurrence_du": null,
  "activite_origine_id": null,
  "lien_verifie_le": "2026-11-17T09:12:00+01:00",
  "created_at": "2026-11-16T18:02:00+01:00",
  "updated_at": "2026-11-17T10:42:00+01:00"
 },
 "suivante": null,
 "projet_cree": null,
 "rappel": null,
 "question_titres": false,
 "avertissements": [
  {
   "code": "prevue_apres_echeance",
   "message": "Prévue après l'échéance."
  }
 ],
 "progression": null,
 "geste_id": 77
}
```

**PROJET**
```json
{
 "id": 3,
 "nom": "Ventes",
 "objectif": "Fini quand les 4 devis sont signés",
 "icone": "",
 "couleur": "vert",
 "priorite": 3,
 "statut": "actif",
 "statut_depuis": "2026-10-01T09:00:00+01:00",
 "domaine": "",
 "date_debut": null,
 "echeance": "2026-12-15",
 "termine_le": null,
 "issue": "",
 "bilan": "",
 "planification_le": "2026-10-01T09:05:00+01:00",
 "rang": 2048,
 "confidentiel": false,
 "affichage": {
  "vue": "liste",
  "tri": "manuel",
  "groupe": "section",
  "montrer_faites": false
 },
 "a_planifier": false,
 "compteurs": {
  "ouvertes": 8,
  "faites": 12
 },
 "sante": [
  {
   "code": "a_l_arret",
   "phrase": "Rien de fait depuis 10 jours travaillés.",
   "donnees": {
    "jours": 10,
    "depuis": "2026-11-03"
   }
  }
 ],
 "focus_semaine": false,
 "updated_at": "2026-11-16T18:00:00+01:00",
 "lock_version": 4
}
```

**PROPOSITION**
```json
{
 "id": 41,
 "type": "proposition_palier",
 "cle": "monter",
 "texte": "Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?",
 "donnees": {
  "N": 5,
  "N1": 6,
  "tenus": 7
 },
 "boutons": [
  {
   "reponse": "oui",
   "libelle": "Monter à 6"
  },
  {
   "reponse": "pas_maintenant",
   "libelle": "Pas maintenant"
  }
 ],
 "expire_le": "2026-11-24"
}
```

**CARTE_DU_MOMENT**
```json
{
 "type": "rythme",
 "proposition": {
  "id": 41,
  "type": "proposition_palier",
  "cle": "monter",
  "texte": "Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?",
  "donnees": {
   "N": 5,
   "N1": 6,
   "tenus": 7
  },
  "boutons": [
   {
    "reponse": "oui",
    "libelle": "Monter à 6"
   },
   {
    "reponse": "pas_maintenant",
    "libelle": "Pas maintenant"
   }
  ],
  "expire_le": "2026-11-24"
 },
 "donnees": {}
}
```

**OBJECTIF**
```json
{
 "nb": 5,
 "source": "accepte",
 "mode": "pousser",
 "zone": null
}
```

**PROGRESSION**
```json
{
 "faites": 1,
 "detail": {
  "etapes": 0,
  "routines": 0,
  "micro_non_comptees": 0,
  "activites_closes": 0
 },
 "prevues": 4,
 "essentiel_faites": 0,
 "essentiel_prevues": 1,
 "plan_tenues": 1,
 "plan_lignes": 4,
 "minutes_prevues": 75,
 "sans_estimation": 1,
 "capacite_minutes": 240,
 "capacite_source": "defaut",
 "rendez_vous_minutes": 60,
 "disponible_minutes": 180,
 "activites_closes": 0,
 "activites": 1,
 "reprise": false
}
```

**LIEN**
```json
{
 "cible": "crm.lead",
 "id": 1637,
 "libelle": "Karim Benali",
 "url": "/crm/leads?lead=1637",
 "etat": "ok"
}
```

**RENDEZ_VOUS**
```json
{
 "cle": "2-9f2c1a7b",
 "agenda_id": 2,
 "agenda": "Microsoft 365",
 "titre": "Réunion banque",
 "debut": "2026-11-17T11:00:00+01:00",
 "fin": "2026-11-17T12:00:00+01:00",
 "journee_entiere": false
}
```

**RYTHME**
```json
{
 "mode": "pousser",
 "comprendre_mon_rythme": true,
 "objectif": {
  "nb": 5,
  "source": "accepte",
  "mode": "pousser",
  "zone": null
 },
 "trace": "5 faites ou plus 7 jours sur 10",
 "bloc": {
  "jours": 7,
  "tenus": 5,
  "sur": 10
 },
 "tenir": null,
 "proposition": {
  "id": 41,
  "type": "proposition_palier",
  "cle": "monter",
  "texte": "Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?",
  "donnees": {
   "N": 5,
   "N1": 6,
   "tenus": 7
  },
  "boutons": [
   {
    "reponse": "oui",
    "libelle": "Monter à 6"
   },
   {
    "reponse": "pas_maintenant",
    "libelle": "Pas maintenant"
   }
  ],
  "expire_le": "2026-11-24"
 },
 "serie": [
  {
   "jour": "2026-11-16",
   "statut_jour": "evalue",
   "faites": 5,
   "objectif": 5,
   "essentiel_faites": 1,
   "essentiel_prevues": 1,
   "plan_tenues": 4,
   "plan_lignes": 5
  }
 ],
 "constats": [
  {
   "id": 44,
   "type": "constat",
   "cle": "C3",
   "texte": "Vendredi : 3,1 tâches en moyenne, 5,2 les autres jours.",
   "donnees": {
    "jour": 4,
    "m1": 3.1,
    "m2": 5.2
   },
   "boutons": [
    {
     "reponse": "oui",
     "libelle": "Oui"
    },
    {
     "reponse": "pas_maintenant",
     "libelle": "Pas maintenant"
    }
   ],
   "expire_le": "2026-11-24"
  }
 ],
 "repere": {
  "p60": 5.5,
  "jours": 9
 },
 "preferences": [
  {
   "cle": "heure_limite",
   "valeur": "19:00",
   "source": "copilote",
   "dite_le": "2026-11-17T09:00:00+01:00"
  }
 ],
 "geste_id": null
}
```


Notes : `ITEM.rang` = `rang_jour` dans une section du jour, `rang_projet` dans un projet (`donnees.md` inv. 32) ;
`confidentiel` = drapeau propre (écrit par PATCH), `confidentielle` = effectif hérité ; `bloquee_par` `{"id","titre"}`
(titre par `nom_pour`) ; `motif` (À revoir) et `raison` `{"code","texte"}` (Proposé, `RaisonPropose`) sont nuls hors
de leur section ; une activité ERP a la même forme (`type:"activite"`, champs sans objet nuls/faux,
`lock_version:null`). `a_notes` : la tâche porte une note (l'indice « note » de la ligne) — toujours `false` sous
l'en-tête assistant (les notes ne lui sont jamais servies, `regles.md` §8) et pour une activité ; `fait_le` : l'instant
où la tâche a été faite (`done_at` d'une activité close), `null` sinon — tous deux lus de colonnes déjà chargées,
aucune requête de plus par ligne. TACHE = ITEM + champs de fiche (`updated_at` sert le bandeau de conflit ; `essentielle` / `prevue_au_plan` d'une TACHE — fiche `GET taches/{id}/` ou TACHE_ECRITE — sont lus du plan du jour, comme dans la journée : Révision 3.3, couture L7). TACHE_ECRITE :
`suivante` = occurrence née (terminer, sauter) ; `progression` posée par terminer/rouvrir ; `question_titres` vrai au
premier rappel tant que `titres_notifications_demande_le` est nul (A17-T4) ; avertissements `prevue_apres_echeance`,
`jour_non_travaille`, `hors_fenetre`, `echeance_aujourdhui` (R3-002 : « L'échéance reste aujourd'hui. », la tâche
reportée reste dans la journée). CARTE_DU_MOMENT : une seule, choisie par le serveur (`retour`, `rythme`, `pause`,
`revelation` portent une PROPOSITION ; `bilan_hier` `{"jour"}` ; `garder` `{"n","objectif"}` ; `alleger` `{"faites",
"prevues"}` ; `faire_bilan` `{}`). OBJECTIF : `zone` `[bas, haut]` en `tenir`, `nb:null` en `libre`. PROGRESSION :
l'écran montre « faites sur OBJECTIF » ; `essentiel_faites`/`essentiel_prevues` = les ★ de la section Essentiel
SERVIE (ouvertes, ou faites aujourd'hui), comptées une fois (R3-001) ; `plan_tenues`/`plan_lignes` restent servis pour
la nuit mais ne sont plus montrés (aucun « x des y gardées », R3-001) ;
`disponible_minutes` = `capacite_minutes` − `rendez_vous_minutes` (inv. 35) ; `reprise` vrai le jour d'une carte
`retour`. RENDEZ_VOUS : un événement d'agenda externe, lecture seule, JAMAIS une tâche (`cle` stable, hachée).

## 2. `GET /api/django/taches/aujourdhui/?jour=&tout=` — LE contrat de la journée

Clés dans l'ORDRE VERTICAL (spec-7 r3 §4) : `progression` ; `carte_du_moment` ; `essentiel` ; `obligations` (bande
« Toute la journée » : visites, poses, interventions, sans heure ; ligne « Suivi des relances ») ; `rendez_vous`
(agendas externes, à leur heure, lecture seule) mêlés par le front à `journee` (« Prévu ») ; `ce_soir` ; `propose` ;
repliés `a_decider` (« À revoir »), `en_attente`, `faites`, « Ailleurs dans l'ERP » (route paresseuse). `jour` défaut
J ; `tout=1` remplit `propose.suite_par_projet` (« Voir toutes les tâches de mes projets », groupé par projet) ;
plafond 200 lignes (`tronque`). Exemple complet (le même que `aujourdhui.json` de l'annexe A, `suite_par_projet` nul
sans `tout=1`) :
```json
{
 "jour": "2026-11-17",
 "maintenant": "2026-11-17T09:12:00+01:00",
 "jour_ouvre": true,
 "prochain_jour_ouvre": "2026-11-19",
 "objectif": {
  "nb": 5,
  "source": "accepte",
  "mode": "pousser",
  "zone": null
 },
 "progression": {
  "faites": 1,
  "detail": {
   "etapes": 0,
   "routines": 0,
   "micro_non_comptees": 0,
   "activites_closes": 0
  },
  "prevues": 4,
  "essentiel_faites": 0,
  "essentiel_prevues": 1,
  "plan_tenues": 1,
  "plan_lignes": 4,
  "minutes_prevues": 75,
  "sans_estimation": 1,
  "capacite_minutes": 240,
  "capacite_source": "defaut",
  "rendez_vous_minutes": 60,
  "disponible_minutes": 180,
  "activites_closes": 0,
  "activites": 1,
  "reprise": false
 },
 "plan": {
  "planifie_le": "2026-11-17T08:40:00+01:00",
  "cloture_le": null,
  "allege_le": null
 },
 "carte_du_moment": {
  "type": "rythme",
  "proposition": {
   "id": 41,
   "type": "proposition_palier",
   "cle": "monter",
   "texte": "Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?",
   "donnees": {
    "N": 5,
    "N1": 6,
    "tenus": 7
   },
   "boutons": [
    {
     "reponse": "oui",
     "libelle": "Monter à 6"
    },
    {
     "reponse": "pas_maintenant",
     "libelle": "Pas maintenant"
    }
   ],
   "expire_le": "2026-11-24"
  },
  "donnees": {}
 },
 "essentiel": [
  {
   "type": "tache",
   "id": 20,
   "titre": "Devis Settat",
   "statut": "a_faire",
   "projet": {
    "id": 3,
    "nom": "Ventes",
    "couleur": "vert",
    "priorite": 3
   },
   "section": null,
   "parent_id": null,
   "priorite": 2,
   "jour_prevu": "2026-11-17",
   "moment": "matin",
   "heure_debut": "10:00",
   "echeance": "2026-11-19",
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": 60,
   "reports": 0,
   "rang": 1024,
   "motif": null,
   "raison": null,
   "explication": "échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes",
   "rappel": null,
   "lien": null,
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "",
   "essentielle": true,
   "prevue_au_plan": true,
   "confidentiel": false,
   "confidentielle": false,
   "source": "rapide",
   "peut_cloturer": true,
   "a_notes": true,
   "fait_le": null,
   "lock_version": 4
  }
 ],
 "obligations": [
  {
   "famille": "visite",
   "id": 88,
   "titre": "Visite — Karim Benali",
   "jour": "2026-11-17",
   "url": "/visites"
  },
  {
   "famille": "pose",
   "id": 42,
   "titre": "Pose — INS-0042",
   "jour": "2026-11-17",
   "url": "/chantiers?id=42"
  },
  {
   "famille": "touches",
   "id": null,
   "titre": "Suivi des relances",
   "jour": "2026-11-17",
   "nb": 5,
   "en_retard": 2,
   "url": "/crm/relances"
  }
 ],
 "rendez_vous": [
  {
   "cle": "2-9f2c1a7b",
   "agenda_id": 2,
   "agenda": "Microsoft 365",
   "titre": "Réunion banque",
   "debut": "2026-11-17T11:00:00+01:00",
   "fin": "2026-11-17T12:00:00+01:00",
   "journee_entiere": false
  }
 ],
 "journee": [
  {
   "type": "tache",
   "id": 42,
   "titre": "Timbres",
   "statut": "a_faire",
   "projet": null,
   "section": null,
   "parent_id": null,
   "priorite": 0,
   "jour_prevu": "2026-11-17",
   "moment": "",
   "heure_debut": null,
   "echeance": null,
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": 15,
   "reports": 0,
   "rang": null,
   "motif": null,
   "raison": null,
   "explication": "prévue aujourd'hui",
   "rappel": null,
   "lien": null,
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "",
   "essentielle": false,
   "prevue_au_plan": true,
   "confidentiel": false,
   "confidentielle": false,
   "source": "manuel",
   "peut_cloturer": true,
   "a_notes": false,
   "fait_le": null,
   "lock_version": 1
  },
  {
   "type": "activite",
   "id": 101,
   "titre": "Rappeler Benali",
   "statut": "a_faire",
   "projet": null,
   "section": null,
   "parent_id": null,
   "priorite": 0,
   "jour_prevu": "2026-11-17",
   "moment": "",
   "heure_debut": null,
   "echeance": null,
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": null,
   "reports": 0,
   "rang": null,
   "motif": null,
   "raison": null,
   "explication": "activité ERP du jour",
   "rappel": null,
   "lien": {
    "cible": "crm.lead",
    "id": 1637,
    "libelle": "Karim Benali",
    "url": "/crm/leads?lead=1637",
    "etat": "ok"
   },
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "",
   "essentielle": false,
   "prevue_au_plan": true,
   "confidentiel": false,
   "confidentielle": false,
   "source": null,
   "peut_cloturer": false,
   "a_notes": false,
   "fait_le": null,
   "lock_version": null
  }
 ],
 "ce_soir": [
  {
   "type": "tache",
   "id": 60,
   "titre": "Préparer offre",
   "statut": "a_faire",
   "projet": {
    "id": 5,
    "nom": "Maison",
    "couleur": "ambre",
    "priorite": 2
   },
   "section": null,
   "parent_id": null,
   "priorite": 0,
   "jour_prevu": "2026-11-17",
   "moment": "soir",
   "heure_debut": null,
   "echeance": null,
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": null,
   "reports": 0,
   "rang": null,
   "motif": null,
   "raison": null,
   "explication": "prévue ce soir",
   "rappel": null,
   "lien": null,
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "",
   "essentielle": false,
   "prevue_au_plan": false,
   "confidentiel": false,
   "confidentielle": false,
   "source": "rapide",
   "peut_cloturer": true,
   "a_notes": false,
   "fait_le": null,
   "lock_version": 0
  }
 ],
 "propose": {
  "replie": false,
  "pour_objectif": [
   {
    "type": "tache",
    "id": 21,
    "titre": "Déclaration TVA",
    "statut": "a_faire",
    "projet": {
     "id": 4,
     "nom": "Admin",
     "couleur": "prune",
     "priorite": 1
    },
    "section": null,
    "parent_id": null,
    "priorite": 3,
    "jour_prevu": null,
    "moment": "",
    "heure_debut": null,
    "echeance": "2026-11-19",
    "echeance_heure": null,
    "quelque_jour": false,
    "estimation_minutes": 30,
    "reports": 0,
    "rang": null,
    "motif": null,
    "raison": {
     "code": "echeance_proche",
     "texte": "échéance jeudi"
    },
    "explication": "échéance jeudi",
    "rappel": null,
    "lien": null,
    "checklist": null,
    "sous_taches": null,
    "recurrente": false,
    "routine": false,
    "jalon": false,
    "bloquee_par": null,
    "en_attente_de": "",
    "essentielle": false,
    "prevue_au_plan": false,
    "confidentiel": false,
    "confidentielle": false,
    "source": "rapide",
    "peut_cloturer": true,
    "a_notes": false,
    "fait_le": null,
    "lock_version": 2
   },
   {
    "type": "tache",
    "id": 41,
    "titre": "Ranger le bureau",
    "statut": "a_faire",
    "projet": null,
    "section": null,
    "parent_id": null,
    "priorite": 0,
    "jour_prevu": "2026-11-16",
    "moment": "",
    "heure_debut": null,
    "echeance": null,
    "echeance_heure": null,
    "quelque_jour": false,
    "estimation_minutes": null,
    "reports": 0,
    "rang": null,
    "motif": null,
    "raison": {
     "code": "retard",
     "texte": "prévue hier"
    },
    "explication": "prévue hier",
    "rappel": null,
    "lien": null,
    "checklist": null,
    "sous_taches": null,
    "recurrente": false,
    "routine": false,
    "jalon": false,
    "bloquee_par": null,
    "en_attente_de": "",
    "essentielle": false,
    "prevue_au_plan": false,
    "confidentiel": false,
    "confidentielle": false,
    "source": "manuel",
    "peut_cloturer": true,
    "a_notes": false,
    "fait_le": null,
    "lock_version": 3
   },
   {
    "type": "tache",
    "id": 30,
    "titre": "Préparer formation",
    "statut": "a_faire",
    "projet": {
     "id": 7,
     "nom": "Équipe",
     "couleur": "bleu",
     "priorite": 3
    },
    "section": null,
    "parent_id": null,
    "priorite": 0,
    "jour_prevu": null,
    "moment": "",
    "heure_debut": null,
    "echeance": null,
    "echeance_heure": null,
    "quelque_jour": false,
    "estimation_minutes": 45,
    "reports": 0,
    "rang": null,
    "motif": null,
    "raison": {
     "code": "prochaine_action",
     "texte": "prochaine action de Équipe"
    },
    "explication": "prochaine action de Équipe",
    "rappel": null,
    "lien": null,
    "checklist": null,
    "sous_taches": null,
    "recurrente": false,
    "routine": false,
    "jalon": false,
    "bloquee_par": null,
    "en_attente_de": "",
    "essentielle": false,
    "prevue_au_plan": false,
    "confidentiel": false,
    "confidentielle": false,
    "source": "manuel",
    "peut_cloturer": true,
    "a_notes": false,
    "fait_le": null,
    "lock_version": 2
   }
  ],
  "reste_nb": 6,
  "charge": {
   "minutes_estimees": 150,
   "disponible_minutes": 180,
   "surcharge": false
  },
  "suite_par_projet": null
 },
 "a_decider": [
  {
   "type": "tache",
   "id": 50,
   "titre": "Site web",
   "statut": "a_faire",
   "projet": {
    "id": 9,
    "nom": "SiteWeb",
    "couleur": "indigo",
    "priorite": 2
   },
   "section": null,
   "parent_id": null,
   "priorite": 1,
   "jour_prevu": "2026-11-13",
   "moment": "",
   "heure_debut": null,
   "echeance": null,
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": null,
   "reports": 3,
   "rang": null,
   "motif": "reportee_3_fois",
   "raison": null,
   "explication": "reportée 3 fois",
   "rappel": null,
   "lien": null,
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "",
   "essentielle": false,
   "prevue_au_plan": false,
   "confidentiel": false,
   "confidentielle": false,
   "source": "rapide",
   "peut_cloturer": true,
   "a_notes": false,
   "fait_le": null,
   "lock_version": 6
  }
 ],
 "en_attente": [
  {
   "type": "tache",
   "id": 51,
   "titre": "Retour Lydec",
   "statut": "en_attente",
   "projet": null,
   "section": null,
   "parent_id": null,
   "priorite": 0,
   "jour_prevu": "2026-11-17",
   "moment": "",
   "heure_debut": null,
   "echeance": null,
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": null,
   "reports": 0,
   "rang": null,
   "motif": null,
   "raison": null,
   "explication": "en attente de : Lydec",
   "rappel": null,
   "lien": null,
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "Lydec",
   "essentielle": false,
   "prevue_au_plan": false,
   "confidentiel": false,
   "confidentielle": false,
   "source": "manuel",
   "peut_cloturer": true,
   "a_notes": false,
   "fait_le": null,
   "lock_version": 3
  }
 ],
 "faites": [
  {
   "type": "tache",
   "id": 12,
   "titre": "Dossier subvention",
   "statut": "fait",
   "projet": {
    "id": 4,
    "nom": "Admin",
    "couleur": "prune",
    "priorite": 1
   },
   "section": null,
   "parent_id": null,
   "priorite": 1,
   "jour_prevu": "2026-11-17",
   "moment": "",
   "heure_debut": null,
   "echeance": "2026-11-17",
   "echeance_heure": null,
   "quelque_jour": false,
   "estimation_minutes": 30,
   "reports": 0,
   "rang": null,
   "motif": null,
   "raison": null,
   "explication": "échéance aujourd'hui",
   "rappel": null,
   "lien": null,
   "checklist": null,
   "sous_taches": null,
   "recurrente": false,
   "routine": false,
   "jalon": false,
   "bloquee_par": null,
   "en_attente_de": "",
   "essentielle": false,
   "prevue_au_plan": true,
   "confidentiel": false,
   "confidentielle": false,
   "source": "rapide",
   "peut_cloturer": true,
   "a_notes": false,
   "fait_le": "2026-11-17T09:20:00+01:00",
   "lock_version": 5
  }
 ],
 "a_trier": {
  "boite_reception": 3,
  "bloquees": 1,
  "suggestions": 2,
  "a_convertir": 7
 },
 "tronque": false
}
```
Placement : `donnees.md` inv. 2, 3, 10, 34 et `regles.md` §4.2. `propose.pour_objectif` (A18-M1/M2) : d'abord ce qui
presse (ici « Déclaration TVA », `echeance_proche` ; « Ranger le bureau », `retard`), puis la prochaine action de
chaque projet (« Préparer formation »), puis les actions suivantes, jusqu'à objectif − faites − gardées ouvertes (ce qui presse s'affiche EN ENTIER, même au-delà de N ; le temps disponible ne filtre plus
Proposé : un dépassement s'affiche en surcharge, `charge.surcharge`) ;
`replie:true` et `pour_objectif:[]` le jour où `plan.allege_le` est posé (A16-N6). **Pastille** (`badge/`) = ouverts
GARDÉS d'`essentiel` + `journee` + `ce_soir` (ici 3), jamais Proposé (A16-N5) ; `prevues` = 1 faite + 3 ouverts
gardés = 4 ; `disponible_minutes` = 240 − 60 = 180.

## 3. Toutes les routes

Auth : S / J:x · 409 : oui = `lock_version` requis · Idem. : C `client_id`, K `Idempotency-Key`, N naturelle.

### 3.1 Journée, rituels, agenda

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/aujourdhui/?jour=` | §2 | S | — | — | Aujourd'hui, carte cockpit, carte `ma_journee`, cache hors ligne | socle, A11, A14, spec-7 r3 |
| GET | `/api/django/taches/aujourdhui/ailleurs/` | compteurs « Ailleurs dans l'ERP » | S | — | — | repli | s6a, T13 |
| GET | `/api/django/taches/badge/` | `{"n":3,"jour":"2026-11-17","a_trier":3}` (`a_trier` = `a_trier.boite_reception` d'`aujourdhui/`) | S | — | — | pastille | s6b, A16-N5 |
| POST | `/api/django/taches/vu/` | ouverture du jour ; carte de retour | S | — | N | toute page Tâches | T12, A14-B1 |
| GET | `/api/django/taches/journee/proposition/?jour=&exclure=&inclure=&tout=` | proposition, sans écriture | S | — | — | « Voir tout », carte `plan_propose` | s3, C37, A11 |
| GET | `/api/django/taches/journee/priorites/?jour=` | « Aide-moi à prioriser » : toutes les ouvertes classées, raison, gestes | S | — | — | carte `priorites`, Copilote | A18-M3 |
| GET | `/api/django/taches/journee/point/` | « Où j'en suis ? » | S | — | — | carte `point`, Copilote | A18-M3 |
| POST | `/api/django/taches/journee/planifier/` | « Garder ces N » (seul mode : `express`) | S | — | K | Proposé, carte du moment, carte `plan_propose` | A11, A14-M1, A17-T2 |
| POST | `/api/django/taches/journee/essentiel/` | ★ | S | — | N | ★, appui long | s3 |
| POST | `/api/django/taches/journee/alleger/` | garder k, le reste aux projets sans report | S | — | K | carte de 15 h, ⋯ | A14-M7, A16-N6 |
| GET | `/api/django/taches/journee/cloture/?jour=` | contenu du bilan (J, ou J−1 jusqu'à 12 h) | S | — | — | Bilan du soir | s3, A14-M4 |
| POST | `/api/django/taches/journee/cloturer/` | clore la journée | S | — | K | Bilan du soir | s3, spec-7 r3 |
| GET | `/api/django/taches/agenda/?du=&au=&vue=&projet=` | jours (≤ 42), À placer, Mes projets | S | — | — | Agenda, Planifier ma semaine | s3, s4, A16-N3/N4 |
| GET | `/api/django/taches/recherche/?q=&limite=` | projets + tâches par mots | S | — | — | Recherche, palette, carte `liste_taches` | s5b, C22, A14-M11 |

### 3.2 Saisie, À trier, tâches

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| POST | `/api/django/taches/saisie-rapide/` | analyse, aperçu (`apercu:true`) ou création | S | — | C, K | Saisie, Coller mes listes, carte `capture_apercu`, file hors ligne | s2, C11 |
| POST | `/api/django/taches/capture/` | Siri / partage | J:capture | — | C | raccourci Siri | s6b, A1 |
| GET | `/api/django/taches/taches/?vue=&q=&projet=&section=&etiquette=&priorite_min=&statut=&periode=&tri=&groupe=&inclure_faites=&cible=&cible_id=&ouvertes=` | listes paginées | S | — | — | À trier (`vue=boite`), Plus tard (`vue=quelque_jour`), filtres, ✓+ des fiches ERP (`count`) | s2, s6a |
| POST | `/api/django/taches/taches/` | une tâche (LIGNE) | S | — | C, K | fiche, agenda (créneau vide), Copilote | socle §4 |
| GET | `/api/django/taches/taches/{id}/` | TACHE ; revérifie le lien | S | — | — | Fiche | s6a |
| PATCH | `/api/django/taches/taches/{id}/` | éditer | S | oui | — | Fiche, Renommer | s2, s4 |
| DELETE | `/api/django/taches/taches/{id}/` | supprimer (+ sous-tâches) | S | — | N | Fiche, menu | socle §2.2, min-20 |
| POST | `/api/django/taches/taches/{id}/planifier/` | seul chemin du jour, de l'heure, du moment ; pose sur un jour | S | oui | — | Reporter, Quand, Agenda, Planifier ma semaine, file hors ligne | socle §4, A16-N3 |
| POST | `/api/django/taches/taches/{id}/terminer/` | cocher | S | — | N | case, file hors ligne | s3, A16-N11 |
| POST | `/api/django/taches/taches/{id}/rouvrir/` | décocher | S | — | N | case | s3 |
| POST | `/api/django/taches/taches/{id}/trancher/` | `aujourdhui`/`garder`/`jour`/`un_jour`/`abandonner` | S | — | N | À revoir, Abandonner | s3, MAJ-5 |
| POST | `/api/django/taches/taches/{id}/sauter/` | sauter une occurrence | S | — | N | fiche récurrente | s2 |
| POST | `/api/django/taches/taches/{id}/attendre/` | En attente de… | S | — | N | appui long | s2 |
| POST | `/api/django/taches/taches/{id}/recu/` | reçu | S | — | N | fiche | s2 |
| POST | `/api/django/taches/taches/{id}/reordonner/` | `{"liste","avant_id","apres_id"}` | S | — | N | Réorganiser, `Alt+↑/↓` | s3, M13 |
| POST | `/api/django/taches/taches/{id}/restaurer/` | restaurer | S | — | N | Supprimées récemment | s2 |
| POST | `/api/django/taches/taches/{id}/rappels/` | poser un rappel | S | — | — | Quand → Rappel, Copilote | s3, A17-T4 |
| POST | `/api/django/taches/taches/{id}/changement/apercu/` | écho renommer/abandonner/supprimer | S | — | N | carte `tache` | s5b |
| POST | `/api/django/taches/taches/lot/` | `deplacer` · `planifier` · `prioriser` · `etiqueter` · `terminer` · `supprimer` · `garder_sans_projet` (≤ 200) | S | — | K | sélection, « Tout pour plus tard », « Tout ranger » | s2, C11, C32 |
| POST | `/api/django/taches/taches/lier-activite/` | lier une tâche à une activité ERP (non close) | S | — | K | appui long sur l'activité | A17 |
| POST | `/api/django/taches/convertir-activite/` | convertir `{activite_ids}` ou `{toutes}` (200 partiel) | S | — | N | bandeau d'À trier | s2, s6a, C20 |
| DELETE | `/api/django/taches/rappels/{id}/` | retirer | S | — | N | fiche | s3 |
| POST | `/api/django/taches/rappels/{id}/repeter/` | « Encore 10 min · 1 h · Demain 9 h » | S | — | — | fiche ouverte par le rappel | s3, A17 |
| PATCH | `/api/django/taches/recurrences/{id}/` | modifier (+ `appliquer_a_l_ouverte`), arrêter (`actif:false`) | S | — | — | fiche → Répéter | s2 |
| POST | `/api/django/taches/checklist/` | ajouter un point `{"tache_id","libelle"}` | S | — | — | Fiche | T10 |
| PATCH | `/api/django/taches/checklist/{id}/` | `{"libelle"?,"fait"?}` | S | — | — | Fiche | T10 |
| DELETE | `/api/django/taches/checklist/{id}/` | retirer | S | — | N | Fiche | T10 |
| POST | `/api/django/taches/checklist/{id}/reordonner/` | ordre | S | — | N | Fiche | T10 |
| GET | `/api/django/taches/etiquettes/` | liste paginée | S | — | — | Fiche → Plus, filtres | s2 |
| POST | `/api/django/taches/etiquettes/` | `{"nom","couleur"}` | S | — | — | idem | s2 |
| PATCH | `/api/django/taches/etiquettes/{id}/` | renommer, couleur | S | — | — | idem | s2 |
| DELETE | `/api/django/taches/etiquettes/{id}/` | supprimer | S | — | N | idem | s2 |
| GET | `/api/django/taches/vues/` | vues (≤ 30, non paginé) | S | — | — | Recherche | s2 |
| POST | `/api/django/taches/vues/` | `{"nom","filtres","rang"}` | S | — | — | Recherche → Enregistrer | s2 |
| PATCH | `/api/django/taches/vues/{id}/` | `{"nom"?,"filtres"?,"rang"?}` | S | — | — | Recherche | s2 |
| DELETE | `/api/django/taches/vues/{id}/` | supprimer | S | — | N | Recherche | s2 |
| GET | `/api/django/taches/supprimees/` | Supprimées récemment (un projet = une ligne) | S | — | — | Supprimées récemment | s2, A16-N7 |
| GET | `/api/django/taches/gestes/` | Derniers gestes (7 j) | S | — | — | Supprimées récemment | s2 |
| POST | `/api/django/taches/gestes/{id}/annuler/` | Annuler (200 partiel ; porte `progression`, forme de TACHE_ECRITE, pour recaler la ligne du jour) | S | — | N | toast, cartes | A7, C2 |
| GET | `/api/django/taches/suggestions/` | ≤ 20 proposées (< 7 j) | S | — | — | À trier « Suggéré par l'ERP » | s6a, A4 |
| POST | `/api/django/taches/suggestions/{id}/accepter/` | Ajouter | S | — | N | À trier | s6a |
| POST | `/api/django/taches/suggestions/{id}/refuser/` | Pas utile | S | — | N | À trier | s6a |

### 3.3 Projets, revue, modèles

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/projets/?statut=actif\|en_pause\|archive` | liste paginée + `constat` | S | — | — | Projets, Archive, sélecteur | s4 |
| POST | `/api/django/taches/projets/` | créer | S | — | K | Nouveau projet, Copilote | s4, C44 |
| GET | `/api/django/taches/projets/{id}/` | PROJET | S | — | — | Un projet (en-tête) | s4 |
| PATCH | `/api/django/taches/projets/{id}/` | éditer | S | oui | — | Un projet, puce de priorité | s4, min-10 |
| DELETE | `/api/django/taches/projets/{id}/` | supprimer avec ses tâches (un geste) | S | — | N | Un projet ⋯ | s4, A16-N7 |
| POST | `/api/django/taches/projets/{id}/reordonner/` | ordre manuel, « Mettre en haut » | S | — | N | Projets | T10, s4 |
| POST | `/api/django/taches/projets/trier-par-priorite/` | ordre par priorité, une fois | S | — | N | Projets ⋯ | s4, A14-M3 |
| GET | `/api/django/taches/projets/{id}/vue/?vue=liste\|tableau\|chronologie` | sections, ITEM, avancement, santé, jalon, burn-up | S | — | — | Un projet, carte `projet` | s4 |
| POST | `/api/django/taches/projets/{id}/planification/apercu/` | lire une liste, rien écrit | S | — | N | Planifier le projet, carte `plan_projet` | s4 |
| POST | `/api/django/taches/projets/{id}/planification/` | tout créer, priorité comprise | S | oui | K | Planifier le projet | s4, A14-M3 |
| POST | `/api/django/taches/projets/{id}/decaler/` | `{"delta_jours","apercu"}` | S | — | K | Décaler les dates | s4 |
| POST | `/api/django/taches/projets/{id}/terminer/` | clôture | S | — | N | Un projet ⋯, Revue | s4 |
| POST | `/api/django/taches/projets/{id}/rouvrir/` | réouverture | S | — | N | Archive | s4 |
| POST | `/api/django/taches/projets/{id}/restaurer/` | projet + tâches supprimées avec lui | S | — | N | Supprimées récemment | verif-2-3 m9, A16-N7 |
| POST | `/api/django/taches/projets/{id}/dupliquer/` | `{"nom","date_debut","apercu"}` | S | — | K | Un projet ⋯ | s4 §G |
| POST | `/api/django/taches/projets/{id}/enregistrer-modele/` | `{"nom","inclure_notes"}` | S | — | K | Un projet ⋯ | s4 §G |
| POST | `/api/django/taches/sections/` | `{"projet_id","nom","date_debut"?,"date_fin"?}` | S | — | — | Un projet | T10 |
| PATCH | `/api/django/taches/sections/{id}/` | renommer, dates | S | — | — | Un projet | T10 |
| DELETE | `/api/django/taches/sections/{id}/` | supprimer (tâches « Sans étape ») | S | — | N | Un projet | T10 |
| POST | `/api/django/taches/sections/{id}/reordonner/` | ordre | S | — | N | Un projet | T10 |
| GET | `/api/django/taches/modeles/` | liste paginée | S | — | — | Modèles | s4 |
| GET | `/api/django/taches/modeles/{id}/` | `{"id","nom","contenu","created_at"}` | S | — | — | Modèles | s4 |
| PATCH | `/api/django/taches/modeles/{id}/` | `{"nom"}` | S | — | — | Modèles | s4 |
| DELETE | `/api/django/taches/modeles/{id}/` | supprimer | S | — | N | Modèles | s4 |
| POST | `/api/django/taches/modeles/{id}/instancier/` | `{"nom","date_lancement","apercu"}` | S | — | K | Nouveau projet → Depuis un modèle | s4 |
| GET | `/api/django/taches/revue/projets/?semaine=` | bilan de semaine (ou Semaine courte) + cartes | S | — | — | Revue, carte `revue_semaine` | s4, C19, A16-N9 |
| PUT | `/api/django/taches/revue/projets/{projet_id}/` | décision d'une carte | S | — | N | Revue | s4 |

### 3.4 Rythme, réglages, iPhone, données

| Méthode | Chemin | But | Auth | 409 | Idem. | Consommateur | Origine |
|---|---|---|---|---|---|---|---|
| GET | `/api/django/taches/rythme/` | RYTHME | S | — | — | Mon rythme, carte `rythme` | s5a, C13 |
| POST | `/api/django/taches/rythme/` | `{"mode","objectif"?,"sens"?}` (seul chemin du mode) | S | — | N | Mon rythme, Copilote | s5a, A2.1, MAJ-6 |
| POST | `/api/django/taches/rythme/propositions/{id}/repondre/` | `{"reponse"}` toute carte | S | — | N | carte du moment, Mon rythme, bilan | s5a, C13 |
| POST | `/api/django/taches/preferences/` | poser `{"cle","valeur"}` → RYTHME | S | — | N | Mes jours, Notifications, Copilote | s5b, C4 |
| DELETE | `/api/django/taches/preferences/{cle}/` | retirer → RYTHME | S | — | N | carte `rythme` « Retirer » | T1 |
| GET | `/api/django/taches/reglages/` | réglages | S | — | — | Réglages, Mon iPhone | T1, A14-M5 |
| PATCH | `/api/django/taches/reglages/` | liste blanche | S | — | — | Réglages, question du 1er rappel | MAJ-6, A17-T4 |
| GET | `/api/django/taches/reglages-societe/` | coupe-circuit (administrateur, `IsAdminRole`) | S + admin | — | — | Réglages → Avancé | A18-M8 |
| PATCH | `/api/django/taches/reglages-societe/` | `{"balayage_actif":false}` | S + admin | — | — | Réglages → Avancé | A18-M8 |
| GET | `/api/django/taches/jetons/` | lister (sans empreinte) | S | — | — | Mon iPhone | s6b §1 |
| POST | `/api/django/taches/jetons/` | créer `{usage}` (clair rendu UNE fois ; révoque l'ancien) | S | — | — | Mon iPhone | s6b |
| POST | `/api/django/taches/jetons/{id}/revoquer/` | révoquer | S | — | N | Mon iPhone | s6b |
| POST | `/api/django/taches/mon-iphone/test-notification/` | push `TACHES_RAPPEL`, hors plafond ; part tout de suite (jamais différé), aucune borne de débit ; coupe-circuit allumé : 409 `envoi_coupe`, rien n'est envoyé | S | — | — | Mon iPhone étape 1 | s6b §9, C43 |
| GET | `/api/django/taches/tuile/` | tuile Scriptable | J:tuile | — | — | Scriptable | s6b §6 |
| GET | `/api/django/taches/flux/{jeton}.ics` | calendrier abonné (`text/calendar`, `no-store`) | J:flux (URL) | — | — | Calendrier d'Apple | s6b §4 |
| GET | `/api/django/taches/coach/entete/` | 2 lignes ≤ 300 car. | S | — | — | relais du Copilote | s5b §5 |
| GET | `/api/django/taches/mes-donnees/` | export JSON des 20 modèles | S | — | — | Réglages → Mes données | s6a, socle §8 |
| POST | `/api/django/taches/tout-effacer/` | `{"confirmation":"EFFACER"}` suppression DURE | S | — | N | Réglages → Mes données | s6a |
| GET | `/api/django/taches/agendas-externes/` | `{"results":[…]}` (≤ 3) | S | — | — | Réglages → Mon iPhone étape 2, Agenda | A18-M4 |
| POST | `/api/django/taches/agendas-externes/` | ajouter une adresse ICS (lue aussitôt) | S | — | K | idem | A18-M4 |
| PATCH | `/api/django/taches/agendas-externes/{id}/` | libellé, actif, rang | S | — | — | idem | A18-M4 |
| DELETE | `/api/django/taches/agendas-externes/{id}/` | retirer | S | — | N | idem | A18-M4 |
| POST | `/api/django/taches/agendas-externes/{id}/rafraichir/` | relire maintenant (ignore le cache) | S | — | N | idem | A18-M4 |

Comptés par script (lignes de tableau de ce §3, méthodes séparées par « · ») : **106** couples méthode × chemin
propres à `taches`, tous distincts, + 2 routes étrangères consommées.

## 4. Corps de requête et erreurs (réponses : annexe A)

**`saisie-rapide/`** — aperçu : `{"textes":["Courses\nlait\npain","Appeler Karim demain #SiteWeb"],"client_id":"c1f4b2a0-5d1e-4b9a-9a51-2b7f0c3e8d11","projet_id":null,"lien":null,"parent_id":null,"proprietaire_attendu":7,"ignorer":[],"apercu":true}`
(ou `"texte":"…"` pour un seul collage ; ou `"ids":[41,42]` pour proposer un projet à des tâches existantes, appliqué
par `lot/` `deplacer` `valeurs.par_tache`) ; création : `{"lignes":[{"index":0,"collage":0,"client_id":"c1f4b2a0-5d1e-4b9a-9a51-2b7f0c3e8d11:0","titre":"Appeler Karim","projet_id":null,"nouveau_projet":{"nom":"SiteWeb","priorite":2},"section_id":null,"nouvelle_section":null,"priorite":0,"jour_prevu":"2026-11-18","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"etiquettes":[2,{"nom":"magasin"}],"recurrence":null,"rappel":{"jour":"2026-11-18","heure":"09:00"},"notes":"","checklist":["Numéro"],"lien":{"cible":"crm.lead","id":1637}}],"proprietaire_attendu":7,"apercu":false}` ; LIGNE = un élément de `lignes`, forme ci-contre.
(`projet_id` et `nouveau_projet` exclusifs ; `section_id` et `nouvelle_section` exclusifs ; `rappel` absolu ou
`{"ancre":"echeance","decalage_jours":-1,"heure":"18:00"}`). Plafonds 200 lignes, 20 000 car. (2 000 via le Copilote).
Venant de l'assistant (en-tête `X-Taqinor-Assistant` ou `Authorization: Bearer`), seul l'aperçu (`apercu:true`,
`ids`, `texte`) est servi : des `lignes` à créer répondent **403** `{"lignes":["L'assistant ne crée pas ces lignes : il
les propose, tu les valides à l'écran."],"detail":"…"}` (refus du canal, échec fermé ; rien n'est écrit) — la personne
valide la carte à l'écran (cookie + `X-Taqinor-Carte-Assistant: 1`, source `assistant`). Chaque « Nouveau projet » de l'aperçu porte sa priorité,
Moyenne (2) par défaut. Erreurs : `{"lignes":{"3":{"titre":["Le titre est vide une fois la date et le projet retirés."]}}}` ·
`{"texte":["Liste trop longue : 200 lignes au plus (ici 340). Colle-la en deux fois."]}` · `{"projet_id":["Projet inexistant."]}` ·
`{"lien":["Élément introuvable ou hors de ta portée."]}` · `{"lien":["Ce type d'élément ne peut pas être lié à une tâche."]}` ·
409 `autre_compte`. Réponses : `saisie_apercu.json`, `saisie_rapide.json`.

**`capture/`** (Bearer `tqc_…`) — `{"titre":"appeler le fournisseur demain 10 h","notes":"","client_id":"7d2e0a11"}`
(titre ≤ 280, notes ≤ 2 000, client_id ≤ 64 ; trois TEXTES JSON : un nombre est refusé, 400) → 201 `capture.json` ; `dans` ∈ `journee` (un jour posé), `projet`
(projet sans jour), `a_trier` (rien, ou une échéance seule) ; nom de projet dit par `nom_pour(projet,'siri')`
(« un projet » si confidentiel, inv. 38) ; rejeu 200 `"deja":true` ; `?reponse=texte` → `text/plain` (un corps illisible s'y lit « Dis-moi quoi noter. »). 400
`{"titre":["Dis-moi quoi noter."]}`.

**`taches/`** POST — une LIGNE (+ `parent_id`) → 201 `tache_ecrite.json`. **PATCH `taches/{id}/`** —
`{"titre":"Devis Settat — relance","notes":"","priorite":3,"echeance":"2026-11-20","echeance_heure":null,"estimation_minutes":60,"duree_reelle_minutes":null,"projet_id":3,"section_id":null,"jalon":false,"bloquee_par_id":null,"confidentiel":false,"etiquettes":[2],"recurrence":null,"lien":null,"lock_version":4}`
(tout champ facultatif sauf `lock_version`) → `tache_ecrite.json` ; 400 `{"bloquee_par_id":["Boucle : « B » attend déjà « T »."]}`,
`{"jour_prevu":["Passe par « Quand »."]}`.
**`planifier/`** `{"jour_prevu":"2026-11-19","moment":"","heure_debut":"10:00","quelque_jour":false,"lock_version":4,"proprietaire_attendu":7}`
→ `tache_ecrite.json` ; 400 `{"heure_debut":["Une heure demande un jour prévu."]}`. **`terminer/`** (corps facultatif
`{"proprietaire_attendu":7}`) → `tache_ecrite.json` (`tache_recurrente_ecrite.json` si récurrente).
**`trancher/`** `{"choix":"garder"}` ou `{"choix":"jour","jour":"2026-11-19"}`. **`attendre/`**
`{"en_attente_de":"Lydec"}` (400 `{"en_attente_de":["Dis de qui ou de quoi tu attends."]}`) ; l'attente d'une tâche passe
par `PATCH` `{"bloquee_par_id":43}` (statut `a_faire` gardé). **`rappels/`** `{"jour":"2026-11-17","heure":"15:00"}` ou
`{"ancre":"echeance","decalage_jours":-1,"heure":"18:00"}` → `tache_ecrite.json` avec `rappel`. **`rappels/{id}/repeter/`**
`{"dans_minutes":60}` ou `{"jour":"2026-11-18","heure":"09:00"}` → `rappel_repeter.json`. **`changement/apercu/`**
`{"geste":"renommer","titre":"Devis Settat — relance"}` → `tache_changement.json`. **`lot/`**
`{"ids":[41,42],"action":"planifier","valeurs":{"jour_prevu":"2026-11-19"}}` (`deplacer` `{"projet_id":3,"section_id":null}`
ou `{"par_tache":{"41":{"projet_id":3}}}` ; `planifier` `{"quelque_jour":true}` ; `prioriser` `{"priorite":3}` ;
`etiqueter` `{"ajouter":[2],"retirer":[]}`) → `lot.json`. **`lier-activite/`** `{"activite_id":101,"titre":"Préparer l'appel Benali","jour_prevu":null}`
→ 201 `lier_activite.json` ; 409 `deja_lie`. **`convertir-activite/`** `{"activite_ids":[41,44]}` ou `{"toutes":true}`
→ `convertir_activite.json` (raisons `introuvable`, `assignee_a_un_collegue`, `deja_convertie`, `close` ; source close
par `records.services.cloturer_a_faire_personnel`). **`suggestions/{id}/accepter/`** `{"titre":"Préparer le chantier","jour_prevu":"2026-11-18"}`
(champs facultatifs) → 201 `tache_ecrite.json`.
**`vu/`** `{"ecran":"aujourdhui"}` → `vu.json` (ou `{"carte_du_moment":null}`) : pose `PlanJour.app_ouverte_le`,
`ouvert_le` des push du jour, crée la carte `retour` ; rien si le compte n'a jamais créé de tâche.
**`journee/proposition/`** `?jour=2026-11-17&exclure=41&inclure=30&tout=1` (un id étranger est ignoré) →
`journee_proposition.json`. **`journee/planifier/`** `{"jour":"2026-11-17","mode":"express","lignes":[{"type":"tache","id":30},{"type":"activite","id":101}],"essentielles":[20],"triage":[]}`
(`triage` facultatif, jamais exigé, A17-T2) → `journee_ecrite.json` ; 400 `{"essentielles":["3 au plus."]}`.
**`journee/essentiel/`** `{"tache_id":20,"essentielle":true}` → `tache_ecrite.json`. **`journee/alleger/`**
`{"jour":"2026-11-17","garder":[20,42]}` → `journee_ecrite.json` (`renvoyees` rempli ; `allege_le` posé, sans report).
**`journee/priorites/`** `?jour=2026-11-17` → `priorites.json` : TOUTES les tâches ouvertes du préfiltre, classées
comme Proposé (inv. 34 étendu au pool entier), chacune avec `raison` ; gestes de la carte : Essentiel →
`journee/essentiel/`, Aujourd'hui → `planifier/` (J), « Reporter à {jour} » → `planifier/` (`plus_tard`), « Garder
ces N » → `journee/planifier/` avec les `garder_n` premières. **`journee/point/`** → `point.json`.
**`journee/cloture/`** `?jour=2026-11-17` (J−1 admis jusqu'à 12 h) → `journee_cloture.json` (UN constat au plus ;
`a_trancher` = reportées 3 fois, marquées, jamais refusées). **`journee/cloturer/`**
`{"jour":"2026-11-17","choix":[{"id":52,"choix":"jour","jour":"2026-11-23"}],"le_reste":true,"reflexion":""}` (`choix` ∈
`prochain_jour_ouvre`, `jour`, `un_jour`, `abandonner` ; `le_reste` = « Tout reporter ») → `journee_cloturee.json`.
**`agenda/`** `?du=2026-11-16&au=2026-11-22&vue=semaine&projet=3` → `agenda.json` ; 400 `{"au":["42 jours au plus."]}` ;
`mes_projets` en `vue=jour` et `vue=semaine` (le même volet « À placer », maquettes `agenda-jour` et `agenda-semaine` ; vide en `mois` et `a-venir`) ; `toute_la_journee` = les `obligations` du jour SANS la famille `touches` (la ligne « Suivi des relances » est une ligne de Prévu, textes.md §2 ; la bande ne porte que ce qui a une date sans heure) ; poser une tâche sur un jour = `taches/{id}/planifier/` ; `externes` =
RENDEZ_VOUS du jour ; chaque jour porte aussi `rendez_vous_minutes` (R2-100 : la durée UNIE de ses rendez-vous horodatés,
bornée aux heures de travail de la société, journée entière = 0 — invariant 35, `minutes_de_rendez_vous` ; le front la
retranche de `capacite.minutes` pour « {h} pour {cap} ») et `faites_nb` (R2-102, règle C-12 : `compte_du_jour` des
tâches finies CE jour local, prévues ce jour-là ou non, + activités ERP closes par lui ; 0 pour un jour à venir) ; une
tâche ouverte d'un projet en pause prévue AUJOURD'HUI reste dans le jour (R2-031b, choix C-5). **`recherche/`** `?q=devis&limite=25` → `recherche.json` ; 400 `{"q":["Requis."]}`.

**`projets/`** POST `{"nom":"Chantier X","priorite":2,"couleur":"vert","icone":"","objectif":"","domaine":""}` ; doublon
→ 400 `{"nom":["Un projet « Chantier X » existe déjà."]}`. **PATCH** `{"nom":"Ventes","objectif":"","icone":"","couleur":"vert","priorite":3,"statut":"en_pause","date_debut":null,"echeance":"2026-12-15","domaine":"","confidentiel":false,"affichage":{"vue":"tableau","tri":"manuel","groupe":"section","montrer_faites":false},"risque":"","lock_version":4}`
→ `projet.json` ; `statut=termine` → 400 `{"statut":["Passe par « Terminer »."]}`. **DELETE**, **`terminer/`**
`{"issue":"atteint","bilan":"","taches_ouvertes":"boite","projet_cible_id":null}` (400 `{"issue":["Atteint ou abandonné ?"]}`),
**`restaurer/`** (409 `nom_pris`) → `projet_ecrit.json`. **`planification/apercu/`**
`{"texte":"Études :\nVisite\n- photos\n◆ Mise en service","mode":"plan"}` (`mode` facultatif : `plan` par défaut ; `etapes` =
le champ « Étapes » de l'écran, où une ligne non indentée EST une étape — `regles.md` §1.10 ; 400 « Valeur inconnue. » sinon)
→ `planification_apercu.json` (même forme dans les deux modes ; `projet` {id, lock_version} : où
écrire et le verrou à renvoyer — la carte `plan_projet` n'a que cette réponse). **`planification/`**
`{"priorite":3,"objectif":"Stand monté","echeance":"2026-12-29","risque":"","sections":[{"nom":"Études","taches":[{"titre":"Visite","jalon":false,"sous_taches":["photos"]}]}],"actions":[{"titre":"Réserver le stand","quand":"aujourdhui"}],"lock_version":4}`
→ `planification.json`. **`decaler/`** `{"delta_jours":7,"apercu":true}` (sans `apercu` : aperçu) → `decalage.json`
(chaque ligne porte son `titre`, par `nom_pour`) ; 400
`{"delta_jours":["2 tâches passeraient avant aujourd'hui."],"changements":[…],"avant_aujourdhui":[41,42]}` (l'aperçu titré
qu'il aurait appliqué ; rien n'est écrit). **`dupliquer/`** `{"nom":"Salon 2027","date_debut":"2027-03-01","apercu":true}`
→ `modele_instancier.json`. **`enregistrer-modele/`** `{"nom":"Salon","inclure_notes":false}` → `modele.json`.
**`modeles/{id}/instancier/`** `{"nom":"Salon","date_lancement":"2026-11-23","apercu":true}` → `modele_instancier.json`
(`apercu:false` → 201 `projet_ecrit.json`). Une date hors plage (`dupliquer/`, `modeles/{id}/instancier/`,
`suggestions/{id}/accepter/`) répond 400 « Date attendue (AAAA-MM-JJ). » sous son champ, jamais 500. **`vues/`** (POST, PATCH) : un nom ou une valeur de filtre portant un caractère nul répond 400
« Valeur inconnue. » ; `rang` est borné à un entier 32 bits. **`sections/`** POST `{"projet_id":3,"nom":"Études","date_debut":null,"date_fin":null}`.
**`checklist/`** POST `{"tache_id":20,"libelle":"Prix"}`, PATCH `{"libelle":"Prix TTC","fait":true}`.
**`revue/projets/{projet_id}/`** PUT `{"semaine":"2026-11-16","intention":"Signer Settat","prochaine_action_id":20,"decision":"garder","focus":true,"issue":null}`
(`terminer` exige `issue`) → `revue_decision.json` ; 400 `{"focus":["Déjà « A » cette semaine."]}`.
**`rythme/`** POST `{"mode":"pousser","objectif":7}` ou `{"mode":"pousser","sens":"plus"}` → `rythme.json` ; 400
`{"mode":["Valeur inconnue."]}`, `{"objectif":["Entre 1 et 12."]}`. **`propositions/{id}/repondre/`** `{"reponse":"oui"}`
→ `proposition_repondue.json` ; 409 `proposition_expiree` ; 400 `{"reponse":["Réponse inconnue."]}`. **`preferences/`**
`{"cle":"heure_limite","valeur":"19:00"}` → `rythme.json` ; 400 `{"valeur":["Heure attendue (HH:MM)."]}`,
`{"cle":["Clé inconnue."]}`.
**`reglages/`** PATCH, liste blanche seule : `titres_notifications` (pose `titres_notifications_demande_le`),
`titres_calendrier`, `titres_tuile`, `messages_sans_delai`, `rappel_avant_bloc_min`, `projet_arret_jours`,
`familles_suggestions`, `suggestions_societe` (non-admin → 403 `{"suggestions_societe":["Réservé à un
administrateur."]}`), `erp_dans_journee`, `comprendre_mon_rythme`, `pauses_sollicitations` ; tout autre champ → 400
`{"<champ>":["Non modifiable ici."]}`. `fenetre_societe` = `notifications.selectors.fenetre_notifications(company, now)`
(`notifications/selectors.py:91`) ; `est_admin` = `IsAdminRole` ; `raccourci_siri_url` = `TACHES_RACCOURCI_SIRI_URL`
(vide → `null`). **`reglages-societe/`** (`IsAdminRole`) PATCH `{"balayage_actif":false}` → `reglages_societe.json`.
**`jetons/`** POST `{"usage":"flux","libelle":""}` → 201 `jeton.json` (clair rendu une seule fois).
**`agendas-externes/`** POST `{"url":"https://outlook.office365.com/owa/calendar/abc/reachcalendar.ics","libelle":"Microsoft 365"}`
(une adresse `webcal://` est réécrite en `https://`) → 201 `agenda_externe.json` (lecture immédiate ; corps ≤ 2 Mo, délai 10 s, cache 15 minutes) ; PATCH `{"libelle":"Bureau","actif":false,"rang":2048}` ; POST
`…/{id}/rafraichir/` (ignore le cache). 400 `{"url":["Ce n'est pas une adresse : colle le lien de ton agenda."]}` (pas une adresse), `{"url":["L'adresse doit commencer par https."]}` (http, ftp…), `{"url":["Adresse injoignable : vérifie le lien."]}` (hôte introuvable ou interne), `{"url":["3 agendas au plus."]}`,
`{"url":["Cet agenda est déjà ajouté."]}` ; l'hôte est validé par `apps/publicapi/validators.py` à l'ajout puis
revérifié à chaque lecture (`donnees.md` inv. 33). **`tout-effacer/`** `{"confirmation":"EFFACER"}` (400
`{"confirmation":["Tape EFFACER pour confirmer."]}`) → `tout_effacer.json` ; efface aussi les notifications
`taches_*` du compte dans la société (cloche de l'ERP : une ligne peut porter un titre), clé `notification`.

## 5. Hors ligne et brouillon (A16-N11)

`features/taches/captureQueue.js` = `Outbox` du module (classe `Outbox`, `lib/offlineOutbox.js:304`) sur
`createModuleOutboxStore('taches')` (`lib/offlineStore.js:137`) ; `OFFLINE_MODULES` et `offlinesync` intacts. Trois ops :
ajouter (`saisie-rapide/`, `client_id`), cocher (`terminer/`), reporter (`planifier/`, `lock_version` du cache). Chaque
op porte `(company_id, user_id)` ; `proprietaire_attendu` envoyé ; 409 `autre_compte` → op jetée ; 409
`conflit_version` → bandeau de conflit. Cache de lecture `taches:aujourdhui:<user_id>:<jour>`. Brouillon de saisie :
`useDraftAutosave` sous la clé `taches:brouillon:<user_id>`, relu par la carte « Reprendre » et la feuille de saisie.
Tout (file, cache, brouillon) vidé sur `taqinor:auth-logout` (`providers/session-bridge.js:74`).

## 6. Contrats d'abord (`apps/taches/contract_samples/*.json`)

Un fichier par échantillon de l'annexe A (même nom, contenu recopié mot pour mot ; `exemple` est toujours un OBJET).
L'export dans `frontend/src/test/fixtures/contractSamples.js` suit le plan (`docs/plans/PLAN_TACHES.md`). Une clé
facultative `nuls` (liste de chemins) dit ce que l'exemple ne montre pas nul mais que le serveur peut servir nul
(`aujourdhui.json` : `plan.planifie_le` ; `journee_proposition.json` : `suite_par_projet`, `rythme` ;
`projets_liste.json` : `constat`) ; elle n'est pas une clé de la réponse.

## 7. Routes du FRONT (une seule table — spec-7 r3 §2)

| Route | Écran | Paramètres |
|---|---|---|
| `/taches` | mène à `/taches/aujourdhui` | — |
| `/taches/aujourdhui` | Aujourd'hui (accueil : `MOBILE_HOME_ALLOWED_ROUTES` + `setLandingModule('taches')`) | `tache=<id>`, `ouvrir=bilan` (ouvre le bilan du soir ; `ouvrir=plan` n'existe pas : le plan est la carte du moment), `tout=1` |
| `/taches/a-trier` | À trier (pastille d'onglet = `a_trier.boite_reception`) | `tache` |
| `/taches/projets` · `/taches/projets/:id` | Projets · Un projet | `vue`, `planifier=1`, `tache` |
| `/taches/projets/archive` · `/taches/projets/modeles` | Archive · Modèles | — |
| `/taches/agenda` | Agenda | `vue=jour\|semaine\|mois\|a-venir`, `jour`, `projet`, `placer=1` (volet À placer ouvert, fin de Revue) |
| `/taches/revue` · `/taches/rythme` · `/taches/recherche` · `/taches/supprimees` | Revue · Mon rythme · Recherche (`q`, `periode=faites_semaine` : « Faites cette semaine », R2-124) · Supprimées | — |
| `/taches/reglages[/:rubrique]` | Réglages | `notifications`, `iphone`, `vie-privee`, `suggestions`, `donnees`, `avance` |

Notifications (A15, spec-7 r3 §2) : `plan_matin`, `relance` → `/taches/aujourdhui` sans paramètre · `bilan_soir` →
`/taches/aujourdhui?ouvrir=bilan` · `revue_semaine` → `/taches/revue` · rappel → `/taches/aujourdhui?tache=<id>`
(« Encore 10 min · 1 h · Demain 9 h ») · test → `/taches/reglages/iphone`. Touches : `g j` = ALLER à
`/taches/aujourdhui` (`shortcut:'j'` du module) ; `c t` = événement `taqinor:taches:saisir` (feuille de saisie).
Événements entre écrans (`features/taches/lib/fiche.js`) : `taqinor:taches:creees` (émis par la feuille de saisie) et,
R2-040, `taqinor:taches:ecrite` (`detail = { tache }`, la tâche rendue par le serveur ou `null`) émis par la fiche
après chaque écriture réussie (champs, check-list, rappel, sous-tâche, suppression, Annuler) et à sa fermeture ;
`useApresCreation` écoute les deux : Aujourd'hui, l'Agenda, Projet et À trier se relisent.
Copilote : les quatre demandes prêtes appellent DIRECTEMENT les routes du §8 et rendent leur carte sans modèle de
langage (A18-M3) ; sans clé d'IA, elles restent. Navigation et `appSku` : selon l'activation (`donnees.md` inv. 28).

## 8. Assistant : demandes prêtes et actions (`agent_actions.py` ; `taches_voir`, `RISK_INTERNAL`, lot `copilote`)

Demandes prêtes (A18-M3, déterministes, sans modèle) : « Planifie ma journée » → GET `journee/proposition/` (carte
`plan_propose`, « Adopter » = « Garder ces N ») · « Aide-moi à prioriser » → GET `journee/priorites/` (carte
`priorites`) · « Range ma liste » → POST `saisie-rapide/` `{"ids":[À trier],"apercu":true}` (carte `capture_apercu`,
rangement par mots, sans modèle) · « Où j'en suis ? » → GET `journee/point/` (carte `point`).

Écritures de l'assistant — garde A5 FERMÉE PAR DÉFAUT (`regles.md` §12) : après toute lecture dans la conversation
(ou un texte collé dans la question), une écriture `taches.*` n'est pas exécutée par le relais : elle arrive en carte à
valider (`ecriture_a_valider.json`, avec `projet {id, nom}` quand elle vise un projet) et c'est le doigt qui l'écrit,
par l'écran (`X-Taqinor-Carte-Assistant: 1` sur une création, §0).

| Clé | Méthode + route | Carte | Note |
|---|---|---|---|
| `taches.journee.lire` | GET `/api/django/taches/aujourdhui/` | `ma_journee` | « Tout au prochain jour travaillé » → `taches/lot/` |
| `taches.journee.prioriser` | GET `/api/django/taches/journee/priorites/` | `priorites` | « Aide-moi à prioriser » (A18-M3 b) |
| `taches.journee.point` | GET `/api/django/taches/journee/point/` | `point` | « Où j'en suis ? » |
| `taches.plan.proposer` | GET `/api/django/taches/journee/proposition/` | `plan_propose` | « Adopter » = « Garder ces N » → `journee/planifier/` express (A17-T2) |
| `taches.tache.chercher` | GET `/api/django/taches/recherche/` | `liste_taches` | `filtrer_q(assistant=True)` |
| `taches.profil.lire` | GET `/api/django/taches/rythme/` | `rythme` | `note_libre` sous enveloppe non fiable |
| `taches.projet.lire` | GET `/api/django/taches/projets/{id}/vue/` | `projet` | « Ouvrir » seulement |
| `taches.revue.semaine` | GET `/api/django/taches/revue/projets/` | `revue_semaine` | |
| `taches.tache.creer` ✎ | POST `/api/django/taches/taches/` | `tache` | `lien` du contexte ; `source='assistant'` |
| `taches.tache.terminer` ✎ | POST `/api/django/taches/taches/{id}/terminer/` | `tache` | |
| `taches.tache.modifier` ✎ | PATCH `/api/django/taches/taches/{id}/` | `tache` | priorité, échéance, projet ; `lock_version` requis ; annulable (A18-M3 c) |
| `taches.tache.planifier` ✎ | POST `/api/django/taches/taches/{id}/planifier/` | `tache` | `lock_version` requis |
| `taches.rappel.poser` ✎ | POST `/api/django/taches/taches/{id}/rappels/` | `tache` | hors fenêtre → carte-écho |
| `taches.projet.creer` ✎ | POST `/api/django/taches/projets/` | `tache` | `priorite` admise |
| `taches.rythme.regler` ✎ | POST `/api/django/taches/rythme/` | `rythme` | `mode`, `objectif` (le nombre qu'IL a dit), `sens` |
| `taches.preference.noter` ✎ | POST `/api/django/taches/preferences/` | `rythme` | clés `Preference` seulement |
| `taches.liste.ranger` ⟲ | POST `/api/django/taches/saisie-rapide/` `apercu:true` | `capture_apercu` | |
| `taches.projet.planifier_apercu` ⟲ | POST `/api/django/taches/projets/{id}/planification/apercu/` | `plan_projet` | 403 si confidentiel |
| `taches.tache.proposer_changement` ⟲ | POST `/api/django/taches/taches/{id}/changement/apercu/` | `tache` | Renommer → PATCH ; Abandonner → `trancher/` ; Supprimer → DELETE ; Annuler → `gestes/{id}/annuler/` |

✎ écrit, ⟲ écho. ≤ 3 écritures par tour ; contenu non fiable dans le tour → toute ✎ devient une carte-écho portant
le corps (A5). `taches.tache.modifier` : sur demande explicite ; annulable par `gestes/{id}/annuler/`. Carte
`rythme` : « Retirer » → `DELETE preferences/{cle}/` ; « Monter à N » / « Descendre à N » / « Garder N » / « Pas maintenant » → `rythme/propositions/{id}/repondre/` (jamais « Passer à »).
Jeu réduit sous Groq (écran `/taches`), calculé en ÉTENDANT `catalogue_du_tour` (`relais_copilote.py:110`, pas de
jumeau) : journee.lire, plan.proposer, journee.prioriser, tache.creer, tache.terminer, liste.ranger, rythme.regler.
Retirées : `taches.suggestions.lister`, `taches.capturer`, `taches.tache.capturer` (C12). Les réglages d'IA de
production (fournisseur, clé) sont un geste de Reda (A18-M3 d).

## 9. Tâches planifiées (`sweeps.py`, file `scheduled`) et événements

| Nom | Cadence | Fait | Idempotence |
|---|---|---|---|
| `taches.balayer` | chaque minute, `_expire_dans(60)` | `active_company_ids()` à module actif ET `ReglagesSociete.balayage_actif` (relu à chaque passage), comptes actifs ayant une `ReglagesRythme` : rappels dus → `TACHES_RAPPEL` groupés par minute (retard > 2 h → `manque`) ; sollicitations dues dans [heure, heure + 15 min) selon `regles.md` §7 — après SON PROPRE contrôle de fenêtre, `notify(…, respect_quiet_hours=False, badge=compter_journee())` (sinon `notify()` DIFFÈRE, `notifications/services.py:631-633`) | rappel pris par `UPDATE … WHERE statut='en_attente'` puis `notify` dans la même transaction ; sollicitation : `get_or_create` du marqueur `IncitationCoach` + `notify` dans la même transaction. AUCUN appel réseau : les agendas externes sont lus du cache seulement (cache froid : sans rendez-vous, rien d'écrit). Un compte sans `taches_voir` ne reçoit rien (relu à chaque passage). Un compte en échec est journalisé (id du compte, classe de l'erreur, jamais le message) et n'arrête pas les suivants (bilan `comptes_en_echec`) |
| `taches.nocturne` | 03:00 `Africa/Casablanca`, `_expire_dans(3600)` | clôt `PlanJour` d'hier ; rythme, cartes, constats (si « comprendre mon rythme ») ; révélation `revue` ; expire les cartes ; `ignoree` sur les push non ouverts en 3 h ; pauses ; revérifie les liens des tâches ouvertes ; purges `donnees.md` §8 | recalcul déterministe ; contrainte unique des cartes ; purges par date |

Types (fin d'énum `notifications/types_evenements.py`, `module_map`/`module_gating` → `taches`, push + in-app seuls) :
`TACHES_PLAN_DU_JOUR`, `TACHES_BILAN_SOIR`, `TACHES_RELANCE`, `TACHES_RAPPEL`. Rappels immédiats : `taches_rappel`
ajouté au défaut de `NOTIFICATIONS_TOUJOURS_IMMEDIATES` (`settings/base.py`) ET vérification du `.env` de prod qui peut
le remplacer (geste de Reda). Coupe-circuit (A18-M8) : `PATCH reglages-societe/ {"balayage_actif":false}` par un
administrateur ; effet au passage suivant, sans redéploiement.

## 10. Plafonds de requêtes visés (A15 : cibles, remplacées par la mesure)

`aujourdhui/` ≤ 25 sans familles ERP, ≤ 31 avec (rendez-vous externes lus en cache, 0 requête de plus) · `badge/` ≤ 10 ·
`tuile/` ≤ 10 · `flux/` ≤ 8 · `journee/proposition/` ≤ 20 · `journee/priorites/` ≤ 20 · `journee/point/` ≤ 18 ·
`agenda/` ≤ 16 · `taches/` ≤ 12 · `projets/` ≤ 12 · `projets/{id}/vue/` ≤ 15 · `saisie-rapide/` aperçu ≤ 10 (constant en
lignes) · `rythme/` ≤ 10 · `recherche/` ≤ 8 · `suggestions/` ≤ 6.

Les plafonds RÉELS sont ceux de `tests/test_plafonds.py` et de `docs/query-budgets.yml` (la mesure). Le coût d'une
route qui passe par la journée dépend de l'HEURE : avant midi, la carte « bilan d'hier » lit en plus le plan de la
veille et ses restes (+ 2 requêtes ; `aujourdhui/` : 26 et 31 l'après-midi, 28 et 33 le matin). Tout test de plafond
fige donc l'horloge (`testkit.time.frozen`) et mesure une telle route aux deux moments.

## 11. Fichiers d'un autre propriétaire (une tâche chacun, A8)

`erp_agentique/urls.py` (fin de `_APP_URLS`), `settings/base.py` (`INSTALLED_APPS`, `TACHES_RACCOURCI_SIRI_URL` dès
l'échafaudage, deux beats, `NOTIFICATIONS_TOUJOURS_IMMEDIATES`), `celery.py` · `apps/roles/permissions_registre.py`
(règle de `donnees.md` inv. 28 : exclusion explicite, Administrateur seul, puis Directeur le 18/11/2026) · `frontend/src/lib/apps/appSkus.js` ·
`apps/notifications/*` (types, migration 0079, `badge` de `notify`) · `apps/records/selectors.py` + `services.py` ·
`apps/crm/selectors.py` (`cibles_du_sujet`, effacement 09-08) · `authentication/selectors.py`
(`MOBILE_HOME_ALLOWED_ROUTES`), `authentication/views.py` (traces) · `seed_registre_traitements.py` ·
`apps/agent/registry.py` + `assistant_reponse.json` (cartes `priorites`, `point` en plus) ·
`backend/fastapi_ia/app/services/action_tools.py` (en-tête par `headers=`), `relais_copilote.py` (`catalogue_du_tour`),
`sql_agent_service.py` (test `_ALLOWED_TABLES`) · `frontend/src/features/ia/cartes/*` ·
`frontend/src/pages/activities/MesActivitesPage.jsx` (« + À faire » ouvre `taqinor:taches:saisir`, critique m4) ·
`Layout.jsx`, `Header.jsx`, `BottomTabBar.jsx`, `sw.js`, `shortcuts.js`, `commandActions.js`, `entityRoutes.js`,
`focusedRecordShortcuts.jsx` · `docs/query-budgets.yml` · régénérés une fois par l'orchestrateur :
`docs/openapi-schema.yml`, `docs/rbac-endpoint-inventory.md` (écrit par son test s'il manque), `contractSamples.js`,
`docs/CODEMAP.md`.

## Décisions de l'intégrateur

- **R1** Chemins complets, un seul `include` en fin de `_APP_URLS`. **R2** `a-venir/` retiré (doublon d'`agenda/`).
- **R3** « Ailleurs » en route paresseuse. **R4** Une énum `Decision`, sous-ensembles par route.
- **R5** `journee/planifier` et `alleger` rendent l'AUJOURDHUI complet. **R6** `journee/planifier` : mode `express` seul.
- **R7** « Alléger » route dédiée. **R8** Carte de retour créée par `vu/`.
- **R9** Toutes les cartes à réponse partagent `rythme/propositions/{id}/repondre/`.
- **R10** `preferences/` POST + DELETE ; interrupteurs par `PATCH reglages/` (liste blanche).
- **R11** `capture/` analyse `titre` (A1). **R12** `textes[]` et `projets_communs[]` : un projet par collage.
- **R13** Budgets = cibles (A15). **R14** `TACHE.rappel` = `{jour, heure}`.
- **R15** `projets/{id}/restaurer/` et `projets/trier-par-priorite/`. **R16** `carte_du_moment` remplace `cartes_coach`.
- **R17** GET redondants retirés ; `GET supprimees/` (un projet = une ligne). **R18** Planifier ma semaine sans route
  nouvelle. **R19** `lier-activite/`. **R20** (rév. 2.1) Liens de notification : bilan `?ouvrir=bilan`.
- **R21** (rév. 3) Les quatre demandes prêtes : deux routes neuves seulement (`journee/priorites/`, `journee/point/`) ;
  « Planifie ma journée » et « Range ma liste » réutilisent `journee/proposition/` et `saisie-rapide/`.
- **R22** (rév. 3) « Assistant » reconnu aussi au `Bearer` JWT (échec fermé sans changer `internal_headers()`).
- **R23** (rév. 3) Listes à plafond enveloppées `{"results":[…]}` ; échantillons générés par un script, sans marqueur.
- **R24** (rév. 3) Agendas externes : 5 routes (liste, ajout, modification, suppression, rafraîchir) ; événements en
  cache seulement, forme RENDEZ_VOUS distincte d'ITEM.
- **R25** (rév. 3) Coupe-circuit en DONNÉE par société (`reglages-societe/`, administrateur), lu à chaque passage :
  seule façon d'agir « sans redéploiement ».

## Ce que les specs demandaient et que je n'ai PAS repris

- `saisie-rapide/apercu/`, `a-venir/`, `decaler/annuler/`, `annulations/{id}/appliquer/`, `accepter_palier`,
  `texte_dit`, `taches.suggestions.lister`, `taches.capturer`, `taches.tache.capturer` (C2, C11, C12, C13, A7, R2).
- Clé `agenda` de `aujourdhui/` → `obligations` (C5) ; `a_trancher`, `en_retard`, `echeances_proches` → `a_decider` puis
  tête de Proposé (A18-M2) ; `incitations`, `cartes_coach` → `carte_du_moment` ; `suggestions{nb}`, `a_convertir{nb}` →
  `a_trier` (C39).
- Réponse capture `{"ok"}`, erreur `{"champ","detail"}` (s6b) → forme commune (C3) ; rejeu `200 deja` sur
  `saisie-rapide/` → `201 deja_creees` (C9).
- Liens `?du=matin`, `/taches/bilan`, `?rituel=`, `/taches/boite`, `/taches/taches/<id>`, `?coach=1`, `?ouvrir=plan|alleger`.
- Accueil `'/taches'` (s6a) → `/taches/aujourdhui` ; raccourci de manifeste « Mes tâches » → « Tâches ».
- Beat toutes les 5 min (s6b), `taches.calculer_rythme` séparé (s5a) → minute + nocturne (C15) ; `TACHE_RAPPEL` (C14).
- Tuile `fait`, `essentiel.total` → `faites`, `essentiel.prevues` (C35).
- Pastille avec Proposé → gardées seules (A16-N5) ; visites « à leur heure » → Toute la journée (A16-N4).
- `mode:"complet"` et triage obligatoire (s3 §3.10) → express seul (A17-T2) ; choix `demain` au bilan ; 400 sur les
  reportées 3 fois.
- Liens facture, chantier, ticket et 9 autres cibles (A3) ; `{"activite_id"}` singulier (s6a) → `activite_ids` ;
  `corbeille` → `supprimer` ; messages en « vous » → tutoiement.
- Un seul agenda externe, route `agenda-externe/` au singulier, dernière vague (rév. 2) → 3 agendas, ESSENTIELS (A18-M4).
- `X-Taqinor-Assistant` posé par `internal_headers()` (rév. 2) → par `headers=` de `_django_call` (verif-plan B9).
- Réglage d'environnement `TACHES_SOLLICITATIONS` (critique M8) → donnée `ReglagesSociete.balayage_actif` (R25).
- Créer `catalogue_pour_tour` (s5b) → étendre `catalogue_du_tour` (verif-plan M22).

## À répercuter dans regles.md / textes.md

- `regles.md` §0 : TYPES d'entrée des modules purs (verif-plan M9) — `ItemPur` (dataclass gelée : les champs d'ITEM
  utiles au calcul + `projet_priorite`, `projet_rang`, `rang_projet`, `created_at`), `PlanPur`, `EtatRythme` (dataclass
  gelée, mêmes noms que les champs de `ReglagesRythme` §2.10 de `donnees.md` + `objectif` en vigueur ; PAS de champ `objectif_dit` : une seule source, `palier` + `palier_source='dit'`, I17 de `donnees.md` — `regles.md` l'applique déjà, `objectif_dit` y reste un nom de fonction), `JourCompte`
  (`jour`, `statut_jour`, `compte`, `essentiels_choisis`, `essentiels_faits`, `plan_prevues`, `plan_faites`) ; signatures
  de `cle_tri`, `placer`, `tuile_pure` sur ces types.
- `regles.md` §3.4 : `proposer_plan` = ce qui presse (`retard` ≤ 7 j, `echeance_passee` ≤ 7 j, `echeance_proche`) puis
  tour des projets par prochaine action (inv. 34 de `donnees.md`) ; `rang_projet` entre dans l'ordre ; nouveau jeu de
  test (collage de listes « Moyenne » sans date : les projets alternent).
- `regles.md` §4.1-§4.2 : À revoir = `reportee_3_fois`, `retard_ancien` (> 7 j), `activite_passee` seulement ; les
  motifs `jour_passe`, `echeance_passee`, `echeance_proche` sortent de `MotifRevoir` et deviennent des `RaisonPropose`.
- `regles.md` §3.6 : capacité − rendez-vous (inv. 35) ; `disponible_minutes`.
- `regles.md` : règle de `classer_priorites` (carte « Aide-moi à prioriser ») et de `journee/point/` ; règle de
  `plus_tard` (prochain jour travaillé de la même semaine, sinon le lundi suivant) ; règle de `repere.p60` (P60 des
  comptes des 9 derniers jours évalués, socle §6) ou retrait de la clé (verif-plan M17).
- `regles.md` §8 : usage `siri` de `nom_pour` ; paramètre `reglages` de `nom_pour` (verif-plan M10).
- `regles.md` §9 : effacement 09-08 par DEUX portes — récepteur `lead_erased` ET fournisseur DSR `erase(company,
  subject_identifier)` qui résout le sujet par `crm.selectors.cibles_du_sujet` (verif-plan M24).
- `regles.md` §1.9 : couleur d'office = `services.creation.couleur_d_office(user)` (verif-plan M14).
- `regles.md` §1 : lecteur ICS maison `moteur/ics.py` (VEVENT, DTSTART, DTEND, DURATION, SUMMARY, TZID ; RRULE non lu
  en v1, limite dite) — aucune dépendance neuve (verif-plan M23).
- `regles.md` / `textes.md` : liens de notification du bilan `?ouvrir=bilan` (critique m1) ; carte `pause` est une
  valeur de `CarteDuMoment` (m2) ; Siri « Ajouté dans un projet » pour un projet confidentiel (m8) ; m5 (plafond des
  micro-tâches, garde de taille, mémoire d'échec) et C6 hors de la première livraison (m6) : à dire dans `regles.md`
  §6 (les champs de données restent).
- `textes.md` : textes des états `EtatAgendaExterne` ; carte `priorites` (titre, raisons, gestes « Essentiel ·
  Aujourd'hui · Reporter à {jour} », « Garder ces N ») ; carte `point` ; « Rendez-vous » sous l'en-tête
  assistant ; texte du coupe-circuit (Réglages → Avancé, administrateur) ; les trois silences de Vie privée (A18).

## Révision 2 : ce qui a changé

Primauté A17, spec-7 r3 ; pastille = gardées ; `carte_du_moment` ; Proposé replié après Alléger ; obligations sans
heure ; Planifier ma semaine ; `lier-activite/`, `supprimees/` ; jeton : société du jeton ; 409 à codes ; hors ligne ;
`PATCH reglages/` en liste blanche ; GET redondants retirés ; tutoiement ; comptes par script (100 routes).

## Révision 2.1

`?ouvrir=bilan` rétabli ; `pause` dans CARTE_DU_MOMENT ; bilan « 4 sur 5 » + « 4 des 5 gardées » ; 10 échantillons ajoutés.

## Révision 3 : ce qui a changé

1. Primauté A18, `critique-finale.md`, `verif-plan-a-blanc.md`.
2. Agendas externes ESSENTIELS : 5 routes, RENDEZ_VOUS dans `aujourdhui/` et `agenda/`, temps disponible retranché.
3. Proposé : `raison` par ligne, ce qui presse en tête, tour des projets ; `?tout=1` → `suite_par_projet`.
4. Copilote : `journee/priorites/`, `journee/point/` ; actions `taches.tache.modifier`, `taches.journee.prioriser`,
   `taches.journee.point` ; jeu Groq avec `rythme.regler` ; demandes prêtes sans modèle.
5. Coupe-circuit `reglages-societe/` ; `respect_quiet_hours=False` après le contrôle propre.
6. En-tête assistant : posé par `headers=` du relais ; Bearer JWT = assistant (échec fermé).
7. Listes à plafond enveloppées ; échantillons COMPLETS générés en annexe A (aucun marqueur).
8. `TACHES_RACCOURCI_SIRI_URL` déclaré à l'échafaudage ; `_APP_URLS` en fin ; bouchon 401 des routes à jeton.
9. Brouillon `taches:brouillon:<user_id>` ; `IdempotentCreateMixin` ; `createModuleOutboxStore` relocalisé.
10. `g j` = aller à Aujourd'hui ; `c t` = saisir ; « + À faire » des Activités → saisie Tâches.
11. Comptes recalculés par script : 106 routes, 19 actions, 60 échantillons (tous des objets).

## Annexe A — échantillons complets (recopiables mot pour mot ; générés par un seul script)

**`agenda.json`** — GET agenda/ · consommateurs : Agenda, Planifier ma semaine
```json
{"du":"2026-11-16","au":"2026-11-22","jours":[{"jour":"2026-11-17","ouvre":true,"ferie":false,"toute_la_journee":[{"famille":"visite","id":88,"titre":"Visite — Karim Benali","jour":"2026-11-17","url":"/visites"}],"sans_heure":[{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":1}],"blocs":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4}],"echeances":[{"type":"tache","id":12,"titre":"Dossier subvention","statut":"fait","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":"2026-11-17","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"échéance aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":"2026-11-17T09:20:00+01:00","lock_version":5}],"externes":[{"cle":"2-9f2c1a7b","agenda_id":2,"agenda":"Microsoft 365","titre":"Réunion banque","debut":"2026-11-17T11:00:00+01:00","fin":"2026-11-17T12:00:00+01:00","journee_entiere":false}],"rendez_vous_minutes":60,"faites_nb":1}],"a_placer":[{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"indigo","priorite":2},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,"rang":null,"motif":"reportee_3_fois","raison":null,"explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":6}],"mes_projets":[{"projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"items":[{"type":"tache","id":30,"titre":"Préparer formation","statut":"a_faire","projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":45,"reports":0,"rang":null,"motif":null,"raison":{"code":"prochaine_action","texte":"prochaine action de Équipe"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2}]}],"capacite":{"minutes":240,"source":"defaut"}}
```

**`agenda_externe.json`** — POST/PATCH agendas-externes/, POST …/rafraichir/ · consommateurs : Réglages
```json
{"id":2,"hote":"outlook.office365.com","libelle":"Microsoft 365","actif":true,"rang":1024,"dernier_chargement_le":"2026-11-17T09:05:00+01:00","dernier_etat":"ok"}
```

**`agendas_externes.json`** — GET agendas-externes/ (non paginé, ≤ 3) · consommateurs : Réglages → Mon iPhone étape 2, Agenda
```json
{"results":[{"id":2,"hote":"outlook.office365.com","libelle":"Microsoft 365","actif":true,"rang":1024,"dernier_chargement_le":"2026-11-17T09:05:00+01:00","dernier_etat":"ok"}]}
```

**`ailleurs.json`** — GET aujourdhui/ailleurs/ · consommateurs : repli Ailleurs
```json
{"chantiers":1,"tickets":0,"da_a_commander":0,"leads_chauds":3,"rappels":0,"devis_expirant":1,"relances":2,"mentions":1,"lien":"/activites"}
```

**`aujourdhui.json`** — GET aujourdhui/ (avec ?tout=1 : `propose.suite_par_projet` rempli) · consommateurs : Aujourd'hui, cockpit, carte `ma_journee`, cache hors ligne
```json
{"jour":"2026-11-17","maintenant":"2026-11-17T09:12:00+01:00","jour_ouvre":true,"prochain_jour_ouvre":"2026-11-19","objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},"progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,"sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180,"activites_closes":0,"activites":1,"reprise":false},"plan":{"planifie_le":"2026-11-17T08:40:00+01:00","cloture_le":null,"allege_le":null},"carte_du_moment":{"type":"rythme","proposition":{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[{"reponse":"oui","libelle":"Monter à 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"},"donnees":{}},"essentiel":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4}],"obligations":[{"famille":"visite","id":88,"titre":"Visite — Karim Benali","jour":"2026-11-17","url":"/visites"},{"famille":"intervention","id":null,"titre":"Intervention Pose — Karim Benali","jour":"2026-11-17","url":"/chantiers?id=42"},{"famille":"touches","id":null,"titre":"Suivi des relances","jour":"2026-11-17","nb":5,"en_retard":2,"url":"/crm/relances"}],"rendez_vous":[{"cle":"2-9f2c1a7b","agenda_id":2,"agenda":"Microsoft 365","titre":"Réunion banque","debut":"2026-11-17T11:00:00+01:00","fin":"2026-11-17T12:00:00+01:00","journee_entiere":false}],"journee":[{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":1},{"type":"activite","id":101,"titre":"Rappeler Benali","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"activité ERP du jour","rappel":null,"lien":{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"},"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":null,"peut_cloturer":false,"a_notes":false,"fait_le":null,"lock_version":null}],"ce_soir":[{"type":"tache","id":60,"titre":"Préparer offre","statut":"a_faire","projet":{"id":5,"nom":"Maison","couleur":"ambre","priorite":2},"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"soir","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue ce soir","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"propose":{"replie":false,"pour_objectif":[{"type":"tache","id":21,"titre":"Déclaration TVA","statut":"a_faire","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":3,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":{"code":"echeance_proche","texte":"échéance jeu. 19"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2},{"type":"tache","id":41,"titre":"Ranger le bureau","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-16","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":{"code":"retard","texte":"prévue hier"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":3},{"type":"tache","id":30,"titre":"Préparer formation","statut":"a_faire","projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":45,"reports":0,"rang":null,"motif":null,"raison":{"code":"prochaine_action","texte":"prochaine action de Équipe"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2}],"reste_nb":6,"charge":{"minutes_estimees":150,"disponible_minutes":180,"surcharge":false},"suite_par_projet":[{"projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"items":[{"type":"tache","id":31,"titre":"Réserver la salle","statut":"a_faire","projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":2048,"motif":null,"raison":{"code":"action_suivante","texte":"suite de Équipe"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}]}]},"a_decider":[{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"indigo","priorite":2},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,"rang":null,"motif":"reportee_3_fois","raison":null,"explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":6}],"en_attente":[{"type":"tache","id":51,"titre":"Retour Lydec","statut":"en_attente","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"en attente de : Lydec","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"Lydec","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":3}],"faites":[{"type":"tache","id":12,"titre":"Dossier subvention","statut":"fait","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":"2026-11-17","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"échéance aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":"2026-11-17T09:20:00+01:00","lock_version":5}],"a_trier":{"boite_reception":3,"bloquees":1,"suggestions":2,"a_convertir":7},"tronque":false}
```

**`badge.json`** — GET badge/ · consommateurs : pastille
```json
{"n":3,"jour":"2026-11-17","a_trier":3}
```

**`capture.json`** — POST capture/ · consommateurs : raccourci Siri
```json
{"id":42,"dans":"journee","message":"Ajouté pour demain 10 h : appeler le fournisseur","deja":false}
```

**`carte_du_moment.json`** — forme CARTE_DU_MOMENT · consommateurs : Aujourd'hui, `vu/`
```json
{"type":"rythme","proposition":{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[{"reponse":"oui","libelle":"Monter à 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"},"donnees":{}}
```

**`coach_entete.json`** — GET coach/entete/ · consommateurs : relais du Copilote
```json
{"lignes":["Rythme : En faire plus · objectif 5 (accepté) · 1 sur 5","Préférences dites : sollicitations jusqu'à 19:00 · jour court : vendredi"]}
```

**`convertir_activite.json`** — POST convertir-activite/ · consommateurs : bandeau d'À trier
```json
{"converties":[{"activite_id":41,"tache_id":90}],"refusees":[{"activite_id":44,"raison":"assignee_a_un_collegue"}],"geste_id":79}
```

**`decalage.json`** — POST projets/{id}/decaler/ · consommateurs : Décaler les dates
```json
{"changements":[{"objet":"tache","id":41,"champ":"jour_prevu","avant":"2026-11-20","apres":"2026-11-27","titre":"Devis Settat"}],"geste_id":null}
```

**`erreurs.json`** — formes d'erreur (400, 400 par ligne, 404, 409) · consommateurs : client API du front
```json
{"champ":{"projet_id":["Projet inexistant."]},"par_ligne":{"lignes":{"3":{"titre":["Le titre est vide une fois la date et le projet retirés."]}}},"introuvable":{"detail":"Introuvable."},"conflit_version":{"detail":"Cet enregistrement a été modifié par quelqu'un d'autre depuis son ouverture.","code":"conflit_version","lock_version":5,"actuel":{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"}},"nom_pris":{"detail":"Un projet actif porte déjà ce nom.","code":"nom_pris"},"proposition_expiree":{"detail":"Cette proposition a expiré.","code":"proposition_expiree"},"autre_compte":{"detail":"Une action d'un autre compte a été retirée de la file.","code":"autre_compte"},"deja_lie":{"detail":"Cette activité a déjà sa tâche.","code":"deja_lie"},"effacement_occupe":{"detail":"Rien n'a été effacé : tes données étaient en cours d'utilisation. Réessaie dans un instant.","code":"effacement_occupe"}}
```

**`etiquettes.json`** — GET etiquettes/ (paginé) · consommateurs : Fiche → Plus, filtres
```json
{"count":2,"next":null,"previous":null,"results":[{"id":2,"nom":"magasin","couleur":"ciel"},{"id":3,"nom":"appels","couleur":"ambre"}]}
```

**`faites_semaine.json`** — GET taches/?periode=faites_semaine (paginé, + `total`, `activites_closes`) · consommateurs : Recherche « Faites cette semaine »
```json
{"count":1,"next":null,"previous":null,"results":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"fait","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":"2026-11-17T11:05:00+01:00","lock_version":5}],"total":2,"activites_closes":[{"jour":"2026-11-16","titre":"Rappeler M. Alami"}]}
```

**`geste_annuler.json`** — POST gestes/{id}/annuler/ · consommateurs : toast, cartes
```json
{"restaurees":[{"objet":"tache","id":41}],"conflits":[{"objet":"tache","id":12,"raison":"modifiee_depuis"}],"deja":false,"progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,"sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180,"activites_closes":0,"activites":1,"reprise":false}}
```

**`gestes.json`** — GET gestes/ (non paginé, ≤ 200) · consommateurs : Derniers gestes
```json
{"results":[{"id":77,"type":"planification","message":"Reportée à jeu. 19","titre":"Appeler le fournisseur","created_at":"2026-11-17T09:20:00+01:00","annule_le":null,"annulable":true},{"id":76,"type":"rythme","message":"Garder ce rythme : environ 5 tâches par jour (4 à 6).","titre":null,"created_at":"2026-11-17T09:12:00+01:00","annule_le":null,"annulable":true}]}
```

**`item.json`** — forme ITEM · consommateurs : toutes les listes
```json
{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4}
```

**`jeton.json`** — POST jetons/ · consommateurs : Mon iPhone
```json
{"id":3,"usage":"flux","prefixe":"tqf_Ab12","libelle":"","created_at":"2026-11-17T09:00:00+01:00","dernier_usage_le":null,"revoque_le":null,"jeton":"tqf_Ab12xYz0123456789abcdefghijklmnopqrstuvw","url":"https://erp.example/api/django/taches/flux/tqf_Ab12xYz0123456789abcdefghijklmnopqrstuvw.ics","webcal":"webcal://erp.example/api/django/taches/flux/tqf_Ab12xYz0123456789abcdefghijklmnopqrstuvw.ics"}
```

**`jetons_liste.json`** — GET jetons/ (non paginé, ≤ 20) · consommateurs : Mon iPhone
```json
{"results":[{"id":3,"usage":"flux","prefixe":"tqf_Ab12","libelle":"","created_at":"2026-11-17T09:00:00+01:00","dernier_usage_le":"2026-11-17T09:41:00+01:00","revoque_le":null}]}
```

**`journee_cloture.json`** — GET journee/cloture/ · consommateurs : Bilan du soir
```json
{"jour":"2026-11-17","faites":[{"type":"tache","id":12,"titre":"Dossier subvention","statut":"fait","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":"2026-11-17","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"échéance aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":"2026-11-17T09:20:00+01:00","lock_version":5}],"restes":[{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":1}],"a_trancher":[{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"indigo","priorite":2},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,"rang":null,"motif":"reportee_3_fois","raison":null,"explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":6}],"prochain_jour_ouvre":"2026-11-19","bilan":{"faites":4,"objectif":5,"objectif_atteint":false,"essentiel_faites":1,"essentiel_prevues":2,"plan_tenues":4,"plan_lignes":5,"texte":"4 sur 5 · essentiel 1 sur 2","texte_gardees":""},"constat":{"id":44,"type":"constat","cle":"C3","texte":"Vendredi : 3,1 tâches en moyenne, 5,2 les autres jours.","donnees":{"jour":4,"m1":3.1,"m2":5.2},"boutons":[{"reponse":"oui","libelle":"Oui"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"},"activites_a_clore":[{"type":"activite","id":101,"titre":"Rappeler Benali","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"activité ERP du jour","rappel":null,"lien":{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"},"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":null,"peut_cloturer":false,"a_notes":false,"fait_le":null,"lock_version":null}],"possible_jusqua":"2026-11-18T12:00:00+01:00"}
```

**`journee_cloturee.json`** — POST journee/cloturer/ · consommateurs : Bilan du soir
```json
{"plan":{"jour":"2026-11-17","cloture_le":"2026-11-17T18:20:00+01:00"},"geste_id":83}
```

**`journee_ecrite.json`** — POST journee/planifier/ et journee/alleger/ · consommateurs : Proposé, carte du moment, Alléger
```json
{"aujourdhui":{"jour":"2026-11-17","maintenant":"2026-11-17T09:12:00+01:00","jour_ouvre":true,"prochain_jour_ouvre":"2026-11-19","objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},"progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,"sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180,"activites_closes":0,"activites":1,"reprise":false},"plan":{"planifie_le":"2026-11-17T08:40:00+01:00","cloture_le":null,"allege_le":null},"carte_du_moment":{"type":"rythme","proposition":{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[{"reponse":"oui","libelle":"Monter à 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"},"donnees":{}},"essentiel":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4}],"obligations":[{"famille":"visite","id":88,"titre":"Visite — Karim Benali","jour":"2026-11-17","url":"/visites"},{"famille":"intervention","id":null,"titre":"Intervention Pose — Karim Benali","jour":"2026-11-17","url":"/chantiers?id=42"},{"famille":"touches","id":null,"titre":"Suivi des relances","jour":"2026-11-17","nb":5,"en_retard":2,"url":"/crm/relances"}],"rendez_vous":[{"cle":"2-9f2c1a7b","agenda_id":2,"agenda":"Microsoft 365","titre":"Réunion banque","debut":"2026-11-17T11:00:00+01:00","fin":"2026-11-17T12:00:00+01:00","journee_entiere":false}],"journee":[{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":1},{"type":"activite","id":101,"titre":"Rappeler Benali","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"activité ERP du jour","rappel":null,"lien":{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"},"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":null,"peut_cloturer":false,"a_notes":false,"fait_le":null,"lock_version":null}],"ce_soir":[{"type":"tache","id":60,"titre":"Préparer offre","statut":"a_faire","projet":{"id":5,"nom":"Maison","couleur":"ambre","priorite":2},"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"soir","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue ce soir","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"propose":{"replie":false,"pour_objectif":[{"type":"tache","id":21,"titre":"Déclaration TVA","statut":"a_faire","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":3,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":{"code":"echeance_proche","texte":"échéance jeu. 19"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2},{"type":"tache","id":41,"titre":"Ranger le bureau","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-16","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":{"code":"retard","texte":"prévue hier"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":3},{"type":"tache","id":30,"titre":"Préparer formation","statut":"a_faire","projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":45,"reports":0,"rang":null,"motif":null,"raison":{"code":"prochaine_action","texte":"prochaine action de Équipe"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2}],"reste_nb":6,"charge":{"minutes_estimees":150,"disponible_minutes":180,"surcharge":false},"suite_par_projet":null},"a_decider":[{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"indigo","priorite":2},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,"rang":null,"motif":"reportee_3_fois","raison":null,"explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":6}],"en_attente":[{"type":"tache","id":51,"titre":"Retour Lydec","statut":"en_attente","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"en attente de : Lydec","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"Lydec","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":3}],"faites":[{"type":"tache","id":12,"titre":"Dossier subvention","statut":"fait","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":"2026-11-17","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"échéance aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":"2026-11-17T09:20:00+01:00","lock_version":5}],"a_trier":{"boite_reception":3,"bloquees":1,"suggestions":2,"a_convertir":7},"tronque":false},"renvoyees":[],"geste_id":81}
```

**`journee_proposition.json`** — GET journee/proposition/ · consommateurs : « Voir tout », carte `plan_propose`, « Planifie ma journée »
```json
{"jour":"2026-11-17","objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},"capacite":{"minutes":240,"source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180},"a_decider":[{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"indigo","priorite":2},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,"rang":null,"motif":"reportee_3_fois","raison":null,"explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":6}],"proposition":[{"item":{"type":"tache","id":21,"titre":"Déclaration TVA","statut":"a_faire","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":3,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":{"code":"echeance_proche","texte":"échéance jeu. 19"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2},"deja_prevue":false,"cochee":true},{"item":{"type":"tache","id":30,"titre":"Préparer formation","statut":"a_faire","projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":45,"reports":0,"rang":null,"motif":null,"raison":{"code":"prochaine_action","texte":"prochaine action de Équipe"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2},"deja_prevue":false,"cochee":true}],"charge":{"minutes_estimees":150,"sans_estimation":1,"surcharge":false,"non_calculable":false},"rythme":{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[{"reponse":"oui","libelle":"Monter à 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"},"suite_par_projet":[{"projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"items":[{"type":"tache","id":31,"titre":"Réserver la salle","statut":"a_faire","projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":2048,"motif":null,"raison":{"code":"action_suivante","texte":"suite de Équipe"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}]}]}
```

**`liens_cibles.json`** — carte des URL de cibles (fichier, pas une route) · consommateurs : `selectors.url_de_cible`, `cibleEcran.js`
```json
{"crm.lead":"/crm/leads?lead={id}","crm.client":"/crm?id={id}","ventes.devis":"/ventes/devis?devis={id}"}
```

**`lier_activite.json`** — POST taches/lier-activite/ · consommateurs : appui long sur une activité
```json
{"tache":{"type":"tache","id":95,"titre":"Préparer l'appel Benali","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"crm.lead","id":1637,"libelle":"Karim Benali","url":"/crm/leads?lead=1637","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"activite","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":101,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"},"suivante":null,"projet_cree":null,"rappel":null,"question_titres":false,"avertissements":[],"progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,"sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180,"activites_closes":0,"activites":1,"reprise":false},"geste_id":92}
```

**`lot.json`** — POST taches/lot/ · consommateurs : sélection, « Tout pour plus tard »
```json
{"appliquees":[41],"refusees":[{"id":42,"raison":"introuvable"}],"geste_id":78}
```

**`mes_donnees.json`** — GET mes-donnees/ · consommateurs : Réglages → Mes données
```json
{"exporte_le":"2026-11-17T10:00:00+01:00","projet":[{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4}],"section":[],"tache":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"}],"element_checklist":[],"etiquette":[],"etiquette_tache":[],"regle_recurrence":[],"plan_jour":[],"ligne_plan_jour":[],"reglages_rythme":[{"mode":"pousser","palier":5}],"preference":[],"incitation_coach":[],"rappel":[],"jeton_acces":[{"id":3,"usage":"flux","prefixe":"tqf_Ab12","revoque_le":null}],"geste_annulable":[],"vue_enregistree":[],"modele_projet":[],"revue_projet":[],"suggestion_tache":[],"agenda_externe":[{"id":2,"hote":"outlook.office365.com","libelle":"Microsoft 365"}],"reglages_societe":[]}
```

**`modele.json`** — GET modeles/{id}/ · consommateurs : Modèles
```json
{"id":2,"nom":"Salon","created_at":"2026-11-10T09:00:00+01:00","contenu":{"v":1,"objectif":"Stand monté","priorite":2,"sections":[{"nom":"Préparation","decalage_debut":0,"decalage_fin":14}],"taches":[{"titre":"Réserver le stand","section_index":0,"priorite":3,"jalon":false,"decalage_jour":0,"decalage_echeance":5,"parent_index":null,"bloquee_par_index":null,"checklist":[],"notes":""}]},"confidentielles_non_reprises":0}
```

**`modele_instancier.json`** — POST modeles/{id}/instancier/ · consommateurs : Depuis un modèle
```json
{"projet":{"nom":"Salon"},"sections":[{"nom":"Préparation","date_debut":"2026-11-23","date_fin":"2026-12-07"}],"taches":[{"titre":"Réserver le stand","jour_prevu":"2026-11-23","echeance":"2026-11-30"}],"confidentielles_non_reprises":0,"geste_id":null}
```

`confidentielles_non_reprises` : le nombre de tâches confidentielles laissées de côté par la copie (dupliquer, enregistrer comme modèle, instancier) ; servi aussi sous l'en-tête de l'assistant (un nombre, jamais un contenu).

**`modeles_liste.json`** — GET modeles/ (paginé) · consommateurs : Modèles, Depuis un modèle
```json
{"count":1,"next":null,"previous":null,"results":[{"id":2,"nom":"Salon","created_at":"2026-11-10T09:00:00+01:00","nb_taches":12,"nb_sections":3}]}
```

**`planification.json`** — POST projets/{id}/planification/ · consommateurs : Planifier le projet
```json
{"projet":{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4},"creees":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"}],"geste_id":85}
```

**`planification_apercu.json`** — POST projets/{id}/planification/apercu/ · consommateurs : Planifier le projet, carte `plan_projet`
```json
{"projet":{"id":3,"lock_version":4},"sections":[{"nom":"Études","taches":[{"titre":"Visite","jalon":false,"sous_taches":["photos"]},{"titre":"Mise en service","jalon":true,"sous_taches":[]}]}]}
```

**`point.json`** — GET journee/point/ · consommateurs : carte `point` (« Où j'en suis ? »)
```json
{"jour":"2026-11-17","maintenant":"2026-11-17T15:00:00+01:00","objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},"progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,"sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180,"activites_closes":0,"activites":1,"reprise":false},"faites":1,"minutes_restantes":75,"deborde_minutes":0,"essentiel_restant":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":4}],"prochaine":{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":1},"restes_nb":3,"rendez_vous_restants":[],"carte_du_moment":{"type":"alleger","proposition":null,"donnees":{"faites":1,"prevues":4}}}
```

**`priorites.json`** — GET journee/priorites/ · consommateurs : carte `priorites` (« Aide-moi à prioriser »)
```json
{"jour":"2026-11-17","objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},"garder_n":2,"plus_tard":"2026-11-19","faites":1,"minutes_restantes":75,"deborde_minutes":0,"geste_propose":null,"lignes":[{"rang":1,"item":{"type":"tache","id":21,"titre":"Déclaration TVA","statut":"a_faire","projet":{"id":4,"nom":"Admin","couleur":"prune","priorite":1},"section":null,"parent_id":null,"priorite":3,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":30,"reports":0,"rang":null,"motif":null,"raison":{"code":"echeance_proche","texte":"échéance jeu. 19"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2}},{"rang":2,"item":{"type":"tache","id":30,"titre":"Préparer formation","statut":"a_faire","projet":{"id":7,"nom":"Équipe","couleur":"bleu","priorite":3},"section":null,"parent_id":null,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":45,"reports":0,"rang":null,"motif":null,"raison":{"code":"prochaine_action","texte":"prochaine action de Équipe"},"explication":"","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":2}},{"rang":3,"item":{"type":"tache","id":50,"titre":"Site web","statut":"a_faire","projet":{"id":9,"nom":"SiteWeb","couleur":"indigo","priorite":2},"section":null,"parent_id":null,"priorite":1,"jour_prevu":"2026-11-13","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":3,"rang":null,"motif":"reportee_3_fois","raison":null,"explication":"reportée 3 fois","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":6}}],"tronque":false}
```

**`projet.json`** — GET projets/{id}/ · consommateurs : Un projet (en-tête)
```json
{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4}
```

**`projet_ecrit.json`** — projets/{id}/terminer/, restaurer/, DELETE projets/{id}/, PATCH · consommateurs : Un projet ⋯, Archive, Supprimées
```json
{"projet":{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"termine","statut_depuis":"2026-11-17T17:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":"2026-11-17T17:00:00+01:00","issue":"atteint","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":5},"deplacees":3,"restaurees":0,"supprimees":0,"geste_id":86}
```

**`projet_vue.json`** — GET projets/{id}/vue/ · consommateurs : Un projet, carte `projet`
```json
{"projet":{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4},"avancement":{"faites":12,"total":20,"derniere_faite_le":"2026-11-03"},"prochain_jalon":{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":true,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4},"prochaine_action":{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4},"sections":[{"id":8,"nom":"Études","rang":1024,"date_debut":null,"date_fin":"2026-11-30","taches":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4}],"compteurs":{"ouvertes":1,"faites":4}}],"sans_section":[{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":1}],"sans_section_compteurs":{"ouvertes":7,"faites":8},"faites_nb":12,"burnup":[{"semaine":"2026-11-09","total":18,"faites":10}],"burnup_legende":"reconstruit depuis les dates actuelles"}
```

**`projets_liste.json`** — GET projets/ (paginé) · consommateurs : Projets, sélecteur
```json
{"count":1,"next":null,"previous":null,"results":[{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4}],"constat":{"actifs":7,"avances_7j":3}}
```

**`proposition.json`** — forme PROPOSITION · consommateurs : cartes, bilan, plan
```json
{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[{"reponse":"oui","libelle":"Monter à 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"}
```

**`proposition_repondue.json`** — POST rythme/propositions/{id}/repondre/ · consommateurs : carte du moment, Mon rythme
```json
{"proposition":{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[],"expire_le":"2026-11-24"},"rythme":{"mode":"pousser","comprendre_mon_rythme":true,"objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},"trace":"5 faites ou plus 7 jours sur 10","bloc":{"jours":7,"tenus":5,"sur":10},"tenir":null,"proposition":{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[{"reponse":"oui","libelle":"Monter à 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"},"serie":[{"jour":"2026-11-16","statut_jour":"evalue","faites":5,"objectif":5,"essentiel_faites":1,"essentiel_prevues":1,"plan_tenues":4,"plan_lignes":5}],"constats":[{"id":44,"type":"constat","cle":"C3","texte":"Vendredi : 3,1 tâches en moyenne, 5,2 les autres jours.","donnees":{"jour":4,"m1":3.1,"m2":5.2},"boutons":[{"reponse":"oui","libelle":"Oui"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"}],"repere":{"p60":5.5,"jours":9},"preferences":[{"cle":"heure_limite","valeur":"19:00","source":"copilote","dite_le":"2026-11-17T09:00:00+01:00"}],"jours_travailles":"1111100","geste_id":91},"geste_id":91}
```

**`rappel_repeter.json`** — POST rappels/{id}/repeter/ · consommateurs : fiche ouverte par le rappel
```json
{"rappel":{"id":32,"jour":"2026-11-17","heure":"16:00","ancre":"","decalage_jours":0,"statut":"en_attente","hors_fenetre":false},"geste_id":90}
```

**`recherche.json`** — GET recherche/ · consommateurs : Recherche, palette, carte `liste_taches`
```json
{"projets":[{"id":3,"nom":"Ventes","couleur":"vert","statut":"actif","priorite":3}],"taches":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4}]}
```

**`reglages.json`** — GET/PATCH reglages/ · consommateurs : Réglages, Mon iPhone
```json
{"titres_notifications":false,"titres_notifications_demande":false,"titres_calendrier":true,"titres_tuile":true,"messages_sans_delai":false,"rappel_avant_bloc_min":null,"projet_arret_jours":10,"familles_suggestions":["devis_accepte","chantier_receptionne","chantier_annule"],"suggestions_societe":false,"erp_dans_journee":true,"comprendre_mon_rythme":true,"pauses_sollicitations":[{"type":"plan_matin","ignorees":14}],"sollicitations":{"heure_matin":"08:30","relance_jour":"15:00","heure_soir":"18:00","heure_limite":"20:00","revue_semaine":"auto"},"fenetre_societe":{"debut":"08:30","fin":"19:00"},"raccourci_siri_url":null,"est_admin":false}
```

**`reglages_societe.json`** — GET/PATCH reglages-societe/ (administrateur) · consommateurs : Réglages → Avancé (admin)
```json
{"balayage_actif":true,"modifie_par":null,"modifie_le":null}
```

**`rendez_vous.json`** — forme RENDEZ_VOUS (aujourdhui/, agenda/) · consommateurs : Aujourd'hui, Agenda
```json
{"results":[{"cle":"2-9f2c1a7b","agenda_id":2,"agenda":"Microsoft 365","titre":"Réunion banque","debut":"2026-11-17T11:00:00+01:00","fin":"2026-11-17T12:00:00+01:00","journee_entiere":false}]}
```

**`revue_decision.json`** — PUT revue/projets/{projet_id}/ · consommateurs : Revue
```json
{"revue":{"semaine":"2026-11-16","intention":"Signer Settat","decision":"garder","focus":true,"prochaine_action_id":20},"projet":{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4},"geste_id":89}
```

**`revue_projets.json`** — GET revue/projets/ · consommateurs : Revue, carte `revue_semaine`
```json
{"semaine":"2026-11-16","semaine_courte":false,"bilan_semaine":{"texte":"Cette semaine : 26 faites (23 la précédente). Essentiel 4 sur 5.","donnees":{"faites":26,"jours":6,"prec":23}},"focus_projet_id":3,"cartes":[{"projet":{"id":3,"nom":"Ventes","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[{"code":"a_l_arret","phrase":"Rien de fait depuis 10 jours travaillés.","donnees":{"jours":10,"depuis":"2026-11-03"}}],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4},"faites_semaine":[{"id":12,"titre":"Dossier subvention"}],"faites_nb":4,"prevues_aujourdhui_nb":1,"bloquees":[{"id":44,"titre":"Pose","attend":{"id":43,"titre":"Livraison"}}],"prochaine_action":{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4},"revue":{"intention":"","decision":"","focus":false}},{"projet":{"id":7,"nom":"Équipe","objectif":"Fini quand la formation est donnée","icone":"","couleur":"bleu","priorite":2,"statut":"en_pause","statut_depuis":"2026-11-17T09:20:00+01:00","domaine":"","date_debut":null,"echeance":null,"termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-05T10:00:00+01:00","rang":3072,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":3,"faites":2},"sante":[],"focus_semaine":false,"updated_at":"2026-11-17T09:20:00+01:00","lock_version":2},"faites_semaine":[],"faites_nb":0,"prevues_aujourdhui_nb":0,"bloquees":[],"prochaine_action":null,"revue":{"intention":"","decision":"pause","focus":false}}]}
```
`prevues_aujourdhui_nb` (C-5, R2-031) : tâches OUVERTES de ce projet prévues AUJOURD'HUI (jour local) qui restent dans la
journée si on le met en pause maintenant — le préfiltre `taches_de_la_journee` (sans sous-tâche, non bloquées, hors « Un
jour »), compté en UNE requête pour toutes les cartes ; 0 quand il n'y en a pas (la Revue ne dit alors rien).

**`rythme.json`** — GET rythme/ (et réponses de rythme/, preferences/) · consommateurs : Mon rythme, carte `rythme`
```json
{"mode":"pousser","comprendre_mon_rythme":true,"objectif":{"nb":5,"source":"accepte","mode":"pousser","zone":null},"trace":"5 faites ou plus 7 jours sur 10","bloc":{"jours":7,"tenus":5,"sur":10},"tenir":null,"proposition":{"id":41,"type":"proposition_palier","cle":"monter","texte":"Ces 10 jours travaillés, tu as fait au moins 5 tâches 7 fois. On passe à 6 ?","donnees":{"N":5,"N1":6,"tenus":7},"boutons":[{"reponse":"oui","libelle":"Monter à 6"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"},"serie":[{"jour":"2026-11-03","statut_jour":"evalue","faites":5,"objectif":5,"essentiel_faites":1,"essentiel_prevues":1,"plan_tenues":4,"plan_lignes":5,"hors_objectif":false},{"jour":"2026-11-04","statut_jour":"evalue","faites":6,"objectif":5,"essentiel_faites":0,"essentiel_prevues":0,"plan_tenues":0,"plan_lignes":0,"hors_objectif":false},{"jour":"2026-11-05","statut_jour":"evalue","faites":4,"objectif":5,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":2,"plan_lignes":4,"hors_objectif":false},{"jour":"2026-11-06","statut_jour":"evalue","faites":5,"objectif":5,"essentiel_faites":1,"essentiel_prevues":1,"plan_tenues":3,"plan_lignes":3,"hors_objectif":false},{"jour":"2026-11-09","statut_jour":"evalue","faites":7,"objectif":5,"essentiel_faites":1,"essentiel_prevues":1,"plan_tenues":5,"plan_lignes":6,"hors_objectif":false},{"jour":"2026-11-10","statut_jour":"sans_donnees","faites":0,"objectif":null,"essentiel_faites":0,"essentiel_prevues":0,"plan_tenues":0,"plan_lignes":0,"hors_objectif":false},{"jour":"2026-11-11","statut_jour":"evalue","faites":5,"objectif":5,"essentiel_faites":0,"essentiel_prevues":0,"plan_tenues":0,"plan_lignes":0,"hors_objectif":false},{"jour":"2026-11-12","statut_jour":"evalue","faites":3,"objectif":5,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":3,"hors_objectif":false},{"jour":"2026-11-13","statut_jour":"evalue","faites":6,"objectif":5,"essentiel_faites":1,"essentiel_prevues":1,"plan_tenues":4,"plan_lignes":4,"hors_objectif":false},{"jour":"2026-11-14","statut_jour":"non_ouvre","faites":3,"objectif":null,"essentiel_faites":0,"essentiel_prevues":0,"plan_tenues":0,"plan_lignes":0,"hors_objectif":true},{"jour":"2026-11-16","statut_jour":"evalue","faites":5,"objectif":5,"essentiel_faites":1,"essentiel_prevues":1,"plan_tenues":4,"plan_lignes":5,"hors_objectif":false}],"constats":[{"id":44,"type":"constat","cle":"C3","texte":"Vendredi : 3,1 tâches en moyenne, 5,2 les autres jours.","donnees":{"jour":4,"m1":3.1,"m2":5.2},"boutons":[{"reponse":"oui","libelle":"Oui"},{"reponse":"pas_maintenant","libelle":"Pas maintenant"}],"expire_le":"2026-11-24"}],"repere":{"p60":5.5,"jours":9},"preferences":[{"cle":"heure_limite","valeur":"19:00","source":"copilote","dite_le":"2026-11-17T09:00:00+01:00"}],"jours_travailles":"1111100","geste_id":91}
```

**`saisie_apercu.json`** — POST saisie-rapide/ apercu:true · consommateurs : Saisie, collage, carte `capture_apercu`, « Range ma liste »
```json
{"projets_communs":[{"collage":0,"id":null,"nom":"Courses","nouveau":true,"priorite":2,"source":"premiere_ligne","ressemble_a":null}],"lignes":[{"index":0,"collage":0,"tache_id":null,"titre":"Appeler Karim","cochee":true,"deja_faite":false,"doublon_de":null,"doublon_projet":null,"etape_de":null,"alertes":[],"jetons":[{"type":"jour","source":"demain","debut":14,"fin":20,"valeur":"2026-11-18","libelle":"mer. 18 nov."},{"type":"projet","source":"#SiteWeb","debut":21,"fin":29,"valeur":{"id":null,"nom":"SiteWeb","nouveau":true,"priorite":2},"libelle":"Nouveau projet : SiteWeb"}],"champs":{"jour_prevu":"2026-11-18","nouveau_projet":{"nom":"SiteWeb","priorite":2},"priorite":0}}],"projets_nouveaux":[{"nom":"SiteWeb","priorite":2,"ressemble_a":null}]}
```

**`saisie_rapide.json`** — POST saisie-rapide/ (création) · consommateurs : Saisie, file hors ligne
```json
{"creees":[{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"}],"projets_crees":[{"id":9,"nom":"SiteWeb","couleur":"menthe","priorite":2}],"deja_creees":["c1f4b2a0-5d1e-4b9a-9a51-2b7f0c3e8d11:0"],"geste_id":77}
```

**`suggestion_refusee.json`** — POST suggestions/{id}/refuser/ · consommateurs : À trier
```json
{"id":5,"statut":"refusee","geste_id":80}
```

**`suggestions.json`** — GET suggestions/ (non paginé, ≤ 20) · consommateurs : À trier « Suggéré par l'ERP »
```json
{"results":[{"id":5,"famille":"devis_accepte","titre":"Préparer le chantier du devis accepté","lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"created_at":"2026-11-17T08:00:00+01:00"}]}
```

**`supprimees.json`** — GET supprimees/ · consommateurs : Supprimées récemment
```json
{"projets":[{"projet":{"id":11,"nom":"Ancien salon","objectif":"Fini quand les 4 devis sont signés","icone":"","couleur":"vert","priorite":3,"statut":"actif","statut_depuis":"2026-10-01T09:00:00+01:00","domaine":"","date_debut":null,"echeance":"2026-12-15","termine_le":null,"issue":"","bilan":"","planification_le":"2026-10-01T09:05:00+01:00","rang":2048,"confidentiel":false,"affichage":{"vue":"liste","tri":"manuel","groupe":"section","montrer_faites":false},"a_planifier":false,"compteurs":{"ouvertes":8,"faites":12},"sante":[],"focus_semaine":false,"updated_at":"2026-11-16T18:00:00+01:00","lock_version":4},"taches_nb":25,"deleted_at":"2026-11-15T10:00:00+01:00"}],"taches":[{"item":{"type":"tache","id":42,"titre":"Timbres","statut":"a_faire","projet":null,"section":null,"parent_id":null,"priorite":0,"jour_prevu":"2026-11-17","moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":15,"reports":0,"rang":null,"motif":null,"raison":null,"explication":"prévue aujourd'hui","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"manuel","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":1},"deleted_at":"2026-11-16T11:00:00+01:00"}]}
```

**`tache.json`** — GET taches/{id}/ · consommateurs : Fiche
```json
{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"}
```

**`tache_changement.json`** — POST taches/{id}/changement/apercu/ · consommateurs : carte `tache` (écho)
```json
{"tache":{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4},"proposition":{"geste":"renommer","avant":"Devis Settat","apres":"Devis Settat — relance"}}
```

**`tache_ecrite.json`** — toute écriture d'une tâche · consommateurs : carte `tache`, toasts, conflit
```json
{"tache":{"type":"tache","id":20,"titre":"Devis Settat","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":4,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"},"suivante":null,"projet_cree":null,"rappel":null,"question_titres":false,"avertissements":[{"code":"prevue_apres_echeance","message":"Prévue après l'échéance."}],"progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,"sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180,"activites_closes":0,"activites":1,"reprise":false},"geste_id":77}
```

**`tache_recurrente_ecrite.json`** — POST taches/{id}/terminer/ (récurrente) · consommateurs : case, toast « Fait · prochaine »
```json
{"tache":{"type":"tache","id":20,"titre":"Devis Settat","statut":"fait","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-17","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":{"jour":"2026-11-17","heure":"09:45"},"lien":{"cible":"ventes.devis","id":512,"libelle":"DEV-2026-11-0042","url":"/ventes/devis?devis=512","etat":"ok"},"checklist":{"faits":1,"total":1},"sous_taches":{"faites":0,"total":1},"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":"2026-11-17T10:05:00+01:00","lock_version":5,"notes":"Appeler avant 11 h.","etiquettes":[{"id":2,"nom":"magasin","couleur":"ciel"}],"elements_checklist":[{"id":71,"libelle":"Prix","fait":true,"rang":1024}],"enfants":[{"type":"tache","id":22,"titre":"Relire les quantités","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":20,"priorite":0,"jour_prevu":null,"moment":"","heure_debut":null,"echeance":null,"echeance_heure":null,"quelque_jour":false,"estimation_minutes":null,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"dans Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":false,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":false,"prevue_au_plan":false,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":false,"fait_le":null,"lock_version":0}],"recurrence":null,"rappels":[{"id":31,"jour":"2026-11-17","heure":"09:45","ancre":"","decalage_jours":0,"statut":"en_attente"}],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":null,"activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"},"suivante":{"type":"tache","id":23,"titre":"Rapport hebdo","statut":"a_faire","projet":{"id":3,"nom":"Ventes","couleur":"vert","priorite":3},"section":null,"parent_id":null,"priorite":2,"jour_prevu":"2026-11-23","moment":"matin","heure_debut":"10:00","echeance":"2026-11-19","echeance_heure":null,"quelque_jour":false,"estimation_minutes":60,"reports":0,"rang":1024,"motif":null,"raison":null,"explication":"échéance jeu. 19 (1 jour travaillé) · projet prioritaire Ventes","rappel":null,"lien":null,"checklist":null,"sous_taches":null,"recurrente":true,"routine":false,"jalon":false,"bloquee_par":null,"en_attente_de":"","essentielle":true,"prevue_au_plan":true,"confidentiel":false,"confidentielle":false,"source":"rapide","peut_cloturer":true,"a_notes":true,"fait_le":null,"lock_version":0,"notes":"Appeler avant 11 h.","etiquettes":[],"elements_checklist":[],"enfants":[],"recurrence":{"id":9,"frequence":"hebdo","intervalle":1,"jours_semaine":"1000000","jour_du_mois":null,"rang_dans_mois":null,"mode":"calendrier","date_debut":"2026-11-17","date_fin":null,"actif":true,"libelle":"chaque lundi"},"rappels":[],"triee_le":"2026-11-16T18:02:00+01:00","premier_jour_prevu":"2026-11-17","reports_tranches":0,"duree_reelle_minutes":null,"annule_le":null,"occurrence_du":"2026-11-23","activite_origine_id":null,"lien_verifie_le":"2026-11-17T09:12:00+01:00","created_at":"2026-11-16T18:02:00+01:00","updated_at":"2026-11-17T10:42:00+01:00"},"projet_cree":null,"rappel":null,"question_titres":false,"avertissements":[],"progression":{"faites":1,"detail":{"etapes":0,"routines":0,"micro_non_comptees":0,"activites_closes":0},"prevues":4,"essentiel_faites":0,"essentiel_prevues":1,"plan_tenues":1,"plan_lignes":4,"minutes_prevues":75,"sans_estimation":1,"capacite_minutes":240,"capacite_source":"defaut","rendez_vous_minutes":60,"disponible_minutes":180,"activites_closes":0,"activites":1,"reprise":false},"geste_id":93}
```

**`tout_effacer.json`** — POST tout-effacer/ · consommateurs : Réglages → Mes données
```json
{"effacees":{"tache":40,"projet":3,"plan_jour":12}}
```

**`tuile.json`** — GET tuile/ · consommateurs : `scriptTuile.js`
```json
{"jour":"2026-11-17","maj":"2026-11-17T09:41:00+01:00","faites":1,"prevues":4,"objectif":5,"essentiel":{"faites":0,"prevues":1},"top":[{"id":20,"titre":"Devis Settat","heure":"10:00","priorite":2}],"reste":1,"prochaine_echeance":{"titre":"Devis Settat","jour":"2026-11-19","heure":null},"lien":"https://erp.example/taches/aujourdhui"}
```

**`vu.json`** — POST vu/ · consommateurs : Aujourd'hui
```json
{"carte_du_moment":{"type":"retour","proposition":{"id":52,"type":"retour","cle":"","texte":"Tu reviens après 10 jours : 18 tâches attendaient.","donnees":{"jours":10,"taches":18,"ids":[30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47]},"boutons":[{"reponse":"remettre_dans_propose","libelle":"Les remettre dans Proposé"},{"reponse":"une_par_une","libelle":"Les voir une par une"}],"expire_le":"2026-11-24"},"donnees":{}}}
```

**`vues.json`** — GET vues/ (non paginé, ≤ 30) · consommateurs : Recherche
```json
{"results":[{"id":4,"nom":"Haute cette semaine","rang":1024,"filtres":{"priorite_min":3,"projets":[3],"inclure_faites":false}}]}
```


## Révision 3.3 — vague 3 (lane L1) : un chiffre, une source

Écrit par la lane L1 (corrections R3) ; l'annexe A est régénérée depuis les échantillons (contrat d'abord).

- **Bilan du soir** (`journee_cloture.json`) : `bilan.texte_gardees` est toujours `""` (clé gardée, plus aucun « x des
  y gardées », R3-001) ; `bilan.essentiel_*` = ceux de la PROGRESSION (même calcul qu'`aujourdhui/`).
- **Revue** (`revue_projets.json`, R3-003, R3-009) : `bilan_semaine.donnees.faites` = la somme de
  `selectors.journee.faites_par_jour` du lundi à aujourd'hui (week-end et aujourd'hui compris), `prec` = la même somme
  sur la semaine d'avant (`null` sans aucune faite ni jour évalué cette semaine-là), `jours` = jours de la semaine où
  il a fait au moins une chose ; texte « Cette semaine : 26 faites (23 la précédente). Essentiel 4 sur 5. » — ni
  « Objectif atteint X jours sur N » ni « x des y gardées ». `cartes` : chaque projet ACTIF, et chaque projet NON
  actif (en pause, terminé) qui a une `RevueProjet` de la semaine, avec sa décision (`revue.decision` = `pause`,
  `terminer`…), dans un seul ordre (priorité décroissante, rang) : la revue rechargée garde le projet mis en pause à
  sa place. Une carte non active : `sante` vide ; `prochaine_action` peut être `null`.
- **Mon rythme** (`rythme.json`, R3-003, C-21) : chaque entrée de `serie` porte `hors_objectif` (booléen). Les 10
  derniers jours TRAVAILLÉS gardent `hors_objectif: false` ; s'y ajoutent, à leur date, les jours NON travaillés
  (`statut_jour` `non_ouvre` ou `conge`) de la même fenêtre où il a fait au moins une chose (`faites` > 0, le compte
  de la nuit) avec `hors_objectif: true` — barre grise, jamais comptée dans `trace`, `bloc`, l'objectif ni le
  rythme. Aucune requête de plus (les `PlanJour` déjà lus). `tenir` (R3-004, C-15) : « Garder ce rythme » part du
  pas réel — R provisoire = moyenne plafonnée des jours évalués disponibles dès 5 (≤ 42 jours), sinon le palier ;
  `tenir.provisoire` reste vrai jusqu'à la fixation de R (14 jours évalués). Toast du geste : moins de 5 jours
  « Pas encore assez de jours pour mesurer ton rythme : je garde {R} pour l'instant. ».
- **« Aide-moi à prioriser »** (`priorites.json`, R3-006) : + `faites` (= `progression.faites`, `compte_du_jour`),
  `minutes_restantes` (estimations des tâches OUVERTES d'Essentiel et Prévu, hors Ce soir — la règle de
  `minutes_prevues` moins les faites), `deborde_minutes` = max(0, `minutes_restantes` − `disponible_minutes`)
  (capacité − rendez-vous, celle de la PROGRESSION), `geste_propose` (`"alleger"` ou `null`). Quand
  `deborde_minutes` > 0 : `lignes` = les tâches GARDÉES ouvertes (Essentiel, puis Prévu, puis Ce soir, chacune dans
  l'ordre de la journée), `raison` nulle, et `geste_propose` = `"alleger"` ; sinon `lignes` inchangées (non gardées)
  et `geste_propose` nul. `garder_n` reste N de Proposé (0 n'est pas « objectif atteint » : comparer `faites` à
  `objectif.nb`). Une requête de plus (l'historique de la capacité) : plafond 22 → 23.
- **« Où j'en suis ? »** (`point.json`, R3-006) : + `faites`, `minutes_restantes`, `deborde_minutes`, mêmes
  définitions que `priorites/` (et `faites` = `progression.faites`) ; aucune requête de plus.
- **Reporter une tâche à échéance aujourd'hui** (`tache_ecrite.json` `avertissements_possibles`, R3-002, C-13) :
  `taches/{id}/planifier/` vers un autre jour (ou sans jour) d'une tâche dont `echeance` = aujourd'hui sert
  `{"code":"echeance_aujourdhui","message":"L'échéance reste aujourd'hui."}` : la règle ne change pas, l'échéance la
  garde dans la journée (`aujourdhui/` la sert encore, ★ comprise) ; « Repousser l'échéance » = le PATCH `echeance`
  qui existe. Rien pour « Plus tard » (elle quitte la journée).
- **« Faites cette semaine »** (`faites_semaine.json`, nouveau, R3-003, C-16) : `GET taches/?periode=faites_semaine`
  garde la page paginée (`results` = ITEM, faites depuis lundi 0 h, la plus récente d'abord) et ajoute, sur chaque
  page, `total` (LA somme de la Revue et de l'Agenda : `faites_par_jour` du lundi à aujourd'hui) et
  `activites_closes` `[{"jour","titre"}]` (les activités ERP closes par lui cette semaine, comptées dans `total`,
  la plus récente d'abord). `results` ne liste que ce que `total` compte : sans routines ni sous-tâches (comme
  `compte_du_jour`). Recherche, Revue et Agenda disent le même nombre.
- **Constat des projets** (`projets_liste.json` `constat`, R3-010) : `{actifs, avances_7j}` ne compte que les projets
  actifs créés il y a 7 jours ou plus (« 0 a avancé ces 7 jours » une minute après leur création était faux) ;
  aucun → `constat: null` (la phrase est omise).
- **Réordonner dans Aujourd'hui** (R3-007) : `taches/{id}/reordonner/` `liste:"jour"` d'une tâche gardée aujourd'hui
  (`jour_prevu` = J OU `echeance` = J) range dans la liste de la JOURNÉE — toute tâche ouverte gardée aujourd'hui est
  une voisine permise ; les autres jours gardent la liste du même `jour_prevu`.
- **La ★ de la fiche** (couture L7) : `GET taches/{id}/` et la TACHE_ECRITE de toute écriture servent `essentielle` et
  `prevue_au_plan` lus du plan du jour (`serializers.saisie.calculs_du_plan` → `selectors.journee.
  lignes_de_taches_du_jour`, UNE requête de plus) — la MÊME source que la journée (`aujourdhui/`) et la vue d'un projet ;
  avant, ces deux champs valaient toujours `false` et la ★ changeait d'avis à l'ouverture de la fiche. `GET taches/`
  (listes) garde ses défauts (§ Révision 3.2). Plafond de la fiche déclaré : `test_plafonds.py::test_fiche_d_une_tache`,
  `docs/query-budgets.yml` (16, estimé : la CI tranche).
- **Derniers gestes** (`gestes.json`, R3-008) : `GET gestes/` ne liste plus que les gestes sur des tâches ou des
  projets — ni réglage du rythme (`rythme`), ni préférence (« Noté : … »), ni réponse à une carte (geste `decision`
  qui touche une `incitation_coach` : il reste annulable par son toast). Un geste ★ porte son `titre` (« Essentielle
  · Devis Benali », « Plus essentielle · … ») ; une revue qui met en pause : « Revue : {projet} en pause ».


## Révision 3.2 — raccord F2 (serveur), ce que le serveur sert réellement

Écrit par la lane de raccord serveur après le pli des huit lanes ; l'annexe A est régénérée depuis les échantillons.

- **Compte neuf** : `POST rythme/` et `PATCH reglages/` créent la `ReglagesRythme` au premier geste qui l'écrit (plus de
  404) ; un corps refusé ne crée rien ; une lecture (`vu/`, `aujourdhui/`, `rythme/`, `reglages/`) n'en crée jamais.
- **TACHE_ECRITE.progression** : toujours la PROGRESSION d'`aujourdhui/` du jour courant (jamais `null`) ;
  `tache_ecrite.json`, `lier_activite.json`.
- **ITEM de `projets/{id}/vue/` et `revue/projets/`** : `explication`, `essentielle`, `prevue_au_plan` calculés comme
  dans la journée (+1 requête). `GET taches/` (listes) garde les défauts (`""`, `false`) : le calcul y coûterait 5
  requêtes de plus pour un plafond de 12.
- **`projet_vue.json`** : chaque étape porte `compteurs` `{ouvertes, faites}` (de TOUTES ses tâches) ; nouvelle clé
  `sans_section_compteurs`. « Faites (n) » : `GET taches/?projet={id}&statut=fait&tri=fait_le` (paginé, la plus récente
  d'abord).
- **`GET taches/`** : `vue` ∈ `boite`, `quelque_jour` · `periode` ∈ `aujourdhui`, `semaine` (J à J+6), `retard`
  (`jour_prevu` < J ou `echeance` < J), `faites_semaine` (R2-124, « Faites cette semaine » de la Recherche : les
  FAITES dont `fait_le` ≥ lundi 0 h de la semaine de J — statut `fait` imposé, tri `fait_le` par défaut, la plus
  récente d'abord ; mêmes filtres de société et de propriétaire que toute liste ; valeur acceptée aussi dans les
  `filtres` d'une vue) · `tri` ∈ `rang` (défaut), `echeance`, `priorite`, `fait_le` · `groupe` ∈
  `projet` · `statut` ∈ valeurs de `StatutTache` (sans lui : ouvertes ; `inclure_faites=1` : + faites) · toute autre
  valeur → 400 « Valeur inconnue. ».
- **Réordonner — deux sens, à ne pas confondre** : `taches/{id}/reordonner/` et `checklist/{id}/reordonner/` : `avant_id`
  = le voisin qui PRÉCÈDE, `apres_id` = le voisin qui SUIT (`liste` ∈ `jour`, `projet`). `projets/{id}/reordonner/` et
  `sections/{id}/reordonner/` : l'élément se place JUSTE AVANT `avant_id` ou JUSTE APRÈS `apres_id` (« Mettre en haut »
  = `{"avant_id": <le premier>}`).
- **Projets** : `GET projets/` sans `statut` = actifs + en pause ; `statut=archive` = terminés ET archivés ·
  `planification/` `actions[].quand` ∈ `aujourdhui`, `demain`, `plus_tard`, `""` (les deux derniers : sans jour) ·
  `terminer/` `taches_ouvertes` ∈ `boite`, `annuler`, `deplacer` (+ `projet_cible_id`).
- **`decaler/`** : lignes titrées ; le 400 rend l'aperçu (§4).
- **Aperçu de collage** (`saisie_apercu.json`) : chaque ligne porte `deja_faite` (cochée « ✓ » à l'origine) et
  `doublon_projet` (nom du projet de la tâche doublon, par `nom_pour` ; `null` sans projet ou sans doublon). « En faire
  des sous-tâches » : `saisie-rapide/` création `{"lignes":[…],"parent_id":20}` (parent vérifié par propriétaire, un
  niveau ; 404 sinon).
  R4-26 — chaque projet NOUVEAU (`projets_nouveaux[]`, et `projets_communs[]` quand `nouveau`) porte `ressemble_a` :
  `{"id","nom"}` du projet OUVERT (actif ou en pause) dont le nom est proche — tous les mots de l'un dans l'autre,
  accents, casse, ponctuation et petits mots ignorés, au moins deux mots communs, le plus de mots communs l'emporte,
  égalité : aucun — sinon `null` (clé toujours présente). Rien n'est fusionné : l'écran propose « Utiliser ».
- **`agenda.json`** : clé `capacite` `{minutes, source}` (la capacité du jour, « {h} pour {cap} »).
- **Carte du moment** : `retour` porte `donnees.ids` (les tâches qui attendaient, lues par « Les remettre dans
  Proposé ») ; `revelation` servie par `aujourdhui/` (la plus récente ouverte, dernière de l'ordre, un bouton « OK »).
- **« Ailleurs dans l'ERP »** (`ailleurs.json`) : `mentions` lues par `notifications.selectors.mentions_non_lues` (clé
  omise si la source échoue) ; `approbations` ABSENTE (aucune porte publique) ; famille d'obligation `pose` absente
  (`reporting.calendar.evenements_assignes` n'existe pas) — les échantillons montrent une `intervention` au titre de l'ERP.
- **Activités closes** : `progression.activites_closes` et `detail.activites_closes` comptent les activités ERP closes
  par le compte ce jour (`records.selectors.activites_closes_par`), moins celles qui portent une tâche (+1 requête sur
  `aujourdhui/`, mesure du §10 à refaire).
- **`lier-activite/`** : toute activité OUVERTE du compte, sans échéance ou reportée comprises
  (`records.selectors.activite_ouverte_de`) ; la tâche née porte `lien_libelle` dès la liaison.
- **Annuler une conversion** (`gestes/{id}/annuler/`, type `conversion`) : rouvre l'à-faire source
  (`records.services.rouvrir_a_faire_personnel`) ; un refus de `records` va dans `conflits` (`objet` = `activite`).
- **Nuit** (§9) : `taches.nocturne` tourne pour toute société active au module actif, coupe-circuit compris (clôture,
  rythme, liens, purges) ; seul `taches.balayer` (envoi) obéit à `balayage_actif`.
- **RYTHME.tenir** (mode `tenir`) : `{"reference":5.0,"provisoire":false,"fixee_le":"2026-11-14","silence_jusquau":null}`
  (`null` hors de ce mode, comme dans `rythme.json`).
- **Textes servis** : `coach_entete.json` « Rythme : En faire plus · … » ; `bilan_semaine.texte` au gabarit de
  textes.md §4.6 ; raisons de Proposé selon textes.md §2.2 (« échéance jeu. 19 », « suite de Équipe ») et `explication`
  vide quand une `raison` est servie ; `erreurs.json` aligné (409 `deja_lie` « Cette activité a déjà sa tâche. »,
  `proposition_expiree` « Cette proposition a expiré. », `autre_compte`, `nom_pris` sans clé `nom`).
- **Plafonds** : `recherche/` `limite` 25 par défaut, 100 au plus ; `supprimees/` et `gestes/` 200 lignes au plus ;
  `taches/lot/` 200 ids au plus, raisons de refus `introuvable`, `sous_tache`, `close`.

## Révision 3.1

Boutons de rythme « Monter à 6 » · « Pas maintenant » ; « 1 sur 5 » ; `EtatRythme` sans `objectif_dit` (`palier` seule source) ; ce qui presse en entier au-delà de N, temps disponible en surcharge seulement ; `webcal://` → `https://` ; agenda externe 2 Mo, 10 s, cache 15 min.
