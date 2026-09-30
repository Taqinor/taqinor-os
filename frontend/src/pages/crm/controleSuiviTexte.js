// COCKPIT-CONTRÔLE (30/09/2026) — les PHRASES et les FORMATS du bloc
// « Contrôle du suivi » (`ControleSuiviPanel.jsx`), en fonctions PURES.
//
// Règle du bloc : tout chiffre affiché vient du serveur (contrat committé
// `apps/crm/contract_samples/controle_suivi.json`). Rien n'est recompté ici :
// on ARRONDIT, on ACCORDE (singulier/pluriel) et on ÉCRIT EN FRANÇAIS ce que le
// serveur a servi. Deux seules opérations sur deux nombres servis, toutes deux
// demandées par l'ordre fondateur : l'écart de points entre le pourcentage de
// la période et celui de la précédente, et le « et N autres » (`total` moins
// les lignes servies).
//
// Les libellés des TYPES d'étape et des réponses sont LUS DANS LA TABLE du
// parcours (`parcours_suivi.json`, via `parcours.js`) : le tableau « Détail par
// étape » n'a aucun nom d'étape écrit à la main.
import { PARCOURS, reponseComplete } from '../../features/crm/relances/parcours'
import { formatNumber, formatPercent } from '../../lib/format'

/** Français : 0 et 1 restent au singulier (« 0 étape », « 1 étape »). */
export const pl = (n, un, plusieurs) => (Number(n) >= 2 ? plusieurs : un)

/** Entier lisible ; `null` → « — » (jamais un 0 inventé). */
export const nombre = (n) => formatNumber(n)

const FORMAT_DECIMAL = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 })

/** 27.5 → « 27,5 » ; 24 → « 24 » ; `null` → « — ». */
export function decimal(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—'
  return FORMAT_DECIMAL.format(Number(n))
}

