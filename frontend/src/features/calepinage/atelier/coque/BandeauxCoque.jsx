import { useEffect, useRef, useState } from 'react'
import { BuilderStatut } from '../BuilderPose'

/* ============================================================================
   COQUE — CE QUI CONCERNE LE CALEPINAGE ENTIER, HORS DU PANNEAU D'ÉTAPE.
   - <BandeauAlertes> : brouillon trouvé, lecture seule, dérive du GPS, conception
     rapide, blocages d'enregistrement / conflit — UNE bande compacte sous le bandeau
     du projet (une ligne de texte, ses boutons à droite) ; « En savoir plus » déplie
     l'explication longue. Les composants (et leurs hooks `data-testid`) sont rendus
     tels quels : seule leur mise en page change. Sans alerte, la bande ne se voit pas.
     Le panneau d'étape commence donc à « Étape N sur 5 », comme la maquette.
   - <StatutCarte> : la ligne d'état du constructeur (`#rp9-status`, écrite par le
     script : « Imagerie satellite indisponible — fond neutre… ») en petite pastille en
     bas à DROITE de la carte (aucun calque des maquettes n'y est), fermable ; un
     nouveau message la rouvre (rien n'est caché pour de bon).
   ========================================================================== */

export function BandeauAlertes({ children, cache = false }) {
  const [deplie, setDeplie] = useState(false)
  return (
    <div className="cal-coque-alertes" data-deplie={deplie ? '1' : '0'} hidden={cache || undefined}>
      <div className="cal-coque-alertes-contenu">{children}</div>
      <button type="button" className="cal-coque-alertes-plus" aria-expanded={deplie}
        onClick={() => setDeplie((d) => !d)}>
        {deplie ? 'Réduire' : 'En savoir plus'}
      </button>
    </div>
  )
}

export function StatutCarte() {
  const hote = useRef(null)
  const [masque, setMasque] = useState(false)
  useEffect(() => {
    const statut = hote.current?.querySelector('#rp9-status')
    if (!statut || typeof MutationObserver === 'undefined') return undefined
    const obs = new MutationObserver(() => setMasque(false))
    obs.observe(statut, { childList: true, characterData: true, subtree: true })
    return () => obs.disconnect()
  }, [])
  return (
    <div ref={hote} className="cal-coque-statut" data-masque={masque ? '1' : '0'}>
      <BuilderStatut />
      <button type="button" className="cal-coque-statut-fermer" aria-label="Masquer ce message"
        onClick={() => setMasque(true)}>
        <span aria-hidden="true">×</span>
      </button>
    </div>
  )
}
