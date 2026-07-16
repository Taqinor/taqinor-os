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

/* Extensions connues par type MIME, pour le REPLI quand le navigateur ne
   fournit pas de `type` (cas réel : certains .pdf/.png/.jpg sélectionnés sous
   Windows/Linux ou glissés depuis une autre app arrivent avec `type === ''`).
   Sans ce repli, un fichier parfaitement valide était refusé côté client AVANT
   tout envoi (« Type de fichier non autorisé »), bloquant l'ajout partout. Le
   contrôle reste strict : un type vide n'est accepté QUE si l'extension
   correspond à un type explicitement autorisé. Le serveur revérifie ensuite par
   octets magiques — c'est lui qui fait foi. */
const MIME_EXTENSIONS = {
  'application/pdf': ['pdf'],
  'image/png': ['png'],
  'image/jpeg': ['jpg', 'jpeg'],
  'image/webp': ['webp'],
  'image/gif': ['gif'],
  'image/tiff': ['tif', 'tiff'],
}

/**
 * Une spec `accept` (style <input accept>) accepte-t-elle ce fichier ?
 * Gère : '' (tout), 'image/*', 'application/pdf', '.pdf', listes séparées par
 * des virgules. `file` = { name, type }. Repli par extension quand le navigateur
 * ne renvoie pas de `type` (sinon des fichiers valides étaient refusés à tort).
 */
export function matchesAccept(file, accept) {
  if (!accept || !accept.trim()) return true
  const type = String(file?.type ?? '').toLowerCase()
  const ext = fileExtension(file?.name)
  const specs = accept.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean)
  return specs.some((spec) => {
    if (spec.startsWith('.')) return spec.slice(1) === ext
    if (spec.endsWith('/*')) {
      // 'image/*' : par type si fourni, sinon par extension d'un type du groupe.
      if (type) return type.startsWith(spec.slice(0, -1))
      const prefix = spec.slice(0, -1) // ex. 'image/'
      return Object.entries(MIME_EXTENSIONS).some(
        ([mime, exts]) => mime.startsWith(prefix) && exts.includes(ext),
      )
    }
    if (type) return spec === type
    // Type absent : on accepte si l'extension correspond à ce type MIME précis.
    return (MIME_EXTENSIONS[spec] || []).includes(ext)
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

// ── VX77 — Compression photo côté client AVANT upload (capture terrain) ─────
// `ChantierPhotos.jsx`, `InterventionFieldExecution.jsx` (PhotosPanel) et
// `InterventionCapturePanels.jsx` (SerialsPanel) envoyaient la photo BRUTE
// (4-8 Mo routiniers sur un appareil photo moderne) — minutes ou timeout sur
// la 3G rurale. Helper pur `<canvas>` + `toBlob`, ZÉRO dépendance : borne le
// bord long à `MAX_DIMENSION`, réencode en JPEG à `JPEG_QUALITY`. Seuls les
// `image/*` sont compressés — un PDF (fiche produit, bon signé...) passe
// intouché. Garde serveur 20 Mo conservée (ce helper est un confort réseau,
// pas une garde de sécurité).
export const MAX_DIMENSION = 1600
export const JPEG_QUALITY = 0.75

/**
 * Compresse un fichier image côté client avant upload (bord long borné,
 * réencodage JPEG). Passthrough silencieux (renvoie `file` inchangé) pour :
 * un fichier non-image (PDF...), une image déjà plus petite que `file` après
 * compression (rare mais possible sur un PNG déjà optimisé), ou tout
 * environnement sans `document`/`Image`/canvas `toBlob` (SSR, vieux
 * navigateur, jsdom en test) — ne DOIT jamais faire échouer un upload.
 */
export async function compressImage(file, {
  maxDimension = MAX_DIMENSION, quality = JPEG_QUALITY,
} = {}) {
  if (!file || !String(file.type ?? '').startsWith('image/')) return file
  // SVG n'a pas de dimensions bitmap fiables via <img> pour ce cas d'usage
  // (et n'a pas besoin de compression) — passthrough.
  if (file.type === 'image/svg+xml') return file
  if (typeof document === 'undefined' || typeof Image === 'undefined') return file

  try {
    const bitmap = await loadImage(file)
    const { width, height } = scaledSize(bitmap.width, bitmap.height, maxDimension)
    if (!width || !height) return file

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) return file
    ctx.drawImage(bitmap, 0, 0, width, height)

    const blob = await canvasToBlob(canvas, 'image/jpeg', quality)
    if (!blob || blob.size <= 0) return file
    // N'utilise le résultat compressé QUE s'il est réellement plus petit —
    // évite de gonfler un petit fichier déjà optimisé.
    if (blob.size >= file.size) return file

    const newName = renameToJpeg(file.name)
    return new File([blob], newName, { type: 'image/jpeg', lastModified: Date.now() })
  } catch {
    // Défensif : une compression en échec ne doit JAMAIS bloquer l'upload —
    // on retombe sur le fichier d'origine.
    return file
  }
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => { URL.revokeObjectURL(url); resolve(img) }
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('image illisible')) }
    img.src = url
  })
}

function canvasToBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    if (typeof canvas.toBlob !== 'function') { reject(new Error('toBlob indisponible')); return }
    canvas.toBlob((blob) => resolve(blob), type, quality)
  })
}

/** Bord long borné à `maxDimension`, ratio préservé. No-op si déjà plus petit. */
export function scaledSize(width, height, maxDimension) {
  const w = Number(width) || 0
  const h = Number(height) || 0
  if (w <= 0 || h <= 0) return { width: 0, height: 0 }
  const longest = Math.max(w, h)
  if (longest <= maxDimension) return { width: Math.round(w), height: Math.round(h) }
  const scale = maxDimension / longest
  return { width: Math.round(w * scale), height: Math.round(h * scale) }
}

function renameToJpeg(name) {
  const base = String(name ?? 'photo').replace(/\.[^./\\]+$/, '')
  return `${base || 'photo'}.jpg`
}
