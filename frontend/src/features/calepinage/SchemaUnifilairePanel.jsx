import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import calepinageApi from '../../api/calepinageApi'
import useResource from '../../hooks/useResource'
import { renderTrustedSvg } from '../../lib/trustedSvg'
import { Button, Card, Input, Label } from '../../ui'
import RetourAtelier from './atelier/RetourAtelier'
import { telechargerBlob } from './exportImage'
import {
  CIBLE_DU_BLOC, corpsEdition, couperTexte, exporterSchemaPng, exporterSchemaSvg, motifDuRefusDxf, nomFichierSchema,
} from './SchemaUnifilairePanel.helpers'
import EtatEcranAtelier from './atelier/EtatEcranAtelier'
import { OPTIONS_TELECHARGEMENT } from './documents/telechargement'
import CroquisSchemaGrise from './CroquisSchemaGrise'

/* ACAL44 — le motif d'un bouton d'écriture en lecture seule (devis lié figé). */
const MOTIF_LECTURE_SEULE = 'Conception figée : révisez le devis (nouvelle version) pour la modifier.'

const LISTES = [
  { cle: 'manquantes', titre: 'Fiche technique incomplète' },
  { cle: 'bloquants', titre: 'Conception non conforme' },
]

export function MotifsSchema({ donnees }) {
  const blocs = LISTES
    .map(({ cle, titre }) => ({ titre, cle, lignes: donnees?.[cle] || [] }))
    .filter((bloc) => bloc.lignes.length > 0)
  if (!blocs.length) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="cal195-sans-motif">
        Aucun schéma pour cette conception.
      </p>
    )
  }
  const croquis = blocs.some((bloc) => bloc.cle === 'manquantes') // ACAL1028 — fiche incomplète seulement
  return (<>
    {croquis ? <CroquisSchemaGrise /> : null}
    {blocs.map((bloc) => (
    <div key={bloc.cle} className="flex flex-col gap-1" data-testid={`cal195-${bloc.cle}`}>
      <div className="flex items-center gap-2 text-sm font-medium">
        <AlertCircle size={15} aria-hidden="true" />
        {bloc.titre}
      </div>
      <ul className="list-disc pl-5 text-sm text-muted-foreground">
        {bloc.lignes.map((ligne) => <li key={ligne}>{ligne}</li>)}
      </ul>
    </div>
    ))}
  </>)
}

/* ACAL1301 — LA PLANCHE DU SOUS-ÉCRAN « SCHÉMA » (maquette `Schema.dc.html`) : le MÊME SVG serveur,
   au centre, dans une carte qui le cadre ENTIER (`viewBox` gardé : rien n'est coupé), avec zoom ± et
   déplacement (glisser, ou flèches au clavier). `actions` : nœud posé à gauche du zoom (le retour au
   raccordement) ; `note` : la phrase servie sous le dessin ; sans SVG, `children` (les motifs). */
const ZOOM_MIN = 0.5
const ZOOM_MAX = 4
const PAS_ZOOM = 1.25
const PAS_CLAVIER = 40

/* F3 (tour 2) — `dessin` : un nœud React (le schéma EN BLOCS, à l'échelle 1) posé à la place du SVG
   servi ; même zoom, même déplacement. Un glisser ne commence qu'au-delà de 4 px : un clic sur un
   bloc reste un clic (et un glisser n'en déclenche aucun). */
const SEUIL_GLISSER = 4

