/* ============================================================================
   PACT61 — Paramétrage des kits d'assemblage : nomenclature, gamme, contrôle
   qualité.
   ----------------------------------------------------------------------------
   Trou (a) élargi au kit lui-même : l'écran Atelier existant ne fait que
   SÉLECTIONNER un kit déjà créé — aucun écran ne crée le kit (pas même de
   wrapper `create`), sa nomenclature, sa gamme d'étapes ni son modèle de
   contrôle qualité. L'Atelier suppose donc en amont une capacité qui
   n'existe pas.
   ========================================================================== */
import { useCallback, useEffect, useState } from 'react'
import { PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'

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

// ── Créer un kit ─────────────────────────────────────────────────────────────
function CreateKitDialog({ produits, onClose, onCreated }) {
  const [nom, setNom] = useState('')
  const [referenceInterne, setReferenceInterne] = useState('')
  const [produitCompose, setProduitCompose] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!nom.trim()) { setError('Le nom du kit est obligatoire.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createKit({
        nom: nom.trim(), reference_interne: referenceInterne || undefined,
        produit_compose: produitCompose ? Number(produitCompose) : null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.nom?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau kit</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="kit-nom">Nom</label>
        <input id="kit-nom" type="text" className="form-control" value={nom} onChange={(e) => setNom(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="kit-ref">Référence interne (optionnel)</label>
        <input id="kit-ref" type="text" className="form-control" value={referenceInterne} onChange={(e) => setReferenceInterne(e.target.value)} />
        <label className="form-label" htmlFor="kit-produit">Article composite (optionnel)</label>
        <select id="kit-produit" className="form-control" value={produitCompose} onChange={(e) => setProduitCompose(e.target.value)}>
          <option value="">—</option>
          {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
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

// ── Onglet Nomenclature ──────────────────────────────────────────────────────
function CreateComposantDialog({ kitId, produits, onClose, onCreated }) {
  const [produit, setProduit] = useState('')
  const [designation, setDesignation] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!produit && !designation.trim()) {
      setError('Indiquez un produit ou une désignation.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createKitComposant({
        kit: kitId, produit: produit ? Number(produit) : null,
        designation: produit ? undefined : designation.trim(), quantite,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau composant</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="kc-produit">Produit (catalogue, optionnel)</label>
        <select id="kc-produit" className="form-control" value={produit} onChange={(e) => setProduit(e.target.value)} autoFocus>
          <option value="">—</option>
          {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
        <label className="form-label" htmlFor="kc-designation">Ou désignation libre</label>
        <input id="kc-designation" type="text" className="form-control" value={designation} onChange={(e) => setDesignation(e.target.value)} disabled={!!produit} />
        <label className="form-label" htmlFor="kc-quantite">Quantité</label>
        <input id="kc-quantite" type="number" step="any" className="form-control" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
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

function NomenclatureTab({ kitId, produits }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getKitComposants, { kit: kitId })
  const [showCreate, setShowCreate] = useState(false)
  const del = async (id) => {
    if (!window.confirm('Retirer ce composant de la nomenclature ?')) return
    await installationsApi.deleteKitComposant(id).catch(() => {})
    reload()
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouveau composant
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Nomenclature vide">
        {rows.length > 0 && rows.map((c) => (
          <div key={c.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`composant-${c.id}`}>
            <span className="font-medium text-sm">{c.produit_nom || c.designation}</span>
            <span className="text-sm text-muted-foreground">Qté {c.quantite}</span>
            {c.taux_perte_pct != null && c.taux_perte_pct !== '' && (
              <span className="text-xs text-muted-foreground">Perte {c.taux_perte_pct}%</span>
            )}
            <Button size="sm" variant="outline" className="ml-auto text-destructive hover:text-destructive"
              onClick={() => del(c.id)}>
              Retirer
            </Button>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateComposantDialog kitId={kitId} produits={produits}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Gamme d'étapes ────────────────────────────────────────────────────
function CreateEtapeDialog({ kitId, ordreSuivant, onClose, onCreated }) {
  const [libelle, setLibelle] = useState('')
  const [instructions, setInstructions] = useState('')
  const [dureeAttendue, setDureeAttendue] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!libelle.trim()) { setError("Le libellé de l'étape est requis."); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createEtapeAssemblageKit({
        kit: kitId, ordre: ordreSuivant, libelle: libelle.trim(),
        instructions: instructions || undefined,
        duree_attendue_min: dureeAttendue || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle étape</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="ea-libelle">Libellé</label>
        <input id="ea-libelle" type="text" className="form-control" value={libelle} onChange={(e) => setLibelle(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="ea-instructions">Instructions (optionnel)</label>
        <textarea id="ea-instructions" className="form-control" rows={2} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
        <label className="form-label" htmlFor="ea-duree">Durée attendue (minutes, optionnel)</label>
        <input id="ea-duree" type="number" className="form-control" value={dureeAttendue} onChange={(e) => setDureeAttendue(e.target.value)} />
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

function GammeTab({ kitId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getEtapesAssemblageKit, { kit: kitId })
  const [showCreate, setShowCreate] = useState(false)
  const del = async (id) => {
    if (!window.confirm("Retirer cette étape de la gamme ?")) return
    await installationsApi.deleteEtapeAssemblageKit(id).catch(() => {})
    reload()
  }
  const sorted = [...rows].sort((a, b) => (a.ordre ?? 0) - (b.ordre ?? 0))
  const ordreSuivant = sorted.length > 0
    ? Math.max(...sorted.map((e) => e.ordre ?? 0)) + 1 : 1
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle étape
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune étape définie">
        {sorted.length > 0 && sorted.map((e) => (
          <div key={e.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`etape-${e.id}`}>
            <Badge tone="neutral">#{e.ordre}</Badge>
            <span className="font-medium text-sm">{e.libelle}</span>
            {e.duree_attendue_min != null && (
              <span className="text-xs text-muted-foreground">{e.duree_attendue_min} min</span>
            )}
            <Button size="sm" variant="outline" className="ml-auto text-destructive hover:text-destructive"
              onClick={() => del(e.id)}>
              Retirer
            </Button>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateEtapeDialog kitId={kitId} ordreSuivant={ordreSuivant}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Contrôle qualité ──────────────────────────────────────────────────
function ControleQualiteTab({ kitId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getControleQualiteModeles, { kit: kitId })
  const [busy, setBusy] = useState(false)
  const modele = rows[0] || null

  const activer = async () => {
    setBusy(true)
    try {
      if (modele) {
        await installationsApi.updateControleQualiteModele(modele.id, { active: true })
      } else {
        await installationsApi.createControleQualiteModele({ kit: kitId, active: true })
      }
      reload()
    } catch { /* affiché nulle part : réessai possible depuis le bouton */ }
    finally { setBusy(false) }
  }
  const desactiver = async () => {
    setBusy(true)
    await installationsApi.updateControleQualiteModele(modele.id, { active: false }).catch(() => {})
    setBusy(false); reload()
  }

  return (
    <div className="flex flex-col gap-3">
      <ListShell loading={loading} error={error} empty="Aucun modèle de contrôle qualité configuré">
        {modele != null && (
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`controle-qualite-${modele.id}`}>
            <span className="text-sm">Modèle de contrôle qualité</span>
            <Badge tone={modele.active ? 'success' : 'neutral'}>
              {modele.active ? 'Actif' : 'Inactif'}
            </Badge>
            <span className="text-xs text-muted-foreground ml-auto">
              {(modele.items || []).length} item(s) de checklist
            </span>
          </div>
        )}
      </ListShell>
      <div className="flex justify-end gap-2">
        {modele == null ? (
          <Button size="sm" disabled={busy} onClick={activer}>
            <PlusCircle className="size-4" aria-hidden="true" /> Configurer un modèle de contrôle
          </Button>
        ) : modele.active ? (
          <Button size="sm" variant="outline" disabled={busy} onClick={desactiver}>Désactiver</Button>
        ) : (
          <Button size="sm" variant="outline" disabled={busy} onClick={activer}>Réactiver</Button>
        )}
      </div>
    </div>
  )
}

function KitFiche({ kit, produits }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{kit.nom}</h2>
        {kit.reference_interne && <span className="text-sm text-muted-foreground">{kit.reference_interne}</span>}
        <Badge tone={kit.active ? 'success' : 'neutral'}>{kit.active ? 'Actif' : 'Inactif'}</Badge>
      </div>
      <Tabs defaultValue="nomenclature" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="nomenclature">Nomenclature</TabsTrigger>
          <TabsTrigger value="gamme">Gamme d'étapes</TabsTrigger>
          <TabsTrigger value="qualite">Contrôle qualité</TabsTrigger>
        </TabsList>
        <TabsContent value="nomenclature">
          <NomenclatureTab kitId={kit.id} produits={produits} />
        </TabsContent>
        <TabsContent value="gamme">
          <GammeTab kitId={kit.id} />
        </TabsContent>
        <TabsContent value="qualite">
          <ControleQualiteTab kitId={kit.id} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default function ParametrageKits() {
  const [kits, setKits] = useState([])
  const [loadingKits, setLoadingKits] = useState(true)
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [produits, setProduits] = useState([])

  const loadKits = useCallback(() => {
    setLoadingKits(true)
    installationsApi.getKitsAssemblage({ page_size: 200 })
      .then((res) => {
        const rows = unwrap(res)
        setKits(rows)
        setSelected((cur) => (cur != null && rows.some((r) => r.id === cur))
          ? cur : (rows[0]?.id ?? null))
      })
      .catch(() => {})
      .finally(() => setLoadingKits(false))
  }, [])

  useEffect(() => { loadKits() }, [loadKits])
  useEffect(() => {
    let alive = true
    stockApi.getProduits({ page_size: 200 }).then((res) => {
      if (alive) setProduits(unwrap(res))
    }).catch(() => {})
    return () => { alive = false }
  }, [])

  const current = kits.find((k) => k.id === selected) || null

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Paramétrage des kits d'assemblage"
        subtitle="Créez un kit, sa nomenclature, sa gamme d'étapes et son modèle de contrôle qualité — l'Atelier les consomme ensuite."
      />
      <div className="flex flex-col gap-4 md:flex-row">
        <aside className="w-full md:w-72 flex-shrink-0 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Kits</h3>
            <Button size="sm" variant="outline" aria-label="Nouveau kit" onClick={() => setShowCreate(true)}>
              <PlusCircle className="size-4" aria-hidden="true" />
            </Button>
          </div>
          {loadingKits ? (
            <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner className="size-4 text-primary" /> Chargement…
            </p>
          ) : kits.length === 0 ? (
            <EmptyState title="Aucun kit" description="Créez le premier kit d'assemblage." className="py-4" />
          ) : (
            <ul className="flex flex-col gap-1" data-testid="liste-kits">
              {kits.map((k) => (
                <li key={k.id}>
                  <button type="button"
                    data-testid={`kit-${k.id}`}
                    className={`w-full text-left rounded-lg border px-3 py-2 text-sm ${selected === k.id ? 'border-primary bg-primary/5' : 'border-border'}`}
                    onClick={() => setSelected(k.id)}>
                    <span className="font-medium block">{k.nom}</span>
                    {k.reference_interne && <span className="text-xs text-muted-foreground">{k.reference_interne}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
        <div className="flex-1 min-w-0">
          {!current ? (
            <EmptyState title="Sélectionnez un kit"
              description="Choisissez un kit dans la liste, ou créez-en un nouveau."
              className="py-10" />
          ) : (
            <KitFiche kit={current} produits={produits} />
          )}
        </div>
      </div>
      {showCreate && (
        <CreateKitDialog produits={produits}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); loadKits() }} />
      )}
    </div>
  )
}
