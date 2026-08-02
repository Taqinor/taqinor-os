import { useCallback } from 'react'
import { AlertTriangle, Ban, CheckCircle2, Download, Loader2, XCircle } from 'lucide-react'
import { Button, Progress, toast } from '../../../ui'
import { formatDateTime } from '../../../lib/format'
import useGenerationJob from './useGenerationJob'

/* ============================================================================
   AOF177 — Le bouton ZIP et le suivi VISIBLE de la génération.
   ----------------------------------------------------------------------------
   Toute la mécanique (lancement, sondage, reprise, annulation, 409 du verrou)
   vit dans `useGenerationJob` ; ce composant n'en est que la surface.

   **Jamais un bouton grisé sans explication** (règle d'AOF176, reprise ici à
   l'identique) : quand un contrôle bloquant est rouge, le motif est écrit SUR
   le bouton. `bloque`/`motifBlocage` viennent du panneau de contrôles — ce
   composant ne re-juge rien.

   **L'interface ne se bloque jamais** pendant la génération : l'avancement
   s'affiche pièce par pièce, chaque pièce en échec est nommée avec son motif,
   et le reste de l'écran reste utilisable. Le succès émet un toast portant un
   LIEN vers le résultat.
   ========================================================================== */

function VerrouMessage({ verrou }) {
  if (!verrou) return null
  const depuis = verrou.depuis ? formatDateTime(verrou.depuis) : null
  return (
    <p className="flex items-start gap-1.5 text-xs text-warning" role="status">
      <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      <span>
        {verrou.detail || 'Une opération est déjà en cours sur ce dossier.'}
        {verrou.porteur ? ` Porteur : ${verrou.porteur}.` : ''}
        {depuis ? ` Depuis ${depuis}.` : ''}
      </span>
    </p>
  )
}

function PieceProgression({ piece }) {
  const echec = piece.statut === 'echec' || piece.statut === 'failed'
  const fait = piece.statut === 'done' || piece.statut === 'succes' || piece.statut === 'termine'
  const Icone = echec ? XCircle : (fait ? CheckCircle2 : Loader2)
  return (
    <li className="flex items-start gap-1.5 text-xs">
      <Icone
        className={`mt-0.5 size-3.5 shrink-0 ${echec ? 'text-destructive' : fait ? 'text-success' : 'animate-spin text-info'}`}
        aria-hidden="true"
      />
      <span className="min-w-0">
        <span className={echec ? 'text-destructive' : ''}>{piece.libelle || piece.code}</span>
        {echec && piece.message_erreur ? ` — ${piece.message_erreur}` : ''}
      </span>
    </li>
  )
}

export default function ZipButton({
  dossierId,
  bloque = false,
  motifBlocage = null,
  onAnnulerServeur,
  intervalMs,
}) {
  const onSucces = useCallback((j) => {
    const url = j?.resultat_url ?? j?.url
    toast.success('Pack de dépôt prêt.', url
      ? { action: { label: 'Ouvrir le ZIP', onClick: () => globalThis.open?.(url, '_blank', 'noopener') } }
      : undefined)
  }, [])
  const onEchec = useCallback((j) => {
    toast.error(j?.message_erreur || 'La génération du pack a échoué — le dossier reste en constitution.')
  }, [])

  const {
    statut, pieces, progression, resultatUrl, erreur, verrou, enCours, lancer, annuler,
  } = useGenerationJob(dossierId, { onSucces, onEchec, onAnnulerServeur, intervalMs })

  if (bloque) {
    return (
      <Button className="self-start" disabled title={motifBlocage || undefined}>
        <Ban aria-hidden="true" />
        {motifBlocage ? `ZIP bloqué — ${motifBlocage}` : 'ZIP bloqué — contrôle bloquant'}
      </Button>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={lancer} disabled={enCours} loading={enCours}>
          {enCours ? 'Génération du pack…' : 'Constituer le ZIP de dépôt'}
        </Button>
        {enCours && (
          <Button variant="outline" size="sm" onClick={annuler}>
            Annuler le suivi
          </Button>
        )}
        {statut === 'succes' && resultatUrl && (
          <Button variant="outline" size="sm" asChild>
            <a href={resultatUrl} download>
              <Download aria-hidden="true" />
              Télécharger le ZIP
            </a>
          </Button>
        )}
      </div>

      <VerrouMessage verrou={verrou} />

      {enCours && (
        <div className="flex flex-col gap-1">
          <Progress
            value={progression}
            aria-label="Avancement de la génération du pack"
            indeterminate={!progression}
          />
          <p className="text-xs text-muted-foreground" aria-live="polite">
            {progression ? `${Math.round(progression)} %` : 'Démarrage…'}
            {' — vous pouvez continuer à travailler.'}
          </p>
        </div>
      )}

      {pieces.length > 0 && (
        <ul className="flex flex-col gap-1">
          {pieces.map((p) => <PieceProgression key={p.code ?? p.id} piece={p} />)}
        </ul>
      )}

      {statut === 'echec' && (
        <p className="flex items-start gap-1.5 text-xs text-destructive" role="alert">
          <XCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          La génération a échoué — les autres pièces restent intactes.
        </p>
      )}

      {erreur && !verrou && (
        <p className="text-xs text-destructive">{erreur}</p>
      )}
    </div>
  )
}
