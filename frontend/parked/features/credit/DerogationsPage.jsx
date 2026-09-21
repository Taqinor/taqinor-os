import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import creditApi from '../../api/creditApi'
import { formatMAD, formatDateTime } from '../../lib/format'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   WIR55 / NTCRD9 — Écran « Dérogations crédit » : liste des demandes et
   traitement (approuver / rejeter) réservé Directeur/Administrateur. Le backend
   re-vérifie (`IsDirecteurOrAdmin`) ; l'UI dégrade proprement sur refus.

   PACT49 / NTCRD26 — le WORKFLOW ci-dessus n'est pas le RAPPORT : la vue
   `rapport_derogations_view` produit depuis toujours un rapport sur période
   (délai de traitement en heures, export XLSX/CSV) qu'aucun écran n'ouvrait.
   Il est ajouté ici, sous la file de traitement, avec les colonnes EXACTES
   documentées côté serveur (`views.rapport_derogations_view::header`) — la
   même liste, dans le même ordre, à l'écran et dans l'export. Le test lit ce
   `header` DANS le fichier serveur : les deux ne peuvent plus diverger.
   ========================================================================== */

// Colonnes STABLES du serveur (jamais renommées en silence) — ordre compris.
const COLONNES_RAPPORT = [
  'ID', 'Client', 'Montant', 'Statut', 'Demandeur', 'Décideur',
  'Créée le', 'Décidée le', 'Délai (h)',
]

const dateOuTiret = (valeur) => (valeur ? formatDateTime(valeur) : '—')

export default function DerogationsPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [periode, setPeriode] = useState({ date_debut: '', date_fin: '' })
  const [rapport, setRapport] = useState(null)
  const [rapportErreur, setRapportErreur] = useState(null)

  const charger = useCallback(() => {
    let alive = true
    setLoading(true)
    creditApi
      .getDerogations()
      .then((res) => {
        if (alive) {
          setRows(res.data?.results ?? res.data ?? [])
          setError(null)
        }
      })
      .catch(() => {
        if (alive) setError('Impossible de charger les dérogations.')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount: reuses the shared `charger` refresh helper
  useEffect(() => charger(), [charger])

  async function decider(id, action) {
    setBusyId(id)
    setError(null)
    try {
      if (action === 'approuver') await creditApi.approuverDerogation(id)
      else await creditApi.rejeterDerogation(id)
      charger()
    } catch {
      setError('Décision impossible (droits Directeur/Administrateur requis).')
    } finally {
      setBusyId(null)
    }
  }

  const parametresPeriode = () => ({
    date_debut: periode.date_debut || undefined,
    date_fin: periode.date_fin || undefined,
  })

  async function calculerRapport(event) {
    event.preventDefault()
    setRapportErreur(null)
    try {
      const res = await creditApi.getRapportDerogations(parametresPeriode())
      setRapport(res.data)
    } catch (err) {
      setRapport(null)
      setRapportErreur(frenchError(err, 'Rapport indisponible.'))
    }
  }

  async function exporter(format) {
    setRapportErreur(null)
    try {
      const res = await creditApi.exportRapportDerogations(parametresPeriode(), format)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const lien = document.createElement('a')
      lien.href = url
      lien.download = `derogations_credit.${format}`
      lien.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setRapportErreur(frenchError(err, 'Export impossible.'))
    }
  }

  if (loading) return <div className="credit-derogations">Chargement…</div>

  return (
    <div className="credit-derogations" data-testid="credit-derogations">
      {error && <p className="credit-derogations__error" role="alert">{error}</p>}
      {rows.length === 0 ? (
        <p>Aucune demande de dérogation.</p>
      ) : (
        <table className="credit-derogations__table">
          <thead>
            <tr>
              <th>Client</th>
              <th>Montant</th>
              <th>Motif</th>
              <th>Statut</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <td>
                  {d.client ? (
                    <Link to={`/credit/clients/${d.client}`}>#{d.client}</Link>
                  ) : '—'}
                </td>
                <td>{formatMAD(d.montant_demande)}</td>
                <td>{d.motif || '—'}</td>
                <td>{d.statut}{d.est_valide ? ' (valide)' : ''}</td>
                <td>
                  {d.statut === 'en_attente' ? (
                    <>
                      <button
                        type="button"
                        disabled={busyId === d.id}
                        onClick={() => decider(d.id, 'approuver')}
                      >
                        Approuver
                      </button>
                      <button
                        type="button"
                        disabled={busyId === d.id}
                        onClick={() => decider(d.id, 'rejeter')}
                      >
                        Rejeter
                      </button>
                    </>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <section className="credit-derogations__rapport" data-testid="credit-derogations-rapport">
        <h3>Rapport sur période</h3>
        {rapportErreur && (
          <p className="credit-derogations__error" role="alert">{rapportErreur}</p>
        )}
        <form onSubmit={calculerRapport}>
          <label htmlFor="rapport-debut">Du</label>
          <input
            id="rapport-debut"
            type="date"
            value={periode.date_debut}
            onChange={(e) => setPeriode({ ...periode, date_debut: e.target.value })}
          />
          <label htmlFor="rapport-fin">Au</label>
          <input
            id="rapport-fin"
            type="date"
            value={periode.date_fin}
            onChange={(e) => setPeriode({ ...periode, date_fin: e.target.value })}
          />
          <button type="submit">Calculer le rapport</button>
        </form>

        {rapport && (
          <div data-testid="credit-derogations-rapport-resultat">
            <p>
              {rapport.lignes.length} dérogation(s) — {rapport.nb_approuvees} approuvée(s)
              — délai moyen de traitement :{' '}
              {rapport.delai_traitement_moyen_h === null
                ? 'aucune décision sur la période'
                : `${rapport.delai_traitement_moyen_h} h`}
            </p>
            <table className="credit-derogations__rapport-table">
              <thead>
                <tr>
                  {COLONNES_RAPPORT.map((colonne) => (
                    <th key={colonne}>{colonne}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rapport.lignes.map((ligne) => (
                  <tr key={ligne.id}>
                    <td>{ligne.id}</td>
                    <td>{ligne.client_id}</td>
                    <td>{formatMAD(ligne.montant_demande)}</td>
                    <td>{ligne.statut}</td>
                    <td>{ligne.demandeur || '—'}</td>
                    <td>{ligne.decideur || '—'}</td>
                    <td>{dateOuTiret(ligne.date_creation)}</td>
                    <td>{dateOuTiret(ligne.date_decision)}</td>
                    <td>
                      {ligne.delai_traitement_h === null
                        || ligne.delai_traitement_h === undefined
                        ? '—'
                        : ligne.delai_traitement_h}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button type="button" onClick={() => exporter('xlsx')}>
              Exporter (.xlsx)
            </button>
            <button type="button" onClick={() => exporter('csv')}>
              Exporter (.csv)
            </button>
          </div>
        )}
      </section>
    </div>
  )
}
