// L5 (fondateur 21/08/2026) — le lien PAGE CLIENT (page devis web publique,
// `chemin_proposition` côté backend) + le message WhatsApp qui l'accompagne.
// QJR531 — SEULE construction de l'URL publique d'une proposition : la fiche
// lead (DevisTab) ET la liste des devis (DevisList, lien client + aperçu
// interne) passent par `clientProposalUrl` — aucune recomposition inline.
//
// Fonctions PURES, testables sans DOM — y compris sous `node --test` (CI
// exécute `src/**/*.test.mjs` en Node NU, sans transform Vite : ce module
// n'accède donc JAMAIS à `import.meta.env` au niveau module, contrairement à
// ToitureDesign.jsx qui peut se le permettre car il n'est chargé que par
// Vite/vitest). L'appelant (DevisTab.jsx, DevisList.jsx) reste responsable de l'appel
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

// Texte du message WhatsApp qui accompagne le lien de la proposition.
export function proposalWhatsappText(name, proposalUrl) {
  const hello = name?.trim() ? `Bonjour ${name.trim()}, ` : 'Bonjour, '
  return (
    `${hello}voici votre proposition d'installation solaire Taqinor : ${proposalUrl} ` +
    `N'hésitez pas à me poser vos questions.`
  )
}

// URL wa.me — QJR635 : le constructeur UNIQUE vit dans `lib/contactLinks.js`
// (`buildWaUrl`, avec `waHref` qui normalise un numéro saisi) ; ré-exporté
// ici pour les appelants existants (DevisTab, QuestionnaireDialog).
export { buildWaUrl } from '../../lib/contactLinks.js'
