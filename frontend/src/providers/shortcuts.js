// I37 — Définition des raccourcis clavier globaux + helpers partagés. Les
// libellés sont en français ; la table sert à la fois au routage clavier et au
// dialogue d'aide « ? ».

// Raccourcis « g puis lettre » → navigation directe vers un écran.
// VX220(c) — audit d'exhaustivité vs les routes de PREMIER NIVEAU (cf.
// router/index.jsx) : /planification et /approbations existaient sans
// raccourci alors qu'elles sont des destinations quotidiennes (dispatch
// planning, boîte d'approbations centralisée VX86) — ajoutées ci-dessous.
//
// ODY28 — SORT DES 10 BINDINGS HISTORIQUES : ils sont CONSERVÉS TELS QUELS.
// Les repointer vers les cockpits d'app aurait silencieusement changé l'écran
// d'atterrissage d'un utilisateur clavier (« g v » ne l'aurait plus amené aux
// devis mais au cockpit Ventes) : une régression déguisée en amélioration.
// Ce sont des sauts d'ÉCRAN directs, tous vers des routes toujours valides ;
// la navigation entre APPS se fait par « g g » (Menu d'accueil) et par les
// bindings d'app déclarés en module.config (cf. `buildAppShortcuts`).
// La collision réelle « g a » (cette table naviguait vers /approbations PENDANT
// que `AppLauncher.jsx` ouvrait le lanceur depuis un 2ᵉ listener privé — les
// DEUX tiraient) est tranchée en faveur de la navigation historique, documentée
// et testée ; le lanceur reçoit son binding propre, « g o ».
//
// Une entrée porte SOIT `to` (navigation), SOIT `event` (événement window,
// pour les surfaces en overlay qui n'ont pas d'URL) — jamais les deux.
export const GOTO_SHORTCUTS = [
  // ODY28 — la sortie clavier du mode immersion, jumelle du bouton ⊞ (ODY5).
  { keys: 'g g', to: '/apps', label: 'Aller au Menu d’accueil (mes apps)' },
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
  // VX9/ODY28 — le lanceur d'applications est un OVERLAY (aucune URL) : il
  // s'ouvre par l'événement window que `AppLauncher.jsx` écoute déjà, le même
  // que le bouton grille émettait. Un SEUL gestionnaire de séquences le
  // déclenche désormais (le listener privé du composant est supprimé).
  { keys: 'g o', event: 'taqinor:app-launcher', label: 'Ouvrir le lanceur d’applications' },
]

/**
 * buildAppShortcuts — ODY28 : bindings « g + lettre » DÉCLARÉS PAR LES APPS.
 * ---------------------------------------------------------------------------
 * Un `module.config.jsx` peut porter un champ OPTIONNEL `shortcut: 'x'` (une
 * lettre) ; l'app gagne alors le raccourci « g x » vers son cockpit
 * (`nav.items[0].to`, la convention de cockpit déjà lue par AppLauncher /
 * PinnedApps / la préférence d'atterrissage VX46). Aucune app n'en déclare
 * aujourd'hui : la fonction renvoie une liste vide et le comportement est
 * strictement celui d'avant — le MÉCANISME est en place, sans binding inventé
 * à la place du fondateur.
 *
 * RÉSOLUTION DES COLLISIONS, dans cet ordre :
 *   1. les raccourcis du noyau (`coreShortcuts`, ci-dessus) gagnent toujours ;
 *   2. entre apps, l'ORDRE DU REGISTRE tranche (premier arrivé, premier servi —
 *      `moduleConfigs` est trié par `order` puis `key`, donc déterministe).
 * Toute collision est RENVOYÉE (jamais avalée) pour être affichée dans l'aide
 * « ? » : un raccourci qui ne marche pas doit être visible, pas mystérieux.
 *
 * Fonction PURE : `configs` est passé en argument (jamais importé ici) pour que
 * ce module reste exécutable par `node --test` — `router/moduleRoutes.jsx`
 * utilise `import.meta.glob`, qui n'existe qu'au travers de Vite.
 *
 * @returns {{bindings: Array, conflicts: Array<{keys, app, wins}>}}
 */
export function buildAppShortcuts(configs, coreShortcuts = []) {
  const owner = new Map()
  for (const s of coreShortcuts || []) owner.set(s.keys, 'noyau')
  const bindings = []
  const conflicts = []
  for (const cfg of configs ?? []) {
    const raw = typeof cfg?.shortcut === 'string' ? cfg.shortcut.trim().toLowerCase() : ''
    if (!/^[a-z]$/.test(raw)) continue
    const to = cfg.nav?.items?.[0]?.to
    if (!to) continue
    const keys = `g ${raw}`
    if (owner.has(keys)) {
      conflicts.push({ keys, app: cfg.key, wins: owner.get(keys) })
      continue
    }
    owner.set(keys, cfg.key)
    bindings.push({ keys, to, label: `Aller à ${cfg.nav?.label ?? cfg.key}`, appKey: cfg.key })
  }
  return { bindings, conflicts }
}

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

// NTUX18 — raccourcis d'ÉDITION documentés dans la cheatsheet enrichie :
// navigation clavier type tableur dans les colonnes éditables du DataTable
// (NTUX8) — gérés LOCALEMENT par le moteur de grille (EditableCell.jsx),
// pas des raccourcis GLOBAUX comme les tables « g x »/« c x » ci-dessus,
// mais listés ici pour que la cheatsheet « ? » les regroupe sous « Édition ».
export const EDIT_SHORTCUTS = [
  { keys: 'Tab', label: 'Cellule éditable suivante (grille)' },
  { keys: '⇧ Tab', label: 'Cellule éditable précédente (grille)' },
  { keys: 'Entrée', label: 'Valider la cellule, passer à la ligne suivante' },
  { keys: 'Échap', label: 'Annuler l’édition de la cellule en cours' },
]

// APX31 — parcours d'une LISTE au clavier (patron Gmail/Superhuman). Existait
// déjà sur la file de leads (LW) ; les tickets SAV l'ont désormais aussi —
// c'est l'agent qui en traite 40 par jour qui en a le plus besoin. Groupe
// distinct d'« Édition » : on se DÉPLACE, on ne modifie rien.
export const LIST_SHORTCUTS = [
  { keys: 'J', label: 'Enregistrement suivant dans la liste' },
  { keys: 'K', label: 'Enregistrement précédent dans la liste' },
  { keys: 'Entrée', label: 'Ouvrir l’enregistrement' },
  { keys: 'Échap', label: 'Fermer le panneau de détail' },
]

// NTUX18 — filtre la cheatsheet par un texte libre (recherche EN DIRECT dans
// la cheatsheet elle-même) : ne garde, dans chaque groupe `{title, items}`,
// que les raccourcis dont le LIBELLÉ contient la requête (insensible à la
// casse). Un groupe sans correspondance disparaît entièrement de l'affichage
// ; une requête vide renvoie tous les groupes inchangés. Module PUR (aucune
// dépendance React), testable isolément.
export function filterShortcutGroups(groups, query) {
  const q = String(query ?? '').trim().toLowerCase()
  if (!q) return groups
  return (groups || [])
    .map((g) => ({ ...g, items: (g.items || []).filter((it) => String(it.label ?? '').toLowerCase().includes(q)) }))
    .filter((g) => g.items.length > 0)
}

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
