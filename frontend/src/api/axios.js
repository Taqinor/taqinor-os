import axios from 'axios'

// Par défaut : MÊME ORIGINE que la page (chemins relatifs via nginx) — l'app
// fonctionne ainsi depuis localhost ET depuis une adresse privée Tailscale
// sans rebuild. VITE_API_URL ne sert qu'à pointer ailleurs explicitement.
import { originFrom } from './origin'
// L53 (toast d'erreur global) + L57 (session expirée). Ces modules sont
// volontairement sans React : ils émettent un toast / un événement window.
import { errorMessageFrom, toastError } from '../lib/toast'
import { apiErrorMessageServi } from '../lib/apiError'
import { estEcritureExpiree, MESSAGE_ECRITURE_EXPIREE } from '../lib/apiError'
// NTADM26 — entité active (filtre d'affichage, module pur sans React ici).
import { lireEntiteActive } from '../lib/entiteActive'
import { emitSessionExpired, sessionEstActive } from '../providers/session-bridge'
import { noterEcritureRefusee } from '../providers/session-bridge'
// VX161 — refresh 401 partagé avec iaApi.js (une seule promesse en vol,
// jamais un POST /token/refresh/ par requête en échec).
import {
  MESSAGE_PANNE_REFRESH, estPanneDeRefresh, refreshSession, reprendreApresPanne,
} from './refreshCoordinator'
// YJPB1 — journal des problèmes VÉCUS par les utilisateurs (module pur,
// transport `fetch` : il n'utilise JAMAIS cette instance axios, donc
// aucune récursion possible par cet intercepteur).
import { signalerErreurRequete } from '../lib/journalProblemes'
// COP-D2 — tampon de diagnostic en mémoire (assistant, « Signaler un bug »).
import { noterRequete } from '../lib/tamponDiagnostic'

const ORIGIN = originFrom(import.meta.env.VITE_API_URL)

// VX55 — aucun timeout n'existait sur l'instance axios : sur une 3G qui cale,
// un écran gelait indéfiniment (aucune requête n'échouait jamais). 20 s laisse
// de la marge aux endpoints lents (export, PDF) tout en bornant l'attente.
const REQUEST_TIMEOUT_MS = 20000

const api = axios.create({
  baseURL: ORIGIN,
  withCredentials: true, // envoie les cookies httpOnly automatiquement
  timeout: REQUEST_TIMEOUT_MS,
})

// NTADM26 — listes sur lesquelles l'ENTITÉ ACTIVE de l'en-tête pose le filtre
// `?entite=` de NTADM2. Liste BLANCHE volontairement courte : les modèles que
// NTADM2 sait rattacher à une entité, et RIEN d'autre (jamais un paramètre
// posé au hasard sur une route qui l'ignorerait).
const ENDPOINTS_ENTITE = [
  /\/crm\/leads\/$/,
  /\/ventes\/devis\/$/,
  /\/ventes\/factures\/$/,
  /\/stock\/produits\/$/,
]

// COP-D2 — une ligne du tampon de diagnostic par réponse ET par erreur (4xx
// compris). Jamais de corps ; best-effort absolu, ne lève jamais.
function noterDansTampon(config, reponse) {
  try {
    const debut = config?._debutDiagnosticMs
    const code = reponse?.data?.code
    noterRequete({
      methode: config?.method,
      url: config?.url,
      statut: reponse?.status ?? 0,
      dureeMs: debut ? Date.now() - debut : 0,
      requestId: reponse?.headers?.['x-request-id'] || reponse?.data?.error?.request_id,
      code: typeof code === 'string' ? code : '',
    })
  } catch {
    // le tampon ne fait jamais planter une requête
  }
}

// ── Requete : prefixe /api/django uniquement ──────────────────
// Plus d'injection manuelle du token — le cookie est envoye automatiquement
api.interceptors.request.use((config) => {
  config._debutDiagnosticMs = Date.now()
  if (config.url && !config.url.startsWith('/api/')) {
    config.url = '/api/django' + config.url
  }
  // NTADM26 — filtre d'AFFICHAGE, jamais une garde : il ne fait que poser le
  // paramètre optionnel `?entite=` que le serveur applique en plus de son
  // propre scoping. Un appelant qui passe `entite` explicitement gagne
  // TOUJOURS (y compris `entite: ''` pour dire « toutes entités »).
  const methode = (config.method || 'get').toLowerCase()
  const chemin = (config.url || '').split('?')[0]
  if (methode === 'get' && ENDPOINTS_ENTITE.some((r) => r.test(chemin))
      && (config.params == null || config.params.entite === undefined)) {
    const active = lireEntiteActive()
    if (active) config.params = { ...(config.params || {}), entite: active }
  }
  return config
})

