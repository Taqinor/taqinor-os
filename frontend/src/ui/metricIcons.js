import { Sun, Zap, Leaf, Wallet, HardHat } from 'lucide-react'

/* VX157 — Vocabulaire d'icône UNIFIÉ pour les grandeurs métier (kWc,
   production, CO₂ évité, économies, chantier). Avant ce fichier, chaque écran
   choisissait la sienne au cas par cas (ex. Co2Page important Leaf/Sprout/Zap
   ad hoc) — un écran qui affiche une de ces grandeurs consomme METRIC_ICONS
   (ou getMetricIcon) pour que le même chiffre affiche toujours le même
   symbole partout dans l'app. */
export const METRIC_ICONS = {
  production: Sun,     // soleil = production (kWh)
  kwc: Zap,             // éclair = puissance installée (kWc)
  co2: Leaf,            // feuille = CO₂ évité
  economies: Wallet,    // portefeuille = économies (MAD)
  chantier: HardHat,    // casque = chantier / installation
}

/** Icône d'une grandeur métier connue, ou `undefined` si la clé est inconnue
 * (l'appelant garde alors son propre repli plutôt qu'une icône par défaut). */
export function getMetricIcon(key) {
  return METRIC_ICONS[key]
}

export default METRIC_ICONS
