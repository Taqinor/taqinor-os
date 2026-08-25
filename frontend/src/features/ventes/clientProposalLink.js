// L5 (fondateur 21/08/2026) — le lien PAGE CLIENT (page devis web publique,
// `chemin_proposition` côté backend) + le message WhatsApp qui l'accompagne,
// pour la fiche lead (DevisTab). MÊME FORMAT que celui déjà en service sur
// l'outil de conception 3D (`frontend/src/pages/ventes/ToitureDesign.jsx`,
// fonctions locales `designProposalUrl`/`designWhatsappText`/`whatsappLink`,
// ~lignes 40-55) — on ne réinvente pas un second message pour le même lien.
//
// Fonctions PURES, testables sans DOM — y compris sous `node --test` (CI
// exécute `src/**/*.test.mjs` en Node NU, sans transform Vite : ce module
// n'accède donc JAMAIS à `import.meta.env` au niveau module, contrairement à
// ToitureDesign.jsx qui peut se le permettre car il n'est chargé que par
// Vite/vitest). L'appelant (DevisTab.jsx) reste responsable de l'appel
// réseau (mint/réutilisation du ShareLink via `ventesApi.shareLinkDevis`), de
// résoudre `VITE_PUBLIC_SITE_URL`, et de la normalisation du numéro
// (`lib/format.js normalizePhoneE164` depuis le 25/08/2026 — LANE NUMÉROS
// INTERNATIONAUX, déjà utilisée pour armer la barre WhatsApp existante de
// cet écran) — cette normalisation n'est PAS refaite ici pour éviter une
// seconde logique de validation téléphonique.

export const DEFAULT_PUBLIC_SITE_URL = 'https://taqinor.ma'

// Chemin relatif renvoyé par `POST /ventes/devis/<id>/share-link/` (`path`,
// ex. "/proposition/jean-dupont/<token>") → URL absolue de la page client,
// hébergée sur le site public (apps/web). `siteUrl` vient de l'appelant
// (`VITE_PUBLIC_SITE_URL`, repli `DEFAULT_PUBLIC_SITE_URL`) — jamais lu ici.
export function clientProposalUrl(proposalPath, siteUrl = DEFAULT_PUBLIC_SITE_URL) {
  const base = (siteUrl || DEFAULT_PUBLIC_SITE_URL).replace(/\/+$/, '')
  const path = proposalPath?.startsWith('/') ? proposalPath : `/${proposalPath ?? ''}`
  return `${base}${path}`
}

// Texte du message WhatsApp — identique à `designWhatsappText` (ToitureDesign.jsx).
export function proposalWhatsappText(name, proposalUrl) {
  const hello = name?.trim() ? `Bonjour ${name.trim()}, ` : 'Bonjour, '
  return (
    `${hello}voici votre proposition d'installation solaire Taqinor : ${proposalUrl} ` +
    `N'hésitez pas à me poser vos questions.`
  )
}

// URL wa.me — `digitsE164` doit déjà être un numéro normalisé (ex.
// `normalizePhoneE164`, chiffres seuls avec indicatif pays — 212 marocain
// OU étranger, sans "+"). `null` si aucun numéro exploitable (aucun lien
// wa.me inventé sur un numéro vide).
export function buildWaUrl(digitsE164, text) {
  if (!digitsE164) return null
  return `https://wa.me/${digitsE164}?text=${encodeURIComponent(text)}`
}
