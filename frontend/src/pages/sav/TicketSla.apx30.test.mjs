// APX30 — SLA par ticket : echeance + compte-a-rebours, rouge PERSISTANT.
// ----------------------------------------------------------------------------
// La logique d'echeance est PURE et exportee : elle se teste sur des tickets
// reels, sans navigateur ni node_modules. Le reste (rendu ligne/carte/detail,
// tri, multi-tenant) est verrouille contre la SOURCE.
//   node --test src/pages/sav/TicketSla.apx30.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const SRC = lf(readFileSync(join(HERE, 'TicketsPage.jsx'), 'utf8'))
const SERIALIZER = lf(readFileSync(
  join(HERE, '../../../../backend/django_core/apps/sav/serializers.py'), 'utf8'))

/* ── La logique PURE, rejouee (le composant n'est pas importable sans bundler
      JSX dans cette lane). Le test « fidele a la source » ci-dessous epingle
      le texte exact de la fonction. ── */
const OUVERTS = ['nouveau', 'planifie', 'en_cours']
const ymdLocal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
function ticketSlaEcheance(ticket, now = new Date()) {
  const dueIso = ticket?.sla_due_at_effectif || ticket?.sla_due_at || null
  if (!dueIso) return null
  const due = new Date(`${String(dueIso).slice(0, 10)}T00:00:00`)
  if (Number.isNaN(due.getTime())) return null
  const aujourdhui = new Date(`${ymdLocal(now)}T00:00:00`)
  const jours = Math.round((due - aujourdhui) / 86400000)
  const ouvert = !ticket?.annule && OUVERTS.includes(ticket?.statut)
  return {
    dueIso: String(dueIso).slice(0, 10),
    jours,
    depasse: ouvert ? jours < 0 : !!ticket?.sla_breach,
    enPause: !!ticket?.en_attente_client,
    ouvert,
  }
}

// Un « maintenant » FIGE : sinon ce test devient flaky autour de minuit
// (classe de bug connue du depot).
const MAINTENANT = new Date('2026-08-01T10:00:00')

test('APX30 : aucune echeance quand la societe n\'a pas active le SLA', () => {
  assert.equal(ticketSlaEcheance({ statut: 'nouveau' }, MAINTENANT), null)
  assert.equal(ticketSlaEcheance({ statut: 'nouveau', sla_due_at: null }, MAINTENANT), null)
})

test('APX30 : compte-a-rebours en jours, positif avant l\'echeance', () => {
  const e = ticketSlaEcheance({ statut: 'en_cours', sla_due_at: '2026-08-04' }, MAINTENANT)
  assert.equal(e.jours, 3)
  assert.equal(e.depasse, false)
  assert.equal(e.ouvert, true)
  assert.equal(ticketSlaEcheance({ statut: 'en_cours', sla_due_at: '2026-08-01' }, MAINTENANT).jours, 0)
})

test('APX30 : un ticket OUVERT dont l\'echeance est passee est en depassement', () => {
  const e = ticketSlaEcheance({ statut: 'en_cours', sla_due_at: '2026-07-30' }, MAINTENANT)
  assert.equal(e.jours, -2)
  assert.equal(e.depasse, true)
})

test('APX30 : le depassement RESTE marque apres resolution/cloture (tracabilite)', () => {
  for (const statut of ['resolu', 'cloture']) {
    const e = ticketSlaEcheance(
      { statut, sla_due_at: '2026-07-20', sla_breach: true }, MAINTENANT)
    assert.equal(e.ouvert, false)
    assert.equal(e.depasse, true, `le rouge doit persister sur un ticket ${statut}`)
  }
  // ... et un ticket resolu DANS les temps n'est jamais marque a posteriori.
  const propre = ticketSlaEcheance(
    { statut: 'resolu', sla_due_at: '2026-07-20', sla_breach: false }, MAINTENANT)
  assert.equal(propre.depasse, false)
})

test('APX30 : l\'echeance EFFECTIVE (pause client, XSAV5) prime sur la brute', () => {
  const t = {
    statut: 'en_cours',
    sla_due_at: '2026-07-28',            // brute : deja depassee
    sla_due_at_effectif: '2026-08-05',   // decalee des jours de pause
    en_attente_client: true,
  }
  const e = ticketSlaEcheance(t, MAINTENANT)
  assert.equal(e.dueIso, '2026-08-05')
  assert.equal(e.depasse, false, 'une pause client ne doit pas compter comme un retard')
  assert.equal(e.enPause, true)
})

test('APX30 : un ticket ANNULE n\'est jamais « ouvert »', () => {
  const e = ticketSlaEcheance(
    { statut: 'en_cours', annule: true, sla_due_at: '2026-07-01' }, MAINTENANT)
  assert.equal(e.ouvert, false)
  assert.equal(e.depasse, false) // pas de sla_breach serveur
})

test('APX30 : le TRI remonte les depassements et rejette les sans-SLA en fin', () => {
  const tickets = [
    { id: 'sans', statut: 'nouveau' },
    { id: 'dans3j', statut: 'en_cours', sla_due_at: '2026-08-04' },
    { id: 'retard2j', statut: 'en_cours', sla_due_at: '2026-07-30' },
    { id: 'aujourdhui', statut: 'nouveau', sla_due_at: '2026-08-01' },
  ]
  const cle = (t) => {
    const e = ticketSlaEcheance(t, MAINTENANT)
    return e ? e.jours : Number.MAX_SAFE_INTEGER
  }
  const ordre = [...tickets].sort((a, b) => cle(a) - cle(b)).map((t) => t.id)
  assert.deepEqual(ordre, ['retard2j', 'aujourdhui', 'dans3j', 'sans'])
})

