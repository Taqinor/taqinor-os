// VX42 — Retour haptique défensif : un tap léger (~10 ms) confirme une action
// terrain sans jamais rien casser. `navigator.vibrate` n'existe pas partout
// (Safari/iOS ne l'implémente pas) — détection de fonctionnalité stricte,
// silencieux si absent, jamais de plantage.
export function hapticTap(durationMs = 10) {
  try {
    navigator.vibrate?.(durationMs)
  } catch {
    // Certains navigateurs lèvent si appelé hors interaction utilisateur —
    // on l'ignore, ce n'est qu'un confort.
  }
}

export default hapticTap