// ── Reponse : refresh silencieux sur 401 ──────────────────────
api.interceptors.response.use(
  (response) => {
    noterDansTampon(response.config, response)
    return response
  },
  async (error) => {
    const originalRequest = error.config || {}
    noterDansTampon(originalRequest, error.response)
    const isAuthEndpoint = originalRequest.url?.includes('/token/')
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !isAuthEndpoint
    ) {
      originalRequest._retry = true
      // Course pré-auth → post-auth (e2e auth.setup, run 34698649953 du
      // 12/09/2026) : un 401 PRÉ-connexion (les providers globaux de /login
      // tirent des endpoints authentifiés) déclenche ce refresh ; l'utilisateur
      // se connecte PENDANT qu'il est en vol ; l'échec 401 du refresh retombe
      // APRÈS le login réussi — et les gardes du bridge passent alors (plus sur
      // /login, session active) : la session NEUVE était « expirée » à tort.
      // On fige donc l'état de session AVANT le refresh : s'il a basculé
      // faux→vrai pendant le vol, ce refresh appartenait au monde d'avant — on
      // rejoue la requête avec les cookies frais au lieu d'expirer la session.
      const sessionAvantRefresh = sessionEstActive()
      try {
        // Le cookie refresh_token est envoye automatiquement par le navigateur.
        // VX161 — promesse de refresh PARTAGÉE (avec iaApi.js) : N 401
        // simultanés n'émettent qu'UN SEUL POST refresh.
        await refreshSession(ORIGIN)
        // Rejoue la requete originale — le nouveau cookie access_token est pris
        return api(originalRequest)
      } catch (errRefresh) {
        // ERR-JPB-REFRESH-MUET-SESSION-EXPIREE — coupure, délai ou 502 de
        // déploiement : la session n'est pas expirée pour autant. Une ligne de
        // journal, un réessai différé, et jamais la modale « reconnectez-vous ».
        if (estPanneDeRefresh(errRefresh) && sessionEstActive()) {
          signalerErreurRequete(errRefresh, { sessionEstActive })
          const silencieux = originalRequest.suppressErrorToast
          return reprendreApresPanne(ORIGIN, {
            rejouer: () => api(originalRequest),
            expirer: emitSessionExpired,
            signaler: (err) => {
              signalerErreurRequete(err, { sessionEstActive })
              if (!silencieux) toastError(MESSAGE_PANNE_REFRESH)
            },
          })
        }
        // Sinon : un vrai refus, la session est réellement expirée.
      }
      if (!sessionAvantRefresh && sessionEstActive()) {
        return api(originalRequest)
      }
      // L57 — Ré-authentification gracieuse EN PLACE (pas de rechargement dur,
      // l'état des formulaires ouverts est préservé). Le SessionProvider écoute
      // cet événement et affiche un modal de reconnexion. La redirection vers
      // /login reste un repli ultime si personne n'écoute (ex. avant montage).
      // NOTE : `emitSessionExpired` n'émet QUE si une session existait
      // réellement (`auth.isAuthenticated`, cf. session-bridge.js) — un 401 sur
      // une page publique n'est pas une expiration, et la modale ne doit pas
      // s'ouvrir par-dessus une vitrine (son overlay bloque tous les clics).
      noterEcritureRefusee(originalRequest.method)
      emitSessionExpired()
      return Promise.reject(error)
    }

    // YJPB1 — JOURNAL DES PROBLÈMES VÉCUS. Jusqu'ici, une requête sans
    // réponse (le délai de 20 s ci-dessus, réseau coupé) ou une 5xx ne
    // laissait AUCUNE trace côté serveur : seul le toast FR, dans le
    // navigateur de l'utilisateur. Posé AVANT la garde du toast, et donc
    // AUSSI pour les écrans qui gèrent l'erreur eux-mêmes
    // (`suppressErrorToast`) — l'incident Meryem du 02/11/2026 vivait
    // précisément derrière un état local « Indisponible pour le
    // moment. ». Best-effort absolu : ne lève jamais, n'attend rien.
    signalerErreurRequete(error, { sessionEstActive })

    // ACNC52 — une ÉCRITURE dont la réponse a expiré a peut-être abouti côté serveur
    // (gunicorn va au bout) : ne jamais inviter à rejouer. Texte unique (lib/apiError).
    if (estEcritureExpiree(error) && !originalRequest.suppressErrorToast) {
      toastError(MESSAGE_ECRITURE_EXPIREE)
      return Promise.reject(error)
    }

    // L53 — Bridge global : toute requête échouée surface un toast d'erreur FR,
    // sauf si l'appelant a explicitement opté pour la gestion locale
    // (`config.suppressErrorToast = true`) ou s'il s'agit d'une annulation.
    if (!originalRequest.suppressErrorToast && !axios.isCancel?.(error)) {
      // VX55 — un timeout (ECONNABORTED, `timeout: 20000` ci-dessus) est
      // distinct d'une annulation volontaire (AbortController, cf. thunks
      // {signal}) : celle-ci ne doit PAS toaster (l'écran a changé/démonté),
      // celui-là DOIT — l'utilisateur doit savoir que le réseau a calé.
      if (error.code === 'ECONNABORTED') {
        toastError('La connexion a expiré. Vérifiez votre connexion et réessayez.')
        return Promise.reject(error)
      }
      const status = error.response?.status
      // On NE toaste PAS les 401 (gérés ci-dessus) ni les 404 (souvent attendus,
      // ex. recherche/feature parquée) — ils restent gérés localement.
      // ERR-AGNR40-IDEMPOTENCE-EN-VOL — un 409 « idempotency_en_cours » n'est
      // pas une erreur : l'écran réessaie seul avec la même clé.
      const enCours = status === 409 && error.response?.data?.code === 'idempotency_en_cours'
      if (status !== 401 && status !== 404 && !enCours) {
        // ADEV112 — corps en Blob (`responseType: 'blob'`) ou `{erreurs: …}` : le
        // toast dit le message SERVI, jamais le générique « Une erreur est survenue. ».
        const corps = error.response?.data
        if ((typeof Blob !== 'undefined' && corps instanceof Blob) || corps?.erreurs) {
          return apiErrorMessageServi(error).then((m) => { toastError(m); return Promise.reject(error) })
        }
        toastError(errorMessageFrom(error))
      }
    }
    return Promise.reject(error)
  }
)

export default api
