import { useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT10 — Supports offline (flyers, bâches, véhicules) avec QR de scan
   (XMKT29).
   ----------------------------------------------------------------------------
   `marketing/supports-offline/` (création : nom + URL cible auto-taguée
   utm_source=offline côté serveur), `<id>/qr/` (SVG téléchargeable, réutilise
   `stock.labels.qr_svg`), `nb_scans` par support (compteur de scans→leads).
   NOTE : la création via cette API dépend d'un correctif backend en attente
   (`SupportOfflineSerializer.url_cible` marqué à tort lecture-seule) —
   suivi séparément, hors périmètre frontend de cette tâche.
   ========================================================================== */

export default function SupportsOffline() {
  const [supports, setSupports] = useState([])
  const [loading, setLoading] = useState(true)
  const [nom, setNom] = useState('')
  const [urlCible, setUrlCible] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.supportsOffline.list()
      .then(r => setSupports(marketingApi.unwrapList(r)))
      .catch(() => setSupports([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const creer = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await marketingApi.supportsOffline.create({ nom, url_cible: urlCible })
      setNom(''); setUrlCible('')
      load()
    } catch {
      setErr('Création impossible.')
    }
  }

  const telechargerQr = async (id, nomSupport) => {
    setErr('')
    try {
      const r = await marketingApi.supportsOffline.qr(id)
      marketingApi.downloadBlob(r.data, `qr-${nomSupport || id}.svg`)
    } catch {
      setErr('QR indisponible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header"><h2>Supports offline (QR)</h2></div>

      <form onSubmit={creer} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap',
        marginBottom: '1rem' }}>
        <input className="form-input" data-testid="support-nom"
          placeholder="Nom (ex. « Flyer SIAM 2026 »)" required value={nom}
          onChange={e => setNom(e.target.value)} style={{ flex: '1 1 220px' }} />
        <input className="form-input" data-testid="support-url"
          placeholder="URL cible" required value={urlCible}
          onChange={e => setUrlCible(e.target.value)} style={{ flex: '1 1 260px' }} />
        <button type="submit" className="btn btn-primary" data-testid="support-creer">
          Créer
        </button>
      </form>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="supports-table">
            <thead><tr><th>Nom</th><th>URL cible</th><th>Scans</th><th /></tr></thead>
            <tbody>
              {supports.map(s => (
                <tr key={s.id} data-testid="support-row">
                  <td>{s.nom}</td>
                  <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.url_cible}
                  </td>
                  <td>{s.nb_scans ?? 0}</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      data-testid="support-qr" onClick={() => telechargerQr(s.id, s.nom)}>
                      Télécharger le QR
                    </button>
                  </td>
                </tr>
              ))}
              {supports.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun support offline
                </td></tr>
              )}
            </tbody>
          </table>
        )}
    </div>
  )
}
