import { useEffect, useRef } from 'react'

/* ACAL1317 (D-ACAL-70) — les gestes de l'onduleur dans la barre d'outils de l'étape Électrique : « Placer
   l'onduleur » tant que l'entrée en attend un de plus, « Déplacer l'onduleur » (le prochain toucher de la carte le
   déplace ; flèches du clavier ou boutons fléchés pour l'ajuster) et « Retirer l'onduleur ». L'état et les gestes
   viennent de `useOnduleurSurCarte` (`onduleurSurCarte.js`) ; en lecture seule, chaque bouton est désactivé avec le
   motif de l'étape. Sans couche électrique dans le constructeur, rien n'est rendu. */

const FLECHES = [
  { touche: 'ArrowUp', libelle: 'le nord', signe: '↑', d: [0, 1] },
  { touche: 'ArrowLeft', libelle: 'l’ouest', signe: '←', d: [-1, 0] },
  { touche: 'ArrowRight', libelle: 'l’est', signe: '→', d: [1, 0] },
  { touche: 'ArrowDown', libelle: 'le sud', signe: '↓', d: [0, -1] },
]

export default function OutilsOnduleur({ onduleur, lectureSeule = false, motifLectureSeule }) {
  const premiereFleche = useRef(null)
  const enDeplacement = !!onduleur?.enDeplacement
  useEffect(() => { if (enDeplacement) premiereFleche.current?.focus?.() }, [enDeplacement])
  if (!onduleur?.disponible) return null
  const { onduleurs, choisi, peutPlacer, enPose, message } = onduleur
  const titre = lectureSeule ? motifLectureSeule : undefined
  // Le pas d'une flèche est celui de la couche électrique (`pasDeplacementM`) : l'écran n'en invente aucun.
  const pousser = ([de, dn]) => onduleur.pousser(de * onduleur.pas, dn * onduleur.pas)
  // Les touches TRAITÉES ici s'arrêtent ici : le plan clavier du constructeur (`mapDraw.ts`, à l'écoute du document,
  // mode « trace » à cette étape) déplacerait sinon son curseur de contour, et Échap fermerait la feuille ou l'aide.
  const auClavier = (e) => {
    const fleche = FLECHES.find((f) => f.touche === e.key)
    if (!fleche && e.key !== 'Escape') return
    e.preventDefault()
    e.stopPropagation()
    if (fleche) pousser(fleche.d); else onduleur.terminer()
  }
  return (
    <>
      {onduleurs.length > 1 && (
        <select className="cel-barre-texte" aria-label="Onduleur visé" data-testid="cal-elec-onduleur-choix"
          value={choisi?.id ?? ''} onChange={(e) => onduleur.choisir(e.target.value)} disabled={lectureSeule} title={titre}>
          {onduleurs.map((o) => <option key={o.id} value={o.id}>{o.label || o.id}</option>)}
        </select>
      )}
      {peutPlacer && (
        <button type="button" className="cel-barre-texte" data-testid="cal-elec-onduleur-placer"
          onClick={enPose ? onduleur.terminer : onduleur.placer} disabled={lectureSeule} title={titre} aria-pressed={enPose}>
          {enPose ? 'Annuler la pose' : 'Placer l’onduleur'}
        </button>
      )}
      {choisi && !enDeplacement && (
        <button type="button" className="cel-barre-texte" data-testid="cal-elec-onduleur-deplacer"
          onClick={onduleur.deplacer} disabled={lectureSeule} title={titre}>
          Déplacer l’onduleur
        </button>
      )}
      {choisi && enDeplacement && (
        // Le déplacement armé : flèches (clavier et toucher), Échap ou « Terminer » pour sortir.
        <div role="group" aria-label="Pousser l’onduleur" data-testid="cal-elec-onduleur-fleches" onKeyDown={auClavier}>
          {FLECHES.map((f, i) => (
            <button key={f.touche} type="button" className="cel-barre-texte" ref={i === 0 ? premiereFleche : undefined}
              aria-label={`Pousser l’onduleur vers ${f.libelle}`} onClick={() => pousser(f.d)} disabled={lectureSeule}>
              {f.signe}
            </button>
          ))}
          <button type="button" className="cel-barre-texte" onClick={onduleur.terminer}>Terminer</button>
        </div>
      )}
      {choisi && (
        <button type="button" className="cel-barre-texte" data-testid="cal-elec-onduleur-retirer"
          onClick={onduleur.retirer} disabled={lectureSeule} title={titre}>
          Retirer l’onduleur
        </button>
      )}
      {message && <p className="cel-barre-message" role="status" data-testid="cal-elec-onduleur-message">{message}</p>}
    </>
  )
}
