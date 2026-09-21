import { useEffect, useState } from 'react'
import { Card, Badge, Button, EmptyState, Spinner, Input, toast } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'
import { openPdfInGesture } from '../../utils/pdfBlob'

/* ============================================================================
   WIR146 — Salles & événements banquets (NTHOT17/NTHOT18/NTHOT19). La
   génération de devis passe TOUJOURS par le flux devis ventes existant
   (`services.generer_devis_evenement`, rule #4 — jamais un moteur parallèle)
   ; le BEO est un document interne régénéré à la demande. Backend complet et
   testé, aucun écran ne le consommait avant ce lot.
   ========================================================================== */

const STATUT_TONE = { brouillon: 'neutral', confirme: 'success', annule: 'danger', termine: 'info' }

const SALLE_VIDE = { nom: '', capacite_max: '' }
const EVENEMENT_VIDE = { nom_evenement: '', date_debut: '', date_fin: '', nb_convives: '', salle: '' }

export default function Banquets() {
  const [salles, setSalles] = useState(null)
  const [evenements, setEvenements] = useState(null)
  const [error, setError] = useState(null)
  const [salleForm, setSalleForm] = useState(SALLE_VIDE)
  const [evenementForm, setEvenementForm] = useState(EVENEMENT_VIDE)
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    Promise.all([hospitalityApi.listSallesEvenement(), hospitalityApi.listEvenementsBanquet()])
      .then(([resSalles, resEvenements]) => {
        setSalles(resSalles.data?.results ?? resSalles.data ?? [])
        setEvenements(resEvenements.data?.results ?? resEvenements.data ?? [])
      })
      .catch(() => setError('Banquets indisponibles.'))
  }

  useEffect(() => { load() }, [])

  const creerSalle = (e) => {
    e.preventDefault()
    if (!salleForm.nom.trim()) return
    setSaving(true)
    hospitalityApi
      .createSalleEvenement(salleForm)
      .then(() => {
        toast.success('Salle créée.')
        setSalleForm(SALLE_VIDE)
        load()
      })
      .catch(() => toast.error('Impossible de créer la salle.'))
      .finally(() => setSaving(false))
  }

  const creerEvenement = (e) => {
    e.preventDefault()
    if (!evenementForm.nom_evenement.trim() || !evenementForm.date_debut || !evenementForm.date_fin) return
    setSaving(true)
    hospitalityApi
      .createEvenementBanquet(evenementForm)
      .then(() => {
        toast.success('Événement créé.')
        setEvenementForm(EVENEMENT_VIDE)
        load()
      })
      .catch((err) => {
        toast.error(err?.response?.data?.salle || "Impossible de créer l'événement.")
      })
      .finally(() => setSaving(false))
  }

  const genererDevis = (evenement) => {
    setBusyId(evenement.id)
    hospitalityApi
      .genererDevisEvenement(evenement.id)
      .then((res) => {
        toast.success(`Devis ${res.data.devis_reference} généré.`)
        load()
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Impossible de générer le devis.'))
      .finally(() => setBusyId(null))
  }

  const telechargerBeo = (evenement) => {
    const pending = openPdfInGesture()
    hospitalityApi
      .beoPdf(evenement.id)
      .then((res) => {
        const blob = new Blob([res.data], { type: 'application/pdf' })
        if (!pending.deliver(blob, `beo-${evenement.id}.pdf`)) {
          toast.error('Ouverture bloquée par le navigateur.')
        }
      })
      .catch(() => toast.error('BEO indisponible.'))
  }

  if (error) return <EmptyState title="Banquets indisponibles" description={error} />
  if (!salles || !evenements) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement des salles et événements…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">Salles événementielles</h2>
        <Card className="flex flex-col gap-3 p-4">
          <form onSubmit={creerSalle} className="flex flex-wrap items-end gap-2">
            <Input
              aria-label="Nom de la salle" placeholder="Nom de la salle"
              value={salleForm.nom} onChange={(e) => setSalleForm({ ...salleForm, nom: e.target.value })}
            />
            <Input
              type="number" aria-label="Capacité maximale" placeholder="Capacité max"
              value={salleForm.capacite_max}
              onChange={(e) => setSalleForm({ ...salleForm, capacite_max: e.target.value })}
            />
            <Button type="submit" disabled={saving || !salleForm.nom.trim()}>Créer</Button>
          </form>
        </Card>
        {salles.length === 0 && <EmptyState title="Aucune salle" description="Ajoutez une première salle." />}
        <div className="flex flex-wrap gap-2">
          {salles.map((s) => (
            <Badge key={s.id} tone="neutral">{s.nom} ({s.capacite_max} pers.)</Badge>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">Événements &amp; banquets</h2>
        <Card className="flex flex-col gap-3 p-4">
          <form onSubmit={creerEvenement} className="flex flex-wrap items-end gap-2">
            <Input
              aria-label="Nom de l'événement" placeholder="Nom de l'événement"
              value={evenementForm.nom_evenement}
              onChange={(e) => setEvenementForm({ ...evenementForm, nom_evenement: e.target.value })}
            />
            <select
              aria-label="Salle" value={evenementForm.salle}
              onChange={(e) => setEvenementForm({ ...evenementForm, salle: e.target.value })}
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
            >
              <option value="">Salle…</option>
              {salles.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
            <Input
              type="datetime-local" aria-label="Début" value={evenementForm.date_debut}
              onChange={(e) => setEvenementForm({ ...evenementForm, date_debut: e.target.value })}
            />
            <Input
              type="datetime-local" aria-label="Fin" value={evenementForm.date_fin}
              onChange={(e) => setEvenementForm({ ...evenementForm, date_fin: e.target.value })}
            />
            <Input
              type="number" aria-label="Nombre de convives" placeholder="Convives"
              value={evenementForm.nb_convives}
              onChange={(e) => setEvenementForm({ ...evenementForm, nb_convives: e.target.value })}
            />
            <Button type="submit" disabled={saving}>Créer</Button>
          </form>
        </Card>

        {evenements.length === 0 && (
          <EmptyState title="Aucun événement" description="Créez votre premier événement." />
        )}
        {evenements.map((ev) => (
          <Card key={ev.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <div className="font-medium">{ev.nom_evenement} — {ev.salle_nom || `Salle #${ev.salle}`}</div>
              <div className="text-sm text-muted-foreground">
                {ev.date_debut} → {ev.date_fin} · {ev.nb_convives} convives
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={STATUT_TONE[ev.statut] || 'neutral'}>{ev.statut_display || ev.statut}</Badge>
              {!ev.devis_ventes_id && (
                <Button disabled={busyId === ev.id} onClick={() => genererDevis(ev)}>
                  {busyId === ev.id ? <Spinner className="size-4" /> : 'Générer le devis'}
                </Button>
              )}
              <Button variant="outline" onClick={() => telechargerBeo(ev)}>BEO (PDF)</Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
