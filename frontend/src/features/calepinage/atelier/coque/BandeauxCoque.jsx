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

/* ACAL1907 — au bureau la carte est plein écran SOUS le bandeau d'alertes, et ses contrôles (pile de zoom, plein écran,
   boussole) sont posés à `--cal-libre-haut` : quand une alerte pousse le rail et le panneau vers le bas, ils restaient sous elle
   (le « + » caché). La hauteur occupée par la bande (+ les 16 px d'écart de la coque) est publiée sur la coque,
   `--cal-alertes-h`, que 56-coque-responsive.css ajoute à `--cal-libre-haut`. 0 sans alerte. */
export const ECART_COQUE_PX = 16
function usePublierHauteurAlertes(ref) {
  useEffect(() => {
    const bande = ref.current
    const coque = bande?.closest?.('.cal-coque')
    if (!bande || !coque) return undefined
    const publier = () => {
      const h = bande.offsetHeight
      coque.style.setProperty('--cal-alertes-h', h > 0 ? `${h + ECART_COQUE_PX}px` : '0px')
    }
    publier()
    const obs = typeof ResizeObserver === 'function' ? new ResizeObserver(publier) : null
    obs?.observe(bande)
    return () => { obs?.disconnect(); coque.style.removeProperty('--cal-alertes-h') }
  }, [ref])
}

/* ACAL1733 — « En savoir plus » n'est offert que s'il y a quelque chose à déplier : une seconde alerte (repliée
   par 50-coque-atelier.css) ou un texte tronqué à une ligne. Avant : un bouton fixe qui ne dépliait rien. */
function useADeplier(ref) {
  const [aDeplier, setADeplier] = useState(true) // comme avant tant que rien n'est mesuré
  useEffect(() => {
    const contenu = ref.current?.querySelector('.cal-coque-alertes-contenu')
    if (!contenu) return undefined
    const mesurer = () => setADeplier(
      [...contenu.children].filter((e) => !e.classList.contains('sr-only')).length > 1
      || [...contenu.querySelectorAll('p')].some((p) => p.scrollWidth > p.clientWidth + 1))
    mesurer()
    const obs = typeof ResizeObserver === 'function' ? new ResizeObserver(mesurer) : null
    obs?.observe(contenu)
    return () => obs?.disconnect()
  })
  return aDeplier
}

export function BandeauAlertes({ children, cache = false }) {
  const [deplie, setDeplie] = useState(false)
  const bande = useRef(null)
  usePublierHauteurAlertes(bande)
  const aDeplier = useADeplier(bande)
  return (
    <div ref={bande} className="cal-coque-alertes" data-deplie={deplie ? '1' : '0'} hidden={cache || undefined}>
      <div className="cal-coque-alertes-contenu">{children}</div>
      {(aDeplier || deplie) && (
        <button type="button" className="cal-coque-alertes-plus" aria-expanded={deplie}
          onClick={() => setDeplie((d) => !d)}>
          {deplie ? 'Réduire' : 'En savoir plus'}
        </button>
      )}
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
