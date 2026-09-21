import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import {
  Badge, Button, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, Label, Input, Tabs, TabsList, TabsTrigger, TabsContent,
  toast, confirmLeaveIfDirty,
} from '../../ui'
import { ListShell } from '../../ui/module'
import agricultureApi from '../../api/agricultureApi'
import useAgricultureResource from '../../features/agriculture/useAgricultureResource'

/* ============================================================================
   NTAGR12 — Écran « Main d'œuvre & Matériel » (`/agriculture/ressources`).
   ----------------------------------------------------------------------------
   Deux onglets : pointage journalier (saisie rapide équipe/tâche/parcelle/
   jour, NTAGR9) et matériel (liste + « Enregistrer une utilisation » avec
   heures + carburant, NTAGR11). Les coûts remontent sur le cockpit campagne
   via `selectors.cout_main_oeuvre_campagne`/heures moteur cumulées côté
   backend — cet écran ne fait qu'afficher/saisir.

   WIR141 — `EquipeSaisonniere` et `MaterielAgricole` (CRUD backend complet)
   n'avaient aucune UI de création : « Nouvelle équipe » sur l'onglet
   Pointage, « Nouveau matériel » sur l'onglet Matériel.
   ========================================================================== */

const TYPE_MATERIEL_LABEL = {
  tracteur: 'Tracteur', moissonneuse: 'Moissonneuse',
  pulverisateur: 'Pulvérisateur', outil: 'Outil',
}

