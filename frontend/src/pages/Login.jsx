import { useState, useEffect, useRef } from 'react'
import { useDispatch } from 'react-redux'
import { useNavigate, Link } from 'react-router-dom'
import { setCredentials } from '../features/auth/store/authSlice'
import api from '../api/axios'

// ── Logo ──────────────────────────────────────────────────────────────────────
function TaqinorLogo({ size = 34 }) {
  const sun = Math.round(size * 0.92)
  const txt = {
    fontFamily: "'Arial Black', 'Arial Bold', Impact, sans-serif",
    fontWeight: 900, fontSize: size, color: '#0d1b3e',
    lineHeight: 1, letterSpacing: '0.03em',
  }
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center' }}>
      <span style={txt}>TAQIN</span>
      <div style={{
        width: sun, height: sun, borderRadius: '50%', backgroundColor: '#F5C100',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        margin: '0 1px', flexShrink: 0,
      }}>
        <svg viewBox="0 0 24 24" width={sun * 0.54} height={sun * 0.54} fill="#0d1b3e">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
      </div>
      <span style={txt}>R</span>
    </div>
  )
}

// ── Bouncing TAQINOR background ───────────────────────────────────────────────
const BLOBS = [
  { size: 150, speed: 0.55, opacity: 0.07, color: '#ffffff', angle: 0.7  },
  { size: 95,  speed: 0.85, opacity: 0.06, color: '#F5C100', angle: 2.1  },
  { size: 190, speed: 0.38, opacity: 0.05, color: '#ffffff', angle: 4.3  },
  { size: 115, speed: 0.70, opacity: 0.08, color: '#F5C100', angle: 1.5  },
  { size: 80,  speed: 1.05, opacity: 0.05, color: '#ffffff', angle: 3.8  },
]

function BouncingBackground() {
  const containerRef = useRef(null)
  const animRef      = useRef(null)
  const stateRef     = useRef([])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const W = window.innerWidth
    const H = window.innerHeight

    stateRef.current = BLOBS.map((cfg) => {
      const el = document.createElement('div')
      el.textContent = 'TAQINOR'
      Object.assign(el.style, {
        position: 'absolute', top: '0', left: '0',
        fontFamily: "'Arial Black', Impact, sans-serif",
        fontWeight: '900',
        fontSize: `${cfg.size}px`,
        color: cfg.color,
        opacity: String(cfg.opacity),
        filter: 'blur(10px)',
        userSelect: 'none', pointerEvents: 'none',
        whiteSpace: 'nowrap', letterSpacing: '0.05em',
        willChange: 'transform',
      })
      container.appendChild(el)

      // Mesure réelle après ajout au DOM
      const rect = el.getBoundingClientRect()
      const w = rect.width  || cfg.size * 5.8
      const h = rect.height || cfg.size * 1.2

      return {
        el, w, h,
        x: Math.random() * Math.max(1, W - w),
        y: Math.random() * Math.max(1, H - h),
        vx: Math.cos(cfg.angle) * cfg.speed,
        vy: Math.sin(cfg.angle) * cfg.speed,
      }
    })

    const tick = () => {
      const W = window.innerWidth
      const H = window.innerHeight
      stateRef.current.forEach((b) => {
        b.x += b.vx
        b.y += b.vy
        if (b.x <= 0)        { b.x = 0;        b.vx =  Math.abs(b.vx) }
        if (b.x + b.w >= W)  { b.x = W - b.w;  b.vx = -Math.abs(b.vx) }
        if (b.y <= 0)        { b.y = 0;        b.vy =  Math.abs(b.vy) }
        if (b.y + b.h >= H)  { b.y = H - b.h;  b.vy = -Math.abs(b.vy) }
        b.el.style.transform = `translate(${b.x}px,${b.y}px)`
      })
      animRef.current = requestAnimationFrame(tick)
    }
    animRef.current = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(animRef.current)
      stateRef.current.forEach((b) => b.el.remove())
    }
  }, [])

  return (
    <div ref={containerRef}
      style={{ position: 'fixed', inset: 0, overflow: 'hidden', pointerEvents: 'none', zIndex: 0 }}
    />
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
  e.target.style.borderColor = '#1863DC'
  e.target.style.boxShadow   = '0 0 0 3px rgba(24,99,220,0.12)'
  e.target.style.background  = '#ffffff'
}
const onBlur = (e) => {
  e.target.style.borderColor = '#e5e7eb'
  e.target.style.boxShadow   = 'none'
  e.target.style.background  = '#f9fafb'
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function Login() {
  const dispatch = useDispatch()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [showPwd,  setShowPwd]  = useState(false)
  // N96 — double authentification (2FA) : quand le serveur répond
  // `otp_required`, on bascule sur la saisie du code à 6 chiffres et on
  // resoumet username + password + otp. Les comptes sans 2FA ne voient jamais
  // cette étape.
  const [otpRequired, setOtpRequired] = useState(false)
  const [otp,         setOtp]         = useState('')

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
      dispatch(setCredentials({
        user: { username },
        role: res.data.role || 'normal',
        role_nom: res.data.role_nom || null,
        permissions: res.data.permissions || [],
      }))
      navigate('/dashboard')
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
    <div style={{
      position: 'fixed', inset: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'linear-gradient(135deg, #050e1f 0%, #0b2050 50%, #050e1f 100%)',
      overflow: 'hidden',
    }}>
      <BouncingBackground />

      {/* Halo lumineux central */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 1, pointerEvents: 'none',
        background: 'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(24,99,220,0.18) 0%, transparent 70%)',
      }} />

      {/* Card */}
      <div style={{
        position: 'relative', zIndex: 10,
        width: '100%', maxWidth: 420, margin: '0 16px',
        background: '#ffffff', borderRadius: 22,
        padding: '44px 40px 38px',
        boxShadow: '0 32px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)',
        animation: 'loginIn 0.55s cubic-bezier(0.16, 1, 0.3, 1) both',
      }}>

        {/* Logo centré */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 6 }}>
          <TaqinorLogo size={36} />
        </div>

        {/* Ligne décorative */}
        <div style={{
          width: 40, height: 3, borderRadius: 2,
          background: 'linear-gradient(90deg, #1863DC, #F5C100)',
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
            <span style={{ flexShrink: 0, marginTop: 1 }}>⚠️</span>
            <span>{error}</span>
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
              onBlur={onBlur}
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
                  color: '#9ca3af', fontSize: 17, padding: 0, lineHeight: 1,
                }}
                tabIndex={-1}
                aria-label={showPwd ? 'Masquer' : 'Afficher'}
              >
                {showPwd ? '🙈' : '👁️'}
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
              background: loading
                ? '#93c5fd'
                : 'linear-gradient(135deg, #1863DC 0%, #326CFE 100%)',
              color: '#fff', fontWeight: 700, fontSize: 15,
              cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '0.03em',
              boxShadow: loading ? 'none' : '0 4px 18px rgba(24,99,220,0.45)',
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

        {/* Retour accueil */}
        <p style={{ textAlign: 'center', marginTop: 26, fontSize: 13, color: '#9ca3af' }}>
          <Link to="/landing" style={{ color: '#1863DC', textDecoration: 'none', fontWeight: 500 }}>
            ← Retour à l'accueil
          </Link>
        </p>
      </div>

      <style>{`
        @keyframes loginIn {
          from { opacity: 0; transform: translateY(28px) scale(0.96); }
          to   { opacity: 1; transform: translateY(0)    scale(1);    }
        }
      `}</style>
    </div>
  )
}

export { Login as Component }
