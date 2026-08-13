// NTMOB3 — Bandeau/badge de statut de synchronisation GLOBAL dans l'en-tête.
//
// L'outbox de capture terrain (N91/F21 + EZ8 pour les photos) existe déjà et
// affiche son compteur DANS le volet de capture. Hors de ce volet — et c'est
// le cas dès qu'on quitte l'écran d'intervention — l'utilisateur n'avait plus
// AUCUN moyen de savoir que des actions attendent encore la synchro. Ce badge
// remonte cet état, sur toutes les pages de l'app shell.
//
// RÈGLES RESPECTÉES :
//   * UN SEUL outbox, UN SEUL compteur (décision VX105) : ce composant ne crée
//     ni file ni compteur, il LIT la file partagée via `useFieldOutbox`
//     (photos incluses, jamais un 2ᵉ indicateur séparé pour elles) ;
//   * `Outbox.flush()` porte déjà une garde anti-réentrance, donc monter le
//     hook ici en plus du volet de capture ne double JAMAIS un envoi ;
//   * aucune op ne disparaît en silence : les ops en échec serveur sont
//     listées avec leur message et ne s'abandonnent qu'explicitement (VX119),
//     l'abandon reste dans le volet de capture — ici c'est un JOURNAL.
//
// Les états sont ceux de la spec : « {n} opérations en attente » /
// « Synchronisé » / « Erreur de synchro ». Ils se rafraîchissent sur les
// événements `online`/`offline` du navigateur et après chaque flush (le hook
// partagé s'en charge).
import { useState } from 'react'
import { CloudOff, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react'
import { useFieldOutbox } from '../../features/installations/offline/useFieldOutbox'
import { Popover, PopoverTrigger, PopoverContent } from '../../ui/Popover'

/** État affiché, dérivé PUREMENT des compteurs (testable sans React). */
export function syncState({ online, pending, pendingPhotos, failedCount }) {
  const enAttente = (pending || 0) + (pendingPhotos || 0)
  if (failedCount > 0) {
    return {
      key: 'erreur',
      label: 'Erreur de synchro',
      icon: AlertTriangle,
      tone: 'text-destructive',
      count: failedCount,
    }
  }
  if (enAttente > 0) {
    return {
      key: 'attente',
      label: `${enAttente} opération${enAttente > 1 ? 's' : ''} en attente`,
      icon: online ? RefreshCw : CloudOff,
      tone: 'text-warning',
      count: enAttente,
    }
  }
  return {
    key: 'ok',
    label: 'Synchronisé',
    icon: CheckCircle2,
    tone: 'text-success',
    count: 0,
  }
}

export default function SyncStatusBadge() {
  const [open, setOpen] = useState(false)
  const {
    online, pending, pendingPhotos, failed, flushing, flush,
  } = useFieldOutbox()

  const etat = syncState({
    online, pending, pendingPhotos, failedCount: failed.length,
  })

  // Rien en attente ET aucune erreur ET réseau présent : on n'encombre pas
  // l'en-tête d'un badge permanent. Dès qu'il y a quelque chose à dire (une
  // op en file, une erreur, ou la perte du réseau), le badge apparaît.
  if (etat.key === 'ok' && online) return null

  const Icon = etat.icon
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="nb-btn"
          aria-label={etat.label}
          title={etat.label}
          data-testid="sync-status-badge"
          data-sync-state={etat.key}
        >
          <Icon size={19} aria-hidden="true" className={etat.tone} />
          {etat.count > 0 && <span className="nb-badge">{etat.count}</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72">
        <div className="mb-2 text-sm font-semibold">Synchronisation</div>
        <p className="mb-2 text-xs text-muted-foreground">
          {online
            ? etat.label
            : `Hors ligne — ${etat.label.toLowerCase()}`}
        </p>
        {failed.length > 0 && (
          <div className="mb-2 flex max-h-52 flex-col gap-1.5 overflow-y-auto">
            {failed.map((op) => (
              <div
                key={op.client_op_id}
                className="rounded-md border border-border px-2.5 py-2"
              >
                <div className="text-xs font-medium">{op.op_type}</div>
                <p className="text-[11px] text-destructive">
                  {op.serverError}
                </p>
              </div>
            ))}
            <p className="text-[11px] text-muted-foreground">
              Ces opérations restent en file : reprenez-les depuis l&apos;écran
              de capture terrain pour les renvoyer ou les abandonner.
            </p>
          </div>
        )}
        <button
          type="button"
          className="w-full rounded-md border border-border px-2.5 py-1.5 text-xs font-medium disabled:opacity-60"
          onClick={() => flush()}
          disabled={flushing || !online}
          data-testid="sync-status-flush"
        >
          {flushing ? 'Synchronisation…' : 'Synchroniser maintenant'}
        </button>
      </PopoverContent>
    </Popover>
  )
}
