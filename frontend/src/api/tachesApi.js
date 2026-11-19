import apiErp from './axios'
import { errorMessageFrom, toastError } from '../lib/toast'
import { fetchAllPages } from '../utils/fetchAllPages'

/* ============================================================================
   TCH42 — Client d'API de l'app Tâches (`apps/taches`) : UNE fonction par route
   de `docs/taches/reference/api.md` §3 (106 couples méthode × chemin), plus les
   quatre lectures « toutes les pages » des listes paginées.

   Chemins : écrits en entier, SANS le préfixe `/api/django` (l'intercepteur
   d'`axios.js` le pose). Réponses : la réponse axios brute (`.data`), comme
   `outillageApi` ; aucune route ne renvoie un tableau nu (api.md §0).
   Contrats de réponse : `backend/django_core/apps/taches/contract_samples/*.json`.

   Quatre conventions de l'API prises en charge ici, une seule fois :
   - `Idempotency-Key` (« K » du tableau §3) : chaque écriture qui la porte en
     génère une, sauf si l'appelant en passe une (rejeu après coupure : même clé)
     ou `cle: null` (jamais d'en-tête) ;
   - `client_id` (« C ») : au corps, posé par l'appelant (un par tâche) ;
   - `proprietaire_attendu` : posé AUTOMATIQUEMENT au corps de `saisie-rapide/`,
     `planifier/` et `terminer/` quand `definirProprietaire(userId)` a été appelé
     (file hors ligne : une op d'un autre compte reçoit 409 `autre_compte`) ;
   - 409 distingués : `classerErreur(err)` rend le `code` (`conflit_version`,
     `nom_pris`, `proposition_expiree`, `autre_compte`, `deja_lie`, …), le
     `lock_version` à renvoyer et l'objet `actuel` du conflit de version.

   Auth : « S » = cookie JWT de l'ERP. Les trois routes « J » (capture, tuile,
   flux) n'acceptent QUE leur jeton d'usage : `capturer(corps, jeton)` et
   `lireTuile(jeton)` l'envoient en `Authorization: Bearer`, `lireFlux(jeton)` le
   porte dans l'URL.
   ========================================================================== */

// ── Conventions ───────────────────────────────────────────────────────────────

// ── Refus 409 nommés : dits par l'écran, jamais par le toast global (F2 acceptation) ──────────────────────────────
// Le pont global de l'ERP (`axios.js`, L53, hors de ce module) toaste tout rejet sauf 401/404 : un 409 que l'écran
// dit déjà (bandeau de conflit, erreur sous le champ) s'affichait deux fois. `api` ci-dessous enveloppe les 5 verbes
// de l'instance de l'ERP : pendant l'appel (synchrone : axios fusionne `defaults` dès l'appel), un 409 RÉSOUT
// (`validateStatus`), donc le pont ne le voit pas ; il est aussitôt rejeté ici avec la même forme d'erreur
// (`response`, `config`) que lisent `classerErreur`, la file hors ligne et les écrans. Nommé (`CODES_409`) ou
// `idempotency_en_cours` (que le pont ne toaste pas non plus) : silence ; tout autre 409 : le même toast que le pont.
// Un 400 que l'écran dit SOUS LE CHAMP (l'appelant passe `{ erreurSousLeChamp: true }` dans ses options : nom de
// projet refusé, agenda externe injoignable, phrase de saisie refusée) suit la même voie, sans aucun toast : le
// message ne se dit qu'une fois, là où il faut agir. Toute autre erreur (400 d'un appelant qui ne le dit pas, 5xx,
// délai, réseau) suit le pont exactement comme avant. Jamais `suppressErrorToast` (il tairait aussi les 5xx).
const garde409 = (statut) => (statut >= 200 && statut < 300) || statut === 409
const garde409Et400 = (statut) => garde409(statut) || statut === 400

function refusResolu(reponse, { toaster }) {
  const erreur = Object.assign(new Error(`Request failed with status code ${reponse.status}`), {
    name: 'AxiosError', code: 'ERR_BAD_REQUEST', isAxiosError: true, response: reponse, config: reponse.config,
  })
  if (toaster) toastError(errorMessageFrom(erreur))
  return erreur
}

