// « Batteries au départ » — choix PURS (aucun chiffre calculé) : quelle ligne
// est LA batterie de l'option « avec », et quelle quantité le serveur a
// recommandée pour elle. Lus par `generator/ControleBatteriesDepart.jsx`.
import { formatNumber } from '../../../lib/format'
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

/**
 * Phrase « onduleur d'extension » (fondateur 17/11/2026), à partir de
 * `onduleur_extension` servi par le serveur — aucun chiffre calculé ici.
 * `nbChoisi` (nombre de batteries au départ) alimente « (N à ajouter plus tard) » ;
 * absent ⇒ la parenthèse est omise. `null` si la donnée serveur est absente.
 */
export function phraseOnduleurExtension(ext, nbChoisi) {
  const retenu = ext?.retenu
  const suffisant = ext?.suffisant
  const max = ext?.batteries_max
  if (!retenu || !suffisant || !Number.isFinite(Number(retenu.kw_ac)) || !Number.isFinite(Number(suffisant.kw_ac))) return null
  const kw = (o) => {
    const q = Number(o.quantite)
    return `${q > 0 && q !== 1 ? `${formatNumber(q)} × ` : ''}${formatNumber(o.kw_ac)} kW`
  }
  const choisi = Number(nbChoisi)
  const reste = Number.isFinite(max) && Number.isFinite(choisi) && nbChoisi != null ? max - choisi : null
  const jusqua = Number.isFinite(max)
    ? ` : jusqu'à ${formatNumber(max)} batteries${reste > 0 ? ` (${formatNumber(reste)} à ajouter plus tard)` : ''}`
    : ''
  return `Onduleur hybride ${kw(retenu)} retenu pour l'extension${jusqua}. `
    + `Un onduleur de ${kw(suffisant)} suffirait pour l'installation de départ.`
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
