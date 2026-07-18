// NTCRM9 — Org chart visuel du compte (onglet « Organigramme » sur la fiche
// client). Liste les ContactClient (NTCRM8) groupés par rôle d'achat avec
// badges couleur + une carte hiérarchique CSS simple (pas de canvas), et des
// actions rapides (appeler/WhatsApp/email) par contact.
// WIR12 — création/édition d'un ContactClient depuis la fiche client, sans
// appel API manuel (POST/PATCH /contacts/contacts-client/, ViewSet déjà scopé
// société).
import { useEffect, useState } from 'react'
import { Plus, Pencil } from 'lucide-react'
import api from '../../../api/axios'
import {
  Spinner, EmptyState, Card, Badge, Button,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { toast } from '../../../ui/confirm'

const ROLE_LABELS = {
  decideur: 'Décideur',
  influenceur: 'Influenceur',
  utilisateur: 'Utilisateur',
  gatekeeper: 'Gatekeeper',
  sponsor: 'Sponsor',
  autre: 'Autre',
}

const ROLE_ORDER = ['decideur', 'sponsor', 'influenceur', 'gatekeeper', 'utilisateur', 'autre']

const ROLE_COLORS = {
  decideur: 'bg-purple-100 text-purple-800',
  sponsor: 'bg-blue-100 text-blue-800',
  influenceur: 'bg-amber-100 text-amber-800',
  gatekeeper: 'bg-red-100 text-red-800',
  utilisateur: 'bg-green-100 text-green-800',
  autre: 'bg-gray-100 text-gray-800',
}

const EMPTY_FORM = {
  nom: '', prenom: '', poste: '', role_achat: 'autre',
  telephone: '', whatsapp: '', email: '',
}

export default function OrgChartTab({ clientId }) {
  const [contacts, setContacts] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formOpen, setFormOpen] = useState(false)
  const [saving, setSaving] = useState(false)

  const loadContacts = () => {
    if (!clientId) return Promise.resolve()
    setLoading(true)
    return api.get('/contacts/contacts-client/', { params: { client: clientId } })
      .then((res) => setContacts(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error("Impossible de charger l'organigramme."))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadContacts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId])

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setFormOpen(true)
  }

  const openEdit = (contact) => {
    setEditingId(contact.id)
    setForm({
      nom: contact.nom || '',
      prenom: contact.prenom || '',
      poste: contact.poste || '',
      role_achat: contact.role_achat || 'autre',
      telephone: contact.telephone || '',
      whatsapp: contact.whatsapp || '',
      email: contact.email || '',
    })
    setFormOpen(true)
  }

  const setField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const saveContact = async () => {
    if (!form.nom.trim()) {
      toast.error('Le nom est requis.')
      return
    }
    setSaving(true)
    const payload = {
      client: clientId,
      nom: form.nom.trim(),
      prenom: form.prenom.trim(),
      poste: form.poste.trim(),
      role_achat: form.role_achat,
      telephone: form.telephone.trim() || null,
      whatsapp: form.whatsapp.trim() || null,
      email: form.email.trim() || null,
    }
    try {
      if (editingId) {
        await api.patch(`/contacts/contacts-client/${editingId}/`, payload)
        toast.success('Contact mis à jour.')
      } else {
        await api.post('/contacts/contacts-client/', payload)
        toast.success('Contact ajouté.')
      }
      setFormOpen(false)
      await loadContacts()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? "Impossible d'enregistrer le contact.")
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Spinner />

  const groupes = ROLE_ORDER
    .map((role) => ({ role, items: contacts.filter((c) => c.role_achat === role) }))
    .filter((g) => g.items.length > 0)

  return (
    <div className="space-y-4" data-testid="org-chart-tab">
      <div className="flex items-center justify-end">
        <Button type="button" size="sm" onClick={openCreate}>
          <Plus className="size-4" /> Ajouter un contact
        </Button>
      </div>

      {contacts.length === 0 ? (
        <EmptyState
          title="Aucun contact"
          description="Ajoutez des contacts pour construire l'organigramme d'achat."
          action={<Button type="button" size="sm" onClick={openCreate}><Plus className="size-4" /> Ajouter un contact</Button>}
        />
      ) : (
        groupes.map((g) => (
          <Card key={g.role} className="p-4 space-y-2">
            <Badge className={ROLE_COLORS[g.role]}>{ROLE_LABELS[g.role]}</Badge>
            <ul className="space-y-2 mt-2">
              {g.items.map((contact) => (
                <li key={contact.id} className="flex items-center justify-between text-sm border-b pb-2">
                  <div>
                    <div className="font-medium">
                      {contact.nom} {contact.prenom}
                      {contact.contact_principal && (
                        <span className="ml-2 text-xs text-muted-foreground">(principal)</span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">{contact.poste}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    {contact.telephone && (
                      <a href={`tel:${contact.telephone}`} className="text-xs underline">Appeler</a>
                    )}
                    {contact.whatsapp && (
                      <a
                        href={`https://wa.me/${contact.whatsapp.replace(/\D/g, '')}`}
                        target="_blank" rel="noreferrer" className="text-xs underline"
                      >
                        WhatsApp
                      </a>
                    )}
                    {contact.email && (
                      <a href={`mailto:${contact.email}`} className="text-xs underline">Email</a>
                    )}
                    <Button
                      type="button" size="sm" variant="ghost"
                      onClick={() => openEdit(contact)}
                      aria-label={`Éditer ${contact.nom}`}
                      title="Éditer"
                    >
                      <Pencil className="size-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        ))
      )}

      <Dialog open={formOpen} onOpenChange={(o) => { if (!o) setFormOpen(false) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingId ? 'Éditer le contact' : 'Nouveau contact'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="oc-nom">Nom</Label>
                <Input id="oc-nom" value={form.nom} onChange={setField('nom')} sanitize="name" autoFocus />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="oc-prenom">Prénom</Label>
                <Input id="oc-prenom" value={form.prenom} onChange={setField('prenom')} sanitize="name" />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="oc-poste">Poste</Label>
              <Input id="oc-poste" value={form.poste} onChange={setField('poste')} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="oc-role">Rôle d'achat</Label>
              <Select value={form.role_achat} onValueChange={(v) => setForm((f) => ({ ...f, role_achat: v }))}>
                <SelectTrigger id="oc-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ROLE_ORDER.map((role) => (
                    <SelectItem key={role} value={role}>{ROLE_LABELS[role]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-1.5">
                <Label htmlFor="oc-tel">Téléphone</Label>
                <Input id="oc-tel" value={form.telephone} onChange={setField('telephone')} sanitize="off" />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="oc-wa">WhatsApp</Label>
                <Input id="oc-wa" value={form.whatsapp} onChange={setField('whatsapp')} sanitize="off" />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="oc-email">Email</Label>
              <Input id="oc-email" type="email" value={form.email} onChange={setField('email')} sanitize="email" />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setFormOpen(false)}>Annuler</Button>
            <Button type="button" onClick={saveContact} loading={saving} disabled={saving}>
              {editingId ? 'Enregistrer' : 'Ajouter'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
