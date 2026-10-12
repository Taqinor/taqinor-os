// ENF28 (ENF19/ENF22) — logique PURE de l'écran des tickets SAV, sortie de
// TicketsPage.jsx (un fichier de composants n'exporte plus de fonctions, plus
// de directive eslint-disable) : messages d'erreur DRF lisibles, actions
// groupées (ASAV48) et horloge SLA de résolution (APX30). Sans import
// extensionless : importable tel quel par `node --test` (TicketSla.apx30).
import { TICKET_OPEN_STATUSES } from '../../features/sav/ticketStatuses.js'

// L302/L11 — libellés FR des champs pour transformer une erreur DRF brute
// ({champ: [raison]}) en message lisible « Échec : {champ} — {raison} », au lieu
// d'un JSON.stringify illisible.
const FIELD_LABELS_FR = {
  statut: 'Statut', type: 'Type', priorite: 'Priorité',
  description: 'Description', sous_garantie: 'Sous garantie',
  equipement: 'Équipement', technicien_responsable: 'Technicien responsable',
  date_resolution: 'Date de résolution', cout: 'Coût',
  detail: 'Erreur', non_field_errors: 'Erreur', body: 'Note', motif: 'Motif',
  produit: 'Produit', quantite: 'Quantité',
}
export function frError(err, fallback = 'Action impossible.') {
  if (!err) return fallback
  const data = err?.response?.data ?? err
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    const parts = []
    for (const [field, raison] of Object.entries(data)) {
      // ERR-QAH-SAV-ERREUR-OBJECT-OBJECT — `error` est l'ENVELOPPE technique du
      // middleware d'erreurs (objet), jamais un champ : on ne l'itère pas.
      if (field === 'error') continue
      if (raison && typeof raison === 'object' && !Array.isArray(raison)) continue
      const label = FIELD_LABELS_FR[field] ?? field
      const txt = Array.isArray(raison) ? raison.join(' ') : String(raison)
      parts.push(field === 'detail' || field === 'non_field_errors'
        ? txt : `Échec : ${label} — ${txt}`)
    }
    if (parts.length) return parts.join(' · ')
  }
  return fallback
}

/* ASAV48 — lecture UNIQUE de la réponse `actions-groupees` du serveur
   ({traites: [id], echecs: [{id, raison}], nb_traites, nb_echecs}) partagée par
   `bulkAction`, `bulkEditStatut` et l'annulation : plus de toast « réussi »
   quand le serveur a répondu 200 avec des échecs. */
export function parseBulkResult(data) {
  const traites = Array.isArray(data?.traites) ? data.traites : []
  const echecs = Array.isArray(data?.echecs) ? data.echecs : []
  return {
    traites,
    echecs,
    nbTraites: data?.nb_traites ?? traites.length,
    nbEchecs: data?.nb_echecs ?? echecs.length,
  }
}

/* ASAV48 — édition de statut en masse : un seul appel atomique, puis pour
   chaque ligne traitée on lit les `statuts_suivants` SERVIS (jamais une copie
   du graphe) afin de ne proposer « Annuler » que si le retour est permis. */
export async function executerEditionStatut(api, selRows, statut) {
  const parId = new Map(selRows.map((r) => [String(r.id), r]))
  const { data } = await api.actionsGroupeesTickets(
    selRows.map((r) => r.id), 'statut', { statut })
  const res = parseBulkResult(data)
  const updated = await Promise.all(res.traites.map(async (tid) => {
    // NTUX37 — `before` capturé AVANT l'écriture (depuis `selRows`).
    const before = parId.get(String(tid))?.statut
    let annulable = false
    try {
      const r = await api.getTicket(tid)
      annulable = !!before && (r.data?.statuts_suivants ?? []).includes(before)
    } catch { annulable = false }
    return { id: tid, before, after: statut, annulable }
  }))
  const failed = res.echecs.map((e) => ({
    id: e.id,
    label: parId.get(String(e.id))?.reference,
    reason: e.raison || 'Transition refusée.',
  }))
  return { updated, failed }
}

// ASAV48 — annulation : ré-applique le statut AVANT par groupe et RAPPORTE le
// résultat serveur (traités / échecs) au lieu de présumer le succès.
export async function annulerEditionStatut(api, rows) {
  const idsParAvant = new Map()
  for (const r of rows) {
    if (!r.before) continue
    if (!idsParAvant.has(r.before)) idsParAvant.set(r.before, [])
    idsParAvant.get(r.before).push(r.id)
  }
  const reponses = await Promise.all(
    [...idsParAvant.entries()].map(
      ([statut, ids]) => api.actionsGroupeesTickets(ids, 'statut', { statut }),
    ),
  )
  return reponses.reduce((acc, { data }) => {
    const r = parseBulkResult(data)
    return { nbTraites: acc.nbTraites + r.nbTraites, nbEchecs: acc.nbEchecs + r.nbEchecs }
  }, { nbTraites: 0, nbEchecs: 0 })
}

/** Date locale du jour au format YYYY-MM-DD (comparaison de chaînes fiable). */
export function ymdLocal(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/**
 * ticketSlaEcheance — état de l'horloge de RÉSOLUTION. Fonction PURE.
 * @returns null si la société n'a pas activé le SLA (aucune échéance posée),
 *   sinon `{ dueIso, jours, depasse, enPause, ouvert }` où `jours` est le
 *   nombre de jours restants (négatif = retard).
 */
export function ticketSlaEcheance(ticket, now = new Date()) {
  const dueIso = ticket?.sla_due_at_effectif || ticket?.sla_due_at || null
  if (!dueIso) return null
  const due = new Date(`${String(dueIso).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(due.getTime())) return null
  const aujourdhui = new Date(`${ymdLocal(now)}T00:00:00`)
  const jours = Math.round((due - aujourdhui) / 86400000)
  const ouvert = !ticket?.annule && TICKET_OPEN_STATUSES.includes(ticket?.statut)
  return {
    dueIso: String(dueIso).slice(0, 10),
    jours,
    // Un ticket fermé n'est « en dépassement » que si le serveur l'a marqué
    // (`sla_breach`) : on ne recalcule pas un retard après coup sur une date
    // de clôture qu'on n'a pas.
    depasse: ouvert ? jours < 0 : !!ticket?.sla_breach,
    enPause: !!ticket?.en_attente_client,
    ouvert,
  }
}

/**
 * ticketSlaTri — clé de TRI par échéance. Fonction PURE.
 * Ordre voulu : les dépassements d'abord, puis l'échéance la plus proche, puis
 * les tickets sans SLA (jamais mélangés au milieu de ceux qui en ont un).
 */
export function ticketSlaTri(ticket, now = new Date()) {
  const e = ticketSlaEcheance(ticket, now)
  if (!e) return Number.MAX_SAFE_INTEGER
  return e.jours
}
