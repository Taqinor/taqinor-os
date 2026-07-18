import { useMemo, useState } from 'react'
import { Sprout, FileText } from 'lucide-react'
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
   ========================================================================== */

const STATUT_TONE = {
  en_culture: 'success',
  jachere: 'warning',
  preparation: 'neutral',
}

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

export default function ParcellesPage() {
  const { data: parcelles, loading, error, reload } = useAgricultureResource(
    agricultureApi.parcelles.list, {})
  // WIR52 — campagnes de la société, pour retrouver la campagne 'en_cours'
  // d'une parcelle (source de vérité, indépendante de `Parcelle.statut`).
  const { data: campagnes, reload: reloadCampagnes } = useAgricultureResource(
    agricultureApi.campagnes.list, {})
  const [campagneParcelle, setCampagneParcelle] = useState(null)

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
    const actions = []
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
    return actions
  }

  return (
    <div className="page flex flex-col gap-4">
      <ListShell
        title="Parcelles"
        subtitle="Parcelles cultivables des exploitations de la société."
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
    </div>
  )
}
