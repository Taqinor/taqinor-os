// COP6 — tampon de diagnostic du navigateur (contrat : `contexte.diagnostic` de
// `backend/django_core/apps/agent/contract_samples/assistant_reponse.json`).
//
// INTERFACE FIGÉE entre l'intercepteur réseau (qui note) et le panneau de
// l'assistant (qui lit `instantaneDiagnostic()` pour « Signaler un bug ») :
//
//   noterRequete({ methode, url, statut, dureeMs, requestId, code })
//   noterErreur({ genre, message })
//   instantaneDiagnostic()  -> { version, ecran, navigateur, en_ligne, requetes[], erreurs[] }
//   viderTampon()
//
// Jamais de donnée personnelle : ni corps de requête, ni chaîne de requête,
// routes normalisées (`<id>`), 15 requêtes et 10 erreurs au plus, en mémoire
// seulement (rien n'est écrit dans le navigateur).

export const MAX_REQUETES = 15
export const MAX_ERREURS = 10

const requetes = []
const erreurs = []

export function noterRequete() {}

export function noterErreur() {}

export function instantaneDiagnostic() {
  return {
    version: '',
    ecran: '',
    navigateur: '',
    en_ligne: true,
    requetes: requetes.slice(),
    erreurs: erreurs.slice(),
  }
}

export function viderTampon() {
  requetes.length = 0
  erreurs.length = 0
}