const nomme409 = (reponse) => CODES_409.includes(reponse.data?.code) || reponse.data?.code === 'idempotency_en_cours'

function appeler(verbe, args) {
  const config = args[verbe === 'get' || verbe === 'delete' ? 1 : 2]
  const sousLeChamp = Boolean(config?.erreurSousLeChamp)
  const defauts = apiErp.defaults
  const regle = defauts?.validateStatus
  if (defauts) defauts.validateStatus = sousLeChamp ? garde409Et400 : garde409
  let promesse
  try {
    promesse = apiErp[verbe](...args)
  } finally {
    if (defauts) defauts.validateStatus = regle // l'instance de l'ERP retrouve sa règle dès l'appel parti
  }
  return Promise.resolve(promesse).then((reponse) => {
    if (reponse?.status === 409) throw refusResolu(reponse, { toaster: !nomme409(reponse) })
    if (reponse?.status === 400 && sousLeChamp) throw refusResolu(reponse, { toaster: false })
    return reponse
  })
}

const api = Object.fromEntries(['get', 'post', 'put', 'patch', 'delete'].map((verbe) => [verbe, (...args) => appeler(verbe, args)]))

let proprietaireAttendu = null

/** Pose le compte qui écrit (`proprietaire_attendu`). `null` : ne rien envoyer. */
export function definirProprietaire(userId) {
  proprietaireAttendu = Number.isInteger(userId) ? userId : null
}

