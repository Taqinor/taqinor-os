import { useCallback, useEffect, useState } from 'react'
import { CalendarRange, Flag, Camera, Plus, X } from 'lucide-react'
import { Card, Button, IconButton, Spinner, EmptyState, Badge, toast } from '../../../ui'
import { formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage, StatutJalon } from '../constants'
import GanttChart from '../GanttChart'
import ProjetPicker from '../components/ProjetPicker'

// WIR244 — jours de la semaine du calendrier ouvré (clés miroir de
// `CalendrierProjet`), utilisés pour les toggles ET la création par défaut
// (semaine de 5 jours : lundi→vendredi ouvrés, week-end chômé).
const JOURS_CALENDRIER = [
  ['lundi', 'Lun'], ['mardi', 'Mar'], ['mercredi', 'Mer'], ['jeudi', 'Jeu'],
  ['vendredi', 'Ven'], ['samedi', 'Sam'], ['dimanche', 'Dim'],
]
const CALENDRIER_5_JOURS = {
  lundi: true, mardi: true, mercredi: true, jeudi: true, vendredi: true,
  samedi: false, dimanche: false,
}

/* UX39 — Planning Gantt : phases / tâches / dépendances / jalons, baseline,
   calendriers & jours fériés. Gantt CSS/SVG léger (aucune lib Gantt). */

