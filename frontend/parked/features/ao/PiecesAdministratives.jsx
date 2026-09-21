import { useMemo, useState } from 'react'
import { AlertTriangle, BookOpen, Link2 } from 'lucide-react'
import aoApi from '../../api/aoApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import {
  Badge, Button, Card, CardHeader, CardTitle, CardContent, Input, Label, Select,
  SelectTrigger, SelectValue, SelectContent, SelectItem, EmptyState, Skeleton, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatDate } from '../../lib/format'
import { getApiError } from '../../lib/apiError'
import { expireAvant } from './administratif/AdministratifPage.utils'

/* ============================================================================
   PACT73 — Bibliothèque des pièces administratives (AOF137).
   ----------------------------------------------------------------------------
   `PieceAdministrative` porte les pièces DATÉES réutilisables d'un AO à
   l'autre : déclaration sur l'honneur, attestation fiscale de moins d'un an,
   CNSS de moins de trois mois, registre de commerce, RIB, assurances. La
   pièce compte : **la date de référence est celle de la remise des plis,
   PAS celle du jour** (`PieceAdministrative.est_expiree_a`, jamais un calcul
   de péremption « à aujourd'hui » côté écran).

   `date_expiration` est DÉRIVÉE côté serveur (émission + durée réglementaire)
   — jamais recalculée ici (AOF94). Ce que ce panneau calcule, c'est une
   COMPARAISON de deux dates déjà servies (la date d'expiration de la pièce et
   la date de remise des plis de l'AO choisi), avec le même comparateur pur
   que le volet Administratif (`expireAvant`, `administratif/AdministratifPage.utils.js`)
   — jamais une seconde règle de péremption.

   Le rattachement (`rattacher`) ajoute la pièce à un DOSSIER (`DossierAO`),
   pas à une affaire : sans dossier de dépôt encore créé, le rattachement est
   refusé avec un motif écrit, jamais un ID deviné.
   ========================================================================== */

const errMsg = (e, fallback) => getApiError(e, fallback).message

const TYPES_PIECE = [
  ['declaration_honneur', "Déclaration sur l'honneur"],
  ['pouvoirs', 'Pouvoirs du signataire'],
  ['attestation_fiscale', 'Attestation fiscale'],
  ['attestation_cnss', 'Attestation CNSS'],
  ['registre_commerce', 'Registre de commerce (modèle J)'],
  ['rib', 'RIB'],
  ['assurance_rc', 'Assurance responsabilité civile'],
  ['assurance_decennale', 'Assurance décennale étanchéité'],
  ['caution_provisoire', 'Caution provisoire'],
  ['autre', 'Autre pièce administrative'],
]

function Champ({ id, label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  )
}

