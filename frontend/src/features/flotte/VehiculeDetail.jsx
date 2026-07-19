import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
  Tabs, TabsList, TabsTrigger, TabsContent,
  DefinitionList, Spinner, EmptyState, Button, Label, Input,
  toast, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'
import { formatMAD, formatNumber, formatDate } from '../../lib/format'
import { ENERGIES, VEHICULE_STATUTS, optionsFrom } from './flotte'
import { VehiculeStatutPill } from './statusPills'
import useFlotteResource from './useFlotteResource'

/* ============================================================================
   UX16 — Panneau détail d'un véhicule (tiroir latéral à onglets).
   ----------------------------------------------------------------------------
   Identité + carte grise (données déjà en ligne) et fiches calculées chargées
   à la demande via les actions detail=True : TCO (coûts d'exploitation +
   coût/km), éco-conduite (CO₂), amortissement (VNC), TSAV (vignette), grand
   livre des coûts (XFLT3), contrats (XFLT1), cycle de vie (XFLT4). Chiffres
   d'exploitation INTERNES — jamais présentés comme prix client ; aucun prix
   d'achat/marge.
   ========================================================================== */

// Onglet générique qui charge une action `fetcher(id)` et rend son payload.
function ComputedTab({ id, fetcher, render, emptyLabel, reloadKey }) {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(() => {
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    fetcher(id)
      .then((res) => { if (!cancelled) setState({ loading: false, error: null, data: res?.data ?? null }) })
      .catch((err) => {
        if (!cancelled) {
          setState({
            loading: false,
            error: err?.response?.data?.detail || 'Donnée indisponible.',
            data: null,
          })
        }
      })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, fetcher, reloadKey])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (state.loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }
  if (!state.data) {
    return <EmptyState title={emptyLabel || 'Aucune donnée'} description="Rien à afficher." />
  }
  return render(state.data)
}

