import { useCallback, useEffect, useState } from 'react'
import { CalendarRange, Flag, Camera, Plus, Sparkles } from 'lucide-react'
import {
  Card, Button, Spinner, EmptyState, Badge, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Form, FormField, Input,
} from '../../../ui'
import { formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage, StatutJalon } from '../constants'
import GanttChart from '../GanttChart'
import ProjetPicker from '../components/ProjetPicker'

/* UX39 — Planning Gantt : phases / tâches / dépendances / jalons, baseline,
   calendriers & jours fériés. Gantt CSS/SVG léger (aucune lib Gantt). */

export default function PlanningPage() {
  const [projetId, setProjetId] = useState('')
  const [data, setData] = useState(null) // { taches, jalons, dependances, baseline, calendrier, feries }
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [busyTacheId, setBusyTacheId] = useState(null)
  // WIR244 — écriture du calendrier ouvré & des jours fériés.
  const [ferieOpen, setFerieOpen] = useState(false)
  const [calBusy, setCalBusy] = useState(false)

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

  /* WIR244 — le calendrier ouvré, les jours fériés et les dépendances CPM
     n'étaient créables NULLE PART : le planning lisait un calendrier qu'aucun
     écran ne permettait de créer. `company` reste posée côté serveur. */
  const creerCalendrier = async () => {
    setCalBusy(true)
    try {
      // Semaine ouvrée marocaine par défaut : lundi→vendredi.
      await gestionProjetApi.createCalendrier({
        projet: projetId,
        lundi: true, mardi: true, mercredi: true, jeudi: true, vendredi: true,
        samedi: false, dimanche: false,
      })
      toast.success('Calendrier créé (semaine 5 jours).')
      load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Création du calendrier impossible.'))
    } finally { setCalBusy(false) }
  }

  const basculerJour = async (cle, valeur) => {
    if (!data?.calendrier) return
    setCalBusy(true)
    try {
      await gestionProjetApi.updateCalendrier(data.calendrier.id, { [cle]: valeur })
      load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Mise à jour du calendrier impossible.'))
    } finally { setCalBusy(false) }
  }

  // Pré-remplissage IDEMPOTENT côté serveur : le compte des doublons évités
  // vient de sa réponse, jamais d'un calcul client.
  const seederFeries = async () => {
    if (!data?.calendrier) return
    setCalBusy(true)
    try {
      const res = await gestionProjetApi.seedFeriesCalendrier(
        data.calendrier.id, new Date().getFullYear())
      const d = res.data || {}
      toast.success(
        `${d.nb_crees ?? 0} jour(s) férié(s) ajouté(s)`
        + `${d.nb_deja_presents ? `, ${d.nb_deja_presents} déjà présent(s)` : ''}.`)
      load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Pré-remplissage des fériés impossible.'))
    } finally { setCalBusy(false) }
  }

  /* WIR244 — dépendances CPM : `createDependance`/`deleteDependance` étaient
     orphelines, le chemin critique ne pouvait donc jamais être alimenté. Le
     serveur refuse en 400 l'auto-dépendance, le cycle direct et deux tâches de
     projets différents — son message est affiché tel quel. Le rechargement
     complet ramène le planning recalculé. */
  const creerDependance = async (payload) => {
    try {
      await gestionProjetApi.createDependance(payload)
      toast.success('Dépendance ajoutée.')
      await load(projetId)
    } catch (err) {
      toast.error(errMessage(err, 'Création de la dépendance impossible.'))
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
              busyTacheId={busyTacheId}
              onCreerDependance={creerDependance}
              onSupprimerDependance={supprimerDependance}
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
              <div className="mb-3 flex items-center justify-between gap-2">
                <h3 className="font-display text-base font-semibold">Calendrier & jours fériés</h3>
                {data?.calendrier && (
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" disabled={calBusy} onClick={seederFeries}>
                      <Sparkles className="size-3.5" aria-hidden="true" /> Pré-remplir les fériés
                    </Button>
                    <Button size="sm" onClick={() => setFerieOpen(true)}>
                      <Plus className="size-3.5" aria-hidden="true" /> Jour férié
                    </Button>
                  </div>
                )}
              </div>
              {data?.calendrier ? (
                <div className="flex flex-col gap-2 text-sm">
                  {/* WIR244 — les jours ouvrés se BASCULENT (updateCalendrier) :
                      ils n'étaient qu'affichés. */}
                  <div className="flex flex-wrap gap-1.5">
                    {[['Lun', 'lundi'], ['Mar', 'mardi'], ['Mer', 'mercredi'], ['Jeu', 'jeudi'], ['Ven', 'vendredi'], ['Sam', 'samedi'], ['Dim', 'dimanche']].map(([lbl, cle]) => {
                      const on = data.calendrier[cle]
                      return (
                        <button key={cle} type="button" disabled={calBusy}
                                aria-pressed={Boolean(on)}
                                onClick={() => basculerJour(cle, !on)}
                                title={`${lbl} — ${on ? 'ouvré' : 'chômé'}`}>
                          <Badge tone={on ? 'success' : 'neutral'}>{lbl}</Badge>
                        </button>
                      )
                    })}
                  </div>
                  {(data.feries ?? []).length ? (
                    <ul className="mt-2 flex flex-col gap-1 text-xs text-muted-foreground">
                      {data.feries.map((f) => (
                        <li key={f.id}>{formatDate(f.date)} — {f.libelle}</li>
                      ))}
                    </ul>
                  ) : <span className="text-xs text-muted-foreground">Aucun jour férié déclaré.</span>}
                </div>
              ) : (
                <div className="flex flex-col items-start gap-2">
                  <p className="text-sm text-muted-foreground">Aucun calendrier défini pour ce projet.</p>
                  <Button size="sm" disabled={calBusy} onClick={creerCalendrier}>
                    <Plus className="size-3.5" aria-hidden="true" /> Créer le calendrier (5 jours)
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

      {ferieOpen && data?.calendrier && (
        <JourFerieForm
          calendrierId={data.calendrier.id}
          onClose={() => setFerieOpen(false)}
          onSaved={() => { setFerieOpen(false); load(projetId) }}
        />
      )}
    </div>
  )
}

/* WIR244 — Ajouter un jour férié à un calendrier. `company` posée serveur ;
   l'unicité (calendrier, date) est garantie côté serveur (400 sur doublon). */
function JourFerieForm({ calendrierId, onClose, onSaved }) {
  const [date, setDate] = useState('')
  const [libelle, setLibelle] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    if (!date) { setError('La date est requise.'); return }
    setSaving(true)
    setError(null)
    try {
      await gestionProjetApi.createJourFerie({
        calendrier: calendrierId, date, libelle: libelle.trim(),
      })
      onSaved?.()
    } catch (err) {
      setError(errMessage(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau jour férié</DialogTitle></DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Date" required htmlFor="jf-date" fullWidth>
            <Input id="jf-date" type="date" value={date}
                   onChange={(e) => setDate(e.target.value)} />
          </FormField>
          <FormField label="Libellé" htmlFor="jf-libelle" fullWidth>
            <Input id="jf-libelle" value={libelle}
                   onChange={(e) => setLibelle(e.target.value)} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
