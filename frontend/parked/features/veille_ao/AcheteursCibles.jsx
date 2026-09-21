import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import veilleAoApi from '../../api/veilleAoApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import {
  Button, Badge, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { ListShell, EcheanceCenter, daysUntil } from '../../ui/module'
import { formatDate } from '../../lib/format'
import { TYPES_ACHETEUR } from './veilleAoShared'

/* ============================================================================
   VAO36 — Écran « Acheteurs cibles » + relances : la prospection qui capte
   les FRDISI suivants (VAO29 : le carnet ne se surveille pas, il se démarche).
   ----------------------------------------------------------------------------
   « Relances dues en tête » via `EcheanceCenter` (ui/module, UX1) — un widget
   PARTAGÉ trié par urgence, PAS un tri de colonne DataTable (une relance due
   doit être visible sans chercher, pas seulement triable). Le lien vers le
   lead CRM ouvre le lead EXISTANT (`lead_id` opaque) — jamais une création
   silencieuse d'un second lead.
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback


const typeLabel = (v) => TYPES_ACHETEUR.find((t) => t.value === v)?.label || v

function NouvelAcheteurDialog({ onClose, onCreated }) {
  const [nom, setNom] = useState('')
  const [type, setType] = useState('fondation')
  const [contact, setContact] = useState('')
  const [prochaineRelance, setProchaineRelance] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!nom.trim()) { setErr('Le nom est requis.'); return }
    setSaving(true)
    setErr(null)
    try {
      await veilleAoApi.acheteursCibles.create({
        nom: nom.trim(),
        type,
        contact: contact.trim() || undefined,
        prochaine_relance: prochaineRelance || undefined,
        notes: notes.trim() || undefined,
      })
      toast.success('Acheteur cible ajouté.')
      onCreated()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvel acheteur cible</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {/* VAO36 (Done=) — aucun champ n'est pré-rempli : la saisie part vide. */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-nom">Nom de l’organisme</Label>
            <Input id="ac-nom" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Nom réel — jamais inventé" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-type">Type</Label>
            <Select value={type} onValueChange={setType}>
              <SelectTrigger id="ac-type" aria-label="Type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPES_ACHETEUR.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-contact">Contact</Label>
            <Input id="ac-contact" value={contact} onChange={(e) => setContact(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-relance">Prochaine relance</Label>
            <Input id="ac-relance" type="date" value={prochaineRelance} onChange={(e) => setProchaineRelance(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ac-notes">Notes</Label>
            <Textarea id="ac-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optionnel" />
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default function AcheteursCibles() {
  const [creating, setCreating] = useState(false)

  const { data: rows, loading, error, refetch } = useResource(
    () => veilleAoApi.acheteursCibles.list(),
    undefined,
    { initialData: [], select: unwrapList, errorMessage: 'Impossible de charger le carnet d’acheteurs cibles.' },
  )

  // VAO36 (Done=) — une relance due est visible SANS la chercher : centre
  // d'échéances partagé (ui/module), trié par urgence, pas une colonne triable.
  const relances = useMemo(() => rows
    .filter((r) => r.prochaine_relance)
    .map((r) => ({
      id: r.id,
      label: r.nom,
      date: r.prochaine_relance,
      meta: typeLabel(r.type),
    })), [rows])

  const columns = useMemo(() => [
    {
      id: 'nom',
      header: 'Nom',
      minWidth: 200,
      accessor: (r) => r.nom || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'type',
      header: 'Type',
      width: 160,
      accessor: (r) => typeLabel(r.type),
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'dernier_contact',
      header: 'Dernier contact',
      width: 150,
      searchable: false,
      accessor: (r) => r.dernier_contact || '',
      cell: (v) => (v ? formatDate(v) : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'prochaine_relance',
      header: 'Prochaine relance',
      width: 160,
      align: 'right',
      searchable: false,
      accessor: (r) => r.prochaine_relance || '',
      cell: (v) => {
        if (!v) return <span className="text-muted-foreground">—</span>
        const due = (daysUntil(v) ?? 0) <= 0
        return (
          <span className="inline-flex items-center justify-end gap-1.5 tabular-nums">
            {formatDate(v)}
            {due && <Badge tone="danger">due</Badge>}
          </span>
        )
      },
    },
    {
      id: 'statut_relation',
      header: 'Statut de la relation',
      width: 160,
      searchable: false,
      accessor: (r) => r.statut_relation_display || r.statut_relation || '',
      cell: (v) => v || <span className="text-muted-foreground">—</span>,
    },
    {
      id: 'lead',
      header: 'Lead CRM',
      width: 130,
      searchable: false,
      accessor: (r) => (r.lead_id ? 'lié' : ''),
      // VAO36 (Done=) — ouvre le lead EXISTANT (lead_id opaque), jamais une
      // création silencieuse d'un second lead.
      cell: (_v, r) => (r.lead_id ? (
        <Link to={`/crm/leads/${r.lead_id}`} className="text-primary hover:underline">
          Voir le lead
        </Link>
      ) : <span className="text-muted-foreground">Aucun lead lié</span>),
    },
  ], [])

  return (
    <ListShell
      title="Acheteurs cibles"
      subtitle="Le carnet à démarcher — la vraie contre-mesure au montage FRDISI."
      actions={(
        <Button onClick={() => setCreating(true)}>
          <Plus className="size-4" /> Nouvel acheteur cible
        </Button>
      )}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      searchPlaceholder="Rechercher un organisme…"
      persistToUrl
      urlKey="veille-ao-acheteurs-cibles"
      exportName="acheteurs-cibles"
      emptyTitle="Aucun acheteur cible"
      emptyDescription="Ajoutez les organismes à démarcher — fondations, cliniques, groupes hôteliers…"
    >
      <EcheanceCenter
        title="Relances dues"
        items={relances}
        loading={loading}
        error={error}
        emptyText="Aucune relance programmée."
      />

      {creating && (
        <NouvelAcheteurDialog
          onClose={() => setCreating(false)}
          onCreated={() => { setCreating(false); refetch() }}
        />
      )}
    </ListShell>
  )
}
