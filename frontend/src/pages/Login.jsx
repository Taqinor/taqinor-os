import { useEffect, useState } from 'react'
import { useDispatch, useStore } from 'react-redux'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { Eye, EyeOff, AlertCircle } from 'lucide-react'
import { setCredentials, fetchMe } from '../features/auth/store/authSlice'
import api from '../api/axios'
import identityApi from '../api/identityApi'
// NTPRT19 — marque white-label du portail, résolue par le DOMAINE appelant.
import portailApi from '../api/portailApi'
import { normalizeTenantTheme } from '../design/tenantTheme'
// VX46 — module d'atterrissage au login (« Mes préférences »), résolu depuis
// `moduleConfigs` (UX1) + le dernier module visité (VX11).
// ODY3 — le repli n'est plus `/dashboard` mais le Menu d'accueil `/apps` (« on
// ouvre l'ERP, on voit SES apps »), avec l'exception mono-app ; toute la
// résolution passe par `lib/apps/landing.js`, partagé avec la garde `/` du
// routeur pour que les deux ne divergent jamais.
import { resolveLandingFromAuth } from '../lib/apps/landing'
// VX154 — le mot-symbole de marque (soleil brass + éclair azur), tokenisé.
import TaqinorMark from '../ui/TaqinorMark'

// VX34 — Login = premier pixel de la marque. On garde EXACTEMENT les teintes de
// marque (#1863DC azur, #F5C100 laiton, #050e1f nuit) mais on les fait entrer
// dans le système : chaque hex est ré-exprimé en OKLCH (round-trip sRGB à
// ΔE ≈ 0, même méthode que design/tokens.css) et exposé en variable CSS locale,
// consommée partout via var(). Aucune couleur ne change à l'écran ; elles sont
// désormais tokenisées. (Pré-auth : pas de token tenant runtime ici, donc ces
// jetons restent locaux à l'écran de login.)
const BRAND_TOKENS = `
  .login-root {
    --login-azur: oklch(53.1% 0.1985 260.25);      /* #1863DC */
    --login-azur-bright: oklch(58.3% 0.2259 264.10);/* #326CFE */
    --login-brass: oklch(83.4% 0.1704 88.96);       /* #F5C100 */
    /* ODY33 — pôle foncé du dégradé du bouton de marque (même teinte que
       --login-brass, clarté abaissée) : un aplat plat ferait moins « objet ». */
    --login-brass-deep: oklch(72.5% 0.1512 84);
    --login-nuit: oklch(16.5% 0.0389 260.32);       /* #050e1f */
    --login-nuit-mid: oklch(26.1% 0.0924 263.49);   /* #0b2050 */
  }
`

// SCA24 — Login est PRÉ-AUTH : on ne connaît pas encore la société de
// l'utilisateur (donc pas son TenantTheme), donc pas de logo/couleur dynamique
// ici. Marque produit NEUTRE fixée au build (env), plus de logo/texte
// "Taqinor" en dur — la première chose qu'un tenant #2 doit voir n'est pas la
// marque d'un autre client. Défaut sobre si la variable n'est pas fournie.
//
// NTPRT19 — SEULE exception, et elle ne contredit pas la règle ci-dessus : si
// le NOM DE DOMAINE appelant est le domaine white-label déclaré par une société
// (`TenantTheme.domaine`), le serveur renvoie SA marque. La société est résolue
// par l'en-tête `Host` seul — jamais par un paramètre que le visiteur
// choisirait, ce qui ferait de l'endpoint un énumérateur de tenants. Sur le
// domaine générique, aucun thème ne correspond : l'écran reste EXACTEMENT
// celui d'aujourd'hui.
//
// ODY33 (fondateur, 2026-08-02) — le REPLI, lui, n'a jamais eu de raison d'être
// neutre : sans domaine white-label, ce portail est le NÔTRE, et il affichait
// un carré bleu « E » plus une étiquette « ERP » qui n'appartiennent à
// personne. Le repli porte désormais le mot-symbole Taqinor et le bouton de
// marque en brass. Ce que SCA24 protège vraiment — la marque d'un client n'est
// jamais recouverte par la nôtre — est intact et testé : dès qu'un TenantTheme
// répond (logo, nom d'affichage ou couleur primaire), l'écran est exactement
// celui d'avant, sans une occurrence de « Taqinor ».
const PRODUCT_NAME = import.meta.env.VITE_PRODUCT_NAME || 'Taqinor'

