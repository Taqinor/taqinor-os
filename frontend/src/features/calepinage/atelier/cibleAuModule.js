// T4-X2-001 / T4-X3-009 (lane E9) — LA cible de l'atelier dite dans le module POSÉ, UN seul lecteur pour tout l'atelier :
// la première pose automatique (useAtelierBoot), la carte « Couvrir la facture » (étape Panneaux), le bandeau des
// Résultats et la feuille Avancé. La conception est une PUISSANCE : un module d'une autre puissance en pose le compte
// SERVI par `modules-disponibles/` (`panneaux_selon_watt`, la règle du moteur `panneaux_pour_la_meme_puissance`) —
// jamais un compte calculé ici. Le compte PROPRE de la conception, quand il est dit, nomme son panneau.
import { formatNumber } from '../../../lib/format'

/** « 8 panneaux de 550 W » (ou « 8 panneaux » quand la puissance n'est pas servie). */
export function panneauxDuModule(panneaux, watt) {
  const n = `${formatNumber(panneaux, { decimals: 0 })} panneau${panneaux > 1 ? 'x' : ''}`
  return Number(watt) > 0 ? `${n} de ${formatNumber(Number(watt))} W` : n
}

/** `{ panneaux, kwc, watt, convertie, conception }` — `panneaux` : le compte à poser dans le module de `wattPose` ;
    `convertie` : le module posé n'a pas la puissance de la conception (`conception` dit alors son propre compte,
    « 8 panneaux de 550 W ») ; module absent de la table servie : `panneaux: null` (la puissance seule, rien à poser).
    `null` sans cible. Sans puissance connue d'un côté : la cible telle quelle. */
export function cibleAuModule(cible, wattPose, table) {
  if (!cible) return null
  const { panneaux, kwc = null, wattConception = null } = cible
  const watt = Number(wattPose) || null
  const meme = !watt || !(Number(wattConception) > 0) || Math.abs(watt - Number(wattConception)) < 0.5
  if (meme || typeof panneaux !== 'number') return { panneaux, kwc, watt: watt ?? wattConception, convertie: false, conception: null }
  const servi = table?.[String(watt)]
  return {
    panneaux: Number.isInteger(servi) ? servi : null, kwc, watt, convertie: true,
    conception: panneauxDuModule(panneaux, wattConception),
  }
}
