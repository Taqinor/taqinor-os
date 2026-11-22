// ACAL589 — l'onglet « Plan » de « Ma journée » : le plan de pose du
// calepinage RETENU du chantier (`GET chantiers/<id>/plan-pose/`, contrat
// `installations/calepinage_plan_pose.json`), lisible aussi réseau coupé.
// - en ligne : la réponse est gardée par `readCache.put('plan_pose', id, …)` ;
// - réseau coupé : le même onglet relit `readCache.get('plan_pose', id)` et le
//   bandeau dit « Données hors-ligne, dernière synchro à HH:MM » (jamais un
//   ancien plan sans sa mention d'âge) ;
// - sans plan (`plan_pose_svg: null`) : le `motif` servi, tel quel.
// Le SVG est affiché dans une <img> d'URL data:image/svg+xml — jamais injecté
// dans le DOM, aucun script ne peut s'y exécuter. Défilable, et zoomable au
// pincement (le navigateur zoome l'image ; `touch-action` laisse le geste).
import { useEffect, useState } from 'react'
import installationsApi from '../../api/installationsApi'
import { readCache } from '../offlinesync/readCache'
import DonneesHorsLigneBanner from '../offlinesync/DonneesHorsLigneBanner'

const imageDuSvg = (svg) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`

export default function PlanPoseTerrain({ installationId }) {
  // { plan, cachedAt } une fois lu ; `erreur` si ni le serveur ni le cache.
  const [etat, setEtat] = useState({ plan: null, cachedAt: null, erreur: false, charge: false })

  useEffect(() => {
    if (!installationId) return undefined
    let actif = true
    installationsApi.getPlanPose(installationId)
      .then((r) => {
        const plan = r?.data ?? null
        readCache.put('plan_pose', installationId, plan)
          .catch(() => console.warn('PlanPoseTerrain : cache de lecture indisponible'))
        if (actif) setEtat({ plan, cachedAt: null, erreur: false, charge: true })
      })
      .catch(() => readCache.get('plan_pose', installationId).catch(() => null).then((entree) => {
        if (!actif) return
        setEtat(entree
          ? { plan: entree.data, cachedAt: entree.cachedAt, erreur: false, charge: true }
          : { plan: null, cachedAt: null, erreur: true, charge: true })
      }))
    return () => { actif = false }
  }, [installationId])

  if (!installationId) {
    return <p className="text-sm text-muted-foreground">Aucun chantier rattaché : pas de plan de pose.</p>
  }
  if (!etat.charge) return <p className="text-sm text-muted-foreground">Chargement du plan…</p>
  if (etat.erreur) {
    return (
      <p className="text-sm text-muted-foreground" role="status" data-testid="plan-pose-indisponible">
        Plan de pose indisponible : réseau coupé et plan jamais ouvert sur ce téléphone.
      </p>
    )
  }
  const { plan, cachedAt } = etat
  return (
    <div className="flex flex-col gap-2" data-testid="plan-pose-terrain">
      <DonneesHorsLigneBanner cachedAt={cachedAt} />
      {plan?.plan_pose_svg ? (
        <div className="max-h-[70vh] overflow-auto rounded-md border border-border bg-background"
             style={{ touchAction: 'pan-x pan-y pinch-zoom' }}>
          <img src={imageDuSvg(plan.plan_pose_svg)} alt="Plan de pose du chantier"
               data-testid="plan-pose-image" className="block h-auto min-w-full max-w-none" />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground" role="status" data-testid="plan-pose-motif">
          {plan?.motif || 'Aucun plan de pose servi.'}
        </p>
      )}
    </div>
  )
}
