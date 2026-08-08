/* ============================================================================
   PACT57 — Prix négociés fournisseurs : commandes-cadres et contrats de prix.
   ----------------------------------------------------------------------------
   Trou (a) élargi aux en-têtes : l'écran Approvisionnement existant affiche
   déjà ces documents en LECTURE SEULE (WIR110). Aucun écran ne permettait de
   CRÉER ou MODIFIER une commande-cadre, un contrat de prix, ni leurs lignes de
   prix négocié — cet écran est cette capacité d'écriture.
   ========================================================================== */
import { useCallback, useEffect, useState } from 'react'
import { PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate, formatMAD } from '../../lib/format'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'

const STATUT_TONE = { brouillon: 'neutral', actif: 'success', clos: 'neutral', expire: 'danger' }

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

// ── Créer une commande-cadre ────────────────────────────────────────────────
function CreateCommandeCadreDialog({ fournisseurs, onClose, onCreated }) {
  const [intitule, setIntitule] = useState('')
  const [fournisseur, setFournisseur] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!intitule.trim() || !fournisseur) {
      setError('Intitulé et fournisseur sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createCommandeCadre({
        intitule: intitule.trim(), fournisseur: Number(fournisseur),
        date_debut: dateDebut || null, date_fin: dateFin || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle commande-cadre</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="cc-intitule">Intitulé</label>
        <input id="cc-intitule" type="text" className="form-control" value={intitule} onChange={(e) => setIntitule(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="cc-fournisseur">Fournisseur</label>
        <select id="cc-fournisseur" className="form-control" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)}>
          <option value="">— Choisir —</option>
          {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
        </select>
        <label className="form-label" htmlFor="cc-debut">Date de début (optionnel)</label>
        <input id="cc-debut" type="date" className="form-control" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
        <label className="form-label" htmlFor="cc-fin">Date de fin (optionnel)</label>
        <input id="cc-fin" type="date" className="form-control" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
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

function CreateCommandeCadreLigneDialog({ commandeCadreId, onClose, onCreated }) {
  const [designation, setDesignation] = useState('')
  const [prixNegocie, setPrixNegocie] = useState('')
  const [volumeEngage, setVolumeEngage] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!designation.trim() || !prixNegocie) {
      setError('Désignation et prix négocié sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createCommandeCadreLigne({
        commande_cadre: commandeCadreId, designation: designation.trim(),
        prix_negocie: prixNegocie, volume_engage: volumeEngage || 0,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle ligne de prix</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="ccl-designation">Désignation</label>
        <input id="ccl-designation" type="text" className="form-control" value={designation} onChange={(e) => setDesignation(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="ccl-prix">Prix négocié (MAD)</label>
        <input id="ccl-prix" type="number" step="any" className="form-control" value={prixNegocie} onChange={(e) => setPrixNegocie(e.target.value)} />
        <label className="form-label" htmlFor="ccl-volume">Volume engagé</label>
        <input id="ccl-volume" type="number" step="any" className="form-control" value={volumeEngage} onChange={(e) => setVolumeEngage(e.target.value)} />
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

function CommandeCadreRow({ cc, onChanged }) {
  const [showLigne, setShowLigne] = useState(false)
  const [busy, setBusy] = useState(false)
  const activer = async () => {
    setBusy(true)
    await installationsApi.activerCommandeCadre(cc.id).catch(() => {})
    setBusy(false); onChanged?.()
  }
  const cloturer = async () => {
    setBusy(true)
    await installationsApi.cloturerCommandeCadre(cc.id).catch(() => {})
    setBusy(false); onChanged?.()
  }
  return (
    <div className="rounded-xl border border-border bg-card p-3" data-testid={`commande-cadre-${cc.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-sm">{cc.intitule}</span>
        <span className="text-xs text-muted-foreground">{cc.fournisseur_nom}</span>
        <Badge tone={STATUT_TONE[cc.statut] || 'neutral'}>{cc.statut_display || cc.statut}</Badge>
        <div className="ml-auto flex gap-2">
          {cc.statut === 'brouillon' && (
            <Button size="sm" variant="outline" disabled={busy} onClick={activer}>Activer</Button>
          )}
          {cc.statut === 'actif' && (
            <Button size="sm" variant="outline" disabled={busy} onClick={cloturer}>Clôturer</Button>
          )}
          <Button size="sm" variant="outline" onClick={() => setShowLigne(true)}>
            <PlusCircle className="size-4" aria-hidden="true" /> Ligne
          </Button>
        </div>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        {(cc.lignes || []).length === 0
          ? <p className="text-xs text-muted-foreground">Aucune ligne de prix.</p>
          : cc.lignes.map((l) => (
            <div key={l.id} className="flex flex-wrap items-center gap-2 text-sm pl-3 border-l border-border" data-testid={`commande-cadre-ligne-${l.id}`}>
              <span>{l.produit_nom || l.designation}</span>
              <span className="text-muted-foreground">P.U. {formatMAD(l.prix_negocie)}</span>
              <span className="text-muted-foreground">
                Volume restant : {l.volume_restant} / {l.volume_engage}
              </span>
            </div>
          ))}
      </div>
      {showLigne && (
        <CreateCommandeCadreLigneDialog commandeCadreId={cc.id}
          onClose={() => setShowLigne(false)}
          onCreated={() => { setShowLigne(false); onChanged?.() }} />
      )}
    </div>
  )
}

function CommandesCadreTab({ fournisseurs }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getCommandesCadre, { page_size: 200 })
  const [showCreate, setShowCreate] = useState(false)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle commande-cadre
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune commande-cadre">
        {rows.length > 0 && (
          <div className="flex flex-col gap-2">
            {rows.map((cc) => <CommandeCadreRow key={cc.id} cc={cc} onChanged={reload} />)}
          </div>
        )}
      </ListShell>
      {showCreate && (
        <CreateCommandeCadreDialog fournisseurs={fournisseurs}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Créer un contrat de prix ────────────────────────────────────────────────
function CreateContratPrixDialog({ fournisseurs, onClose, onCreated }) {
  const [intitule, setIntitule] = useState('')
  const [fournisseur, setFournisseur] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!intitule.trim() || !fournisseur) {
      setError('Intitulé et fournisseur sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createContratPrixFournisseur({
        intitule: intitule.trim(), fournisseur: Number(fournisseur),
        date_debut: dateDebut || null, date_fin: dateFin || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau contrat de prix</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="cp-intitule">Intitulé</label>
        <input id="cp-intitule" type="text" className="form-control" value={intitule} onChange={(e) => setIntitule(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="cp-fournisseur">Fournisseur</label>
        <select id="cp-fournisseur" className="form-control" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)}>
          <option value="">— Choisir —</option>
          {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
        </select>
        <label className="form-label" htmlFor="cp-debut">Date de début (optionnel)</label>
        <input id="cp-debut" type="date" className="form-control" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
        <label className="form-label" htmlFor="cp-fin">Date de fin (optionnel)</label>
        <input id="cp-fin" type="date" className="form-control" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
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

function CreateContratPrixLigneDialog({ contratId, onClose, onCreated }) {
  const [designation, setDesignation] = useState('')
  const [prixConvenu, setPrixConvenu] = useState('')
  const [remisePct, setRemisePct] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!designation.trim() || !prixConvenu) {
      setError('Désignation et prix convenu sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createContratPrixLigne({
        contrat: contratId, designation: designation.trim(),
        prix_convenu: prixConvenu, remise_pct: remisePct || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle ligne de prix convenu</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="cpl-designation">Désignation</label>
        <input id="cpl-designation" type="text" className="form-control" value={designation} onChange={(e) => setDesignation(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="cpl-prix">Prix convenu (MAD)</label>
        <input id="cpl-prix" type="number" step="any" className="form-control" value={prixConvenu} onChange={(e) => setPrixConvenu(e.target.value)} />
        <label className="form-label" htmlFor="cpl-remise">Remise % (optionnel)</label>
        <input id="cpl-remise" type="number" step="any" className="form-control" value={remisePct} onChange={(e) => setRemisePct(e.target.value)} />
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

function ContratPrixRow({ contrat, onChanged }) {
  const [showLigne, setShowLigne] = useState(false)
  const [busy, setBusy] = useState(false)
  const activer = async () => {
    setBusy(true)
    await installationsApi.activerContratPrixFournisseur(contrat.id).catch(() => {})
    setBusy(false); onChanged?.()
  }
  const expirer = async () => {
    setBusy(true)
    await installationsApi.expirerContratPrixFournisseur(contrat.id).catch(() => {})
    setBusy(false); onChanged?.()
  }
  return (
    <div className="rounded-xl border border-border bg-card p-3" data-testid={`contrat-prix-${contrat.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-sm">{contrat.intitule}</span>
        <span className="text-xs text-muted-foreground">{contrat.fournisseur_nom}</span>
        <Badge tone={STATUT_TONE[contrat.statut] || 'neutral'}>{contrat.statut_display || contrat.statut}</Badge>
        <span className="text-xs text-muted-foreground">
          {formatDate(contrat.date_debut)} → {formatDate(contrat.date_fin)}
        </span>
        <div className="ml-auto flex gap-2">
          {contrat.statut === 'brouillon' && (
            <Button size="sm" variant="outline" disabled={busy} onClick={activer}>Activer</Button>
          )}
          {contrat.statut === 'actif' && (
            <Button size="sm" variant="outline" disabled={busy} onClick={expirer}>Expirer</Button>
          )}
          <Button size="sm" variant="outline" onClick={() => setShowLigne(true)}>
            <PlusCircle className="size-4" aria-hidden="true" /> Ligne
          </Button>
        </div>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        {(contrat.lignes || []).length === 0
          ? <p className="text-xs text-muted-foreground">Aucune ligne de prix.</p>
          : contrat.lignes.map((l) => (
            <div key={l.id} className="flex flex-wrap items-center gap-2 text-sm pl-3 border-l border-border" data-testid={`contrat-prix-ligne-${l.id}`}>
              <span>{l.produit_nom || l.designation}</span>
              <span className="text-muted-foreground">Prix convenu {formatMAD(l.prix_convenu)}</span>
              {l.remise_pct != null && l.remise_pct !== '' && (
                <span className="text-muted-foreground">Remise {l.remise_pct}%</span>
              )}
            </div>
          ))}
      </div>
      {showLigne && (
        <CreateContratPrixLigneDialog contratId={contrat.id}
          onClose={() => setShowLigne(false)}
          onCreated={() => { setShowLigne(false); onChanged?.() }} />
      )}
    </div>
  )
}

function ContratsPrixTab({ fournisseurs }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getContratsPrixFournisseur, { page_size: 200 })
  const [showCreate, setShowCreate] = useState(false)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouveau contrat de prix
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucun contrat de prix">
        {rows.length > 0 && (
          <div className="flex flex-col gap-2">
            {rows.map((c) => <ContratPrixRow key={c.id} contrat={c} onChanged={reload} />)}
          </div>
        )}
      </ListShell>
      {showCreate && (
        <CreateContratPrixDialog fournisseurs={fournisseurs}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

export default function PrixNegocies() {
  const [fournisseurs, setFournisseurs] = useState([])

  useEffect(() => {
    let alive = true
    stockApi.getFournisseurs({ page_size: 200 }).then((res) => {
      if (alive) setFournisseurs(unwrap(res))
    }).catch(() => {})
    return () => { alive = false }
  }, [])

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Prix négociés fournisseurs"
        subtitle="Commandes-cadres et contrats de prix : en-têtes, lignes de prix négocié et volume restant engagé."
      />
      <Tabs defaultValue="cadres" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="cadres">Commandes-cadres</TabsTrigger>
          <TabsTrigger value="contrats">Contrats de prix</TabsTrigger>
        </TabsList>
        <TabsContent value="cadres">
          <CommandesCadreTab fournisseurs={fournisseurs} />
        </TabsContent>
        <TabsContent value="contrats">
          <ContratsPrixTab fournisseurs={fournisseurs} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
