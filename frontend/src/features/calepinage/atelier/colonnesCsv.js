/* ACAL753 — les colonnes que l'on peut cocher pour la série horaire (CSV).
   Le vocabulaire vient du serveur (`services/export_csv.py::COLONNES_HORAIRE`,
   échantillon `calepinage_export_csv.json`) ; ici ne figurent que le libellé
   et l'unité, en mots simples. Les quatre colonnes de date sont toujours
   envoyées en tête. */

export const COLONNES_DATE = ['annee', 'mois', 'jour', 'heure']

export const COLONNES_CSV = [
  { nom: 'production_kw', libelle: 'Production (kW)', defaut: true },
  { nom: 'irradiance_plan_w_m2', libelle: 'Rayonnement sur les panneaux (W/m²)', defaut: true },
  { nom: 'temperature_air_c', libelle: "Température de l'air (°C)", defaut: true },
  { nom: 'gb_i_w_m2', libelle: 'Rayonnement direct sur les panneaux (W/m²)' },
  { nom: 'gd_i_w_m2', libelle: 'Rayonnement diffus sur les panneaux (W/m²)' },
  { nom: 'gr_i_w_m2', libelle: 'Rayonnement réfléchi par le sol (W/m²)' },
  { nom: 'ws10m', libelle: 'Vitesse du vent à 10 m (m/s)' },
  { nom: 'h_sun_deg', libelle: 'Hauteur du soleil (°)' },
  { nom: 't_cell_c', libelle: 'Température des cellules (°C)' },
  { nom: 'p_dc_kw', libelle: 'Puissance avant onduleur (kW)' },
  { nom: 'p_ac_kw', libelle: 'Puissance après onduleur (kW)' },
  { nom: 'ecretage_kw', libelle: 'Puissance écrêtée (kW)' },
  { nom: 'charge_kwh', libelle: 'Consommation du site (kWh)' },
  { nom: 'batterie_soc_pct', libelle: 'Charge de la batterie (%)' },
  { nom: 'reseau_import_kwh', libelle: 'Énergie prise au réseau (kWh)' },
  { nom: 'reseau_export_kwh', libelle: 'Énergie envoyée au réseau (kWh)' },
]

export const COLONNES_D_OFFICE = COLONNES_CSV.filter((c) => c.defaut).map((c) => c.nom)

/** La chaîne CSV des colonnes à envoyer, ou `null` si la sélection est celle
    d'office (l'appel reste alors à deux arguments, comme avant). Les colonnes
    sont rendues DANS L'ORDRE de la liste, jamais dans l'ordre des clics. */
export function colonnesAEnvoyer(cochees) {
  const choisies = COLONNES_CSV.filter((c) => cochees.has(c.nom)).map((c) => c.nom)
  if (choisies.join(',') === COLONNES_D_OFFICE.join(',')) return null
  return [...COLONNES_DATE, ...choisies].join(',')
}
