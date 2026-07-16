// I37 — Définition des raccourcis clavier globaux + helpers partagés. Les
// libellés sont en français ; la table sert à la fois au routage clavier et au
// dialogue d'aide « ? ».

// Raccourcis « g puis lettre » → navigation directe vers un écran.
// VX220(c) — audit d'exhaustivité vs les routes de PREMIER NIVEAU (cf.
// router/index.jsx) : /planification et /approbations existaient sans
// raccourci alors qu'elles sont des destinations quotidiennes (dispatch
// planning, boîte d'approbations centralisée VX86) — ajoutées ci-dessous.
export const GOTO_SHORTCUTS = [
  { keys: 'g d', to: '/dashboard', label: 'Aller au tableau de bord' },
  { keys: 'g l', to: '/crm/leads', label: 'Aller aux leads' },
  { keys: 'g c', to: '/crm', label: 'Aller aux clients' },
  { keys: 'g v', to: '/ventes/devis', label: 'Aller aux devis' },
  { keys: 'g f', to: '/ventes/factures', label: 'Aller aux factures' },
  { keys: 'g s', to: '/stock', label: 'Aller au stock' },
  { keys: 'g h', to: '/chantiers', label: 'Aller aux chantiers' },
  { keys: 'g t', to: '/sav', label: 'Aller au SAV' },
  { keys: 'g p', to: '/planification', label: 'Aller à la planification' },
  { keys: 'g a', to: '/approbations', label: 'Aller aux approbations' },
]

// VX220(b) — raccourcis « c puis lettre » → CRÉATION directe (lead/devis/
// client). Périmètre RÉDUIT à dessein : NTUX possède la palette de
// quick-create générique (NTUX9/10, @coord) — ceci pose SEULEMENT le
// câblage clavier direct + le paramètre `?new=1` lu par LeadsPage.jsx/
// ClientList.jsx (DevisGenerator est déjà un écran de création dédié, aucun
// paramètre nécessaire).
export const CREATE_SHORTCUTS = [
  { keys: 'c l', to: '/crm/leads?new=1', label: 'Créer un lead' },
  { keys: 'c d', to: '/ventes/devis/nouveau', label: 'Créer un devis' },
  { keys: 'c c', to: '/crm?new=1', label: 'Créer un client' },
]

// VX73 — l'ERP tourne réellement sur Windows/Linux (glyphe ⌘ codé en dur
// mentait sur la plateforme) : détecte Mac vs le reste pour choisir le bon
// libellé de raccourci clavier. `navigator` est absent en SSR/Node → repli LTR
// « Ctrl K » (comportement Windows/Linux, la plateforme réelle de l'ERP).
export function isMacPlatform(nav) {
  const n = nav || (typeof navigator !== 'undefined' ? navigator : null)
  if (!n) return false
  const platform = n.platform || ''
  const uaData = n.userAgentData && n.userAgentData.platform
  return /mac/i.test(platform) || /mac/i.test(uaData || '')
}

export function quickSearchShortcutLabel(nav) {
  return isMacPlatform(nav) ? '⌘ K' : 'Ctrl K'
}

// Raccourcis « globaux » affichés dans l'aide (les actions sont câblées
// ailleurs : ⌘K/Ctrl K par la palette, ? par le ShortcutsProvider).
export const GLOBAL_SHORTCUTS = [
  { keys: quickSearchShortcutLabel(), label: 'Ouvrir la recherche rapide' },
  { keys: '?', label: 'Afficher l’aide des raccourcis' },
]

/**
 * isTypingTarget — vrai si l'événement vient d'un champ de saisie, d'un
 * textarea, d'un select ou d'un contenu éditable : on n'y intercepte JAMAIS la
 * frappe (sauf les combinaisons avec modificateur, gérées à part).
 */
export function isTypingTarget(target) {
  if (!target) return false
  const tag = target.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (target.isContentEditable) return true
  // Champ ARIA personnalisé (ex. combobox).
  const role = target.getAttribute?.('role')
  if (role === 'textbox' || role === 'combobox' || role === 'searchbox') return true
  return false
}
