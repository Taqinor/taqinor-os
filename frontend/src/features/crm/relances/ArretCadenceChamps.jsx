import { Button, Input } from '../../../ui'

// ENF19 — les contrôles « Arrêter la cadence » (bouton, puis motif OBLIGATOIRE +
// Annuler/Confirmer), partagés par la file du Cockpit (RelancesDuJourWidget) et la
// page Suivi (RelancesSuiviPage) : avant, deux copies littérales. Présentation
// pure : l'état (ouvert, motif, busy) et l'appel serveur restent chez l'appelant.
export default function ArretCadenceChamps({
  ouvert, motif, busy, onOuvrir, onFermer, onMotif, onConfirmer,
}) {
  if (!ouvert) {
    return (
      <Button
        type="button" size="sm" variant="outline" disabled={busy}
        onClick={onOuvrir}
      >
        Arrêter la cadence
      </Button>
    )
  }
  return (
    <>
      <Input
        placeholder="Motif d'arrêt (obligatoire)" value={motif}
        onChange={(e) => onMotif(e.target.value)}
        data-testid="cad50-arreter-motif"
      />
      <Button
        type="button" size="sm" variant="outline" disabled={busy}
        onClick={onFermer}
      >
        Annuler
      </Button>
      <Button type="button" size="sm" disabled={busy || !motif.trim()} onClick={onConfirmer}>
        Confirmer
      </Button>
    </>
  )
}
