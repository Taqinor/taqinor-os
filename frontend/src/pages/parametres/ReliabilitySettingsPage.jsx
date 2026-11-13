// NTOBS21 — Paramètres → Fiabilité → Réglages : préférences de notification
// et d'affichage de la société (`core.ReliabilitySettings`, singleton GET/PATCH
// `/core/fiabilite/reglages/`). Lecture `fiabilite_voir`, écriture
// `fiabilite_administration` (Directeur/Administrateur toujours) — un refus
// d'écriture s'affiche comme tel, sans casser l'écran.
import { useEffect, useState } from 'react'
import { BellRing } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent, Input, Label, Switch } from '../../ui'
import { toast } from '../../ui/confirm'
import { frErrDetail as frErr } from '../../lib/frErr'
import { PageChargement, PageReglages, FormulaireReglages } from './EtatsSection'
import useFormulaireReglages from './useFormulaireReglages'
import { LectureEchouee } from './SectionEnregistrement'

const DEFAUTS = {
  notifier_maintenance_email: true,
  notifier_quota_email: true,
  notifier_incident_region: '',
  afficher_badge_sla_dashboard: true,
}

const INTERRUPTEURS = [
  {
    cle: 'notifier_maintenance_email',
    titre: 'Prévenir des fenêtres de maintenance',
    aide: 'Annonce 24 h puis 1 h avant chaque maintenance planifiée.',
  },
  {
    cle: 'notifier_quota_email',
    titre: 'Prévenir des quotas',
    aide: "Alerte quand une ressource atteint 80 % puis 100 % de sa limite.",
  },
  {
    cle: 'afficher_badge_sla_dashboard',
    titre: 'Afficher le badge SLA sur le tableau de bord',
    aide: 'Carte « Disponibilité ce mois-ci » du tableau de bord.',
  },
]

function depuisServeur(data) {
  const d = data ?? {}
  return {
    notifier_maintenance_email: d.notifier_maintenance_email ?? true,
    notifier_quota_email: d.notifier_quota_email ?? true,
    notifier_incident_region: d.notifier_incident_region ?? '',
    afficher_badge_sla_dashboard: d.afficher_badge_sla_dashboard ?? true,
  }
}

export default function ReliabilitySettingsPage() {
  const {
    form, setForm, loading, setLoading, saving, setSaving, setField,
  } = useFormulaireReglages(DEFAUTS)
  // AERR56 — lecture rejetée : jamais de formulaire par défaut enregistrable.
  const [lectureEchouee, setLectureEchouee] = useState(false)
  const [essai, setEssai] = useState(0)
  const reessayer = () => { setLectureEchouee(false); setLoading(true); setEssai((n) => n + 1) }

  useEffect(() => {
    let active = true
    parametresApi.getReliabilitySettings()
      .then((r) => { if (active) setForm(depuisServeur(r.data)) })
      .catch((err) => {
        if (active) setLectureEchouee(true)
        toast.error(frErr(err, 'Chargement des réglages de fiabilité impossible.'))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [setForm, setLoading, essai])

  const submit = (e) => {
    e.preventDefault()
    if (lectureEchouee) return
    setSaving(true)
    parametresApi.saveReliabilitySettings(form)
      .then((r) => {
        setForm(depuisServeur(r.data))
        toast.success('Réglages de fiabilité enregistrés.')
      })
      .catch((err) => toast.error(frErr(err, "L'enregistrement a échoué.")))
      .finally(() => setSaving(false))
  }

  if (loading) return <PageChargement />

  return (
    <PageReglages titre="Réglages fiabilité"
      sousTitre="Ce que votre société reçoit et affiche au sujet de la disponibilité du service.">
      {lectureEchouee ? <LectureEchouee onRetry={reessayer} /> : (
      <FormulaireReglages onSubmit={submit} saving={saving}>
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <BellRing className="size-4 text-muted-foreground" aria-hidden="true" />
              Notifications et affichage
            </h2>
            {INTERRUPTEURS.map(({ cle, titre, aide }) => (
              <div key={cle} className="flex items-center justify-between gap-3 rounded-md border p-3">
                <div>
                  <p className="text-sm font-medium">{titre}</p>
                  <p className="text-xs text-muted-foreground">{aide}</p>
                </div>
                <Switch
                  id={`fiab-${cle}`}
                  checked={form[cle]}
                  onCheckedChange={(v) => setField(cle, v)}
                  aria-label={titre}
                />
              </div>
            ))}
            <div className="max-w-sm">
              <Label htmlFor="fiab-region">Région suivie pour les maintenances</Label>
              <Input
                id="fiab-region"
                value={form.notifier_incident_region}
                maxLength={100}
                placeholder="Vide = toutes les régions"
                onChange={(e) => setField('notifier_incident_region', e.target.value)}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Renseignée, seules les maintenances de cette région (ou sans région) sont annoncées.
              </p>
            </div>
          </CardContent>
        </Card>
      </FormulaireReglages>
      )}
    </PageReglages>
  )
}
