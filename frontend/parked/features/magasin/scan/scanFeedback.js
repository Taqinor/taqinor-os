import { hapticTap } from '../../../lib/haptics.js'

/* ============================================================================
   XSTK5 — Retour sonore (best-effort) pour un scan hors-liste. Même pattern
   que `components/layout/NotificationBell.jsx` (WebAudio, zéro dépendance) —
   ton grave/court pour signaler un REJET (à distinguer d'une notification).
   Jamais bloquant : silencieux si l'autoplay est refusé / API absente.
   ========================================================================== */
export function playRejectBeep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'square'
    osc.frequency.value = 220
    gain.gain.setValueAtTime(0.0001, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35)
    osc.start()
    osc.stop(ctx.currentTime + 0.35)
    osc.onended = () => { try { ctx.close() } catch { /* noop */ } }
  } catch { /* best-effort : pas de son si l'autoplay est bloqué */ }
}

/* ============================================================================
   APX23 — Retour scan FORT, SANS bip de succès : le bip de rejet ci-dessus
   reste le SEUL son du scan (« pas de son » = pas de son NOUVEAU). Le canal
   haptique partagé (VX42, `lib/haptics.js`) confirme accepté ET refusé — le
   flash visuel plein écran (accent réussite/échec, CSS pur, réduit à une
   bordure statique sous `prefers-reduced-motion`) vit dans le composant
   appelant car il doit suivre l'état React monté/démonté ; ce module reste
   le point d'entrée unique du feedback scan (audio + haptique).
   ========================================================================== */
export function triggerScanHaptic() {
  hapticTap(10)
}

export default playRejectBeep
