import { AlertTriangle, RefreshCw, ShieldOff } from 'lucide-react'
import { Badge, Button } from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import { StatutPiece } from '../statusAo'
import { estHorsControle } from './PieceRow.utils'

/* ============================================================================
   AOF174 — Une pièce du dossier de soumission (ligne de la colonne gauche).
   ----------------------------------------------------------------------------
   Hooks e2e : `data-ao-piece` (la pièce) et `data-ao-etat` (sa pastille) —
   les DEUX viennent du contrat figé `../E2E_HOOKS.md` (AOF8), aucun nom
   inventé ici.

   Pastille d'état : `StatutPiece` de `../statusAo` (AOF10) — les 7 états
   (à produire / généré / à jour / PÉRIMÉ / fourni / signé / hors contrôle)
   et leurs tons y sont définis UNE fois ; ce fichier ne pose ni couleur ni
   libellé d'état.

   PÉRIMÉ n'est jamais une pastille muette : la ligne déplie un bandeau
   « régénérer » qui NOMME le motif renvoyé par le serveur (« le calepinage
   du bâtiment C est passé de 264 à 314 »). Une pièce FOURNIE hors fabrique
   (AOF149) affiche « hors contrôle » + son motif — jamais du vert présumé.

   Aucun chiffre n'est dérivé ici (AOF94) : tout est lu tel quel du payload.
   ========================================================================== */

export default function PieceRow({
  piece,
  selected = false,
  onSelect,
  onRegenerer,
  regenerating = false,
  verrouille = false,
}) {
  const perime = piece.statut === 'perime'
  const horsControle = estHorsControle(piece)
  const libelle = piece.libelle || piece.code || `Pièce #${piece.id}`

  return (
    <li
      data-ao-piece={piece.code || String(piece.id)}
      className={[
        'rounded-lg border p-3 transition-colors',
        selected ? 'border-primary bg-primary/5' : 'border-border',
        perime ? 'border-l-4 border-l-destructive' : '',
      ].filter(Boolean).join(' ')}
    >
      <button
        type="button"
        onClick={() => onSelect?.(piece)}
        aria-pressed={selected}
        className="flex w-full items-start justify-between gap-2 text-left"
      >
        <span className="flex flex-col gap-0.5">
          <span className="text-sm font-medium">{libelle}</span>
          {piece.date_generation && (
            <span className="text-xs text-muted-foreground">
              Généré le {formatDateTime(piece.date_generation)}
            </span>
          )}
        </span>
        <StatutPiece status={piece.statut} data-ao-etat={piece.statut} />
      </button>

      {horsControle && (
        <p className="mt-2 flex items-start gap-1.5 rounded-md bg-destructive/5 p-2 text-xs text-destructive">
          <ShieldOff className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          <span>
            <span className="font-medium">Hors contrôle</span>
            {piece.motif_hors_controle ? ` — ${piece.motif_hors_controle}` : ''}
          </span>
        </p>
      )}

      {perime && (
        <div className="mt-2 flex flex-col gap-2 rounded-md border border-destructive/40 bg-destructive/5 p-2">
          <p className="flex items-start gap-1.5 text-xs text-destructive">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            <span>
              <span className="font-medium">Périmé — à régénérer.</span>
              {piece.motif_peremption ? ` ${piece.motif_peremption}` : ''}
            </span>
          </p>
          {/* WIR207 — le libellé mentait : cliquer ici régénère TOUT LE PACK
              (le serveur ignore tout argument de pièce), jamais cette seule
              pièce. Le libellé dit maintenant ce que le clic fait vraiment. */}
          <Button
            size="sm"
            variant="outline"
            className="self-start"
            disabled={regenerating || verrouille}
            onClick={() => onRegenerer?.()}
          >
            <RefreshCw className={`size-3.5 ${regenerating ? 'animate-spin' : ''}`} aria-hidden="true" />
            {regenerating ? 'Régénération…' : 'Régénérer le dossier complet'}
          </Button>
        </div>
      )}

      {piece.obligatoire && !perime && !horsControle && (
        <Badge tone="neutral" className="mt-2">Obligatoire</Badge>
      )}
    </li>
  )
}
