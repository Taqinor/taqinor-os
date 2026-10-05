// Bloc « niveau de relance + aperçu » de la fenêtre Relancer.
// Contrat : apps/ventes/contract_samples/facture_relance_apercu.json.
// Stepper « 1 Rappel courtois → 2 Relance → 3 Relance ferme » : le niveau
// SUGGÉRÉ (niveau_suivant) est mis en avant, le niveau choisi est cliquable.
import { formatMAD } from '../../lib/format'

export default function RelanceApercu({ apercu, niveauChoisi, onChoisir }) {
  if (!apercu) return null
  const suggere = apercu.niveau_suivant?.ordre
  return (
    <div className="grid gap-2" data-testid="relance-apercu">
      <ol className="flex flex-wrap items-center gap-2 text-sm" aria-label="Niveaux de relance">
        {(apercu.niveaux || []).map((n, i) => {
          const actif = n.ordre === niveauChoisi
          return (
            <li key={n.id} className="flex items-center gap-2">
              {i > 0 && <span aria-hidden="true">→</span>}
              <button type="button" onClick={() => onChoisir?.(n.ordre)}
                      aria-pressed={actif}
                      data-suggere={n.ordre === suggere ? 'true' : undefined}
                      className={`rounded-md border px-2 py-1 ${actif
                        ? 'border-primary bg-primary/10 font-medium' : 'border-border'}`}>
                {n.ordre} {n.nom}{n.ordre === suggere ? ' (suggéré)' : ''}
              </button>
            </li>
          )
        })}
      </ol>
      {apercu.deja_tous_envoyes && (
        <p className="text-xs text-muted-foreground">
          Les 3 niveaux ont déjà été envoyés.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Retard : {apercu.jours_retard} j · Montant dû : {formatMAD(apercu.montant_du)}
      </p>
      <div className="rounded-md border bg-muted/30 p-2 text-sm">
        <p className="text-xs text-muted-foreground">Aperçu du niveau suggéré</p>
        <p><span className="font-medium">Objet :</span> {apercu.sujet}</p>
        <p className="whitespace-pre-wrap" data-testid="relance-apercu-message">{apercu.message}</p>
      </div>
    </div>
  )
}
