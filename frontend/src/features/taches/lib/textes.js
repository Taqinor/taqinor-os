/* ============================================================================
   TCH44/TCH46 — Formats de texte de l'app Tâches : jours, heures, durées, accords.
   JUMEAU de `apps/taches/moteur/gabarits.py` (TCH30) : mêmes règles, mêmes sorties,
   testées sur les mêmes dates (`textes.test.js`). Source : docs/taches/reference/textes.md
   « Conventions d'écriture ». Fonctions PURES : aucune horloge cachée — le jour courant
   est toujours un argument (ISO `AAAA-MM-JJ`), défaut = le jour local de l'appareil.

   Jours : « aujourd'hui », « demain », sinon « jeu. 19 » dans les 13 jours, « mar. 1 déc. »
   au-delà, « 12/11/2027 » hors de l'année, et au passé « jeu. 12 nov. » (UNE forme de date à l'écran).
   Heures : « 10:00 » sur une puce ou une ligne ; « 10 h », « 10 h 30 » dans une phrase lue.
   Durées : « 45 min », « 1 h », « 3 h 10 ». Accord : 0 et 1 au singulier, ≥ 2 au pluriel.
   ========================================================================== */

export const ABR_JOURS = ['dim.', 'lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.']
export const ABR_MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
const JOURS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi']
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
  'novembre', 'décembre']

const deux = (n) => String(n).padStart(2, '0')

/** Le jour local de l'appareil, en ISO `AAAA-MM-JJ`. */
export function aujourdhuiIso(date = new Date()) {
  return `${date.getFullYear()}-${deux(date.getMonth() + 1)}-${deux(date.getDate())}`
}

function composants(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''))
  if (!m) return null
  const [annee, mois, jour] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const utc = Date.UTC(annee, mois - 1, jour)
  return { annee, mois, jour, utc, joursem: new Date(utc).getUTCDay() }
}

/** Écart en jours entiers entre deux dates ISO (positif = `iso` est après `reference`). */
export function ecartJours(iso, reference = aujourdhuiIso()) {
  const a = composants(iso)
  const b = composants(reference)
  if (!a || !b) return null
  return Math.round((a.utc - b.utc) / 86400000)
}

/** « aujourd'hui » · « demain » · « jeu. 19 » · « mar. 1 déc. » · « 12/11/2027 » · passé « jeu. 12 nov. ». */
export function jourCourt(iso, aujourdhui = aujourdhuiIso()) {
  const c = composants(iso)
  const ref = composants(aujourdhui)
  const ecart = ecartJours(iso, aujourdhui)
  if (!c || !ref || ecart === null) return ''
  if (ecart === 0) return "aujourd'hui"
  if (ecart === 1) return 'demain'
  if (c.annee !== ref.annee) return `${deux(c.jour)}/${deux(c.mois)}/${c.annee}`
  if (ecart > 0 && ecart <= 13) return `${ABR_JOURS[c.joursem]} ${c.jour}`
  return `${ABR_JOURS[c.joursem]} ${c.jour} ${ABR_MOIS[c.mois - 1]}`
}

/** « jeu. 19 » sans « aujourd'hui » ni « demain » : pour « Reporter à lun. 23 », « → lun. 23 ». */
export function jourNomme(iso, aujourdhui = aujourdhuiIso()) {
  const c = composants(iso)
  if (!c) return ''
  const ecart = ecartJours(iso, aujourdhui)
  if (ecart !== null && ecart >= 0 && ecart <= 13 && c.annee === composants(aujourdhui).annee) {
    return `${ABR_JOURS[c.joursem]} ${c.jour}`
  }
  return jourCourt(iso, aujourdhui)
}

/** « Vendredi 20 novembre » : le jour au-dessus du titre d'Aujourd'hui. */
export function jourLong(iso = aujourdhuiIso()) {
  const c = composants(iso)
  if (!c) return ''
  const texte = `${JOURS[c.joursem]} ${c.jour} ${MOIS[c.mois - 1]}`
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

/** « 10:00 » (secondes retirées) ; vide si l'heure est absente. */
export function heure(valeur) {
  const m = /^(\d{1,2}):(\d{2})/.exec(String(valeur ?? ''))
  return m ? `${deux(m[1])}:${m[2]}` : ''
}

/**
 * « 10:42 » du bandeau de conflit (textes.md §2.2) : l'heure de la version de l'autre appareil, lue dans la réponse
 * 409 (`actuel.updated_at`, ISO servi à l'heure du Maroc) — jamais l'horloge du navigateur ; '' si absente.
 */
export function heureDuConflit(actuel) {
  return heure(String(actuel?.updated_at ?? '').slice(11, 16))
}

/** « 10 h » · « 10 h 30 » : l'heure dans une phrase lue ou dite. */
export function heureDite(valeur) {
  const m = /^(\d{1,2}):(\d{2})/.exec(String(valeur ?? ''))
  if (!m) return ''
  const h = Number(m[1])
  return m[2] === '00' ? `${h} h` : `${h} h ${m[2]}`
}

/** « 45 min » · « 1 h » · « 3 h 10 » ; vide pour 0, null ou négatif. */
export function duree(minutes) {
  const n = Math.round(Number(minutes))
  if (!Number.isFinite(n) || n <= 0) return ''
  if (n < 60) return `${n} min`
  const h = Math.floor(n / 60)
  const reste = n % 60
  return reste === 0 ? `${h} h` : `${h} h ${reste}`
}

/** « 1 faite » · « 0 tâche » · « 3 tâches » : 0 et 1 au singulier. */
export function accord(n, singulier, pluriel = `${singulier}s`) {
  return `${n} ${Math.abs(n) >= 2 ? pluriel : singulier}`
}

/**
 * La puce d'échéance d'une ligne : `{ texte, ton }`, `ton` ∈ `alerte` (aujourd'hui ou dépassée,
 * seul usage du rouge avec le destructif) · `fort` (échéance proche : `--foreground` 500, sans teinte).
 */
export function echeanceTexte(echeance, aujourdhui = aujourdhuiIso()) {
  const ecart = ecartJours(echeance, aujourdhui)
  if (ecart === null) return null
  if (ecart === 0) return { texte: "échéance aujourd'hui", ton: 'alerte' }
  if (ecart < 0) {
    const c = composants(echeance)
    return { texte: `échéance dépassée le ${deux(c.jour)}/${deux(c.mois)}`, ton: 'alerte' }
  }
  return { texte: `échéance ${jourCourt(echeance, aujourdhui)}`, ton: 'fort' }
}

/** Ce que dit l'écran d'un lien ERP qui n'est plus lisible (textes.md « Lien ERP ») : jamais un libellé ni une adresse. */
export const ETATS_LIEN = {
  archive: 'Élément archivé', introuvable: 'Élément introuvable', inaccessible: 'Hors de ta portée', efface: 'Lead effacé',
}

/** Les familles de suggestions de l'ERP et leur phrase (textes.md « L'ERP me suggère »), dans l'ordre du serveur. */
export const FAMILLES_SUGGESTIONS = [
  ['devis_accepte', 'Devis accepté : préparer le chantier'],
  ['chantier_receptionne', 'Chantier réceptionné : demander un avis'],
  ['chantier_annule', 'Chantier annulé : comprendre pourquoi'],
  ['visite_validee', 'Visite validée : préparer le devis'],
]
