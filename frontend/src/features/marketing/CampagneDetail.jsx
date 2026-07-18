import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import { computeAbComparatif } from './campagneDetail'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   NTMKT2/NTMKT3 — Détail d'une campagne : trace destinataire, envoi de test,
   pré-check santé, comparatif A/B.
   ----------------------------------------------------------------------------
   `marketing/envois-campagne/?campagne=<id>` (XMKT2) pour le drill-down par
   destinataire (queued/envoyé/ouvert/cliqué/rebond/désinscrit), l'action
   `envoyer-test` (XMKT13, jamais vers de vrais destinataires) et `precheck`
   (bloquant/avertissant, affiché avant confirmation d'envoi de masse). NTMKT3
   — panneau comparatif A vs B vs reste depuis la même trace (`variante_ab`),
   gagnant affiché une fois `ab_gagnant`/`ab_decide_le` posés côté serveur.
   ========================================================================== */

const ENVOI_STATUTS = [
  { key: '', label: 'Tous' },
  { key: 'queued', label: 'En file' },
  { key: 'envoye', label: 'Envoyé' },
  { key: 'delivre', label: 'Délivré' },
  { key: 'ouvert', label: 'Ouvert' },
  { key: 'clique', label: 'Cliqué' },
  { key: 'rebond', label: 'Rebond' },
  { key: 'desinscrit', label: 'Désinscrit' },
]

export default function CampagneDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [campagne, setCampagne] = useState(null)
  const [envois, setEnvois] = useState([])
  const [statutFiltre, setStatutFiltre] = useState('')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  // ── XMKT13 — envoi de test ──
  const [adressesSeed, setAdressesSeed] = useState('')
  const [testEnCours, setTestEnCours] = useState(false)
  const [testResultat, setTestResultat] = useState(null)

  // ── XMKT13 — pré-check santé avant envoi de masse ──
  const [precheck, setPrecheck] = useState(null)
  const [precheckLoading, setPrecheckLoading] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setErr('')
    Promise.all([
      marketingApi.campagnes.get(id),
      marketingApi.envoisCampagne.list({ campagne: id }),
    ]).then(([cRes, eRes]) => {
      setCampagne(cRes.data)
      setEnvois(marketingApi.unwrapList(eRes))
    }).catch(() => setErr('Campagne introuvable.'))
      .finally(() => setLoading(false))
  }, [id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const envoisFiltres = statutFiltre
    ? envois.filter(e => e.statut === statutFiltre) : envois

  const envoyerTest = async () => {
    setTestEnCours(true)
    setTestResultat(null)
    setErr('')
    try {
      const adresses = adressesSeed.split(',').map(a => a.trim()).filter(Boolean)
      const r = await marketingApi.campagnes.envoyerTest(id, { adresses_seed: adresses })
      setTestResultat(r.data)
    } catch {
      setErr("Envoi de test impossible.")
    } finally {
      setTestEnCours(false)
    }
  }

  const lancerPrecheck = async () => {
    setPrecheckLoading(true)
    setErr('')
    try {
      const r = await marketingApi.campagnes.precheck(id)
      setPrecheck(r.data)
    } catch {
      setErr('Pré-check impossible.')
    } finally {
      setPrecheckLoading(false)
    }
  }

  const confirmerEnvoi = async () => {
    setErr('')
    try {
      await marketingApi.campagnes.envoyer(id, {})
      load()
    } catch {
      setErr('Envoi impossible.')
    }
  }

  if (loading) return <div className="page"><p className="page-loading">Chargement…</p></div>
  if (!campagne) return <div className="page"><p style={{ color: '#dc2626' }}>{err || 'Introuvable.'}</p></div>

  const abComparatif = computeAbComparatif(envois)
  const abConfigure = !!(campagne.ab_test && (campagne.ab_test.objet_b || campagne.ab_test.corps_b))

  return (
    <div className="page">
      <div className="page-header">
        <button className="btn btn-light" onClick={() => navigate('/marketing/campagnes')}>
          ← Campagnes
        </button>
        <h2>{campagne.nom}</h2>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      <div data-testid="campagne-detail-kpis" style={{ display: 'flex',
        flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
        {[
          ['Statut', campagne.statut_display || campagne.statut],
          ['Envoyés', campagne.nb_envois ?? 0],
          ['Ouverture %', `${campagne.taux_ouverture_pct ?? 0}%`],
          ['Clic %', `${campagne.taux_clic_pct ?? 0}%`],
          ['Désinscription %', `${campagne.taux_desinscription_pct ?? 0}%`],
        ].map(([label, value]) => (
          <div key={label} style={{ border: '1px solid #e2e8f0', borderRadius: 8,
            padding: '0.6rem 0.9rem', minWidth: 120 }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>{label}</div>
            <div style={{ fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>

      <section style={{ marginBottom: '1.25rem' }}>
        <h3>Envoyer un test (XMKT13)</h3>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <input className="form-input" data-testid="campagne-test-adresses"
            placeholder="Adresses de test, séparées par virgule"
            value={adressesSeed} onChange={e => setAdressesSeed(e.target.value)}
            style={{ flex: '1 1 260px' }} />
          <button className="btn btn-light" data-testid="campagne-envoyer-test"
            disabled={testEnCours} onClick={envoyerTest}>
            {testEnCours ? 'Envoi…' : 'Envoyer un test'}
          </button>
        </div>
        {testResultat && (
          <p data-testid="campagne-test-resultat" style={{ color: '#16a34a' }}>
            Test envoyé ({testResultat.nb_envoyes ?? testResultat.envoyes ?? 'ok'}).
          </p>
        )}
      </section>

      <section style={{ marginBottom: '1.25rem' }}>
        <h3>Pré-check santé avant envoi de masse</h3>
        <button className="btn btn-light" data-testid="campagne-precheck-btn"
          disabled={precheckLoading} onClick={lancerPrecheck}>
          {precheckLoading ? 'Vérification…' : 'Lancer le pré-check'}
        </button>
        {precheck && (
          <div data-testid="campagne-precheck-resultat"
            style={{ marginTop: 8, border: '1px solid #e2e8f0', borderRadius: 8,
              padding: '0.6rem' }}>
            {(precheck.avertissements || []).map((a, i) => (
              <p key={i} style={{ color: '#b45309', margin: '2px 0' }}>⚠ {a}</p>
            ))}
            {(precheck.bloquants || []).map((b, i) => (
              <p key={i} style={{ color: '#dc2626', margin: '2px 0' }}>✖ {b}</p>
            ))}
            {!(precheck.bloquants || []).length
              && !(precheck.avertissements || []).length && (
              <p style={{ color: '#16a34a', margin: 0 }}>Aucun problème détecté.</p>
            )}
            <button className="btn btn-primary" data-testid="campagne-confirmer-envoi"
              disabled={(precheck.bloquants || []).length > 0}
              style={{ marginTop: 8 }}
              onClick={confirmerEnvoi}>
              Confirmer l'envoi
            </button>
          </div>
        )}
      </section>

      {abConfigure && (
        <section style={{ marginBottom: '1.25rem' }} data-testid="campagne-ab-comparatif">
          <h3>
            Test A/B (XMKT14)
            {campagne.ab_gagnant && (
              <span style={{ marginLeft: 8, color: '#16a34a', fontSize: '0.85rem' }}>
                Gagnant : variante {campagne.ab_gagnant.toUpperCase()}
              </span>
            )}
          </h3>
          <table className="data-table">
            <thead>
              <tr><th>Variante</th><th>Envoyés</th><th>Ouverture %</th><th>Clic %</th></tr>
            </thead>
            <tbody>
              <tr data-testid="campagne-ab-ligne-a">
                <td>A</td><td>{abComparatif.a.total}</td>
                <td>{abComparatif.a.taux_ouverture_pct}%</td>
                <td>{abComparatif.a.taux_clic_pct}%</td>
              </tr>
              <tr data-testid="campagne-ab-ligne-b">
                <td>B</td><td>{abComparatif.b.total}</td>
                <td>{abComparatif.b.taux_ouverture_pct}%</td>
                <td>{abComparatif.b.taux_clic_pct}%</td>
              </tr>
              <tr data-testid="campagne-ab-ligne-reste">
                <td>Reste</td><td>{abComparatif.reste.total}</td>
                <td>{abComparatif.reste.taux_ouverture_pct}%</td>
                <td>{abComparatif.reste.taux_clic_pct}%</td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h3>Trace par destinataire ({envoisFiltres.length})</h3>
        <select className="form-input" data-testid="envois-filtre-statut"
          value={statutFiltre} onChange={e => setStatutFiltre(e.target.value)}
          style={{ marginBottom: 8 }}>
          {ENVOI_STATUTS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <table className="data-table" data-testid="envois-table">
          <thead>
            <tr><th>Destinataire</th><th>Statut</th><th>Envoyé le</th><th>Ouvert le</th><th>Cliqué le</th></tr>
          </thead>
          <tbody>
            {envoisFiltres.map(e => (
              <tr key={e.id} data-testid="envoi-row">
                <td>{e.destinataire}</td>
                <td>{e.statut_display || e.statut}</td>
                <td>{e.envoye_le ? formatDateTime(e.envoye_le) : '—'}</td>
                <td>{e.ouvert_le ? formatDateTime(e.ouvert_le) : '—'}</td>
                <td>{e.clique_le ? formatDateTime(e.clique_le) : '—'}</td>
              </tr>
            ))}
            {envoisFiltres.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                Aucun envoi
              </td></tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  )
}
