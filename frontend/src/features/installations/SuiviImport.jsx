/* ============================================================================
   PACT56 — Import et douane : dossiers, frais, coût débarqué.
   ----------------------------------------------------------------------------
   Trou (a) : `DossierImport` (incoterm, connaissement, conteneur, statut
   douanier), `FraisImport` et `LandedCostLigne` existent côté serveur
   (FG315/FG316) sans aucune trace côté frontend. Donnée INTERNE, jamais
   montrée au client.
   ========================================================================== */
import { useCallback, useEffect, useState } from 'react'
import { PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, IconButton, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate, formatMAD } from '../../lib/format'
import installationsApi from '../../api/installationsApi'

const INCOTERMS = [
  ['exw', "EXW — À l'usine"], ['fob', 'FOB — Franco à bord'],
  ['cfr', 'CFR — Coût et fret'], ['cif', 'CIF — Coût, assurance, fret'],
  ['dap', 'DAP — Rendu au lieu'], ['ddp', 'DDP — Rendu droits acquittés'],
]
const STATUT_DOUANE_ORDER = [
  ['commande', 'Commandé'], ['expedie', 'Expédié'],
  ['arrive_port', 'Arrivé au port'], ['en_douane', 'En cours de dédouanement'],
  ['dedouane', 'Dédouané'], ['livre', 'Livré'],
]
const STATUT_DOUANE_LABEL = Object.fromEntries(STATUT_DOUANE_ORDER)
const CATEGORIES_FRAIS = [
  ['fret', 'Fret maritime / aérien'], ['douane', 'Droits de douane'],
  ['tva_import', "TVA à l'import"], ['transit', 'Transit / transport interne'],
  ['manutention', 'Manutention / magasinage'], ['assurance', 'Assurance'],
  ['autre', 'Autre frais'],
]

function unwrap(res) {
  const p = res?.data
  return Array.isArray(p) ? p : (p?.results ?? [])
}

function useFilteredList(fetcher, params) {
  const key = JSON.stringify(params)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    let cancelled = false
    setLoading(true); setError(null)
    fetcher(params)
      .then((res) => { if (!cancelled) setRows(unwrap(res)) })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage/changement de filtre
  useEffect(() => load(), [load])
  return { rows, loading, error, reload: load }
}

function ListShell({ loading, error, empty, children }) {
  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (error) return <EmptyState title="Impossible de charger" description={error} className="py-6" />
  if (!children) return <EmptyState title={empty} className="py-6" />
  return children
}

