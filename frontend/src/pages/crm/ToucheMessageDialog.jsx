// MRY32 — implémentation DÉPLACÉE vers `features/crm/relances/
// ToucheMessageDialog.jsx` (la frise de la fiche lead, un fichier `features/`,
// doit pouvoir l'ouvrir sans jamais importer depuis `pages/`). Ré-export pur
// pour ne rien casser des appelants de ce chemin historique (le widget
// Cockpit, l'écran de suivi, et `ToucheMessageDialog.mry14.test.jsx`).
export { default } from '../../features/crm/relances/ToucheMessageDialog'
