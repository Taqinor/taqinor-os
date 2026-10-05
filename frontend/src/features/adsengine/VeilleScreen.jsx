import { useEffect, useState, useCallback } from 'react'
import { Binoculars, Plus, ExternalLink } from 'lucide-react'
import adsengineApi from './adsengineApi'
import VeilleDecouverte from './VeilleDecouverte'

/* ============================================================================
   PUB70 / PLAN_VEILLE — Écran « Veille concurrentielle ».
   ----------------------------------------------------------------------------
   La couverture de l'API Ad Library de Meta dépend du PAYS (servie par
   `veille/couverture/`, VEIL10) : pubs commerciales servies pour l'Union
   européenne, Royaume-Uni à confirmer, politique seulement ailleurs (dont le
   Maroc). Deux onglets :
   - « Découverte » (défaut, VEIL30) : trouver les vendeurs par mots-clés × pays
     via l'API officielle, à la demande, plafonds explicites ;
   - « Saisie manuelle » (PUB70) : on suit des Pages concurrentes (lien Ad
     Library web PROFOND à ouvrir soi-même) et on SAISIT les hooks/angles
     observés (« inspiration », jamais copiés verbatim). Aucune collecte du
     site web (règle #5 — GATED derrière un dossier tos_risk/).
   ========================================================================== */

const EMPTY_PAGE = { name: '', page_id: '', country: 'MA', website: '' }
const EMPTY_OBS = {
  competitor_page: '', observed_at: '', hook_text: '', angle: '',
  format: '', source_url: '',
}

const LIBELLES_ACCES = {
  non_configure: 'Accès Ad Library non configuré.',
  desactive: 'Accès Ad Library désactivé.',
  non_autorise: "Cette société n'est pas autorisée à lancer une découverte.",
  pret: 'Accès Ad Library prêt.',
  expire_bientot: 'Accès Ad Library prêt — le jeton expire bientôt.',
  invalide: 'Accès Ad Library invalide : jeton refusé par Meta.',
}
const LIBELLES_STATUT_PAYS = {
  couvert: 'Pubs commerciales couvertes',
  a_confirmer: 'À confirmer',
  non_couvert: 'Politique seulement',
}

function BandeauCouverture({ couverture }) {
  if (!couverture) return null
  const parStatut = {}
  for (const ligne of couverture.couverture || []) {
    (parStatut[ligne.statut] ||= []).push(ligne)
  }
  const acces = couverture.acces || {}
  return (
    <div className="alert alert-info" data-testid="ae-veille-couverture">
      {Object.entries(parStatut).map(([statut, lignes]) => (
        <div key={statut} data-testid={`ae-veille-couverture-${statut}`}>
          <strong>{LIBELLES_STATUT_PAYS[statut] || statut}</strong>
          {' : '}{lignes.map(l => l.pays).join(', ')}
          {' — '}{lignes[0].motif_fr}
        </div>
      ))}
      <div data-testid="ae-veille-acces" data-etat={acces.etat}>
        {LIBELLES_ACCES[acces.etat] || acces.etat}
        {acces.expire_le && ` (expire le ${new Date(acces.expire_le).toLocaleDateString('fr-FR')})`}
      </div>
    </div>
  )
}

const ONGLETS = [
  { cle: 'decouverte', libelle: 'Découverte' },
  { cle: 'manuel', libelle: 'Saisie manuelle' },
]

export default function VeilleScreen() {
  const [onglet, setOnglet] = useState('decouverte')
  const [couverture, setCouverture] = useState(null)
  const [decouverteId, setDecouverteId] = useState(null)

  useEffect(() => {
    adsengineApi.veille.couverture()
      .then(r => setCouverture(r.data))
      .catch(() => setCouverture(null))
  }, [])

  return (
    <div className="p-4" data-testid="ae-veille-screen">
      <h1 className="h4 d-flex align-items-center gap-2">
        <Binoculars size={20} aria-hidden="true" /> Veille concurrentielle
      </h1>
      <BandeauCouverture couverture={couverture} />
      <ul className="nav nav-tabs mb-3" role="tablist">
        {ONGLETS.map(o => (
          <li className="nav-item" key={o.cle}>
            <button
              type="button" role="tab" aria-selected={onglet === o.cle}
              className={`nav-link${onglet === o.cle ? ' active' : ''}`}
              data-testid={`ae-veille-onglet-${o.cle}`}
              onClick={() => setOnglet(o.cle)}>
              {o.libelle}
            </button>
          </li>
        ))}
      </ul>
      {onglet === 'decouverte' && (
        <VeilleDecouverte
          couverture={couverture?.couverture || []}
          decouverteId={decouverteId} onSelection={setDecouverteId} />
      )}
      {onglet === 'manuel' && <SaisieManuelle />}
    </div>
  )
}

function SaisieManuelle() {
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
    <div data-testid="ae-veille-manuel">
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
