import { useMemo } from 'react'
import { Briefcase, Trophy, Wallet, Layers, Gauge } from 'lucide-react'
import aoApi from '../../api/aoApi'
import useResource from '../../hooks/useResource'
import { ModuleDashboard, EcheanceCenter } from '../../ui/module'
import { formatMAD, formatNumber, formatPercent, toNumber } from '../../lib/format'

/* ============================================================================
   AOF172 — Tableau de bord AO + centre d'échéances.
   ----------------------------------------------------------------------------
   `ModuleDashboard` + `EcheanceCenter` alimentés par l'appel agrégé UNIQUE
   d'AOF166 (`GET /ao/tableau-marches/` — nom d'endpoint et selector repris
   nominativement de NTMAR27, cf. `docs/plans/PLAN_FINANCE.md:660`, pour
   éviter deux tableaux de bord AO concurrents).

   CONTRAT SERVEUR — la seule vérité est `apps/ao/selectors.py::tableau_marches`
   (et son jumeau `tableau_marches_vide`, qui publie les mêmes clés à zéro) :

     en_cours              {total, sous_7_jours, en_retard, par_echeance:[…]}
     echeances_dues        ENTIER (un len(), PAS une liste)
     reussite              {gagnes, perdus, total_decides, total_resultats,
                            taux_reussite_pct}
     capacite              {demontree_modules, engagee_modules, ecart_modules,
                            toitures_prouvees}
     cautions              {montant_immobilise, nombre,
                            expirant_avant_ouverture}
     marches_en_execution  {total, montant_offre_ht}

   Cet écran a planté en production (03/08/2026) parce qu'il lisait des clés
   PLATES inexistantes (`ao_en_cours`, `taux_reussite`, …), rendait l'OBJET
   `marches_en_execution` comme enfant React et appelait `.map()` sur l'ENTIER
   `echeances_dues`. Règle qui en découle et qui tient ce fichier : chaque
   valeur affichée est LUE dans le bloc qui la porte et passe par un
   formateur qui rend TOUJOURS une chaîne ou un nombre — jamais un objet.

   AUCUN calcul de KPI côté front : chaque stat est une LECTURE directe du
   payload agrégé (au plus un arrondi/formatage d'affichage), y compris les
   jours restants du centre d'échéances (`jours_restants`, calculé serveur).
   `EcheanceCenter` porte lui-même les seuils d'urgence (`ui/module/urgency.js`)
   : ce fichier ne définit AUCUNE constante de seuil locale.
   ========================================================================== */

/** Entier d'affichage — garantit qu'un bloc reçu par erreur ne part JAMAIS
    dans le JSX comme objet (c'était le crash de production). */
const entier = (valeur) => toNumber(valeur) ?? 0

export default function DashboardPage() {
  const { data, loading, error } = useResource(
    () => aoApi.tableauMarches(),
    undefined,
    {
      select: (res) => res.data,
      errorMessage: 'Impossible de charger le tableau de bord.',
    },
  )

  const stats = useMemo(() => {
    if (!data) return []
    const enCours = data.en_cours ?? {}
    const reussite = data.reussite ?? {}
    const cautions = data.cautions ?? {}
    const marches = data.marches_en_execution ?? {}
    const capacite = data.capacite ?? {}

    const demontree = entier(capacite.demontree_modules)
    const engagee = entier(capacite.engagee_modules)

    return [
      {
        label: 'AO en cours', icon: Briefcase,
        value: entier(enCours.total), to: '/ao/affaires',
        hint: `${entier(enCours.sous_7_jours)} sous 7 jours · ${entier(enCours.en_retard)} en retard`,
      },
      {
        label: 'Taux de réussite', icon: Trophy,
        // Calculé serveur depuis ResultatAO (jamais saisi, jamais recalculé ici).
        value: formatPercent(reussite.taux_reussite_pct),
        hint: `${entier(reussite.gagnes)} gagnés · ${entier(reussite.perdus)} perdus`,
      },
      {
        label: 'Cautions immobilisées', icon: Wallet,
        value: formatMAD(cautions.montant_immobilise, { decimals: 0 }),
        hint: `${entier(cautions.nombre)} caution(s) · ${entier(cautions.expirant_avant_ouverture)} expirant avant ouverture`,
      },
      {
        label: 'Marchés en exécution', icon: Layers,
        value: entier(marches.total),
        hint: `${formatMAD(marches.montant_offre_ht, { decimals: 0 })} d'offre HT`,
      },
      {
        label: 'Capacité vs engagement', icon: Gauge,
        value: `${formatNumber(demontree)} / ${formatNumber(engagee)}`,
        hint: `modules démontrés vs engagés · écart ${formatNumber(entier(capacite.ecart_modules))}`,
      },
    ]
  }, [data])

  /* Le centre d'échéances est alimenté par LE MÊME payload agrégé (jamais une
     seconde requête réseau) : `en_cours.par_echeance` est la VRAIE liste que
     rend le serveur — les AO en cours rangés par date limite de remise, « la
     seule qui fait perdre » (commentaire du selector). `echeances_dues`, lui,
     est un COMPTEUR de rappels dus : il s'affiche comme un compteur, en
     suffixe du titre — on ne peut pas itérer un entier. */
  const echeances = useMemo(() => {
    const lignes = Array.isArray(data?.en_cours?.par_echeance)
      ? data.en_cours.par_echeance
      : []
    return lignes
      .filter((ligne) => ligne && ligne.date_limite)
      .map((ligne) => ({
        id: ligne.id,
        label: ligne.objet || ligne.reference || 'Appel d’offres',
        date: ligne.date_limite,
        // Jours restants CALCULÉS SERVEUR : on les relaie tels quels.
        daysLeft: typeof ligne.jours_restants === 'number' ? ligne.jours_restants : undefined,
        meta: [ligne.reference, ligne.acheteur, ligne.statut_display]
          .filter(Boolean).join(' · '),
        to: ligne.id != null ? `/ao/affaires/${ligne.id}` : undefined,
      }))
  }, [data])

  const titreEcheances = useMemo(() => {
    const dues = entier(data?.echeances_dues)
    if (!dues) return 'Échéances de remise'
    // « dû » au singulier, « dus » au pluriel (l'accent circonflexe tombe).
    return `Échéances de remise — ${dues} ${dues > 1 ? 'rappels dus' : 'rappel dû'}`
  }, [data])

  return (
    <div className="flex flex-col gap-6">
      <ModuleDashboard stats={stats} loading={loading} error={error} accent="var(--module-accent-brass)" />
      <EcheanceCenter
        title={titreEcheances}
        items={echeances}
        loading={loading}
        error={error}
        max={8}
        emptyText="Aucun appel d’offres en cours avec une date limite de remise."
      />
    </div>
  )
}
