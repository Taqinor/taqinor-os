/* SPL295 — fragment projet et bibliotheque de calepinageApi.js (move only). */
import api from '../axios'
import { pivot } from './_base'

export const projet = {
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

    // CALX349 — la DÉCISION D'APPROBATION (second regard interne, CALX347) :
    // GET rend `{etat, decide_par, decide_le, motif, exigee}` (contrat
    // `contract_samples/calepinage_approbation.json`) ; POST décide
    // (`{decision: 'approuve'|'refuse', motif}`) et rend le MÊME état à jour
    // — l'écran n'enchaîne aucun second appel de lecture. Un refus 400 NOMME
    // son champ (`decision`, `motif`, ou une clé par suggestion automatique
    // encore en attente, ex. `buildings[0].hauteurM`).
    approbation: (id) => api.get(`${pivot(id)}approbation/`),
    decisionApprobation: (id, corps) => api.post(`${pivot(id)}approbation/`, corps),

    // CALX360 — la NOMENCLATURE DE FIXATION (CALX359, contrat
    // `contract_samples/calepinage_fixation_bom.json`) : `{systeme, lignes,
    // refus}`, lecture PURE. `params.systeme` désigne un système du
    // catalogue (borné société) ; à défaut, l'UNIQUE système actif de la
    // société est appliqué, ou `refus` dit pourquoi (catalogue vide,
    // plusieurs systèmes actifs sans choix).
    bomFixation: (id, params) => api.get(`${pivot(id)}bom-fixation/`, { params }),

    // CALX362 — le CATALOGUE des zones de vent/neige SAISIES par la société
    // (réglages CALX361, contrat `parametres_calepinage.json`, section
    // `lestage.zones`) : le panneau « Masse & lestage » le lit pour lister
    // les zones au CHOIX à côté de celle retenue par le calepinage
    // (`masseLestage`), et lier vers les réglages quand aucune zone n'est
    // saisie. MÊME lecture que `parametres.get()` (CAL45) — AUCUNE seconde
    // porte HTTP : exposée ici pour rester dans le groupe que le panneau
    // consomme déjà.
    zonesLestage: () => api.get('/calepinage/parametres/'),
    // CALX365 — la REPRISE de la visite technique validée (contrat
    // `contract_samples/calepinage_releve_visite.json`, CALX336 ; porte
    // `views/reprise_visite.py`, CALX364). GET et POST rendent la MÊME
    // forme : POST crée UN relevé de provenance `visite` (201) ou rend celui
    // déjà repris (200, `deja_repris`) ; sans visite validée, 400 SOUS le
    // champ `visite_id`, le motif du serveur tel quel.
    releveVisite: (id) => api.get(`${pivot(id)}releve-visite/`),
    // ACAL211 — `{remplacer: true}` (ACAL210, « Mettre à jour depuis la visite ») : met à jour EN
    // PLACE un relevé déjà repris ; sans corps, un relevé déjà repris n'est jamais touché.
    reprendreVisite: (id, corps) => api.post(`${pivot(id)}releve-visite/`, corps),
    // CALX367 — la POSE RÉELLE et ses écarts (contrat
    // `contract_samples/calepinage_asbuilt_ecarts.json`, CALX337 ; porte
    // `views/asbuilt.py`, CALX366). UNE URL, UNE forme en GET comme en POST :
    // POST `{pan, modules_poses, ecarts_position, releve_le}` saisit UN pan,
    // POST `{creer_version: true}` gèle une version des écarts. Un refus 400
    // NOMME le champ (`pan`, `modules_poses`, `releve_le`, `creer_version`).
    poseReelle: (id) => api.get(`${pivot(id)}pose-reelle/`),
    enregistrerPoseReelle: (id, corps) => api.post(`${pivot(id)}pose-reelle/`, corps),
    creerVersionPoseReelle: (id) => api.post(`${pivot(id)}pose-reelle/`, { creer_version: true }),

    // CALX371 — le PROJET COMPLET en JSON : téléchargement TEL QUEL du
    // document déjà servi (CALX312/CALX370, contrat
    // `contract_samples/export_projet.json`) et sa réimportation (`POST
    // calepinages/import-projet/`, contrat `calepinage_projet_json.json`,
    // porte `views/projet_json.py`). `apercu: true` ne fait qu'afficher ce
    // qui SERAIT écrit — le serveur n'écrit rien tant que l'écran ne
    // renvoie pas `apercu: false` en confirmation explicite.
    exporterProjet: (id) =>
      api.get(`${pivot(id)}export-projet.json/`, { responseType: 'blob' }),
    importerProjet: (corps) =>
      api.post('/calepinage/calepinages/import-projet/', corps),

    // CALX346 — le différentiel champ par champ entre deux versions (contrat
    // `contract_samples/calepinage_versions_diff.json`, CALX333 ; porte
    // `views/versions_diff.py`, CALX345). Sans `contreId`, la DROITE est
    // l'ÉTAT COURANT du calepinage (`id: null`) — jamais une seconde route.
    versionsDiff: (id, versionId, contreId) =>
      api.get(`${pivot(id)}versions/${versionId}/diff/`,
        { params: contreId ? { contre: contreId } : {} }),
}
