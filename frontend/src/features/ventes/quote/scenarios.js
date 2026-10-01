// ERR-QJR576-602-RESIDUS-SUPERSEDE — LE vocabulaire des scénarios de
// l'Édition complète, tapé UNE seule fois. Module FEUILLE (n'importe rien) :
// `sizingReducer.js` importe `solar.js`, donc `solar.js` ne peut pas importer
// le reducer sans cycle — les deux lisent ces constantes ICI.
// Libellés EXACTS du moteur PDF (constantes SCENARIO_* d'apps/ventes/
// services.py) : jamais reformulés.
// source-choix: ventes.utils.options.SCENARIOS_ALTERNATIVE
export const SCENARIOS_VALIDES = ['Les deux (Sans + Avec)', 'Sans batterie', 'Avec batterie']
export const [SCENARIO_LES_DEUX, SCENARIO_SANS, SCENARIO_AVEC] = SCENARIOS_VALIDES
