// COCKPIT-CONTRÔLE (30/09/2026) — les PHRASES et les FORMATS du bloc
// « Contrôle du suivi » (`ControleSuiviPanel.jsx`), en fonctions PURES.
//
// Règle du bloc : tout chiffre affiché vient du serveur (contrat committé
// `apps/crm/contract_samples/controle_suivi.json`). Rien n'est recompté ici :
// on ARRONDIT, on ACCORDE (singulier/pluriel) et on ÉCRIT EN FRANÇAIS ce que le
// serveur a servi. Trois seules opérations, chacune sur deux nombres servis :
// l'écart de points entre le pourcentage de
// la période et celui de la précédente, le « et N autres » (`total` moins
// les lignes servies) et les étapes « reportées une fois » (`total` moins `plusieurs_fois`).
//
// Les libellés des TYPES d'étape et des réponses sont LUS DANS LA TABLE du
// parcours (`parcours_suivi.json`, via `parcours.js`) : le tableau « Détail par
// étape » n'a aucun nom d'étape écrit à la main.
import { PARCOURS, reponsesDeLEtape } from '../../features/crm/relances/parcours'
import { formatNumber, formatPercent } from '../../lib/format'

/** Français : 0 et 1 restent au singulier (« 0 étape », « 1 étape »). */
export const pl = (n, un, plusieurs) => (Number(n) >= 2 ? plusieurs : un)

/** Entier lisible ; `null` → « — » (jamais un 0 inventé). */
export const nombre = (n) => formatNumber(n)

/** « 1 jour ouvré », « 4 jours ouvrés » : le retard et l'attente se comptent en
 *  JOURS OUVRÉS (contrat `notes.retard` : week-ends, jours fériés de la société et
 *  absences déclarées du responsable ne comptent pas). Le nombre est celui du
 *  serveur ; seul l'accord est fait ici. */
export const joursOuvres = (n) => `${nombre(n)} ${pl(n, 'jour ouvré', 'jours ouvrés')}`

/** « reportée 2 fois » : les reports humains de CETTE étape (`nb_reports`, servi). */
export const phraseReportee = (n) => `reportée ${nombre(n)} fois`

/** « 1 étape annulée par le moteur — hors compte » : la liste d'un jour de la frise n'a
 *  pas de ligne pour une touche retirée du plan par le MOTEUR (cadence arrêtée parce que
 *  le client a répondu) — ni due ni manquée ; cette phrase dit seulement combien. */
export const phraseAnnulees = (n) =>
  `${nombre(n)} ${pl(n, 'étape annulée', 'étapes annulées')} par le moteur — hors compte`

/** Un seuil SERVI par le serveur (`seuils.*`) ou `null` : un libellé ne dit jamais
 *  un nombre que le serveur n'a pas servi, ni un nombre écrit dans le code. */
export const seuil = (seuils, cle) => (Number.isFinite(seuils?.[cle]) ? seuils[cle] : null)

/** Les mots des niveaux du verdict — UNE source, lue par le bandeau et par « Comment
 *  lire ce bloc » : ils ne peuvent pas diverger. */
export const MOTS_NIVEAU = {
  ok: 'Tout est à jour',
  attention: 'À surveiller',
  alerte: 'Action requise',
  vide: 'Pas encore de données',
}

/** « Comment lire ce bloc » : les sept lignes, dans l'ordre. `terme` = le mot défini
 *  (`null` pour une phrase entière). Les seuils viennent de `seuils` (servis) : jamais un
 *  nombre écrit ici, et une ligne dont un seuil manque n'est pas affichée. */
export function lignesLecture(seuils) {
  const alerte = seuil(seuils, 'retard_alerte_jours')
  const attente = seuil(seuils, 'tache_attente_jours')
  const reports = seuil(seuils, 'reports_min')
  const lignes = [
    { cle: 'a_temps', terme: 'À temps', texte: 'traitée au plus tard le jour de son échéance.' },
    { cle: 'en_retard', terme: 'Traitée en retard', texte: 'traitée après le jour de son échéance.' },
    { cle: 'sautee', terme: 'Sautée', texte: 'passée volontairement (« Sauter »).' },
    {
      cle: 'ouvert',
      terme: 'Toujours en retard',
      texte: 'pas encore traitée, au moins un jour ouvré après son échéance.',
    },
    {
      cle: 'reportee',
      terme: 'Reportée',
      texte: "échéance repoussée par la commerciale (« Reporter », « Mettre en veille ») — l'échéance d'origine reste affichée.",
    },
    {
      cle: 'jours_non_comptes',
      terme: null,
      texte: 'Week-ends, jours fériés et absences déclarées ne comptent pas dans les retards ; '
        + 'les étapes annulées par le moteur (client joint, devis accepté…) ne comptent ni pour ni contre.',
    },
  ]
  if (alerte !== null && attente !== null && reports !== null) {
    lignes.push({
      cle: 'niveaux',
      terme: null,
      texte: `« ${MOTS_NIVEAU.alerte} » : un retard de ${joursOuvres(alerte)} ou plus, un dossier sans `
        + `prochaine étape ou un premier contact hors délai. « ${MOTS_NIVEAU.attention} » : un retard, `
        + `une tâche en attente depuis ${joursOuvres(attente)}, ou une étape reportée ${nombre(reports)} fois.`,
    })
  }
  return lignes
}