/** Une clé d'idempotence neuve (UUID v4). */
export function nouvelleCle() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `k-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

/** F3 acceptation ERR 5 — une CRÉATION validée au doigt sur une carte du Copilote (`{ carteAssistant: true }`) :
 *  le serveur la range `source='assistant'` (A5). Jamais `X-Taqinor-Assistant`, qui masquerait la réponse. */
export const ENTETE_CARTE_ASSISTANT = 'X-Taqinor-Carte-Assistant'

/** `{ erreurSousLeChamp: true }` de l'appelant : son 400 ne passe pas par le toast global (voir `appeler`). */
const sousLeChamp = (options) => (options?.erreurSousLeChamp ? { erreurSousLeChamp: true } : undefined)

const avecCle = (options = {}) => {
  const { cle, carteAssistant } = options ?? {}
  const headers = {}
  if (cle !== null) headers['Idempotency-Key'] = cle || nouvelleCle()
  if (carteAssistant) headers[ENTETE_CARTE_ASSISTANT] = '1'
  const config = { ...(Object.keys(headers).length > 0 ? { headers } : {}), ...sousLeChamp(options) }
  return Object.keys(config).length > 0 ? config : undefined
}

const avecProprietaire = (corps, options = {}) => {
  const proprietaire = options.proprietaire === undefined ? proprietaireAttendu : options.proprietaire
  if (proprietaire == null || corps?.proprietaire_attendu !== undefined) return corps ?? {}
  return { ...(corps ?? {}), proprietaire_attendu: proprietaire }
}

const bearer = (jeton) => ({ headers: { Authorization: `Bearer ${jeton}` } })

/** Codes 409 portés par `erreurs.json` : jamais devinés sur le texte. */
export const CODES_409 = ['conflit_version', 'nom_pris', 'proposition_expiree', 'autre_compte', 'deja_lie', 'effacement_occupe']

/**
 * Classe une erreur axios en une forme unique :
 *   { statut, code, message, champs, lockVersion, actuel }
 * `code` ∈ CODES_409 pour un 409 reconnu, `'idempotency_en_cours'` (l'écran
 * réessaie seul avec la même clé), `'validation'` (400), `'introuvable'`,
 * `'limite'` (429), `'reseau'` (aucune réponse) ou `'autre'`. `champs` = le corps
 * d'un 400 (`{champ: [messages]}`, ou `{lignes: {n: {champ: […]}}}`).
 */
export function classerErreur(err) {
  const reponse = err?.response
  if (!reponse) return { statut: 0, code: 'reseau', message: '', champs: null, lockVersion: null, actuel: null }
  const { status: statut, data } = reponse
  const corps = data && typeof data === 'object' ? data : {}
  const message = typeof corps.detail === 'string' ? corps.detail : ''
  let code = 'autre'
  if (statut === 409) code = typeof corps.code === 'string' ? corps.code : 'conflit'
  else if (statut === 400) code = 'validation'
  else if (statut === 404) code = 'introuvable'
  else if (statut === 429) code = 'limite'
  return {
    statut,
    code,
    message,
    champs: statut === 400 ? corps : null,
    lockVersion: Number.isInteger(corps.lock_version) ? corps.lock_version : null,
    actuel: corps.actuel ?? null,
  }
}

/** Vrai pour le 409 `conflit_version` (bandeau « Garder la mienne · Prendre l'autre »). */
export const estConflitVersion = (err) => classerErreur(err).code === 'conflit_version'

/** Vrai pour le 409 `autre_compte` (op de la file jetée). */
export const estAutreCompte = (err) => classerErreur(err).code === 'autre_compte'

// ── 3.1 Journée, rituels, agenda ──────────────────────────────────────────────

export const lireAujourdhui = (params) => api.get('/taches/aujourdhui/', { params })
export const lireAilleurs = () => api.get('/taches/aujourdhui/ailleurs/')
export const lireBadge = () => api.get('/taches/badge/')
export const marquerVu = (corps) => api.post('/taches/vu/', corps ?? {})
export const proposerJournee = (params) => api.get('/taches/journee/proposition/', { params })
export const lirePriorites = (params) => api.get('/taches/journee/priorites/', { params })
export const lirePoint = () => api.get('/taches/journee/point/')
export const garderJournee = (corps, options) => api.post('/taches/journee/planifier/', corps, avecCle(options))
export const marquerEssentiel = (corps) => api.post('/taches/journee/essentiel/', corps)
export const alleger = (corps, options) => api.post('/taches/journee/alleger/', corps, avecCle(options))
export const lireCloture = (params) => api.get('/taches/journee/cloture/', { params })
export const cloturerJournee = (corps, options) => api.post('/taches/journee/cloturer/', corps, avecCle(options))
export const lireAgenda = (params) => api.get('/taches/agenda/', { params })
export const rechercher = (params) => api.get('/taches/recherche/', { params })

// ── 3.2 Saisie, À trier, tâches ───────────────────────────────────────────────

export const saisieRapide = (corps, options) =>
  api.post('/taches/saisie-rapide/', avecProprietaire(corps, options), avecCle(options))
export const capturer = (corps, jeton) => api.post('/taches/capture/', corps, bearer(jeton))
export const listerTaches = (params) => api.get('/taches/taches/', { params })
export const creerTache = (corps, options) => api.post('/taches/taches/', corps, avecCle(options))
export const lireTache = (id) => api.get(`/taches/taches/${id}/`)
export const modifierTache = (id, corps) => api.patch(`/taches/taches/${id}/`, corps)
export const supprimerTache = (id) => api.delete(`/taches/taches/${id}/`)
export const planifierTache = (id, corps, options) =>
  api.post(`/taches/taches/${id}/planifier/`, avecProprietaire(corps, options))
export const terminerTache = (id, corps, options) =>
  api.post(`/taches/taches/${id}/terminer/`, avecProprietaire(corps, options))
export const rouvrirTache = (id) => api.post(`/taches/taches/${id}/rouvrir/`, {})
export const trancherTache = (id, corps) => api.post(`/taches/taches/${id}/trancher/`, corps)
export const sauterTache = (id) => api.post(`/taches/taches/${id}/sauter/`, {})
export const attendreTache = (id, corps) => api.post(`/taches/taches/${id}/attendre/`, corps)
export const recevoirTache = (id) => api.post(`/taches/taches/${id}/recu/`, {})
export const reordonnerTache = (id, corps) => api.post(`/taches/taches/${id}/reordonner/`, corps)
export const restaurerTache = (id) => api.post(`/taches/taches/${id}/restaurer/`, {})
export const poserRappel = (id, corps) => api.post(`/taches/taches/${id}/rappels/`, corps)
export const apercuChangement = (id, corps) => api.post(`/taches/taches/${id}/changement/apercu/`, corps)
export const traiterLot = (corps, options) => api.post('/taches/taches/lot/', corps, avecCle(options))
export const lierActivite = (corps, options) => api.post('/taches/taches/lier-activite/', corps, avecCle(options))
export const convertirActivites = (corps) => api.post('/taches/convertir-activite/', corps)
export const retirerRappel = (id) => api.delete(`/taches/rappels/${id}/`)
export const repeterRappel = (id, corps) => api.post(`/taches/rappels/${id}/repeter/`, corps)
export const modifierRecurrence = (id, corps) => api.patch(`/taches/recurrences/${id}/`, corps)
export const ajouterPoint = (corps) => api.post('/taches/checklist/', corps)
export const modifierPoint = (id, corps) => api.patch(`/taches/checklist/${id}/`, corps)
export const retirerPoint = (id) => api.delete(`/taches/checklist/${id}/`)
export const reordonnerPoint = (id, corps) => api.post(`/taches/checklist/${id}/reordonner/`, corps)
export const listerEtiquettes = (params) => api.get('/taches/etiquettes/', { params })
export const creerEtiquette = (corps) => api.post('/taches/etiquettes/', corps)
export const modifierEtiquette = (id, corps) => api.patch(`/taches/etiquettes/${id}/`, corps)
export const supprimerEtiquette = (id) => api.delete(`/taches/etiquettes/${id}/`)
export const listerVues = () => api.get('/taches/vues/')
export const creerVue = (corps) => api.post('/taches/vues/', corps)
export const modifierVue = (id, corps) => api.patch(`/taches/vues/${id}/`, corps)
export const supprimerVue = (id) => api.delete(`/taches/vues/${id}/`)
export const listerSupprimees = () => api.get('/taches/supprimees/')
export const listerGestes = () => api.get('/taches/gestes/')
export const annulerGeste = (id) => api.post(`/taches/gestes/${id}/annuler/`, {})
export const listerSuggestions = () => api.get('/taches/suggestions/')
export const accepterSuggestion = (id, corps) => api.post(`/taches/suggestions/${id}/accepter/`, corps ?? {})
export const refuserSuggestion = (id) => api.post(`/taches/suggestions/${id}/refuser/`, {})

// ── 3.3 Projets, revue, modèles ───────────────────────────────────────────────

export const listerProjets = (params) => api.get('/taches/projets/', { params })
export const creerProjet = (corps, options) => api.post('/taches/projets/', corps, avecCle(options))
export const lireProjet = (id) => api.get(`/taches/projets/${id}/`)
export const modifierProjet = (id, corps, options) =>
  api.patch(`/taches/projets/${id}/`, corps, ...[sousLeChamp(options)].filter(Boolean))
export const supprimerProjet = (id) => api.delete(`/taches/projets/${id}/`)
export const reordonnerProjet = (id, corps) => api.post(`/taches/projets/${id}/reordonner/`, corps)
export const trierProjetsParPriorite = () => api.post('/taches/projets/trier-par-priorite/', {})
export const lireVueProjet = (id, params) => api.get(`/taches/projets/${id}/vue/`, { params })
export const apercuPlanification = (id, corps) => api.post(`/taches/projets/${id}/planification/apercu/`, corps)
export const planifierProjet = (id, corps, options) =>
  api.post(`/taches/projets/${id}/planification/`, corps, avecCle(options))
export const decalerProjet = (id, corps, options) => api.post(`/taches/projets/${id}/decaler/`, corps, avecCle(options))
export const terminerProjet = (id, corps, options) =>
  api.post(`/taches/projets/${id}/terminer/`, corps, ...[sousLeChamp(options)].filter(Boolean))
export const rouvrirProjet = (id) => api.post(`/taches/projets/${id}/rouvrir/`, {})
export const restaurerProjet = (id) => api.post(`/taches/projets/${id}/restaurer/`, {})
export const dupliquerProjet = (id, corps, options) =>
  api.post(`/taches/projets/${id}/dupliquer/`, corps, avecCle(options))
export const enregistrerModele = (id, corps, options) =>
  api.post(`/taches/projets/${id}/enregistrer-modele/`, corps, avecCle(options))
export const creerSection = (corps) => api.post('/taches/sections/', corps)
export const modifierSection = (id, corps) => api.patch(`/taches/sections/${id}/`, corps)
export const supprimerSection = (id) => api.delete(`/taches/sections/${id}/`)
export const reordonnerSection = (id, corps) => api.post(`/taches/sections/${id}/reordonner/`, corps)
export const listerModeles = (params) => api.get('/taches/modeles/', { params })
export const lireModele = (id) => api.get(`/taches/modeles/${id}/`)
export const renommerModele = (id, corps, options) =>
  api.patch(`/taches/modeles/${id}/`, corps, ...[sousLeChamp(options)].filter(Boolean))
export const supprimerModele = (id) => api.delete(`/taches/modeles/${id}/`)
export const instancierModele = (id, corps, options) =>
  api.post(`/taches/modeles/${id}/instancier/`, corps, avecCle(options))
export const lireRevue = (params) => api.get('/taches/revue/projets/', { params })
export const deciderRevue = (projetId, corps) => api.put(`/taches/revue/projets/${projetId}/`, corps)

// ── 3.4 Rythme, réglages, iPhone, données ─────────────────────────────────────

export const lireRythme = () => api.get('/taches/rythme/')
export const poserMode = (corps) => api.post('/taches/rythme/', corps)
export const repondreProposition = (id, corps) => api.post(`/taches/rythme/propositions/${id}/repondre/`, corps)
export const poserPreference = (corps) => api.post('/taches/preferences/', corps)
export const retirerPreference = (cle) => api.delete(`/taches/preferences/${encodeURIComponent(cle)}/`)
export const lireReglages = () => api.get('/taches/reglages/')
export const modifierReglages = (corps) => api.patch('/taches/reglages/', corps)
export const lireReglagesSociete = () => api.get('/taches/reglages-societe/')
export const modifierReglagesSociete = (corps) => api.patch('/taches/reglages-societe/', corps)
export const listerJetons = () => api.get('/taches/jetons/')
export const creerJeton = (corps) => api.post('/taches/jetons/', corps)
export const revoquerJeton = (id) => api.post(`/taches/jetons/${id}/revoquer/`, {})
export const testerNotification = () => api.post('/taches/mon-iphone/test-notification/', {})
export const lireTuile = (jeton) => api.get('/taches/tuile/', bearer(jeton))
export const lireFlux = (jeton) => api.get(`/taches/flux/${jeton}.ics`, { responseType: 'text' })
export const lireEnteteCoach = () => api.get('/taches/coach/entete/')
export const exporterMesDonnees = () => api.get('/taches/mes-donnees/')
export const toutEffacer = (corps) => api.post('/taches/tout-effacer/', corps)
export const listerAgendasExternes = () => api.get('/taches/agendas-externes/')
export const ajouterAgendaExterne = (corps, options) => api.post('/taches/agendas-externes/', corps, avecCle(options))
export const modifierAgendaExterne = (id, corps, options) =>
  api.patch(`/taches/agendas-externes/${id}/`, corps, ...[sousLeChamp(options)].filter(Boolean))
export const retirerAgendaExterne = (id) => api.delete(`/taches/agendas-externes/${id}/`)
export const rafraichirAgendaExterne = (id) => api.post(`/taches/agendas-externes/${id}/rafraichir/`, {})

// ── Listes paginées lues en entier (`StandardPagination`, 50 : api.md §0) ─────

const toutesLesPages = (lire, params) =>
  fetchAllPages((page, { page_size: pageSize } = {}) =>
    lire({ ...(params ?? {}), page, page_size: pageSize }).then((r) => r.data))
    .then((lignes) => (Array.isArray(lignes) ? lignes : (lignes?.results ?? [])))

export const listerToutesLesTaches = (params) => toutesLesPages(listerTaches, params)
export const listerTousLesProjets = (params) => toutesLesPages(listerProjets, params)
export const listerToutesLesEtiquettes = (params) => toutesLesPages(listerEtiquettes, params)
export const listerTousLesModeles = (params) => toutesLesPages(listerModeles, params)
