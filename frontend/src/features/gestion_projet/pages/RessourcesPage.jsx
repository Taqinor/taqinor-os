import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Users, Settings, Send, Copy, Wand2 } from 'lucide-react'
import {
  Card, Button, Spinner, EmptyState, Badge, DataTable, Tabs, TabsList,
  TabsTrigger, TabsContent, Input, Label, toast,
} from '../../../ui'
import { useConfirmDialog } from '../../../ui/confirm'
import { BarArrondie } from '../../../ui/charts'
import { formatMAD, formatNumber, formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'
import RessourceFormDialog from '../components/RessourceFormDialog'
import TimesheetsTab from '../components/TimesheetsTab'
import ReglagesTempsDialog from '../components/ReglagesTempsDialog'

/* UX40 — Ressources & capacité : profils, équipes, affectations,
   indisponibilités, plan de charge (capacité vs affecté), timesheets.
   `cout_horaire` reste un indicateur INTERNE de pilotage — jamais un prix
   d'achat / marge, jamais rendu dans un PDF client. */

function todayISO(offset = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offset)
  return d.toISOString().slice(0, 10)
}

export default function RessourcesPage() {
  const { confirmDelete } = useConfirmDialog()
  const [ressources, setRessources] = useState([])
  const [equipes, setEquipes] = useState([])
  const [affectations, setAffectations] = useState([])
  const [indispos, setIndispos] = useState([])
  const [timesheets, setTimesheets] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editRes, setEditRes] = useState(null)
  const [showReglages, setShowReglages] = useState(false)
  const [affectBusy, setAffectBusy] = useState(false)

  // Plan de charge : fenêtre par défaut = 30 prochains jours.
  const [debut, setDebut] = useState(todayISO())
  const [fin, setFin] = useState(todayISO(30))
  const [charge, setCharge] = useState(null)
  const [chargeLoading, setChargeLoading] = useState(false)

  const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [r, e, a, i, t] = await Promise.all([
        gestionProjetApi.getRessources(),
        gestionProjetApi.getEquipes(),
        gestionProjetApi.getAffectations(),
        gestionProjetApi.getIndisponibilites(),
        gestionProjetApi.getTimesheets(),
      ])
      setRessources(asList(r))
      setEquipes(asList(e))
      setAffectations(asList(a))
      setIndispos(asList(i))
      setTimesheets(asList(t))
    } catch (err) {
      setError(errMessage(err, 'Chargement des ressources impossible.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    return () => { alive = false }
  }, [load])

  const loadCharge = useCallback(async () => {
    if (!debut || !fin) return
    setChargeLoading(true)
    try {
      const res = await gestionProjetApi.getPlanDeCharge({ debut, fin })
      setCharge(res.data)
    } catch (err) {
      toast.error(errMessage(err, 'Plan de charge indisponible.'))
    } finally {
      setChargeLoading(false)
    }
  }, [debut, fin])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await loadCharge() })()
    return () => { alive = false }
  }, [loadCharge])

  const deleteRessource = async (r) => {
    const ok = await confirmDelete({ title: `Supprimer « ${r.nom} » ?`, description: 'Action irréversible.' })
    if (!ok) return
    try {
      await gestionProjetApi.deleteRessource(r.id)
      setRessources((rows) => rows.filter((x) => x.id !== r.id))
      toast.success('Ressource supprimée.')
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  // ZPRJ2 — Publier les affectations BROUILLON de la fenêtre affichée.
  const publierAffectations = async () => {
    setAffectBusy(true)
    try {
      const res = await gestionProjetApi.publierAffectations({ debut, fin })
      toast.success(`${res.data?.nb_publiees ?? 0} affectation(s) publiée(s).`)
      load()
    } catch (err) {
      toast.error(errMessage(err, 'Publication impossible.'))
    } finally {
      setAffectBusy(false)
    }
  }

  // ZPRJ3 — Copie le plan de la semaine précédente vers la semaine affichée.
  const copierSemaineAffectations = async () => {
    setAffectBusy(true)
    try {
      const semaineCible = debut
      const src = new Date(debut)
      src.setDate(src.getDate() - 7)
      const semaineSource = src.toISOString().slice(0, 10)
      const res = await gestionProjetApi.copierSemaineAffectations({
        semaine_source: semaineSource, semaine_cible: semaineCible,
      })
      toast.success(`${res.data?.nb_copiees ?? 0} affectation(s) copiée(s).`)
      load()
    } catch (err) {
      toast.error(errMessage(err, 'Copie impossible.'))
    } finally {
      setAffectBusy(false)
    }
  }

  // ZPRJ4 — Auto-affectation (simulation puis confirmation demandée à l'utilisateur).
  const autoAffecter = async () => {
    setAffectBusy(true)
    try {
      const simulation = await gestionProjetApi.autoAffecter({ debut, fin }, false)
      const nb = simulation.data?.propositions?.length ?? simulation.data?.nb_propositions ?? 0
      const ok = window.confirm(
        `${nb} proposition(s) d'affectation — confirmer l'application (statut brouillon) ?`)
      if (!ok) return
      const res = await gestionProjetApi.autoAffecter({ debut, fin }, true)
      toast.success(`${res.data?.nb_appliquees ?? nb} affectation(s) créée(s)/déplacée(s).`)
      load()
    } catch (err) {
      toast.error(errMessage(err, 'Auto-affectation impossible.'))
    } finally {
      setAffectBusy(false)
    }
  }

  // Données du graphique plan de charge : deux barres par ressource
  // (capacité vs affecté), distinguées par couleur.
  const chargeBars = useMemo(() => {
    const lignes = charge?.ressources ?? charge?.lignes ?? []
    const bars = []
    for (const l of lignes) {
      const nom = l.ressource_nom ?? l.nom ?? `#${l.ressource_id ?? l.id}`
      const cap = Number(l.capacite ?? l.capacite_heures ?? 0)
      const aff = Number(l.affecte ?? l.affecte_heures ?? 0)
      bars.push({ label: `${nom} · cap.`, value: cap, color: 'muted-foreground' })
      bars.push({ label: `${nom} · aff.`, value: aff, color: aff > cap ? 'destructive' : 'primary' })
    }
    return bars
  }, [charge])

  if (loading) return <div className="flex justify-center p-10"><Spinner /></div>
  if (error) return <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={load}>Réessayer</Button>} />

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Ressources & capacité</h1>
          <p className="text-sm text-muted-foreground">Profils, équipes, affectations, plan de charge et temps.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setShowReglages(true)}>
            <Settings /> Réglages temps
          </Button>
          <Button onClick={() => { setEditRes(null); setShowForm(true) }}>
            <Plus /> Nouvelle ressource
          </Button>
        </div>
      </div>

      <Tabs defaultValue="ressources">
        <TabsList className="flex-wrap">
          <TabsTrigger value="ressources">Ressources</TabsTrigger>
          <TabsTrigger value="equipes">Équipes</TabsTrigger>
          <TabsTrigger value="charge">Plan de charge</TabsTrigger>
          <TabsTrigger value="affectations">Affectations</TabsTrigger>
          <TabsTrigger value="indispos">Indisponibilités</TabsTrigger>
          <TabsTrigger value="timesheets">Timesheets</TabsTrigger>
        </TabsList>

        <TabsContent value="ressources">
          <Card className="p-4 sm:p-5">
            <DataTable
              data={ressources}
              getRowId={(r) => r.id}
              columns={[
                { id: 'nom', header: 'Nom', accessor: (r) => r.nom, cell: (v) => <span className="font-medium">{v}</span> },
                { id: 'role', header: 'Rôle', accessor: (r) => r.role || '—' },
                { id: 'competences', header: 'Compétences', accessor: (r) => r.competences || '—' },
                { id: 'cout', header: 'Coût horaire (interne)', align: 'right', numeric: true, searchable: false, accessor: (r) => Number(r.cout_horaire ?? 0), cell: (_v, r) => (r.cout_horaire ? formatMAD(r.cout_horaire) : '—') },
                { id: 'actif', header: 'Actif', searchable: false, accessor: (r) => r.actif, cell: (v) => <Badge tone={v ? 'success' : 'neutral'}>{v ? 'Actif' : 'Inactif'}</Badge> },
              ]}
              rowActions={(r) => [
                { id: 'edit', label: 'Éditer', onClick: () => { setEditRes(r); setShowForm(true) } },
                { id: 'del', label: 'Supprimer', destructive: true, separatorBefore: true, onClick: () => deleteRessource(r) },
              ]}
              exportName="ressources"
              emptyTitle="Aucune ressource"
              emptyDescription="Créez des profils de ressources internes pour planifier."
            />
          </Card>
        </TabsContent>

        <TabsContent value="equipes">
          <Card className="p-4 sm:p-5">
            {equipes.length ? (
              <ul className="flex flex-col gap-2">
                {equipes.map((e) => (
                  <li key={e.id} className="flex flex-wrap items-center gap-2 rounded-md border border-border p-2 text-sm">
                    <span className="font-medium">{e.nom}</span>
                    <Badge tone="info">{(e.membres_detail ?? e.membres ?? []).length} membres</Badge>
                    {e.description && <span className="text-xs text-muted-foreground">{e.description}</span>}
                  </li>
                ))}
              </ul>
            ) : <EmptyState icon={Users} title="Aucune équipe" description="Regroupez des ressources en équipes." />}
          </Card>
        </TabsContent>

        <TabsContent value="charge">
          <Card className="p-4 sm:p-5">
            <div className="mb-4 flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <Label htmlFor="charge-debut">Début</Label>
                <Input id="charge-debut" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="charge-fin">Fin</Label>
                <Input id="charge-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
              </div>
            </div>
            {chargeLoading ? (
              <div className="flex justify-center p-6"><Spinner /></div>
            ) : chargeBars.length ? (
              <BarArrondie
                data={chargeBars}
                layout="vertical"
                categoryWidth={130}
                height={Math.max(200, chargeBars.length * 26)}
                name="Heures"
                tooltipFormat={(v) => `${formatNumber(v)} h`}
              />
            ) : (
              <EmptyState title="Aucune donnée de charge" description="Aucune affectation sur cette période." />
            )}
          </Card>
        </TabsContent>

        <TabsContent value="affectations">
          <Card className="p-4 sm:p-5">
            <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
              <Button size="sm" variant="outline" disabled={affectBusy} onClick={publierAffectations} title="Publier les affectations brouillon (ZPRJ2)">
                <Send className="size-3.5" aria-hidden="true" /> Publier
              </Button>
              <Button size="sm" variant="outline" disabled={affectBusy} onClick={copierSemaineAffectations} title="Copier le plan de la semaine précédente (ZPRJ3)">
                <Copy className="size-3.5" aria-hidden="true" /> Copier la semaine
              </Button>
              <Button size="sm" variant="outline" disabled={affectBusy} onClick={autoAffecter} title="Auto-affecter les tâches en excès (ZPRJ4)">
                <Wand2 className="size-3.5" aria-hidden="true" /> Auto-affecter
              </Button>
            </div>
            <DataTable
              data={affectations}
              getRowId={(a) => a.id}
              columns={[
                { id: 'tache', header: 'Tâche', accessor: (a) => a.tache_libelle || `#${a.tache}` },
                { id: 'ressource', header: 'Ressource', accessor: (a) => a.ressource_nom || a.equipe_nom || (a.actif_type ? `Actif ${a.actif_type} #${a.actif_id}` : '—') },
                { id: 'debut', header: 'Début', searchable: false, accessor: (a) => a.date_debut || '', cell: (v) => v ? formatDate(v) : '—' },
                { id: 'fin', header: 'Fin', searchable: false, accessor: (a) => a.date_fin || '', cell: (v) => v ? formatDate(v) : '—' },
                { id: 'charge', header: 'Charge (j)', align: 'right', numeric: true, searchable: false, accessor: (a) => Number(a.charge_jours ?? 0), cell: (v) => v ? formatNumber(v) : '—' },
              ]}
              exportName="affectations"
              emptyTitle="Aucune affectation"
              emptyDescription="Affectez des ressources aux tâches du planning."
            />
          </Card>
        </TabsContent>

        <TabsContent value="indispos">
          <Card className="p-4 sm:p-5">
            <DataTable
              data={indispos}
              getRowId={(i) => i.id}
              columns={[
                { id: 'ressource', header: 'Ressource', accessor: (i) => i.ressource_nom || `#${i.ressource}` },
                { id: 'type', header: 'Type', searchable: false, accessor: (i) => i.type_indispo, cell: (v) => <Badge tone="warning">{v}</Badge> },
                { id: 'debut', header: 'Début', searchable: false, accessor: (i) => i.date_debut || '', cell: (v) => v ? formatDate(v) : '—' },
                { id: 'fin', header: 'Fin', searchable: false, accessor: (i) => i.date_fin || '', cell: (v) => v ? formatDate(v) : '—' },
                { id: 'motif', header: 'Motif', accessor: (i) => i.motif || '—' },
              ]}
              exportName="indisponibilites"
              emptyTitle="Aucune indisponibilité"
              emptyDescription="Déclarez congés, formations ou arrêts."
            />
          </Card>
        </TabsContent>

        <TabsContent value="timesheets">
          <TimesheetsTab timesheets={timesheets} onChanged={load} />
        </TabsContent>
      </Tabs>

      {showForm && (
        <RessourceFormDialog
          ressource={editRes}
          onClose={() => setShowForm(false)}
          onSaved={(saved) => {
            setShowForm(false)
            setRessources((rows) => {
              const exists = rows.some((x) => x.id === saved.id)
              return exists ? rows.map((x) => (x.id === saved.id ? saved : x)) : [...rows, saved]
            })
            toast.success('Ressource enregistrée.')
          }}
        />
      )}
      {showReglages && (
        <ReglagesTempsDialog
          onClose={() => setShowReglages(false)}
          onSaved={() => { setShowReglages(false); toast.success('Réglages temps enregistrés.') }}
        />
      )}
    </div>
  )
}
