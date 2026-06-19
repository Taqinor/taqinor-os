import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, FilePlus2, PackageX } from 'lucide-react'
import {
  fetchBonsCommande,
  createBonCommande,
  updateBonCommande,
  confirmerBC,
  marquerLivreBC,
  annulerBC,
  creerFactureFromBC,
} from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'
import {
  Button, Badge, StatusPill, Card, EmptyState, Spinner,
  Tabs, TabsList, TabsTrigger,
  Input,
  Dialog, DialogContent, DialogHeader, DialogTitle,
  Form, FormField, FormActions,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Textarea, Label,
} from '../../ui'
import { formatMAD } from '../../lib/format'

const STATUT_DISPLAY = {
  en_attente: 'En attente',
  confirme:   'Confirmé',
  livre:      'Livré',
  annule:     'Annulé',
}

const TABS = [
  { key: 'tous',       label: 'Tous' },
  { key: 'en_attente', label: 'En attente' },
  { key: 'confirme',   label: 'Confirmés' },
  { key: 'livre',      label: 'Livrés' },
  { key: 'annule',     label: 'Annulés' },
]

export default function BonCommandeList() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { bonsCommande, loading, error } = useSelector(s => s.ventes)

  const [activeTab, setActiveTab] = useState('tous')
  const [search, setSearch]       = useState('')
  const [actionId, setActionId]   = useState(null)
  const [showForm, setShowForm]   = useState(false)
  const [editBC, setEditBC]       = useState(null)
  const [actionError, setActionError] = useState('')

  useEffect(() => { dispatch(fetchBonsCommande()) }, [dispatch])

  const filtered = useMemo(() => {
    let list = activeTab === 'tous'
      ? bonsCommande
      : bonsCommande.filter(b => b.statut === activeTab)
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(b =>
        b.reference?.toLowerCase().includes(q) ||
        (b.client_nom ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [bonsCommande, activeTab, search])

  const counts = useMemo(() => ({
    tous:       bonsCommande.length,
    en_attente: bonsCommande.filter(b => b.statut === 'en_attente').length,
    confirme:   bonsCommande.filter(b => b.statut === 'confirme').length,
    livre:      bonsCommande.filter(b => b.statut === 'livre').length,
    annule:     bonsCommande.filter(b => b.statut === 'annule').length,
  }), [bonsCommande])

  const doAction = async (thunk, id, confirmMsg) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return
    setActionId(id)
    setActionError('')
    try {
      await dispatch(thunk(id)).unwrap()
    } catch (err) {
      setActionError(err?.detail ?? "L'action a échoué. Réessayez.")
    } finally {
      setActionId(null)
    }
  }

  // Création de facture depuis un BC : message FR clair quand une facture
  // existe déjà (le backend renvoie un 400), avec un raccourci vers les factures.
  const handleCreerFacture = async (bc) => {
    if (!window.confirm(`Créer une facture pour ${bc.reference} ?`)) return
    setActionId(bc.id)
    setActionError('')
    try {
      await dispatch(creerFactureFromBC(bc.id)).unwrap()
      dispatch(fetchBonsCommande())
    } catch (err) {
      const detail = err?.detail ?? ''
      if (/existe déjà/i.test(detail)) {
        setActionError(`Une facture existe déjà pour le BC ${bc.reference}.`)
        if (window.confirm('Une facture existe déjà pour ce BC. Ouvrir la liste des factures ?')) {
          navigate('/ventes/factures')
        }
      } else {
        setActionError(detail || 'Création de la facture impossible. Réessayez.')
      }
    } finally {
      setActionId(null)
    }
  }

  const openNew  = () => { setEditBC(null); setShowForm(true) }
  const openEdit = bc => { setEditBC(bc);   setShowForm(true) }
  const closeForm = () => { setShowForm(false); setEditBC(null) }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
        <Spinner /> Chargement des bons de commande…
      </div>
    )
  }
  if (error) {
    return (
      <div className="page">
        <EmptyState icon={PackageX} title="Erreur de chargement"
                    description="Impossible de charger les bons de commande. Réessayez." />
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Bons de commande
          {bonsCommande.length > 0 && (
            <Badge tone="primary" className="ml-2 align-middle">{bonsCommande.length}</Badge>
          )}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            className="w-full sm:w-64"
            leading={<Search />}
            placeholder="Référence, client…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <Button onClick={openNew}><Plus /> Nouveau BC</Button>
        </div>
      </div>

      {actionError && (
        <div role="alert" className="mt-2 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {showForm && (
        <BCForm
          bc={editBC}
          onClose={closeForm}
          onSaved={() => { dispatch(fetchBonsCommande()); closeForm() }}
        />
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-1">
        <TabsList className="flex-wrap">
          {TABS.map(t => (
            <TabsTrigger key={t.key} value={t.key}>
              {t.label}
              {counts[t.key] > 0 && (
                <span className="ml-1.5 rounded bg-muted px-1.5 text-xs text-muted-foreground">{counts[t.key]}</span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {filtered.length === 0 ? (
        <EmptyState
          icon={PackageX}
          title={search ? `Aucun résultat pour « ${search} »` : 'Aucun bon de commande'}
          description={
            search
              ? 'Affinez votre recherche.'
              : activeTab !== 'tous'
                ? 'Aucun BC dans cet onglet.'
                : 'Créez-en un ou convertissez un devis.'
          }
          className="mt-4"
        />
      ) : (
        <Card className="mt-4 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Référence</th>
                  <th>Client</th>
                  <th>Devis</th>
                  <th className="ta-right">Total TTC</th>
                  <th>Livraison prévue</th>
                  <th>Statut</th>
                  <th>Facture</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(bc => {
                  const busy = actionId === bc.id
                  return (
                    <tr key={bc.id}>
                      <td><strong>{bc.reference}</strong></td>
                      <td>{bc.client_nom ?? '—'}</td>
                      <td>{bc.devis_reference ?? <span className="text-muted-foreground">—</span>}</td>
                      <td className="ta-right tabular-nums">
                        {bc.total_ttc != null
                          ? formatMAD(bc.total_ttc)
                          : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td>
                        {bc.date_livraison_prevue
                          ? new Date(bc.date_livraison_prevue).toLocaleDateString('fr-FR')
                          : '—'}
                      </td>
                      <td>
                        <StatusPill status={bc.statut} label={STATUT_DISPLAY[bc.statut] ?? STATUT_DISPLAY.en_attente} />
                      </td>
                      <td>
                        {bc.has_facture
                          ? <Badge tone="success">Oui</Badge>
                          : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td>
                        <div className="flex flex-wrap items-center gap-2">
                          {(bc.statut === 'en_attente' || bc.statut === 'confirme') && (
                            <Button size="sm" variant="outline" onClick={() => openEdit(bc)}>
                              Éditer
                            </Button>
                          )}
                          {bc.statut === 'en_attente' && (
                            <Button size="sm" loading={busy} onClick={() => doAction(confirmerBC, bc.id)}>
                              Confirmer
                            </Button>
                          )}
                          {bc.statut === 'confirme' && (
                            <Button size="sm" variant="success" loading={busy}
                                    onClick={() => doAction(marquerLivreBC, bc.id, `Marquer le BC ${bc.reference} comme livré ?`)}>
                              Livrer
                            </Button>
                          )}
                          {(bc.statut === 'confirme' || bc.statut === 'livre') && !bc.has_facture && (
                            <Button size="sm" variant="outline" loading={busy}
                                    onClick={() => handleCreerFacture(bc)}>
                              <FilePlus2 /> Facture
                            </Button>
                          )}
                          {bc.statut !== 'livre' && bc.statut !== 'annule' && (
                            <Button size="sm" variant="outline" loading={busy}
                                    onClick={() => doAction(annulerBC, bc.id, `Annuler le BC ${bc.reference} ?`)}>
                              Annuler
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

// ── Formulaire BC (création / édition) ─────────────────────────────────────────

function BCForm({ bc = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const isEdit = !!bc

  const [clients, setClients] = useState([])
  const [saving, setSaving]   = useState(false)
  const [errors, setErrors]   = useState({})

  const [fields, setFields] = useState({
    client:               bc ? String(bc.client) : '',
    date_livraison_prevue: bc?.date_livraison_prevue ?? '',
    note:                 bc?.note ?? '',
  })

  useEffect(() => {
    crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const validate = () => {
    const e = {}
    if (!fields.client) e.client = 'Client requis'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        client:               parseInt(fields.client),
        date_livraison_prevue: fields.date_livraison_prevue || null,
        note:                 fields.note || null,
      }
      if (isEdit) {
        await dispatch(updateBonCommande({ id: bc.id, data: payload })).unwrap()
      } else {
        await dispatch(createBonCommande(payload)).unwrap()
      }
      onSaved()
    } catch (err) {
      const msg = err?.detail ?? err?.non_field_errors?.[0] ?? JSON.stringify(err)
      setErrors(prev => ({ ...prev, submit: msg }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? `Éditer — ${bc.reference}` : 'Nouveau bon de commande'}</DialogTitle>
        </DialogHeader>
        <Form onSubmit={handleSubmit} className="gap-4">
          <FormField label="Client" required htmlFor="bc-client" error={errors.client} fullWidth>
            <Select value={fields.client || undefined}
                    onValueChange={v => setField('client', v)}
                    disabled={isEdit}>
              <SelectTrigger id="bc-client" invalid={!!errors.client}>
                <SelectValue placeholder="— Sélectionner un client —" />
              </SelectTrigger>
              <SelectContent>
                {clients.map(c => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.nom}{c.prenom ? ` ${c.prenom}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <FormField label="Date de livraison prévue" htmlFor="bc-livraison" fullWidth>
            <Input id="bc-livraison" type="date" value={fields.date_livraison_prevue}
                   onChange={e => setField('date_livraison_prevue', e.target.value)} />
          </FormField>

          <div className="grid gap-1.5">
            <Label htmlFor="bc-note">Note</Label>
            <Textarea id="bc-note" rows={3} value={fields.note}
                      onChange={e => setField('note', e.target.value)}
                      placeholder="Instructions, remarques..." />
          </div>

          {errors.submit && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </p>
          )}

          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>
              {isEdit ? 'Mettre à jour' : 'Créer le BC'}
            </Button>
          </FormActions>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
