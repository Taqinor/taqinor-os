/* ============================================================================
   NTI18N12 — Conversion d'AFFICHAGE grégorien → hégirien.
   ----------------------------------------------------------------------------
   Lib PURE JS, AUCUNE dépendance ajoutée : s'appuie sur le calendrier
   islamique NATIF d'`Intl` (extension Unicode `u-ca-islamic-umalqura` —
   calendrier hégirien officiel le plus largement reconnu), déjà embarqué
   dans tout navigateur/moteur JS moderne (données ICU) — zéro implémentation
   maison d'algorithme de conversion (source d'erreurs notoire, cf. NTI18N14
   qui exclut explicitement tout calcul algorithmique pour les FÊTES
   religieuses officielles — ceci est un AFFICHAGE secondaire, pas une date
   légale).

   AFFICHAGE SEUL : ces fonctions ne calculent et ne renvoient JAMAIS rien qui
   soit stocké — jamais en remplacement de la date grégorienne, toujours EN
   PLUS d'elle (règle NTI18N12).
   ========================================================================== */

// Locale FR + calendrier hégirien : rend les noms de mois en transcription
// française usuelle (« ramadan », « chaabane »…) plutôt qu'en écriture
// arabe — cohérent avec l'exemple de l'énoncé (« 12 Ramadan 1447 »).
const HIJRI_LOCALE_TAG = 'fr-u-ca-islamic-umalqura'

function toDate(value) {
  // Garde falsy AVANT construction : `new Date(null)` vaut l'epoch
  // (1970-01-01, PAS une date invalide) — sans ce garde, `formatHijriDate
  // (null)` renverrait une vraie date au lieu de `null`.
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}

/**
 * Date hégirienne SEULE : « 26 Ramadan 1447 » (jour, mois capitalisé, année).
 * `null` si `value` n'est pas une date valide (jamais d'exception).
 */
export function formatHijriDate(value) {
  const d = toDate(value)
  if (!d) return null
  const parts = new Intl.DateTimeFormat(HIJRI_LOCALE_TAG, {
    day: 'numeric', month: 'long', year: 'numeric',
  }).formatToParts(d)
  const get = (type) => parts.find((p) => p.type === type)?.value
  const day = get('day')
  const month = get('month')
  const year = get('year')
  if (!day || !month || !year) return null
  return `${day} ${capitalize(month)} ${year}`
}

/**
 * Date hégirienne + grégorienne EN PLUS (jamais en remplacement) :
 * « 26 Ramadan 1447 (2026-03-15) » — format de l'exemple d'acceptation
 * NTI18N12. `null` si `value` n'est pas une date valide : l'appelant garde
 * alors simplement la date grégorienne déjà affichée par ailleurs (aucune
 * régression visuelle possible).
 */
export function formatWithHijri(value) {
  const d = toDate(value)
  if (!d) return null
  const hijri = formatHijriDate(d)
  if (!hijri) return null
  const iso = d.toISOString().slice(0, 10)
  return `${hijri} (${iso})`
}

/**
 * Vrai UNIQUEMENT quand les DEUX conditions de l'énoncé sont réunies : la
 * langue d'interface est l'arabe ET la préférence utilisateur est active.
 * Centralise la garde pour que chaque écran consommateur applique EXACTEMENT
 * la même règle (jamais une variante qui affiche l'hégirien en FR/EN, jamais
 * une variante qui l'affiche sans préférence explicite).
 */
export function shouldShowHijri({ locale, calendrierHegirien }) {
  return locale === 'ar' && calendrierHegirien === true
}

/* ── CAD37 ─────────────────────────────────────────────────────────────────
   PROPOSER les dates de Ramadan d'une année grégorienne — jamais les POSER.

   Le calendrier hégirien glisse d'environ onze jours par an : les deux dates
   `ramadan_debut` / `ramadan_fin` de la société doivent être retapées chaque
   année, et tant qu'elles sont vides `est_en_ramadan` renvoie faux — les
   appels sonnent de 09 h à 20 h en plein jeûne.

   Ces fonctions lisent le MÊME calendrier ICU que le reste de ce module
   (`islamic-umalqura`, aucune dépendance ajoutée) et renvoient une
   PROPOSITION que l'utilisateur confirme à la main. Les dates officielles du
   début et de la fin du mois sont annoncées chaque année par l'observation :
   rien ici n'est une date légale, rien n'est écrit automatiquement.
   ======================================================================== */

