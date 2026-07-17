import { Fragment, useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'
import ReglesUpsell from './ReglesUpsell'

/* ============================================================================
   NTMKT9 — Comptes de fidélité (points, paliers, FG240) + historique de
   mouvements + onglet Règles d'upsell (FG241).
   ----------------------------------------------------------------------------
   `marketing/comptes-fidelite/` (lecture — points/palier recalculés côté
   serveur, `crediter` gère les gains), `marketing/mouvements-fidelite/`
   filtré côté client par `compte`. Lecture seule depuis la fiche client
   (lien croisé) — pas de duplication d'écran client ici. `ReglesUpsell.jsx`
   partage cet écran via un onglet (le sous-menu Marketing garde 9 entrées,
   NTMKT1 — pas de route dédiée pour ce second onglet).
   ========================================================================== */

const PALIER_LABEL = { bronze: 'Bronze', argent: 'Argent', or: 'Or', platine: 'Platine' }

export default function FideliteList() {
  const [onglet, setOnglet] = useState('comptes')
  const [comptes, setComptes] = useState([])
  const [loading, setLoading] = useState(true)
  const [ouvertId, setOuvertId] = useState(null)
  const [mouvements, setMouvements] = useState([])
  const [points, setPoints] = useState('')
  const [motif, setMotif] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.comptesFidelite.list()
      .then(r => setComptes(marketingApi.unwrapList(r)))
      .catch(() => setComptes([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const ouvrir = (compte) => {
    if (ouvertId === compte.id) { setOuvertId(null); return }
    setOuvertId(compte.id)
    marketingApi.mouvementsFidelite.list({ compte: compte.id })
      .then(r => setMouvements(marketingApi.unwrapList(r)))
      .catch(() => setMouvements([]))
  }

  const crediter = async (compteId) => {
    if (!points) return
    setErr('')
    try {
      await marketingApi.comptesFidelite.crediter(compteId, { points: Number(points), motif })
      setPoints(''); setMotif('')
      load()
      marketingApi.mouvementsFidelite.list({ compte: compteId })
        .then(r => setMouvements(marketingApi.unwrapList(r)))
    } catch {
      setErr('Créditation impossible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h2>Fidélité</h2></div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button className={`btn ${onglet === 'comptes' ? 'btn-primary' : 'btn-light'}`}
          data-testid="fidelite-onglet-comptes" onClick={() => setOnglet('comptes')}>
          Comptes de fidélité
        </button>
        <button className={`btn ${onglet === 'upsell' ? 'btn-primary' : 'btn-light'}`}
          data-testid="fidelite-onglet-upsell" onClick={() => setOnglet('upsell')}>
          Règles d'upsell
        </button>
      </div>

      {onglet === 'upsell' && <ReglesUpsell />}

      {onglet === 'comptes' && err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {onglet === 'comptes' && (loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="fidelite-table">
            <thead><tr><th>Client</th><th>Points</th><th>Palier</th><th /></tr></thead>
            <tbody>
              {comptes.map(c => (
                <Fragment key={c.id}>
                  <tr data-testid="fidelite-row" style={{ cursor: 'pointer' }}
                    onClick={() => ouvrir(c)}>
                    <td>Client #{c.client_id}</td>
                    <td>{c.points}</td>
                    <td>{PALIER_LABEL[c.palier] || c.palier}</td>
                    <td>{ouvertId === c.id ? '▲' : '▼'}</td>
                  </tr>
                  {ouvertId === c.id && (
                    <tr>
                      <td colSpan={4}>
                        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: 8 }}
                          onClick={e => e.stopPropagation()}>
                          <input type="number" className="form-input" placeholder="Points"
                            data-testid="fidelite-credit-points" value={points}
                            onChange={e => setPoints(e.target.value)} style={{ maxWidth: 120 }} />
                          <input className="form-input" placeholder="Motif"
                            data-testid="fidelite-credit-motif" value={motif}
                            onChange={e => setMotif(e.target.value)} />
                          <button className="btn btn-primary" type="button"
                            data-testid="fidelite-crediter" onClick={() => crediter(c.id)}>
                            Créditer
                          </button>
                        </div>
                        <table className="data-table" data-testid="mouvements-table">
                          <thead><tr><th>Points</th><th>Motif</th><th>Date</th></tr></thead>
                          <tbody>
                            {mouvements.map(m => (
                              <tr key={m.id}>
                                <td>{m.points > 0 ? `+${m.points}` : m.points}</td>
                                <td>{m.motif || '—'}</td>
                                <td>{m.date_creation ? new Date(m.date_creation).toLocaleDateString('fr-FR') : '—'}</td>
                              </tr>
                            ))}
                            {mouvements.length === 0 && (
                              <tr><td colSpan={3} style={{ textAlign: 'center', color: '#64748b' }}>
                                Aucun mouvement
                              </td></tr>
                            )}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {comptes.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun compte de fidélité
                </td></tr>
              )}
            </tbody>
          </table>
        ))}
    </div>
  )
}
