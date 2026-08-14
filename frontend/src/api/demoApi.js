import api from './axios'

// NTDMO7/10 — actions Démo & mode présentation sur une société.
const demoApi = {
  // Réinitialise les données de démonstration d'une société démo.
  resetDemo: (companyId) =>
    api.post(`/companies/${companyId}/reset-demo/`),
  // NTDMO10 — bascule le mode présentation (masquage PII) — admin société démo.
  setPresentationMode: (companyId, active) =>
    api.patch(`/companies/${companyId}/`, { mode_presentation_actif: active }),
  // NTDMO27 — bascule le toggle global « visites guidées actives » (toute
  // société, jamais réservé à une société démo — contrairement à
  // `setPresentationMode` ci-dessus).
  setToursActifs: (companyId, actif) =>
    api.patch(`/companies/${companyId}/`, { tours_actifs: actif }),
}

export default demoApi
