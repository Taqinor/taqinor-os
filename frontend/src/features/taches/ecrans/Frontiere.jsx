import { Suspense, useEffect } from 'react'

import SqueletteListe from '../ui/SqueletteListe'
import { prechargerEcrans } from './precharger'

/* ============================================================================
   R4-41 — pas de page blanche au premier passage sur un écran. Chaque écran est un morceau chargé à la demande ; tant
   qu'il n'est pas arrivé, le repli du routeur de l'ERP (hors du module) remplaçait TOUT : la coque du module (`.tch`)
   disparaissait, la barre de l'ERP revenait, l'onglet actif repassait à l'or (mesuré : ≈ 280 ms sur 4G). Ici chaque écran
   porte SA frontière de chargement, DANS le module : le repli est la coquille (en-tête, titre, squelette), sous la même
   enveloppe `.route-fade > .tch` — les règles de l'enveloppe (base.css) tiennent donc pendant le chargement.
   Le repli est volontairement minuscule : il vit dans le morceau commun du module.
   ========================================================================== */

/** Le repli d'un écran en chargement : la coquille du module, à la même place que la vraie (rangée du haut sur iPhone,
 *  sur-titre, grand titre au même pixel), puis le squelette. `titre` absent (la page d'un projet : son nom n'est pas
 *  encore connu) : une barre à la place du titre. */
function ChargementEcran({ ecran, titre = null, pleine = false }) {
  return (
    <div className="tch tch-chargement" data-ecran={ecran} data-largeur={pleine ? 'pleine' : undefined} aria-busy="true">
      <div className="tch-page">
        <header className="entete">
          <div className="entete-barre" />
          <div className="entete-titres">
            <div className="entete-surtitre" />
            {/* ni titre de niveau 1 ni texte lu : l'écran réel pose le sien dans quelques instants (le squelette annonce « Chargement ») */}
            <p className="entete-titre" aria-hidden="true">{titre ?? <span className="os titre-os" />}</p>
          </div>
        </header>
        <SqueletteListe />
      </div>
    </div>
  )
}

/** La frontière de chargement d'un écran, DANS le module ; son montage lance le préchargement des autres. */
export default function Frontiere({ ecran, titre, pleine, children }) {
  useEffect(() => { prechargerEcrans() }, [])
  return <Suspense fallback={<ChargementEcran ecran={ecran} titre={titre} pleine={pleine} />}>{children}</Suspense>
}