export function PlancheSchema({ balisage, dessin = null, actions = null, note = null, children = null }) {
  const [echelle, setEchelle] = useState(1)
  const [decalage, setDecalage] = useState({ x: 0, y: 0 })
  const glisse = useRef(null)
  const aGlisse = useRef(false)
  const zoomer = (facteur) => {
    const suivante = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, echelle * facteur))
    setEchelle(suivante)
    if (Math.abs(suivante - 1) < 1e-9) setDecalage({ x: 0, y: 0 })
  }
  const deplacer = (dx, dy) => setDecalage((d) => ({ x: d.x + dx, y: d.y + dy }))
  const auClavier = (e) => {
    const pas = { ArrowLeft: [PAS_CLAVIER, 0], ArrowRight: [-PAS_CLAVIER, 0], ArrowUp: [0, PAS_CLAVIER], ArrowDown: [0, -PAS_CLAVIER] }[e.key]
    if (pas) { e.preventDefault(); deplacer(...pas) } else if (e.key === '+' || e.key === '=') zoomer(PAS_ZOOM)
    else if (e.key === '-') zoomer(1 / PAS_ZOOM)
  }
  return (
    <section className="csch-planche" aria-labelledby="csch-titre">
      <div className="csch-tete">
        <div className="csch-titres">
          <h2 id="csch-titre">Schéma électrique</h2>
          <span>Des panneaux jusqu’au réseau · sans échelle</span>
        </div>
        <div className="csch-outils">
          {actions}
          {(dessin || balisage) && (
            <div role="group" aria-label="Zoom du schéma" className="csch-zoom">
              <button type="button" aria-label="Zoomer" onClick={() => zoomer(PAS_ZOOM)} disabled={echelle >= ZOOM_MAX}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
              </button>
              <button type="button" aria-label="Dézoomer" onClick={() => zoomer(1 / PAS_ZOOM)} disabled={echelle <= ZOOM_MIN}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M5 12h14" /></svg>
              </button>
            </div>
          )}
        </div>
      </div>
      {(dessin || balisage)
        ? (
          <div className="csch-vue" tabIndex={0} role={dessin ? 'group' : 'img'}
            aria-label={dessin ? 'Schéma en blocs : glisser ou utiliser les flèches pour le déplacer'
              : 'Schéma unifilaire : glisser ou utiliser les flèches pour le déplacer'}
            data-testid="csch-vue" data-echelle={echelle} data-vue={dessin ? 'blocs' : 'detaille'} onKeyDown={auClavier}
            onPointerDown={(e) => {
              aGlisse.current = false
              glisse.current = { x: e.clientX - decalage.x, y: e.clientY - decalage.y, sx: e.clientX, sy: e.clientY, pointeur: e.pointerId }
            }}
            onPointerMove={(e) => {
              const g = glisse.current
              if (!g) return
              if (!aGlisse.current) {
                if (Math.hypot(e.clientX - g.sx, e.clientY - g.sy) < SEUIL_GLISSER) return
                aGlisse.current = true
                e.currentTarget.setPointerCapture?.(g.pointeur)
              }
              setDecalage({ x: e.clientX - g.x, y: e.clientY - g.y })
            }}
            onClickCapture={(e) => { if (aGlisse.current) { e.stopPropagation(); e.preventDefault() } }}
            onPointerUp={() => { glisse.current = null }} onPointerCancel={() => { glisse.current = null }}>
            {dessin
              ? (
                <div className="csch-dessin csch-dessin-blocs" data-testid="csch-blocs"
                  style={{ transform: `translate(${decalage.x}px, ${decalage.y}px) scale(${echelle})` }}>
                  {dessin}
                </div>
              )
              : (
                <div className="csch-dessin" data-testid="csch-svg"
                  style={{ transform: `translate(${decalage.x}px, ${decalage.y}px) scale(${echelle})` }}
                  /* Le SVG du serveur, passé par `renderTrustedSvg` (VX120) comme dans le panneau. */
                  dangerouslySetInnerHTML={balisage} />
              )}
          </div>
        )
        : <div className="csch-motifs">{children}</div>}
      {note && <p className="csch-note">{note}</p>}
    </section>
  )
}

/* F3 — les pictogrammes des organes (tracés de la maquette `Schema.dc.html`, 24 × 24). */
const PICTOS = {
  parafoudre: <><rect x="6" y="3" width="12" height="14" rx="1" /><path d="M13 6l-3 4h4l-3 4M12 17v4M8 21h8" /></>,
  sectionneur: <><path d="M3 12h6M15 12h6M9 12l6-5" /><circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" /></>,
  disjoncteur: <><path d="M12 2v6M12 16v6M12 8l5 6" /><path d="M9 10h-3M9 13h-3" /></>,
  fusible: <><rect x="4" y="9" width="16" height="6" rx="1" /><path d="M2 12h2M20 12h2M7 12h10" /></>,
}

/** Un élément cliquable du schéma : ouvre la section où SA valeur se règle (clavier : Entrée / Espace). */
function Element({ cible, libelle, onOuvrir, children, testId }) {
  if (!onOuvrir) return <g aria-label={libelle} data-testid={testId}>{children}</g>
  const ouvrir = () => onOuvrir(cible)
  return (
    <g role="button" tabIndex={0} aria-label={libelle} className="csch-element" data-testid={testId}
      onClick={ouvrir} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ouvrir() } }}>
      {children}
    </g>
  )
}

