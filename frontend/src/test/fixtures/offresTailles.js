/* ENF19 — bloc « sans batterie » de l'offre Recommandé (22 panneaux), miroir de
   apps/ventes/contract_samples/offres_tailles.json, partagé par les tests
   DevisTab et DevisOffresTailles (une seule copie du littéral). */
export function sansRecommande() {
  return {
    nb_panneaux: 22, puissance_kwc: 12.1, prix_ttc: 108900.0,
    economie_annuelle_mad: 13260.0, payback_annees: 8.21, couverture_pct: 61.0,
    production_annuelle_kwh: 19140.0,
    materiel: [{ role: 'panneau', famille: 'panneau', marque: 'Longi', modele: 'Panneau 550 W' }],
    toit_ok: true,
  }
}
