// SPL46 — déplacé tel quel de DevisGenerator.jsx.
// QJR572 — sous un choix que le registre IMPOSE : le dire, et offrir le
// retour à l'automatique (DELETE ?chemin=, `regenererOverride`).
export default function IndicationRegistre({ chemin, busy, onRegenerer }) {
  return (
    <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground"
       data-testid={`registre-impose-${chemin}`}>
      Imposé par le registre —
      <button type="button" className="underline underline-offset-2 hover:text-foreground disabled:opacity-50"
              disabled={busy} onClick={() => onRegenerer(chemin)}>
        revenir à l&apos;automatique
      </button>
    </p>
  )
}
