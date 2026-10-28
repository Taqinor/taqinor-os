// RGEN5 — miroir EXACT de `quote_engine/pricing.py::_economie_avec_nette`
// (RHOR6) : hors moteur horaire, un devis au niveau de règles 3
// (`regles_au_moins(devis, 3)`) imprime l'économie « avec batterie » NETTE de
// la perte aller-retour de sa part stockée, relève la facture « avec »
// d'autant, et le cashflow lit ce chiffre net (part stockée 0 : déduction
// unique). `series` (facultatif) : séries mensuelles remises à l'échelle du net
// (Σ des 12 points = la carte) — tableaux de nombres ou d'objets `cle`.
export function economieAvecNette(economie, factureAvec, partStockee, {
  nette = false, roundtrip, series = [],
} = {}) {
  if (!nette || !(partStockee > 0) || !(economie > 0)) return { economie, factureAvec, partStockee }
  const brut = Math.round(economie)
  const net = Math.round(brut * (1 - (1 - roundtrip) * partStockee))
  for (const { valeurs, cle } of series) {
    valeurs.forEach((v, i) => {
      if (cle) v[cle] = v[cle] * (net / economie)
      else valeurs[i] = v * (net / economie)
    })
  }
  return { economie: net, factureAvec: factureAvec == null ? factureAvec : factureAvec + (brut - net), partStockee: 0 }
}
