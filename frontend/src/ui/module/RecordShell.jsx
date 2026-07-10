import { DetailShell } from './DetailShell'
import { Button } from '../Button'
import { useOptimisticSave } from '../../hooks/useOptimisticSave'

/* ============================================================================
   ARC46 — Coquille d'enregistrement (le pendant détail/formulaire de ListShell).
   ----------------------------------------------------------------------------
   Là où `ListShell` (UX1) coiffe les LISTES, `RecordShell` coiffe une FICHE
   d'enregistrement. AUCUN markup dupliqué : l'en-tête (retour + titre + statut
   + actions), les onglets et le panneau latéral sont rendus par COMPOSITION de
   `DetailShell` (toutes ses props passent inchangées). RecordShell n'apporte
   que : (1) l'alias `chatter` du slot `activity` (futur consommateur nommé :
   VX23) et (2) la BARRE D'ENREGISTREMENT optionnelle branchée sur
   `useOptimisticSave` (édition optimiste + rollback), montée sous le corps via
   le slot `footer` de DetailShell. Zéro refonte visuelle (VX possède le style).

   ── Barre d'enregistrement (opt-in) ──
   Fournir `record` (l'enregistrement en cours d'édition) ET `onSave(record)`
   (l'appel réseau réel, qui REJETTE en cas d'échec) active la barre. Sans
   `onSave`, AUCUNE barre n'est rendue — la coquille se comporte alors
   exactement comme `DetailShell` (fiche en lecture). `dirty` (par défaut : la
   présence d'un `record`) pilote l'état actif du bouton ; le libellé d'état FR
   ('Enregistrement…' / 'Enregistré') vient de `useOptimisticSave`.

   tabs : [{ value, label, content, count? }] — contrat DetailShell inchangé.
   ========================================================================== */

export function RecordShell({
  activity,
  chatter,          // alias de `activity` (slot chatter) — futur consommateur VX23
  // ── Save-bar (opt-in) ──
  record,           // valeur serveur suivie (active la barre avec `onSave`)
  onSave,           // (record) => Promise — REJETTE en cas d'échec (rollback auto)
  dirty,            // bool optionnel : force l'état « modifié » de la barre
  saveLabel = 'Enregistrer',
  onSaveError,
  ...detailProps    // title/subtitle/status/statusPill/actions/backTo/backLabel/
                    // tabs/defaultTab/className/children → DetailShell inchangés
}) {
  const hasSaveBar = typeof onSave === 'function'

  // Édition optimiste + rollback. `useOptimisticSave` suit `record` au repos.
  const { statusLabel, isSaving, save } = useOptimisticSave(record, {
    onError: onSaveError,
  })

  // « Modifié » : par défaut vrai si un record est fourni ; sinon piloté par
  // `dirty`. Le bouton reste bloqué pendant un enregistrement en cours.
  const isDirty = dirty ?? record != null

  // Seul markup PROPRE à RecordShell : la barre d'enregistrement.
  const saveBar = hasSaveBar ? (
    <div
      className="flex flex-wrap items-center justify-end gap-3 rounded-lg border border-border bg-card px-4 py-3"
      data-record-savebar
    >
      {statusLabel && (
        <span
          className="text-sm text-muted-foreground"
          aria-live="polite"
          data-record-savebar-status
        >
          {statusLabel}
        </span>
      )}
      <Button
        type="button"
        disabled={isSaving || !isDirty}
        aria-busy={isSaving}
        onClick={() => save(record, onSave)}
      >
        {isSaving ? 'Enregistrement…' : saveLabel}
      </Button>
    </div>
  ) : null

  return (
    <DetailShell
      {...detailProps}
      activity={chatter ?? activity}
      footer={saveBar}
    />
  )
}

export default RecordShell