// XFLT4 — Onglet « Cycle de vie » : transitions de statut (gate checklist
// commande→actif côté serveur) + cession + historique.
function CycleDeVieTab({ vehicule, onUpdated }) {
  const [statut, setStatut] = useState(vehicule?.statut || '')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)
  const [historique, setHistorique] = useState({ loading: true, items: [] })
  const [cession, setCession] = useState({ date_cession: '', prix_cession: '', acheteur: '' })
  const [cedant, setCedant] = useState(false)
  const vehiculeId = vehicule?.id

  const loadHistorique = useCallback(() => {
    if (!vehiculeId) return undefined
    let cancelled = false
    setHistorique({ loading: true, items: [] })
    flotteApi.vehiculeHistorique(vehiculeId)
      .then((res) => { if (!cancelled) setHistorique({ loading: false, items: res?.data || [] }) })
      .catch(() => { if (!cancelled) setHistorique({ loading: false, items: [] }) })
    return () => { cancelled = true }
  }, [vehiculeId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { loadHistorique() }, [loadHistorique])

  const changerStatut = async (e) => {
    e.preventDefault()
    if (!vehicule?.id || !statut || statut === vehicule.statut) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.changerStatut(vehicule.id, statut)
      toast.success('Statut mis à jour.')
      onUpdated?.()
      loadHistorique()
    } catch (err) {
      setServerError(err?.response?.data?.detail || 'Changement de statut impossible.')
    } finally {
      setSaving(false)
    }
  }

  const submitCession = async (e) => {
    e.preventDefault()
    if (!vehicule?.id || !cession.date_cession || cession.prix_cession === '') return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.ceder(vehicule.id, {
        date_cession: cession.date_cession,
        prix_cession: cession.prix_cession,
        acheteur: cession.acheteur,
      })
      toast.success('Véhicule cédé.')
      setCedant(false)
      onUpdated?.()
      loadHistorique()
    } catch (err) {
      setServerError(err?.response?.data?.detail || 'Cession impossible.')
    } finally {
      setSaving(false)
    }
  }

  const peutCeder = vehicule?.statut === 'a_vendre'

  return (
    <div className="flex flex-col gap-5">
      <form onSubmit={changerStatut} className="flex flex-col gap-3 rounded-md border border-border p-3">
        <Label htmlFor="cv-statut">Changer le statut</Label>
        <div className="flex items-center gap-2">
          <select
            id="cv-statut"
            value={statut}
            onChange={(e) => setStatut(e.target.value)}
            className="h-9 flex-1 rounded-md border border-border bg-card px-3 text-sm"
          >
            {optionsFrom(VEHICULE_STATUTS).map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <Button type="submit" disabled={saving || statut === vehicule?.statut}>
            {saving ? 'Enregistrement…' : 'Appliquer'}
          </Button>
        </div>
        {vehicule?.statut === 'commande' && !vehicule?.checklist_mise_en_service_ok && (
          <p className="text-xs text-warning">
            Le passage « Commandé » → « Actif » exige la checklist de mise en
            service complète (immatriculation, plaques, assurance, carte grise).
          </p>
        )}
        {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
      </form>

      {peutCeder && (
        <div className="flex flex-col gap-3 rounded-md border border-border p-3">
          {!cedant ? (
            <Button type="button" variant="outline" onClick={() => setCedant(true)}>
              Céder (vendre) ce véhicule
            </Button>
          ) : (
            <form onSubmit={submitCession} className="flex flex-col gap-3" noValidate>
              <p className="text-sm font-medium">Cession du véhicule</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="cession-date">Date de cession</Label>
                  <Input id="cession-date" type="date" value={cession.date_cession}
                    onChange={(e) => setCession((c) => ({ ...c, date_cession: e.target.value }))} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="cession-prix">Prix de cession (MAD)</Label>
                  <Input id="cession-prix" type="number" step="any" value={cession.prix_cession}
                    onChange={(e) => setCession((c) => ({ ...c, prix_cession: e.target.value }))} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cession-acheteur">Acheteur (option.)</Label>
                <Input id="cession-acheteur" value={cession.acheteur}
                  onChange={(e) => setCession((c) => ({ ...c, acheteur: e.target.value }))} />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setCedant(false)}>Annuler</Button>
                <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Confirmer la cession'}</Button>
              </div>
            </form>
          )}
        </div>
      )}

      <div>
        <p className="mb-2 text-sm font-medium">Historique des transitions</p>
        {historique.loading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Spinner className="size-4" /> Chargement…
          </div>
        ) : historique.items.length === 0 ? (
          <EmptyState title="Aucune transition" description="Aucun changement de statut enregistré." />
        ) : (
          <ul className="flex flex-col gap-2">
            {historique.items.map((h) => (
              <li key={h.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                <span>
                  {VEHICULE_STATUTS[h.ancien_statut] || h.ancien_statut || '—'}
                  {' → '}
                  <strong>{VEHICULE_STATUTS[h.nouveau_statut] || h.nouveau_statut}</strong>
                </span>
                <span className="text-xs text-muted-foreground">
                  {h.horodatage ? formatDate(h.horodatage) : ''}{h.user_nom ? ` · ${h.user_nom}` : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

// XFLT1 — Onglet « Contrats » du véhicule (leasing/LLD/location/entretien).
function ContratsTab({ vehiculeId }) {
  const [state, setState] = useState({ loading: true, error: null, data: [] })

  const load = useCallback(() => {
    if (!vehiculeId) return undefined
    let cancelled = false
    setState({ loading: true, error: null, data: [] })
    flotteApi.contratsVehicule.list({ vehicule: vehiculeId })
      .then((res) => {
        if (cancelled) return
        const payload = res?.data
        const rows = Array.isArray(payload) ? payload : payload?.results || []
        setState({ loading: false, error: null, data: rows })
      })
      .catch((err) => {
        if (cancelled) return
        setState({ loading: false, error: err?.response?.data?.detail || 'Contrats indisponibles.', data: [] })
      })
    return () => { cancelled = true }
  }, [vehiculeId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (state.loading) {
    return <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</div>
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }
  if (state.data.length === 0) {
    return <EmptyState title="Aucun contrat" description="Aucun contrat véhicule (leasing/LLD/location/entretien)." />
  }
  return (
    <ul className="flex flex-col gap-2">
      {state.data.map((c) => (
        <li key={c.id} className="rounded-md border border-border px-3 py-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-medium">{c.type_contrat_display || c.type_contrat}</span>
            <span className="text-xs text-muted-foreground">{c.statut_calcule || c.statut}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            {c.fournisseur || '—'} · {c.date_debut ? formatDate(c.date_debut) : '?'} → {c.date_fin ? formatDate(c.date_fin) : '?'}
          </p>
          {c.montant_recurrent != null && (
            <p className="text-xs text-muted-foreground">
              {formatMAD(c.montant_recurrent, { decimals: 0 })} / {c.periodicite_display || c.periodicite}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

// XFLT3 — Onglet « Grand livre des coûts » (ledger unifié, lecture seule).
function LedgerTab({ id }) {
  return (
    <ComputedTab
      id={id}
      fetcher={flotteApi.vehiculeLedger}
      emptyLabel="Aucune ligne de coût"
      render={(d) => {
        const lignes = Array.isArray(d) ? d : d?.lignes || []
        if (lignes.length === 0) {
          return <EmptyState title="Aucune ligne" description="Aucun coût enregistré pour ce véhicule." />
        }
        return (
          <ul className="flex flex-col gap-2">
            {lignes.map((l, i) => (
              <li key={l.id || i} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                <div>
                  <p className="font-medium">{l.libelle || l.categorie || l.source}</p>
                  <p className="text-xs text-muted-foreground">{l.date ? formatDate(l.date) : '—'}</p>
                </div>
                <span className="tabular-nums">{formatMAD(Number(l.montant ?? 0), { decimals: 0 })}</span>
              </li>
            ))}
          </ul>
        )
      }}
    />
  )
}

// WIR47 — Types d'accessoire (miroir fidèle de `RemiseAccessoire.Type`,
// backend/apps/flotte/models.py).
const TYPE_ACCESSOIRES = {
  cle: 'Clé',
  double_cle: 'Double de clé',
  carte_carburant: 'Carte carburant',
  tag_jawaz: 'Tag Jawaz',
  badge: 'Badge',
}

// WIR47 — Dialogue « Remettre un accessoire » : `remisesAccessoire.create`
// n'avait aucun appelant — détenteurs et historique étaient DÉJÀ affichés,
// mais impossible d'enregistrer une nouvelle remise depuis l'écran.
function RemiseAccessoireDialog({ actifId, conducteurs = [], onClose, onSaved }) {
  const [typeAccessoire, setTypeAccessoire] = useState('cle')
  const [conducteurId, setConducteurId] = useState('')
  const [dateRemise, setDateRemise] = useState('')
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(conducteurId && dateRemise)
  const dirty = Boolean(conducteurId || dateRemise || commentaire || typeAccessoire !== 'cle')
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.remisesAccessoire.create({
        actif_flotte: actifId,
        type_accessoire: typeAccessoire,
        conducteur: Number(conducteurId),
        date_remise: dateRemise,
        commentaire,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Remettre un accessoire</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="remise-type">Type d’accessoire</Label>
              <select
                id="remise-type"
                autoFocus
                value={typeAccessoire}
                onChange={(e) => setTypeAccessoire(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {Object.entries(TYPE_ACCESSOIRES).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="remise-conducteur">Conducteur</Label>
              <select
                id="remise-conducteur"
                value={conducteurId}
                onChange={(e) => setConducteurId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {conducteurs.map((c) => (
                  <option key={c.id} value={c.id}>{c.nom}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="remise-date">Date de remise</Label>
            <Input id="remise-date" type="date" value={dateRemise} onChange={(e) => setDateRemise(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="remise-commentaire">Commentaire</Label>
            <Input id="remise-commentaire" value={commentaire} onChange={(e) => setCommentaire(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Remettre'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// XFLT20 — Onglet « Accessoires » : détenteurs courants (clés/cartes/badges)
// + historique des remises. Résout l'``ActifFlotte`` du véhicule (la custody
// est trackée par actif unifié, pas directement par Vehicule).
function AccessoiresTab({ vehiculeId }) {
  const [state, setState] = useState({ loading: true, error: null, actifId: null, detenteurs: [], remises: [] })
  const [showForm, setShowForm] = useState(false)
  const { data: conducteurs } = useFlotteResource(flotteApi.conducteurs.list, { actif: 'true' })

  const load = useCallback(() => {
    if (!vehiculeId) return undefined
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null }))
    flotteApi.actifs.list({ type_actif: 'vehicule' })
      .then((res) => {
        if (cancelled) return
        const payload = res?.data
        const rows = Array.isArray(payload) ? payload : payload?.results || []
        const actif = rows.find((a) => String(a.vehicule) === String(vehiculeId))
        if (!actif) {
          setState({ loading: false, error: null, actifId: null, detenteurs: [], remises: [] })
          return
        }
        return Promise.all([
          flotteApi.actifs.detenteursCourants(actif.id),
          flotteApi.remisesAccessoire.list({ actif_flotte: actif.id }),
        ]).then(([det, rem]) => {
          if (cancelled) return
          const remPayload = rem?.data
          const remRows = Array.isArray(remPayload) ? remPayload : remPayload?.results || []
          setState({ loading: false, error: null, actifId: actif.id, detenteurs: det?.data || [], remises: remRows })
        })
      })
      .catch((err) => {
        if (cancelled) return
        setState({ loading: false, error: err?.response?.data?.detail || 'Indisponible.', actifId: null, detenteurs: [], remises: [] })
      })
    return () => { cancelled = true }
  }, [vehiculeId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (state.loading) {
    return <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Spinner className="size-4" /> Chargement…</div>
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }
  if (state.actifId == null) {
    return <EmptyState title="Aucun actif lié" description="Ce véhicule n’est pas encore rattaché à un actif de flotte." />
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowForm(true)}>Remettre un accessoire</Button>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium">Détenteurs courants</p>
        {state.detenteurs.length === 0 ? (
          <EmptyState title="Aucun accessoire détenu" description="Aucune clé/carte/badge en cours de détention." />
        ) : (
          <ul className="flex flex-col gap-2">
            {state.detenteurs.map((d) => (
              <li key={d.type} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                <span className="font-medium">{d.type_display}</span>
                <span className="text-xs text-muted-foreground">
                  {d.conducteur_nom} · depuis le {d.date_remise ? formatDate(d.date_remise) : '—'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <p className="mb-2 text-sm font-medium">Historique des remises</p>
        {state.remises.length === 0 ? (
          <EmptyState title="Aucune remise" description="Aucun accessoire remis pour ce véhicule." />
        ) : (
          <ul className="flex flex-col gap-2">
            {state.remises.map((r) => (
              <li key={r.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                <span>{r.type_accessoire_display} — {r.conducteur_nom}</span>
                <span className="text-xs text-muted-foreground">
                  {r.date_remise ? formatDate(r.date_remise) : '—'}
                  {r.date_retour ? ` → ${formatDate(r.date_retour)}` : ' (en cours)'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {showForm && (
        <RemiseAccessoireDialog
          actifId={state.actifId}
          conducteurs={conducteurs}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); load(); toast.success('Accessoire remis.') }}
        />
      )}
    </div>
  )
}

export default function VehiculeDetail({ vehicule, onClose, onChanged }) {
  const v = vehicule
  const open = Boolean(v)
  const [refreshKey, setRefreshKey] = useState(0)

  const bump = () => { setRefreshKey((k) => k + 1); onChanged?.() }

  const identite = useMemo(() => [
    { term: 'Immatriculation', description: v?.immatriculation || '—' },
    { term: 'Marque / modèle', description: [v?.marque, v?.modele].filter(Boolean).join(' ') || '—' },
    { term: 'Énergie', description: v?.energie_display || ENERGIES[v?.energie] || '—' },
    { term: 'Puissance fiscale', description: v?.puissance_fiscale ? `${v.puissance_fiscale} CV` : '—' },
    { term: 'Kilométrage', description: v?.kilometrage != null ? `${formatNumber(v.kilometrage)} km` : '—' },
    { term: 'Catégorie de permis requise', description: v?.categorie_permis_requise || '— (aucune)' },
    { term: 'Emplacement de stock', description: v?.emplacement_stock_label || '—' },
    { term: 'Valeur (immobilisation)', description: v?.valeur != null ? formatMAD(v.valeur, { decimals: 0 }) : '—' },
    // ZCTR11 — carte mobilité affichée sur la fiche véhicule.
    { term: 'Carte mobilité', description: v?.carte_mobilite || '—' },
  ], [v])

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose?.() }}>
      <SheetContent side="right" className="w-[min(40rem,calc(100%-2rem))]">
        <SheetHeader>
          <div className="flex flex-wrap items-center gap-2">
            <SheetTitle>{v?.immatriculation || 'Véhicule'}</SheetTitle>
            {v?.statut && <VehiculeStatutPill status={v.statut} />}
          </div>
          <p className="text-sm text-muted-foreground">
            {[v?.marque, v?.modele].filter(Boolean).join(' ')}
          </p>
        </SheetHeader>

        <Tabs defaultValue="identite">
          <TabsList className="flex-wrap">
            <TabsTrigger value="identite">Identité</TabsTrigger>
            <TabsTrigger value="cycle-de-vie">Cycle de vie</TabsTrigger>
            <TabsTrigger value="contrats">Contrats</TabsTrigger>
            <TabsTrigger value="ledger">Grand livre</TabsTrigger>
            <TabsTrigger value="accessoires">Accessoires</TabsTrigger>
            <TabsTrigger value="tco">Coûts TCO</TabsTrigger>
            <TabsTrigger value="eco">Éco-conduite</TabsTrigger>
            <TabsTrigger value="amortissement">Amortissement</TabsTrigger>
            <TabsTrigger value="tsav">TSAV</TabsTrigger>
          </TabsList>

          <TabsContent value="identite">
            <DefinitionList items={identite} />
          </TabsContent>

          <TabsContent value="cycle-de-vie">
            {v?.id && <CycleDeVieTab vehicule={v} onUpdated={bump} />}
          </TabsContent>

          <TabsContent value="contrats">
            <ContratsTab vehiculeId={v?.id} />
          </TabsContent>

          <TabsContent value="ledger">
            <LedgerTab id={v?.id} key={`ledger-${refreshKey}`} />
          </TabsContent>

          <TabsContent value="accessoires">
            <AccessoiresTab vehiculeId={v?.id} />
          </TabsContent>

          <TabsContent value="tco">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeTco}
              emptyLabel="Aucun coût enregistré"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Carburant', description: formatMAD(d.carburant ?? d.carburant_total, { decimals: 0 }) },
                    { term: 'Réparations', description: formatMAD(d.reparations ?? d.reparations_total, { decimals: 0 }) },
                    { term: 'Pneus & pièces', description: formatMAD(d.pneus_pieces ?? d.pieces, { decimals: 0 }) },
                    { term: 'Infractions', description: formatMAD(d.infractions, { decimals: 0 }) },
                    { term: 'Sinistres', description: formatMAD(d.sinistres, { decimals: 0 }) },
                    { term: 'Coût total', description: formatMAD(d.cout_total ?? d.total, { decimals: 0 }) },
                    { term: 'Coût / km', description: d.cout_par_km != null ? `${formatNumber(d.cout_par_km, { decimals: 2 })} MAD/km` : '—' },
                  ]}
                />
              )}
            />
          </TabsContent>

          <TabsContent value="eco">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeEcoConduite}
              emptyLabel="Pas de données d’éco-conduite"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Consommation moyenne', description: d.consommation_moyenne != null ? `${formatNumber(d.consommation_moyenne, { decimals: 1 })} L/100km` : '—' },
                    { term: 'CO₂ (g/km)', description: d.co2_g_km != null ? `${formatNumber(d.co2_g_km)} g/km` : '—' },
                    { term: 'CO₂ total', description: d.co2_total_kg != null ? `${formatNumber(d.co2_total_kg)} kg` : '—' },
                    { term: 'Score éco', description: d.eco_score != null ? formatNumber(d.eco_score) : '—' },
                  ]}
                />
              )}
            />
          </TabsContent>

          <TabsContent value="amortissement">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeAmortissement}
              emptyLabel="Aucune immobilisation liée"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Valeur d’acquisition', description: d.valeur_acquisition != null ? formatMAD(d.valeur_acquisition, { decimals: 0 }) : '—' },
                    { term: 'Amortissement cumulé', description: d.amortissement_cumule != null ? formatMAD(d.amortissement_cumule, { decimals: 0 }) : '—' },
                    { term: 'Valeur nette comptable', description: d.vnc != null ? formatMAD(d.vnc, { decimals: 0 }) : '—' },
                    { term: 'Part non déductible (plafond CGI)', description: d.part_non_deductible != null ? formatMAD(d.part_non_deductible, { decimals: 0 }) : '—' },
                  ]}
                />
              )}
            />
          </TabsContent>

          <TabsContent value="tsav">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeTsav}
              emptyLabel="Barème TSAV indisponible"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Montant TSAV', description: d.exonere ? 'Exonéré' : (d.montant != null ? formatMAD(d.montant, { decimals: 0 }) : '—') },
                    { term: 'Note', description: d.note || '—' },
                  ]}
                />
              )}
            />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}
