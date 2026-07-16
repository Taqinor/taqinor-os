// N91/F21/VX119 — bandeau discret d'état de la synchro terrain hors-ligne.
//
// Affiché en tête du volet de capture d'une intervention : indique si on est
// hors ligne, combien d'actions attendent d'être synchronisées, et — SIGNAL
// DISTINCT — combien ont été REJETÉES par le serveur (message + détail par
// op, jamais une disparition silencieuse ; une signature client capturée
// hors-ligne doit rester visible tant qu'elle n'est pas résolue). Bouton
// « Synchroniser » pour forcer le flush. Reste silencieux (rien affiché)
// quand on est en ligne, la file vide et aucune erreur — zéro bruit visuel
// dans le cas nominal.
import { useState } from 'react'
import { CloudOff, RefreshCw, AlertTriangle } from 'lucide-react'
import { Button, Badge } from '../../../ui'
import { useFieldOutbox } from './useFieldOutbox'

export default function OfflineSyncIndicator() {
  const { online, pending, failed, flushing, flush, discard } = useFieldOutbox()
  const [showFailed, setShowFailed] = useState(false)
  const hasFailed = failed.length > 0
  if (online && pending === 0 && !hasFailed) return null
  return (
    <div className="mt-2 flex flex-col gap-2 rounded border border-border bg-muted/40 p-2 text-[12px]">
      <div className="flex items-center gap-2">
        {!online && <CloudOff className="size-4 text-amber-600" aria-hidden="true" />}
        {hasFailed && <AlertTriangle className="size-4 text-destructive" aria-hidden="true" />}
        <span className="flex-1">
          {!online ? 'Hors ligne — ' : ''}
          {hasFailed
            ? (
              <button
                type="button"
                className="underline decoration-dotted underline-offset-2"
                onClick={() => setShowFailed((v) => !v)}
              >
                {failed.length} action(s) en échec — voir détail
              </button>
            )
            : pending > 0
              ? <>{pending} action(s) en attente de synchro</>
              : 'Connexion rétablie.'}
        </span>
        {hasFailed && <Badge tone="danger">{failed.length}</Badge>}
        {pending > 0 && !hasFailed && <Badge tone="warning">{pending}</Badge>}
        {(pending > 0 || hasFailed) && online && (
          <Button size="sm" variant="outline" onClick={flush} disabled={flushing}>
            <RefreshCw className={`size-4${flushing ? ' animate-spin' : ''}`} aria-hidden="true" />
            Synchroniser
          </Button>
        )}
      </div>
      {hasFailed && showFailed && (
        <ul className="flex flex-col gap-1 border-t border-border pt-2">
          {failed.map((op) => (
            <li key={op.client_op_id} className="flex items-center justify-between gap-2">
              <span className="flex-1 text-destructive">
                {op.op_type} — {op.serverError}
                {op.attempts > 1 ? ` (${op.attempts} tentatives)` : ''}
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => discard(op.client_op_id)}
              >
                Abandonner
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