// ── Créer un dossier d'import ───────────────────────────────────────────────
function CreateDossierDialog({ onClose, onCreated }) {
  const [designation, setDesignation] = useState('')
  const [incoterm, setIncoterm] = useState('')
  const [numeroBl, setNumeroBl] = useState('')
  const [numeroConteneur, setNumeroConteneur] = useState('')
  const [portArrivee, setPortArrivee] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!designation.trim()) { setError('La désignation est obligatoire.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createDossierImport({
        designation: designation.trim(), incoterm: incoterm || null,
        numero_bl: numeroBl || undefined, numero_conteneur: numeroConteneur || undefined,
        port_arrivee: portArrivee || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.designation?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau dossier d'import</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="di-designation">Désignation</label>
        <input id="di-designation" type="text" className="form-control" value={designation} onChange={(e) => setDesignation(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="di-incoterm">Incoterm (optionnel)</label>
        <select id="di-incoterm" className="form-control" value={incoterm} onChange={(e) => setIncoterm(e.target.value)}>
          <option value="">—</option>
          {INCOTERMS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="form-label" htmlFor="di-bl">N° connaissement / BL (optionnel)</label>
        <input id="di-bl" type="text" className="form-control" value={numeroBl} onChange={(e) => setNumeroBl(e.target.value)} />
        <label className="form-label" htmlFor="di-conteneur">N° conteneur (optionnel)</label>
        <input id="di-conteneur" type="text" className="form-control" value={numeroConteneur} onChange={(e) => setNumeroConteneur(e.target.value)} />
        <label className="form-label" htmlFor="di-port">Port d'arrivée (optionnel)</label>
        <input id="di-port" type="text" className="form-control" value={portArrivee} onChange={(e) => setPortArrivee(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

// ── Onglet Frais ─────────────────────────────────────────────────────────────
function CreateFraisDialog({ dossierId, onClose, onCreated }) {
  const [categorie, setCategorie] = useState('fret')
  const [libelle, setLibelle] = useState('')
  const [montant, setMontant] = useState('')
  const [dateFrais, setDateFrais] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!montant) { setError('Le montant est requis.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createFraisImport({
        dossier: dossierId, categorie, libelle: libelle || undefined,
        montant, date_frais: dateFrais || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.montant?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau frais d'import</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="fi-categorie">Catégorie</label>
        <select id="fi-categorie" className="form-control" value={categorie} onChange={(e) => setCategorie(e.target.value)} autoFocus>
          {CATEGORIES_FRAIS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="form-label" htmlFor="fi-libelle">Libellé (optionnel)</label>
        <input id="fi-libelle" type="text" className="form-control" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
        <label className="form-label" htmlFor="fi-montant">Montant (MAD)</label>
        <input id="fi-montant" type="number" step="any" className="form-control" value={montant} onChange={(e) => setMontant(e.target.value)} />
        <label className="form-label" htmlFor="fi-date">Date (optionnel)</label>
        <input id="fi-date" type="date" className="form-control" value={dateFrais} onChange={(e) => setDateFrais(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function FraisTab({ dossierId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getFraisImport, { dossier: dossierId })
  const [showCreate, setShowCreate] = useState(false)
  const total = rows.reduce((sum, f) => sum + Number(f.montant || 0), 0)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Total des frais : <strong>{formatMAD(total)}</strong></span>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouveau frais
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucun frais saisi">
        {rows.length > 0 && rows.map((f) => (
          <div key={f.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`frais-${f.id}`}>
            <Badge tone="neutral">{f.categorie_display || f.categorie}</Badge>
            <span className="text-sm">{f.libelle}</span>
            <span className="text-sm font-medium ml-auto">{formatMAD(f.montant)}</span>
            <span className="text-xs text-muted-foreground">{formatDate(f.date_frais)}</span>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateFraisDialog dossierId={dossierId}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Coût débarqué ─────────────────────────────────────────────────────
function CreateLandedLigneDialog({ dossierId, onClose, onCreated }) {
  const [designation, setDesignation] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [valeurFob, setValeurFob] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!designation.trim()) { setError('La désignation est requise.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createLandedCostLigne({
        dossier: dossierId, designation: designation.trim(),
        quantite, valeur_fob: valeurFob || 0,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.designation?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle ligne SKU</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="lc-designation">Désignation</label>
        <input id="lc-designation" type="text" className="form-control" value={designation} onChange={(e) => setDesignation(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="lc-quantite">Quantité</label>
        <input id="lc-quantite" type="number" step="any" className="form-control" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
        <label className="form-label" htmlFor="lc-fob">Valeur FOB (MAD)</label>
        <input id="lc-fob" type="number" step="any" className="form-control" value={valeurFob} onChange={(e) => setValeurFob(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function CoutDebarqueTab({ dossierId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getLandedCostLignes, { dossier: dossierId })
  const [showCreate, setShowCreate] = useState(false)
  const [calcul, setCalcul] = useState(null)
  const [calculBusy, setCalculBusy] = useState(false)

  const calculer = async () => {
    setCalculBusy(true)
    try {
      const res = await installationsApi.getLandedCostDossier(dossierId)
      setCalcul(res?.data ?? null)
    } catch { /* affiché nulle part : le bouton reste disponible pour réessayer */ }
    finally { setCalculBusy(false) }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="outline" loading={calculBusy} disabled={calculBusy} onClick={calculer}>
          Calculer le coût débarqué
        </Button>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle ligne SKU
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune ligne SKU">
        {rows.length > 0 && rows.map((l) => {
          const detail = calcul?.lignes?.find((d) => d.ligne_id === l.id)
          return (
            <div key={l.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`landed-ligne-${l.id}`}>
              <span className="font-medium text-sm">{l.produit_nom || l.designation}</span>
              <span className="text-xs text-muted-foreground">Qté {l.quantite}</span>
              <span className="text-sm">FOB {formatMAD(l.valeur_fob)}</span>
              {detail && (
                <>
                  <span className="text-sm text-muted-foreground">
                    Quote-part frais : {formatMAD(detail.quote_part_frais)}
                  </span>
                  <span className="text-sm font-medium ml-auto">
                    Débarqué : {formatMAD(detail.cout_debarque_total)}
                    {' '}({formatMAD(detail.cout_debarque_unitaire)}/u)
                  </span>
                </>
              )}
            </div>
          )
        })}
      </ListShell>
      {calcul && (
        <p className="text-sm text-muted-foreground" data-testid="landed-totaux">
          Total FOB {formatMAD(calcul.total_fob)} · Total frais {formatMAD(calcul.total_frais)}
          {' '}· Total débarqué {formatMAD(calcul.total_landed)}
        </p>
      )}
      {showCreate && (
        <CreateLandedLigneDialog dossierId={dossierId}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Fiche dossier (onglets) ──────────────────────────────────────────────────
function DossierFiche({ dossier, onAdvanced }) {
  const [busy, setBusy] = useState(false)
  const idx = STATUT_DOUANE_ORDER.findIndex(([v]) => v === dossier.statut_douane)
  const dernier = idx === STATUT_DOUANE_ORDER.length - 1
  const avancer = async () => {
    setBusy(true)
    await installationsApi.avancerDossierImport(dossier.id).catch(() => {})
    setBusy(false); onAdvanced?.()
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{dossier.designation}</h2>
        <span className="text-sm text-muted-foreground">{dossier.reference}</span>
        <Badge tone="info">
          {dossier.statut_douane_display || STATUT_DOUANE_LABEL[dossier.statut_douane]}
        </Badge>
        {!dernier && (
          <Button size="sm" variant="outline" loading={busy} disabled={busy} onClick={avancer}>
            Faire avancer
          </Button>
        )}
      </div>
      <Tabs defaultValue="frais" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="frais">Frais</TabsTrigger>
          <TabsTrigger value="cout">Coût débarqué</TabsTrigger>
        </TabsList>
        <TabsContent value="frais">
          <FraisTab dossierId={dossier.id} />
        </TabsContent>
        <TabsContent value="cout">
          <CoutDebarqueTab dossierId={dossier.id} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default function SuiviImport() {
  const [dossiers, setDossiers] = useState([])
  const [loadingList, setLoadingList] = useState(true)
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const loadDossiers = useCallback(() => {
    setLoadingList(true)
    installationsApi.getDossiersImport({ page_size: 200 })
      .then((res) => {
        const rows = unwrap(res)
        setDossiers(rows)
        setSelected((cur) => (cur != null && rows.some((r) => r.id === cur))
          ? cur : (rows[0]?.id ?? null))
      })
      .catch(() => {})
      .finally(() => setLoadingList(false))
  }, [])

  useEffect(() => { loadDossiers() }, [loadDossiers])

  const current = dossiers.find((d) => d.id === selected) || null

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Import et douane"
        subtitle="Dossiers d'import, frais et coût de revient débarqué — donnée interne, jamais client-facing."
      />
      <div className="flex flex-col gap-4 md:flex-row">
        <aside className="w-full md:w-72 flex-shrink-0 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Dossiers d'import</h3>
            <IconButton size="md" variant="outline" label="Nouveau dossier" onClick={() => setShowCreate(true)}>
              <PlusCircle className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
          {loadingList ? (
            <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner className="size-4 text-primary" /> Chargement…
            </p>
          ) : dossiers.length === 0 ? (
            <EmptyState title="Aucun dossier d'import" description="Créez le premier dossier suivi." className="py-4" />
          ) : (
            <ul className="flex flex-col gap-1" data-testid="liste-dossiers-import">
              {dossiers.map((d) => (
                <li key={d.id}>
                  <button type="button"
                    data-testid={`dossier-import-${d.id}`}
                    className={`w-full text-left rounded-lg border px-3 py-2 text-sm ${selected === d.id ? 'border-primary bg-primary/5' : 'border-border'}`}
                    onClick={() => setSelected(d.id)}>
                    <span className="font-medium block">{d.designation}</span>
                    <span className="text-xs text-muted-foreground">
                      {d.statut_douane_display || STATUT_DOUANE_LABEL[d.statut_douane]}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
        <div className="flex-1 min-w-0">
          {!current ? (
            <EmptyState title="Sélectionnez un dossier"
              description="Choisissez un dossier d'import dans la liste, ou créez-en un nouveau."
              className="py-10" />
          ) : (
            <DossierFiche dossier={current} onAdvanced={loadDossiers} />
          )}
        </div>
      </div>
      {showCreate && (
        <CreateDossierDialog
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); loadDossiers() }} />
      )}
    </div>
  )
}