/** La note du bas de « À traiter en priorité » : le seuil d'alerte SERVI, en jours
 *  ouvrés, puis — dès qu'une liste de retard ou d'attente est affichée — ce qui ne
 *  compte pas. `null` s'il n'y a rien à dire. */
export function noteJoursOuvres({ alerteJours, listesRetard }) {
  const phrases = []
  if (alerteJours !== null && alerteJours !== undefined) {
    phrases.push(`Alerte dès ${joursOuvres(alerteJours)} de retard.`)
  }
  if (listesRetard) {
    phrases.push('Week-ends, jours fériés et absences déclarées ne comptent pas.')
  }
  return phrases.length > 0 ? phrases.join(' ') : null
}

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

// `en-CA` rend AAAA-MM-JJ : le JOUR de Casablanca d'un instant, comparable à une
// date de calendrier servie (`due_date`) par simple égalité de chaînes.
const FORMAT_JOUR_CASA = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' })

/** Quand une étape a été traitée, dit par rapport au JOUR lu (`jour`, AAAA-MM-JJ) :
 *  « traitée à 12:54 » si elle l'a été ce jour-là, « traitée le 29/09 à 13:33 » si elle
 *  l'a été un autre jour — la liste d'un jour de la frise montre les étapes DUES ce
 *  jour-là, pas forcément traitées ce jour-là ; l'heure seule le laisserait croire.
 *  `null` sans instant lisible. */
