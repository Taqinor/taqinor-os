// « Batteries au départ » — choix PURS (aucun chiffre calculé) : quelle ligne
// est LA batterie de l'option « avec », et quelle quantité le serveur a
// recommandée pour elle. Lus par `generator/ControleBatteriesDepart.jsx`.
import { appartientAuPanierAvec, isBattery, texteClassement } from './classification.js'

/** L'unique ligne batterie de l'option « avec » (non optionnelle) — sinon `null`. */
export function ligneBatterieUnique(lines, produits) {
  const candidates = (lines || []).filter(l => (
    l && (l.typeLigne ?? 'produit') === 'produit' && !l.optionnelle
    && appartientAuPanierAvec(l, produits)
    && (String(l.role_devis ?? '').trim() === 'batterie'
      || (!String(l.role_devis ?? '').trim() && isBattery(texteClassement(l, produits))))
  ))
  return candidates.length === 1 ? candidates[0] : null
}

/** Quantité recommandée connue (entier > 0) pour CETTE ligne, sinon `null`. */
export function quantiteRecommandee(ligne, banque, apercuBatterie) {
  const entier = (v) => (Number.isInteger(v) && v > 0 ? v : null)
  if (banque && String(banque.produit) === String(ligne?.produit)) {
    const r = entier(banque.quantite)
    if (r) return r
  }
  return entier(apercuBatterie?.quantite_recommandee)
}
