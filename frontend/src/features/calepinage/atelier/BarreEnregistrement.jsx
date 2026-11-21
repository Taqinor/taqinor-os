import { formaterHeureBrouillon } from './contexteAtelier'

/* ACAL399 — barre d'enregistrement du calepinage, collée en bas de la fenêtre : le bouton se
   voit sans défiler, avec l'état de la scène (« Modifications non enregistrées » / « Enregistré
   à HH:MM »). `children` : emplacement du résumé (ACAL401). État d'écran seulement : l'heure
   vient de la réponse 2xx, rien n'est stocké. */
export default function BarreEnregistrement({
  libelle, enCours, desactive, onEnregistrer, modifiee, enregistreLe, statut, erreur, children,
}) {
  const heure = enregistreLe ? formaterHeureBrouillon(enregistreLe) : ''
  const etat = modifiee ? 'Modifications non enregistrées'
    : (heure ? `Enregistré à ${heure}` : null)
  return (
    <div className="sticky bottom-0 z-30 mt-6 border-t border-border bg-card p-3 backdrop-blur"
      data-testid="cal-enregistrer-calepinage">
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" onClick={onEnregistrer} disabled={desactive}
          className="inline-flex items-center justify-center gap-3 bg-success px-6 py-3 text-base font-bold text-success-foreground disabled:cursor-not-allowed disabled:opacity-60">
          {enCours && (
            <span aria-hidden="true"
              className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
          )}
          <span>{enCours ? 'Enregistrement en cours…' : libelle}</span>
        </button>
        {etat && (
          <p className={`text-sm ${modifiee ? 'text-primary' : 'text-muted-foreground'}`}
            role="status" data-testid="cal-etat-enregistrement">{etat}</p>
        )}
        {children}
      </div>
      {statut && <p className="mt-2 text-sm text-muted-foreground" aria-live="polite">{statut}</p>}
      {erreur && (
        <p className="mt-2 text-sm text-destructive" role="alert" data-testid="cal-erreur-enregistrement">{erreur}</p>
      )}
    </div>
  )
}
