// Les trois libellés de scénario commercial, dans un module FEUILLE (aucun
// import) : `solar.js` et `quote/sizingReducer.js` s'importent déjà l'un
// l'autre, donc la source unique ne peut vivre dans aucun des deux.
// Vocabulaire EXACT du moteur PDF (constantes SCENARIO_* d'apps/ventes/
// services.py) : jamais reformulé ailleurs.
export const SCENARIO_LES_DEUX = 'Les deux (Sans + Avec)'
export const SCENARIO_SANS = 'Sans batterie'
export const SCENARIO_AVEC = 'Avec batterie'

// Les trois libellés qui DÉCLARENT une alternative commerciale (le noyau sert
// alors UNE option, panier filtré ET règle QF9 appliquée).
// source-choix: ventes.utils.options.SCENARIOS_ALTERNATIVE
export const SCENARIOS_VALIDES = ['Les deux (Sans + Avec)', 'Sans batterie', 'Avec batterie']