test('APX30 : la copie de logique de ce test est fidele a la source', () => {
  assert.match(SRC, /export function ticketSlaEcheance\(ticket, now = new Date\(\)\) \{/)
  assert.match(SRC, /const dueIso = ticket\?\.sla_due_at_effectif \|\| ticket\?\.sla_due_at \|\| null/)
  assert.match(SRC, /depasse: ouvert \? jours < 0 : !!ticket\?\.sla_breach,/)
  assert.match(SRC, /export function ticketSlaTri\(ticket, now = new Date\(\)\) \{/)
})

test('APX30 : ZERO backend — tous les champs lus existent deja au serializer', () => {
  for (const champ of [
    'sla_due_at', 'sla_due_at_effectif', 'sla_breach',
    'jours_pause', 'en_attente_client', 'attente_depuis', 'date_premiere_reponse',
  ]) {
    assert.match(SERIALIZER, new RegExp(`\\b${champ}\\b`), `${champ} absent du serializer SAV`)
  }
  // Aucun nouvel appel reseau introduit par cette tache.
  // L'extraction s'arrete a la FIN de la DERNIERE declaration APX30, jamais sur
  // un repere voisin : ce test bornait autrefois le bloc par « export function
  // TicketDetail », qui n'appartient PAS a APX30 et ne le suivait que par
  // hasard. Des qu'une tache voisine (PACT142, memo vocal) s'est intercalee, la
  // garde avalait son appel reseau parfaitement legitime. Bornes recalculees
  // depuis les declarations APX30 elles-memes : tout ce que APX30 possede reste
  // couvert, y compris un helper ajoute au milieu du bloc.
  const DECLARATIONS_APX30 = [
    'function ymdLocal(d) {',
    'export function ticketSlaEcheance(ticket, now = new Date()) {',
    'export function ticketSlaTri(ticket, now = new Date()) {',
    'export function TicketSlaEcheanceChip({ ticket }) {',
    'export function TicketPremiereReponseChip({ ticket }) {',
  ]
  const finDeclaration = (entete) => {
    const i = SRC.indexOf(entete)
    assert.notEqual(i, -1, `declaration APX30 absente de la source : ${entete}`)
    // Les declarations sont au premier niveau du module : leur accolade
    // fermante est seule en colonne 0.
    const fin = SRC.indexOf('\n}\n', i)
    assert.notEqual(fin, -1, `fin de declaration APX30 introuvable : ${entete}`)
    return fin + 2
  }
  const debut = SRC.indexOf('APX30 — SLA PAR TICKET')
  assert.notEqual(debut, -1, 'la banniere APX30 a disparu de la source')
  const bloc = SRC.slice(debut, Math.max(...DECLARATIONS_APX30.map(finDeclaration)))
  // Un bloc tronque (ou vide) ferait passer la garde en silence : on exige que
  // CHAQUE declaration APX30 soit reellement dans l'extrait analyse.
  for (const entete of DECLARATIONS_APX30) {
    assert.ok(bloc.includes(entete), `le bloc APX30 extrait ne couvre plus : ${entete}`)
  }
  assert.doesNotMatch(bloc, /api\.|savApi|fetch\(|useEffect/)
})

test('APX30 : DEUX horloges distinctes — 1re reponse et resolution', () => {
  assert.match(SRC, /export function TicketPremiereReponseChip\(\{ ticket \}\) \{/)
  assert.match(SRC, /if \(ticket\.date_premiere_reponse\) return null/)
  assert.match(SRC, /1ʳᵉ réponse à faire/)
  assert.match(SRC, /à résoudre sous \$\{e\.jours\} j/)
})

test('APX30 : les chips sont rendues en LIGNE, en CARTE et au DETAIL', () => {
  assert.equal((SRC.match(/<TicketSlaEcheanceChip ticket=/g) || []).length, 3)
  assert.equal((SRC.match(/<TicketPremiereReponseChip ticket=/g) || []).length, 3)
})

test('APX30 : la colonne SLA devient triable par echeance', () => {
  const colonne = SRC.slice(SRC.indexOf("id: 'sla',"))
  const bloc = colonne.slice(0, colonne.indexOf('\n    },'))
  assert.match(bloc, /sortable: true/)
  assert.match(bloc, /accessor: \(row\) => ticketSlaTri\(row\)/)
  assert.match(bloc, /exportValue:/)
})

test('APX30 : les statuts ouverts viennent de la source unique, jamais d\'un litteral recopie', () => {
  assert.match(SRC, /TICKET_OPEN_STATUSES,\s*\n\s*TICKET_TYPES,/)
  // L'ancien litteral en dur de la colonne a disparu.
  assert.doesNotMatch(SRC, /\['nouveau', 'planifie', 'en_cours'\]\.includes\(row\.statut\)/)
})

test('APX30 : le panneau detail passe a 32rem (un seul hit, comme verifie)', () => {
  assert.equal((SRC.match(/w-\[32rem\]/g) || []).length, 1)
  assert.doesNotMatch(SRC, /w-\[26rem\]/)
})
