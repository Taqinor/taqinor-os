import { useEffect, useState, useCallback } from 'react'
import { Binoculars, Plus, ExternalLink } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB70 — Écran « Veille concurrentielle » (périmètre HONNÊTE, zéro scraping).
   ----------------------------------------------------------------------------
   L'API Ad Library de Meta ne couvre PAS les pubs commerciales marocaines : la
   veille est MANUELLE et OUTILLÉE. On suit des Pages concurrentes (avec un lien
   Ad Library web PROFOND à ouvrir soi-même) et on SAISIT les hooks/angles
   observés (« inspiration », jamais copiés verbatim). Une cadence par concurrent
   et la matière de brief sont agrégées côté serveur. Aucune collecte
   automatisée (règle #5 — GATED derrière un dossier tos_risk/).
   ========================================================================== */

const EMPTY_PAGE = { name: '', page_id: '', country: 'MA', website: '' }
const EMPTY_OBS = {
  competitor_page: '', observed_at: '', hook_text: '', angle: '',
  format: '', source_url: '',
}

export default function VeilleScreen() {
  const [pages, setPages] = useState([])
  const [veille, setVeille] = useState(null)
  const [pageDraft, setPageDraft] = useState(EMPTY_PAGE)
  const [obsDraft, setObsDraft] = useState(EMPTY_OBS)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      adsengineApi.competitors.list()
        .then(r => Array.isArray(r.data) ? r.data : (r.data?.results || []))
        .catch(() => []),
      adsengineApi.competitors.veille().then(r => r.data).catch(() => null),
    ]).then(([pgs, v]) => {
      setPages(pgs)
      setVeille(v)
    }).finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const addPage = async (e) => {
    e.preventDefault()
    setBusy(true); setErr(''); setMsg('')
    try {
      await adsengineApi.competitors.create(pageDraft)
      setMsg('Concurrent ajouté.')
      setPageDraft(EMPTY_PAGE)
      load()
    } catch {
      setErr('Ajout impossible (nom requis).')
    } finally {
      setBusy(false)
    }
  }

  const addObs = async (e) => {
    e.preventDefault()
    setBusy(true); setErr(''); setMsg('')
    try {
      await adsengineApi.competitorObservations.create(obsDraft)
      setMsg('Observation saisie.')
      setObsDraft(EMPTY_OBS)
      load()
    } catch {
      setErr('Saisie impossible (concurrent + date requis).')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-4" data-testid="ae-veille-screen">
      <h1 className="h4 d-flex align-items-center gap-2">
        <Binoculars size={20} aria-hidden="true" /> Veille concurrentielle
      </h1>

      {veille?.finding && (
        <div className="alert alert-info" data-testid="ae-veille-finding">
          {veille.finding.reason_fr}
        </div>
      )}
      {msg && <div className="alert alert-success" data-testid="ae-veille-msg">{msg}</div>}
      {err && <div className="alert alert-danger" data-testid="ae-veille-err">{err}</div>}

      {loading ? (
        <p data-testid="ae-veille-loading">Chargement…</p>
      ) : (
        <>
          <h2 className="h6 mt-3">Pages suivies</h2>
          <table className="table" data-testid="ae-veille-pages">
            <thead>
              <tr><th>Concurrent</th><th>Pays</th><th>Ad Library</th></tr>
            </thead>
            <tbody>
              {pages.map(p => (
                <tr key={p.id} data-testid={`ae-veille-page-${p.id}`}>
                  <td>{p.name}</td>
                  <td>{p.country}</td>
                  <td>
                    <a
                      href={p.ad_library_url} target="_blank" rel="noreferrer"
                      className="btn btn-sm btn-light"
                      data-testid={`ae-veille-link-${p.id}`}>
                      <ExternalLink size={14} aria-hidden="true" /> Ouvrir
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <form onSubmit={addPage} data-testid="ae-veille-page-form" noValidate className="row g-2 mb-4">
            <div className="col-md-4">
              <input
                className="form-control" placeholder="Nom du concurrent"
                data-testid="ae-veille-page-name" value={pageDraft.name}
                onChange={e => setPageDraft(d => ({ ...d, name: e.target.value }))} required />
            </div>
            <div className="col-md-3">
              <input
                className="form-control" placeholder="ID de Page (optionnel)"
                data-testid="ae-veille-page-id" value={pageDraft.page_id}
                onChange={e => setPageDraft(d => ({ ...d, page_id: e.target.value }))} />
            </div>
            <div className="col-md-2">
              <button type="submit" className="btn btn-primary" data-testid="ae-veille-page-add" disabled={busy}>
                <Plus size={15} aria-hidden="true" /> Suivre
              </button>
            </div>
          </form>

          <h2 className="h6">Saisir une observation (inspiration, jamais copiée)</h2>
          <form onSubmit={addObs} data-testid="ae-veille-obs-form" noValidate className="row g-2 mb-4">
            <div className="col-md-3">
              <select
                className="form-select" data-testid="ae-veille-obs-page"
                value={obsDraft.competitor_page}
                onChange={e => setObsDraft(d => ({ ...d, competitor_page: e.target.value }))} required>
                <option value="">— Concurrent —</option>
                {pages.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="col-md-2">
              <input
                type="date" className="form-control" data-testid="ae-veille-obs-date"
                value={obsDraft.observed_at}
                onChange={e => setObsDraft(d => ({ ...d, observed_at: e.target.value }))} required />
            </div>
            <div className="col-md-4">
              <input
                className="form-control" placeholder="Accroche reformulée"
                data-testid="ae-veille-obs-hook" value={obsDraft.hook_text}
                onChange={e => setObsDraft(d => ({ ...d, hook_text: e.target.value }))} />
            </div>
            <div className="col-md-2">
              <button type="submit" className="btn btn-primary" data-testid="ae-veille-obs-add" disabled={busy}>
                <Plus size={15} aria-hidden="true" /> Saisir
              </button>
            </div>
          </form>

          <h2 className="h6">Cadence par concurrent</h2>
          <ul data-testid="ae-veille-cadence">
            {(veille?.cadence || []).map(c => (
              <li key={c.competitor_id}>{c.competitor} — {c.total} observation(s)</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
