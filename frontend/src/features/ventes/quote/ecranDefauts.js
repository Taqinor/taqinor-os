// SPL43 — LES DÉFAUTS D'ÉCRAN DU GÉNÉRATEUR (déplacés tels quels de
// DevisGenerator.jsx : aucune ligne de logique n'a changé). Les hooks du
// générateur (SPL44-SPL55) les importent d'ici : un hook ne peut pas importer
// depuis le fichier du composant (import circulaire).
import { DAY_USAGE_DEFAULTS, TVA_STANDARD_DEFAUT } from '../solar.js'
import { formatNumber } from '../../../lib/format.js'

// CJ2b — libellés FR des 3 saisons de l'étude horaire (etude.saisons, clés
// serveur inchangeables).
export const SAISON_LABELS = { hiver: 'Hiver', mi_saison: 'Mi-saison', ete: 'Été' }

// QJR586 (contrat QJR506) — la « ville de calcul » du lead SERVIE par le
// serveur (`ville_effective` : rattachement VREF prioritaire), la même que le
// moteur, le PDF et le transport. Repli sur `ville` pour un lead servi sans
// la clé (ancienne réponse) ; '' jamais null.
export const villeEffectiveLead = (lead) => (lead?.ville_effective ?? lead?.ville) || ''

// QJR641 — le Marché est la SEULE source : le sélecteur « Type d'installation »
// (qui doublonnait le marché sans jamais le changer) est supprimé ; le défaut
// de la part diurne se DÉRIVE du marché (libellés du simulateur →
// `DAY_USAGE_DEFAULTS`). La valeur persistée `part_diurne_pct` (QJR528) prime
// à la réouverture.
export const INST_TYPE_PAR_MODE = {
  residentiel: 'Résidentielle',
  agricole: 'Agricole',
}
export const partDiurneParDefaut = (mode) =>
  DAY_USAGE_DEFAULTS[INST_TYPE_PAR_MODE[mode] ?? 'Résidentielle'] ?? 50

// VX93 — défaut intelligent : dernier taux TVA saisi sur une ligne ajoutée à la
// main (localStorage). Repli sur le taux standard (20 %) si absent. Toujours
// modifiable ligne par ligne ; jamais bloquant.
export const LAST_TVA_KEY = 'taqinor.devisGenerator.lastTva'
export const lireLastTva = () => {
  try { return window.localStorage.getItem(LAST_TVA_KEY) || String(TVA_STANDARD_DEFAUT) }
  catch { return String(TVA_STANDARD_DEFAUT) }
}
export const ecrireLastTva = (v) => {
  try { if (v !== '' && v != null) window.localStorage.setItem(LAST_TVA_KEY, String(v)) }
  catch { /* no-op silencieux */ }
}

// QJR581 — durée pendant laquelle les états posés par le mappeur `?edit=` (et
// ses relectures immédiates : lead, réouverture) forment la RÉFÉRENCE « rien
// n'a changé » de l'Édition complète.
export const FENETRE_REFERENCE_MS = 1500

export const fmtNum = (v) => (v !== null && v !== undefined) ? formatNumber(v) : 'N/A'
