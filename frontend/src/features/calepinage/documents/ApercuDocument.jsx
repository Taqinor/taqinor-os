import { useEffect, useState } from 'react'
import { Download, Maximize2 } from 'lucide-react'
import Vignette from './Vignettes'

/* ACAL1726 — la colonne d'APERÇU de l'étape Documents (maquette v2 `Documents.dc.html`, 320 px) : la feuille du
   document choisi, son titre, « Aperçu » (le geste d'origine : le document en grand, dans un onglet) et
   « Télécharger » (le même téléchargement que la carte). Cette colonne ne FAIT que montrer :
   - pièce `documents/` à aperçu HTML servi (`apercu: 'html'`) : la PREMIÈRE PAGE RÉELLE, lue par `chargerHtml`
     (le même appel que « Aperçu »), dans un cadre isolé (`sandbox` : aucun script) ramené à la largeur de la feuille ;
   - toute autre pièce (PDF de `sorties/`, DXF), ou lecture refusée : le MODÈLE de page de son type (la vignette
     agrandie), dit comme tel — jamais un faux plan du projet ni un chiffre inventé ;
   - pièce indisponible : le modèle grisé et le motif servi. */

const LARGEUR_PAGE = 794 // une page A4 à 96 dpi : la largeur à laquelle le HTML servi est mis en page
const LARGEUR_FEUILLE = 304

/** La première page réelle, en lecture seule. `html` est du texte servi par le serveur, jamais exécuté. */
function PremierePage({ html, titre }) {
  return (
    <span className="cdoc-feuille-reelle" data-testid="cal-docs-colonne-feuille-reelle">
      <iframe title={`Première page : ${titre}`} sandbox="" srcDoc={html} tabIndex={-1}
        style={{ width: LARGEUR_PAGE, height: Math.round(LARGEUR_PAGE * 1.414), transform: `scale(${LARGEUR_FEUILLE / LARGEUR_PAGE})` }} />
    </span>
  )
}

export default function ApercuDocument({ carte, enCours, onApercu, onTelecharger, chargerHtml, note = null }) {
  const [lu, setLu] = useState({ cle: null, html: null })
  const reel = carte.apercu === 'html' && carte.disponible && typeof chargerHtml === 'function'
  useEffect(() => {
    if (!reel) return undefined
    let vivant = true
    Promise.resolve(chargerHtml(carte))
      .then((html) => { if (vivant) setLu({ cle: carte.cle, html: typeof html === 'string' && html.trim() ? html : null }) })
      .catch(() => { if (vivant) setLu({ cle: carte.cle, html: null }) })
    return () => { vivant = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- relire seulement quand la pièce choisie change
  }, [reel, carte.cle])
  const html = reel && lu.cle === carte.cle ? lu.html : null
  return (
    <div className="cdoc-apercu-col" data-testid="cal-docs-colonne-apercu" data-document={carte.cle}>
      <section className="cdoc-apercu" aria-label="Aperçu du document choisi">
        <div className="cdoc-apercu-feuille" data-disponible={carte.disponible ? 'oui' : 'non'}>
          {html ? <PremierePage html={html} titre={carte.titre} /> : <Vignette nom={carte.vignette} grande />}
        </div>
        <div className="cdoc-apercu-pied">
          <div className="cdoc-apercu-titres">
            <span className="cdoc-apercu-titre">{carte.titre}</span>
            <span className="cdoc-apercu-sous" data-testid="cal-docs-colonne-legende">
              {html ? 'Aperçu de la première page' : 'Modèle de page de ce document'}
            </span>
            {/* le motif SERVI en entier (la carte le coupe à une ligne) */}
            {!carte.disponible && carte.motif
              ? <span className="cdoc-apercu-motif" data-testid="cal-docs-colonne-motif">{carte.motif}</span> : null}
          </div>
          <div className="cdoc-apercu-actions">
            {carte.apercu ? (
              <button type="button" className="cdoc-bouton" disabled={!carte.disponible}
                data-testid={`cal-docs-apercu-${carte.cle}`} onClick={() => onApercu(carte)}>
                <Maximize2 size={16} aria-hidden="true" />Aperçu
              </button>
            ) : null}
            <button type="button" className="cdoc-bouton cdoc-bouton-marine" disabled={!carte.disponible || enCours}
              aria-busy={enCours || undefined} data-testid={`cal-docs-colonne-telecharger-${carte.cle}`}
              onClick={() => onTelecharger(carte)}>
              <Download size={16} aria-hidden="true" />Télécharger
            </button>
          </div>
        </div>
      </section>
      {note}
    </div>
  )
}
