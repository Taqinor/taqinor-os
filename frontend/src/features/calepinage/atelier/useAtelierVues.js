// SPL215 — état et handlers des outils de vue de l'atelier (plan 2D, export image
// HD, plein écran 3D), déplacés VERBATIM depuis pages/ventes/ToitureDesign.jsx
// (move only : le corps est inchangé ; seuls l'enveloppe du hook et les imports
// sont ajoutés).
import { useEffect, useRef, useState } from 'react'
import { exporterImageHd } from '../exportImage'
import { basculerPleinEcran, estEnPleinEcranSur } from '../pleinEcran'

export function useAtelierVues({ builderApi, calepinageId, devisId }) {
  // CAL180 — état de l'export image HD (message affiché SOUS le bouton : soit la taille
  // réellement obtenue, soit le motif du refus — jamais un « ça a marché » supposé).
  // CAL104 — onglet vue 2D : le plan est DEMANDÉ au builder (`planView`), jamais
  // reconstruit ici — sinon la 2D et la 3D divergeraient silencieusement.
  const [vue2d, setVue2d] = useState(false)
  const [plan2d, setPlan2d] = useState(null)
  // CALX111 câblage — le pan dont on dessine le plan. `Vue2DPlan` accepte `panId` depuis
  // CALX111 pour lire les numéros de module du DOCUMENT ; personne ne le lui passait, donc
  // le plan 2D sortait MUET (`if (!plan || !panId) return []`). Capturé au MÊME instant
  // que le plan : les deux décrivent le même pan.
  const [panId2d, setPanId2d] = useState(null)
  const ouvrirVue2d = () => {
    setPlan2d(builderApi.current?.planView?.(900, 560) ?? null)
    setPanId2d(builderApi.current?.panActifId?.() || null) // CALX111 câblage
    setVue2d(true)
  }
  const [hdBusy, setHdBusy] = useState(false)
  const [hdMessage, setHdMessage] = useState(null)
  const exporterHd = async (scale) => {
    if (hdBusy) return
    setHdBusy(true)
    setHdMessage(null)
    const res = await exporterImageHd(builderApi, { scale, reference: calepinageId ?? devisId ?? 'calepinage' })
    setHdMessage(res.ok ? `Image HD exportée : ${res.width} × ${res.height} px (${res.nom}).` : res.motif)
    setHdBusy(false)
  }
  // CALX129 — plein écran RÉVERSIBLE du conteneur de la scène 3D. `mapWrapRef`
  // pointe `.rp9-map-wrap`, l'enveloppe ADDITIVE déjà posée par L-MAP autour de
  // `#rp9-map` (jamais l'id lui-même : le builder ne cherche que ses propres
  // id, et cette enveloppe couvre aussi `ToitClientOverlay`). Le composant
  // n'est ni démonté ni ré-amorcé : seule sa classe change.
  const mapWrapRef = useRef(null)
  const [pleinEcran3d, setPleinEcran3d] = useState(false)

  // Sortie par Échap suivie via l'évènement du document — jamais supposé que
  // le bouton est la seule sortie (même repli que Vue2DPlan.jsx).
  useEffect(() => {
    const onChange = () => setPleinEcran3d(estEnPleinEcranSur(document, mapWrapRef.current))
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  const basculerPleinEcran3d = () => {
    Promise.resolve(basculerPleinEcran(mapWrapRef.current, document, pleinEcran3d))
      .then((etat) => setPleinEcran3d(etat.enPleinEcran))
  }

  return {
    vue2d, setVue2d, plan2d, panId2d, ouvrirVue2d,
    hdBusy, hdMessage, exporterHd,
    mapWrapRef, pleinEcran3d, basculerPleinEcran3d,
  }
}
