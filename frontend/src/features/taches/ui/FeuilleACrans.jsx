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

export default function FeuilleACrans({
  ouverte,
  onFermer,
  titre,
  cranInitial = '50',
  variante = 'dialogue',
  children,
}) {
  const [cran, setCran] = useState(cranInitial)
  const feuille = useRef(null)
  const origine = useRef(null)
  const clavier = useClavier(Boolean(ouverte))

  useEffect(() => {
    if (!ouverte) return undefined
    origine.current = document.activeElement
    const premier = feuille.current?.querySelector(FOCALISABLES)
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
