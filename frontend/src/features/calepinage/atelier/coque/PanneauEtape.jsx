import { useRef } from 'react'
import { ETAPES } from '../parcoursGuide'
import { decisionGesteTiroir } from './gesteTiroir'

/* Coque — le panneau d'étape de droite (maquette v2 Main : 384 px, flottant au bureau).
   En-tête : cinq traits de progression (ACAL1803), « Étape N sur 5 » (12 px), titre Archivo 24 px ;
   corps qui défile seul ; pied collé en bas (bouton doré 52 px). Porte l'id historique
   `rp9-studio-inspecteur` (specs).
   `refCorps` / `refPied` : les nœuds que la coque ouvre aux portails `<DansPanneau>` / `<PiedEtape>`.
   TIROIR (maquette Tablette, et téléphone) — `tiroir` : le même panneau devient le tiroir du bas
   (56-coque-responsive.css) : une poignée qui l'agrandit ou le réduit, puis UNE rangée « titre ·
   contrôle principal (`refControle`, portail `<EnTeteEtape>`) · bouton d'action », les cartes de
   l'étape dessous. Les mêmes enfants, aux mêmes places de l'arbre : rien n'est remonté au passage. */
/** ACAL1803 — les cinq traits de progression de la tête d'étape (maquettes v2) : un par étape du parcours, `fait`
    (lu sur `etats` servis par parcours/), `actif` (l'étape affichée), sinon `a-venir`. Décoratif : « Étape N sur 5 »
    dit la même chose en texte. */
export function ProgressionEtapes({ numero, etats = {} }) {
  return (
    <div className="cal-progression-etapes" data-testid="cal-progression-etapes" aria-hidden="true">
      {ETAPES.map((e, i) => (
        <span key={e.cle} data-etat={i + 1 === numero ? 'actif' : (etats[e.cle] === 'fait' ? 'fait' : 'a-venir')} />
      ))}
    </div>
  )
}

/** Capture le pointeur sur la poignée ; rend `false` quand le navigateur la refuse (pointeur déjà levé, événement
    synthétique) : le geste reste alors lisible sans capture. */
function capturerLeDoigt(e) {
  try {
    e.currentTarget.setPointerCapture?.(e.pointerId)
    return true
  } catch {
    return false
  }
}

/** Les poignées de geste du tiroir : la poignée (bouton) ET la rangée du titre. Le toucher de la poignée reste son `click`
    (clavier compris) ; un balayage la dépasse sans déclencher le `click` qui suit ; la rangée du titre, qui n'a aucun
    contrôle, prend aussi le toucher. `touch-action: none` (56-coque-responsive.css) garde le geste au tiroir. */
function useGesteTiroir({ tiroir, deplie, onDeplier }) {
  const depart = useRef(null)
  const balaye = useRef(false)
  const appliquer = (decision) => {
    if (decision === 'ouvrir') onDeplier?.(true)
    else if (decision === 'fermer') onDeplier?.(false)
    else if (decision === 'basculer') onDeplier?.(!deplie)
  }
  const bas = (e) => {
    depart.current = e.clientY
    balaye.current = false
    capturerLeDoigt(e)
  }
  const lever = (e, { toucher }) => {
    if (depart.current == null) return
    const decision = decisionGesteTiroir({ dy: e.clientY - depart.current, deplie })
    depart.current = null
    if (decision === 'basculer') { if (toucher) appliquer(decision); return }
    balaye.current = true
    // Le `click` qui suit un balayage tombe dans l'instant ; passé ce délai (un balayage tactile n'en émet aucun), le drapeau
    // retombe : l'activation suivante (clavier, lecteur d'écran) n'est jamais avalée.
    window.setTimeout(() => { balaye.current = false }, 350)
    appliquer(decision)
  }
  if (!tiroir) return {}
  return {
    poignee: {
      onPointerDown: bas,
      onPointerUp: (e) => lever(e, { toucher: false }),
      onPointerCancel: () => { depart.current = null },
      onClick: (e) => { if (balaye.current && e.detail !== 0) { balaye.current = false; return } balaye.current = false; onDeplier?.(!deplie) }, // detail 0 = clavier / lecteur d'écran : jamais avalé
    },
    tete: {
      onPointerDown: bas,
      onPointerUp: (e) => lever(e, { toucher: true }),
      onPointerCancel: () => { depart.current = null },
    },
  }
}

export default function PanneauEtape({
  numero = null, total = 5, titre, cache = false, refCorps, refPied, children, pied = null,
  tiroir = false, deplie = false, onDeplier = null, refControle = null, etats = {},
}) {
  const geste = useGesteTiroir({ tiroir, deplie, onDeplier })
  return (
    <aside id="rp9-studio-inspecteur" aria-label={titre || 'Étape'} hidden={cache}
      className="cal-panneau-etape" data-testid="cal-panneau-etape"
      data-tiroir={tiroir ? '1' : undefined} data-deplie={tiroir ? (deplie ? '1' : '0') : undefined}>
      {tiroir && (
        <button type="button" className="cal-tiroir-poignee" aria-expanded={deplie}
          aria-label="Agrandir ou réduire le panneau du bas" {...geste.poignee}>
          <span aria-hidden="true" />
        </button>
      )}
      {titre && (
        <div className="cal-panneau-etape-tete" {...geste.tete}>
          {numero && !cache && !tiroir && <ProgressionEtapes numero={numero} etats={etats} />}
          {numero && <p className="cal-panneau-etape-rang">{`Étape ${numero} sur ${total}`}</p>}
          <h2 className="cal-panneau-etape-titre" data-testid="cal-panneau-etape-titre">{titre}</h2>
        </div>
      )}
      {tiroir && <div ref={refControle} className="cal-panneau-etape-controle" />}
      <div className="cal-panneau-etape-corps">
        <div ref={refCorps} className="cal-panneau-etape-emplacement" />
        {children}
      </div>
      <div ref={refPied} className="cal-panneau-etape-pied">{pied}</div>
    </aside>
  )
}