function Lignes({ x, y, lignes, pas, className, ancre = 'start' }) {
  return lignes.map((t, i) => <text key={`${i}-${t}`} x={x} y={y + i * pas} className={className} textAnchor={ancre}>{t}</text>)
}

function Coffret({ titre, boite, onOuvrir, cleCible }) {
  const { x, y, l, h, organes = [], detail = null } = boite
  const contenu = organes.length ? organes.map((o) => o.nom.toLowerCase()).join(' et ') : (detail ?? []).join(' ')
  return (
    <Element cible={cleCible} libelle={contenu ? `${titre} : ${contenu}` : titre} onOuvrir={onOuvrir}
      testId={`csch-bloc-${boite.cle ?? 'coffret_dc'}`}>
      <rect x={x} y={y} width={l} height={h} rx="10" className="csch-boite" />
      <text x={x + 12} y={y + 28} className="csch-t14">{titre}</text>
      {detail && <Lignes x={x + 12} y={y + 50} lignes={detail} pas={16} className="csch-t12 csch-attenue" />}
      {organes.map((o, i) => {
        const oy = y + 42 + i * 66
        return (
          <g key={o.clef}>
            <rect x={x + 12} y={oy} width={l - 24} height="56" rx="8" className="csch-organe" />
            <g transform={`translate(${x + 20} ${oy + 16})`} className="csch-picto">{PICTOS[o.picto]}</g>
            <text x={x + 54} y={oy + 20} className="csch-t14">{o.nom}</text>
            <Lignes x={x + 54} y={oy + 36} lignes={couperTexte(o.detail, 19, 2)} pas={14} className="csch-t12 csch-attenue" />
          </g>
        )
      })}
    </Element>
  )
}

function Onduleur({ o, onOuvrir }) {
  const lignes = [...o.designation, ...(o.entrees ? [o.entrees] : [])]
  // Pile verticale centrée : pictogramme 64, « Onduleur » 16, puissance 20, lignes 12, pastille 22.
  const total = 88 + (o.puissance ? 28 : 0) + 22 + Math.max(0, lignes.length - 1) * 16 + 10 + 22
  const icone = o.y + Math.max(16, (o.h - total) / 2)
  const cx = o.x + o.l / 2
  const titre = icone + 88
  const puissance = o.puissance ? titre + 28 : null
  const designation = (puissance ?? titre) + 22
  const pilule = designation + Math.max(0, lignes.length - 1) * 16 + 10
  return (
    <Element cible={CIBLE_DU_BLOC.onduleur} onOuvrir={onOuvrir} testId="csch-bloc-onduleur"
      libelle={['Onduleur', o.puissance, ...o.designation, o.entrees].filter(Boolean).join(', ')}>
      <rect x={o.x} y={o.y} width={o.l} height={o.h} rx="10" className="csch-boite" />
      <g transform={`translate(${cx - 32} ${icone})`} className="csch-picto csch-picto-fin">
        <rect x="4" y="4" width="56" height="56" rx="4" /><path d="M8 56L56 8" /><path d="M14 18h16M14 24h16" /><path d="M36 46c3-5 6-5 9 0s6 5 9 0" />
      </g>
      <text x={cx} y={titre} textAnchor="middle" className="csch-t16">Onduleur</text>
      {puissance !== null && <text x={cx} y={puissance} textAnchor="middle" className="csch-t20">{o.puissance}</text>}
      <Lignes x={cx} y={designation} lignes={lignes} pas={16} className="csch-t12 csch-attenue" ancre="middle" />
      <rect x={cx - 64} y={pilule} width="128" height="22" rx="11" className="csch-pilule" />
      <text x={cx} y={pilule + 15} textAnchor="middle" className="csch-t12 csch-pilule-texte">continu → alternatif</text>
    </Element>
  )
}

/* LOT 6 — la batterie : une carte du même langage que les autres, reliée à l'onduleur par une liaison NEUTRE à
   double flèche (charge / décharge). Seules les lignes servies existent (`plan.batterie.lignes`) : aucune valeur
   absente n'est remplacée. Aucune protection : le serveur n'en calcule aucune. */
