// SPL216 — DOM complet du builder (rp9-*), déplacé VERBATIM depuis
// pages/ventes/ToitureDesign.jsx (move only : le JSX est inchangé ; seuls
// l'enveloppe du composant et les imports sont ajoutés, l'état arrive en props
// NOMMÉES). Mêmes ids, MÊME ORDRE des enfants (consommés par roofPro11/layoutEditor.ts).
// Coque (22/11) — le DOM est DÉCOUPÉ en quatre groupes DÉPLACÉS tels quels (BuilderCarte,
// BuilderOutils, BuilderToit, BuilderPose) : chaque groupe garde son sous-arbre entier (hôtes
// `parentElement`, ancres `insertAdjacentElement`). Ce fichier les remet DANS LE MÊME ORDRE, dans
// la même carte, pour le mode lead (DOM identique, golden inchangé) ; la coque du module les place
// elle-même (carte au centre, le reste dans le panneau) — toujours montés, jamais démontés.
import BuilderCarte from './BuilderCarte'
import BuilderOutils from './BuilderOutils'
import BuilderToit from './BuilderToit'
import BuilderPose, { BuilderStatut } from './BuilderPose'

export default function BuilderDom(props) {
  return (
    <>
        {/* BUILDER — DOM complet (mêmes ids que la preview pro-11). */}
        <div className="rounded-xl border border-border bg-card mt-6 overflow-hidden">
          <BuilderCarte {...props} />
          <BuilderOutils {...props} />
          <BuilderToit {...props} />
          <BuilderPose {...props} />
          <BuilderStatut />
        </div>
    </>
  )
}
