import { useCallback, useEffect, useRef, useState } from 'react'
import marketingApi from '../../api/marketingApi'
import {
  CANAUX_ACTION, CONDITIONS_ARC, CONDITIONS_AVEC_VALEUR, TAILLE_NOEUD,
  TYPES_NOEUD, ajouterArc, grapheDepuisApi, libelleCondition, nouveauNoeud,
  payloadArc, payloadNoeud, segmentArc,
} from './journeyGraph'

/* ============================================================================
   NTMKT13 — Canevas visuel du journey (SVG + drag MAISON, zéro dépendance).
   ----------------------------------------------------------------------------
   Aucune librairie de flow-chart n'est ajoutée (patron zéro-dépendance de
   Toiture-3D/DatePicker) : le canevas est un <svg> et le déplacement des
   nœuds un simple suivi de pointeur. Les données consommées sont EXACTEMENT
   celles livrées par NTMKT12 (`noeuds-journey` / `arcs-journey`) — le nœud
   est persisté dès sa création pour que les arcs puissent le référencer par
   son id serveur ; le déplacement n'enregistre la position qu'au relâchement.
   ========================================================================== */

export default function JourneyBuilder({ sequenceId, sequenceNom }) {
  const [noeuds, setNoeuds] = useState([])
  const [arcs, setArcs] = useState([])
  const [chargement, setChargement] = useState(true)
  const [err, setErr] = useState('')
  const [selection, setSelection] = useState(null)      // nœud sélectionné
  const [origineLien, setOrigineLien] = useState(null)  // départ d'une liaison
  const [condition, setCondition] = useState('toujours')
  const [valeur, setValeur] = useState('')
  const canevas = useRef(null)
  const drag = useRef(null)

  const charger = useCallback(async () => {
    if (!sequenceId) return
    setChargement(true)
    try {
      const [rn, ra] = await Promise.all([
        marketingApi.noeudsJourney.list({ sequence: sequenceId }),
        marketingApi.arcsJourney.list({ sequence: sequenceId }),
      ])
      const g = grapheDepuisApi(
        marketingApi.unwrapList(rn), marketingApi.unwrapList(ra))
      setNoeuds(g.noeuds)
      setArcs(g.arcs)
      setErr('')
    } catch {
      setErr('Chargement du journey impossible.')
    } finally {
      setChargement(false)
    }
  }, [sequenceId])

  useEffect(() => { charger() }, [charger])

  // ── Palette : ajouter un nœud (persisté immédiatement) ───────────────────
  const ajouterNoeud = async (type) => {
    const y = 40 + noeuds.length * 20
    const brouillon = nouveauNoeud(type, 40 + noeuds.length * 30, y)
    try {
      const res = await marketingApi.noeudsJourney.create(
        payloadNoeud(brouillon, sequenceId))
      setNoeuds(ns => [...ns, { ...brouillon, id: res?.data?.id, sequence: sequenceId }])
      setErr('')
    } catch {
      setErr("Ajout du nœud impossible.")
    }
  }

  // ── Drag maison : pointer down/move/up sur le groupe SVG du nœud ─────────
  const onPointerDown = (noeud) => (e) => {
    if (origineLien) return
    const rect = canevas.current?.getBoundingClientRect()
    drag.current = {
      id: noeud.id,
      dx: e.clientX - (rect?.left || 0) - noeud.x,
      dy: e.clientY - (rect?.top || 0) - noeud.y,
    }
    setSelection(noeud.id)
  }

  const onPointerMove = (e) => {
    if (!drag.current) return
    const rect = canevas.current?.getBoundingClientRect()
    const x = Math.max(0, e.clientX - (rect?.left || 0) - drag.current.dx)
    const y = Math.max(0, e.clientY - (rect?.top || 0) - drag.current.dy)
    setNoeuds(ns => ns.map(n => (n.id === drag.current.id
      ? { ...n, x: Math.round(x), y: Math.round(y) } : n)))
  }

  const onPointerUp = async () => {
    const encours = drag.current
    drag.current = null
    if (!encours) return
    const noeud = noeuds.find(n => n.id === encours.id)
    if (!noeud) return
    try {
      await marketingApi.noeudsJourney.update(noeud.id, {
        position_x: noeud.x, position_y: noeud.y,
      })
    } catch {
      setErr('Position non enregistrée.')
    }
  }

  // ── Liaison : clic sur le nœud source puis sur le nœud cible ─────────────
  const cliquerNoeud = async (noeud) => {
    if (!origineLien) { setOrigineLien(noeud.id); return }
    if (origineLien === noeud.id) { setOrigineLien(null); return }
    const avant = arcs
    const apres = ajouterArc(avant, {
      source: origineLien, cible: noeud.id, condition, valeur,
    })
    setOrigineLien(null)
    if (apres === avant) { setErr('Connexion déjà existante ou invalide.'); return }
    const nouvelArc = apres[apres.length - 1]
    try {
      const res = await marketingApi.arcsJourney.create(payloadArc(nouvelArc))
      setArcs([...avant, { ...nouvelArc, id: res?.data?.id }])
      setErr('')
    } catch {
      setErr('Connexion non enregistrée.')
    }
  }

  const supprimerNoeud = async (noeud) => {
    try {
      await marketingApi.noeudsJourney.remove(noeud.id)
      setNoeuds(ns => ns.filter(n => n.id !== noeud.id))
      setArcs(as => as.filter(a => a.source !== noeud.id && a.cible !== noeud.id))
    } catch {
      setErr('Suppression impossible.')
    }
  }

  const majConfig = async (noeud, cle, val) => {
    const config = { ...(noeud.config || {}), [cle]: val }
    setNoeuds(ns => ns.map(n => (n.id === noeud.id ? { ...n, config } : n)))
    try {
      await marketingApi.noeudsJourney.update(noeud.id, { config })
    } catch {
      setErr('Réglage du nœud non enregistré.')
    }
  }

  const noeudSelectionne = noeuds.find(n => n.id === selection) || null

  return (
    <div className="journey-builder">
      <h3>Journey {sequenceNom ? `— ${sequenceNom}` : ''}</h3>
      {err && <p role="alert">{err}</p>}
      {chargement && <p>Chargement…</p>}

      <div className="journey-palette">
        {TYPES_NOEUD.map(t => (
          <button key={t.key} type="button" onClick={() => ajouterNoeud(t.key)}>
            + {t.label}
          </button>
        ))}
      </div>

      <div className="journey-liaison">
        <label>
          Condition de la prochaine connexion
          <select value={condition} onChange={e => setCondition(e.target.value)}>
            {CONDITIONS_ARC.map(c => (
              <option key={c.key} value={c.key}>{c.label}</option>
            ))}
          </select>
        </label>
        {CONDITIONS_AVEC_VALEUR.includes(condition) && (
          <label>
            Valeur
            <input value={valeur} onChange={e => setValeur(e.target.value)} />
          </label>
        )}
        <span>
          {origineLien
            ? 'Cliquez le nœud cible pour créer la connexion.'
            : 'Cliquez un nœud source pour démarrer une connexion.'}
        </span>
      </div>

      <svg
        ref={canevas}
        className="journey-canevas"
        width="100%"
        height="420"
        role="application"
        aria-label="Canevas du journey"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        {arcs.map((arc, i) => {
          const seg = segmentArc(noeuds, arc)
          if (!seg) return null
          return (
            <g key={arc.id || `arc-${i}`}>
              <line
                x1={seg.x1} y1={seg.y1} x2={seg.x2} y2={seg.y2}
                stroke="currentColor" strokeWidth="2"
              />
              <text
                x={(seg.x1 + seg.x2) / 2} y={(seg.y1 + seg.y2) / 2 - 4}
                fontSize="11" textAnchor="middle"
              >
                {libelleCondition(arc)}
              </text>
            </g>
          )
        })}
        {noeuds.map(noeud => (
          <g
            key={noeud.id}
            transform={`translate(${noeud.x},${noeud.y})`}
            onPointerDown={onPointerDown(noeud)}
            onClick={() => cliquerNoeud(noeud)}
          >
            <rect
              width={TAILLE_NOEUD.largeur} height={TAILLE_NOEUD.hauteur}
              rx="8" fill="var(--surface, #fff)" stroke="currentColor"
              strokeWidth={origineLien === noeud.id ? 3 : 1}
            />
            <text x="10" y="22" fontSize="12">{noeud.libelle}</text>
            <text x="10" y="40" fontSize="10">{noeud.type_noeud}</text>
          </g>
        ))}
      </svg>

      {noeudSelectionne && (
        <div className="journey-inspecteur">
          <h4>Nœud « {noeudSelectionne.libelle} »</h4>
          {noeudSelectionne.type_noeud === 'attente' && (
            <label>
              Délai (jours)
              <input
                type="number" min="0"
                value={noeudSelectionne.config?.delai_jours ?? ''}
                onChange={e => majConfig(
                  noeudSelectionne, 'delai_jours', Number(e.target.value) || 0)}
              />
            </label>
          )}
          {noeudSelectionne.type_noeud === 'action' && (
            <label>
              Canal
              <select
                value={noeudSelectionne.config?.canal || ''}
                onChange={e => majConfig(noeudSelectionne, 'canal', e.target.value)}
              >
                <option value="">—</option>
                {CANAUX_ACTION.map(c => (
                  <option key={c.key} value={c.key}>{c.label}</option>
                ))}
              </select>
            </label>
          )}
          <button type="button" onClick={() => supprimerNoeud(noeudSelectionne)}>
            Supprimer ce nœud
          </button>
        </div>
      )}
    </div>
  )
}
