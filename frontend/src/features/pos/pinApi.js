import api from '../../api/axios'

// NTRET3 — helpers d'appel API pour le verrouillage PIN de session. Extraits
// de PinLock.jsx : un fichier composant ne doit exporter QUE son composant
// (react-refresh/only-export-components) — ces helpers vivent ici à côté.

const CAISSIER_ACTIF_KEY = 'pos:caissier-actif'

// Le « caissier précédent » (pour la journalisation du changement côté
// serveur, apps.pos.services.verifier_pin) survit au verrouillage — stocké
// en localStorage, PAS en state React (le composant peut être démonté/
// remonté entre deux verrouillages).
export function lireCaissierActif(storage = safeStorage()) {
  try {
    const raw = storage?.getItem(CAISSIER_ACTIF_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function memoriserCaissierActif(user, storage = safeStorage()) {
  try {
    if (user?.id) storage?.setItem(CAISSIER_ACTIF_KEY, JSON.stringify(user))
    else storage?.removeItem(CAISSIER_ACTIF_KEY)
  } catch { /* quota/privé */ }
}

function safeStorage() {
  return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null
}

/**
 * Vérifie un PIN contre le backend (POST /pos/verifier-pin/). Transmet le
 * caissier précédemment actif (localStorage) pour que le serveur journalise
 * un changement de caissier — jamais posé côté client (audit server-side
 * only, cf. CLAUDE.md).
 */
export async function verifierPin({ userId, pin }) {
  const precedent = lireCaissierActif()
  const res = await api.post('/pos/verifier-pin/', {
    user_id: userId,
    pin,
    caissier_precedent: precedent?.id || null,
  })
  memoriserCaissierActif(res.data)
  return res.data
}

export async function definirPin(pin) {
  return api.post('/pos/definir-pin/', { pin })
}
