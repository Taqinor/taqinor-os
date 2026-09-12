// NTI18N7 — charge la police arabe (auto-hébergée, `public/fonts/arabic.css`)
// PARESSEUSEMENT : injecte un `<link rel="stylesheet">` dans `<head>` la
// PREMIÈRE fois que la locale devient 'ar', jamais au chargement FR/EN par
// défaut (même principe que Sora retirée d'`index.html` pour /landing —
// VX57 : un poids utilisé par une seule langue ne doit jamais peser sur
// toutes les autres). Idempotent (id fixe) : un second appel est un no-op.
const LINK_ID = 'nti18n7-arabic-font'
const HREF = '/fonts/arabic.css'

export function ensureArabicFontLoaded() {
  if (typeof document === 'undefined') return
  if (document.getElementById(LINK_ID)) return
  const link = document.createElement('link')
  link.id = LINK_ID
  link.rel = 'stylesheet'
  link.href = HREF
  document.head.appendChild(link)
}
