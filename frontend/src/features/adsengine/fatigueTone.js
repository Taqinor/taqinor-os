// Teinte + libellé de la pastille de fatigue créative (source unique des écrans
// annonce et cockpit — ENF19, ex-duplicat littéral).
export function fatigueTone(fatigue) {
  if (!fatigue) return { bg: '#f1f5f9', color: '#64748b', label: 'Inconnu' }
  if (fatigue.insufficient_data) return { bg: '#f1f5f9', color: '#64748b', label: 'Historique insuffisant' }
  if (!fatigue.fired) return { bg: '#dcfce7', color: '#166534', label: 'Pas de fatigue' }
  return fatigue.severity === 'critique'
    ? { bg: '#fee2e2', color: '#991b1b', label: 'Fatigue confirmée' }
    : { bg: '#ffedd5', color: '#9a3412', label: 'Fatigue possible' }
}
