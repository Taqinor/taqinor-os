import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import creditApi from '../../api/creditApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   PACT50 — Segments crédit : RATTACHER un client à son segment (NTCRD13).

   L'écran « Conditions de paiement par segment » configure le délai et
   l'acompte D'UN SEGMENT ; sans rattachement, cette configuration reste
   décorative pour un client donné : le serveur résout la condition d'un client
   par `segment_du_client` → `condition_paiement_client`, et sans
   `SegmentClientCredit` la chaîne s'arrête à `None` (réglages société par
   défaut). Cet écran est le maillon manquant.

   Il affiche, pour chaque client rattaché, LA condition que le rattachement
   rend applicable — jointe sur la MÊME chaîne « segment » que le serveur.
   Un segment sans condition configurée est dit tel quel (« aucune condition
   configurée »), jamais rendu par un tiret muet.
   ========================================================================== */

function lignes(reponse) {
  const charge = reponse?.data
  if (Array.isArray(charge)) return charge
  if (Array.isArray(charge?.results)) return charge.results
  return []
}

export default function SegmentsClientPage() {
  const [rattachements, setRattachements] = useState([])
  const [conditions, setConditions] = useState([])
  const [clients, setClients] = useState([])
  const [erreur, setErreur] = useState(null)
  const [rechargement, setRechargement] = useState(0)
  const [form, setForm] = useState({ client: '', segment: '' })
  const [occupe, setOccupe] = useState(false)

  useEffect(() => {
    let vivant = true
    Promise.all([
      creditApi.getSegmentsClient(),
      creditApi.getConditionsSegment(),
      creditApi.getExposition(),
    ])
      .then(([resSegments, resConditions, resExposition]) => {
        if (!vivant) return
        setRattachements(lignes(resSegments))
        setConditions(lignes(resConditions))
        setClients(resExposition?.data?.resultats ?? [])
      })
      .catch((err) => {
        if (vivant) setErreur(frenchError(err, 'Chargement impossible.'))
      })
    return () => { vivant = false }
  }, [rechargement])

  const conditionParSegment = useMemo(() => {
    const table = {}
    conditions.forEach((c) => { table[c.segment] = c })
    return table
  }, [conditions])

  const nomClient = useMemo(() => {
    const table = {}
    clients.forEach((c) => { table[c.client_id] = c.client_nom })
    return table
  }, [clients])

  async function rattacher(event) {
    event.preventDefault()
    if (occupe) return
    setOccupe(true)
    setErreur(null)
    try {
      await creditApi.createSegmentClient({
        client: form.client, segment: form.segment,
      })
      setForm({ client: '', segment: '' })
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(frenchError(err, 'Rattachement impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  async function changerSegment(id, segment) {
    setErreur(null)
    try {
      await creditApi.updateSegmentClient(id, { segment })
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(frenchError(err, 'Changement de segment impossible.'))
    }
  }

  async function retirer(id) {
    setErreur(null)
    try {
      await creditApi.deleteSegmentClient(id)
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(frenchError(err, 'Retrait impossible.'))
    }
  }

  const segments = conditions.map((c) => c.segment)

  return (
    <div className="credit-segments" data-testid="credit-segments-client">
      <h3>Segments crédit des clients</h3>
      <p>
        Rattacher un client à un segment rend applicables les{' '}
        <Link to="/credit/conditions">conditions de paiement de ce segment</Link>{' '}
        (délai, acompte, mode de hold) — sans rattachement, ces conditions ne
        s’appliquent à personne.
      </p>
      {erreur && <p className="credit-segments__error" role="alert">{erreur}</p>}

      {segments.length === 0 && (
        <p>
          Aucun segment n’est configuré : commencez par créer une condition de
          paiement par segment.
        </p>
      )}

      {rattachements.length === 0 ? (
        <p>Aucun client rattaché à un segment.</p>
      ) : (
        <table className="credit-segments__table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Segment</th>
              <th>Délai de paiement</th>
              <th>Acompte</th>
              <th>Mode de hold</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rattachements.map((r) => {
              const condition = conditionParSegment[r.segment]
              return (
                <tr key={r.id} data-testid={`segment-client-${r.client}`}>
                  <td>{nomClient[r.client] || `#${r.client}`}</td>
                  <td>{r.segment}</td>
                  <td>
                    {condition
                      ? `${condition.delai_paiement_jours} j`
                      : 'aucune condition configurée'}
                  </td>
                  <td>
                    {condition && condition.pct_acompte_defaut !== null
                      && condition.pct_acompte_defaut !== undefined
                      ? `${condition.pct_acompte_defaut} %`
                      : 'défaut société'}
                  </td>
                  <td>
                    {condition && condition.mode_hold_override
                      ? condition.mode_hold_override
                      : 'défaut société'}
                  </td>
                  <td>
                    <label htmlFor={`segment-select-${r.id}`}>
                      Segment de {nomClient[r.client] || `#${r.client}`}
                    </label>
                    <select
                      id={`segment-select-${r.id}`}
                      value={r.segment}
                      onChange={(e) => changerSegment(r.id, e.target.value)}
                    >
                      {(segments.includes(r.segment)
                        ? segments
                        : [r.segment, ...segments]
                      ).map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                    <button type="button" onClick={() => retirer(r.id)}>
                      Retirer
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}

      <form onSubmit={rattacher} className="credit-segments__form">
        <label htmlFor="rattachement-client">Client à rattacher</label>
        <select
          id="rattachement-client"
          value={form.client}
          onChange={(e) => setForm({ ...form, client: e.target.value })}
          required
        >
          <option value="">Choisir un client</option>
          {clients.map((c) => (
            <option key={c.client_id} value={c.client_id}>{c.client_nom}</option>
          ))}
        </select>
        <label htmlFor="rattachement-segment">Segment</label>
        <select
          id="rattachement-segment"
          value={form.segment}
          onChange={(e) => setForm({ ...form, segment: e.target.value })}
          required
        >
          <option value="">Choisir un segment</option>
          {segments.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <button type="submit" disabled={occupe}>Rattacher</button>
      </form>
    </div>
  )
}
