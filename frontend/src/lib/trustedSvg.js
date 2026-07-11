// VX120 — Rendu d'un SVG généré CÔTÉ SERVEUR (ex. QR code TOTP 2FA) sans passer
// par un service tiers. Le backend produit le SVG (voir
// `apps/stock/labels.py::qr_svg`, réutilisé par `authentication` pour
// `2fa/setup/`) — on ne fait JAMAIS de requête réseau vers un domaine externe
// pour afficher ce visuel, ce qui évite d'exfiltrer une graine secrète (TOTP)
// dans l'URL d'un tiers et évite tout blocage par la CSP `img-src` en prod.
//
// `isTrustedSvg` refuse tout balisage capable d'exécuter du code si jamais la
// source changeait un jour (défense en profondeur — le générateur serveur
// n'émet que des `<svg>`/`<rect>`/`<g>`) : pas de `<script`, pas de gestionnaire
// d'événement `on...=`, pas d'URI `javascript:`.
const UNSAFE_PATTERNS = [
  /<script/i,
  /\son\w+\s*=/i, // onload=, onclick=, onerror=, …
  /javascript:/i,
]

export function isTrustedSvg(svg) {
  if (typeof svg !== 'string' || !svg.trim()) return false
  if (!/^\s*<svg[\s>]/i.test(svg)) return false
  return !UNSAFE_PATTERNS.some((re) => re.test(svg))
}

// Retourne les props à passer à un conteneur (`dangerouslySetInnerHTML`)
// UNIQUEMENT si le SVG est jugé sûr ; sinon `null` (l'appelant doit alors ne
// rien rendre plutôt que d'injecter un balisage suspect).
export function renderTrustedSvg(svg) {
  if (!isTrustedSvg(svg)) return null
  return { __html: svg }
}
