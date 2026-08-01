/* APX11 — L'IDENTITÉ VENTES, en un seul endroit.
   ---------------------------------------------------------------------------
   Avant APX11, `brass` (l'accent du module Ventes déclaré dans
   `features/ventes/module.config.jsx`) n'apparaissait que dans le générateur :
   les écrans de flux (liste devis, factures, relances, bons de commande)
   n'avaient AUCUN signe visuel d'appartenance. On réutilise ici le patron
   déjà en place partout ailleurs (Header/Sidebar/HomeMenu posent
   `--module-accent` en style inline, cf. `Sidebar.jsx:204`) plutôt que
   d'inventer un second mécanisme d'accent.

   Deux exports seulement :
     - VENTES_ACCENT_STYLE : le style à poser sur un conteneur pour que
       `var(--module-accent)` y vaille le brass du module.
     - ACCENT_RAIL : la classe du liseré (définie dans index.css, section
       APX11) — un filet de 3 px à gauche, teinté par --module-accent. */

export const VENTES_ACCENT_STYLE = { '--module-accent': 'var(--module-accent-brass)' }

export const ACCENT_RAIL = 'app-accent-rail'
