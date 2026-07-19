import { useEffect, useState, useCallback } from 'react'
import { ShieldCheck, PlugZap, ExternalLink, CircleHelp, RefreshCw } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeWiringStatuses, formatMAD } from './adsengine'
import { WIZARD_STEPS, HEALTH_REMEDIATIONS, stepStatus } from './connectionWizard'

/* ============================================================================
   ENG22 — Écran « Connexion & garde-fous » du moteur publicitaire.
   ----------------------------------------------------------------------------
   Quatre blocs :
   0. PUB46 — Assistant de connexion guidé : le wizard pas-à-pas FR (créer
      l'app Meta, le System User, générer le jeton, trouver l'ID du compte
      publicitaire) qui manquait à un non-technicien — 6 champs de jetons bruts
      sans aide était plus technique qu'Ads Manager lui-même. Chaque étape
      pointe vers Meta (liens externes) et se « vérifie » en réutilisant
      `connection.health` DÉJÀ construit (jamais un nouveau contrat backend).
   1. Identifiants Meta — WRITE-ONLY : les champs partent TOUJOURS vides ; le
      serveur ne renvoie JAMAIS un secret (`connection.get` = statut seul). On
      n'envoie que les champs remplis (jamais d'écrasement par du vide).
   2. Statuts de câblage (ENG12 `connection.health`) — jeton / compte pub /
      pixel / CAPI / client en pause, avec REMÉDIATION par item (PUB46).
   3. Garde-fous — édition du plafond (quotidien/mensuel) et du « band »
      d'approbation obligatoire.
   PAR DESIGN, AUCUN toggle d'activation n'existe à l'écran : le client Meta naît
   PAUSED (règle CLAUDE.md #3) et ne s'active jamais depuis l'ERP.
   ========================================================================== */

// Champs d'identifiants (write-only). `secret: true` → saisie masquée.
const CRED_FIELDS = [
  { key: 'app_id', label: 'App ID Meta', secret: false },
  { key: 'app_secret', label: 'App Secret', secret: true },
  { key: 'access_token', label: "Jeton d'accès (System User)", secret: true },
  { key: 'ad_account_id', label: 'ID compte publicitaire', secret: false },
  { key: 'page_id', label: 'ID Page Facebook', secret: false },
  { key: 'pixel_id', label: 'ID Pixel', secret: false },
]
const EMPTY_CREDS = Object.fromEntries(CRED_FIELDS.map(f => [f.key, '']))

// Garde-fous éditables (plafond + band d'approbation).
const GUARD_FIELDS = [
  { key: 'max_daily_budget_mad', label: 'Plafond quotidien (MAD)' },
  { key: 'max_monthly_budget_mad', label: 'Plafond mensuel (MAD)' },
  { key: 'require_approval_above_mad', label: 'Approbation obligatoire au-dessus de (MAD)' },
]

