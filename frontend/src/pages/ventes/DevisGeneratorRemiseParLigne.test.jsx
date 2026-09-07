// QJRREM (fondateur 07/09/2026) — le CALCUL derrière la remise par ligne de
// l'écran de création (`DevisGenerator.jsx` : `lignesRemiseesTtc`). Verrouille
// exactement la population et la formule décrites dans le commentaire de
// `DevisGenerator.jsx` : `totalHt` du miroir reçoit le TTC de ligne
// (quantite × prix_unit_ttc, comme `DevisLineRow.lineTtc`), la population est
// celle de `ligneCompteDansTotaux` (produit non optionnelle — `optionnelle`/
// `typeLigne` mappés depuis les champs de l'écran), jamais celle
// d'`optionTotalsTTC` (paniers Sans/Avec par mots-clés/`variante`).
//
// Fonctions PURES, aucun rendu React : `.test.jsx` par cohérence d'emplacement
// avec les autres tests de cet écran (frontend/src/pages/ventes/), exécuté par
// vitest comme eux — voir DevisLineRowRemise.test.jsx pour l'AFFICHAGE.
import { describe, it, expect } from 'vitest'
import { repartirRemiseParLigne } from '../../features/ventes/remise'
import { optionTotalsTTC } from '../../features/ventes/solar'

// Même formule que DevisGenerator.jsx (`lignesRemiseesTtc`) et DevisLineRow.jsx
// (`lineTtc`) : cet écran est 100 % TTC, jamais une conversion HT.
const lineTtc = (l) => (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0)
// Même mapping que DevisGenerator.jsx vers le miroir : `totalHt` reçoit le
// TTC de ligne, `optionnelle`/`typeLigne` passent tels quels (le miroir sait
// déjà lire ces deux champs via `ligneCompteDansTotaux`).
const versMiroir = (lignes) => lignes.map(l => ({
  totalHt: lineTtc(l), optionnelle: l.optionnelle, typeLigne: l.typeLigne,
}))

