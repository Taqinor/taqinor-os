// VISITE-QUALIF — étape « Qualification client » à la fin de la visite
// terrain (wizard VT5/VT6/VT7). 6 questions à un tap (chips larges, DÉFAUT
// TOUJOURS pré-sélectionné — rapide, utilisable mains gantées) + un champ
// texte conditionnel (« Quoi changer ? », requis seulement si le devis ne
// convient pas) + un conseil de closing en texte libre optionnel.
//
// RÈGLE fondateur erreurs (`errors_point_at_field_rule`) : jamais un message
// générique — la garde client (devis_details manquant) ET les erreurs 400 du
// serveur (`POST .../qualification/` → `{champ: message}`) s'affichent TOUTES
// deux SOUS le champ fautif exact, via le même état `erreurs`.
//
// Lecture seule (visite `validée`) : rendu en résumé texte, jamais les chips
// interactives — mêmes libellés que `visiteHelpers.labelQualification`.
import { useState } from 'react'
import visitesApi from '../../api/visitesApi'
import { Button, Card, Input, Label, Textarea } from '../../ui'
import { toast } from '../../ui/confirm'
import { cn } from '../../lib/cn'
import { QUALIFICATION_SCHEMA, QUALIFICATION_DEFAULTS, labelQualification } from './visiteHelpers'
import MicDicteeButton from '../../components/MicDicteeButton'

const toForm = (qualification) => ({
  temperature: qualification?.temperature ?? QUALIFICATION_DEFAULTS.temperature,
  devis: qualification?.devis ?? QUALIFICATION_DEFAULTS.devis,
  devis_details: qualification?.devis_details ?? '',
  decideur: qualification?.decideur ?? QUALIFICATION_DEFAULTS.decideur,
  frein: qualification?.frein ?? QUALIFICATION_DEFAULTS.frein,
  declencheur: qualification?.declencheur ?? QUALIFICATION_DEFAULTS.declencheur,
  rappel: qualification?.rappel ?? QUALIFICATION_DEFAULTS.rappel,
  conseil_closing: qualification?.conseil_closing ?? '',
})

// Groupe de chips larges à un tap — sélection unique, valeur toujours définie
// (le défaut est déjà dans `value` avant toute interaction).
function ChipQuestion({ id, question, aide, options, value, onChange, disabled }) {
  return (
    <div>
      <p id={id} className="text-sm font-medium">{question}</p>
      <div className="mt-2 flex flex-wrap gap-2" role="group" aria-labelledby={id}>
        {options.map((o) => {
          const actif = value === o.value
          return (
            <button
              key={o.value}
              type="button"
              aria-pressed={actif}
              disabled={disabled}
              onClick={() => onChange(o.value)}
              className={cn(
                'min-h-11 rounded-full border px-4 py-2 text-sm font-medium transition-colors',
                'focus-ring disabled:cursor-not-allowed disabled:opacity-60',
                actif
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-input bg-card text-foreground hover:bg-accent',
              )}
            >
              {o.label}
            </button>
          )
        })}
      </div>
      {aide && <p className="mt-1 text-xs text-muted-foreground">{aide}</p>}
    </div>
  )
}

// Résumé lecture seule (visite validée, ou verrouillée pour toute autre
// raison serveur) — mêmes libellés FR que le formulaire, jamais recalculés.
function QualificationResume({ qualification }) {
  if (!qualification) {
    return <p className="text-sm text-muted-foreground">Qualification non renseignée.</p>
  }
  return (
    <dl className="grid grid-cols-1 gap-x-3 gap-y-1 text-sm sm:grid-cols-2">
      {QUALIFICATION_SCHEMA.map((q) => (
        <div key={q.key} className="contents">
          <dt className="text-muted-foreground">{q.question}</dt>
          <dd>{labelQualification(q.key, qualification[q.key])}</dd>
        </div>
      ))}
      {qualification.devis !== 'convient' && qualification.devis_details && (
        <div className="contents">
          <dt className="text-muted-foreground">Quoi changer ?</dt>
          <dd>{qualification.devis_details}</dd>
        </div>
      )}
      {qualification.conseil_closing && (
        <div className="contents">
          <dt className="text-muted-foreground">Conseil closing</dt>
          <dd>{qualification.conseil_closing}</dd>
        </div>
      )}
    </dl>
  )
}

