/* SPL293 — fragment sorties et exports de calepinageApi.js (move only). */
import api from '../axios'
import { pivot } from './_base'

export const sorties = {
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
    // ACAL204/205 — corriger (PATCH, le MÊME relevé) ou retirer (DELETE) un
    // relevé de saisie ; GET releve/ rend aussi `releve_courant_id`.
    corrigerReleve: (id, releveId, corps) => api.patch(`${pivot(id)}releve/${releveId}/`, corps),
    supprimerReleve: (id, releveId) => api.delete(`${pivot(id)}releve/${releveId}/`),

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
}
