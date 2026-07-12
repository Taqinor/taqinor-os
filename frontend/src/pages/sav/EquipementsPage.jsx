import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import {
  Download, Upload, PackageSearch, AlarmClock, AlertTriangle, RotateCcw, Save,
  Wrench, Pencil, ShieldCheck, Trash2, ChevronRight, Activity,
} from 'lucide-react'
import { fetchEquipements } from '../../features/sav/store/equipementsSlice'
import savApi from '../../api/savApi'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import importApi from '../../api/importApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import ExcelImport from '../../components/ExcelImport'
import RegistreGarantiesDialog from './RegistreGarantiesDialog'
import EquipementFiabilitePanel from './EquipementFiabilitePanel'
import {
  EMPTY_EQUIP_FILTERS,
  EQUIP_STATUTS,
  EQUIP_STATUT_LABELS,
  GARANTIE_FILTRES,
  GARANTIE_ETATS,
  filterEquipements,
  sortEquipements,
  garantieLabel,
} from '../../features/sav/equipement'
import {
  TooltipProvider,
  Button,
  StatusPill,
  Card,
  EmptyState,
  Skeleton,
  Spinner,
  Input,
  Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  Form, FormSection, FormField, FormActions, useDirtyGuard, confirmLeaveIfDirty,
  DataTable,
  toast,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// État de garantie → ton StatusPill (la couleur n'est jamais le seul signal :
// le libellé reste explicite). Aligné sur equipement.js / le serializer backend.
const GARANTIE_TONES = {
  sous_garantie: 'success',
  expire_bientot: 'warning',
  hors_garantie: 'danger',
  non_renseignee: 'neutral',
}

export function GarantiePill({ eq }) {
  const etat = eq?.garantie_etat ?? 'non_renseignee'
  return <StatusPill tone={GARANTIE_TONES[etat] ?? 'neutral'} label={garantieLabel(eq)} />
}

// L611/L11 — message d'erreur FR lisible mappé au champ (jamais de JSON brut).
const FIELD_LABELS_EQ = {
  numero_serie: 'Numéro de série', date_pose: 'Date de pose',
  statut: 'Statut', produit: 'Produit', installation: 'Chantier',
}
function frError(data, fallback) {
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  if (typeof data === 'object') {
    const [field, val] = Object.entries(data)[0] ?? []
    if (field) {
      const msg = Array.isArray(val) ? val[0] : val
      const label = FIELD_LABELS_EQ[field] ?? field
      return `Échec : ${label} — ${msg}`
    }
  }
  return fallback
}

// XSAV15/16/17 — section repliable (même patron que TicketsPage.CollapsibleSection).
function CollapsibleSection({ icon: Icon, title, children }) {
  return (
    <details open className="group flex flex-col gap-3 [&[open]>summary>svg.chevron]:rotate-90">
      <summary className="flex cursor-pointer list-none items-center gap-2 font-display text-base font-semibold text-foreground">
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
        <span className="flex-1">{title}</span>
        <ChevronRight className="chevron size-4 rotate-0 text-muted-foreground transition-transform" aria-hidden="true" />
      </summary>
      <div className="flex flex-col gap-3 pt-2">{children}</div>
    </details>
  )
}

export function EquipementDetail({ equipement, onClose, onSaved }) {
  const navigate = useNavigate()
  const initial = useMemo(() => ({
    numero_serie: equipement.numero_serie ?? '',
    date_pose: equipement.date_pose ?? '',
    statut: equipement.statut ?? 'en_service',
    note: equipement.note ?? '',
  }), [equipement])

  const [fields, setFields] = useState(initial)
  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [creatingTicket, setCreatingTicket] = useState(false)
  // L624 — compte des tickets SAV ouverts liés à cet équipement.
  const [nbTickets, setNbTickets] = useState(equipement.nb_tickets_ouverts ?? null)
  // L628 — correction gardée du produit / chantier (readOnly par défaut).
  const [correcting, setCorrecting] = useState(false)
  const [produit, setProduit] = useState(String(equipement.produit ?? ''))
  const [installation, setInstallation] = useState(String(equipement.installation ?? ''))
  const [produits, setProduits] = useState([])
  const [installations, setInstallations] = useState([])

  // L624 — recharge le compte de tickets ouverts à l'ouverture de la fiche
  // (sauf si le serializer l'a déjà fourni via nb_tickets_ouverts).
  useEffect(() => {
    if (equipement.nb_tickets_ouverts != null) return
    savApi.getTickets({ equipement: equipement.id, ouvert: 'tous' })
      .then((r) => {
        const rows = r.data.results ?? r.data ?? []
        setNbTickets(rows.filter((t) => !t.annule
          && ['nouveau', 'planifie', 'en_cours'].includes(t.statut)).length)
      })
      .catch(() => setNbTickets(null))
  }, [equipement.id, equipement.nb_tickets_ouverts])

  // L628 — charge les options produit/chantier seulement quand on corrige.
  useEffect(() => {
    if (!correcting || produits.length) return
    stockApi.getProduits()
      .then((r) => setProduits(r.data.results ?? r.data ?? [])).catch(() => {})
    installationsApi.getInstallations()
      .then((r) => setInstallations(r.data.results ?? r.data ?? [])).catch(() => {})
  }, [correcting]) // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(
    () => Object.keys(initial).some((k) => (fields[k] ?? '') !== (initial[k] ?? ''))
      || (correcting && (produit !== String(equipement.produit ?? '')
        || installation !== String(equipement.installation ?? ''))),
    [fields, initial, correcting, produit, installation, equipement],
  )
  useDirtyGuard(dirty)

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      const payload = {
        numero_serie: nullable(fields.numero_serie),
        date_pose: nullable(fields.date_pose),
        statut: fields.statut,
        note: nullable(fields.note),
      }
      // L628 — produit/chantier ne sont envoyés que si la correction est ouverte.
      if (correcting) {
        if (produit) payload.produit = produit
        if (installation) payload.installation = installation
      }
      await savApi.updateEquipement(equipement.id, payload)
      toast.success('Équipement mis à jour')
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frError(err.response?.data, 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  // L626 — ouvre un ticket SAV pré-rempli (équipement → installation + client
  // déduits côté serveur), puis bascule vers la liste des tickets.
  const creerTicket = async () => {
    setCreatingTicket(true)
    setError(null)
    try {
      await savApi.createTicket({
        equipement: equipement.id, type: 'correctif',
        description: `Ticket ouvert depuis l'équipement ${equipement.numero_serie ?? equipement.produit_nom ?? ''}`.trim(),
      })
      toast.success('Ticket SAV créé')
      navigate('/sav')
    } catch (err) {
      setError(frError(err.response?.data, 'Création du ticket impossible.'))
    } finally {
      setCreatingTicket(false)
    }
  }

  // ── ZMFG12 — mise au rebut motivée / réactivation ──
  const [rebutOpen, setRebutOpen] = useState(false)
  const [motifRebut, setMotifRebut] = useState('')
  const [rebutBusy, setRebutBusy] = useState(false)
  const [current, setCurrent] = useState(equipement)

  const mettreAuRebut = async () => {
    if (!motifRebut.trim()) return
    setRebutBusy(true)
    try {
      const r = await savApi.mettreAuRebutEquipement(equipement.id, motifRebut.trim())
      setCurrent(r.data)
      setRebutOpen(false)
      setMotifRebut('')
      toast.success('Équipement mis au rebut')
      onSaved?.()
    } catch (err) {
      setError(frError(err.response?.data, 'Mise au rebut impossible.'))
    } finally { setRebutBusy(false) }
  }
  const reactiverRebut = async () => {
    setRebutBusy(true)
    try {
      const r = await savApi.reactiverRebutEquipement(equipement.id)
      setCurrent(r.data)
      toast.success('Équipement réactivé')
      onSaved?.()
    } catch (err) {
      setError(frError(err.response?.data, 'Réactivation impossible.'))
    } finally { setRebutBusy(false) }
  }

  return (
    <Sheet open onOpenChange={(o) => { if (!o && confirmLeaveIfDirty(dirty)) onClose() }}>
      <SheetContent side="right" className="w-[min(34rem,calc(100%-2rem))] sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Équipement — {equipement.produit_nom ?? ''}</SheetTitle>
          <SheetDescription>
            Numéro de série, pose et statut. La fin de garantie est recalculée
            automatiquement.
          </SheetDescription>
        </SheetHeader>

        {/* ZMFG12 — bannière de rebut, même patron que le bandeau ticket annulé. */}
        {current.mis_au_rebut && (
          <div role="alert"
               className="flex flex-wrap items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <span>
              <strong>Équipement mis au rebut.</strong>
              {current.motif_rebut ? ` Motif : ${current.motif_rebut}` : ''}
            </span>
            <Button size="sm" variant="outline" loading={rebutBusy} onClick={reactiverRebut}>
              Réactiver
            </Button>
          </div>
        )}

        <Form onSubmit={(e) => { e.preventDefault(); save() }} className="gap-5">
          <FormSection title="Identité">
            {/* L628 — produit/chantier readOnly par défaut, corrigeables sur action. */}
            {correcting ? (
              <>
                <FormField label="Produit" fullWidth>
                  <Select value={produit || '__none'}
                          onValueChange={(v) => setProduit(v === '__none' ? '' : v)}>
                    <SelectTrigger><SelectValue placeholder="— Produit —" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none">— Produit —</SelectItem>
                      {produits.map((p) => (
                        <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
                <FormField label="Chantier" fullWidth>
                  <Select value={installation || '__none'}
                          onValueChange={(v) => setInstallation(v === '__none' ? '' : v)}>
                    <SelectTrigger><SelectValue placeholder="— Chantier —" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none">— Chantier —</SelectItem>
                      {installations.map((i) => (
                        <SelectItem key={i.id} value={String(i.id)}>
                          {i.reference ?? `Chantier ${i.id}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormField>
              </>
            ) : (
              <>
                <FormField label="Produit">
                  <Input value={equipement.produit_nom ?? '—'} readOnly />
                </FormField>
                <FormField label="Marque">
                  <Input value={equipement.produit_marque ?? '—'} readOnly />
                </FormField>
                <FormField label="Chantier">
                  <Input value={equipement.installation_reference ?? '—'} readOnly />
                </FormField>
                <FormField label="Client">
                  <Input value={equipement.client_nom ?? '—'} readOnly />
                </FormField>
              </>
            )}
            <FormField label="Correction" fullWidth
                       hint="Corriger un produit ou un chantier saisi par erreur (recalcule la garantie).">
              <Button type="button" size="sm" variant={correcting ? 'default' : 'outline'}
                      onClick={() => setCorrecting((c) => !c)}>
                <Pencil /> {correcting ? 'Annuler la correction' : 'Corriger'}
              </Button>
            </FormField>
          </FormSection>

          {/* L624 — tickets SAV ouverts liés + L626 — créer un ticket pré-rempli. */}
          <FormSection title="Service après-vente">
            <FormField label="Tickets liés" fullWidth>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">
                  {nbTickets == null ? '—'
                    : `${nbTickets} ticket${nbTickets > 1 ? 's' : ''} SAV ouvert${nbTickets > 1 ? 's' : ''}`}
                </span>
                <Button type="button" size="sm" variant="outline"
                        loading={creatingTicket} onClick={creerTicket}>
                  <Wrench /> Créer un ticket SAV
                </Button>
              </div>
            </FormField>
            {/* L629 — équipement remplacé : lien vers le ticket de remplacement. */}
            {equipement.statut === 'remplace' && equipement.remplace_par_ticket && (
              <FormField label="Remplacement" fullWidth>
                <Button type="button" variant="link" className="h-auto p-0"
                        onClick={() => navigate('/sav')}>
                  Remplacé via ticket {equipement.remplace_par_ticket_reference ?? `#${equipement.remplace_par_ticket}`}
                </Button>
              </FormField>
            )}
          </FormSection>

          <FormSection title="Suivi">
            <FormField label="Numéro de série" fullWidth>
              <Input value={fields.numero_serie}
                     onChange={(e) => set('numero_serie', e.target.value)} />
            </FormField>
            <FormField label="Date de pose">
              <Input type="date" value={fields.date_pose ?? ''}
                     onChange={(e) => set('date_pose', e.target.value)} />
            </FormField>
            <FormField label="Statut">
              <Select value={fields.statut} onValueChange={(v) => set('statut', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EQUIP_STATUTS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormField>
            <FormField label="Note" fullWidth>
              <Textarea rows={2} value={fields.note ?? ''}
                        onChange={(e) => set('note', e.target.value)} />
            </FormField>
          </FormSection>

          <FormSection title="Garantie">
            <FormField label="État" fullWidth
                       hint="La date de fin de garantie est recalculée automatiquement à partir de la durée du produit et de la date de pose.">
              <div className="flex flex-wrap items-center gap-2">
                <GarantiePill eq={equipement} />
                {/* L633 — fin de garantie production en badge distinct labellisé. */}
                {equipement.date_fin_garantie_production && (
                  <StatusPill tone="neutral"
                              label={`Garantie production : ${formatDateFR(equipement.date_fin_garantie_production)}`} />
                )}
              </div>
            </FormField>
          </FormSection>

          {error && (
            <div role="alert"
                 className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
              <span className="break-words">{error}</span>
            </div>
          )}

          {/* L632 — qui/quand : ajout & dernière modification. */}
          <p className="text-xs text-muted-foreground">
            Ajouté le {formatDateFR((equipement.date_creation ?? '').slice(0, 10))}
            {equipement.created_by_nom ? ` par ${equipement.created_by_nom}` : ''}
            {' · '}modifié le {formatDateFR((equipement.date_modification ?? '').slice(0, 10))}
          </p>

          <FormActions sticky={false}>
            {!current.mis_au_rebut && (
              <Button type="button" variant="destructive" className="mr-auto"
                      onClick={() => setRebutOpen(true)}>
                <Trash2 /> Mettre au rebut
              </Button>
            )}
            <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
            <Button type="submit" loading={saving}><Save /> Mettre à jour</Button>
          </FormActions>
        </Form>

        {/* XSAV15/16/17 — fiabilité, disponibilité, immobilisation, relevés compteur. */}
        <CollapsibleSection icon={Activity} title="Fiabilité & maintenance">
          <EquipementFiabilitePanel equipementId={equipement.id} />
        </CollapsibleSection>

        <AlertDialog open={rebutOpen} onOpenChange={setRebutOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Mettre cet équipement au rebut ?</AlertDialogTitle>
              <AlertDialogDescription>
                Motif obligatoire — l'équipement sortira du parc actif et des
                générations de visites préventives. Cette action est réservée
                responsable/admin.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="grid gap-1.5">
              <label htmlFor="motif-rebut" className="text-sm font-medium">Motif</label>
              <Textarea id="motif-rebut" rows={2} value={motifRebut}
                        onChange={(e) => setMotifRebut(e.target.value)} />
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <AlertDialogAction disabled={!motifRebut.trim() || rebutBusy}
                                  onClick={(e) => { e.preventDefault(); mettreAuRebut() }}>
                Confirmer la mise au rebut
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </SheetContent>
    </Sheet>
  )
}

export default function EquipementsPage() {
  const dispatch = useDispatch()
  const { items, loading, error } = useSelector((s) => s.equipements)
  const [filters, setFilters] = useState(EMPTY_EQUIP_FILTERS)
  const [selected, setSelected] = useState(null)
  // WR11/FG290 — registre des garanties par parc (échéancier).
  const [showRegistre, setShowRegistre] = useState(false)
  // VX172 — pending visible sur « Exporter Excel » (VX49 pose déjà le toast
  // d'erreur ; ceci ajoute juste l'état chargement manquant).
  const [xlsxBusy, setXlsxBusy] = useState(false)
  // VX109 — import Excel/CSV du parc d'équipements.
  const [showImport, setShowImport] = useState(false)

  const reload = () => dispatch(fetchEquipements())
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const produitOptions = useMemo(() => {
    const seen = new Map()
    for (const it of items) if (it.produit && !seen.has(it.produit)) seen.set(it.produit, it.produit_nom)
    return [...seen.entries()].map(([id, nom]) => ({ id, nom: nom ?? `#${id}` }))
  }, [items])

  const marqueOptions = useMemo(
    () => [...new Set(items.map((it) => it.produit_marque).filter(Boolean))].sort(),
    [items])

  const rows = useMemo(
    () => sortEquipements(filterEquipements(items, filters), 'date_fin_garantie', 'asc'),
    [items, filters])

  // L623/L631 — comptes par état de garantie sur tout le parc (KPI + synthèse).
  const garantieCounts = useMemo(() => {
    const c = { sous_garantie: 0, expire_bientot: 0, hors_garantie: 0, non_renseignee: 0 }
    for (const it of items) {
      const k = it.garantie_etat ?? 'non_renseignee'
      if (k in c) c[k] += 1
    }
    return c
  }, [items])

  const expirantBientot = filters.garantie === 'expire_bientot'
  const hasFilters = filters.q || filters.produit || filters.marque || filters.garantie || filters.statut

  // L625 — clic sur un badge de ligne : pose le filtre garantie à cet état.
  const filterByGarantie = (etat) => setF('garantie', filters.garantie === etat ? '' : etat)

  const columns = useMemo(() => [
    {
      id: 'numero_serie',
      header: 'Série',
      width: 150,
      accessor: (r) => r.numero_serie ?? '—',
      cell: (v) => <span className="font-medium">{v}</span>,
    },
    { id: 'produit_nom', header: 'Produit', width: 200, accessor: (r) => r.produit_nom ?? '—' },
    { id: 'produit_marque', header: 'Marque', width: 130, accessor: (r) => r.produit_marque ?? '—' },
    { id: 'installation_reference', header: 'Chantier', width: 140, accessor: (r) => r.installation_reference ?? '—' },
    { id: 'client_nom', header: 'Client', width: 160, accessor: (r) => r.client_nom ?? '—' },
    {
      id: 'statut',
      header: 'Statut',
      width: 120,
      searchable: false,
      accessor: (r) => EQUIP_STATUT_LABELS[r.statut] ?? r.statut,
    },
    {
      // L635 — colonne « Posé le » triable (ordering backend inclut date_pose).
      id: 'date_pose',
      header: 'Posé le',
      width: 120,
      searchable: false,
      accessor: (r) => r.date_pose ?? '',
      cell: (_v, row) => formatDateFR(row.date_pose),
      exportValue: (row) => formatDateFR(row.date_pose),
    },
    {
      id: 'date_fin_garantie',
      header: 'Garantie',
      width: 240,
      searchable: false,
      // L625 — le badge est cliquable et filtre la table à cet état de garantie.
      cell: (_v, row) => (
        <button type="button" title="Filtrer par cet état de garantie"
                onClick={(e) => { e.stopPropagation(); filterByGarantie(row.garantie_etat ?? 'non_renseignee') }}
                className="cursor-pointer rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <GarantiePill eq={row} />
        </button>
      ),
      exportValue: (row) => garantieLabel(row),
    },
  ], [filters.garantie]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root flex flex-col gap-5 p-1">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-2xl font-bold tracking-tight">Parc d'équipements</h1>
            <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span>{rows.length} équipement{rows.length > 1 ? 's' : ''}</span>
              {/* L623 — puce KPI « Expirant bientôt » : compte + filtre rapide. */}
              {garantieCounts.expire_bientot > 0 && (
                <button type="button"
                        onClick={() => setF('garantie', expirantBientot ? '' : 'expire_bientot')}
                        className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors ${
                          expirantBientot ? 'border-amber-500 bg-amber-500/10 text-amber-700' : 'border-border bg-card'}`}>
                  <AlarmClock className="size-3.5" aria-hidden="true" />
                  {garantieCounts.expire_bientot} expirant bientôt
                </button>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* WR11/FG290 — échéancier des garanties par parc. */}
            <Button variant="outline" size="sm" onClick={() => setShowRegistre(true)}>
              <ShieldCheck /> Registre des garanties
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowImport(true)}>
              <Upload /> Importer
            </Button>
            <Button variant="outline" size="sm" disabled={xlsxBusy}
                    onClick={() => {
                      const pending = downloadBlobInGesture()
                      setXlsxBusy(true)
                      importApi.exportList('equipements', rows.map((r) => r.id))
                        .then((r) => pending.deliver(r.data, 'equipements.xlsx'))
                        .catch(() => {})
                        .finally(() => setXlsxBusy(false))
                    }}>
              {xlsxBusy ? <Spinner /> : <Download />} Exporter Excel
            </Button>
          </div>
        </header>

        {showImport && (
          <ExcelImport target="equipements" onClose={() => setShowImport(false)}
                       onDone={reload} />
        )}

        {/* ── Filtres ── */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[220px] flex-1">
            <Input placeholder="Rechercher (série, produit, chantier, client)…"
                   value={filters.q} onChange={(e) => setF('q', e.target.value)} />
          </div>
          <Select value={filters.produit || '__all'}
                  onValueChange={(v) => setF('produit', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[160px]"><SelectValue placeholder="Tous les produits" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous les produits</SelectItem>
              {produitOptions.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.marque || '__all'}
                  onValueChange={(v) => setF('marque', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[150px]"><SelectValue placeholder="Toutes les marques" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Toutes les marques</SelectItem>
              {marqueOptions.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.garantie || '__all'}
                  onValueChange={(v) => setF('garantie', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[170px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {GARANTIE_FILTRES.map((g) => (
                <SelectItem key={g.value || '__all'} value={g.value || '__all'}>{g.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {/* L627 — filtre statut (en_service / remplacé / hors_service). */}
          <Select value={filters.statut || '__all'}
                  onValueChange={(v) => setF('statut', v === '__all' ? '' : v)}>
            <SelectTrigger className="w-auto min-w-[150px]"><SelectValue placeholder="Tous statuts" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous statuts</SelectItem>
              {EQUIP_STATUTS.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {hasFilters && (
            <Button size="sm" variant="ghost" onClick={() => setFilters(EMPTY_EQUIP_FILTERS)}>
              <RotateCcw /> Réinitialiser
            </Button>
          )}
        </div>

        {/* L631 — barre de synthèse d'état de garantie (compte par état, alignée
            sur la légende GARANTIE_ETATS) ; chaque carte filtre la table. */}
        {!loading && !error && items.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {Object.entries(GARANTIE_ETATS).map(([k, v]) => (
              <button key={k} type="button"
                      onClick={() => setF('garantie', filters.garantie === k ? '' : k)}
                      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                        filters.garantie === k ? 'border-primary bg-primary/10' : 'border-border bg-card'}`}>
                <span aria-hidden="true" className="inline-block size-2.5 rounded-sm"
                      style={{ background: v.color }} />
                {v.label}
                <span className="font-semibold">{garantieCounts[k] ?? 0}</span>
              </button>
            ))}
          </div>
        )}

        {loading ? (
          <Card className="space-y-2 p-4">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </Card>
        ) : error ? (
          <EmptyState
            icon={AlertTriangle}
            title="Chargement impossible"
            description="Le parc d'équipements n'a pas pu être chargé. Réessayez."
            action={<Button size="sm" variant="outline" onClick={reload}><RotateCcw /> Réessayer</Button>}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={PackageSearch}
            title="Aucun équipement"
            description={hasFilters
              ? 'Aucun équipement ne correspond à vos filtres.'
              : "Aucun équipement. Ajoutez-en depuis la fiche d'un chantier."}
            action={hasFilters
              ? <Button size="sm" variant="outline" onClick={() => setFilters(EMPTY_EQUIP_FILTERS)}><RotateCcw /> Réinitialiser</Button>
              : undefined}
          />
        ) : (
          <DataTable
            data={rows}
            columns={columns}
            getRowId={(row) => row.id}
            searchable={false}
            onRowClick={(row) => setSelected(row)}
            exportName="equipements"
            emptyTitle="Aucun équipement"
            emptyDescription="Aucun équipement ne correspond à votre recherche."
          />
        )}

        {selected && (
          <EquipementDetail equipement={selected} onClose={() => setSelected(null)}
                            onSaved={reload} />
        )}

        {showRegistre && (
          <RegistreGarantiesDialog onClose={() => setShowRegistre(false)} />
        )}
      </div>
    </TooltipProvider>
  )
}
