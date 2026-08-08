import { useCallback, useState } from 'react'
import { Paperclip, ShieldOff } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import recordsApi from '../../../api/recordsApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import { Badge, Button, Card, EmptyState, Skeleton, toast } from '../../../ui'
import { getApiError } from '../../../lib/apiError'

/* ============================================================================
   PACT72 — Pièces FOURNIES du dossier de dépôt (AOF115/AOF149).
   ----------------------------------------------------------------------------
   `PieceDossierAO.type_piece` distingue une pièce GÉNÉRÉE par la fabrique
   d'une pièce FOURNIE (par le partenaire ou l'acheteur — acte d'engagement au
   modèle imposé, caution bancaire scannée, attestations…). La colonne
   « Pièces du dossier » de `DossierPage` (`PieceRow`) affiche déjà les DEUX
   types, mais aucun écran n'offrait de marquer une pièce fournie « présente »
   ni d'y attacher son fichier — pas même un wrapper client (`aoApi.piecesDossierAo`,
   publié dans le même commit).

   Le fichier part en `records.Attachment` (upload générique, cible
   `ao.piecedossierao`) — JAMAIS un `FileField` local (garde ARC26) — puis son
   identifiant est posé sur la pièce (`attachment`) dans le MÊME geste que
   `presente=true` : une pièce « présente » sans fichier attaché serait un état
   qui ment.
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

function PieceFournieRow({ piece, occupe, onMarquerPresente }) {
  const [envoi, setEnvoi] = useState(false)
  const inputId = `ao-piece-fournie-fichier-${piece.id}`

  const surFichier = async (e) => {
    const fichier = e.target.files?.[0]
    e.target.value = ''
    if (!fichier) return
    setEnvoi(true)
    try {
      await onMarquerPresente(piece, fichier)
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5">
      <span className="min-w-0 flex-1 text-sm font-medium">{piece.libelle || piece.code}</span>
      {piece.obligatoire && <Badge tone="neutral">Obligatoire</Badge>}
      {piece.controlee === 'hors_controle' && (
        <Badge tone="warning">
          <ShieldOff className="size-3" aria-hidden="true" />
          Hors contrôle
        </Badge>
      )}
      {piece.presente ? (
        <Badge tone="success">Présente</Badge>
      ) : (
        <Badge tone="danger">Manquante</Badge>
      )}
      <label htmlFor={inputId} className="ml-auto">
        <Button asChild size="sm" variant="outline" disabled={occupe || envoi}>
          <span>
            <Paperclip className="size-3.5" aria-hidden="true" />
            {piece.presente ? 'Remplacer le fichier' : 'Marquer présente + joindre'}
          </span>
        </Button>
      </label>
      <input
        id={inputId}
        type="file"
        className="sr-only"
        aria-label={`Fichier — ${piece.libelle || piece.code}`}
        disabled={occupe || envoi}
        onChange={surFichier}
      />
    </li>
  )
}

export default function PiecesFournies({ dossierId }) {
  const [occupe, setOccupe] = useState(false)

  const { data: pieces, loading, error, refetch } = useResource(
    () => aoApi.piecesDossierAo.list({ dossier: dossierId, type_piece: 'fournie' }), dossierId,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les pièces fournies.',
      enabled: Boolean(dossierId),
    },
  )

  const marquerPresente = useCallback(async (piece, fichier) => {
    setOccupe(true)
    try {
      const upload = await recordsApi.uploadAttachment('ao.piecedossierao', piece.id, fichier)
      await aoApi.piecesDossierAo.update(piece.id, {
        attachment: upload?.data?.id,
        presente: true,
      })
      toast.success(`« ${piece.libelle || piece.code} » marquée présente.`)
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Pièce non enregistrée.'))
    } finally {
      setOccupe(false)
    }
  }, [refetch])

  if (!dossierId) return null
  if (loading) return <Skeleton className="h-32 w-full" />
  if (error) {
    return <EmptyState icon={Paperclip} tone="error" title="Pièces fournies indisponibles" description={error} />
  }
  if (pieces.length === 0) return null

  return (
    <Card className="flex flex-col gap-2 p-3">
      <div>
        <h2 className="font-display text-base font-semibold">Pièces fournies</h2>
        <p className="text-xs text-muted-foreground">
          Pièces remises par le partenaire ou l’acheteur — hors production de la fabrique.
        </p>
      </div>
      <ul className="flex flex-col gap-2">
        {pieces.map((p) => (
          <PieceFournieRow key={p.id} piece={p} occupe={occupe} onMarquerPresente={marquerPresente} />
        ))}
      </ul>
    </Card>
  )
}