/** Minutes → « 42 min » ; à partir d'une heure « 1 h 05 » (même durée, autre unité). */
export function duree(minutes) {
  if (minutes === null || minutes === undefined || Number.isNaN(Number(minutes))) return '—'
  const total = Math.round(Number(minutes))
  if (total < 60) return `${total} min`
  const h = Math.floor(total / 60)
  const m = total % 60
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, '0')}`
}

// ── Dates ──────────────────────────────────────────────────────────────────
// `AAAA-MM-JJ` est une date de CALENDRIER (déjà à l'heure de Casablanca côté
// serveur) : on la lit en UTC pour qu'aucun fuseau de navigateur ne la fasse
// glisser d'un jour.
const FORMAT_JOUR_LONG = new Intl.DateTimeFormat('fr-FR', {
  weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC',
})
const FORMAT_JOUR_COURT = new Intl.DateTimeFormat('fr-FR', { weekday: 'short', timeZone: 'UTC' })
const FORMAT_HEURE_CASA = new Intl.DateTimeFormat('fr-FR', {
  hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
})

const midi = (date) => new Date(`${date}T12:00:00Z`)
const dateValide = (date) => typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)

/** « mardi 29 septembre ». */
export function jourLong(date) {
  return dateValide(date) ? FORMAT_JOUR_LONG.format(midi(date)) : '—'
}

/** « mar » (sans point) pour la case de la frise. */
export function jourCourt(date) {
  return dateValide(date) ? FORMAT_JOUR_COURT.format(midi(date)).replace('.', '') : ''
}

/** Numéro du jour dans le mois : « 2026-09-29 » → 29. */
export function numeroJour(date) {
  return dateValide(date) ? Number(date.slice(8, 10)) : ''
}

/** « 2026-09-27 » → « 27/09 » (jour/mois, sans année). */
export function jjmm(date) {
  return dateValide(date) ? `${date.slice(8, 10)}/${date.slice(5, 7)}` : '—'
}

/** Instant ISO → « HH:MM » à l'heure de Casablanca (jamais celle du navigateur). */
export function heureCasa(iso) {
  if (!iso) return null
  const t = new Date(iso).getTime()
  return Number.isNaN(t) ? null : FORMAT_HEURE_CASA.format(t)
}

// ── Verdict ────────────────────────────────────────────────────────────────
/** UNE phrase construite depuis les cinq listes d'exceptions (les retards d'abord). */
export function phraseExceptions(exceptions, niveau) {
  const ex = exceptions || {}
  const total = (cle) => Number(ex[cle]?.total) || 0
  const parts = []

  const retard = total('en_retard')
  if (retard > 0) parts.push(`${nombre(retard)} ${pl(retard, 'étape', 'étapes')} en retard`)

  const taches = total('taches_en_attente')
  if (taches > 0) {
    // Les lignes sont triées par ancienneté décroissante (contrat) : la première
    // est la plus ancienne — on lit son ancienneté, on ne la calcule pas.
    const jours = ex.taches_en_attente?.lignes?.[0]?.ouverte_depuis_jours
    let phrase = `${nombre(taches)} ${pl(taches, 'tâche', 'tâches')} en attente`
    if (jours !== undefined && jours !== null) {
      const depuis = `depuis ${nombre(jours)} ${pl(jours, 'jour', 'jours')}`
      phrase += taches > 1 ? ` (la plus ancienne ${depuis})` : ` ${depuis}`
    }
    parts.push(phrase)
  }

  const reports = total('reports')
  if (reports > 0) {
    parts.push(`${nombre(reports)} ${pl(reports, 'étape reportée', 'étapes reportées')} plusieurs fois`)
  }

  const sans = total('sans_prochaine_etape')
  if (sans > 0) {
    parts.push(`${nombre(sans)} ${pl(sans, 'dossier sans prochaine étape', 'dossiers sans prochaine étape')}`)
  }

  const premier = total('premier_contact_hors_delai')
  if (premier > 0) {
    parts.push(`${nombre(premier)} ${pl(premier, 'premier contact', 'premiers contacts')} hors délai`)
  }

  if (parts.length > 0) return `${parts.join(', ')}.`
  if (niveau === 'vide') return "Aucune étape n'était due sur cette période."
  if (niveau === 'ok') return "Rien n'est en retard ni en attente."
  return ''
}

/** « Sur 14 jours : 36 étapes sur 42 traitées à temps (86 %), 3 rattrapées en retard, … ». */
export function phrasePeriode(verdict, periodeJours) {
  const v = verdict || {}
  const periode = `Sur ${nombre(periodeJours)} jours`
  if (!v.du) return `${periode} : aucune étape n'était due.`
  const pct = v.a_temps_pct === null || v.a_temps_pct === undefined ? '—' : formatPercent(v.a_temps_pct)
  return `${periode} : ${nombre(v.a_temps)} ${pl(v.a_temps, 'étape', 'étapes')} sur ${nombre(v.du)} `
    + `${pl(v.a_temps, 'traitée', 'traitées')} à temps (${pct}), `
    + `${nombre(v.en_retard)} ${pl(v.en_retard, 'rattrapée', 'rattrapées')} en retard, `
    + `${nombre(v.sautees)} ${pl(v.sautees, 'sautée', 'sautées')}, `
    + `${nombre(v.ouvert)} ${pl(v.ouvert, 'encore ouverte', 'encore ouvertes')}.`
}

/** Comparaison à la période précédente ; `null` (rien à dire) si l'un des deux pourcentages est `null`. */
export function comparaisonPrecedent(verdict) {
  const v = verdict || {}
  if (v.a_temps_pct === null || v.a_temps_pct === undefined
    || v.precedent_a_temps_pct === null || v.precedent_a_temps_pct === undefined) return null
  // L'écart se lit sur les deux pourcentages TELS QU'AFFICHÉS (arrondis) : la
  // flèche ne contredit jamais les chiffres voisins.
  const actuel = Math.round(v.a_temps_pct)
  const avant = Math.round(v.precedent_a_temps_pct)
  const ecart = actuel - avant
  const reference = `par rapport à la période précédente (${avant} %)`
  if (ecart > 0) {
    return { sens: 'hausse', fleche: '↑', texte: `↑ ${ecart} ${pl(ecart, 'point', 'points')} ${reference}` }
  }
  if (ecart < 0) {
    const points = Math.abs(ecart)
    return { sens: 'baisse', fleche: '↓', texte: `↓ ${points} ${pl(points, 'point', 'points')} ${reference}` }
  }
  return { sens: 'stable', fleche: '→', texte: `→ Stable ${reference}` }
}