/** marqueDeTenant — ce domaine porte-t-il la marque d'une société cliente ? */
function marqueDeTenant(marque) {
  return !!(marque?.logoUrl || marque?.nomAffichage || marque?.couleurPrimaire)
}

function ProductBrand({ marque }) {
  const nom = marque?.nomAffichage || PRODUCT_NAME
  if (marque?.logoUrl) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 10, height: 52,
      }}>
        <img src={marque.logoUrl} alt={nom}
             style={{ maxHeight: 44, maxWidth: 220, objectFit: 'contain' }} />
      </div>
    )
  }
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      gap: 10, height: 52,
    }}>
      {marqueDeTenant(marque) ? (
        <span style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 40, height: 40, borderRadius: 10,
          background: marque.couleurPrimaire
            || 'linear-gradient(135deg, var(--login-azur) 0%, var(--login-azur-bright) 100%)',
          color: '#fff', fontWeight: 800, fontSize: 18,
        }} aria-hidden="true">
          {nom.charAt(0).toUpperCase()}
        </span>
      ) : (
        <TaqinorMark size={40} />
      )}
      {/* VX150 — le wordmark utilise la POLICE DE MARQUE (var(--font-display),
          Archivo — la même que les headings/logo), au lieu d'hériter la police
          de corps ou d'un « Arial Black » hors-système. Dernier delta non
          couvert par VX34 (la mise en page cockpit du login venait de là). */}
      <span style={{
        fontFamily: 'var(--font-display)',
        fontSize: 22, fontWeight: 700, color: '#0c1335', letterSpacing: '-0.01em',
      }}>
        {nom}
      </span>
    </div>
  )
}

// ── Styles inputs ─────────────────────────────────────────────────────────────
const baseInput = {
  width: '100%', padding: '12px 14px', borderRadius: 10,
  border: '1.5px solid #e5e7eb', fontSize: 14, color: '#111827',
  outline: 'none', boxSizing: 'border-box', background: '#f9fafb',
  transition: 'border-color 0.2s, box-shadow 0.2s, background 0.2s',
  fontFamily: 'inherit',
}
const onFocus = (e) => {
  e.target.style.borderColor = 'var(--login-azur)'
  e.target.style.boxShadow   = '0 0 0 3px rgba(24,99,220,0.12)'
  e.target.style.background  = '#ffffff'
}
const onBlur = (e) => {
  e.target.style.borderColor = '#e5e7eb'
  e.target.style.boxShadow   = 'none'
  e.target.style.background  = '#f9fafb'
}

