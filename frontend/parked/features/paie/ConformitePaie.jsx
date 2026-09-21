import { useEffect, useState } from 'react'
import { ShieldCheck, AlertTriangle, CalendarClock, FileWarning } from 'lucide-react'
import api from '../../api/axios'
import { Card, Badge, Spinner, EmptyState, toast, DataTable } from '../../ui'

/* ============================================================================
   NTPAY16 — Cockpit de conformité paie.
   ----------------------------------------------------------------------------
   UN écran pour l'état de conformité, agrégé côté serveur
   (`/paie/periodes/conformite/`, sélecteur `cockpit_conformite_paie`) :
   échéances déclaratives en retard / à venir (XPAI6), preuves de dépôt
   manquantes (NTPAY5), barèmes non validés par le fondateur, périodes
   ouvertes en retard de clôture (ZPAI12) et avertissements pré-run bloquants
   (ZPAI2).

   Rien n'est recalculé ici : l'écran AFFICHE ce que le serveur dit. Une
   société à jour affiche « Conforme ».
   ========================================================================== */

const MOIS = [
  '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
  'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

const libellePeriode = (r) => (
  r?.mois >= 1 && r?.mois <= 12 ? `${MOIS[r.mois]} ${r.annee}` : `${r?.annee ?? ''}`
)

export default function ConformitePaie() {
  const [etat, setEtat] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = () =>
    api.get('/paie/periodes/conformite/')
      .then((r) => setEtat(r.data))
      .catch(() => toast.error('Chargement de l’état de conformité impossible.'))
      .finally(() => setLoading(false))

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }

  if (!etat) {
    return (
      <EmptyState
        icon={FileWarning}
        title="État de conformité indisponible"
        description="Réessayez dans un instant."
      />
    )
  }

  const colonnesEcheances = [
    { id: 'libelle', header: 'Déclaration', accessor: (r) => r.libelle },
    {
      id: 'periode', header: 'Période', width: 160,
      accessor: (r) => libellePeriode(r),
    },
    {
      id: 'date_limite', header: 'Date limite', width: 140,
      accessor: (r) => r.date_limite,
    },
    {
      id: 'jours', header: 'Échéance', width: 150,
      accessor: (r) => r.jours,
      cell: (_v, r) => (
        <Badge tone={r.jours < 0 ? 'danger' : 'warning'}>
          {r.jours < 0
            ? `${Math.abs(r.jours)} j de retard`
            : `dans ${r.jours} j`}
        </Badge>
      ),
    },
  ]

  const colonnesBaremes = [
    { id: 'libelle', header: 'Jeu versionné', accessor: (r) => r.libelle },
    {
      id: 'date_effet', header: 'Date d’effet', width: 150,
      accessor: (r) => r.date_effet,
    },
  ]

  const colonnesPeriodes = [
    {
      id: 'periode', header: 'Période', accessor: (r) => libellePeriode(r),
    },
    { id: 'statut', header: 'Statut', width: 140, accessor: (r) => r.statut },
  ]

  const colonnesPreRun = [
    {
      id: 'periode', header: 'Période', accessor: (r) => libellePeriode(r),
    },
    {
      id: 'bloquants', header: 'Bloquants', width: 120,
      accessor: (r) => r.bloquants,
      cell: (v) => <Badge tone={v > 0 ? 'danger' : 'neutral'}>{v}</Badge>,
    },
    {
      id: 'avertissements', header: 'Avertissements', width: 150,
      accessor: (r) => r.avertissements,
    },
  ]

  const sections = [
    {
      cle: 'echeances_en_retard', titre: 'Échéances déclaratives en retard',
      colonnes: colonnesEcheances, ton: 'danger',
    },
    {
      cle: 'depots_manquants', titre: 'Preuves de dépôt manquantes',
      colonnes: colonnesEcheances, ton: 'danger',
    },
    {
      cle: 'periodes_en_retard', titre: 'Périodes ouvertes en retard de clôture',
      colonnes: colonnesPeriodes, ton: 'danger',
    },
    {
      cle: 'baremes_non_valides', titre: 'Barèmes non validés par le fondateur',
      colonnes: colonnesBaremes, ton: 'warning',
    },
    {
      cle: 'alertes_pre_run', titre: 'Avertissements avant de payer',
      colonnes: colonnesPreRun, ton: 'warning',
    },
    {
      cle: 'echeances_a_venir', titre: 'Échéances à venir (30 jours)',
      colonnes: colonnesEcheances, ton: 'neutral',
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Conformité paie
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Échéances déclaratives, preuves de dépôt, barèmes à valider et
          clôtures en retard — en un seul endroit.
        </p>
      </div>

      <Card className="flex items-center gap-3 p-4 sm:p-5">
        {etat.conforme ? (
          <>
            <ShieldCheck className="size-6 text-emerald-600" aria-hidden="true" />
            <div>
              <p className="font-medium">Conforme</p>
              <p className="text-sm text-muted-foreground">
                Aucune échéance en retard, aucune preuve manquante, aucun
                barème en attente de validation.
              </p>
            </div>
          </>
        ) : (
          <>
            <AlertTriangle className="size-6 text-amber-600" aria-hidden="true" />
            <div>
              <p className="font-medium">Points à traiter</p>
              <p className="text-sm text-muted-foreground">
                Les listes ci-dessous détaillent ce qui reste à régulariser.
              </p>
            </div>
          </>
        )}
      </Card>

      {sections.map((section) => {
        const lignes = etat[section.cle] || []
        if (lignes.length === 0) return null
        return (
          <Card key={section.cle} className="p-4 sm:p-5">
            <div className="mb-3 flex items-center gap-2">
              <CalendarClock className="size-4 text-muted-foreground" aria-hidden="true" />
              <h2 className="font-medium">{section.titre}</h2>
              <Badge tone={section.ton}>{lignes.length}</Badge>
            </div>
            <DataTable data={lignes} columns={section.colonnes} />
          </Card>
        )
      })}
    </div>
  )
}