describe('QJRREM — DevisGenerator : population + alignement de la remise par ligne', () => {
  it('alignement : une valeur PAR LIGNE, dans le même ordre — jamais un tableau raccourci', () => {
    const lignes = [
      { quantite: '2', prix_unit_ttc: '1000', typeLigne: 'produit', optionnelle: false },
      { quantite: '1', prix_unit_ttc: '1', typeLigne: 'note', optionnelle: false },
      { quantite: '3', prix_unit_ttc: '100', typeLigne: 'produit', optionnelle: false },
    ]
    const parts = repartirRemiseParLigne(versMiroir(lignes), '10')
    expect(parts).toHaveLength(lignes.length)
  })

  it('une ligne OPTIONNELLE (case Option cochée, XSAL5 : add-on hors total) ne reçoit jamais de part — null', () => {
    const lignes = [
      { quantite: '2', prix_unit_ttc: '1000', typeLigne: 'produit', optionnelle: false },
      { quantite: '1', prix_unit_ttc: '500', typeLigne: 'produit', optionnelle: true },
      { quantite: '3', prix_unit_ttc: '100', typeLigne: 'produit', optionnelle: false },
    ]
    const parts = repartirRemiseParLigne(versMiroir(lignes), '10')
    expect(parts[1]).toBeNull()
    expect(parts[0]).not.toBeNull()
    expect(parts[2]).not.toBeNull()
  })

  it('une ligne de SECTION ou de NOTE (XSAL14, sans prix) ne reçoit jamais de part — null, même si son "prix" est non nul', () => {
    const lignes = [
      { quantite: '2', prix_unit_ttc: '1000', typeLigne: 'produit', optionnelle: false },
      { quantite: '1', prix_unit_ttc: '1', typeLigne: 'section', optionnelle: false },
      { quantite: '1', prix_unit_ttc: '1', typeLigne: 'note', optionnelle: false },
      { quantite: '3', prix_unit_ttc: '100', typeLigne: 'produit', optionnelle: false },
    ]
    const parts = repartirRemiseParLigne(versMiroir(lignes), '10')
    expect(parts[1]).toBeNull()
    expect(parts[2]).toBeNull()
    expect(parts[0]).not.toBeNull()
    expect(parts[3]).not.toBeNull()
  })

  // Fixture reprise VALEUR POUR VALEUR de `remise.test.mjs`
  // (« sept panneaux + onduleur + pose — remise 5 % »), elle-même produite
  // par le noyau PYTHON (`test_remise_par_ligne.py`) — quantite=1 sur chaque
  // ligne pour que `totalHt` du miroir reste EXACTEMENT le `prix_unit_ttc`
  // d'origine. Prouve que le mapping TTC de cet écran (quantite × prix_unit_ttc)
  // fait recoller la répartition avec la valeur CERTIFIÉE, pas une valeur
  // recalculée localement.
  it('mapping TTC de l’écran : recolle AU CENTIME avec la fixture appariée noyau Python', () => {
    const lignes = [
      { quantite: '1', prix_unit_ttc: '8166.69', typeLigne: 'produit', optionnelle: false },
      { quantite: '1', prix_unit_ttc: '12500', typeLigne: 'produit', optionnelle: false },
      { quantite: '1', prix_unit_ttc: '3333.33', typeLigne: 'produit', optionnelle: false },
    ]
    const parts = repartirRemiseParLigne(versMiroir(lignes), '5')
    expect(parts.map(p => p.toFixed(2))).toEqual(['7758.36', '11875.00', '3166.66'])
  })

  // ── Composition réaliste (6 lignes, TTC à 2 décimales, quantités
  // entières, remise 5 %) — AUCUNE ligne `variante`, AUCUN onduleur réseau
  // dans la désignation : `appartientAuPanierAvec` (solar.js) ne retire donc
  // AUCUNE ligne — le panier « avec » == TOUTES les lignes, exactement la
  // population de `ligneCompteDansTotaux` sur cette fixture. Valeurs
  // vérifiées avec le VRAI code du dépôt (voir rapport de la tâche) : écart
  // ZÉRO sur cette composition — le cas mono-composition documenté dans
  // DevisGenerator.jsx.
  it('composition réaliste sans variante/onduleur réseau : Σ des montants par ligne == optionTotalsTTC(...).totalAvec, au centime', () => {
    const lignes = [
      { designation: 'Panneau solaire 550W', quantite: '12', prix_unit_ttc: '1250.50', typeLigne: 'produit', optionnelle: false },
      { designation: 'Structure aluminium toiture inclinée', quantite: '12', prix_unit_ttc: '180.25', typeLigne: 'produit', optionnelle: false },
      { designation: 'Câble solaire 6mm rouleau 100m', quantite: '3', prix_unit_ttc: '450.75', typeLigne: 'produit', optionnelle: false },
      { designation: 'Coffret protection DC AC', quantite: '2', prix_unit_ttc: '890.00', typeLigne: 'produit', optionnelle: false },
      { designation: 'Disjoncteur différentiel', quantite: '4', prix_unit_ttc: '210.30', typeLigne: 'produit', optionnelle: false },
      { designation: 'Main d’œuvre installation', quantite: '1', prix_unit_ttc: '3500.00', typeLigne: 'produit', optionnelle: false },
    ]
    const parts = repartirRemiseParLigne(versMiroir(lignes), 5)
    const sommeCentimes = parts.reduce((s, p) => s + Math.round((p ?? 0) * 100), 0)

    const totals = optionTotalsTTC(lignes, 5)
    expect(totals.totalAvec).toBe(totals.totalSans) // aucune ligne variantée : les deux paniers sont identiques ici
    expect(sommeCentimes).toBe(Math.round(totals.totalAvec * 100))
  })

  it('invariant #10, formulation TTC de l’écran : la somme des lignes retenues == arrondiCentime(brut) − arrondiCentime(remise), sans ligne sautée', () => {
    const lignes = [
      { quantite: '2', prix_unit_ttc: '1500', typeLigne: 'produit', optionnelle: false },
      { quantite: '1', prix_unit_ttc: '999.99', typeLigne: 'produit', optionnelle: false },
      { quantite: '5', prix_unit_ttc: '10', typeLigne: 'produit', optionnelle: false },
    ]
    const parts = repartirRemiseParLigne(versMiroir(lignes), '15')
    // Aucune part manquante (toutes les lignes sont des lignes produit non
    // optionnelles) — l'invariant Σ n'a de sens que si rien n'a été perdu.
    expect(parts.every(p => p !== null)).toBe(true)
    const brut = lignes.reduce((s, l) => s + lineTtc(l), 0)
    const sommeCentimes = parts.reduce((s, p) => s + Math.round(p * 100), 0)
    // Remise 15 % arrondie au centime, puis net arrondi au centime — les
    // DEUX arrondis du miroir (jamais un flottant naïf `brut * 0.85`).
    const remiseCentimes = Math.round(Math.round(brut * 100) * 15 / 100)
    expect(sommeCentimes).toBe(Math.round(brut * 100) - remiseCentimes)
  })
})
