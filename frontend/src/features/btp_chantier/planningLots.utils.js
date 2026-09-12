/* ============================================================================
   NTCON14 — helpers PURS du planning par lot (aucun composant ici : la règle
   `react-refresh/only-export-components` interdit de mélanger composants et
   helpers dans un même fichier de `src/features/**`).
   ========================================================================== */

/* Borne temporelle du Gantt : min des débuts / max des fins sur tout ce qui
   porte une date (lots + tâches). Renvoie null si rien n'est daté. */
export function bornesPlanning(blocs) {
  const dates = []
  for (const bloc of blocs || []) {
    for (const d of [bloc.date_debut_prevue, bloc.date_fin_prevue]) {
      if (d) dates.push(d)
    }
    for (const t of bloc.taches || []) {
      for (const d of [t.date_debut_prevue, t.date_fin_prevue]) {
        if (d) dates.push(d)
      }
    }
  }
  if (!dates.length) return null
  dates.sort()
  return { debut: dates[0], fin: dates[dates.length - 1] }
}

/* Position/largeur d'une barre en % de la fenêtre du planning. */
export function barre(bornes, debut, fin) {
  if (!bornes || !debut || !fin) return null
  const t0 = Date.parse(bornes.debut)
  const t1 = Date.parse(bornes.fin)
  const span = Math.max(t1 - t0, 1)
  const a = Math.max(Date.parse(debut) - t0, 0)
  const b = Math.min(Date.parse(fin) - t0, span)
  return {
    left: `${(a / span) * 100}%`,
    width: `${Math.max(((b - a) / span) * 100, 2)}%`,
  }
}

/* Montant formaté en MAD (cockpit NTCON21) — « — » si la valeur n'est pas un
   nombre : on n'invente jamais un chiffre. */
const MONNAIE = new Intl.NumberFormat('fr-MA', {
  style: 'currency', currency: 'MAD', maximumFractionDigits: 0,
})

export function formatMontant(valeur) {
  const nombre = Number(valeur)
  if (!Number.isFinite(nombre)) return '—'
  return MONNAIE.format(nombre)
}