function CreationForm({ onCree }) {
  const [form, setForm] = useState({
    type_piece: 'declaration_honneur', libelle: '', emetteur: '', societe_emettrice: '',
    date_emission: '', duree_validite_jours: '', rappel_jours: '30',
  })
  const [envoi, setEnvoi] = useState(false)
  const set = (champ) => (e) => setForm((p) => ({ ...p, [champ]: e.target.value }))

  const soumettre = async (e) => {
    e.preventDefault()
    if (!form.libelle.trim()) return
    setEnvoi(true)
    try {
      const payload = { type_piece: form.type_piece, libelle: form.libelle.trim() }
      if (form.emetteur.trim()) payload.emetteur = form.emetteur.trim()
      if (form.societe_emettrice.trim()) payload.societe_emettrice = form.societe_emettrice.trim()
      if (form.date_emission) payload.date_emission = form.date_emission
      if (form.duree_validite_jours !== '') payload.duree_validite_jours = Number(form.duree_validite_jours)
      payload.rappel_jours = form.rappel_jours === '' ? 30 : Number(form.rappel_jours)
      await aoApi.piecesAdministratives.create(payload)
      toast.success('Pièce administrative enregistrée.')
      setForm({
        type_piece: 'declaration_honneur', libelle: '', emetteur: '', societe_emettrice: '',
        date_emission: '', duree_validite_jours: '', rappel_jours: '30',
      })
      onCree()
    } catch (e2) {
      toast.error(errMsg(e2, 'Pièce non enregistrée.'))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <form onSubmit={soumettre} noValidate className="grid gap-3 sm:grid-cols-3">
      <Champ id="ao-pa-type" label="Type de pièce">
        <Select value={form.type_piece} onValueChange={(v) => setForm((p) => ({ ...p, type_piece: v }))}>
          <SelectTrigger id="ao-pa-type"><SelectValue /></SelectTrigger>
          <SelectContent>
            {TYPES_PIECE.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
          </SelectContent>
        </Select>
      </Champ>
      <Champ id="ao-pa-libelle" label="Libellé">
        <Input id="ao-pa-libelle" value={form.libelle} onChange={set('libelle')} required />
      </Champ>
      <Champ id="ao-pa-emetteur" label="Émetteur">
        <Input id="ao-pa-emetteur" value={form.emetteur} onChange={set('emetteur')} placeholder="DGI, CNSS, tribunal de commerce…" />
      </Champ>
      <Champ id="ao-pa-societe" label="Société titulaire de la pièce">
        <Input id="ao-pa-societe" value={form.societe_emettrice} onChange={set('societe_emettrice')} />
      </Champ>
      <Champ id="ao-pa-emission" label="Date d'émission">
        <Input id="ao-pa-emission" type="date" value={form.date_emission} onChange={set('date_emission')} />
      </Champ>
      <Champ id="ao-pa-duree" label="Durée de validité (jours)">
        <Input id="ao-pa-duree" type="number" step="1" value={form.duree_validite_jours} onChange={set('duree_validite_jours')} placeholder="fiscale 365 / CNSS 90 par défaut" />
      </Champ>
      <Champ id="ao-pa-rappel" label="Rappel avant expiration (jours)">
        <Input id="ao-pa-rappel" type="number" step="1" value={form.rappel_jours} onChange={set('rappel_jours')} />
      </Champ>
      <div className="flex items-end">
        <Button type="submit" disabled={envoi || !form.libelle.trim()}>
          {envoi ? 'Enregistrement…' : 'Enregistrer la pièce'}
        </Button>
      </div>
    </form>
  )
}

function RattacherDialog({ piece, onClose, onConfirmer }) {
  const [affaireId, setAffaireId] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const { data: affaires } = useResource(
    () => aoApi.affaires.list(), undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les affaires.' },
  )

  const affaireChoisie = affaires.find((a) => String(a.id) === affaireId) || null
  const dateRemise = affaireChoisie?.date_ouverture_plis || affaireChoisie?.date_limite || null
  const expiree = expireAvant(piece.date_expiration, dateRemise)

  const confirmer = async () => {
    if (!affaireId) return
    setEnvoi(true)
    try {
      await onConfirmer(piece, Number(affaireId))
      onClose()
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Rattacher « {piece.libelle} » à une affaire</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <Champ id="ao-pa-rattacher-affaire" label="Affaire">
            <Select value={affaireId} onValueChange={setAffaireId}>
              <SelectTrigger id="ao-pa-rattacher-affaire"><SelectValue placeholder="Choisir une affaire…" /></SelectTrigger>
              <SelectContent>
                {affaires.map((a) => (
                  <SelectItem key={a.id} value={String(a.id)}>{a.reference || `#${a.id}`} — {a.objet}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Champ>
          {expiree && (
            <p role="alert" className="flex items-start gap-1.5 rounded-md border border-destructive/50 bg-destructive/5 p-2 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Cette pièce expire le {formatDate(piece.date_expiration)}, AVANT la remise des plis
              {dateRemise ? ` du ${formatDate(dateRemise)}` : ''} de cette affaire.
            </p>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="button" disabled={!affaireId || envoi} onClick={confirmer}>
            {envoi ? 'Rattachement…' : 'Rattacher'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function LignePiece({ piece, onRattacher }) {
  return (
    <li className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5 text-sm">
      <Badge tone="neutral">{piece.type_piece_display}</Badge>
      <span className="font-medium">{piece.libelle}</span>
      {piece.emetteur && <span className="text-xs text-muted-foreground">— {piece.emetteur}</span>}
      <span className="ml-auto text-xs text-muted-foreground">
        {piece.date_expiration ? `valable jusqu’au ${formatDate(piece.date_expiration)}` : 'sans péremption connue'}
      </span>
      {!piece.actif && <Badge tone="warning">Inactive</Badge>}
      <Button size="sm" variant="outline" onClick={() => onRattacher(piece)}>
        <Link2 className="size-3.5" aria-hidden="true" />
        Rattacher à une affaire
      </Button>
    </li>
  )
}

export default function PiecesAdministratives() {
  const [aRattacher, setARattacher] = useState(null)

  const { data: pieces, loading, error, refetch } = useResource(
    () => aoApi.piecesAdministratives.list(), undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger les pièces administratives.' },
  )

  const parType = useMemo(() => {
    const groupes = new Map()
    for (const p of pieces) {
      const cle = p.type_piece_display || p.type_piece
      if (!groupes.has(cle)) groupes.set(cle, [])
      groupes.get(cle).push(p)
    }
    return [...groupes.entries()]
  }, [pieces])

  const rattacher = async (piece, affaireId) => {
    try {
      const dossiers = await aoApi.dossiers.list({ appel_offre: affaireId })
      const dossier = unwrapList(dossiers)[0]
      if (!dossier) {
        toast.error("Cette affaire n'a pas encore de dossier de dépôt — rien à rattacher.")
        return
      }
      await aoApi.piecesAdministratives.rattacher(piece.id, dossier.id)
      toast.success(`« ${piece.libelle} » rattachée au dossier de ce dossier de dépôt.`)
      refetch()
    } catch (e) {
      toast.error(errMsg(e, 'Rattachement impossible.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Pièces administratives"
        subtitle="Attestations et pièces datées, enregistrées une fois et réutilisées d’un appel d’offres à l’autre."
      />

      <Card>
        <CardHeader><CardTitle>Nouvelle pièce</CardTitle></CardHeader>
        <CardContent><CreationForm onCree={refetch} /></CardContent>
      </Card>

      {loading && <Skeleton className="h-56 w-full" />}
      {error && <EmptyState icon={BookOpen} tone="error" title="Bibliothèque indisponible" description={error} />}
      {!loading && !error && (
        pieces.length === 0 ? (
          <EmptyState icon={BookOpen} title="Aucune pièce administrative" description="Rien n’est encore enregistré." />
        ) : (
          <div className="flex flex-col gap-4">
            {parType.map(([type, lignes]) => (
              <Card key={type} className="flex flex-col gap-2 p-3">
                <h2 className="font-display text-base font-semibold">{type}</h2>
                <ul className="flex flex-col gap-2">
                  {lignes.map((p) => (
                    <LignePiece key={p.id} piece={p} onRattacher={setARattacher} />
                  ))}
                </ul>
              </Card>
            ))}
          </div>
        )
      )}

      {aRattacher && (
        <RattacherDialog piece={aRattacher} onClose={() => setARattacher(null)} onConfirmer={rattacher} />
      )}
    </div>
  )
}