// `numeric` sur un calendrier hégirien rend le RANG du mois (« 9 » = ramadan)
// et non son nom : c'est ce qui permet de reconnaître le mois sans dépendre
// d'une transcription (« ramadan », « ramaḍān », « رمضان »…).
const HIJRI_PARTS_TAG = 'en-u-ca-islamic-umalqura'
const RAMADAN_RANG = 9

let partsFormatter = null
function hijriParts(date) {
  if (!partsFormatter) {
    partsFormatter = new Intl.DateTimeFormat(HIJRI_PARTS_TAG, {
      day: 'numeric', month: 'numeric', year: 'numeric',
    })
  }
  const parts = partsFormatter.formatToParts(date)
  const get = (type) => parts.find((p) => p.type === type)?.value
  const mois = Number(get('month'))
  const jour = Number(get('day'))
  const annee = Number(String(get('year')).replace(/[^0-9]/g, ''))
  if (!mois || !jour || !annee) return null
  return { mois, jour, annee }
}

function isoUTC(date) {
  return date.toISOString().slice(0, 10)
}

/**
 * Toutes les périodes de Ramadan qui TOMBENT dans l'année grégorienne
 * `annee` — il peut y en avoir deux (une en janvier, une en décembre), le
 * mois hégirien reculant d'environ onze jours chaque année.
 *
 * Renvoie `[{ debut, fin, anneeHegirienne }]` (dates ISO `AAAA-MM-JJ`),
 * toujours un tableau, jamais d'exception. Le balayage DÉBORDE d'un mois de
 * chaque côté puis ne garde que les périodes qui croisent l'année demandée :
 * sans ce débordement, un Ramadan à cheval sur le 31 décembre serait proposé
 * TRONQUÉ, c'est-à-dire faux.
 */
export function periodesRamadan(annee) {
  const an = Number(annee)
  if (!Number.isInteger(an)) return []
  const periodes = []
  let courante = null
  const jour = new Date(Date.UTC(an - 1, 11, 1))
  const borne = new Date(Date.UTC(an + 1, 1, 1))
  while (jour < borne) {
    const h = hijriParts(jour)
    if (h && h.mois === RAMADAN_RANG) {
      if (!courante) {
        courante = {
          debut: isoUTC(jour), fin: isoUTC(jour),
          anneeHegirienne: String(h.annee),
        }
      } else {
        courante.fin = isoUTC(jour)
      }
    } else if (courante) {
      periodes.push(courante)
      courante = null
    }
    jour.setUTCDate(jour.getUTCDate() + 1)
  }
  if (courante) periodes.push(courante)
  const prefixe = String(an)
  return periodes.filter(
    (p) => p.debut.startsWith(prefixe) || p.fin.startsWith(prefixe))
}

/**
 * LA proposition à montrer pour l'année de `aujourdHui` : la période de
 * Ramadan qui n'est pas encore terminée, sinon la dernière de l'année (celle
 * qu'on vient de vivre reste la bonne réponse jusqu'au 31 décembre).
 *
 * `null` si le moteur JS ne sait pas rendre ce calendrier — l'écran retombe
 * alors sur la saisie manuelle, sans rien casser.
 */
export function proposerRamadan(aujourdHui = new Date()) {
  const d = aujourdHui instanceof Date ? aujourdHui : new Date(aujourdHui)
  if (Number.isNaN(d.getTime())) return null
  const periodes = periodesRamadan(d.getUTCFullYear())
  if (!periodes.length) return null
  const iso = isoUTC(d)
  return periodes.find((p) => p.fin >= iso) || periodes[periodes.length - 1]
}

/**
 * Les deux dates saisies couvrent-elles bien l'année de `aujourdHui` ?
 * Faux dès qu'une des deux manque ou qu'aucune des deux ne tombe dans cette
 * année — c'est exactement le cas « on a oublié de retaper les dates ».
 */
export function datesRamadanASaisir(debut, fin, aujourdHui = new Date()) {
  if (!debut || !fin) return true
  const d = aujourdHui instanceof Date ? aujourdHui : new Date(aujourdHui)
  if (Number.isNaN(d.getTime())) return false
  const annee = String(d.getUTCFullYear())
  return !(String(debut).startsWith(annee) || String(fin).startsWith(annee))
}
