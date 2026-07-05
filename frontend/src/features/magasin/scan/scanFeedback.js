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

export default playRejectBeep
