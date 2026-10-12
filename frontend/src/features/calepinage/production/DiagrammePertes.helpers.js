// ENF22 — helpers extraits de DiagrammePertes.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

export const CASCADE_DEPART = 'Irradiance incidente'

export const CASCADE_ARRIVEE = 'Énergie livrée'

/**
 * CALX48 / ACAL140 — la cascade construite depuis `resultat['cascade'].etapes`
 * (CALX141), PAS depuis la liste plate. Les barres viennent des ÉNERGIES
 * servies (`kwh_avant` / `kwh_apres`, rapportées à l'énergie incidente =
 * `kwh_avant` de la première étape), JAMAIS d'une soustraction de pourcentages
 * relatifs : deux pertes de 10 % composent 19 %, pas 20 % (la composition est
 * celle du serveur, `chaine_pertes._total_pct`). Un GAIN (bifacial : énergie
 * après > avant) est posé AU-DESSUS du niveau courant ; une étape OMISE
 * (`perte_pct: null`) traverse à hauteur nulle, hachurée, JAMAIS un zéro qui
 * prétendrait qu'elle n'a rien coûté. « Énergie livrée » = 100 − `total_pct`
 * servi (repli : dernier niveau en énergie).
 *
 * Sans énergie servie (aucun `kwh_avant`), repli MULTIPLICATIF sur `perte_pct`
 * (jamais additif).
 */
export function construireCascadeDetaillee(etapes, totalPct = null) {
  const reference = Number(etapes[0]?.kwh_avant)
  const parKwh = Number.isFinite(reference) && reference > 0
  const niveauKwh = (kwh) => (parKwh && kwh !== null && kwh !== undefined
    && Number.isFinite(Number(kwh)) ? (Number(kwh) / reference) * 100 : null)

  let courant = 100
  const lignes = [{ nom: CASCADE_DEPART, base: 0, valeur: 100, total: true, niveau: 100 }]
  for (const etape of etapes) {
    const omise = etape.perte_pct === null || etape.perte_pct === undefined
    let haut = courant
    let bas = courant
    if (!omise) {
      const hautKwh = niveauKwh(etape.kwh_avant)
      const basKwh = niveauKwh(etape.kwh_apres)
      if (basKwh !== null) {
        haut = hautKwh ?? courant
        bas = basKwh
      } else {
        bas = courant * (1 - (Number(etape.perte_pct) || 0) / 100)
      }
    }
    lignes.push({
      nom: etape.libelle || etape.etape,
      base: Math.max(Math.min(haut, bas), 0),
      valeur: Math.abs(haut - bas),
      total: false,
      niveau: bas,
      source: etape.source ?? null,
      poste: etape.etape,
      rang: etape.rang,
      omise,
      motif: etape.motif_omission || '',
      pertePct: etape.perte_pct,
      kwhAvant: etape.kwh_avant ?? null,
      kwhApres: etape.kwh_apres ?? null,
      gain: Boolean(etape.gain) || bas > haut,
    })
    courant = bas
  }
  const livree = typeof totalPct === 'number' && Number.isFinite(totalPct)
    ? 100 - totalPct : courant
  lignes.push({
    nom: CASCADE_ARRIVEE, base: 0, valeur: Math.max(livree, 0), total: true,
    arrivee: true, niveau: livree,
  })
  return lignes
}