function Batterie({ b, onOuvrir }) {
  const lib = ['Batterie', ...b.lignes].join(', ')
  return (
    <>
      <polyline points={b.lien.map((p) => p.join(',')).join(' ')} className="csch-liaison csch-liaison-batterie"
        markerStart="url(#csch-fleche)" markerEnd="url(#csch-fleche)" data-testid="csch-lien-batterie" />
      <Element cible={CIBLE_DU_BLOC.batterie} onOuvrir={onOuvrir} testId="csch-bloc-batterie" libelle={lib}>
        <rect x={b.x} y={b.y} width={b.l} height={b.h} rx="10" className="csch-boite" />
        <g transform={`translate(${b.x + 12} ${b.y + 10})`} className="csch-picto">
          <rect x="1" y="4" width="20" height="11" rx="2" /><path d="M23 7v5M5 8v3M9 8v3M13 8v3" />
        </g>
        <text x={b.x + 44} y={b.y + 24} className="csch-t14">Batterie</text>
        <Lignes x={b.x + 12} y={b.y + 52} lignes={b.lignes} pas={16} className="csch-t12 csch-attenue" />
      </Element>
    </>
  )
}

/* Côté réseau pas encore servi : la boîte en creux (pointillés), son nom, « à calculer » — aucune valeur. */
function BlocACalculer({ b }) {
  const cx = b.x + b.l / 2
  const titre = b.titre ?? []
  const total = titre.length * 17 + 18
  const y0 = b.y + (b.h - total) / 2
  return (
    <g data-testid={`csch-bloc-${b.cle}`} data-a-calculer="true"
      aria-label={`${titre.join(' ')} : à calculer`}>
      <rect x={b.x} y={b.y} width={b.l} height={b.h} rx="10" className="csch-boite csch-boite-creux" />
      <Lignes x={cx} y={y0 + 14} lignes={titre} pas={17} className="csch-t14 csch-attenue" ancre="middle" />
      <text x={cx} y={y0 + titre.length * 17 + 14} textAnchor="middle" className="csch-t12 csch-attenue">à calculer</text>
    </g>
  )
}

function BlocAc({ b, onOuvrir }) {
  if (b.aCalculer) return <BlocACalculer b={b} />
  const cx = b.x + b.l / 2
  if (b.cle === 'coffret_ac') return <Coffret titre="Coffret côté réseau" boite={b} onOuvrir={onOuvrir} cleCible={CIBLE_DU_BLOC.coffret} />
  const titre = b.titre ?? []
  const detail = b.detail ?? []
  const icone = b.cle === 'tgbt' || b.aConfirmer ? 0 : 40
  const total = icone + (icone ? 6 : 0) + titre.length * 17 + detail.length * 16
  const y0 = b.y + (b.h - total) / 2
  return (
    <Element cible={CIBLE_DU_BLOC.reseau} onOuvrir={onOuvrir} testId={`csch-bloc-${b.cle}`}
      libelle={[...titre, ...detail].join(' ')}>
      <rect x={b.x} y={b.y} width={b.l} height={b.h} rx="10" className="csch-boite" />
      {b.cle === 'compteur' && (
        <g transform={`translate(${cx - 18} ${y0 + 2})`} className="csch-picto csch-picto-fin">
          <circle cx="18" cy="18" r="15" /><path d="M11 21l3-6 3 6M20 15v6M20 18h5" />
        </g>
      )}
      {b.cle === 'reseau' && (
        <g transform={`translate(${cx - 18} ${y0})`} className="csch-picto csch-picto-fin">
          <path d="M18 2L8 38M18 2l10 36M6 12h24M9 22h18M12 30l12 0M10 22l14 8M26 22l-14 8" />
        </g>
      )}
      <Lignes x={cx} y={y0 + icone + (icone ? 6 : 0) + 14} lignes={titre} pas={17} className="csch-t14" ancre="middle" />
      <Lignes x={cx} y={y0 + icone + (icone ? 6 : 0) + titre.length * 17 + 12} lignes={detail} pas={16} className="csch-t12 csch-attenue" ancre="middle" />
      {/* Étage moyenne tension : bloc servi mais « à confirmer » — la pastille le dit. */}
      {b.aConfirmer && (
        <>
          <rect x={cx - 46} y={b.y + b.h - 30} width="92" height="22" rx="11" className="csch-pilule" />
          <text x={cx} y={b.y + b.h - 15} textAnchor="middle" className="csch-t12 csch-pilule-texte">à confirmer</text>
        </>
      )}
    </Element>
  )
}

