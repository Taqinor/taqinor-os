import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   CAL33 — Client API du module Calepinage autonome (`apps/calepinage`).
   ----------------------------------------------------------------------------
   ARC44 — factory CRUD partagée (`api/resource.js`), JAMAIS un `axios.get`
   direct dans `features/calepinage/`.

   **LA VÉRITÉ EST LE SERVEUR, PAS CE FICHIER.**
   Un autre client d'API du dépôt a longtemps prétendu « publier le contrat que
   le backend enregistre ensuite » : construites en parallèle, les deux lanes
   ont divergé et neuf chemins appelés n'existaient sous AUCUNE route (404
   constatée en production le 03/08/2026). Ce fichier-ci ne rejoue
   pas cette faute : chaque chemin ci-dessous est RECOPIÉ d'une source écrite
   AVANT lui, et son test jumeau (`calepinageApi.test.mjs`) le relit à cette
   source — jamais à une supposition.

   LES DEUX SOURCES, DANS CET ORDRE :
     1. `backend/django_core/apps/calepinage/contract_samples/*.json` (PACT10) —
        la clé `endpoint` de chaque échantillon porte le verbe + le chemin EXACT
        tel qu'il sera enregistré. Ces fichiers ont atterri SEULS sur `main`
        avant toute lane productrice, précisément pour que les deux moitiés du
        contrat ne l'inventent pas chacune de son côté.
     2. `docs/PLAN2.md`, Groupe CAL — pour les actions dont l'agrégat n'a pas
        (encore) d'échantillon : le chemin y est écrit dans le texte de la tâche
        qui l'expose (CAL18 `layout`, CAL19 `roof-image`, CAL20 `versions` +
        `restaurer`, CAL21 `variantes` + `retenir`, CAL23 `moteur/resultat`,
        CAL24 `generer-devis`, CAL25 `sync-devis`, CAL231 `design-context`,
        CAL45 `parametres`).

   UNE SEULE FORME D'URL (décision de structure n°3 du Groupe CAL, et règle n°1
   du README des échantillons) : `/api/django/calepinage/calepinages/<pk>/…`,
   routeur DRF + sous-ressources en `@action` ; les réglages société vivent sous
   `/api/django/calepinage/parametres/`. Aucun autre préfixe n'est servi.

   ÉTAT DU SERVEUR AU MOMENT DE CETTE LANE (à dire, jamais à cacher) :
   `apps/calepinage/` ne porte encore QUE `contract_samples/` — ni `urls.py`, ni
   `views/`. Les routes ci-dessous sont construites en parallèle par les lanes
   backend (CAL4 monte le préfixe, CAL16/CAL17 le CRUD, CAL18-CAL25 les
   actions). C'est exactement la situation que PACT10 organise : le contrat est
   déjà là, les deux moitiés branchent dessus. Tant que `apps/calepinage/urls.py`
   n'existe pas, `scripts/check_api_contract.py` signale ces chemins comme sans
   route serveur — c'est un état TRANSITOIRE attendu, et le test jumeau le dit
   explicitement plutôt que de le masquer.

   AUCUN APPEL RÉSEAU À L'IMPORT : ce module ne fait que DÉCLARER des fonctions.
   ========================================================================== */

// Fabrique CRUD standard sur `/calepinage/<ressource>/`.
const crud = makeResourceFactory(api, '/calepinage')

// Racine du pivot. Écrite UNE fois : toute action ci-dessous s'y accroche, ce
// qui rend une seconde forme d'URL mécaniquement impossible.
const pivot = (id) => `/calepinage/calepinages/${id}/`

// CALX37 — corps du POST de duplication d'une variante : `nom` saisi prime ;
// sans lui, un nom dérivé de la source évite un POST refusé pour nom vide.
// Fonction PURE (aucun appel réseau) : la garde CAL33 exige que chaque
// `api.<verbe>(` soit le corps direct d'une fonction fléchée.
function corpsDeCopieVariante(source, nom) {
  const src = source ?? {}
  const nomFinal = nom || (src.nom ? `${src.nom} (copie)` : 'Copie de variante')
  return { nom: nomFinal, roof_layout: src.roof_layout, resultat: src.resultat }
}

