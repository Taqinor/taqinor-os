/* Tuiles de chiffres cliquables du bandeau d'un cockpit de module (CRM, Ventes) :
   chaque tuile affiche un libellé + une valeur et ouvre sa cible via
   `onOpen(to)`. `colonnes` = classes de grille (nombre de colonnes mobile). */
export function ChiffresCockpit({ stats, onOpen, colonnes, testId }) {
  return (
    <div className={`mt-2 grid ${colonnes} gap-3 sm:grid-cols-3`} data-testid={testId}>
      {stats.map((s) => (
        <button
          key={s.label}
          type="button"
          onClick={() => onOpen(s.to)}
          className="rounded-lg border border-border bg-card p-3 text-left transition-colors hover:bg-muted"
        >
          <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {s.label}
          </span>
          <span className="font-display text-xl font-semibold tabular-nums">{s.value}</span>
        </button>
      ))}
    </div>
  )
}
