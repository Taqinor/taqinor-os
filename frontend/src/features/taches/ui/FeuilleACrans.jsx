import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

/* ============================================================================
   TCH45 — Feuille du bas à crans (spec-7 §10, spec-8 §2 : rayon 20, `--popover` +
   `--shadow-lg`, 260 ms entrée / 180 ms sortie). Deux crans, 50 % et 85 % de la hauteur,
   que la poignée (44 px) fait basculer : « Agrandir la feuille » / « Réduire la feuille ».
   CLAVIER OUVERT : les crans ne valent plus (86 px utiles à 50 %) — la feuille épouse son
   contenu et se pose SUR le clavier (`sur-clavier`, hauteur du clavier lue sur
   `visualViewport`, jetée dans `--tch-clavier-h`). Au bureau (≥ 768 px) la même feuille est
   un dialogue centré (`dialogue-bureau`) ou un popover (`popover-bureau`) — CSS seul.
   Dialogue modal : focus piégé, Échap ferme, le focus revient à l'élément qui l'a ouverte.
   Maquettes : docs/taches/maquettes/composants-5.html, composants-6.html.
   ========================================================================== */

const SEUIL_CLAVIER_PX = 120
const FOCALISABLES = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Hauteur (px) du clavier virtuel, 0 s'il est fermé ou si `visualViewport` n'existe pas. */
function lireClavier() {
  const vv = typeof window !== 'undefined' ? window.visualViewport : null
  if (!vv) return 0
  const bas = window.innerHeight - vv.height - (vv.offsetTop || 0)
  return bas > SEUIL_CLAVIER_PX ? Math.round(bas) : 0
}

function useClavier(actif) {
  const [clavier, setClavier] = useState(0)
  useEffect(() => {
    const vv = typeof window !== 'undefined' ? window.visualViewport : null
    if (!actif || !vv) return undefined
    const maj = () => setClavier(lireClavier())
    maj()
    vv.addEventListener('resize', maj)
    vv.addEventListener('scroll', maj)
    return () => {
      vv.removeEventListener('resize', maj)
      vv.removeEventListener('scroll', maj)
    }
  }, [actif])
  return actif ? clavier : 0
}

/**
 * Raccord F2 — le retour arrière du navigateur (geste de l'iPhone) ferme la feuille au lieu de quitter l'écran :
 * à l'ouverture, une entrée d'historique MARQUÉE est posée (sans changer l'adresse) ; un retour qui la retire ferme
 * la feuille ; une fermeture par la croix, Échap ou le voile retire l'entrée. La pose est différée d'un tour pour
 * que le double montage du mode strict (développement) n'en laisse aucune.
 */
function useRetourFerme(actif, onFermer) {
  const fermer = useRef(onFermer)
  useEffect(() => { fermer.current = onFermer })
  useEffect(() => {
    if (!actif || typeof window === 'undefined' || typeof window.history?.pushState !== 'function') return undefined
    const marque = `tch-feuille-${Math.random().toString(36).slice(2)}`
    let posee = false
    let parRetour = false
    const surRetour = () => {
      if (posee && window.history.state?.tchFeuille !== marque) { parRetour = true; fermer.current?.() }
    }
    const minuteur = setTimeout(() => {
      window.history.pushState({ ...(window.history.state ?? {}), tchFeuille: marque }, '')
      posee = true
      window.addEventListener('popstate', surRetour)
    }, 0)
    return () => {
      clearTimeout(minuteur)
      window.removeEventListener('popstate', surRetour)
      if (posee && !parRetour && window.history.state?.tchFeuille === marque) window.history.back()
    }
  }, [actif])
}

export default function FeuilleACrans({
  ouverte,
  onFermer,
  titre,
  cranInitial = '50',
  variante = 'dialogue',
  historique = true,
  children,
}) {
  const [cran, setCran] = useState(cranInitial)
  const feuille = useRef(null)
  const origine = useRef(null)
  const clavier = useClavier(Boolean(ouverte))
  useRetourFerme(Boolean(ouverte) && historique, onFermer)

  useEffect(() => {
    if (!ouverte) return undefined
    origine.current = document.activeElement
    // F2 acceptation (P144.3) — une feuille ouverte au clavier peut désigner son action par défaut
    // (`data-focus-initial`) : Entrée la valide aussitôt ; sinon le premier élément focalisable (la poignée)
    const voulu = feuille.current?.querySelector('[data-focus-initial]')
    const premier = voulu ?? feuille.current?.querySelector(FOCALISABLES)
    premier?.focus()
    return () => origine.current?.focus?.()
  }, [ouverte])

  if (!ouverte) return null

  const surTouche = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); onFermer?.(); return }
    if (e.key !== 'Tab') return
    const liste = [...(feuille.current?.querySelectorAll(FOCALISABLES) ?? [])]
    if (liste.length === 0) return
    const premier = liste[0]
    const dernier = liste[liste.length - 1]
    if (e.shiftKey && document.activeElement === premier) { e.preventDefault(); dernier.focus() }
    else if (!e.shiftKey && document.activeElement === dernier) { e.preventDefault(); premier.focus() }
  }

  const classes = ['feuille', clavier ? 'sur-clavier' : `cran-${cran}`, `${variante}-bureau`]
  const style = clavier ? { '--tch-clavier-h': `${clavier}px` } : undefined
  const grand = cran === '85'

  return (
    <>
      <div className="voile" onClick={onFermer} aria-hidden="true" />
      <div
        ref={feuille}
        className={classes.join(' ')}
        style={style}
        role="dialog"
        aria-modal="true"
        aria-label={titre}
        onKeyDown={surTouche}
      >
        <button
          type="button"
          className="poignee"
          aria-label={grand ? 'Réduire la feuille' : 'Agrandir la feuille'}
          onClick={() => setCran(grand ? '50' : '85')}
        />
        <div className="feuille-entete">
          <button type="button" className="bouton-icone" aria-label="Fermer" onClick={onFermer}>
            <X className="i" aria-hidden="true" />
          </button>
          <div className="feuille-titre">{titre}</div>
          <span />
        </div>
        <div className="feuille-corps">{children}</div>
      </div>
    </>
  )
}
