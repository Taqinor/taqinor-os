import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FileWarning, Files } from 'lucide-react'
import aoApi from '../../api/aoApi'
import recordsApi from '../../api/recordsApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import {
  Badge, Button, Card, CardHeader, CardTitle, CardContent, Input, Label, Select,
  SelectTrigger, SelectValue, SelectContent, SelectItem, EmptyState, Skeleton, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { formatDate } from '../../lib/format'
import { getApiError } from '../../lib/apiError'

/* ============================================================================
   PACT74 — Pièces du dossier de CONSULTATION reçu de l'acheteur (AOF21).
   ----------------------------------------------------------------------------
   `PieceConsultation` (CPS, règlement, plans d'architecte, cadre de bordereau
   vierge, additifs/erratums) n'était exposée nulle part : un additif reçu
   après téléchargement ne marquait rien « à revérifier », et l'écran des
   exigences CPS (déjà câblé, `cps/ExigencesPage.jsx`) référence « la page du
   CPS » alors que le CPS lui-même n'est jamais stocké.

   **Un ADDITIF n'est jamais créé à la main comme une pièce ordinaire** : il
   part TOUJOURS de l'action serveur `additif` sur la pièce qu'il modifie
   (`services.enregistrer_additif`) — c'est ce qui garantit que `modifie` est
   toujours renseigné et que les exigences dérivées sont marquées « à
   revérifier » dans le MÊME geste. Le formulaire de création ci-dessous
   exclut donc le type « Additif / erratum » de ses choix.

   `empreinte_sha256` est calculée côté serveur (reconnaît un même document
   reçu deux fois) — jamais affichée comme un identifiant à saisir.
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

const TYPES_PIECE = [
  ['cps', 'CPS (cahier des prescriptions spéciales)'],
  ['reglement', 'Règlement de consultation'],
  ['plan_architecte', "Plan d'architecte"],
  ['modele_acte', "Modèle d'acte d'engagement"],
  ['bordereau_vierge', 'Bordereau des prix vierge'],
  ['autre', 'Autre pièce du DCE'],
]

function Champ({ id, label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

function CreationForm({ affaireId, onCree }) {
  const [form, setForm] = useState({ type_piece: 'cps', reference: '', version: '', date_reception: '' })
  const [fichier, setFichier] = useState(null)
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    setEnvoi(true)
    try {
      const payload = { appel_offre: affaireId, type_piece: form.type_piece }
      if (form.reference.trim()) payload.reference = form.reference.trim()
      if (form.version.trim()) payload.version = form.version.trim()
      if (form.date_reception) payload.date_reception = form.date_reception
      const cree = await aoApi.piecesConsultation.create(payload)
      const id = cree?.data?.id
      if (fichier && id) {
        const upload = await recordsApi.uploadAttachment('ao.piececonsultation', id, fichier)
        await aoApi.piecesConsultation.update(id, { attachment: upload?.data?.id })
      }
      toast.success('Pièce du DCE enregistrée.')
      setForm({ type_piece: 'cps', reference: '', version: '', date_reception: '' })
      setFichier(null)
      onCree()
    } catch (e2) {
      toast.error(errMsg(e2, 'Pièce non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-3">
      <Champ id="ao-pc-type" label="Type de pièce">
        <Select value={form.type_piece} onValueChange={(v) => setForm((p) => ({ ...p, type_piece: v }))}>
          <SelectTrigger id="ao-pc-type"><SelectValue /></SelectTrigger>
          <SelectContent>
            {TYPES_PIECE.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-pc-reference" label="Référence">
        <Input id="ao-pc-reference" value={form.reference} onChange={set('reference')} />
      </Champ>
      <Champ id="ao-pc-version" label="Version reçue">
        <Input id="ao-pc-version" value={form.version} onChange={set('version')} />
      </Champ>
      <Champ id="ao-pc-date" label="Date de réception">
        <Input id="ao-pc-date" type="date" value={form.date_reception} onChange={set('date_reception')} />
      </Champ>
      <Champ id="ao-pc-fichier" label="Fichier (facultatif)">
        <input
          id="ao-pc-fichier" type="file" className="text-sm"
          onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
        />
      </Champ>
      <div className="flex items-end">
        <Button type="submit" disabled={envoi}>{envoi ? 'Enregistrement…' : 'Enregistrer la pièce'}</Button>
      </div>
    </form>
  )
}

function AdditifDialog({ piece, onClose, onConfirmer }) {
  const [reference, setReference] = useState('')
  const [version, setVersion] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setEnvoi(true)
    try {
      await onConfirmer(piece, { reference, version })
      onClose()
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Signaler un additif à « {piece.reference || piece.type_piece_display} »</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <p className="rounded-md border border-warning/40 bg-warning/5 p-2.5 text-xs text-warning">
            L’additif marquera automatiquement « à revérifier » les exigences CPS qui dérivent de cette pièce.
          </p>
          <Champ id="ao-additif-reference" label="Référence de l'additif">
            <Input id="ao-additif-reference" value={reference} onChange={(e) => setReference(e.target.value)} />
          </Champ>
          <Champ id="ao-additif-version" label="Version">
            <Input id="ao-additif-version" value={version} onChange={(e) => setVersion(e.target.value)} />
          </Champ>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={envoi}>{envoi ? 'Enregistrement…' : "Enregistrer l'additif"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function LignePiece({ piece, pieceModifiee, onSignalerAdditif }) {
  return (
    <li className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5 text-sm">
      <Badge tone={piece.est_additif ? 'warning' : 'neutral'}>{piece.type_piece_display}</Badge>
      <span className="font-medium">{piece.reference || `#${piece.id}`}</span>
      {piece.version && <span className="text-xs text-muted-foreground">version {piece.version}</span>}
      {piece.date_reception && (
        <span className="text-xs text-muted-foreground">reçue le {formatDate(piece.date_reception)}</span>
      )}
      {piece.est_additif && pieceModifiee && (
        <Badge tone="warning">modifie « {pieceModifiee.reference || pieceModifiee.type_piece_display} »</Badge>
      )}
      {!piece.est_additif && (
        <Button size="sm" variant="outline" className="ml-auto" onClick={() => onSignalerAdditif(piece)}>
          Signaler un additif
        </Button>
      )}
    </li>
  )
}

export default function PiecesConsultation({ affaireId } = {}) {
  const routeParams = useParams()
  const id = affaireId ?? routeParams.id
  const [aSignaler, setASignaler] = useState(null)

  const { data: pieces, loading, error, refetch } = useResource(
    () => aoApi.piecesConsultation.list({ appel_offre: id }), id,
    {
      initialData: [],
      select: unwrapList,
      errorMessage: 'Impossible de charger les pièces du dossier de consultation.',
      enabled: Boolean(id),
    },
  )

  const parId = useMemo(() => new Map(pieces.map((p) => [p.id, p])), [pieces])

  const signalerAdditif = async (piece, { reference, version }) => {
    try {
      const res = await aoApi.piecesConsultation.additif(piece.id, { reference, version })
      const n = res?.data?.exigences_a_reverifier?.length ?? 0
      toast.success(
        n > 0
          ? `Additif enregistré — ${n} exigence(s) CPS marquée(s) « à revérifier ».`
          : 'Additif enregistré.',
      )
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Additif non enregistré.'))
    }
  }

  if (!id) {
    return (
      <EmptyState
        icon={Files}
        title="Pièces du DCE indisponibles"
        description="Cet écran se rattache à une affaire — ouvrez-la depuis la liste des affaires."
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">Pièces du dossier de consultation</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          CPS, règlement, plans reçus de l’acheteur — un additif est rattaché à la pièce qu’il modifie.
        </p>
      </div>

      <Card>
        <CardHeader><CardTitle>Nouvelle pièce reçue</CardTitle></CardHeader>
        <CardContent><CreationForm affaireId={id} onCree={refetch} /></CardContent>
      </Card>

      {loading && <Skeleton className="h-40 w-full" />}
      {error && <EmptyState icon={FileWarning} tone="error" title="Pièces indisponibles" description={error} />}
      {!loading && !error && (
        pieces.length === 0 ? (
          <EmptyState icon={Files} title="Aucune pièce reçue" description="Rien n’est encore enregistré pour cette affaire." />
        ) : (
          <Card className="p-3">
            <ul className="flex flex-col gap-2">
              {pieces.map((p) => (
                <LignePiece
                  key={p.id}
                  piece={p}
                  pieceModifiee={p.modifie ? parId.get(p.modifie) : null}
                  onSignalerAdditif={setASignaler}
                />
              ))}
            </ul>
          </Card>
        )
      )}

      {aSignaler && (
        <AdditifDialog piece={aSignaler} onClose={() => setASignaler(null)} onConfirmer={signalerAdditif} />
      )}
    </div>
  )
}
