// NTDMO25 — Wizard « Créer ma société de démonstration » (3 étapes).
// Réservé aux super-admins TAQINOR (même garde que le reste de l'admin
// technique — le backend refuse 403 hors superuser). Enveloppe
// `seed_demo_company --profil --densite` (défauts = comportement historique
// byte-identique) déclenchée en tâche Celery avec repli synchrone ; la
// progression est pollée sur GET /auth/demo-wizard/statut/.
import { useEffect, useRef, useState } from 'react'
import api from '../../api/axios'
import { Button, Card, Input, Progress, RadioGroup, RadioGroupItem } from '../../ui'
import { toast } from '../../ui/confirm'

const PROFILS = [
  { value: 'residentiel', label: 'Résidentiel uniquement' },
  { value: 'industriel', label: 'Industriel/Commercial uniquement' },
  { value: 'mixte', label: 'Mix complet (3 marchés)' },
]
const DENSITES = [
  { value: 'leger', label: 'Léger (~15 leads)' },
  { value: 'complet', label: 'Complet (~40 leads)' },
]

export default function DemoWizard() {
  const [step, setStep] = useState(1)
  const [slug, setSlug] = useState('')
  const [profil, setProfil] = useState('mixte')
  const [densite, setDensite] = useState('complet')
  const [running, setRunning] = useState(false)
  const [pourcentage, setPourcentage] = useState(0)
  const [statut, setStatut] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const poll = (targetSlug) => {
    pollRef.current = setInterval(() => {
      api.get('/auth/demo-wizard/statut/', { params: { slug: targetSlug } })
        .then((res) => {
          setPourcentage(res.data?.pourcentage ?? 0)
          setStatut(res.data?.statut ?? null)
          if (res.data?.statut === 'termine') {
            clearInterval(pollRef.current)
            setRunning(false)
            toast.success('Société de démonstration générée.')
          }
        })
        .catch(() => {})
    }, 1500)
  }

  const generer = () => {
    const targetSlug = slug.trim() || undefined
    setRunning(true)
    setPourcentage(0)
    setStatut('en_cours')
    api.post('/auth/demo-wizard/', { slug: targetSlug, profil, densite })
      .then((res) => {
        const finalSlug = res.data?.slug || targetSlug
        if (res.data?.statut === 'termine') {
          setPourcentage(100)
          setStatut('termine')
          setRunning(false)
          toast.success('Société de démonstration générée.')
        } else {
          poll(finalSlug)
        }
      })
      .catch(() => {
        setRunning(false)
        toast.error('Impossible de lancer la génération.')
      })
  }

  return (
    <Card className="mx-auto max-w-xl space-y-4 p-6">
      <h1 className="text-lg font-semibold">
        Créer ma société de démonstration
      </h1>
      <p className="text-sm text-muted-foreground">Étape {step} / 3</p>

      {step === 1 && (
        <div className="space-y-3">
          <p className="font-medium">1. Secteur / scénario</p>
          <RadioGroup value={profil} onValueChange={setProfil}>
            {PROFILS.map((p) => (
              <label key={p.value} className="flex items-center gap-2">
                <RadioGroupItem value={p.value} id={`profil-${p.value}`} />
                {p.label}
              </label>
            ))}
          </RadioGroup>
          <Button onClick={() => setStep(2)}>Suivant</Button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-3">
          <p className="font-medium">2. Densité de l'historique</p>
          <RadioGroup value={densite} onValueChange={setDensite}>
            {DENSITES.map((d) => (
              <label key={d.value} className="flex items-center gap-2">
                <RadioGroupItem value={d.value} id={`densite-${d.value}`} />
                {d.label}
              </label>
            ))}
          </RadioGroup>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setStep(1)}>Précédent</Button>
            <Button onClick={() => setStep(3)}>Suivant</Button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-3">
          <p className="font-medium">3. Récapitulatif</p>
          <Input
            placeholder="Identifiant (slug) de la société — optionnel"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
          />
          <ul className="list-disc pl-5 text-sm">
            <li>Profil : {PROFILS.find((p) => p.value === profil)?.label}</li>
            <li>Densité : {DENSITES.find((d) => d.value === densite)?.label}</li>
          </ul>
          {running && (
            <div className="space-y-1" data-testid="demo-wizard-progress">
              <Progress value={pourcentage} />
              <p className="text-xs text-muted-foreground">
                {statut === 'termine' ? 'Terminé' : `${pourcentage}%`}
              </p>
            </div>
          )}
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setStep(2)} disabled={running}>
              Précédent
            </Button>
            <Button onClick={generer} disabled={running}>
              Générer
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
