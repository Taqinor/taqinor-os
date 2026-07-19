import { useEffect, useState, useCallback } from 'react'
import { ShieldCheck, PlugZap } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeWiringStatuses, formatMAD } from './adsengine'

/* ============================================================================
   ENG22 — Écran « Connexion & garde-fous » du moteur publicitaire.
   ----------------------------------------------------------------------------
   Trois blocs :
   1. Identifiants Meta — WRITE-ONLY : les champs partent TOUJOURS vides ; le
      serveur ne renvoie JAMAIS un secret (`connection.get` = statut seul). On
      n'envoie que les champs remplis (jamais d'écrasement par du vide).
   2. Statuts de câblage (ENG12 `connection.health`) — jeton / compte pub /
      pixel / CAPI / client en pause.
   3. Garde-fous avancés (PUB9) — TOUS les champs sérialisés de
      `GuardrailConfig` (plafonds, variation hebdo, fenêtre d'anomalie,
      bascules d'auto-application ENG8, bande de pacing + planchers
      d'exploration ADSENG4, poids des scores de santé SIG1) — avant cette
      tâche, l'écran n'éditait que 2 champs, ET avec des clés qui NE
      correspondaient PAS au serializer (`max_daily_budget_mad` au lieu de
      `daily_budget_ceiling_mad`, `require_approval_above_mad` qui n'existe
      PAS côté modèle) — les garde-fous ne s'enregistraient donc JAMAIS
      réellement (DRF ignore silencieusement un champ inconnu). Aide FR par
      champ ; aucune bascule d'ACTIVATION de campagne n'existe ici (interdite
      en dur côté service, pas un réglage).
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

// PUB9 — TOUS les champs sérialisés de `GuardrailConfig` (id/created_at/
// updated_at exclus, les seuls en lecture seule), groupés par thème, avec une
// aide FR par champ. `type: 'bool'` → checkbox ; `type: 'number'` → input
// numérique (vide = non envoyé, sauf pour les bascules qui partent toujours
// avec une valeur).
const GUARD_FIELD_GROUPS = [
  {
    label: 'Plafonds & variation',
    fields: [
      { key: 'daily_budget_ceiling_mad', label: 'Plafond budget quotidien (MAD)', type: 'number',
        help: "Seuil de garde-fou (pas un montant comptable) : le détecteur d'anomalie compare la dépense réelle des miroirs à ce plafond." },
      { key: 'monthly_budget_ceiling_mad', label: 'Plafond budget mensuel (MAD)', type: 'number',
        help: 'Optionnel — laissé vide, il est dérivé automatiquement du plafond quotidien × jours du mois.' },
      { key: 'weekly_change_pct_max', label: 'Variation hebdomadaire maximale (%)', type: 'number',
        help: "Variation de budget autorisée par semaine, dans les deux sens, avant qu'une approbation humaine devienne obligatoire." },
    ],
  },
  {
    label: "Détection d'anomalie",
    fields: [
      { key: 'anomaly_window_hours', label: "Fenêtre de détection d'anomalie (heures)", type: 'number',
        help: 'Durée d’observation « dépense en cours et zéro lead » avant de déclencher une alerte d’anomalie.' },
    ],
  },
  {
    label: 'Auto-application (ENG8)',
    fields: [
      { key: 'auto_rotate_creative', label: 'Auto — rotation créative', type: 'bool',
        help: "Si activé, le moteur peut roter un créatif fatigué SANS attendre une approbation — l'action reste tracée dans le journal (auto=vrai)." },
      { key: 'auto_rebalance_within_band', label: 'Auto — rééquilibrage budgétaire dans la bande', type: 'bool',
        help: "Si activé, le moteur peut rééquilibrer le budget entre bras SANS approbation, tant que ça reste dans la bande de pacing ci-dessous." },
    ],
  },
  {
    label: 'Pacing & exploration (trésorerie, ADSENG4)',
    fields: [
      { key: 'pacing_band_pct', label: 'Bande de pacing (%)', type: 'number',
        help: "Écart toléré entre la dépense projetée et l'enveloppe mensuelle avant qu'une alerte de pacing se déclenche." },
      { key: 'exploration_floor_mad', label: "Plancher d'exploration (MAD/jour)", type: 'number',
        help: "Dépense minimale garantie par jour pour un bras minoritaire du bandit — il n'est jamais totalement étouffé." },
      { key: 'exploration_floor_pct', label: "Plancher d'exploration (%)", type: 'number',
        help: "Même plancher exprimé en % du budget — le PLUS ÉLEVÉ des deux (MAD ou %) s'applique effectivement." },
    ],
  },
  {
    label: 'Poids des scores de santé (SIG1)',
    fields: [
      { key: 'health_creative_weight_ctr', label: 'Santé créatif — poids CTR', type: 'number',
        help: "Poids relatif du CTR dans le score de santé créatif. Poids FIXES, révisés trimestriellement à la main — jamais appris (pour ne pas pousser au clickbait)." },
      { key: 'health_creative_weight_freshness', label: 'Santé créatif — poids fraîcheur', type: 'number',
        help: 'Poids relatif du temps écoulé depuis le dernier test dans le score de santé créatif.' },
      { key: 'health_ops_weight_cpl', label: 'Santé opérations — poids CPL', type: 'number',
        help: 'Poids relatif du coût par lead dans le score de santé opérations.' },
      { key: 'health_ops_weight_delivery', label: 'Santé opérations — poids diffusion', type: 'number',
        help: 'Poids relatif de la diffusion (delivery) dans le score de santé opérations.' },
    ],
  },
]
const GUARD_FIELDS = GUARD_FIELD_GROUPS.flatMap(g => g.fields)

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
  const setGuardBool = (k) => (e) => setGuard(g => ({ ...g, [k]: e.target.checked }))

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
      if (f.type === 'bool') {
        // Une bascule part TOUJOURS avec une valeur explicite (false par
        // défaut) — jamais omise, contrairement aux plafonds numériques.
        payload[f.key] = Boolean(v)
      } else if (v !== '' && v !== null && v !== undefined) {
        payload[f.key] = Number(v)
      }
    }
    try {
      await adsengineApi.guardrail.update(payload)
      setMsg('Garde-fous mis à jour.')
    } catch {
      setErr('Mise à jour des garde-fous impossible.')
    }
  }

  return (
    <div className="page ae-connection">
      <div className="page-header">
        <h2>Connexion &amp; garde-fous</h2>
      </div>

      {msg && <p data-testid="ae-conn-msg" style={{ color: '#16a34a', margin: '0 0 0.75rem' }}>{msg}</p>}
      {err && <p data-testid="ae-conn-err" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>{err}</p>}

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
              {health.map(s => (
                <li key={s.key} data-testid={`ae-conn-health-${s.key}`}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className="badge" style={{
                    background: s.ok ? '#dcfce7' : '#fee2e2',
                    color: s.ok ? '#166534' : '#991b1b' }}>
                    {s.ok ? 'OK' : 'À configurer'}
                  </span>
                  <span>{s.label}</span>
                  {s.detail && <span style={{ color: '#64748b', fontSize: '0.85rem' }}>— {s.detail}</span>}
                </li>
              ))}
            </ul>
          )}
      </section>

      {/* PUB9 — Garde-fous avancés : TOUS les champs sérialisés, groupés,
          avec aide FR par champ (plafonds/variation, anomalie, bascules
          d'auto-application ENG8, pacing/exploration ADSENG4, poids santé
          SIG1). */}
      <form onSubmit={saveGuard} data-testid="ae-conn-guard-form"
        className="card" style={{ padding: '1rem', display: 'grid', gap: '1.1rem', maxWidth: 640 }}>
        <h3 style={{ margin: 0 }}>Garde-fous avancés</h3>
        {GUARD_FIELD_GROUPS.map(group => (
          <fieldset key={group.label} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.75rem 0.9rem', display: 'grid', gap: '0.6rem' }}>
            <legend style={{ padding: '0 0.4rem', fontWeight: 600, fontSize: '0.9rem' }}>{group.label}</legend>
            {group.fields.map(f => (
              <label key={f.key} style={{ display: 'grid', gap: '0.2rem' }}>
                {f.type === 'bool' ? (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input type="checkbox" data-testid={`ae-conn-guard-${f.key}`}
                      checked={Boolean(guard[f.key])} onChange={setGuardBool(f.key)} />
                    <span style={{ fontSize: '0.85rem', color: '#475569', fontWeight: 600 }}>{f.label}</span>
                  </span>
                ) : (
                  <>
                    <span style={{ fontSize: '0.85rem', color: '#475569', fontWeight: 600 }}>{f.label}</span>
                    <input className="form-input" type="number" step="any" min="0"
                      data-testid={`ae-conn-guard-${f.key}`}
                      value={guard[f.key] ?? ''} onChange={setGuardField(f.key)} />
                  </>
                )}
                <span style={{ color: '#64748b', fontSize: '0.8rem' }}>{f.help}</span>
              </label>
            ))}
          </fieldset>
        ))}
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.85rem' }}>
          Plafond quotidien actuel : {formatMAD(guard.daily_budget_ceiling_mad)}.
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