/** F3 — le schéma en blocs de la maquette `Schema.dc.html`, dessiné depuis `planSchemaEnBlocs` (données servies). */
export function SchemaEnBlocs({ plan, onOuvrir = null, coteReseau = null }) {
  const { largeur, hauteur, bandes, chaines, coffretDc, onduleur, blocsAc, liaisons, terre } = plan
  const xMax = terre ? Math.max(...terre.descentes.map(([x]) => x)) : 0
  return (
    <svg width={largeur} height={hauteur} viewBox={`0 0 ${largeur} ${hauteur}`} className="csch-blocs-svg"
      xmlns="http://www.w3.org/2000/svg">
      {plan.batterie && (
        <defs>
          <marker id="csch-fleche" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0 1L10 5L0 9z" className="csch-fleche" />
          </marker>
        </defs>
      )}
      {bandes.map((b) => (
        <g key={b.cle}>
          <rect x="0.5" y={b.y + 0.5} width={largeur - 1} height={b.h - 1} rx="10" className="csch-bande" />
          <text x="16" y={b.y + 22} className="csch-t12 csch-gras csch-attenue">{b.libelle}</text>
          {/* Côté réseau pas encore calculé : UNE ligne, sur la ligne du titre de la bande, et le geste qui le dimensionne. */}
          {b.cle === 'ac' && plan.coteReseauACalculer && coteReseau && (
            coteReseau.onOuvrir
              ? (
                <g role="button" tabIndex={0} className="csch-element csch-a-calculer" data-testid="csch-a-calculer"
                  onClick={coteReseau.onOuvrir}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); coteReseau.onOuvrir() } }}>
                  <text x="212" y={b.y + 22} className="csch-t12 csch-lien-svg csch-etiquette">{coteReseau.texte}</text>
                </g>
              )
              : <text x="212" y={b.y + 22} className="csch-t12 csch-attenue csch-etiquette" data-testid="csch-a-calculer">{coteReseau.texte}</text>
          )}
        </g>
      ))}
      {terre && (
        <g className="csch-terre" aria-hidden="true">
          <path d={`M${terre.x1} ${terre.y}H${xMax}`} />
          {terre.descentes.map(([x, y]) => <path key={`${x}-${y}`} d={`M${x} ${y}V${terre.y}`} />)}
          <g transform={`translate(${terre.x1 - 14} ${terre.y})`} className="csch-terre-symbole"><path d="M14 0v8M3 8h22M7 14h14M11 20h6" /></g>
        </g>
      )}
      {liaisons.map((l) => (
        <polyline key={l.cle} points={l.points.map((p) => p.join(',')).join(' ')}
          className={l.couleur ? 'csch-liaison' : `csch-liaison csch-liaison-ac${l.aCalculer ? ' csch-liaison-creux' : ''}`} style={l.couleur ? { stroke: l.couleur } : undefined} />
      ))}
      {liaisons.filter((l) => l.etiquette).map((l) => (
        <Element key={`e-${l.cle}`} cible={CIBLE_DU_BLOC.cable} onOuvrir={onOuvrir} libelle={`Câble : ${l.etiquette.lignes.join(', ')}`}>
          <Lignes x={l.etiquette.x} y={l.etiquette.y} lignes={l.etiquette.lignes} pas={16} className="csch-t12 csch-gras csch-etiquette" />
        </Element>
      ))}
      {chaines.map((c) => (
        <Element key={c.chaine} cible={CIBLE_DU_BLOC.chaine} onOuvrir={onOuvrir} testId={`csch-chaine-${c.chaine}`}
          libelle={`${c.libelle}${c.mppt == null ? '' : `, entrée ${c.mppt} de l'onduleur`}`}>
          <rect x={c.x} y={c.y} width="214" height={c.h} rx="10" className="csch-zone" />
          <rect x={c.x + 8} y={c.y + 11} width="12" height="12" rx="3" className="csch-couleur" style={c.couleur ? { fill: c.couleur } : undefined} />
          <text x={c.x + 26} y={c.y + 22} className="csch-t14">{c.libelle}</text>
          {Array.from({ length: c.glyphes.n }, (_, i) => (
            <rect key={i} x={c.x + 8 + i * (c.glyphes.l + c.glyphes.gap)} y={c.y + 32} width={c.glyphes.l} height={c.hGlyphe} rx="2"
              className="csch-glyphe" style={c.couleur ? { fill: c.couleur } : undefined} />
          ))}
          {c.detail && <text x={c.x + 8} y={c.y + c.yDetail} className="csch-t12 csch-attenue">{c.detail}</text>}
        </Element>
      ))}
      {coffretDc && <Coffret titre="Coffret côté panneaux" boite={coffretDc} onOuvrir={onOuvrir} cleCible={CIBLE_DU_BLOC.coffret} />}
      <Onduleur o={onduleur} onOuvrir={onOuvrir} />
      {plan.batterie && <Batterie b={plan.batterie} onOuvrir={onOuvrir} />}
      {blocsAc.map((b) => <BlocAc key={b.cle} b={b} onOuvrir={onOuvrir} />)}
      {terre && <text x={terre.x1 + 20} y={terre.y + 19} className="csch-t12 csch-gras csch-etiquette csch-terre-texte">{terre.libelle}</text>}
    </svg>
  )
}

