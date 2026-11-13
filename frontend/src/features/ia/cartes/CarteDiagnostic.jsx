import { Copy } from 'lucide-react'
import { Button } from '../../../ui'
import { toast } from '../../../ui/confirm'
import { instantaneDiagnostic } from '../../../lib/tamponDiagnostic'
import { texteDiagnostic } from './diagnosticTexte'

/* COP-F4 — carte « diagnostic » (administrateurs) : un résumé lisible de ce qui a
   cassé et de l'état de l'assistant, plus « Copier pour Claude Code » (texte
   prêt à coller : routes, statuts, identifiants de requête, erreurs — aucune
   donnée client). */

function copierTexte(texte) {
  return navigator.clipboard.writeText(texte)
    .then(() => toast.success('Diagnostic copié.'))
    .catch(() => toast.error('Copie impossible : sélectionnez le texte à la main.'))
}

export default function CarteDiagnostic({ carte }) {
  const d = carte.donnees
  const problemes = d.problemes ?? []
  const a = d.assistant
  return (
    <div>
      <p className="text-sm font-semibold">Diagnostic ({d.jours ?? 1} j)</p>
      {problemes.length === 0
        ? <p className="mt-1 text-sm text-muted-foreground">Aucun problème signalé.</p>
        : (
          <ul className="mt-1.5 space-y-1.5">
            {problemes.slice(0, 5).map((p, i) => (
              <li key={i} className="text-xs">
                <span className="font-medium">{p.methode} {p.route}</span> → {p.statut_reponse}
                {' '}· {p.occurrences} fois · {p.personnes} pers.{p.classe ? ` · ${p.classe}` : ''}
              </li>
            ))}
          </ul>
        )}
      {a && (
        <p className="mt-2 text-xs text-muted-foreground">
          Assistant : {a.questions} questions · {a.erreurs} erreurs · repli {Math.round((a.part_repli || 0) * 100)} %
          {a.signalements?.length ? ` · ${a.signalements.length} signalement(s)` : ''}
        </p>
      )}
      <Button variant="outline" size="sm" className="mt-2.5 min-h-10"
        onClick={() => copierTexte(texteDiagnostic(d, instantaneDiagnostic()))}>
        <Copy className="size-4" aria-hidden="true" />
        Copier pour Claude Code
      </Button>
    </div>
  )
}
