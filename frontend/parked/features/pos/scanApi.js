// NTRET22 — helpers du mode « scan douchette en flux continu » + raccourcis
// clavier caisse. Extraits de ScanMode.jsx : un fichier composant ne doit
// exporter QUE son composant (react-refresh/only-export-components) — ces
// helpers vivent ici à côté (même patron que pinApi.js pour PinLock.jsx).

// Délai (ms) sous lequel DEUX scans successifs du MÊME code sont fusionnés en
// un seul ajout — absorbe le rebond mécanique d'une douchette ou une double
// lecture accidentelle, sans jamais bloquer un VRAI second scan du même
// article (au-delà du délai, il compte normalement).
export const SCAN_DEBOUNCE_MS = 400

// Traite un code scanné : PURE, sans I/O — le composant n'appelle que ceci.
// `dernier` = { code, ts } | null (dernier scan accepté). Renvoie
// { accepte, dernier } : `accepte` faux pour un code vide OU un doublon du
// même code arrivé sous SCAN_DEBOUNCE_MS ; `dernier` à reporter à l'appel
// suivant dans tous les cas où un code non vide a été soumis.
export function traiterScan(code, dernier, maintenant = Date.now()) {
  const c = (code ?? '').trim()
  if (!c) return { accepte: false, dernier }
  if (dernier && dernier.code === c && (maintenant - dernier.ts) < SCAN_DEBOUNCE_MS) {
    return { accepte: false, dernier }
  }
  return { accepte: true, dernier: { code: c, ts: maintenant } }
}

// Raccourcis clavier caisse : F2 nouveau ticket, F4 encaisser, Échap annuler
// la ligne en cours. `handlers` = { onNouveauTicket, onEncaisser,
// onAnnulerLigne } — chaque callback est optionnel (raccourci sans handler =
// no-op silencieux, jamais une erreur). Renvoie la fonction de nettoyage
// (retirer l'écouteur) — à appeler au démontage/à chaque changement de deps.
export function attacherRaccourcisClavier(handlers, target = typeof window !== 'undefined' ? window : null) {
  if (!target) return () => {}
  const onKeyDown = (e) => {
    if (e.key === 'F2') { e.preventDefault?.(); handlers.onNouveauTicket?.() }
    else if (e.key === 'F4') { e.preventDefault?.(); handlers.onEncaisser?.() }
    else if (e.key === 'Escape') { handlers.onAnnulerLigne?.() }
  }
  target.addEventListener('keydown', onKeyDown)
  return () => target.removeEventListener('keydown', onKeyDown)
}

// Bip de confirmation (best-effort — Web Audio absente en test/jsdom ou
// navigateur restreint = no-op silencieux, jamais une exception qui casse le
// scan suivant).
export function biperConfirmation() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 880
    gain.gain.value = 0.05
    osc.start()
    osc.stop(ctx.currentTime + 0.08)
  } catch {
    // best-effort — jamais bloquant.
  }
}
