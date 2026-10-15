/* Étape de chantier bloquée par un gate (CH6 / CHT22) : bandeau d'alerte et
   liste à puces des raisons — jamais un message brut. `children` : champs de
   dérogation propres à l'écran (motif d'acompte, réouverture…). */
export default function RaisonsBlocageGate({ raisons, children }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-1 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive"
      data-testid="ch6-blocked-reasons"
    >
      <strong>Étape bloquée par un gate&nbsp;:</strong>
      <ul className="flex flex-col gap-0.5">
        {raisons.map((r) => <li key={r}>• {r}</li>)}
      </ul>
      {children}
    </div>
  )
}
