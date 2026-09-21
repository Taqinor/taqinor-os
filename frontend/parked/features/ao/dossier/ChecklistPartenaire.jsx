import { useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertTriangle, ClipboardCheck, UserRound } from 'lucide-react'
import aoApi from '../../../api/aoApi'
import useResource from '../../../hooks/useResource'
import { unwrapList } from '../../../api/resource'
import {
  Badge, Button, Card, Checkbox, EmptyState, Skeleton, Textarea, toast,
} from '../../../ui'
import { getApiError } from '../../../lib/apiError'

/* ============================================================================
   PACT71 — Checklist partenaire du dossier de dépôt (AOF136).
   ----------------------------------------------------------------------------
   `LigneChecklistPartenaire` couvre les 7 blocs d'une remise réelle (CPS,
   acte d'engagement, bordereau, lettre de soumission, mémoire, dossier
   administratif, vérifications avant dépôt) : case, responsable, commentaire.
   Un point OBLIGATOIRE encore ouvert BLOQUE la transition « prêt à déposer »
   (`DossierAO.raisons_de_non_depot`) — mais `DossierPage`/`PieceRow`
   n'affichent que les pièces et les états, jamais cette checklist. La porte
   de blocage était donc invisible, et on la contournait par l'API en croyant
   bien faire — exactement le motif qui a justifié le panneau « Contrôles
   avant dépôt » (AOF176) pour la cohérence croisée.

   **Responsable et date de pointage sont TRACÉS CÔTÉ SERVEUR** (l'action
   `pointer`, jamais un PATCH nu sur `faite`) : l'écran affiche `responsable_nom`
   tel quel, il ne l'invente jamais.

   **La cause du blocage est le texte AUTHENTIQUE du serveur**
   (`dossiers-ao/<id>/completude/` → `raisons_de_non_depot`), jamais reconstruit
   ici : un point obligatoire ouvert de la checklist y apparaît nommément,
   avec le libellé exact que le serveur écrirait pour refuser le dépôt.
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

function LignePoint({ ligne, occupe, onPointer }) {
  const [commentaire, setCommentaire] = useState(ligne.commentaire || '')
  const ouverte = ligne.obligatoire && !ligne.faite

  const commitCommentaire = () => {
    if (commentaire === (ligne.commentaire || '')) return
    onPointer(ligne, ligne.faite, commentaire)
  }

  return (
    <li
      className={`flex flex-col gap-1.5 rounded-lg border p-2.5 ${
        ouverte ? 'border-destructive/50 bg-destructive/5' : 'border-border'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Checkbox
          checked={Boolean(ligne.faite)}
          disabled={occupe}
          aria-label={ligne.libelle}
          onCheckedChange={(val) => onPointer(ligne, val === true, commentaire)}
        />
        <span className={`text-sm ${ouverte ? 'font-medium text-destructive' : ''}`}>{ligne.libelle}</span>
        {ligne.obligatoire && <Badge tone={ligne.faite ? 'success' : 'danger'}>Obligatoire</Badge>}
        <span className="ml-auto flex items-center gap-1 text-xs text-muted-foreground">
          <UserRound className="size-3" aria-hidden="true" />
          {ligne.responsable_nom || 'Responsable non désigné'}
        </span>
      </div>
      <Textarea
        value={commentaire}
        onChange={(e) => setCommentaire(e.target.value)}
        onBlur={commitCommentaire}
        rows={1}
        placeholder="Commentaire…"
        aria-label={`Commentaire — ${ligne.libelle}`}
        className="text-xs"
      />
    </li>
  )
}

function BlocChecklist({ bloc, lignes, occupe, onPointer }) {
  return (
    <div>
      <h3 className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">{bloc}</h3>
      <ul className="flex flex-col gap-2">
        {lignes.map((ligne) => (
          <LignePoint key={ligne.id} ligne={ligne} occupe={occupe} onPointer={onPointer} />
        ))}
      </ul>
    </div>
  )
}

export default function ChecklistPartenaire({ dossierId } = {}) {
  const routeParams = useParams()
  const id = dossierId ?? routeParams.id
  const [occupe, setOccupe] = useState(false)
  const [initialisation, setInitialisation] = useState(false)

  const { data: lignes, loading, error, refetch } = useResource(
    () => aoApi.checklistPartenaire.list({ dossier: id }), id,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger la checklist partenaire.',
      enabled: Boolean(id),
    },
  )

  const { data: completude, refetch: refetchCompletude } = useResource(
    () => aoApi.dossiers.completude(id), id,
    {
      select: (res) => res?.data ?? null,
      errorMessage: () => '',
      enabled: Boolean(id),
    },
  )

  const parBloc = useMemo(() => {
    const groupes = new Map()
    for (const ligne of lignes) {
      const cle = ligne.bloc_display || ligne.bloc
      if (!groupes.has(cle)) groupes.set(cle, [])
      groupes.get(cle).push(ligne)
    }
    return [...groupes.entries()]
  }, [lignes])

  const pointer = useCallback(async (ligne, faite, commentaire) => {
    setOccupe(true)
    try {
      await aoApi.checklistPartenaire.pointer(ligne.id, { faite, commentaire })
      refetch()
      refetchCompletude()
    } catch (e) {
      toast.error(errMsg(e, 'Point non enregistré.'))
    } finally {
      setOccupe(false)
    }
  }, [refetch, refetchCompletude])

  const initialiser = useCallback(async () => {
    setInitialisation(true)
    try {
      const res = await aoApi.dossiers.initialiserChecklist(id)
      const crees = res?.data?.crees ?? 0
      toast.success(crees > 0 ? `${crees} point(s) de checklist créés.` : 'Checklist déjà initialisée.')
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Initialisation impossible.'))
    } finally {
      setInitialisation(false)
    }
  }, [id, refetch])

  const raisonsChecklist = useMemo(
    () => (completude?.raisons_de_non_depot || []).filter((r) => r.includes('checklist partenaire')),
    [completude],
  )

  if (!id) {
    return (
      <EmptyState
        icon={ClipboardCheck}
        title="Checklist indisponible"
        description="Cette checklist se rattache à un dossier de dépôt."
      />
    )
  }
  if (loading) {
    return <div className="flex flex-col gap-3"><Skeleton className="h-8 w-64" /><Skeleton className="h-56 w-full" /></div>
  }
  if (error) {
    return <EmptyState icon={ClipboardCheck} tone="error" title="Checklist indisponible" description={error} />
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-base font-semibold">Checklist partenaire</h2>
          <p className="text-xs text-muted-foreground">
            Les sept blocs d’une remise réelle — un point obligatoire ouvert bloque le dépôt.
          </p>
        </div>
      </div>

      {raisonsChecklist.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/60 bg-destructive/5 p-2.5" role="alert">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
          <ul className="flex flex-col gap-0.5">
            {raisonsChecklist.map((r) => <li key={r} className="text-xs font-medium text-destructive">{r}</li>)}
          </ul>
        </div>
      )}

      {lignes.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="Checklist non initialisée"
          description="Aucun point de checklist n’a encore été créé pour ce dossier."
          action={(
            <Button size="sm" onClick={initialiser} disabled={initialisation}>
              {initialisation ? 'Initialisation…' : 'Initialiser la checklist'}
            </Button>
          )}
        />
      ) : (
        <div className="flex flex-col gap-4">
          {parBloc.map(([bloc, lignesBloc]) => (
            <BlocChecklist key={bloc} bloc={bloc} lignes={lignesBloc} occupe={occupe} onPointer={pointer} />
          ))}
        </div>
      )}
    </Card>
  )
}
