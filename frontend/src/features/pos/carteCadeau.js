// NTRET15 — Cartes cadeaux (émission, utilisation comme mode de paiement).
// Logique PURE de l'écran caisse : le nouveau mode de paiement
// `carte_cadeau` (apps/pos/services.py::MODE_CARTE_CADEAU) transporte un
// `carte_code` en plus du montant — ce module construit/valide ce paiement
// avant de le pousser dans la liste `paiements` de posApi.validerVente().
// Aucune I/O ici (les appels réseau restent dans CaisseScreen.jsx / posApi.js).

export const MODE_CARTE_CADEAU = 'carte_cadeau'

// Construit un paiement carte cadeau prêt à être ajouté à `paiements` (même
// forme que les autres modes : { mode, montant }, + `carte_code`).
export function paiementCarteCadeau(code, montant) {
  return {
    mode: MODE_CARTE_CADEAU,
    montant: String(montant ?? ''),
    carte_code: (code || '').trim().toUpperCase(),
  }
}

// Un paiement carte cadeau saisi est valide s'il porte un code non vide et
// un montant strictement positif — ne vérifie PAS le solde (fait
// côté serveur, seule source de vérité sur l'état réel de la carte).
export function paiementCarteCadeauValide(code, montant) {
  const m = Number(montant)
  return !!(code && code.trim()) && Number.isFinite(m) && m > 0
}

// Formatte l'aperçu de solde renvoyé par GET .../payer-carte-cadeau/
// ({ code, solde }) pour affichage — jamais un calcul local du solde (le
// serveur reste la seule source de vérité, cf. apps.promotions.services).
export function libelleSoldeCarteCadeau({ code, solde } = {}) {
  if (!code) return ''
  return `Carte ${code} — solde disponible : ${Number(solde || 0).toFixed(2)} DH`
}
