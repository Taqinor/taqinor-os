/* G26 — Logique pure de validation/affichage des fichiers (testable en .mjs).
   Zéro dépendance, zéro accès DOM : tout ce qui touche au navigateur (input,
   drag-drop, XHR de progression) reste dans FileUpload.jsx. */

/** Taille lisible : « 0 o », « 512 o », « 4 Ko », « 1,5 Mo ». */
export function formatFileSize(bytes) {
  const n = Number(bytes)
  if (!Number.isFinite(n) || n <= 0) return '0 o'
  if (n < 1024) return `${n} o`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} Ko`
  return `${(n / 1024 / 1024).toFixed(1).replace('.', ',')} Mo`
}

/** Extension en minuscules sans le point (« facture.PDF » → « pdf »), ou ''. */
export function fileExtension(name) {
  const s = String(name ?? '')
  const i = s.lastIndexOf('.')
  return i > 0 && i < s.length - 1 ? s.slice(i + 1).toLowerCase() : ''
}

/**
 * Une spec `accept` (style <input accept>) accepte-t-elle ce fichier ?
 * Gère : '' (tout), 'image/*', 'application/pdf', '.pdf', listes séparées par
 * des virgules. `file` = { name, type }.
 */
export function matchesAccept(file, accept) {
  if (!accept || !accept.trim()) return true
  const type = String(file?.type ?? '').toLowerCase()
  const ext = fileExtension(file?.name)
  const specs = accept.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean)
  return specs.some((spec) => {
    if (spec.startsWith('.')) return spec.slice(1) === ext
    if (spec.endsWith('/*')) return type.startsWith(spec.slice(0, -1)) // 'image/*'
    return spec === type
  })
}

/**
 * Valide un fichier contre `{ accept, maxSize }` (maxSize en octets).
 * Renvoie `{ ok: true }` ou `{ ok: false, code, message }` (message fr-FR).
 */
export function validateFile(file, { accept, maxSize } = {}) {
  if (!file) return { ok: false, code: 'missing', message: 'Aucun fichier.' }
  if (accept && !matchesAccept(file, accept)) {
    return { ok: false, code: 'type', message: `Type de fichier non autorisé (${file.name}).` }
  }
  if (maxSize && Number(file.size) > maxSize) {
    return {
      ok: false,
      code: 'size',
      message: `Fichier trop volumineux : ${formatFileSize(file.size)} (max ${formatFileSize(maxSize)}).`,
    }
  }
  return { ok: true }
}

/**
 * Valide une liste de fichiers. Renvoie `{ accepted: [], rejected: [{file,error}] }`.
 * Si `multiple` est faux, seul le premier fichier valide est retenu.
 */
export function validateFiles(files, { accept, maxSize, multiple = true } = {}) {
  const list = Array.from(files || [])
  const accepted = []
  const rejected = []
  for (const file of list) {
    const res = validateFile(file, { accept, maxSize })
    if (res.ok) accepted.push(file)
    else rejected.push({ file, error: res.message })
    if (!multiple && accepted.length >= 1) break
  }
  return { accepted: multiple ? accepted : accepted.slice(0, 1), rejected }
}

/** Borne un pourcentage de progression à un entier 0–100. */
export function clampProgress(value) {
  const n = Math.round(Number(value))
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n))
}
