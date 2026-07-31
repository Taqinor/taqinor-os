import { useEffect, useMemo, useState } from 'react'
import { Sprout, FileText, Plus, Droplets } from 'lucide-react'
import {
  Badge, Button, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, Label, Input, toast, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import MapView from '../../components/MapView'
import agricultureApi from '../../api/agricultureApi'
import useAgricultureResource from '../../features/agriculture/useAgricultureResource'
import { openPdfInGesture } from '../../utils/pdfBlob'

/* ============================================================================
   NTAGR4 — Écran « Parcelles » (`/agriculture/parcelles`).
   ----------------------------------------------------------------------------
   Liste des parcelles (superficie/culture/statut), carte simple (réutilise
   `components/MapView.jsx`, patron `crm.SiteProfile`/lead GPS) à partir du
   premier point du polygone GPS de chaque parcelle, et un bouton
   « Démarrer une campagne » depuis une parcelle libre (jachère/préparation).
   WIR52 — action de ligne « Registre phytosanitaire (PDF) » dès qu'une
   campagne 'en_cours' est rattachée à la parcelle (`agricultureApi.campagnes
   .registrePhytoPdf`, déjà exposé côté client mais jamais appelé) : le lien
   parcelle→campagne vient de la liste réelle des campagnes, jamais du champ
   `Parcelle.statut` seul (les deux ne sont pas synchronisés côté serveur).

   WIR141 — Backend CRUD complet pour Exploitation/Parcelle et le duo
   PointIrrigation/RelevePointIrrigation (NTAGR13/14) n'avait AUCUNE UI de
   création : (a) sélecteur « Exploitation » filtrant la liste des parcelles
   par `exploitation_id` (déjà supporté serveur) + dialogues de création
   Exploitation/Parcelle ; (b) action de ligne « Irrigation » ouvrant un
   dialogue listant les points d'irrigation de la parcelle, la saisie d'un
   relevé (volume + coût énergie, nul si pompage solaire — gratuit par
   construction) et le coût/volume d'irrigation de la campagne en cours de
   cette parcelle (`agricultureApi.campagnes.coutIrrigation`, sélecteurs
   NTAGR14 testés, jusqu'ici sans appelant REST — endpoint ajouté par ce
   même chantier, `apps/agriculture/views.py` `CampagneCulturaleViewSet
   .cout_irrigation`).
   ========================================================================== */

const STATUT_TONE = {
  en_culture: 'success',
  jachere: 'warning',
  preparation: 'neutral',
}

const STATUT_OPTIONS = [
  ['preparation', 'Préparation'],
  ['jachere', 'Jachère'],
  ['en_culture', 'En culture'],
]

const TYPE_SOURCE_OPTIONS = [
  ['puits', 'Puits'],
  ['pompage_solaire', 'Pompage solaire'],
  ['reseau', 'Réseau'],
]

function parcelleToMarker(parcelle) {
  const points = Array.isArray(parcelle.geometrie_gps) ? parcelle.geometrie_gps : []
  const first = points[0]
  if (!first || first.lat == null || first.lng == null) return null
  return {
    id: parcelle.id,
    lat: first.lat,
    lng: first.lng,
    label: parcelle.nom,
    color: parcelle.statut === 'en_culture' ? '#16a34a' : '#6b7280',
  }
}

function DemarrerCampagneDialog({ parcelle, onClose, onSaved }) {
  const [culture, setCulture] = useState('')
  const [variete, setVariete] = useState('')
  const [dateSemis, setDateSemis] = useState('')
  const [dateRecoltePrevue, setDateRecoltePrevue] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(culture || variete || dateSemis || dateRecoltePrevue)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!culture) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.campagnes.create({
        parcelle: parcelle.id, culture, variete,
        date_semis: dateSemis || null,
        date_recolte_prevue: dateRecoltePrevue || null,
        statut: 'en_cours',
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.statut || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Démarrer une campagne — {parcelle.nom}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="camp-culture">Culture</Label>
            <Input
              id="camp-culture" autoFocus value={culture}
              onChange={(e) => setCulture(e.target.value)} placeholder="Tomate, blé…"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="camp-variete">Variété (option.)</Label>
            <Input id="camp-variete" value={variete} onChange={(e) => setVariete(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="camp-semis">Date de semis</Label>
              <Input id="camp-semis" type="date" value={dateSemis} onChange={(e) => setDateSemis(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="camp-recolte">Récolte prévue</Label>
              <Input id="camp-recolte" type="date" value={dateRecoltePrevue} onChange={(e) => setDateRecoltePrevue(e.target.value)} />
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!culture || saving}>
              {saving ? 'Enregistrement…' : 'Démarrer la campagne'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR141 — Création d'une exploitation (aucune UI jusqu'ici).
function ExploitationDialog({ onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [adresse, setAdresse] = useState('')
  const [superficie, setSuperficie] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || adresse || superficie)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!nom) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.exploitations.create({
        nom, adresse,
        superficie_totale_ha: superficie === '' ? null : superficie,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.nom || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle exploitation</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="expl-nom">Nom</Label>
            <Input id="expl-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="expl-adresse">Adresse (option.)</Label>
            <Input id="expl-adresse" value={adresse} onChange={(e) => setAdresse(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="expl-superficie">Superficie totale (ha, option.)</Label>
            <Input
              id="expl-superficie" type="number" step="any" value={superficie}
              onChange={(e) => setSuperficie(e.target.value)}
            />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!nom || saving}>
              {saving ? 'Enregistrement…' : 'Créer l’exploitation'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR141 — Création/édition d'une parcelle (aucune UI de création jusqu'ici).
function ParcelleDialog({ exploitations, defaultExploitationId, record, onClose, onSaved }) {
  const isEdit = Boolean(record)
  const [exploitationId, setExploitationId] = useState(
    record?.exploitation != null ? String(record.exploitation) : (defaultExploitationId || ''))
  const [nom, setNom] = useState(record?.nom || '')
  const [code, setCode] = useState(record?.code || '')
  const [superficie, setSuperficie] = useState(record?.superficie_ha ?? '')
  const [culturePrincipale, setCulturePrincipale] = useState(record?.culture_principale || '')
  const [typeSol, setTypeSol] = useState(record?.type_sol || '')
  const [statut, setStatut] = useState(record?.statut || 'preparation')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || code || superficie || culturePrincipale || typeSol)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const peutEnregistrer = Boolean(exploitationId && nom)

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    const payload = {
      exploitation: exploitationId,
      nom, code,
      superficie_ha: superficie === '' ? null : superficie,
      culture_principale: culturePrincipale,
      type_sol: typeSol,
      statut,
    }
    try {
      if (isEdit) {
        await agricultureApi.parcelles.update(record.id, payload)
      } else {
        await agricultureApi.parcelles.create(payload)
      }
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.exploitation || data?.nom || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? `Modifier — ${record.nom}` : 'Nouvelle parcelle'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="parc-exploitation">Exploitation</Label>
            <select
              id="parc-exploitation" value={exploitationId}
              onChange={(e) => setExploitationId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {(exploitations || []).map((ex) => (
                <option key={ex.id} value={ex.id}>{ex.nom}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="parc-nom">Nom</Label>
              <Input id="parc-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="parc-code">Code (option.)</Label>
              <Input id="parc-code" value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="parc-culture">Culture principale (option.)</Label>
              <Input
                id="parc-culture" value={culturePrincipale}
                onChange={(e) => setCulturePrincipale(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="parc-superficie">Superficie (ha, option.)</Label>
              <Input
                id="parc-superficie" type="number" step="any" value={superficie}
                onChange={(e) => setSuperficie(e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="parc-sol">Type de sol (option.)</Label>
              <Input id="parc-sol" value={typeSol} onChange={(e) => setTypeSol(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="parc-statut">Statut</Label>
              <select
                id="parc-statut" value={statut}
                onChange={(e) => setStatut(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {STATUT_OPTIONS.map(([v, label]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </select>
            </div>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : (isEdit ? 'Enregistrer' : 'Créer la parcelle')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR141 — Points d'irrigation d'une parcelle + saisie de relevés, avec le
// coût d'irrigation payante / volume solaire de la campagne en cours (si
// une campagne est rattachée à cette parcelle).
function IrrigationDialog({ parcelle, campagneId, onClose }) {
  const { data: points, loading, error, reload } = useAgricultureResource(
    agricultureApi.pointsIrrigation.list, { parcelle_id: parcelle.id })
  const [selectedPointId, setSelectedPointId] = useState(null)
  const { data: releves, reload: reloadReleves } = useAgricultureResource(
    agricultureApi.relevesIrrigation.list,
    { point_id: selectedPointId || 0 }, [selectedPointId])

  const [showPointForm, setShowPointForm] = useState(false)
  const [typeSource, setTypeSource] = useState('puits')
  const [installationId, setInstallationId] = useState('')
  const [savingPoint, setSavingPoint] = useState(false)
  const [pointError, setPointError] = useState(null)

  const [showReleveForm, setShowReleveForm] = useState(false)
  const [date, setDate] = useState('')
  const [volumeM3, setVolumeM3] = useState('')
  const [coutEnergie, setCoutEnergie] = useState('')
  const [savingReleve, setSavingReleve] = useState(false)
  const [releveError, setReleveError] = useState(null)

  const [cockpit, setCockpit] = useState(null)
  const [cockpitLoading, setCockpitLoading] = useState(false)

  useEffect(() => {
    if (!campagneId) { setCockpit(null); return }
    let cancelled = false
    setCockpitLoading(true)
    agricultureApi.campagnes.coutIrrigation(campagneId)
      .then((res) => { if (!cancelled) setCockpit(res.data) })
      .catch(() => { if (!cancelled) setCockpit(null) })
      .finally(() => { if (!cancelled) setCockpitLoading(false) })
    return () => { cancelled = true }
  }, [campagneId])

  const selectedPoint = useMemo(
    () => (points || []).find((p) => String(p.id) === String(selectedPointId)) || null,
    [points, selectedPointId],
  )

  const submitPoint = async (e) => {
    e.preventDefault()
    setSavingPoint(true)
    setPointError(null)
    try {
      await agricultureApi.pointsIrrigation.create({
        parcelle: parcelle.id,
        type_source: typeSource,
        installation_id: typeSource === 'pompage_solaire' && installationId
          ? installationId : null,
      })
      setShowPointForm(false)
      setTypeSource('puits')
      setInstallationId('')
      reload()
      toast.success('Point d’irrigation créé.')
    } catch (err) {
      const data = err?.response?.data
      setPointError(
        data?.installation_id || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSavingPoint(false)
    }
  }

  const solaireGratuit = selectedPoint?.type_source === 'pompage_solaire'

  const submitReleve = async (e) => {
    e.preventDefault()
    if (!selectedPointId || !date || !volumeM3) return
    setSavingReleve(true)
    setReleveError(null)
    try {
      await agricultureApi.relevesIrrigation.create({
        point: selectedPointId, date, volume_m3: volumeM3,
        cout_energie_mad: (solaireGratuit || coutEnergie === '') ? null : coutEnergie,
      })
      setShowReleveForm(false)
      setDate('')
      setVolumeM3('')
      setCoutEnergie('')
      reloadReleves()
      toast.success('Relevé enregistré.')
    } catch (err) {
      const data = err?.response?.data
      setReleveError(
        data?.detail || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSavingReleve(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose?.() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Irrigation — {parcelle.nom}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          {campagneId && (
            <div className="rounded-md border border-border bg-muted/40 p-3 text-sm">
              {cockpitLoading && <span className="text-muted-foreground">Calcul du coût de la campagne en cours…</span>}
              {!cockpitLoading && cockpit && (
                <div className="flex flex-wrap gap-4">
                  <span>
                    Coût d’irrigation (campagne en cours) :{' '}
                    <strong>{cockpit.cout_irrigation_mad} MAD</strong>
                  </span>
                  <span>
                    Volume irrigué en pompage solaire :{' '}
                    <strong>{cockpit.volume_irrigation_solaire_m3} m³</strong> (gratuit)
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">Points d’irrigation</h3>
            <Button size="sm" variant="outline" onClick={() => setShowPointForm((s) => !s)}>
              <Plus /> Nouveau point
            </Button>
          </div>

          {showPointForm && (
            <form onSubmit={submitPoint} className="flex flex-col gap-3 rounded-md border border-border p-3" noValidate>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="pi-source">Source</Label>
                  <select
                    id="pi-source" value={typeSource}
                    onChange={(e) => setTypeSource(e.target.value)}
                    className="h-9 rounded-md border border-border bg-card px-3 text-sm"
                  >
                    {TYPE_SOURCE_OPTIONS.map(([v, label]) => (
                      <option key={v} value={v}>{label}</option>
                    ))}
                  </select>
                </div>
                {typeSource === 'pompage_solaire' && (
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="pi-installation">Installation (option.)</Label>
                    <Input
                      id="pi-installation" type="number" step="1" value={installationId}
                      onChange={(e) => setInstallationId(e.target.value)}
                    />
                  </div>
                )}
              </div>
              {pointError && <p className="text-sm text-destructive" role="alert">{pointError}</p>}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => setShowPointForm(false)}>Annuler</Button>
                <Button type="submit" size="sm" disabled={savingPoint}>
                  {savingPoint ? 'Enregistrement…' : 'Créer le point'}
                </Button>
              </div>
            </form>
          )}

          {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          {!loading && (points || []).length === 0 && (
            <p className="text-sm text-muted-foreground">Aucun point d’irrigation pour cette parcelle.</p>
          )}
          <ul className="flex flex-col gap-1">
            {(points || []).map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => setSelectedPointId(p.id)}
                  className={`flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm ${
                    String(selectedPointId) === String(p.id) ? 'border-primary bg-accent' : 'border-border'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <Droplets className="size-4" aria-hidden="true" />
                    {TYPE_SOURCE_OPTIONS.find(([v]) => v === p.type_source)?.[1] || p.type_source}
                  </span>
                  {p.type_source === 'pompage_solaire' && <Badge tone="success">Gratuit</Badge>}
                </button>
              </li>
            ))}
          </ul>

          {selectedPoint && (
            <div className="flex flex-col gap-3 border-t border-border pt-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium">
                  Relevés — {TYPE_SOURCE_OPTIONS.find(([v]) => v === selectedPoint.type_source)?.[1]}
                </h3>
                <Button size="sm" variant="outline" onClick={() => setShowReleveForm((s) => !s)}>
                  <Plus /> Nouveau relevé
                </Button>
              </div>

              {showReleveForm && (
                <form onSubmit={submitReleve} className="flex flex-col gap-3 rounded-md border border-border p-3" noValidate>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="rel-date">Date</Label>
                      <Input id="rel-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="rel-volume">Volume (m³)</Label>
                      <Input
                        id="rel-volume" type="number" step="any" value={volumeM3}
                        onChange={(e) => setVolumeM3(e.target.value)}
                      />
                    </div>
                  </div>
                  {solaireGratuit ? (
                    <p className="text-xs text-muted-foreground">
                      Pompage solaire — coût variable nul, aucun coût énergie à saisir.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      <Label htmlFor="rel-cout">Coût énergie (MAD, option.)</Label>
                      <Input
                        id="rel-cout" type="number" step="any" value={coutEnergie}
                        onChange={(e) => setCoutEnergie(e.target.value)}
                      />
                    </div>
                  )}
                  {releveError && <p className="text-sm text-destructive" role="alert">{releveError}</p>}
                  <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={() => setShowReleveForm(false)}>Annuler</Button>
                    <Button type="submit" size="sm" disabled={!date || !volumeM3 || savingReleve}>
                      {savingReleve ? 'Enregistrement…' : 'Enregistrer le relevé'}
                    </Button>
                  </div>
                </form>
              )}

              {(releves || []).length === 0 && (
                <p className="text-sm text-muted-foreground">Aucun relevé pour ce point.</p>
              )}
              <ul className="flex flex-col gap-1 text-sm">
                {(releves || []).map((r) => (
                  <li key={r.id} className="flex justify-between rounded-md border border-border px-3 py-1.5">
                    <span>{r.date}</span>
                    <span>{r.volume_m3} m³</span>
                    <span>{r.cout_energie_mad != null ? `${r.cout_energie_mad} MAD` : 'gratuit'}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ParcellesPage() {
  const [exploitationFilter, setExploitationFilter] = useState('')
  const { data: exploitations, reload: reloadExploitations } = useAgricultureResource(
    agricultureApi.exploitations.list, {})

  const parcellesParams = useMemo(
    () => (exploitationFilter ? { exploitation_id: exploitationFilter } : {}),
    [exploitationFilter],
  )
  const { data: parcelles, loading, error, reload } = useAgricultureResource(
    agricultureApi.parcelles.list, parcellesParams, [exploitationFilter])
  // WIR52 — campagnes de la société, pour retrouver la campagne 'en_cours'
  // d'une parcelle (source de vérité, indépendante de `Parcelle.statut`).
  const { data: campagnes, reload: reloadCampagnes } = useAgricultureResource(
    agricultureApi.campagnes.list, {})
  const [campagneParcelle, setCampagneParcelle] = useState(null)
  const [showExploitationForm, setShowExploitationForm] = useState(false)
  const [parcelleDialog, setParcelleDialog] = useState(null) // { record? }
  const [irrigationParcelle, setIrrigationParcelle] = useState(null)

  const markers = useMemo(
    () => (parcelles || []).map(parcelleToMarker).filter(Boolean),
    [parcelles],
  )

  // WIR52 — parcelle_id → id de sa campagne 'en_cours' (une seule à la fois,
  // contrainte serveur — apps/agriculture/serializers.py:validate).
  const campagneEnCoursId = useMemo(() => {
    const map = {}
    for (const c of campagnes || []) {
      if (c.statut === 'en_cours') map[c.parcelle] = c.id
    }
    return map
  }, [campagnes])

  // WIR52 — registre phytosanitaire ONSSA (NTAGR7) : jusqu'ici
  // `agricultureApi.campagnes.registrePhytoPdf` n'avait aucun appelant.
  const telechargerRegistrePhyto = (campagneId) => {
    // VX48 — window.open SYNCHRONE, avant tout await (Safari iOS bloque en
    // silence un window.open() qui suit un await).
    const pending = openPdfInGesture()
    agricultureApi.campagnes.registrePhytoPdf(campagneId)
      .then((res) => {
        const blob = new Blob([res.data], { type: 'application/pdf' })
        if (!pending.deliver(blob, `registre-phyto-${campagneId}.pdf`)) {
          toast.error('Ouverture bloquée par le navigateur.')
        }
      })
      .catch(() => toast.error('Registre phytosanitaire indisponible.'))
  }

  const columns = useMemo(() => [
    { id: 'nom', header: 'Parcelle', width: 180, accessor: (r) => r.nom, cell: (v) => v || '—' },
    { id: 'code', header: 'Code', width: 100, accessor: (r) => r.code, cell: (v) => v || '—' },
    {
      id: 'culture', header: 'Culture', width: 150,
      accessor: (r) => r.culture_principale, cell: (v) => v || '—',
    },
    {
      id: 'superficie', header: 'Superficie', align: 'right', numeric: true, width: 110,
      accessor: (r) => r.superficie_ha, cell: (v) => (v != null ? `${v} ha` : '—'),
    },
    {
      id: 'statut', header: 'Statut', width: 130, searchable: false,
      accessor: (r) => r.statut_display || r.statut,
      cell: (v, r) => <Badge tone={STATUT_TONE[r.statut] || 'neutral'}>{v || '—'}</Badge>,
    },
  ], [])

  const rowActions = (row) => {
    const actions = [{
      id: 'modifier', label: 'Modifier',
      onClick: () => setParcelleDialog({ record: row }),
    }]
    if (row.statut !== 'en_culture') {
      actions.push({
        id: 'demarrer-campagne', label: 'Démarrer une campagne',
        onClick: () => setCampagneParcelle(row),
      })
    }
    const campagneId = campagneEnCoursId[row.id]
    if (campagneId) {
      actions.push({
        id: 'registre-phyto', label: 'Registre phytosanitaire (PDF)', icon: FileText,
        onClick: () => telechargerRegistrePhyto(campagneId),
      })
    }
    actions.push({
      id: 'irrigation', label: 'Irrigation', icon: Droplets,
      onClick: () => setIrrigationParcelle(row),
    })
    return actions
  }

  const actions = (
    <div className="flex items-center gap-2">
      <select
        aria-label="Exploitation"
        value={exploitationFilter}
        onChange={(e) => setExploitationFilter(e.target.value)}
        className="h-9 rounded-md border border-border bg-card px-3 text-sm"
      >
        <option value="">Toutes les exploitations</option>
        {(exploitations || []).map((ex) => (
          <option key={ex.id} value={ex.id}>{ex.nom}</option>
        ))}
      </select>
      <Button variant="outline" onClick={() => setShowExploitationForm(true)}>
        <Plus /> Nouvelle exploitation
      </Button>
      <Button onClick={() => setParcelleDialog({})} disabled={!(exploitations || []).length}>
        <Plus /> Nouvelle parcelle
      </Button>
    </div>
  )

  return (
    <div className="page flex flex-col gap-4">
      <ListShell
        title="Parcelles"
        subtitle="Parcelles cultivables des exploitations de la société."
        actions={actions}
        columns={columns}
        rows={parcelles}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="parcelles"
        emptyTitle="Aucune parcelle"
        emptyDescription="Aucune parcelle enregistrée pour l’instant."
      >
        {markers.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Sprout className="size-4" aria-hidden="true" /> Carte des parcelles géolocalisées
            </div>
            <MapView markers={markers} height="40vh" />
          </div>
        )}
      </ListShell>

      {campagneParcelle && (
        <DemarrerCampagneDialog
          parcelle={campagneParcelle}
          onClose={() => setCampagneParcelle(null)}
          onSaved={() => {
            setCampagneParcelle(null)
            reload()
            reloadCampagnes()
            toast.success('Campagne démarrée.')
          }}
        />
      )}

      {showExploitationForm && (
        <ExploitationDialog
          onClose={() => setShowExploitationForm(false)}
          onSaved={() => {
            setShowExploitationForm(false)
            reloadExploitations()
            toast.success('Exploitation créée.')
          }}
        />
      )}

      {parcelleDialog && (
        <ParcelleDialog
          exploitations={exploitations}
          defaultExploitationId={exploitationFilter}
          record={parcelleDialog.record}
          onClose={() => setParcelleDialog(null)}
          onSaved={() => {
            setParcelleDialog(null)
            reload()
            toast.success(parcelleDialog.record ? 'Parcelle modifiée.' : 'Parcelle créée.')
          }}
        />
      )}

      {irrigationParcelle && (
        <IrrigationDialog
          parcelle={irrigationParcelle}
          campagneId={campagneEnCoursId[irrigationParcelle.id] || null}
          onClose={() => setIrrigationParcelle(null)}
        />
      )}
    </div>
  )
}