// VX65 — Garde anti-open-redirect pour `?next=` : on ne suit la destination
// d'origine que si c'est un chemin interne (`/...`), jamais un `//host` ou une
// URL absolue (protocole-relative), qui redirigerait vers un domaine externe.
const safeNextPath = (next) => {
  if (!next || !next.startsWith('/') || next.startsWith('//')) return null
  return next
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function Login() {
  const dispatch = useDispatch()
  // ODY3 — accès au store pour relire rôle/permissions JUSTE APRÈS
  // `setCredentials` (une valeur de `useSelector` serait celle du rendu
  // précédent, donc pré-connexion).
  const store = useStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [showPwd,  setShowPwd]  = useState(false)
  // N96 — double authentification (2FA) : quand le serveur répond
  // `otp_required`, on bascule sur la saisie du code à 6 chiffres et on
  // resoumet username + password + otp. Les comptes sans 2FA ne voient jamais
  // cette étape.
  // WIR134 / NTSEC28 — bannière/mention légale de connexion, résolue par
  // username (pré-auth, AllowAny). Vide = aucun bandeau (écran inchangé).
  const [banner, setBanner] = useState('')
  const loadBanner = async () => {
    const uname = (username || '').trim()
    try {
      const r = await identityApi.loginBanner.get(uname)
      setBanner(r.data?.login_banner_text ?? '')
    } catch { setBanner('') }
  }
  const [otpRequired, setOtpRequired] = useState(false)
  const [otp,         setOtp]         = useState('')

  // NTPRT19 — marque du tenant pour CE domaine (endpoint public, résolu par
  // l'en-tête Host côté serveur). Aucun domaine white-label ⇒ marque vide ⇒
  // écran STRICTEMENT identique à aujourd'hui. Un échec réseau/permission ne
  // doit jamais empêcher de se connecter : on retombe en silence.
  const [marque, setMarque] = useState(null)
  const marqueTenant = marqueDeTenant(marque)
  useEffect(() => {
    let annule = false
    portailApi.themePublic()
      .then((r) => { if (!annule) setMarque(normalizeTenantTheme(r.data)) })
      .catch(() => { if (!annule) setMarque(null) })
    return () => { annule = true }
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      // Le serveur set les cookies httpOnly — aucun token visible cote frontend.
      // On joint `otp` uniquement si l'étape 2FA a été demandée.
      const body = { username, password }
      if (otpRequired) body.otp = otp.trim()
      const res = await api.post('/token/', body)
      // WIR134 / NTSEC28 — accuse la bannière légale (best-effort) si affichée.
      if (banner) { identityApi.loginBanner.acknowledge(username).catch(() => {}) }
      dispatch(setCredentials({
        user: { username },
        role: res.data.role || 'normal',
        role_nom: res.data.role_nom || null,
        permissions: res.data.permissions || [],
      }))
      // NTMOB6 — le stub `{ username }` ci-dessus ne porte ni rôle fin ni
      // `mobile_home_route` (seul `/auth/me` les porte) ; le loader de session
      // du routeur ne relance PAS `fetchMe()` puisque `isAuthenticated` est
      // déjà vrai. Sans cet appel, le sélecteur de démarrage par rôle
      // resterait aveugle sur toute la session tant qu'aucun rechargement de
      // page n'intervient. Fire-and-forget : ne bloque jamais la navigation.
      dispatch(fetchMe())
      // VX65 : un lien profond `?next=` interne est prioritaire ; sinon VX46
      // route vers le module d'atterrissage préféré, puis (ODY3) mono-app,
      // puis le Menu d'accueil `/apps`. L'état d'auth est relu à L'INSTANT de
      // la décision (`store.getState()`), pas capturé au rendu précédent : le
      // `setCredentials` ci-dessus vient d'y poser rôle et permissions.
      const next = safeNextPath(searchParams.get('next'))
      navigate(next || resolveLandingFromAuth(store.getState().auth))
    } catch (err) {
      const data = err.response?.data || {}
      // 2FA requise : on déverrouille le champ code et on demande le code.
      if (data.otp_required) {
        setOtpRequired(true)
        // Si on avait déjà un code et qu'il est refusé, on signale l'erreur.
        setError(otpRequired && otp.trim()
          ? 'Code de double authentification invalide.'
          : null)
        setOtp('')
      } else if (data.detail) {
        setError(data.detail)
      } else if (err.message === 'Network Error') {
        setError('Impossible de contacter le serveur. Vérifiez votre connexion.')
      } else {
        setError("Identifiants incorrects. Vérifiez votre nom d'utilisateur et mot de passe.")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-root" style={{
      position: 'fixed', inset: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, var(--login-nuit) 0%, var(--login-nuit-mid) 50%, var(--login-nuit) 100%)',
      overflow: 'hidden',
    }}>
      {/* Halo lumineux central */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 1, pointerEvents: 'none',
        background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(24,99,220,0.18) 0%, transparent 70%)',
      }} />

      {/* Card */}
      <div className="login-card" style={{
        position: 'relative', zIndex: 10,
        width: '100%', maxWidth: 420, margin: '0 16px',
        background: '#ffffff', borderRadius: 22,
        padding: '44px 40px 38px',
        boxShadow: '0 32px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)',
      }}>

        {/* Marque produit centrée */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 6 }}>
          <ProductBrand marque={marque} />
        </div>

        {/* Ligne décorative */}
        <div style={{
          width: 40, height: 3, borderRadius: 2,
          background: 'linear-gradient(90deg, var(--login-azur), var(--login-brass))',
          margin: '14px auto 0',
        }} />

        <p style={{
          textAlign: 'center', color: '#6b7280', fontSize: 13.5,
          marginTop: 14, marginBottom: 30, letterSpacing: '0.01em',
        }}>
          Connectez-vous à votre espace de gestion
        </p>

        {/* Erreur */}
        {error && (
          <div style={{
            marginBottom: 18, padding: '10px 14px', borderRadius: 10,
            background: '#fef2f2', border: '1px solid #fecaca',
            color: '#b91c1c', fontSize: 13,
            display: 'flex', alignItems: 'flex-start', gap: 8,
          }}>
            <AlertCircle size={15} style={{ flexShrink: 0, marginTop: 1 }} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {/* WIR134 / NTSEC28 — mention légale de connexion (si configurée). */}
        {banner && (
          <div
            data-testid="login-banner"
            style={{
              marginBottom: 16, padding: '10px 12px', borderRadius: 8,
              background: '#fef3c7', border: '1px solid #fcd34d',
              color: '#78350f', fontSize: 13, whiteSpace: 'pre-wrap',
            }}
          >
            {banner}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Identifiant */}
          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              Nom d'utilisateur
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="Entrez votre identifiant"
              style={baseInput}
              onFocus={onFocus}
              onBlur={(e) => { onBlur(e); loadBanner() }}
            />
          </div>

          {/* Mot de passe */}
          <div>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              Mot de passe
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                style={{ ...baseInput, paddingRight: 46 }}
                onFocus={onFocus}
                onBlur={onBlur}
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                style={{
                  position: 'absolute', right: 13, top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#9ca3af', padding: 0, lineHeight: 1,
                  display: 'inline-flex', alignItems: 'center',
                }}
                tabIndex={-1}
                aria-label={showPwd ? 'Masquer' : 'Afficher'}
              >
                {showPwd ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
              </button>
            </div>
          </div>

          {/* Code 2FA (N96) — affiché uniquement si le serveur l'exige */}
          {otpRequired && (
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
                Code de double authentification
              </label>
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                required
                autoFocus
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="123456"
                style={{ ...baseInput, letterSpacing: '0.25em', fontFamily: 'monospace' }}
                onFocus={onFocus}
                onBlur={onBlur}
              />
              <p style={{ marginTop: 6, fontSize: 12, color: '#6b7280' }}>
                Saisissez le code à 6 chiffres de votre application
                d'authentification (ou un code de secours).
              </p>
            </div>
          )}

          {/* Bouton */}
          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 4, width: '100%', padding: '13px 0',
              borderRadius: 12, border: 'none',
              // ODY33 — brass (notre primaire) sur le portail générique ; l'azur
              // reste INCHANGÉ dès qu'un domaine porte la marque d'un client.
              ...(marqueTenant ? {
                background: loading
                  ? '#93c5fd'
                  : 'linear-gradient(135deg, var(--login-azur) 0%, var(--login-azur-bright) 100%)',
                color: '#fff',
                boxShadow: loading ? 'none' : '0 4px 18px rgba(24,99,220,0.45)',
              } : {
                background: loading
                  ? 'color-mix(in oklch, var(--login-brass) 45%, transparent)'
                  : 'linear-gradient(135deg, var(--login-brass) 0%, var(--login-brass-deep) 100%)',
                // Texte NUIT sur l'or : ~11:1. Du blanc sur du brass échouerait.
                color: 'var(--login-nuit)',
                boxShadow: loading
                  ? 'none'
                  : '0 4px 18px color-mix(in oklch, var(--login-brass) 45%, transparent)',
              }),
              fontWeight: 700, fontSize: 15,
              cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '0.03em',
              transition: 'opacity 0.2s, box-shadow 0.2s',
              fontFamily: 'inherit',
            }}
            onMouseEnter={(e) => { if (!loading) e.target.style.opacity = '0.9' }}
            onMouseLeave={(e) => { e.target.style.opacity = '1' }}
          >
            {loading
              ? 'Connexion en cours…'
              : otpRequired ? 'Vérifier le code →' : 'Se connecter →'}
          </button>
        </form>

        {/* PACT116 — porte d'entrée de l'inscription : `POST
            /auth/register-company/` existait depuis toujours, sans aucun lien
            pour l'atteindre. */}
        <p style={{ textAlign: 'center', marginTop: 22, fontSize: 13, color: '#6b7280' }}>
          Pas encore de société ?{' '}
          <Link to="/register" style={{ color: 'var(--login-azur)', textDecoration: 'none', fontWeight: 600 }}>
            Créer votre société
          </Link>
        </p>

        {/* Retour accueil */}
        <p style={{ textAlign: 'center', marginTop: 10, fontSize: 13, color: '#9ca3af' }}>
          <Link to="/landing" style={{ color: 'var(--login-azur)', textDecoration: 'none', fontWeight: 500 }}>
            ← Retour à l'accueil
          </Link>
        </p>
      </div>

      <style>{`
        ${BRAND_TOKENS}
        @keyframes loginIn {
          from { opacity: 0; transform: translateY(28px) scale(0.96); }
          to   { opacity: 1; transform: translateY(0)    scale(1);    }
        }
        .login-card { animation: loginIn 0.55s cubic-bezier(0.16, 1, 0.3, 1) both; }
        @media (prefers-reduced-motion: reduce) {
          .login-card { animation: none; }
        }
      `}</style>
    </div>
  )
}

export { Login as Component }
