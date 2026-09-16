import crmApi from '../api/crmApi'

/* ============================================================================
   QJ-EQUIPE-3 (14-16/09/2026) — reconnaissance AUTOMATIQUE des appareils
   équipe. Avant ce lot, un appareil (téléphone de Reda/Meryem) ne devenait
   « équipe » qu'après un marquage MANUEL depuis l'écran Visiteurs — en
   attendant, ses propres ouvertures du lien client déclenchaient de fausses
   alertes « devis ouvert »/« multi-prospects ». Ici, tout navigateur connecté
   à l'ERP s'enregistre lui-même comme appareil équipe, une fois par 24 h
   (jamais à chaque montage), en best-effort (une erreur réseau ne doit
   JAMAIS bloquer ni bruiter l'UI).

   Fonctions PURES (testables sans DOM réel) + UNE fonction d'effet
   (`enregistrerNavigateurEquipe`) qui orchestre le tout. Le module ne pose
   JAMAIS lui-même de cookie — c'est la RÉPONSE du serveur qui pose
   `tq_appareil` sur le domaine partagé du site (jamais `tq_equipe`, signal
   non scopé société : l'exclusion vient du registre serveur, scopé société).
   On se contente de relire `tq_appareil` s'il existe déjà — sinon
   l'identifiant que le serveur nous a attribué la dernière fois
   (localStorage `tq_appareil_erp`) — pour qu'il réutilise le même identifiant
   plutôt que d'en émettre un nouveau à chaque passage (un navigateur qui perd
   ses cookies mais garde son localStorage ne crée pas une ligne par jour).
   ========================================================================== */

const VINGT_QUATRE_HEURES_MS = 24 * 60 * 60 * 1000

// Regex UUID standard (v1-v5), insensible à la casse.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** Parseur minimal de `document.cookie` : `''` si le cookie est absent. */
export function lireCookie(nom, source = (typeof document !== 'undefined' ? document.cookie : '')) {
  if (!source) return ''
  const cible = `${nom}=`
  for (let morceau of source.split(';')) {
    morceau = morceau.trim()
    if (morceau.startsWith(cible)) {
      try {
        return decodeURIComponent(morceau.slice(cible.length))
      } catch {
        return morceau.slice(cible.length)
      }
    }
  }
  return ''
}

/** `true` si `v` ressemble à un UUID (jamais un identifiant inventé/tronqué). */
export function estUuidPlausible(v) {
  return typeof v === 'string' && UUID_RE.test(v)
}

/** Clé localStorage de l'identifiant attribué par le serveur (repli sans cookie). */
export const CLE_APPAREIL_ERP = 'tq_appareil_erp'

/** Clé localStorage « déjà enregistré » — une par utilisateur (poste partagé). */
export function cleEnregistrement(userId) {
  return `tq_equipe_enregistre_${userId}`
}

/** Faut-il (ré)enregistrer ? Oui si jamais fait, illisible, ou > 24 h. */
export function doitEnregistrer(dernierIso, maintenant = new Date()) {
  if (!dernierIso) return true
  const dernier = new Date(dernierIso)
  if (Number.isNaN(dernier.getTime())) return true
  return maintenant.getTime() - dernier.getTime() > VINGT_QUATRE_HEURES_MS
}

/**
 * Enregistre CE navigateur comme appareil équipe, best-effort, au plus une
 * fois par 24 h par utilisateur. Ne fait RIEN sans utilisateur connecté.
 * Toute erreur (réseau, 4xx/5xx) est avalée — jamais de throw, jamais de
 * toast : c'est une reconnaissance silencieuse en tâche de fond, pas une
 * action que l'utilisateur a demandée.
 */
export function enregistrerNavigateurEquipe(user, { api = crmApi, storage = localStorage, maintenant } = {}) {
  if (!user?.id) return Promise.resolve()
  const maintenantEff = maintenant || new Date()
  const cle = cleEnregistrement(user.id)
  let dernier = null
  try {
    dernier = storage?.getItem(cle)
  } catch {
    dernier = null
  }
  if (!doitEnregistrer(dernier, maintenantEff)) return Promise.resolve()

  const cookieAppareil = lireCookie('tq_appareil')
  let appareilId = estUuidPlausible(cookieAppareil) ? cookieAppareil : ''
  if (!appareilId) {
    try {
      const memorise = storage?.getItem(CLE_APPAREIL_ERP)
      if (estUuidPlausible(memorise)) appareilId = memorise
    } catch {
      /* storage indisponible : le serveur attribuera un identifiant */
    }
  }
  const navigateurUA = (typeof navigator !== 'undefined' && navigator.userAgent) || ''

  return api.enregistrerNavigateurEquipe({
    appareil_id: appareilId,
    navigateur: navigateurUA.slice(0, 80),
  })
    .then((res) => {
      try {
        storage?.setItem(cle, maintenantEff.toISOString())
        const attribue = res?.data?.appareil_id
        if (estUuidPlausible(attribue)) storage?.setItem(CLE_APPAREIL_ERP, attribue)
      } catch {
        /* best-effort : un storage indisponible (navigation privée…) ne doit
           jamais empêcher l'enregistrement serveur, juste le re-tenter plus
           tôt la prochaine fois. */
      }
    })
    .catch((err) => {
      try {
        console.debug('[appareilEquipe] enregistrement ignoré (best-effort)', err)
      } catch {
        /* environnement sans console : silencieux */
      }
    })
}
