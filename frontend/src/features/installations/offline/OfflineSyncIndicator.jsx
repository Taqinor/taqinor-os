// N91/F21 — bandeau discret d'état de la synchro terrain hors-ligne.
//
// Affiché en tête du volet de capture d'une intervention : indique si on est
// hors ligne et combien d'actions attendent d'être synchronisées, avec un
// bouton « Synchroniser » pour forcer le flush. Reste silencieux (rien
// affiché) quand on est en ligne et que la file est vide — zéro bruit visuel
// dans le cas nominal.
import { CloudOff, RefreshCw } from 'lucide-react'
import { Button, Badge } from '../../../ui'
import { useFieldOutbox } from './useFieldOutbox'

export default function OfflineSyncIndicator() {
  const { online, pending, flushing, flush } = useFieldOutbox()
  if (online && pending === 0) return null
  return (
    <div className="mt-2 flex items-center gap-2 rounded border border-border bg-muted/40 p-2 text-[12px]">
      {!online && <CloudOff className="size-4 text-amber-600" aria-hidden="true" />}
      <span className="flex-1">
        {!online ? 'Hors ligne — ' : ''}
        {pending > 0
          ? <>{pending} action(s) en attente de synchro <Badge tone="warning" className="ml-1">{pending}</Badge></>
          : 'Connexion rétablie.'}
      </span>
      {pending > 0 && online && (
        <Button size="sm" variant="outline" onClick={flush} disabled={flushing}>
          <RefreshCw className={`size-4${flushing ? ' animate-spin' : ''}`} aria-hidden="true" />
          Synchroniser
        </Button>
      )}
    </div>
  )
}