function PointageDialog({ equipes, campagnes, parcelles, onClose, onSaved }) {
  const [equipeId, setEquipeId] = useState('')
  const [travailleurNom, setTravailleurNom] = useState('')
  const [campagneId, setCampagneId] = useState('')
  const [parcelleId, setParcelleId] = useState('')
  const [date, setDate] = useState('')
  const [tache, setTache] = useState('')
  const [nombreJournees, setNombreJournees] = useState('')
  const [tauxJournalier, setTauxJournalier] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(
    equipeId || travailleurNom || date || tache || nombreJournees || tauxJournalier)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const peutEnregistrer = Boolean(
    (equipeId || travailleurNom) && parcelleId && date && tache
    && nombreJournees && tauxJournalier)

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.pointages.create({
        equipe: equipeId || null,
        travailleur_nom: equipeId ? '' : travailleurNom,
        campagne: campagneId || null,
        parcelle: parcelleId,
        date, tache,
        nombre_journees: nombreJournees,
        taux_journalier_mad: tauxJournalier,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouveau pointage</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-equipe">Équipe</Label>
              <select
                id="pt-equipe" value={equipeId}
                onChange={(e) => setEquipeId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Aucune —</option>
                {(equipes || []).map((eq) => (
                  <option key={eq.id} value={eq.id}>{eq.nom}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-travailleur">Travailleur libre</Label>
              <Input
                id="pt-travailleur" value={travailleurNom} disabled={Boolean(equipeId)}
                onChange={(e) => setTravailleurNom(e.target.value)}
                placeholder="Si pas d’équipe"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-parcelle">Parcelle</Label>
              <select
                id="pt-parcelle" value={parcelleId}
                onChange={(e) => setParcelleId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {(parcelles || []).map((p) => (
                  <option key={p.id} value={p.id}>{p.nom}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-campagne">Campagne (option.)</Label>
              <select
                id="pt-campagne" value={campagneId}
                onChange={(e) => setCampagneId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Aucune —</option>
                {(campagnes || []).map((c) => (
                  <option key={c.id} value={c.id}>{c.culture} — #{c.id}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-date">Date</Label>
              <Input id="pt-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-tache">Tâche</Label>
              <Input id="pt-tache" value={tache} onChange={(e) => setTache(e.target.value)} placeholder="Récolte, désherbage…" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-journees">Nombre de journées</Label>
              <Input
                id="pt-journees" type="number" step="any" value={nombreJournees}
                onChange={(e) => setNombreJournees(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pt-taux">Taux journalier (MAD)</Label>
              <Input
                id="pt-taux" type="number" step="any" value={tauxJournalier}
                onChange={(e) => setTauxJournalier(e.target.value)}
              />
            </div>
          </div>

          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function UtilisationDialog({ materiel, campagnes, onClose, onSaved }) {
  const [campagneId, setCampagneId] = useState('')
  const [date, setDate] = useState('')
  const [heuresUtilisees, setHeuresUtilisees] = useState('')
  const [coutCarburant, setCoutCarburant] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(date || heuresUtilisees || coutCarburant)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const peutEnregistrer = Boolean(date && heuresUtilisees)

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.utilisationsMateriel.create({
        materiel: materiel.id,
        campagne: campagneId || null,
        date,
        heures_utilisees: heuresUtilisees,
        cout_carburant_mad: coutCarburant === '' ? null : coutCarburant,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Utilisation — {materiel.nom}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ut-campagne">Campagne (option.)</Label>
            <select
              id="ut-campagne" value={campagneId}
              onChange={(e) => setCampagneId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Aucune —</option>
              {(campagnes || []).map((c) => (
                <option key={c.id} value={c.id}>{c.culture} — #{c.id}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ut-date">Date</Label>
              <Input id="ut-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ut-heures">Heures utilisées</Label>
              <Input
                id="ut-heures" type="number" step="any" value={heuresUtilisees}
                onChange={(e) => setHeuresUtilisees(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ut-carburant">Coût carburant (MAD, option.)</Label>
            <Input
              id="ut-carburant" type="number" step="any" value={coutCarburant}
              onChange={(e) => setCoutCarburant(e.target.value)}
            />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR141 — Création d'une équipe saisonnière (aucune UI jusqu'ici).
function EquipeDialog({ onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [chefEquipeId, setChefEquipeId] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || chefEquipeId)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!nom) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.equipesSaisonnieres.create({
        nom, chef_equipe_id: chefEquipeId === '' ? null : chefEquipeId,
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
          <DialogTitle>Nouvelle équipe saisonnière</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="eq-nom">Nom</Label>
            <Input id="eq-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="eq-chef">Chef d’équipe — id utilisateur (option.)</Label>
            <Input
              id="eq-chef" type="number" step="1" value={chefEquipeId}
              onChange={(e) => setChefEquipeId(e.target.value)}
            />
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!nom || saving}>
              {saving ? 'Enregistrement…' : 'Créer l’équipe'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// WIR141 — Création d'un matériel agricole (aucune UI jusqu'ici).
function MaterielDialog({ parcelles, onClose, onSaved }) {
  const [nom, setNom] = useState('')
  const [typeMateriel, setTypeMateriel] = useState('tracteur')
  const [numeroSerie, setNumeroSerie] = useState('')
  const [parcelleAffectee, setParcelleAffectee] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const dirty = Boolean(nom || numeroSerie || parcelleAffectee)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!nom) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.materiels.create({
        nom, type_materiel: typeMateriel, numero_serie: numeroSerie,
        parcelle_affectee: parcelleAffectee || null,
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
          <DialogTitle>Nouveau matériel</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mat-nom">Nom</Label>
            <Input id="mat-nom" autoFocus value={nom} onChange={(e) => setNom(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mat-type">Type</Label>
              <select
                id="mat-type" value={typeMateriel}
                onChange={(e) => setTypeMateriel(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {Object.entries(TYPE_MATERIEL_LABEL).map(([v, label]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mat-serie">N° série (option.)</Label>
              <Input id="mat-serie" value={numeroSerie} onChange={(e) => setNumeroSerie(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mat-parcelle">Parcelle affectée (option.)</Label>
            <select
              id="mat-parcelle" value={parcelleAffectee}
              onChange={(e) => setParcelleAffectee(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Aucune —</option>
              {(parcelles || []).map((p) => (
                <option key={p.id} value={p.id}>{p.nom}</option>
              ))}
            </select>
          </div>
          {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!nom || saving}>
              {saving ? 'Enregistrement…' : 'Créer le matériel'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PointageTab() {
  const { data: pointages, loading, error, reload } = useAgricultureResource(
    agricultureApi.pointages.list, {})
  const { data: equipes, reload: reloadEquipes } = useAgricultureResource(
    agricultureApi.equipesSaisonnieres.list, {})
  const { data: campagnes } = useAgricultureResource(agricultureApi.campagnes.list, {})
  const { data: parcelles } = useAgricultureResource(agricultureApi.parcelles.list, {})
  const [showForm, setShowForm] = useState(false)
  const [showEquipeForm, setShowEquipeForm] = useState(false)

  const columns = useMemo(() => [
    { id: 'date', header: 'Date', width: 100, accessor: (r) => r.date, cell: (v) => v || '—' },
    {
      id: 'qui', header: 'Équipe / travailleur', width: 180,
      accessor: (r) => equipes?.find((e) => String(e.id) === String(r.equipe))?.nom
        || r.travailleur_nom, cell: (v) => v || '—',
    },
    { id: 'tache', header: 'Tâche', width: 160, accessor: (r) => r.tache, cell: (v) => v || '—' },
    {
      id: 'journees', header: 'Journées', align: 'right', numeric: true, width: 100,
      accessor: (r) => r.nombre_journees, cell: (v) => (v != null ? v : '—'),
    },
    {
      id: 'taux', header: 'Taux/j (MAD)', align: 'right', numeric: true, width: 120,
      accessor: (r) => r.taux_journalier_mad, cell: (v) => (v != null ? v : '—'),
    },
  ], [equipes])

  return (
    <div className="flex flex-col gap-4">
      <ListShell
        title="Pointage journalier"
        subtitle="Saisie rapide équipe/tâche/parcelle/jour."
        actions={(
          <div className="flex items-center gap-2">
            <Button onClick={() => setShowForm(true)}>
              <Plus /> Nouveau pointage
            </Button>
            <Button variant="outline" onClick={() => setShowEquipeForm(true)}>
              <Plus /> Nouvelle équipe
            </Button>
          </div>
        )}
        columns={columns}
        rows={pointages}
        loading={loading}
        error={error}
        exportName="pointages"
        emptyTitle="Aucun pointage"
        emptyDescription="Aucun pointage enregistré pour l’instant."
      />
      {showForm && (
        <PointageDialog
          equipes={equipes} campagnes={campagnes} parcelles={parcelles}
          onClose={() => setShowForm(false)}
          onSaved={() => {
            setShowForm(false)
            reload()
            toast.success('Pointage enregistré.')
          }}
        />
      )}
      {showEquipeForm && (
        <EquipeDialog
          onClose={() => setShowEquipeForm(false)}
          onSaved={() => {
            setShowEquipeForm(false)
            reloadEquipes()
            toast.success('Équipe créée.')
          }}
        />
      )}
    </div>
  )
}

function MaterielTab() {
  const { data: materiels, loading, error, reload } = useAgricultureResource(
    agricultureApi.materiels.list, {})
  const { data: campagnes } = useAgricultureResource(agricultureApi.campagnes.list, {})
  const { data: parcelles } = useAgricultureResource(agricultureApi.parcelles.list, {})
  const [utilisationMateriel, setUtilisationMateriel] = useState(null)
  const [showMaterielForm, setShowMaterielForm] = useState(false)

  const columns = useMemo(() => [
    { id: 'nom', header: 'Matériel', width: 200, accessor: (r) => r.nom, cell: (v) => v || '—' },
    {
      id: 'type', header: 'Type', width: 140,
      accessor: (r) => r.type_materiel_display || TYPE_MATERIEL_LABEL[r.type_materiel],
      cell: (v) => (v ? <Badge tone="neutral">{v}</Badge> : '—'),
    },
    {
      id: 'serie', header: 'N° série', width: 130,
      accessor: (r) => r.numero_serie, cell: (v) => v || '—',
    },
    {
      id: 'heures', header: 'Heures moteur', align: 'right', numeric: true, width: 130,
      accessor: (r) => r.heures_moteur, cell: (v) => (v != null ? `${v} h` : '—'),
    },
  ], [])

  const rowActions = (row) => [{
    id: 'enregistrer-utilisation', label: 'Enregistrer une utilisation',
    onClick: () => setUtilisationMateriel(row),
  }]

  return (
    <div className="flex flex-col gap-4">
      <ListShell
        title="Matériel"
        subtitle="Parc de matériel agricole (heures moteur cumulées)."
        actions={(
          <Button variant="outline" onClick={() => setShowMaterielForm(true)}>
            <Plus /> Nouveau matériel
          </Button>
        )}
        columns={columns}
        rows={materiels}
        loading={loading}
        error={error}
        rowActions={rowActions}
        exportName="materiel-agricole"
        emptyTitle="Aucun matériel"
        emptyDescription="Aucun matériel agricole enregistré pour l’instant."
      />
      {showMaterielForm && (
        <MaterielDialog
          parcelles={parcelles}
          onClose={() => setShowMaterielForm(false)}
          onSaved={() => {
            setShowMaterielForm(false)
            reload()
            toast.success('Matériel créé.')
          }}
        />
      )}
      {utilisationMateriel && (
        <UtilisationDialog
          materiel={utilisationMateriel} campagnes={campagnes}
          onClose={() => setUtilisationMateriel(null)}
          onSaved={() => {
            setUtilisationMateriel(null)
            reload()
            toast.success('Utilisation enregistrée.')
          }}
        />
      )}
    </div>
  )
}

export default function RessourcesPage() {
  return (
    <div className="page flex flex-col gap-4">
      <Tabs defaultValue="pointage">
        <TabsList>
          <TabsTrigger value="pointage">Pointage</TabsTrigger>
          <TabsTrigger value="materiel">Matériel</TabsTrigger>
        </TabsList>
        <TabsContent value="pointage">
          <PointageTab />
        </TabsContent>
        <TabsContent value="materiel">
          <MaterielTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