const calepinageApi = {
  /* ── Le calepinage lui-même (CAL16 liste + création, CAL17 détail agrégé) ──
     Les filtres de liste sont ceux RÉELLEMENT servis par CAL16 : `lead`,
     `client`, `statut`, `depuis`, `q`. La leçon PV22 est qu'un filtre ignoré
     par le serveur fait ouvrir le mauvais objet — on n'en invente donc aucun
     autre ici. */
  calepinages: {
    ...crud('calepinages'),

    // CAL199/CAL246 — les calepinages marqués MODÈLE de la société (drapeau
    // `records.Tag`, jamais un champ propre). Lecture pure.
    modeles: () => api.get('/calepinage/calepinages/modeles/'),

    // CAL18 — le document `roof_layout` (contrat v2 : CAL232,
    // `contract_samples/roof_layout_v2.schema.json`). GET relit, POST
    // enregistre ; le serveur ne touche que `roof_layout`/`layout_hash` et ne
    // change AUCUN statut.
    layout: (id) => api.get(`${pivot(id)}layout/`),
    enregistrerLayoutCalepinage: (id, corps) => api.post(`${pivot(id)}layout/`, corps),

    // CAL19 — l'image d'aperçu de toiture, stockée par le MÊME chemin que les
    // ventes (MinIO + URL présignée) ; aucun second chemin de stockage.
    // `corps` est un FormData : on laisse axios poser sa frontière multipart.
    envoyerImage: (id, corps) => api.post(`${pivot(id)}roof-image/`, corps),

    // CAL52 — les photos de site (drone/oblique/sol), MÊME magasin que
    // `roof-image`. `corps` est un FormData (photo, genre, prise_le, legende).
    photos: (id) => api.get(`${pivot(id)}photos/`),
    ajouterPhoto: (id, corps) => api.post(`${pivot(id)}photos/`, corps),
    // CAL53 — le calage (4 coins [latitude, longitude]) d'UNE photo de site,
    // rechargé tel quel à la réouverture. `null` efface le calage.
    calerPhoto: (id, photoId, coins) =>
      api.patch(`${pivot(id)}photos/${photoId}/calage/`,
        { calage: coins ? { coins } : null }),

    // CAL20 — historique. La restauration REJOUE une version en en créant une
    // NOUVELLE : jamais une réécriture, jamais une suppression d'historique.
    versions: (id) => api.get(`${pivot(id)}versions/`),
    restaurerVersion: (id, versionId) =>
      api.post(`${pivot(id)}versions/${versionId}/restaurer/`),

    // CAL21 — variantes. `retenir` est une ACTION (elle dé-retient la
    // précédente), jamais un PATCH de ressource — même patron qu'AO.
    variantes: (id) => api.get(`${pivot(id)}variantes/`),
    retenirVariante: (id, varianteId) =>
      api.post(`${pivot(id)}variantes/${varianteId}/retenir/`),

    // CALX37 — créer une variante (`services.creer_variante`, déjà servi par
    // `POST variantes/`) : `corps` porte `nom`/`roof_layout`/`resultat`, un nom
    // vide est refusé CÔTÉ ÉCRAN avant tout appel (la garde serveur existe
    // aussi, elle n'est jamais la seule).
    creerVariante: (id, corps) => api.post(`${pivot(id)}variantes/`, corps),

    // CALX37 — dupliquer : AUCUNE action serveur dédiée n'existe, c'est un
    // geste d'écran qui relit le détail complet de la source (`roof_layout`/
    // `resultat`, que le comparatif ne publie pas) puis crée une variante
    // neuve avec ce contenu. `nom` (saisi par l'utilisateur) prime ; sans lui,
    // un nom dérivé de la source évite un POST refusé pour nom vide.
    dupliquerVariante: (id, varianteId, nom) =>
      api.get(`${pivot(id)}variantes/${varianteId}/`)
        .then((res) => api.post(`${pivot(id)}variantes/`, corpsDeCopieVariante(res?.data, nom))),

    // CAL21 — comparatif des variantes, conforme à
    // `contract_samples/variantes_comparer.json`. Les ÉCARTS viennent du
    // serveur : un écran ne les recalcule jamais.
    comparer: (id) => api.get(`${pivot(id)}comparer/`),

    // CAL243 — les équipements RETENUS et leur complétude de fiche
    // (`contract_samples/calepinage_equipements.json`). Lecture PURE : aucune
    // clé de prix d'achat ni de marge n'y transite (gardé par CAL122).
    equipements: (id) => api.get(`${pivot(id)}equipements/`),

    // CAL92/93 — le profil d'horizon PVGIS du site (`printhorizon`),
    // contrat `contract_samples/calepinage_horizon.json`. Lecture PURE :
    // n'enregistre rien — `HorizonPanel.jsx` persiste ensuite le profil
    // choisi via `layout`/`enregistrerLayoutCalepinage` (CAL18).
    horizon: (id) => api.get(`${pivot(id)}horizon/`),

    // CAL159 — le dimensionnement du pompage (puits, besoin, réservoir,
    // courbe + point de fonctionnement, 12 volumes mensuels, pompe/variateur),
    // contrat `contract_samples/calepinage_pompage.json`. POST parce que
    // l'entrée est une SAISIE ; le serveur n'écrit RIEN.
    pompage: (id, corps) => api.post(`${pivot(id)}pompage/`, corps),

    // CAL244 — le résultat retenu du calepinage
    // (`contract_samples/calepinage_resultat.json`).
    resultat: (id) => api.get(`${pivot(id)}resultat/`),

    /* CAL125 — l'ENTRÉE du calcul électrique. Le matériel est DÉSIGNÉ et les
       longueurs/températures sont SAISIES ; la réponse est le `resultat`
       recalculé. CAL234 y fait voyager `affectation_manuelle` : c'est LÀ, et
       là seulement, qu'une affectation faite à la main est ENREGISTRÉE. */
    enregistrerEntreeElectrique: (id, corps) =>
      api.post(`${pivot(id)}entree-electrique/`, corps),

    /* CAL128 — le VERDICT à chaud, sans rien persister (garde en lecture).
       CAL234 : l'atelier y envoie l'affectation PROPOSÉE sous la MÊME clé
       `affectation_manuelle`, et lit les bloquants NOMMÉS (contrainte, pan,
       chaîne) avant de décider d'enregistrer. */
    evaluerElectrique: (id, corps) =>
      api.post(`${pivot(id)}evaluer-electrique/`, corps),

    // CAL195 — le schéma unifilaire du calepinage, en SVG inline. Le SVG est
    // composé PAR LE SERVEUR (même moteur que le devis, `core.electrique`) :
    // l'écran l'affiche, il ne dessine rien. `svg: null` + `bloquants` quand
    // la conception ne permet pas de dessiner — jamais un schéma approximatif.
    schemaUnifilaire: (id) => api.get(`${pivot(id)}schema-unifilaire/`),

    // CAL247 — les dossiers réglementaires
    // (`contract_samples/dossiers_reglementaires.json`).
    dossiersReglementaires: (id) => api.get(`${pivot(id)}dossiers-reglementaires/`),

    // CAL231 — le contexte de conception (pin/contour/ville résolus par le
    // serveur, CAL15) : toutes les clés toujours présentes, nulles si la source
    // manque. Aucune coordonnée devinée côté écran.
    designContext: (id) => api.get(`${pivot(id)}design-context/`),

    // SOLMVP15 — `importer-contour-ao` (CAL240) vivait ici. L'endpoint est
    // parti avec l'app d'appels d'offres, qui sort du produit : il n'y a plus
    // d'affaire dont reprendre le contour. Le contour de l'atelier reste
    // `roof_layout.outline` (v2), posé par le tracé sur carte.

    // CAL24/CAL25 — le devis. Le chemin canonique de création vit dans
    // `apps/ventes/services` et n'est pas doublé : ces deux actions l'appellent.
    // RÈGLE #4 : aucune ligne de devis n'est fabriquée ici, aucun PDF n'est
    // produit, aucun statut n'est écrit par l'écran.
    genererDevis: (id, corps) => api.post(`${pivot(id)}generer-devis/`, corps),
    syncDevis: (id, corps) => api.post(`${pivot(id)}sync-devis/`, corps),

    /* CALX27 — la levée du VERROU (CAL207, `views/verrou.py`). L'action
       existait, testée, et n'avait aucun consommateur : l'atelier affichait un
       bandeau « lecture seule » sans aucune sortie. Elle ne touche AUCUN
       statut de devis (règle #4) ; le serveur la trace au journal et rend
       `{calepinage, verrouille, deverrouille}`. Gardée par `calepinage_gerer`
       côté serveur — l'écran cache l'affordance avec le MÊME code. */
    deverrouiller: (id) => api.post(`${pivot(id)}deverrouiller/`, {}),

    // CALX19 — l'INVENTAIRE des sorties d'un calepinage (planche, plans, note
    // de calcul, DXF, tableurs, pack technique), contrat
    // `contract_samples/calepinage_sorties.json`. Lecture PURE : ne produit
    // aucun document, dit seulement ce qui existe et pourquoi une sortie
    // manque quand elle manque.
    sorties: (id) => api.get(`${pivot(id)}sorties/`),
    // CALX19 — le téléchargement GÉNÉRIQUE d'UNE sortie de cet inventaire :
    // `endpoint` vient TOUJOURS de l'entrée servie par `sorties()` ci-dessus
    // (déjà préfixée `/api/django/…`, l'intercepteur d'`api/axios.js` ne la
    // préfixe pas deux fois) — jamais un chemin reconstruit à la main ici.
    // `params` porte `?feuille=` pour le tableur CSV (CALX23), vide ailleurs.
    telechargerSortie: (endpoint, params) =>
      api.get(endpoint, { responseType: 'blob', params }),

    // CALX24 — compose le dossier technique (planche + note de calcul
    // fusionnées) et le DÉPOSE dans la GED : en ÉCRITURE (POST), gardée par
    // `calepinage_gerer` côté serveur. Réponse JSON normale (jamais un blob) :
    // `{document, nom, pieces, pages_attendues, signalements}`. Aucun import
    // `apps.ged` ici — l'écran ne parle qu'à CETTE action.
    composerPackTechnique: (id) => api.post(`${pivot(id)}pack-technique/`),

    // CALX28 — export/import du DOCUMENT de conception (`roof_layout`,
    // schéma v2 — `views/io_layout.py`, CAL216). `exporterConception` rend
    // `{roof_layout, layout_hash, schema_version}` TEL QUEL ; `importerConception`
    // VALIDE STRICTEMENT côté serveur avant écriture, et refuse en NOMMANT le
    // CHEMIN JSON du premier champ fautif (`champ`) — jamais une validation
    // recalculée ici. Distinct de `layout()`/`enregistrerLayoutCalepinage`
    // (CAL18, l'ATELIER) : ce sont les portes ÉCHANGE / round-trip fichier.
    exporterConception: (id) => api.get(`${pivot(id)}export-layout/`),
    importerConception: (id, document) => api.post(`${pivot(id)}import-layout/`, document),

    // CALX18 — les postes de pertes (catalogue CAL139, `views/simulation.py`) :
    // lecture pure du catalogue + des postes persistés, et leur enregistrement.
    pertes: (id) => api.get(`${pivot(id)}pertes/`),
    enregistrerPertes: (id, corps) => api.post(`${pivot(id)}enregistrer-pertes/`, corps),

    // CALX25 — le relevé terrain (chaînes de cotes, CAL64, `views/releve.py`).
    // GET rend l'historique (`releves`) ; POST enregistre une chaîne ET rend
    // le relevé créé PLUS l'historique à jour (contrat `calepinage_releve.json`).
    releve: (id) => api.get(`${pivot(id)}releve/`),
    enregistrerReleve: (id, corps) => api.post(`${pivot(id)}releve/`, corps),

    // CALX31 — le chatter GÉNÉRIQUE de la plateforme (`records`), hérité par
    // `CalepinageViewSet` via `ChatterViewSetMixin` (views/calepinages.py) :
    // AUCUNE seconde API de chatter, AUCUNE classe `…Activity` maison. GET
    // rend l'historique (créations + notes), POST ajoute une note manuelle
    // (auteur + société posés côté serveur).
    chatterHistorique: (id) => api.get(`${pivot(id)}chatter/historique/`),
    chatterNoter: (id, body) => api.post(`${pivot(id)}chatter/noter/`, { body }),

    /* APPEND-ONLY (D-CALX 13) : une méthode neuve s'ajoute ICI, EN FIN,
       avec son commentaire `// CALX<id>` — jamais au milieu, jamais triée. */

    // CALX17 — la masse posée et la feuille de lestage, telles que
    // `services/lestage.py` les compose (contrat
    // `contract_samples/calepinage_masse_lestage.json`). Lecture PURE ;
    // `module` désigne le produit dont le poids de fiche est lu, à défaut
    // le panneau du devis lié.
    masseLestage: (id, params) => api.get(`${pivot(id)}masse-lestage/`, { params }),

    // CALX39 — l'import d'un plan (DXF / PDF vectoriel) : le serveur ANALYSE
    // le fichier et rend ses calques, puis le contour du calque choisi (contrat
    // `contract_samples/calepinage_import_plan.json`). Il n'ÉCRIT RIEN : ni
    // `roof_layout`, ni document — l'enregistrement reste le geste de
    // l'utilisateur (`enregistrerLayoutCalepinage`). `corps` est un FormData
    // (`fichier`, et `calque` une fois choisi) : on laisse axios poser sa
    // frontière multipart.
    importerPlan: (id, corps) => api.post(`${pivot(id)}importer-plan/`, corps),

    /* ↓ APPEND-ONLY (décision D-CALX 13) : toute méthode neuve s'ajoute EN FIN
       de cet objet, avec son commentaire `// CALX<id>` — jamais au milieu,
       jamais de tri (deux lanes qui trient ce fichier, c'est le conflit de
       fusion garanti que la règle append-only évite). */

    // CALX40 — ouvre la génération d'un dossier réglementaire. Le corps
    // désigne `{dossier}` (un dossier déjà commencé) ou `{gabarit}` (le
    // gabarit déposé par la société). Un refus sort en 400 SOUS le champ
    // qu'il nomme (`gabarit`, `dossier`, ou le code de la pièce).
    genererDossier: (id, corps) => api.post(`${pivot(id)}generer-dossier/`, corps),

    // CALX41 — enregistre les champs à compléter d'un dossier réglementaire
    // (`{dossier|gabarit, champs: {code: valeur}}`). La réponse est l'agrégat
    // du contrat CAL247 RECOMPOSÉ : le panneau relit sa saisie sans second
    // appel. Un code hors du gabarit sort en 400 sous ce code-là.
    enregistrerChampsDossier: (id, corps) => api.post(`${pivot(id)}champs-dossier/`, corps),

    // CALX26 — l'archivage RÉVERSIBLE (CAL208, `views/archivage.py`) : la
    // corbeille plateforme `apps.trash`, jamais une suppression dure ni un
    // second modèle d'archive. `restaurer-corbeille` (et non `restaurer`,
    // pris par la restauration de VERSION, CAL20) sort de la corbeille.
    archiver: (id) => api.post(`${pivot(id)}archiver/`),
    restaurerCorbeille: (id) => api.post(`${pivot(id)}restaurer-corbeille/`),

    // CALX42 — le drapeau « modèle réutilisable » (`records.Tag`, CAL199 —
    // jamais un champ propre) et la création d'un calepinage NEUF depuis un
    // modèle. `creerDepuisModele` est une action de LISTE : elle ne vise
    // aucun calepinage existant, elle en fabrique un — `{modele, lead,
    // client, titre}`, le rattachement du modèle n'étant JAMAIS recopié.
    marquerModele: (id) => api.post(`${pivot(id)}marquer-modele/`),
    demarquerModele: (id) => api.post(`${pivot(id)}demarquer-modele/`),
    creerDepuisModele: (corps) =>
      api.post('/calepinage/calepinages/creer-depuis-modele/', corps),

    // CALX35 — la porte HTTP du service de copie qui existe depuis CAL14
    // (`services/variantes.py::dupliquer`), forme de réponse figée par
    // `contract_samples/calepinage_dupliquer.json`. `{avec_variantes}` est
    // EXPLICITE : absent, le serveur garde le comportement d'aujourd'hui.
    dupliquer: (id, corps) => api.post(`${pivot(id)}dupliquer/`, corps),

    // CALX47 — LA PORTE CRM du module : le calepinage OUVERT de ce lead, le
    // MÊME à chaque appel (le serveur est idempotent — un lead qui en a déjà
    // un reçoit celui-là, jamais un second). Le geste existant « Concevoir la
    // toiture (3D) » du rail CRM garde exactement sa sémantique : cette porte
    // vient À CÔTÉ de lui, elle ne le remplace pas.
    depuisLead: (leadId) =>
      api.post('/calepinage/calepinages/depuis-lead/', { lead: leadId }),

    // CALX6 — le TÉLÉCHARGEMENT d'une série de la simulation. La porte
    // existe depuis CAL144 (`views/export_csv.py`, `url_path='export-csv'`)
    // et n'avait AUCUN consommateur : `quoi` vaut `horaire`, `mensuel` ou
    // `ombrage` (`services/export_csv.py::EXPORTS`). La réponse est un
    // FICHIER (blob) ; quand la donnée manque, le serveur refuse en 400 et
    // NOMME le champ absent (`points`, `mensuel`, `shading12x24`) — l'écran
    // affiche ce motif-là sous le bouton, il n'en invente aucun.
    exportCsv: (id, quoi) =>
      api.get(`${pivot(id)}export-csv/`, { responseType: 'blob', params: { quoi } }),

    // CALX62 — le DÉPÔT d'une série météo horaire de la société, à la place
    // de PVGIS (`views/meteo_fichier.py`, contrat
    // `contract_samples/calepinage_meteo_fichier.json`). `corps` est un
    // FormData (`fichier` CSV + `fournisseur` SAISI) : on laisse axios poser
    // sa frontière multipart. La réponse 201 rend la PROVENANCE (`meteo`) et
    // le RÉSUMÉ de la série — jamais ses 8 760 points. Un refus 400 NOMME la
    // colonne fautive du fichier et, quand elle est connue, sa `ligne`.
    deposerMeteoFichier: (id, corps) =>
      api.post(`${pivot(id)}meteo-fichier/`, corps),

    // CALX5 — LANCER la simulation (`views/simulation.py`, contrat
    // `contract_samples/calepinage_simulation.json`). Deux réponses, jamais
    // une troisième : 202 `{job_id, kind, nature}` — le travail est parti en
    // tâche de fond, à suivre par `moteur.resultat(jobId)` (UN seul kind,
    // D-CALX 12) — ou 200 `{deja_calcule: true, calcule_le}` quand les
    // entrées n'ont pas bougé. `{ forcer: true }` relance quand même. Un
    // refus 400 NOMME le réglage ou le champ à corriger.
    simuler: (id, { forcer = false } = {}) =>
      api.post(`${pivot(id)}simuler/`, { forcer }),

    // CALX229 — le métré et la chute, TRONÇON PAR TRONÇON (contrat
    // `contract_samples/calepinage_troncons.json`, CALX203). ÉTAT DU SERVEUR
    // À L'ÉCRITURE DE CETTE LIGNE : la route n'existe pas encore — son
    // producteur est `services/troncons.py` (CALX224-226) et sa vue arrive
    // avec la suite de la vague ÉLECTRIQUE PRO ; l'échantillon est déclaré
    // `POSES_AVANT_LEUR_ROUTE` dans `tests/test_cal223_contrats.py`
    // (mécanisme PACT10 déjà posé). `CheminementCables.jsx` traite un 404 de
    // CETTE porte comme un état « pas encore calculable », jamais une panne.
    troncons: (id) => api.get(`${pivot(id)}troncons/`),

    // CALX244 — le POINT DE RACCORDEMENT réseau (contrat
    // `contract_samples/calepinage_raccordement.json`, CALX205), servi par
    // `views/raccordement.py`. UNE SEULE URL, deux méthodes : `GET` lit,
    // `POST` enregistre la saisie ET REND le raccordement recalculé —
    // l'écran n'enchaîne aucun second appel. Les deux réponses portent les
    // trois blocs `{saisie, calcul, verdicts}` et les CINQ verdicts, même
    // quand rien n'est saisi. Un refus 400 NOMME le champ fautif
    // (`source_limite`, `phases`… — les noms du bloc `saisie`, comme
    // `refus_limite_sans_source` du contrat) : une limite ou un cos φ sans
    // leur provenance n'entre jamais en base.
    raccordement: (id) => api.get(`${pivot(id)}raccordement/`),
    enregistrerRaccordement: (id, corps) =>
      api.post(`${pivot(id)}raccordement/`, corps),

    // CALX235 — le schéma unifilaire en DXF, pour qu'un bureau d'études le
    // reprenne (`views/schema.py`, `url_path='schema-unifilaire.dxf'` — le
    // point fait partie du chemin, comme `export.csv`). Le fichier est
    // transposé du MÊME dessin que le SVG : les deux ne peuvent pas
    // diverger. Réponse BLOB ; une conception incomplète ou bloquée ne
    // produit AUCUN fichier et le serveur refuse en 400 en NOMMANT le champ
    // en cause — l'écran affiche CE motif-là, il n'en invente aucun.
    sldDxf: (id) =>
      api.get(`${pivot(id)}schema-unifilaire.dxf/`, { responseType: 'blob' }),

    // CALX109 — les modules que la société peut RÉELLEMENT poser, avec les
    // cotes de leur fiche technique (`views/modules_disponibles.py`, contrat
    // `calepinage_modules_disponibles.json`). L'atelier 3D ne connaissait
    // qu'un module écrit en dur : cette lecture lui sert le catalogue, dans
    // la forme EXACTE du catalogue `modules[]` du document v2 (CALX82), donc
    // sans traduction de clés. Une fiche incomplète est LISTÉE avec son motif
    // et n'est pas sélectionnable ; une liste vide porte son propre motif —
    // l'écran affiche CEUX-LÀ, il n'en invente aucun.
    modulesDisponibles: (id) => api.get(`${pivot(id)}modules-disponibles/`),

    // CALX107 — le FICHIER du plan de fond : son URL servie (pré-signée, même
    // magasin que les photos de site) et sa taille en PIXELS NATURELS
    // (`views/plan_importe.py`, contrat `calepinage_plan_importe.json`).
    // L'atelier sait peindre le calque de fond mais ne parle jamais à Django :
    // c'est l'écran qui va chercher la pièce jointe que le document désigne
    // (`underlay.attachmentId`) et la lui redonne. Une taille illisible vaut
    // `null` avec son motif — l'écran affiche CELUI-LÀ, il n'invente aucune
    // étendue.
    planImporte: (id) => api.get(`${pivot(id)}plan-importe/`),

    // CALX302 — dépose une image PRODUITE PAR LE NAVIGATEUR (carte de
    // chaleur d'ombrage, diagramme de pertes, rendu 3D). `genre` : un des
    // trois admis (`ombrage`, `sankey`, `plan3d`), `fichier` : une data-URL
    // base64 (`documents/deposerImage.js` la produit depuis un Blob) — le
    // serveur refuse tout le reste en NOMMANT le champ fautif (jamais une
    // confiance au type déclaré par le navigateur).
    deposerImageDocument: (id, { genre, fichier }) =>
      api.post(`${pivot(id)}image-document/`, { genre, fichier }),

    // CALX320 — l'inventaire des NEUF documents du lot 6 (CALX291/321/322),
    // contrat `contract_samples/calepinage_documents.json`, DISTINCT de
    // `sorties()` ci-dessus : chaque pièce porte `manque[]` (le champ NOMMÉ
    // qui manque, jamais une phrase générique) et `versions[]` (l'historique
    // retrouvable, la plus récente d'abord). C'est CET inventaire que
    // `documents/PanneauDocuments.jsx` consomme désormais — lecture PURE,
    // même discipline que `sorties()`.
    documents: (id) => api.get(`${pivot(id)}documents/`),

    // CALX320 — le téléchargement GÉNÉRIQUE d'UN document de l'inventaire
    // `documents()` ci-dessus : MÊME geste que `telechargerSortie`
    // (`endpoint` vient TOUJOURS de l'entrée servie, jamais reconstruit),
    // nommé à part — un document du lot 6 n'est pas une sortie technique.
    telechargerDocument: (endpoint, params) =>
      api.get(endpoint, { responseType: 'blob', params }),

    // CALX320 — le diagramme de pertes SERVEUR, SVG autonome (CALX308,
    // `services/diagramme_pertes.py`, la MÊME cascade que la pièce
    // imprimable) — à RASTÉRISER dans CE navigateur avant de le déposer
    // comme image `sankey` (`deposerImageDocument` ci-dessus,
    // `documents/deposerImage.js::deposerDiagrammeDePertes`) : aucun
    // rasteriseur SVG n'est installé côté serveur (même limite que
    // `sorties/planche_png`, CAL175).
    diagrammePertesSvg: (id, params) =>
      api.get(`${pivot(id)}diagramme-pertes.svg/`, { responseType: 'blob', params }),

    // CALX342 — le COMPARATIF de 1 à 5 calepinages DISTINCTS (contrat
    // `contract_samples/calepinage_comparaison_projets.json`, CALX331 ; porte
    // `views/comparaison_projets.py`, CALX341). Action de LISTE : POST parce
    // que la liste d'identifiants voyage dans le corps — le serveur n'écrit
    // RIEN. Plus de 5 identifiants, ou aucun : 400 SOUS le champ `ids`.
    comparerProjets: (ids) =>
      api.post('/calepinage/calepinages/comparer-projets/', { ids }),
    // CALX342 — le MÊME comparatif en classeur (feuille « Comparatif ») : le
    // calepinage `id` ouvre le tableau, `autres` complètent (5 au total).
    // Réponse BLOB ; un refus 400 arrive lui aussi en Blob.
    comparatifXlsx: (id, autres = []) =>
      api.get(`${pivot(id)}comparatif.xlsx/`,
        { responseType: 'blob', params: autres.length ? { ids: autres.join(',') } : {} }),

    // CALX344 — les ÉTIQUETTES LIBRES du calepinage (contrat
    // `contract_samples/calepinage_etiquettes.json`, CALX332 ; porte
    // `views/etiquettes.py`, CALX343). UNE URL, trois méthodes, UNE forme :
    // chaque réponse est la liste À JOUR `{etiquettes: [{id, nom, couleur}]}`
    // — l'écran n'enchaîne aucun second appel. L'étiquette se CHOISIT dans le
    // vocabulaire de la société (`recordsApi.getTags`), elle ne se crée
    // jamais ici ; un refus 400 NOMME le champ (`tag_id`, `nom`). Le filtre de
    // liste passe par `list({ etiquette })` (identifiants joints par virgule).
    etiquettes: (id) => api.get(`${pivot(id)}etiquettes/`),
    poserEtiquette: (id, tagId) =>
      api.post(`${pivot(id)}etiquettes/`, { tag_id: tagId }),
    retirerEtiquette: (id, tagId) =>
      api.delete(`${pivot(id)}etiquettes/`, { data: { tag_id: tagId } }),
    // CALX352 — démarrer un calepinage depuis un MODÈLE et/ou un JEU DE
    // RÉGLAGES société (`views/bibliotheque.py::depuis_modele`, CALX351) :
    // `{modele_id?, lead_id|client_id|devis_id, titre?, preset_id?}` → le
    // DÉTAIL agrégé (contrat `calepinage_detail.json`). Un refus 400 NOMME
    // le champ du corps (`preset_id`, `modele_id`…) ; un modèle d'une autre
    // société est introuvable (404). Sans modèle ni jeu, l'écran de création
    // garde `create()` — la création d'aujourd'hui, inchangée.
    depuisModele: (corps) =>
      api.post('/calepinage/calepinages/depuis-modele/', corps),
  },

  /* ── Le moteur, porte HTTP NEUTRE (CAL22/CAL23) ──────────────────────────
     `calculer` rend soit le résultat, soit 202 `{job_id}` au-delà du seuil de
     coût (CAL23) ; `resultat(jobId)` suit alors le travail de fond. Une seule
     file, un seul `kind` — jamais une seconde. */
  moteur: {
    calculer: (corps) => api.post('/calepinage/moteur/calculer/', corps),
    // `pose` (contrat `pose.json`) : le relevé voyage sous `demande`, la
    // réponse porte la pose ET son régime de preuve.
    pose: (corps) => api.post('/calepinage/moteur/pose/', corps),
    resultat: (jobId) => api.get(`/calepinage/moteur/resultat/${jobId}/`),
  },

  /* ── Réglages société (CAL45) ────────────────────────────────────────────
     UN enregistrement par société, sections JSON. Singleton : pas de `<pk>`,
     GET pour lire, PUT pour écrire. À vide, le serveur garde le comportement
     actuel — aucune valeur par défaut n'est inventée côté écran. */
  parametres: {
    get: () => api.get('/calepinage/parametres/'),
    update: (corps) => api.put('/calepinage/parametres/', corps),

    // CALX29 — suggestion de pente par LiDAR IGN (France seule,
    // `services/lidar_ign.py`). GET est une LECTURE LOCALE : elle dit si le
    // service est offert à la société de l'appelant SANS émettre de requête
    // sortante, même quand il l'est — c'est elle qui commande l'affichage du
    // bouton. POST envoie le document de conception et reçoit une suggestion
    // par pan, jamais persistée côté serveur : c'est l'écran qui accepte ou
    // jette, puis enregistre via `enregistrerLayoutCalepinage` (CAL18).
    suggestionPenteDisponible: () => api.get('/calepinage/parametres/suggestion-pente/'),
    suggererPentesIGN: (roofLayout) =>
      api.post('/calepinage/parametres/suggestion-pente/', { roof_layout: roofLayout }),

    // CALX30 — les PROFILS TYPES de consommation de la société (CAL149,
    // `views/consommation.py`, servi sous le préfixe `parametres` parce
    // qu'aucun identifiant de calepinage n'y entre). Le GET sert les profils
    // SAISIS puis les replis ÉTIQUETÉS « hypothèse interne » ; le PUT
    // REMPLACE les profils saisis — un repli n'en est pas un, il n'est donc
    // jamais renvoyé comme une saisie.
    profilsTypes: () => api.get('/calepinage/parametres/profils-types/'),
    enregistrerProfilsTypes: (profils) =>
      api.put('/calepinage/parametres/profils-types/', { profils }),
  },
}

export default calepinageApi