export function momentTraitement(iso, jour) {
  const heure = heureCasa(iso)
  if (!heure) return null
  const jourTraite = FORMAT_JOUR_CASA.format(new Date(iso).getTime())
  return jourTraite === jour ? `traitée à ${heure}` : `traitée le ${jjmm(jourTraite)} à ${heure}`
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
    // est la plus ancienne — on lit son ancienneté (en JOURS OUVRÉS, contrat
    // `notes.retard`), on ne la calcule pas.
    const jours = ex.taches_en_attente?.lignes?.[0]?.ouverte_depuis_jours
    let phrase = `${nombre(taches)} ${pl(taches, 'tâche', 'tâches')} en attente`
    if (jours !== undefined && jours !== null) {
      const depuis = `depuis ${joursOuvres(jours)}`
      phrase += taches > 1 ? ` (la plus ancienne ${depuis})` : ` ${depuis}`
    }
    parts.push(phrase)
  }

  // Toutes les étapes reportées sont dites (dès le premier report), en deux comptes : celles
  // qui l'ont été PLUSIEURS fois (`plusieurs_fois`, servi — elles font passer le niveau à
  // « À surveiller ») et les autres, reportées une fois (`total` − `plusieurs_fois` : une
  // simple différence de deux nombres servis). Un serveur qui ne sert pas `plusieurs_fois`
  // (ancien contrat : la liste n'avait QUE des étapes reportées plusieurs fois) les dit toutes ainsi.
  const reportees = total('reports')
  const plusieurs = ex.reports?.plusieurs_fois === undefined
    ? reportees : (Number(ex.reports.plusieurs_fois) || 0)
  const uneFois = Math.max(0, reportees - plusieurs)
  if (plusieurs > 0) {
    parts.push(`${nombre(plusieurs)} ${pl(plusieurs, 'étape reportée', 'étapes reportées')} plusieurs fois`)
  }
  if (uneFois > 0) {
    parts.push(`${nombre(uneFois)} ${pl(uneFois, 'étape reportée', 'étapes reportées')} une fois`)
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

/** « Sur 14 jours : 36 étapes sur 42 traitées à temps (86 %), 3 traitées en retard, 1 sautée,
 *  2 toujours en retard — dont 6 reportées au moins une fois. »
 *  `ouvert` = encore à faire ET déjà en retard (contrat `notes.verdict`) ; `reportees` est
 *  un fait montré à côté du pourcentage, jamais retranché de lui — la fin « — dont … »
 *  n'apparaît que s'il y en a. */
export function phrasePeriode(verdict, periodeJours) {
  const v = verdict || {}
  const periode = `Sur ${nombre(periodeJours)} jours`
  if (!v.du) return `${periode} : aucune étape n'était due.`
  const pct = v.a_temps_pct === null || v.a_temps_pct === undefined ? '—' : formatPercent(v.a_temps_pct)
  const reportees = Number(v.reportees) > 0
    ? ` — dont ${nombre(v.reportees)} ${pl(v.reportees, 'reportée', 'reportées')} au moins une fois`
    : ''
  return `${periode} : ${nombre(v.a_temps)} ${pl(v.a_temps, 'étape', 'étapes')} sur ${nombre(v.du)} `
    + `${pl(v.a_temps, 'traitée', 'traitées')} à temps (${pct}), `
    + `${nombre(v.en_retard)} ${pl(v.en_retard, 'traitée', 'traitées')} en retard, `
    + `${nombre(v.sautees)} ${pl(v.sautees, 'sautée', 'sautées')}, `
    + `${nombre(v.ouvert)} toujours en retard${reportees}.`
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
    morceaux.push(`${nombre(j.en_retard)} ${pl(j.en_retard, 'traitée', 'traitées')} en retard`)
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

/** REPLI UNIQUE : le libellé GÉNÉRIQUE de chaque issue enregistrée par le
 *  serveur (`par_type[].reponses[].cle`). Il sert quand la clé ne désigne pas UNE
 *  réponse du type — plusieurs réponses la partagent (`non_joint` est portée par
 *  « Pas de réponse », « Répondeur », « Occupé », « Numéro invalide »… : aucun de
 *  ces libellés ne dit ce que compte le chiffre) ou aucune ne la porte. Les
 *  libellés sont ceux de la table (`parcours_suivi.json`, modèles `pas_de_reponse`,
 *  `joint`, `rappel`, `refus`, `visite`, `fait`) ; un test les y rattache. */
export const LIBELLES_ISSUE = {
  non_joint: 'Pas de réponse',
  joint: 'Client joint',
  rappel: 'À rappeler',
  refuse: 'Refus',
  visite_acceptee: 'Visite acceptée',
  sans_issue: 'Fait',
}

/** Le libellé d'une réponse servie (`cle` = l'issue enregistrée) :
 *   · `sans_issue` (un « Fait — passer à la suite ») → « Fait » ;
 *   · UNE seule réponse du type porte cette clé (son `outcome` ou sa `reponse`) →
 *     SON libellé dans la table (« Pas encore — à rappeler le… » pour le devis) ;
 *   · plusieurs la partagent → le libellé générique de l'issue (`LIBELLES_ISSUE`),
 *     jamais celui de la première (« Répondeur » pour `non_joint`) ;
 *   · aucune ne la porte → le libellé générique s'il existe, sinon la clé telle quelle.
 *  Les réponses du type sont celles que l'écran propose sur une étape d'APPEL
 *  (`reponsesDeLEtape` de parcours.js) : `reponses` + `reponses_appel` (objets
 *  `{ modele, effet, suite… }` ou identifiants de modèle), même normalisation. */
export function libelleReponse(typeId, cle) {
  if (cle === 'sans_issue') return LIBELLES_ISSUE.sans_issue
  const type = TYPES.get(typeId)
  const candidates = type
    ? reponsesDeLEtape(type, { canal: 'appel' })
      .filter((r) => r.outcome === cle || r.reponse === cle)
    : []
  const generique = LIBELLES_ISSUE[cle]
  if (candidates.length === 1) return candidates[0].label ?? generique ?? cle
  if (candidates.length > 1) return generique ?? candidates[0].label ?? cle
  return generique ?? cle
}

// ── Premier contact et résultats ───────────────────────────────────────────
/** L'attente d'un lead jamais contacté, sur l'horloge du DÉLAI (contrat `notes.exceptions` :
 *  heures d'horloge, jours non ouvrés retirés — un lead créé il y a six jours vaut ~99 h).
 *  UN seul format : sous 48 h, en heures (« 27,5 h ») ; à partir de 48 h, en jours ouvrés
 *  ENTIERS, arrondis vers le bas (99,1 h → « 4 jours ouvrés »). `null` → « — ». */
export function dureeAttente(heures) {
  if (heures === null || heures === undefined || Number.isNaN(Number(heures))) return '—'
  const h = Number(heures)
  if (h < 48) return `${decimal(h)} h`
  return joursOuvres(Math.floor(h / 24))
}

/** « 19 sur 23 contactés dans le délai (24 h) · délai médian 1 h 11 (heures ouvrées) ·
 *  plus longue attente : 4 jours ouvrés » — ou « … · aucun lead en attente ». */
export function phrasePremierContact(pc) {
  const p = pc || {}
  if (!p.nouveaux) return 'Aucun nouveau lead sur la période.'
  const mediane = p.mediane_minutes === null || p.mediane_minutes === undefined
    ? 'délai médian —'
    : `délai médian ${duree(p.mediane_minutes)} (heures ouvrées)`
  const attente = p.plus_longue_attente_heures === null || p.plus_longue_attente_heures === undefined
    ? 'aucun lead en attente'
    : `plus longue attente : ${dureeAttente(p.plus_longue_attente_heures)}`
  return `${nombre(p.dans_le_delai)} sur ${nombre(p.nouveaux)} ${pl(p.nouveaux, 'contacté', 'contactés')}`
    + ` dans le délai (${decimal(p.delai_heures)} h) · ${mediane} · ${attente}`
}

/** « 3 visites planifiées · 4 devis envoyés · 1 devis accepté ». */
export function phraseResultats(r) {
  const x = r || {}
  return `${nombre(x.visites_planifiees)} ${pl(x.visites_planifiees, 'visite planifiée', 'visites planifiées')}`
    + ` · ${nombre(x.devis_envoyes)} ${pl(x.devis_envoyes, 'devis envoyé', 'devis envoyés')}`
    + ` · ${nombre(x.devis_acceptes)} ${pl(x.devis_acceptes, 'devis accepté', 'devis acceptés')}`
}
