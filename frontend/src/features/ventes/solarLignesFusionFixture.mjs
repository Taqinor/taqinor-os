// Fixture partagée des tests solar.* : panier « sans / avec » à fusion de
// variantes (réseau Huawei, hybride Deye, batterie, deux quantités de panneaux,
// transport). Une copie fraîche à chaque appel — jamais d'état partagé.
export const lignesFusionSansAvec = () => [
  { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: 1, prix_unit_ttc: 20000, variante: '' },
  { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: 1, prix_unit_ttc: 28000, variante: '' },
  { designation: 'Batterie Dyness 10 kWh', quantite: 1, prix_unit_ttc: 17000, variante: '' },
  { designation: 'Panneau Canadien Solar 710W', quantite: 10, prix_unit_ttc: 1400, variante: 'sans' },
  { designation: 'Panneau Canadien Solar 710W', quantite: 17, prix_unit_ttc: 1400, variante: 'avec' },
  { designation: 'Transport', quantite: 1, prix_unit_ttc: 1000, variante: '' },
]
