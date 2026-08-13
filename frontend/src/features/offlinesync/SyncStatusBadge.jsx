// NTMOB3 — Bandeau de statut de synchronisation GLOBAL (en-tête).
//
// Jusqu'ici l'état de la file hors-ligne n'était visible QUE dans le volet de
// capture d'une intervention (`OfflineSyncIndicator`, N91/F21) : un technicien
// qui posait des actions hors-ligne puis quittait l'écran n'avait plus AUCUN
// repère sur ce qui restait à synchroniser. Ce badge remonte l'information
// dans l'en-tête, à côté de la cloche de notifications, sur TOUT écran
// authentifié.
//
// Trois états, exactement ceux du cahier des charges :
//   • « {n} opération(s) en attente » — file non vide (JSON + photos, même
//     file, même badge — décision EZ8, jamais un 2ᵉ indicateur) ;
//   • « Erreur de synchro » — au moins une op REFUSÉE par le serveur (elle ne
//     disparaît jamais toute seule, VX119) ;
//   • « Synchronisé » — hors ligne mais rien en attente.
// EN LIGNE + file vide + aucune erreur ⇒ le badge ne rend RIEN : zéro bruit
// visuel dans le cas nominal, et surtout aucune 10ᵉ cible permanente dans
// `.header-right` (VX181 — l'en-tête déborde déjà à 320-375 px).
//
// Le clic ouvre le JOURNAL des opérations en attente (type d'op, horodatage de
// mise en file, message d'erreur serveur + abandon explicite) et offre
// « Synchroniser » pour forcer le vidage. L'écran de résolution de conflit
// (`SyncConflictsPanel`, NTMOB2) n'existe pas encore — il se branchera ici
// quand le moteur serveur (NTMOB1, `OfflineOperation`) sera livré ; ce module
// ne préjuge de rien à sa place.
//
// Source de vérité : l'outbox terrain DÉJÀ en place
// (`features/installations/offline`). Ce composant ne crée NI file, NI
// stockage, NI endpoint — il ne fait que rendre visible l'existant.
import { useCallback, useState } from 'react'
import { CloudOff, AlertTriangle, RefreshCw } from 'lucide-react'
import { Popover, PopoverTrigger, PopoverContent } from '../../ui/Popover'
import Button from '../../ui/Button'
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'
import { useFieldOutbox } from '../installations/offline/useFieldOutbox'
import { fieldOutbox, binaryOutbox } from '../installations/offline/fieldOutbox'

// Cadences de rafraîchissement du compteur. Volontairement modestes : après le
// premier chargement, l'outbox sert ses ops depuis son cache MÉMOIRE (voir
// `Outbox._ensureLoaded`), donc un tick coûte une lecture de tableau — pas un
// accès disque, encore moins un appel réseau. Le hook est sensible à la
// visibilité de l'onglet (VX56) : onglet caché ⇒ aucun tick.
export const POLL_ACTIF_MS = 4000
export const POLL_REPOS_MS = 20000

// Libellé humain d'une op en file. Les `op_type` sont des clés techniques
// (`intervention.checkin`…) : on affiche la clé telle quelle plutôt que
// d'inventer une table de traduction qui divergerait de FIELD_OPS.
function ligneJournal(op) {
  return {
    id: op.client_op_id,
    type: op.op_type,
    // Seule la file BINAIRE horodate la mise en file (`queuedAt`) ; la file
    // JSON ne le fait pas — on n'affiche donc l'heure que quand elle existe,
    // jamais une date inventée.
    heure: op.queuedAt ? new Date(op.queuedAt).toLocaleTimeString('fr-FR', {
      hour: '2-digit', minute: '2-digit',
    }) : null,
    erreur: op.serverError || null,
    tentatives: op.attempts || 0,
  }
}

export default function SyncStatusBadge() {
  const {
    online, pending, pendingPhotos, failed, flushing, flush, discard, refreshCount,
  } = useFieldOutbox()
  const [journal, setJournal] = useState([])
  const [open, setOpen] = useState(false)

  const enAttente = pending + pendingPhotos
  const hasFailed = failed.length > 0

  // Recharge compteur ET journal dans le même tick : une seule lecture de la
  // file par cadence, jamais deux sondes concurrentes sur le même stockage.
  const tick = useCallback(() => {
    refreshCount()
    Promise.all([fieldOutbox.pending(), binaryOutbox.pending()])
      .then(([json, bin]) => setJournal([...json, ...bin].map(ligneJournal)))
      .catch(() => { /* défensif : le badge ne casse jamais l'en-tête */ })
  }, [refreshCount])

  useVisibilityAwarePolling([{
    fn: tick,
    intervalMs: (enAttente > 0 || hasFailed || !online) ? POLL_ACTIF_MS : POLL_REPOS_MS,
  }])

  // Cas nominal (en ligne, file vide, aucune erreur) : rien du tout.
  if (online && enAttente === 0 && !hasFailed) return null

  const libelle = hasFailed
    ? 'Erreur de synchro'
    : enAttente > 0
      ? `${enAttente} opération${enAttente > 1 ? 's' : ''} en attente`
      : 'Synchronisé'
  const Icone = hasFailed ? AlertTriangle : online ? RefreshCw : CloudOff
  const tonIcone = hasFailed
    ? 'text-destructive'
    : online ? 'text-muted-foreground' : 'text-amber-600'

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="nb-btn"
          aria-label={`Synchronisation hors-ligne — ${libelle}`}
          title={libelle}
          data-testid="sync-status-badge"
        >
          <Icone size={19} aria-hidden="true" className={tonIcone} />
          {(enAttente > 0 || hasFailed) && (
            <span className="nb-badge">{hasFailed ? failed.length : enAttente}</span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="mb-1 text-sm font-semibold">Synchronisation hors-ligne</div>
        <p className="mb-2 text-xs text-muted-foreground" data-testid="sync-status-libelle">
          {!online && 'Hors ligne — '}{libelle}
        </p>
        {journal.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Aucune opération en attente sur cet appareil.
          </p>
        ) : (
          <ul className="flex max-h-80 flex-col gap-1.5 overflow-y-auto">
            {journal.map((l) => (
              <li key={l.id}
                className="flex flex-col gap-1 rounded-md border border-border px-2.5 py-2">
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="font-medium">{l.type}</span>
                  {l.heure && <span className="ml-auto text-muted-foreground">{l.heure}</span>}
                </div>
                {l.erreur && (
                  <p className="text-[11px] text-destructive">
                    {l.erreur}
                    {l.tentatives > 1 ? ` (${l.tentatives} tentatives)` : ''}
                  </p>
                )}
                {l.erreur && (
                  <Button size="sm" variant="ghost" className="self-start"
                    onClick={() => discard(l.id).then(tick)}>
                    Abandonner
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
        {online && (enAttente > 0 || hasFailed) && (
          <Button size="sm" variant="outline" className="mt-2 w-full"
            disabled={flushing} onClick={() => flush().then(tick)}>
            <RefreshCw className={`size-4${flushing ? ' animate-spin' : ''}`} aria-hidden="true" />
            Synchroniser
          </Button>
        )}
      </PopoverContent>
    </Popover>
  )
}
