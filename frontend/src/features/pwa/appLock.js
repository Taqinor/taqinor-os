// NTMOB18 — Verrouillage d'ÉCRAN local de l'app (Face ID / empreinte).
//
// PÉRIMÈTRE, à ne jamais confondre : ceci est un verrou d'AFFICHAGE propre à
// CET APPAREIL. Il ne remplace, n'affaiblit ni ne prolonge l'authentification
// JWT existante — un jeton expiré reste expiré, une session révoquée reste
// révoquée. Son seul rôle : masquer le contenu déjà chargé quand le téléphone
// d'un technicien traîne sur un chantier, exactement comme le verrou d'une app
// bancaire par-dessus une session déjà ouverte.
//
// Aucune dépendance npm : l'API WebAuthn (`navigator.credentials`) est standard
// et l'authentificateur PLATEFORME est précisément Face ID / Touch ID /
// empreinte Android. Aucun appel serveur : le challenge est local et sans
// valeur cryptographique côté backend (là encore, ce n'est PAS une
// authentification, c'est un déverrouillage d'écran) ; le repli code PIN est
// stocké HACHÉ (SHA-256, `crypto.subtle`), jamais en clair.

export const LOCK_ENABLED_KEY = 'taqinor.appLock.enabled'
export const LOCK_CRED_KEY = 'taqinor.appLock.credId'
export const LOCK_PIN_KEY = 'taqinor.appLock.pin'
export const LOCK_DELAY_KEY = 'taqinor.appLock.delayMin'
export const LOCK_HIDDEN_AT_KEY = 'taqinor.appLock.hiddenAt'
/** Délai d'inactivité par défaut avant re-verrouillage (minutes). */
export const DEFAULT_LOCK_DELAY_MIN = 5

function storage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch {
    return null
  }
}

function read(key) {
  try {
    return storage()?.getItem(key) ?? null
  } catch {
    return null
  }
}

function write(key, value) {
  try {
    if (value === null || value === undefined || value === '') storage()?.removeItem(key)
    else storage()?.setItem(key, String(value))
  } catch { /* stockage indisponible : réglage non persisté sur cet appareil */ }
}

// ── Réglage ────────────────────────────────────────────────────────────────

export function isAppLockEnabled() {
  return read(LOCK_ENABLED_KEY) === '1'
}

export function getLockDelayMinutes() {
  const raw = Number(read(LOCK_DELAY_KEY))
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_LOCK_DELAY_MIN
}

export function setLockDelayMinutes(minutes) {
  const n = Number(minutes)
  write(LOCK_DELAY_KEY, Number.isFinite(n) && n > 0 ? n : null)
}

/** Désactive le verrou et efface TOUT son état local (credential + PIN). */
export function disableAppLock() {
  write(LOCK_ENABLED_KEY, null)
  write(LOCK_CRED_KEY, null)
  write(LOCK_PIN_KEY, null)
  write(LOCK_HIDDEN_AT_KEY, null)
}

// ── Horloge de mise en veille ──────────────────────────────────────────────

/** Mémorise l'instant où l'app est passée en arrière-plan. */
export function markHidden(now = Date.now()) {
  write(LOCK_HIDDEN_AT_KEY, now)
}

export function clearHidden() {
  write(LOCK_HIDDEN_AT_KEY, null)
}

/**
 * shouldLock — l'écran doit-il être verrouillé au retour au premier plan ?
 * Vrai uniquement si le verrou est activé ET que l'app est restée en veille
 * au-delà du délai configuré. Un aller-retour bref (lire une notification,
 * prendre une photo) ne reverrouille donc pas.
 */
export function shouldLock(now = Date.now()) {
  if (!isAppLockEnabled()) return false
  const hiddenAt = Number(read(LOCK_HIDDEN_AT_KEY))
  if (!Number.isFinite(hiddenAt) || hiddenAt <= 0) return false
  return now - hiddenAt >= getLockDelayMinutes() * 60_000
}

// ── Repli code PIN (haché) ─────────────────────────────────────────────────

export async function hashPin(pin) {
  const data = new TextEncoder().encode(`taqinor-app-lock:${pin}`)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

export async function setPin(pin) {
  write(LOCK_PIN_KEY, await hashPin(pin))
}

export function hasPin() {
  return !!read(LOCK_PIN_KEY)
}

export async function verifyPin(pin) {
  const stored = read(LOCK_PIN_KEY)
  if (!stored) return false
  return (await hashPin(pin)) === stored
}

// ── WebAuthn (authentificateur PLATEFORME = biométrie de l'appareil) ───────

function randomChallenge() {
  const buf = new Uint8Array(32)
  crypto.getRandomValues(buf)
  return buf
}

function toBase64(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)))
}

function fromBase64(value) {
  return Uint8Array.from(atob(value), (c) => c.charCodeAt(0))
}

export function isBiometricApiAvailable() {
  return typeof window !== 'undefined'
    && !!window.PublicKeyCredential
    && !!navigator.credentials?.create
}

/** Enrôle la biométrie de CET appareil. Retourne true si le credential est posé. */
export async function enrollBiometric(label = 'Verrouillage TAQINOR') {
  if (!isBiometricApiAvailable()) return false
  const userId = randomChallenge()
  try {
    const credential = await navigator.credentials.create({
      publicKey: {
        challenge: randomChallenge(),
        rp: { name: 'TAQINOR OS' },
        user: { id: userId, name: label, displayName: label },
        pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
        authenticatorSelection: {
          authenticatorAttachment: 'platform',
          userVerification: 'required',
        },
        timeout: 60_000,
        attestation: 'none',
      },
    })
    if (!credential?.rawId) return false
    write(LOCK_CRED_KEY, toBase64(credential.rawId))
    write(LOCK_ENABLED_KEY, '1')
    return true
  } catch {
    return false
  }
}

/** Demande la biométrie pour déverrouiller. Retourne true si vérifiée. */
export async function verifyBiometric() {
  const credId = read(LOCK_CRED_KEY)
  if (!credId || !navigator.credentials?.get) return false
  try {
    const assertion = await navigator.credentials.get({
      publicKey: {
        challenge: randomChallenge(),
        allowCredentials: [{ type: 'public-key', id: fromBase64(credId) }],
        userVerification: 'required',
        timeout: 60_000,
      },
    })
    return !!assertion
  } catch {
    return false
  }
}

export function hasBiometricCredential() {
  return !!read(LOCK_CRED_KEY)
}