function EditionSchema({ id, donnees, onPoste, lectureSeule = false }) {
  const blocs = Array.isArray(donnees?.blocs) ? donnees.blocs : []
  const [saisie, setSaisie] = useState({ libelles: {}, reperes: {} })
  const [erreurs, setErreurs] = useState({})
  const [enCours, setEnCours] = useState(false)
  if (blocs.length === 0) return null

  const corps = corpsEdition(blocs, saisie)
  const modifie = Object.keys(corps).length > 0
  const poser = (rubrique, clef, valeur) => setSaisie((s) => ({ ...s, [rubrique]: { ...s[rubrique], [clef]: valeur } }))

  const enregistrer = (evenement) => {
    evenement.preventDefault()
    setEnCours(true)
    setErreurs({})
    calepinageApi.calepinages.enregistrerEditionSld(id, corps)
      .then((reponse) => {
        onPoste(reponse?.data)
        setSaisie({ libelles: {}, reperes: {} })
      })
      .catch((err) => {
        const donneesRefus = err?.response?.data
        const parChamp = {}
        if (donneesRefus && typeof donneesRefus === 'object') {
          for (const [cle, m] of Object.entries(donneesRefus)) parChamp[cle] = Array.isArray(m) ? m.join(' ') : String(m)
        }
        setErreurs(Object.keys(parChamp).length ? parChamp : { edition: 'Édition non enregistrée : le serveur n’a pas accepté la saisie.' })
      })
      .finally(() => setEnCours(false))
  }

  const refus = (rubrique, clef) => erreurs[`edition.${rubrique}.${clef}`]
  const connus = new Set(blocs.flatMap((b) => [`edition.libelles.${b.clef}`, `edition.reperes.${b.clef}`]))
  const generaux = Object.entries(erreurs).filter(([cle]) => !connus.has(cle))

  return (
    <form className="flex flex-col gap-3" onSubmit={enregistrer} data-testid="acal161-edition">
      <h3 className="text-sm font-semibold">Libellés et repères des blocs</h3>
      {generaux.map(([cle, m]) => (
        <p key={cle} role="alert" className="text-sm text-destructive" data-testid="acal161-bandeau">{`${cle} : ${m}`}</p>
      ))}
      <ul className="flex flex-col gap-2">
        {blocs.map((bloc) => (
          <li key={bloc.clef} className="grid gap-2 sm:grid-cols-2" data-testid={`acal161-bloc-${bloc.clef}`}>
            {[['libelles', 'titre', 'Libellé'], ['reperes', 'repere', 'Repère']].map(([rubrique, cle, libelle]) => (
              <div key={rubrique} className="flex flex-col gap-1">
                <Label htmlFor={`acal161-${rubrique}-${bloc.clef}`}>{`${libelle} — ${bloc.clef}`}</Label>
                <Input
                  id={`acal161-${rubrique}-${bloc.clef}`}
                  value={saisie[rubrique][bloc.clef] ?? (bloc[cle] ?? '')}
                  invalid={Boolean(refus(rubrique, bloc.clef))}
                  onChange={(e) => poser(rubrique, bloc.clef, e.target.value)}
                />
                {refus(rubrique, bloc.clef)
                  ? <p className="text-xs text-destructive" data-testid={`acal161-erreur-${rubrique}-${bloc.clef}`}>{refus(rubrique, bloc.clef)}</p>
                  : null}
              </div>
            ))}
          </li>
        ))}
      </ul>
      <div>
        <Button
          type="submit"
          disabled={lectureSeule || !modifie || enCours}
          title={lectureSeule ? MOTIF_LECTURE_SEULE : undefined}
          data-testid="acal161-enregistrer"
        >
          {enCours ? 'Enregistrement…' : 'Enregistrer l’édition'}
        </Button>
      </div>
    </form>
  )
}