export default function PlanningPage() {
  const [projetId, setProjetId] = useState('')
  const [data, setData] = useState(null) // { taches, jalons, dependances, baseline, calendrier, feries }
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [busyTacheId, setBusyTacheId] = useState(null)
  // WIR244 — calendrier & jours fériés + dépendances : busy dédié pour ne
  // jamais bloquer le reste de l'écran (baseline, drag Gantt…) pendant une
  // écriture calendrier isolée.
  const [calendrierBusy, setCalendrierBusy] = useState(false)
  const [nouveauFerie, setNouveauFerie] = useState({ date: '', libelle: '' })

  const load = useCallback(async (pid) => {
    if (!pid) { setData(null); return }
    setLoading(true)
    setError(null)
    try {
      const [taches, jalons, deps, bases, cals, feries] = await Promise.all([
        gestionProjetApi.getTaches({ projet: pid }),
        gestionProjetApi.getJalons({ projet: pid }),
        gestionProjetApi.getDependances({ projet: pid }),
        gestionProjetApi.getBaselines({ projet: pid }),
        gestionProjetApi.getCalendriers({ projet: pid }),
        gestionProjetApi.getJoursFeries({ projet: pid }),
      ])
      const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])
      setData({
        taches: asList(taches),
        jalons: asList(jalons),
        dependances: asList(deps),
        baselines: asList(bases),
        calendrier: asList(cals)[0] ?? null,
        feries: asList(feries),
      })
    } catch (err) {
      setError(errMessage(err, 'Chargement du planning impossible.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load(projetId) })()
    return () => { alive = false }
  }, [projetId, load])

  // PROJ11 — Drag-to-reschedule dans le Gantt : appelle l'action serveur
  // `reprogrammer` (cascade successeurs conservée) avec rollback réseau.
  const reprogrammerTache = async (tache, nouvelleDateDebut) => {
    if (!tache) return
    const ancien = { debut: tache.date_debut_prevue, fin: tache.date_fin_prevue }
    setBusyTacheId(tache.id)
    setData((d) => (d ? { ...d, taches: d.taches.map((t) => (t.id === tache.id ? { ...t, date_debut_prevue: nouvelleDateDebut } : t)) } : d))
    try {
      const res = await gestionProjetApi.reprogrammerTache(tache.id, { date_debut: nouvelleDateDebut })
      const modifiees = Array.isArray(res.data) ? res.data : []
      setData((d) => {
        if (!d) return d
        return {
          ...d,
          taches: d.taches.map((t) => {
            const maj = modifiees.find((m) => m.id === t.id)
            return maj ? { ...t, ...maj } : t
          }),
        }
      })
      toast.success('Tâche replanifiée.')
    } catch (err) {
      setData((d) => (d ? { ...d, taches: d.taches.map((t) => (t.id === tache.id ? { ...t, date_debut_prevue: ancien.debut, date_fin_prevue: ancien.fin } : t)) } : d))
      toast.error(errMessage(err, "La replanification n'a pas pu être enregistrée — réessayez."))
    } finally {
      setBusyTacheId(null)
    }
  }

  const prendreBaseline = async () => {
    setBusy(true)
    try {
      await gestionProjetApi.prendreBaseline(projetId, { libelle: `Baseline ${formatDate(new Date())}` })
      toast.success('Baseline figée.')
      load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Baseline impossible.'))
    } finally {
      setBusy(false)
    }
  }

  // WIR244 — carte « Calendrier & jours fériés » : jusqu'ici purement lecture
  // seule. Création du calendrier (semaine de 5 jours par défaut), bascule
  // ouvré/chômé par jour, ajout/suppression de jours fériés + pré-remplissage
  // IDEMPOTENT des fériés marocains (seed-feries, jamais de doublon serveur).
  const creerCalendrier = async () => {
    setCalendrierBusy(true)
    try {
      await gestionProjetApi.createCalendrier({ projet: projetId, ...CALENDRIER_5_JOURS })
      toast.success('Calendrier créé (semaine de 5 jours).')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Création du calendrier impossible.'))
    } finally {
      setCalendrierBusy(false)
    }
  }

  const basculerJourCalendrier = async (jourKey) => {
    if (!data?.calendrier) return
    setCalendrierBusy(true)
    try {
      await gestionProjetApi.updateCalendrier(
        data.calendrier.id, { [jourKey]: !data.calendrier[jourKey] })
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Mise à jour du calendrier impossible.'))
    } finally {
      setCalendrierBusy(false)
    }
  }

  const ajouterJourFerie = async () => {
    if (!data?.calendrier || !nouveauFerie.date || !nouveauFerie.libelle.trim()) return
    setCalendrierBusy(true)
    try {
      await gestionProjetApi.createJourFerie({
        calendrier: data.calendrier.id, date: nouveauFerie.date,
        libelle: nouveauFerie.libelle.trim(),
      })
      setNouveauFerie({ date: '', libelle: '' })
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, "Impossible d'ajouter ce jour férié."))
    } finally {
      setCalendrierBusy(false)
    }
  }

  const supprimerJourFerie = async (ferie) => {
    setCalendrierBusy(true)
    try {
      await gestionProjetApi.deleteJourFerie(ferie.id)
      toast.success('Jour férié supprimé.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    } finally {
      setCalendrierBusy(false)
    }
  }

  const preRemplirFeries = async () => {
    if (!data?.calendrier) return
    setCalendrierBusy(true)
    try {
      const annee = new Date().getFullYear()
      const res = await gestionProjetApi.seedFeriesCalendrier(data.calendrier.id, annee)
      toast.success(`${res.data.nb_crees} jour(s) férié(s) ajouté(s) (${res.data.nb_deja_presents} déjà présents).`)
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Pré-remplissage impossible.'))
    } finally {
      setCalendrierBusy(false)
    }
  }

  // WIR244 — dépendances CPM depuis le Gantt (créées/supprimées directement
  // dans <GanttChart>, callbacks presentational comme `onReprogrammer`).
  const creerDependance = async (payload) => {
    try {
      await gestionProjetApi.createDependance(payload)
      toast.success('Dépendance ajoutée.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, "Impossible d'ajouter la dépendance."))
    }
  }

  const supprimerDependance = async (dep) => {
    try {
      await gestionProjetApi.deleteDependance(dep.id)
      toast.success('Dépendance supprimée.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Suppression impossible.'))
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Planning Gantt</h1>
          <p className="text-sm text-muted-foreground">Sélectionnez un projet pour visualiser son planning.</p>
        </div>
        <div className="flex items-end gap-2">
          <ProjetPicker value={projetId} onChange={setProjetId} />
          {projetId && (
            <Button variant="outline" size="sm" disabled={busy} onClick={prendreBaseline}>
              <Camera /> Figer une baseline
            </Button>
          )}
        </div>
      </div>

      {!projetId ? (
        <EmptyState icon={CalendarRange} title="Aucun projet sélectionné" description="Choisissez un projet pour afficher son diagramme de Gantt." />
      ) : loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={() => load(projetId)}>Réessayer</Button>} />
      ) : (
        <>
          <Card className="p-4 sm:p-5">
            <GanttChart
              taches={data?.taches ?? []}
              jalons={data?.jalons ?? []}
              dependances={data?.dependances ?? []}
              baseline={[]}
              onReprogrammer={reprogrammerTache}
              onCreerDependance={creerDependance}
              onSupprimerDependance={supprimerDependance}
              busyTacheId={busyTacheId}
            />
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Jalons</h3>
              {(data?.jalons ?? []).length ? (
                <ul className="flex flex-col gap-2">
                  {data.jalons.map((j) => (
                    <li key={j.id} className="flex items-center gap-2 text-sm">
                      <Flag className="size-4 text-amber-600" aria-hidden="true" />
                      <span className="font-medium">{j.libelle}</span>
                      <StatutJalon status={j.statut} />
                      <span className="ml-auto text-xs text-muted-foreground">{j.date_prevue ? formatDate(j.date_prevue) : '—'}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-muted-foreground">Aucun jalon.</p>}
            </Card>

            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Calendrier & jours fériés</h3>
              {data?.calendrier ? (
                <div className="flex flex-col gap-2 text-sm">
                  <div className="flex flex-wrap gap-1.5">
                    {JOURS_CALENDRIER.map(([key, lbl]) => (
                      <button
                        key={key}
                        type="button"
                        disabled={calendrierBusy}
                        onClick={() => basculerJourCalendrier(key)}
                        aria-pressed={!!data.calendrier[key]}
                        title={`${lbl} — cliquer pour basculer ouvré/chômé`}
                      >
                        <Badge tone={data.calendrier[key] ? 'success' : 'neutral'}>{lbl}</Badge>
                      </button>
                    ))}
                  </div>
                  {(data.feries ?? []).length ? (
                    <ul className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
                      {data.feries.map((f) => (
                        <li key={f.id} className="flex items-center gap-1">
                          <span>{formatDate(f.date)} — {f.libelle}</span>
                          <IconButton size="sm" variant="ghost" label="Supprimer ce jour férié"
                                      onClick={() => supprimerJourFerie(f)}>
                            <X className="size-3" aria-hidden="true" />
                          </IconButton>
                        </li>
                      ))}
                    </ul>
                  ) : <span className="text-xs text-muted-foreground">Aucun jour férié déclaré.</span>}

                  <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-border pt-2">
                    <input
                      type="date"
                      className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                      aria-label="Date du jour férié"
                      value={nouveauFerie.date}
                      onChange={(e) => setNouveauFerie((f) => ({ ...f, date: e.target.value }))}
                    />
                    <input
                      type="text"
                      className="h-8 flex-1 rounded-md border border-input bg-background px-2 text-xs"
                      aria-label="Libellé du jour férié"
                      placeholder="Libellé (ex. Fête du Trône)"
                      value={nouveauFerie.libelle}
                      onChange={(e) => setNouveauFerie((f) => ({ ...f, libelle: e.target.value }))}
                    />
                    <Button type="button" size="sm" variant="outline" disabled={calendrierBusy || !nouveauFerie.date || !nouveauFerie.libelle.trim()} onClick={ajouterJourFerie}>
                      <Plus className="size-3.5" aria-hidden="true" /> Ajouter
                    </Button>
                  </div>
                  <Button type="button" size="sm" variant="ghost" disabled={calendrierBusy} onClick={preRemplirFeries} className="self-start">
                    Pré-remplir les fériés ({new Date().getFullYear()})
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col items-start gap-2">
                  <p className="text-sm text-muted-foreground">Aucun calendrier défini pour ce projet.</p>
                  <Button type="button" size="sm" disabled={calendrierBusy} onClick={creerCalendrier}>
                    <Plus className="size-4" aria-hidden="true" /> Créer le calendrier (semaine de 5 jours)
                  </Button>
                </div>
              )}
            </Card>
          </div>

          {(data?.baselines ?? []).length > 0 && (
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">Baselines</h3>
              <ul className="flex flex-col gap-1 text-sm">
                {data.baselines.map((b) => (
                  <li key={b.id} className="flex items-center gap-2">
                    <span className="font-medium">{b.libelle || `Baseline #${b.id}`}</span>
                    <Badge tone="info">{b.nb_lignes} tâches</Badge>
                    <span className="ml-auto text-xs text-muted-foreground">{b.date_creation ? formatDate(b.date_creation) : ''}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
