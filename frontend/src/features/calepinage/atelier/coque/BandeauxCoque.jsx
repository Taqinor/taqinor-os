import { useEffect, useRef, useState } from 'react'
import { BuilderStatut } from '../BuilderPose'
import { usePointARegler } from '../../commun/lecturePretAEnvoyer'

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
  const mesure = useRef(null)
  useEffect(() => {
    const contenu = ref.current?.querySelector('.cal-coque-alertes-contenu')
    if (!contenu) return undefined
    const mesurer = () => setADeplier(
      [...contenu.children].filter((e) => !e.classList.contains('sr-only')).length > 1
      || [...contenu.querySelectorAll('p')].some((p) => p.scrollWidth > p.clientWidth + 1))
    mesure.current = mesurer
    // UN seul observateur par montage (jamais un nouveau à chaque rendu) ; la mutation voit une alerte ajoutée ou retirée.
    const obs = typeof ResizeObserver === 'function' ? new ResizeObserver(mesurer) : null
    obs?.observe(contenu)
    const mutation = typeof MutationObserver === 'function' ? new MutationObserver(mesurer) : null
    mutation?.observe(contenu, { childList: true, subtree: true, characterData: true })
    return () => { mesure.current = null; obs?.disconnect(); mutation?.disconnect() }
  }, [ref])
  // Chaque rendu relit seulement la mesure (aucun observateur créé ici).
  useEffect(() => { mesure.current?.() })
  return aDeplier
}

/* ACAL1980 — « module absent du catalogue » : le script (zones.ts::direRefusModule) écrit le motif dans
   `#rp9-pan-module-erreur` et le marque `data-ton="a-regler"`. Avant, il n'apparaissait que dans la pilule grise du bas de
   carte. La bande le dit au ton « À régler », avec le geste de réparation (choisir un module à l'étape Panneaux, où se
   trouve le sélecteur — qui, lui, porte déjà le motif : la bande ne le répète pas là). */
function useMotifARegler(ref) {
  const [motif, setMotif] = useState(null)
  useEffect(() => {
    const racine = ref.current?.closest?.('.cal-coque') ?? document
    const lire = () => {
      const noeud = racine.querySelector('#rp9-pan-module-erreur[data-code]')
      const etape = racine.getAttribute?.('data-etape')
      const texte = noeud && !noeud.hidden && etape !== 'panneaux' ? (noeud.textContent ?? '').trim() : ''
      // Deux causes, deux gestes : `module-absent` (choisir un module) ≠ `catalogue-illisible` (relire le catalogue).
      const reessayable = Boolean(racine.querySelector?.('[data-testid="cal-reessayer-lecture"]'))
      setMotif(texte ? { texte, code: noeud.dataset.code ?? 'module-absent', reessayable } : null)
    }
    lire()
    if (typeof MutationObserver === 'undefined') return undefined
    const obs = new MutationObserver(lire)
    obs.observe(racine, { subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ['hidden', 'data-ton', 'data-etape'] })
    return () => obs.disconnect()
  }, [ref])
  return motif
}

/* ACAL1980 (revue) — la bande ne dit « À régler » que si la lecture servie « Prêt à envoyer ? » liste AUSSI le point
   (code `materiel_designe`) : le rail compte sur la même liste. Sinon c'est une information qu'on peut traiter, dite
   comme telle, pour que la bande et le rail ne se contredisent pas. Un catalogue illisible n'est jamais « À régler » :
   le module n'est pas retiré, il n'a pas pu être vérifié. */
function LigneModule({ motif, calepinageId, bande }) {
  const compte = usePointARegler(calepinageId, 'materiel_designe')
  if (motif.code === 'catalogue-illisible') {
    const coque = () => bande.current?.closest?.('.cal-coque')
    const reessayer = () => coque()?.querySelector?.('[data-testid="cal-reessayer-lecture"]')?.click()
    return (
      <div className="cal-alerte-entiere" data-testid="cal-catalogue-illisible" data-ton="info">
        <p><strong>Catalogue des modules illisible</strong></p>
        <p>{motif.texte}</p>
        {motif.reessayable && <div><button type="button" onClick={reessayer}>Réessayer</button></div>}
      </div>
    )
  }
  const allerAuxPanneaux = () => bande.current?.closest?.('.cal-coque')?.querySelector?.('[data-testid="cal-etape-panneaux"]')?.click()
  return (
    <div className="cal-alerte-entiere" data-testid="cal-a-regler-module" data-ton={compte ? 'a-regler' : 'info'}>
      <p><strong>{compte ? 'À régler' : 'Module retiré du catalogue — choisissez-en un'}</strong></p>
      <p>{motif.texte}</p>
      <div>
        <button type="button" onClick={allerAuxPanneaux}>Choisir un module</button>
      </div>
    </div>
  )
}

export function BandeauAlertes({ children, cache = false, calepinageId = null }) {
  const [deplie, setDeplie] = useState(false)
  const bande = useRef(null)
  usePublierHauteurAlertes(bande)
  const aDeplier = useADeplier(bande)
  const motifARegler = useMotifARegler(bande)
  return (
    <div ref={bande} className="cal-coque-alertes" data-deplie={deplie ? '1' : '0'} hidden={cache || undefined}>
      <div className="cal-coque-alertes-contenu">
        {children}
        {motifARegler && (
          <LigneModule motif={motifARegler} calepinageId={calepinageId} bande={bande} />
        )}
      </div>
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