export default function SchemaUnifilairePanel({ calepinageId, lectureSeule = false }) {
  const { id: idRoute } = useParams()
  const id = calepinageId ?? idRoute

  const { data: lu, loading, error } = useResource(
    () => calepinageApi.calepinages.schemaUnifilaire(id), id,
    { select: (r) => r.data, errorMessage: 'Schéma unifilaire indisponible.' },
  )
  // ACAL161 — la réponse du POST d'édition (le MÊME document, édition appliquée) remplace
  // la lecture : le SVG relu porte le texte, sans second GET.
  const [poste, setPoste] = useState(null)
  const data = poste ?? lu

  const balisage = renderTrustedSvg(data?.svg)
  const [motifExport, setMotifExport] = useState(null)
  const [dxfEnCours, setDxfEnCours] = useState(false)

  // CALX236 — le clic sérialise le SVG déjà reçu (`data.svg`) : aucun second
  // appel à `schemaUnifilaire()`, aucune route neuve.
  const exporterPng = () => {
    setMotifExport(null)
    exporterSchemaPng(data.svg, nomFichierSchema(data?.calepinage, 'png'))
      .catch((err) => setMotifExport(err?.message || 'Export PNG impossible sur ce navigateur.'))
  }
  const telechargerSvg = () => {
    exporterSchemaSvg(data.svg, nomFichierSchema(data?.calepinage, 'svg'))
  }
  // CALX235 — le SEUL appel réseau de ce panneau : le DXF est produit par le
  // serveur depuis le même dessin, il n'est pas dans le DOM.
  const telechargerDxf = () => {
    setMotifExport(null)
    setDxfEnCours(true)
    calepinageApi.calepinages.sldDxf(id, OPTIONS_TELECHARGEMENT)
      .then((reponse) => {
        telechargerBlob(reponse.data, nomFichierSchema(data?.calepinage, 'dxf'))
      })
      .catch(async (err) => { setMotifExport(await motifDuRefusDxf(err)) })
      .finally(() => setDxfEnCours(false))
  }

  if (loading || error) {
    return <EtatEcranAtelier id={id} loading={loading} error={error} testIdErreur="cal195-erreur" />
  }

  return (
    <>
      <RetourAtelier calepinageId={id} />
      <Card className="flex flex-col gap-3 p-4" data-testid="cal195-panneau">
      <h2 className="text-base font-semibold">Schéma unifilaire</h2>
      {balisage
        ? (
          <>
            <div
              data-testid="cal195-svg"
              /* Le SVG vient du serveur, jamais d'une saisie. Il passe malgré
                 tout par `renderTrustedSvg` (VX120, défense en profondeur) :
                 un balisage capable d'exécuter du code n'est PAS inséré — on
                 montre alors les motifs plutôt qu'un cadre piégé. */
              dangerouslySetInnerHTML={balisage}
            />
            {/* CALX236 — les boutons n'existent QUE quand un schéma est
                affiché : `svg` nul n'a rien à exporter. */}
            <div className="flex flex-wrap gap-2" data-testid="calx236-export">
              <Button type="button" onClick={exporterPng} data-testid="calx236-exporter-png">
                Exporter en PNG
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={telechargerSvg}
                data-testid="calx236-telecharger-svg"
              >
                Télécharger le SVG
              </Button>
              {/* CALX235/236 — le DXF : même dessin, repris par un bureau
                  d'études. Produit par le serveur, donc un appel réseau. */}
              <Button
                type="button"
                variant="outline"
                onClick={telechargerDxf}
                disabled={dxfEnCours}
                data-testid="calx235-telecharger-dxf"
              >
                {dxfEnCours ? 'Préparation du DXF…' : 'Télécharger le DXF'}
              </Button>
            </div>
            {motifExport
              ? <p className="text-sm text-destructive" data-testid="calx236-erreur-export">{motifExport}</p>
              : null}
            <EditionSchema id={id} donnees={data} onPoste={setPoste} lectureSeule={lectureSeule} />
          </>
        )
        : <MotifsSchema donnees={data} />}
    </Card>
    </>
  )
}