export default function ConnectionScreen() {
  const [status, setStatus] = useState(null) // statut de connexion (sans secret)
  const [health, setHealth] = useState([])
  const [creds, setCreds] = useState(EMPTY_CREDS)
  const [guard, setGuard] = useState({})
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    // Statut de connexion : jamais de secret relu — seulement l'état affichable.
    adsengineApi.connection.get()
      .then(r => setStatus(r.data || null))
      .catch(() => setStatus(null))
    adsengineApi.connection.health()
      .then(r => setHealth(normalizeWiringStatuses(r.data)))
      .catch(() => setHealth([]))
    adsengineApi.guardrail.get()
      .then(r => setGuard(r.data || {}))
      .catch(() => setGuard({}))
  }, [])

  useEffect(() => { load() }, [load])

  const setCred = (k) => (e) => setCreds(c => ({ ...c, [k]: e.target.value }))
  const setGuardField = (k) => (e) => setGuard(g => ({ ...g, [k]: e.target.value }))

  const saveCreds = async (e) => {
    e.preventDefault()
    setErr(''); setMsg('')
    // N'envoyer QUE les champs remplis (pas d'écrasement d'un secret existant
    // par une chaîne vide).
    const payload = Object.fromEntries(
      Object.entries(creds).filter(([, v]) => v !== ''))
    if (Object.keys(payload).length === 0) {
      setErr('Renseignez au moins un identifiant.')
      return
    }
    try {
      await adsengineApi.connection.save(payload)
      setCreds(EMPTY_CREDS) // on ne conserve JAMAIS les secrets en mémoire écran
      setMsg('Identifiants enregistrés.')
      load()
    } catch {
      setErr('Enregistrement des identifiants impossible.')
    }
  }

  const saveGuard = async (e) => {
    e.preventDefault()
    setErr(''); setMsg('')
    const payload = {}
    for (const f of GUARD_FIELDS) {
      const v = guard[f.key]
      if (v !== '' && v !== null && v !== undefined) payload[f.key] = Number(v)
    }
    try {
      await adsengineApi.guardrail.update(payload)
      setMsg('Garde-fous mis à jour.')
    } catch {
      setErr('Mise à jour des garde-fous impossible.')
    }
  }

  // PUB46 — {clé -> ok} dérivé du dernier `connection.health()` connu ; sert
  // à la fois au wizard (statut par étape) et à la remédiation par item.
  const healthByKey = Object.fromEntries(health.map(s => [s.key, s.ok]))

  return (
    <div className="page ae-connection">
      <div className="page-header">
        <h2>Connexion &amp; garde-fous</h2>
      </div>

      {msg && <p data-testid="ae-conn-msg" style={{ color: '#16a34a', margin: '0 0 0.75rem' }}>{msg}</p>}
      {err && <p data-testid="ae-conn-err" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>{err}</p>}

      {/* PUB46 — Assistant de connexion guidé (wizard pas-à-pas FR). */}
      <section className="card" data-testid="ae-conn-wizard" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <h3 style={{ margin: '0 0 0.25rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <CircleHelp size={18} aria-hidden="true" /> Assistant de connexion guidé
        </h3>
        <p style={{ margin: '0 0 0.75rem', color: '#64748b', fontSize: '0.85rem' }}>
          Suivez les étapes dans l&apos;ordre, de zéro jusqu&apos;à une connexion verte —
          aucune connaissance technique préalable requise.
        </p>
        <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
          {WIZARD_STEPS.map(step => {
            const state = stepStatus(step, healthByKey)
            const tone = state === 'ok'
              ? { bg: '#dcfce7', color: '#166534', label: 'Vérifié' }
              : state === 'a_faire'
                ? { bg: '#fee2e2', color: '#991b1b', label: 'À faire' }
                : state === 'manuel'
                  ? { bg: '#f1f5f9', color: '#475569', label: 'À faire manuellement' }
                  : { bg: '#f1f5f9', color: '#475569', label: 'À vérifier' }
            return (
              <li key={step.key} id={`ae-conn-wizard-step-${step.numero}`}
                data-testid={`ae-conn-wizard-step-${step.numero}`}
                style={{ padding: '0.65rem 0.8rem', border: '1px solid #e2e8f0', borderRadius: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span className="badge" style={{ background: '#eef2ff', color: '#3730a3' }}>
                    Étape {step.numero}
                  </span>
                  <strong>{step.titre}</strong>
                  <span className="badge" data-testid={`ae-conn-wizard-status-${step.numero}`}
                    style={{ background: tone.bg, color: tone.color, marginLeft: 'auto' }}>
                    {tone.label}
                  </span>
                </div>
                <p style={{ margin: '0.35rem 0', color: '#334155' }}>{step.description}</p>
                <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <a href={step.lien} target="_blank" rel="noopener noreferrer"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                      color: '#2563eb', fontSize: '0.85rem' }}>
                    <ExternalLink size={13} aria-hidden="true" /> {step.lienLabel}
                  </a>
                  {step.statutCles.length > 0 && (
                    <button type="button" className="btn btn-light" data-testid={`ae-conn-wizard-verify-${step.numero}`}
                      onClick={load}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}>
                      <RefreshCw size={13} aria-hidden="true" /> Vérifier cette étape
                    </button>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      </section>

      {/* Statut de connexion (jamais de secret) */}
      <section className="card" data-testid="ae-conn-status" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <h3 style={{ margin: '0 0 0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <PlugZap size={18} aria-hidden="true" /> État de la connexion
        </h3>
        <p style={{ margin: 0, color: '#475569' }}>
          {status?.connected
            ? `Connecté${status.ad_account_id_masque ? ` — compte ${status.ad_account_id_masque}` : ''}.`
            : 'Non connecté — renseignez les identifiants ci-dessous.'}
        </p>
        <p style={{ margin: '0.4rem 0 0', color: '#64748b', fontSize: '0.85rem' }}>
          Le client publicitaire est en pause par design : aucune activation
          n'est possible depuis l'ERP (règle de sécurité).
        </p>
      </section>

      {/* Identifiants Meta — write-only */}
      <form onSubmit={saveCreds} data-testid="ae-conn-cred-form"
        className="card" style={{ padding: '1rem', marginBottom: '1rem',
          display: 'grid', gap: '0.6rem', maxWidth: 640 }}>
        <h3 style={{ margin: 0 }}>Identifiants Meta</h3>
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.85rem' }}>
          Saisie sécurisée : ces valeurs sont écrites mais jamais relues ni
          réaffichées.
        </p>
        {CRED_FIELDS.map(f => (
          <label key={f.key} style={{ display: 'grid', gap: '0.2rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#475569' }}>{f.label}</span>
            <input className="form-input"
              data-testid={`ae-conn-cred-${f.key}`}
              type={f.secret ? 'password' : 'text'}
              autoComplete={f.secret ? 'new-password' : 'off'}
              value={creds[f.key]} onChange={setCred(f.key)} />
          </label>
        ))}
        <div>
          <button type="submit" className="btn btn-primary" data-testid="ae-conn-cred-save">
            Enregistrer les identifiants
          </button>
        </div>
      </form>

      {/* Statuts de câblage (ENG12) */}
      <section className="card" data-testid="ae-conn-health" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <h3 style={{ margin: '0 0 0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <ShieldCheck size={18} aria-hidden="true" /> Câblage
        </h3>
        {health.length === 0
          ? <p style={{ margin: 0, color: '#64748b' }}>Aucun état de câblage disponible.</p>
          : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.35rem' }}>
              {health.map(s => {
                // PUB46 — remédiation FR par item : COMPLÈTE le `detail` déjà
                // renvoyé par le backend, ne l'écrase jamais.
                const remediation = !s.ok ? HEALTH_REMEDIATIONS[s.key] : null
                return (
                <li key={s.key} data-testid={`ae-conn-health-${s.key}`}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span className="badge" style={{
                      background: s.ok ? '#dcfce7' : '#fee2e2',
                      color: s.ok ? '#166534' : '#991b1b' }}>
                      {s.ok ? 'OK' : 'À configurer'}
                    </span>
                    <span>{s.label}</span>
                    {s.detail && <span style={{ color: '#64748b', fontSize: '0.85rem' }}>— {s.detail}</span>}
                  </div>
                  {remediation && (
                    <p data-testid={`ae-conn-remediation-${s.key}`}
                      style={{ margin: '0.2rem 0 0 0', color: '#9a3412', fontSize: '0.8rem' }}>
                      {remediation.message}
                      {remediation.etape != null && (
                        <>
                          {' '}
                          <a href={`#ae-conn-wizard-step-${remediation.etape}`}>
                            Reprendre l&apos;étape {remediation.etape} ci-dessus
                          </a>.
                        </>
                      )}
                    </p>
                  )}
                </li>
                )
              })}
            </ul>
          )}
      </section>

      {/* Garde-fous : plafond + band d'approbation */}
      <form onSubmit={saveGuard} data-testid="ae-conn-guard-form"
        className="card" style={{ padding: '1rem', display: 'grid', gap: '0.6rem', maxWidth: 640 }}>
        <h3 style={{ margin: 0 }}>Garde-fous</h3>
        {GUARD_FIELDS.map(f => (
          <label key={f.key} style={{ display: 'grid', gap: '0.2rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#475569' }}>{f.label}</span>
            <input className="form-input" type="number" step="any" min="0"
              data-testid={`ae-conn-guard-${f.key}`}
              value={guard[f.key] ?? ''} onChange={setGuardField(f.key)} />
          </label>
        ))}
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.85rem' }}>
          Plafond quotidien actuel : {formatMAD(guard.max_daily_budget_mad)}.
        </p>
        <div>
          <button type="submit" className="btn btn-primary" data-testid="ae-conn-guard-save">
            Mettre à jour les garde-fous
          </button>
        </div>
      </form>
    </div>
  )
}
