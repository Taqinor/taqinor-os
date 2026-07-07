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
  livrerPartielBC,
  creerFactureFromBC,
} from '../../features/ventes/store/ventesSlice'
import crmApi from '../../api/crmApi'
import ventesApi from '../../api/ventesApi'
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
import { ouvrirPdfBlob } from '../../utils/pdfBlob'

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
  // XSAL12 — livraison partielle : BC ouvert dans le dialogue de saisie.
  const [livraisonBC, setLivraisonBC] = useState(null)

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

  // ZSAL8 — PDF imprimable du bon de commande (blob, ouverture nouvel onglet).
  const handleTelechargerPdfBC = async (bc) => {
    setActionId(bc.id)
    setActionError('')
    try {
      const res = await ventesApi.getBonCommandePdf(bc.id)
      ouvrirPdfBlob(res.data, `${bc.reference}.pdf`)
    } catch {
      setActionError('PDF indisponible. Réessayez.')
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

      {livraisonBC && (
        <LivraisonPartielleDialog
          bc={livraisonBC}
          onClose={() => setLivraisonBC(null)}
          onSaved={() => { dispatch(fetchBonsCommande()); setLivraisonBC(null) }}
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
                  <th>Reliquat</th>
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
                        {/* XSAL12 — état dérivé de livraison partielle (lecture seule). */}
                        {bc.est_partiellement_livre
                          ? <Badge tone="warning">Partiel</Badge>
                          : <span className="text-muted-foreground">—</span>}
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
                          {/* XSAL12 — livraison partielle : réservée aux BC avec devis, pas déjà livrés. */}
                          {bc.statut === 'confirme' && bc.devis_reference && (
                            <Button size="sm" variant="outline" loading={busy}
                                    onClick={() => setLivraisonBC(bc)}>
                              Livrer partiellement
                            </Button>
                          )}
                          {(bc.statut === 'confirme' || bc.statut === 'livre') && !bc.has_facture && (
                            <Button size="sm" variant="outline" loading={busy}
                                    onClick={() => handleCreerFacture(bc)}>
                              <FilePlus2 /> Facture
                            </Button>
                          )}
                          {/* ZSAL8 — PDF imprimable du BC (layout legacy, jamais le moteur devis premium). */}
                          <Button size="sm" variant="outline" loading={busy}
                                  onClick={() => handleTelechargerPdfBC(bc)}>
                            PDF
                          </Button>
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

// Délai de livraison par défaut (jours) appliqué aux nouveaux bons de commande.
const BC_DELAI_LIVRAISON_DEFAUT = 14

// Date par défaut : aujourd'hui + délai (AAAA-MM-JJ).
function defaultLivraison(days = BC_DELAI_LIVRAISON_DEFAUT) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function BCForm({ bc = null, onClose, onSaved }) {
  const dispatch = useDispatch()
  const isEdit = !!bc

  const [clients, setClients] = useState([])
  const [saving, setSaving]   = useState(false)
  const [errors, setErrors]   = useState({})

  const [fields, setFields] = useState({
    client:               bc ? String(bc.client) : '',
    // Nouveau BC : pré-remplir la livraison prévue (émission + délai), éditable.
    date_livraison_prevue: bc?.date_livraison_prevue ?? (bc ? '' : defaultLivraison()),
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

// ── XSAL12 — Dialogue de livraison partielle ────────────────────────────────
// Saisit, ligne par ligne, la quantité livrée MAINTENANT (bornée par le
// reliquat déjà calculé côté serveur `bc.reliquat_par_ligne`) ; le BC passe
// automatiquement à « livré » côté serveur seulement quand tout le reliquat
// est soldé — cet écran ne fait qu'envoyer la saisie.
function LivraisonPartielleDialog({ bc, onClose, onSaved }) {
  const dispatch = useDispatch()
  const reliquats = (bc.reliquat_par_ligne ?? []).filter(r => r.reliquat > 0)
  const [quantites, setQuantites] = useState(() =>
    Object.fromEntries(reliquats.map(r => [r.ligne_devis_id, ''])))
  const [dateLivraison, setDateLivraison] = useState(() => new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const setQuantite = (ligneId, v) => setQuantites(q => ({ ...q, [ligneId]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    const lignes = Object.entries(quantites)
      .filter(([, v]) => parseFloat(v) > 0)
      .map(([ligne_devis, quantite]) => ({ ligne_devis: parseInt(ligne_devis, 10), quantite }))
    if (lignes.length === 0) {
      setError('Saisissez au moins une quantité à livrer.')
      return
    }
    setSaving(true)
    try {
      await dispatch(livrerPartielBC({
        id: bc.id,
        data: { lignes, date_livraison: dateLivraison, note: note || undefined },
      })).unwrap()
      onSaved()
    } catch (err) {
      setError(err?.detail ?? "La livraison partielle a échoué. Vérifiez les quantités.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Livraison partielle — {bc.reference}</DialogTitle>
        </DialogHeader>
        <Form onSubmit={handleSubmit} className="gap-4">
          {reliquats.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun reliquat à livrer sur ce BC.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Ligne</th>
                    <th className="ta-right">Reliquat</th>
                    <th className="ta-right">Quantité livrée</th>
                  </tr>
                </thead>
                <tbody>
                  {reliquats.map(r => (
                    <tr key={r.ligne_devis_id}>
                      <td>{r.designation}</td>
                      <td className="ta-right tabular-nums">{r.reliquat}</td>
                      <td className="ta-right">
                        <Input
                          type="number" min="0" max={r.reliquat} step="any"
                          className="w-28 text-right"
                          aria-label={`Quantité livrée — ${r.designation}`}
                          value={quantites[r.ligne_devis_id] ?? ''}
                          onChange={e => setQuantite(r.ligne_devis_id, e.target.value)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <FormField label="Date de livraison" htmlFor="lp-date" fullWidth>
            <Input id="lp-date" type="date" value={dateLivraison}
                   onChange={e => setDateLivraison(e.target.value)} />
          </FormField>

          <div className="grid gap-1.5">
            <Label htmlFor="lp-note">Note</Label>
            <Textarea id="lp-note" rows={2} value={note}
                      onChange={e => setNote(e.target.value)}
                      placeholder="Référence bon de livraison, transporteur..." />
          </div>

          {error && (
            <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </p>
          )}

          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={reliquats.length === 0}>
              Enregistrer la livraison
            </Button>
          </FormActions>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
