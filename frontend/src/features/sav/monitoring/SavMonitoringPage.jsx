// D-ASAV-4 option (b) (ASAV93, Reda 08/10/2026) — écran SAV/monitoring :
// les fonctions monitoring jusque-là dormantes (sans route ni écran) rendues
// utilisables. Responsable/admin (route gardée par le module SAV, chaque
// endpoint gardé côté serveur). Une section par fonction :
//   * ASAV100 — abonnements de supervision (création, résiliation) ;
//   * ASAV101 — SLA de disponibilité (taux garanti saisi, écart, pénalité) ;
//   * ASAV102 — registre des certificats carbone (émission mesurée) ;
//   * ASAV103 — pertes de production catégorisées d'un système.
import { TooltipProvider } from '../../../ui'
import useSupervisedSystems from '../../../pages/monitoring/useSupervisedSystems'
import AbonnementsSection from './AbonnementsSection'
import SlaDisponibiliteSection from './SlaDisponibiliteSection'
import CertificatsCarboneSection from './CertificatsCarboneSection'
import PertesCategoriseesSection from './PertesCategoriseesSection'

export default function SavMonitoringPage() {
  const { systems, loading } = useSupervisedSystems()
  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-5xl flex-col gap-5 p-1">
        <header>
          <h1 className="font-display text-2xl font-bold tracking-tight">Monitoring</h1>
          <p className="text-sm text-muted-foreground">
            Supervision du parc installé : abonnements et suivi contractuel.
          </p>
        </header>
        <AbonnementsSection systems={systems} loadingSystems={loading} />
        <SlaDisponibiliteSection systems={systems} loadingSystems={loading} />
        <CertificatsCarboneSection systems={systems} loadingSystems={loading} />
        <PertesCategoriseesSection systems={systems} loadingSystems={loading} />
      </div>
    </TooltipProvider>
  )
}
