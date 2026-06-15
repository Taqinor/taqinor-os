/* PWA — invites en français, autonomes (styles inline, aucune dépendance au
   CSS de l'app). Deux choses :
   1) Bandeau « Installer l'application » : sur Android/Chrome on capture
      beforeinstallprompt et on déclenche l'invite native ; sur iPhone (Safari
      n'expose pas d'invite) on affiche la consigne Partager → écran d'accueil.
      Masqué si l'app tourne déjà installée (display-mode: standalone) ou si
      l'utilisateur a refusé.
   2) Toast « Nouvelle version disponible — actualiser » : repli au cas où la
      mise à jour automatique (registerType autoUpdate) ne s'applique pas seule. */
import { useEffect, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

const NAVY = '#0f172a'
const GOLD = '#f5a623'
const DISMISS_KEY = 'taqinor-pwa-install-dismissed'

function isStandalone() {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches
    || window.navigator.standalone === true // iOS Safari installé
  )
}

function isIos() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent)
}

const bannerStyle = {
  position: 'fixed', left: 12, right: 12, bottom: 12, zIndex: 4000,
  margin: '0 auto', maxWidth: 460,
  background: NAVY, color: '#e2e8f0',
  border: '1px solid #1e293b', borderRadius: 14,
  boxShadow: '0 10px 30px rgba(0,0,0,.45)',
  padding: '14px 16px', display: 'flex', gap: 12, alignItems: 'center',
  fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
}
const primaryBtn = {
  background: GOLD, color: NAVY, border: 'none', borderRadius: 9,
  padding: '8px 14px', fontWeight: 700, fontSize: 14, cursor: 'pointer',
  whiteSpace: 'nowrap',
}
const ghostBtn = {
  background: 'transparent', color: '#94a3b8', border: 'none',
  fontSize: 20, lineHeight: 1, cursor: 'pointer', padding: '0 4px',
}

function eligible() {
  return !isStandalone() && localStorage.getItem(DISMISS_KEY) !== '1'
}

function InstallBanner() {
  const [deferred, setDeferred] = useState(null)
  // iPhone : pas d'événement beforeinstallprompt -> on affiche d'emblée la
  // consigne (état initial, pas de setState dans l'effet).
  const [show, setShow] = useState(() => eligible() && isIos())

  useEffect(() => {
    if (!eligible()) return undefined

    // Android / Chrome desktop : l'invite native devient disponible.
    const onPrompt = (e) => {
      e.preventDefault()
      setDeferred(e)
      setShow(true)
    }
    window.addEventListener('beforeinstallprompt', onPrompt)
    // Une fois installée, on cache le bandeau.
    const onInstalled = () => setShow(false)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  if (!show) return null

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, '1')
    setShow(false)
  }

  const install = async () => {
    if (!deferred) return
    deferred.prompt()
    try { await deferred.userChoice } catch { /* ignore */ }
    setDeferred(null)
    setShow(false)
  }

  return (
    <div style={bannerStyle} role="dialog" aria-label="Installer Taqinor OS">
      <img src="/pwa-192.png" alt="" width="40" height="40"
           style={{ borderRadius: 9, flex: '0 0 auto' }} />
      <div style={{ flex: 1, fontSize: 14, lineHeight: 1.4 }}>
        <strong style={{ display: 'block', color: '#f1f5f9' }}>
          Installer Taqinor OS
        </strong>
        {deferred ? (
          <span style={{ color: '#94a3b8' }}>
            Ajoutez l’app à votre écran d’accueil pour l’ouvrir en plein écran.
          </span>
        ) : (
          <span style={{ color: '#94a3b8' }}>
            Sur iPhone : appuyez sur Partager puis « Sur l’écran d’accueil ».
          </span>
        )}
      </div>
      {deferred && (
        <button type="button" style={primaryBtn} onClick={install}>
          Installer l’application
        </button>
      )}
      <button type="button" style={ghostBtn} aria-label="Fermer"
              onClick={dismiss}>✕</button>
    </div>
  )
}

function UpdateToast() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    immediate: true,
    onRegisteredSW(_url, reg) {
      // Vérifie périodiquement une nouvelle version (toutes les heures).
      if (reg) setInterval(() => reg.update(), 60 * 60 * 1000)
    },
  })

  if (!needRefresh) return null

  return (
    <div style={{ ...bannerStyle, bottom: 'auto', top: 12 }} role="alert">
      <div style={{ flex: 1, fontSize: 14 }}>
        Nouvelle version disponible.
      </div>
      <button type="button" style={primaryBtn}
              onClick={() => updateServiceWorker(true)}>
        Actualiser
      </button>
      <button type="button" style={ghostBtn} aria-label="Plus tard"
              onClick={() => setNeedRefresh(false)}>✕</button>
    </div>
  )
}

export default function PwaPrompts() {
  return (
    <>
      <UpdateToast />
      <InstallBanner />
    </>
  )
}
