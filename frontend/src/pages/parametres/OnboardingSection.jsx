// FG16 — Onglet « Prise en main » des Paramètres : checklist de configuration
// (3 étapes) avec état FAIT/À FAIRE dérivé des données EXISTANTES (profil
// entreprise, nombre de produits, nombre d'utilisateurs), plus un bouton pour
// revoir le guide d'accueil (coachmarks). Section autonome : charge ses propres
// données, comme le reste des Paramètres. Texte 100 % français. Aucun nouveau
// modèle serveur — on lit les endpoints déjà en place.
import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import { CheckCircle2, Circle, PlayCircle, ArrowRight, RotateCcw } from 'lucide-react'
import stockApi from '../../api/stockApi'
import api from '../../api/axios'
import {
  Card, CardContent, Button, Spinner, Progress,
} from '../../ui'
import { SectionTitle } from './peComponents'
import {
  isCompanyProfileComplete, countFromListResponse, replayCoachmarks,
} from '../../features/onboarding/onboardingHelpers'
import { fetchTours, reviewTour } from '../../features/onboarding/productTours'

// NTDMO16 — libellés FR des 6 tours (mêmes clés que le catalogue serveur
// NTDMO14, `apps/onboarding/services.py::DEFAULT_TOUR_STEPS`).
const TOUR_LABELS = {
  devis: 'Créer un devis',
  leads: 'Suivre vos prospects',
  factures: 'Facturer un client',
  chantiers: 'Suivre un chantier',
  stock: 'Gérer votre catalogue',
  dashboard: 'Votre tableau de bord',
}

// NTDMO16 — bloc « Visites guidées » : statut vu/non-vu des 6 tours par écran
// + bouton « Revoir » par tour (reset MANUEL, pour cet utilisateur seulement).
export function VisitesGuideesBlock() {
  const [tours, setTours] = useState(null)
  const [busyKey, setBusyKey] = useState(null)

  const load = () => { fetchTours({ force: true }).then(setTours) }
  useEffect(() => { load() }, [])

  const onRevoir = async (tourKey) => {
    setBusyKey(tourKey)
    try {
      await reviewTour(tourKey)
      load()
    } finally {
      setBusyKey(null)
    }
  }

  if (!tours) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4 text-primary" /> Chargement des visites guidées…
      </p>
    )
  }

  return (
    <ul className="flex flex-col gap-2">
      {tours.map((t) => (
        <li key={t.tour_key}
            className="flex items-center justify-between gap-3 rounded-lg border border-border p-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            {t.vu ? (
              <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden="true" />
            ) : (
              <Circle className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            )}
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">
                {TOUR_LABELS[t.tour_key] ?? t.tour_key}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {t.vu ? 'Déjà vue' : 'Pas encore vue'}
              </p>
            </div>
          </div>
          <Button type="button" size="sm" variant="outline"
                  disabled={busyKey === t.tour_key}
                  onClick={() => onRevoir(t.tour_key)}>
            <RotateCcw className="size-3.5" aria-hidden="true" /> Revoir
          </Button>
        </li>
      ))}
    </ul>
  )
}

export default function OnboardingSection() {
  // Le profil entreprise est déjà chargé dans le store par la page Paramètres.
  const profile = useSelector(s => s.parametres.profile)
  const [produitCount, setProduitCount] = useState(null)
  const [userCount, setUserCount] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    Promise.allSettled([
      stockApi.getProduits({ page_size: 1 }),
      api.get('/users/'),
    ]).then(([prod, users]) => {
      if (!alive) return
      // En cas d'échec d'une lecture, on laisse null → l'étape reste « à faire »
      // sans jamais casser la page.
      setProduitCount(prod.status === 'fulfilled'
        ? countFromListResponse(prod.value.data) : null)
      setUserCount(users.status === 'fulfilled'
        ? countFromListResponse(users.value.data) : null)
    }).finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const steps = [
    {
      done: isCompanyProfileComplete(profile),
      title: "Complétez le profil de l'entreprise",
      desc: "Nom, adresse et contact — utilisés en en-tête de vos devis et factures.",
      to: '/parametres',
      cta: 'Ouvrir Société & identité',
    },
    {
      done: (produitCount ?? 0) > 0,
      title: 'Créez votre premier produit',
      desc: 'Ajoutez au catalogue un panneau, un onduleur ou un article de pompage.',
      to: '/stock',
      cta: 'Ouvrir le catalogue',
    },
    {
      // « Premier utilisateur invité » = au moins un compte au-delà du vôtre.
      done: (userCount ?? 0) > 1,
      title: 'Invitez un membre de votre équipe',
      desc: "Créez un compte collaborateur et attribuez-lui un rôle.",
      to: '/admin/users',
      cta: "Gérer l'équipe",
    },
  ]

  const doneCount = steps.filter(s => s.done).length
  const pct = Math.round((doneCount / steps.length) * 100)
  const allDone = doneCount === steps.length

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Prise en main"
          icon={<><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>} />
        <p className="mb-4 text-[11.5px] text-muted-foreground">
          Quelques étapes pour bien démarrer. Leur état se met à jour
          automatiquement à mesure que vous configurez votre espace.
        </p>

        {/* Progression globale */}
        <div className="mb-4 rounded-lg border border-border bg-muted/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">
              {allDone ? 'Configuration terminée' : `${doneCount} / ${steps.length} étapes complétées`}
            </span>
            <span className="text-xs text-muted-foreground">{pct} %</span>
          </div>
          <Progress value={pct} tone={allDone ? 'success' : 'primary'} />
        </div>

        {loading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4 text-primary" /> Chargement de l'état…
          </p>
        ) : (
          <ul className="flex flex-col gap-2.5">
            {steps.map((s) => (
              <li key={s.title}
                  className={['flex items-start gap-3 rounded-lg border p-3',
                    s.done ? 'border-success/30 bg-success/8' : 'border-border'].join(' ')}>
                {s.done ? (
                  <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden="true" />
                ) : (
                  <Circle className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{s.title}</p>
                  <p className="mt-0.5 text-[12px] text-muted-foreground">{s.desc}</p>
                </div>
                {!s.done && (
                  <Button asChild size="sm" variant="outline" className="shrink-0">
                    <Link to={s.to}>{s.cta} <ArrowRight className="size-4" aria-hidden="true" /></Link>
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Rejouer le guide d'accueil (coachmarks) */}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <Button type="button" size="sm" variant="secondary" onClick={replayCoachmarks}>
            <PlayCircle className="size-4" aria-hidden="true" /> Revoir le guide d'accueil
          </Button>
          <span className="inline-flex items-center gap-1 text-[11.5px] text-muted-foreground">
            <RotateCcw className="size-3.5" aria-hidden="true" />
            Relance la visite guidée des principales étapes.
          </span>
        </div>

        {/* NTDMO16 — visites guidées PAR ÉCRAN (money-path), statut vu/non-vu
            + « Revoir » par tour (reset pour cet utilisateur seulement). */}
        <div className="mt-4 border-t border-border pt-4">
          <p className="mb-2 text-sm font-medium text-foreground">Visites guidées</p>
          <VisitesGuideesBlock />
        </div>
      </CardContent>
    </Card>
  )
}