// ── Frise ──────────────────────────────────────────────────────────────────
/** Nom accessible complet d'une case : « mardi 29 septembre : 6 dues, 4 à temps, 2 encore ouvertes ». */
export function libelleJour(jour) {
  const j = jour || {}
  const morceaux = []
  if (j.du > 0) morceaux.push(`${nombre(j.du)} ${pl(j.du, 'due', 'dues')}`)
  if (j.a_temps > 0) morceaux.push(`${nombre(j.a_temps)} à temps`)
  if (j.en_retard > 0) {
    morceaux.push(`${nombre(j.en_retard)} ${pl(j.en_retard, 'rattrapée', 'rattrapées')} en retard`)
  }
  if (j.sautees > 0) morceaux.push(`${nombre(j.sautees)} ${pl(j.sautees, 'sautée', 'sautées')}`)
  if (j.ouvert > 0) morceaux.push(`${nombre(j.ouvert)} ${pl(j.ouvert, 'encore ouverte', 'encore ouvertes')}`)
  let qualif = ''
  if (j.aujourdhui) qualif = " (aujourd'hui)"
  else if (j.ouvre === false) qualif = ' (jour non ouvré)'
  return `${jourLong(j.date)}${qualif} : ${morceaux.length > 0 ? morceaux.join(', ') : 'rien de dû'}`
}

// ── Table du parcours ──────────────────────────────────────────────────────
const TYPES = new Map(PARCOURS.etapes.map((t) => [t.id, t]))

/** Le type d'étape de la table pour son identifiant, ou `undefined`. */
export const typeDeLaTable = (id) => TYPES.get(id)

/** Le NOM du type lu dans la table ; identifiant tel quel s'il n'y figure pas, '' s'il est vide. */
export function nomType(id) {
  if (!id) return ''
  return TYPES.get(id)?.nom ?? id
}

/** La FAMILLE du type lue dans la table (« Visite technique »…), '' si inconnue. */
export const familleType = (id) => TYPES.get(id)?.famille ?? ''

/** Une TÂCHE selon la table (préparer le devis, décider la suite…). */
export const typeEstTache = (id) => Boolean(TYPES.get(id)?.tache)

/** Le libellé d'une réponse servie : celui de la table pour ce type (première
 *  réponse dont l'`outcome` ou la `reponse` vaut la clé) ; `sans_issue` →
 *  « Fait » ; clé inconnue → la clé telle quelle. */
export function libelleReponse(typeId, cle) {
  if (cle === 'sans_issue') return 'Fait'
  const type = TYPES.get(typeId)
  const trouvee = (type?.reponses ?? [])
    .map(reponseComplete)
    .find((r) => r.outcome === cle || r.reponse === cle)
  return trouvee?.label ?? cle
}

// ── Premier contact et résultats ───────────────────────────────────────────
/** « 8 sur 9 dans le délai (24 h) · médiane 42 min · plus longue attente 27,5 h ». */
export function phrasePremierContact(pc) {
  const p = pc || {}
  if (!p.nouveaux) return 'Aucun nouveau lead sur la période.'
  const attente = p.plus_longue_attente_heures === null || p.plus_longue_attente_heures === undefined
    ? 'aucun lead en attente'
    : `plus longue attente ${decimal(p.plus_longue_attente_heures)} h`
  return `${nombre(p.dans_le_delai)} sur ${nombre(p.nouveaux)} dans le délai (${decimal(p.delai_heures)} h)`
    + ` · médiane ${duree(p.mediane_minutes)} · ${attente}`
}

/** « 3 visites planifiées · 4 devis envoyés · 1 devis accepté ». */
export function phraseResultats(r) {
  const x = r || {}
  return `${nombre(x.visites_planifiees)} ${pl(x.visites_planifiees, 'visite planifiée', 'visites planifiées')}`
    + ` · ${nombre(x.devis_envoyes)} ${pl(x.devis_envoyes, 'devis envoyé', 'devis envoyés')}`
    + ` · ${nombre(x.devis_acceptes)} ${pl(x.devis_acceptes, 'devis accepté', 'devis acceptés')}`
}
