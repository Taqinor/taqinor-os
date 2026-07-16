/* VX126 — Utilitaire partagé de « press » (retour tactile au clic/tap) calqué
   sur le pattern prouvé de Button.jsx : `[@media(hover:hover)]:active:scale-[0.98]`
   + léger assombrissement, réservé au pointeur fin (jamais déclenché par le
   « survol émulé » du tactile). Sert de socle commun à tous les contrôles
   `ui/*` qui n'avaient jusqu'ici AUCUN retour pressé (Switch, Slider,
   Segmented, Tabs, Checkbox, Radio, items Select/Combobox/MultiSelect/
   DropdownMenu/ContextMenu, cellules DatePicker) — évite 12 courbes de press
   divergentes et la re-frappe sur mobile 4G faute de feedback visible.

   `press` = la classe de scale/assombrissement à poser sur un déclencheur/item.
   `pressCurve` = la même courbe de transition que Button (150 ms,
   cubic-bezier(0.23,1,0.32,1)) à réutiliser partout où un contrôle avait sa
   propre transition Tailwind par défaut (Switch, Progress) pour que toutes
   les primitives bougent à la même vitesse. */

export const pressCurve = 'duration-150 [transition-timing-function:cubic-bezier(0.23,1,0.32,1)]'

// Press générique : léger scale + assombrissement, uniquement sur pointeur fin.
export const press = '[@media(hover:hover)]:active:scale-[0.98] active:brightness-95'

// Press pour un item de liste/menu (pas de scale — casserait l'alignement de
// la liste — juste l'assombrissement au clic, cohérent avec le focus/hover).
export const pressItem = 'active:brightness-95'

export default press