export default function VisiteQualificationForm({ visiteId, qualification, lectureSeule, onSaved }) {
  const [form, setForm] = useState(() => toForm(qualification))
  const [erreurs, setErreurs] = useState({})
  const [saving, setSaving] = useState(false)

  const setChamp = (key, v) => {
    setForm((prev) => ({ ...prev, [key]: v }))
    setErreurs((prev) => (prev[key] ? { ...prev, [key]: undefined } : prev))
  }

  if (lectureSeule) {
    return (
      <Card className="mb-3 p-3" data-testid="visite-qualification">
        <p className="text-sm font-medium">Qualification client</p>
        <div className="mt-2">
          <QualificationResume qualification={qualification} />
        </div>
      </Card>
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    // Garde CLIENT : même règle que le serveur (devis_details requis dès que
    // le devis ne convient pas), pour éviter l'aller-retour réseau évitable —
    // mais le message reste SOUS le champ, jamais un toast générique.
    if (form.devis !== 'convient' && !form.devis_details.trim()) {
      setErreurs((prev) => ({ ...prev, devis_details: 'Précisez ce qu’il faut changer.' }))
      return
    }
    setSaving(true)
    setErreurs({})
    const payload = {
      temperature: form.temperature,
      devis: form.devis,
      devis_details: form.devis !== 'convient' ? form.devis_details.trim() : '',
      decideur: form.decideur,
      frein: form.frein,
      declencheur: form.declencheur,
      rappel: form.rappel,
      conseil_closing: form.conseil_closing.trim(),
    }
    try {
      const res = await visitesApi.qualifierVisite(visiteId, payload)
      onSaved?.(res.data)
      toast.success('Qualification enregistrée.')
    } catch (err) {
      // Revue Fable (15/09) — le serveur ENVELOPPE toujours ses erreurs de
      // champ : {erreurs: {champ: [message]}} (même forme que mesures/ —
      // voir VisiteMesuresForm). Lire l'objet nu rendait tout 400 muet.
      const enveloppe = err?.response?.data?.erreurs
      if (enveloppe && typeof enveloppe === 'object') {
        setErreurs(Object.fromEntries(Object.entries(enveloppe).map(
          ([champ, messages]) => [champ,
            Array.isArray(messages) ? messages[0] : String(messages)],
        )))
      } else {
        toast.error('Enregistrement de la qualification impossible.')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="mb-3 p-3" data-testid="visite-qualification">
      <form noValidate onSubmit={submit} className="space-y-4">
        <p className="text-sm font-medium">Qualification client</p>
        {QUALIFICATION_SCHEMA.map((q) => (
          <div key={q.key}>
            <ChipQuestion
              id={`visite-qualif-${q.key}`}
              question={q.question}
              aide={q.aide}
              options={q.options}
              value={form[q.key]}
              onChange={(v) => setChamp(q.key, v)}
            />
            {erreurs[q.key] && (
              <p role="alert" className="mt-1 text-xs text-destructive">{erreurs[q.key]}</p>
            )}
            {q.key === 'devis' && form.devis !== 'convient' && (
              <div className="mt-2">
                <Label htmlFor="visite-qualif-devis-details">Quoi changer ?</Label>
                <Input
                  id="visite-qualif-devis-details"
                  value={form.devis_details}
                  maxLength={300}
                  aria-invalid={erreurs.devis_details ? 'true' : undefined}
                  onChange={(e) => setChamp('devis_details', e.target.value)}
                />
                {erreurs.devis_details && (
                  <p role="alert" className="mt-1 text-xs text-destructive">{erreurs.devis_details}</p>
                )}
              </div>
            )}
          </div>
        ))}
        <div>
          <Label htmlFor="visite-qualif-conseil">Conseil pour l’appel de closing</Label>
          <div className="flex items-start gap-2">
            <Textarea
              id="visite-qualif-conseil"
              value={form.conseil_closing}
              maxLength={500}
              placeholder="Ce qui l’a fait vibrer, ce qu’il faut éviter…"
              onChange={(e) => setChamp('conseil_closing', e.target.value)}
              className="flex-1"
            />
            {/* Dictée : mise à jour FONCTIONNELLE — plusieurs résultats
                finaux s'enchaînent dans une même dictée, un état capturé au
                rendu perdrait les segments précédents. */}
            <MicDicteeButton
              onTexte={(texte) => setForm((prev) => ({
                ...prev,
                conseil_closing: prev.conseil_closing
                  ? `${prev.conseil_closing} ${texte}` : texte,
              }))}
            />
          </div>
        </div>
        <Button type="submit" size="sm" disabled={saving}>Enregistrer la qualification</Button>
      </form>
    </Card>
  )
}
