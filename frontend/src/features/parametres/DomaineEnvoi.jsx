import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   NTMKT10 — Paramètres → Marketing : domaine d'envoi (SPF/DKIM/DMARC, XMKT33).
   ----------------------------------------------------------------------------
   `marketing/domaines-envoi/` (CRUD), `enregistrements-attendus` (les 3
   enregistrements DNS attendus, affichés AVANT vérification), `verifier`
   (relance le lookup DNS réel côté serveur — jamais d'appel réseau ici).
   Lien vers `SupportsOffline.jsx` (XMKT29, `frontend/src/features/marketing/`)
   pour les flyers/QR, regroupés sous la même page Paramètres → Marketing.
   ========================================================================== */

export default function DomaineEnvoi() {
  const navigate = useNavigate()
  const [domaines, setDomaines] = useState([])
  const [loading, setLoading] = useState(true)
  const [nouveauDomaine, setNouveauDomaine] = useState('')
  const [attendusParId, setAttendusParId] = useState({})
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.domainesEnvoi.list()
      .then(r => setDomaines(marketingApi.unwrapList(r)))
      .catch(() => setDomaines([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const ajouter = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await marketingApi.domainesEnvoi.create({ domaine: nouveauDomaine })
      setNouveauDomaine('')
      load()
    } catch {
      setErr('Ajout impossible.')
    }
  }

  const revoir = async (id) => {
    setErr('')
    try {
      const r = await marketingApi.domainesEnvoi.enregistrementsAttendus(id)
      setAttendusParId(m => ({ ...m, [id]: r.data }))
    } catch {
      setErr('Impossible de lire les enregistrements attendus.')
    }
  }

  const revérifier = async (id) => {
    setErr('')
    try {
      await marketingApi.domainesEnvoi.verifier(id)
      load()
    } catch {
      setErr('Vérification impossible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Paramètres — Marketing : domaine d'envoi</h2>
        <button className="btn btn-light" data-testid="voir-supports-offline"
          onClick={() => navigate('/marketing/supports-offline')}>
          Supports offline (QR)
        </button>
      </div>

      <form onSubmit={ajouter} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <input className="form-input" data-testid="domaine-nouveau"
          placeholder="ex. votredomaine.ma" required value={nouveauDomaine}
          onChange={e => setNouveauDomaine(e.target.value)} style={{ flex: '1 1 220px' }} />
        <button type="submit" className="btn btn-primary" data-testid="domaine-ajouter">
          Ajouter
        </button>
      </form>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="domaines-table">
            <thead>
              <tr><th>Domaine</th><th>SPF</th><th>DKIM</th><th>DMARC</th>
                <th>Authentifié</th><th>Dernière vérif.</th><th /></tr>
            </thead>
            <tbody>
              {domaines.map(d => (
                <tr key={d.id} data-testid="domaine-row">
                  <td>{d.domaine}</td>
                  <td>{d.spf_verifie ? '✓' : '✗'}</td>
                  <td>{d.dkim_verifie ? '✓' : '✗'}</td>
                  <td>{d.dmarc_verifie ? '✓' : '✗'}</td>
                  <td>{d.authentifie ? 'Oui' : 'Non'}</td>
                  <td>{d.derniere_verification_le
                    ? formatDateTime(d.derniere_verification_le) : 'Jamais'}</td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button className="btn btn-light" type="button"
                      data-testid="domaine-attendus" onClick={() => revoir(d.id)}>
                      Enregistrements attendus
                    </button>
                    <button className="btn btn-primary" type="button"
                      data-testid="domaine-reverifier" onClick={() => revérifier(d.id)}>
                      Revérifier
                    </button>
                  </td>
                </tr>
              ))}
              {domaines.length === 0 && (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun domaine
                </td></tr>
              )}
            </tbody>
          </table>
        )}

      {domaines.map(d => attendusParId[d.id] && (
        <div key={`attendus-${d.id}`} data-testid={`domaine-attendus-${d.id}`}
          style={{ marginTop: 8, border: '1px dashed #cbd5e1', borderRadius: 8, padding: '0.6rem' }}>
          <strong>{d.domaine}</strong> — enregistrements attendus :
          <ul>
            {Object.entries(attendusParId[d.id]).map(([cle, rec]) => (
              <li key={cle}>
                {cle.toUpperCase()} — {rec.type} {rec.hote} → {rec.valeur_attendue}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}
