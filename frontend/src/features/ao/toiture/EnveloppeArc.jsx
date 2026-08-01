/* AOF91 — Enveloppe en ARC : saisie PARAMÉTRIQUE, rendu développé ET rendu réel.
   ----------------------------------------------------------------------------
   Un arc ne se trace pas à la souris. On le SAISIT : rayon extérieur, largeur,
   longueurs développées des segments, épaisseur des murets qui les séparent.
   Le relevé de référence : R_ext 274,00 · largeur 10,90 (donc R_int 263,10) ·
   trois segments 20,55 + 23,00 + 23,60 séparés par deux murets de 0,45 —
   développé muret-à-muret 68,05 m.

   DEUX PIÈGES QUE CET ÉCRAN EXISTE POUR ÉVITER :

   1. UNE RANGÉE À CHEVAL SUR UN MURET. Chaque segment a son PROPRE plan de pose
      et ses rives d'extrémité (0,35 m) : une rangée proposée par-dessus un muret
      n'est pas une rangée « presque bonne », c'est une rangée impossible à
      poser. L'écran ne la propose donc jamais, et il l'affiche : « 0 rangée à
      cheval ».

   2. LE PAS DE POSE MESURÉ AU MAUVAIS RAYON. Poser les tables jointives en
      abscisse DÉVELOPPÉE (celle du bord extérieur) les fait se RECOUVRIR de
      quelques centimètres au rayon INTÉRIEUR — le bord intérieur est plus court.
      Le pas vaut donc `largeur_module × R_ext / (R_int + y0)`, évalué au bord
      intérieur (y0 = 0), là où la contrainte est la plus dure. L'écran affiche
      le recouvrement ainsi ÉVITÉ, en centimètres : c'est ce chiffre qui explique
      pourquoi on pose quelques modules de moins.

   Les deux rendus sont côte à côte parce qu'ils ne servent pas à la même chose :
   le développé est celui sur lequel on relève et on cote, le réel est celui que
   le maître d'ouvrage reconnaît sur sa toiture. */
import { useCallback, useMemo, useState } from 'react'
import {
  ARC_REFERENCE,
  m,
  validerArc,
  decouperArc,
  rangeesProposees,
  rangeeACheval,
  recouvrementEvite,
  cheminSecteur,
  boiteArc,
} from './EnveloppeArc.geometrie'

/* ── Écran ──────────────────────────────────────────────────────────────────── */

// Centre de l'arc en X : à l'origine (l'arc est centré autour de son axe vertical).
const CX = 0

export default function EnveloppeArc({
  valeurInitiale = ARC_REFERENCE,
  moduleLargeurM = 1.134,
  onValider,
}) {
  const [params, setParams] = useState(valeurInitiale)
  const [refus, setRefus] = useState(null)

  const majChamp = useCallback(
    (champ, valeur) => setParams((p) => ({ ...p, [champ]: valeur })),
    [],
  )

  const majSegments = useCallback((texte) => {
    setParams((p) => ({
      ...p,
      segmentsM: texte
        .split(/[;,\s]+/)
        .map((t) => t.trim())
        .filter(Boolean)
        .map((t) => Number(t.replace(',', '.'))),
    }))
  }, [])

  const controle = useMemo(() => validerArc(params), [params])
  const { arc, pas, rangees } = useMemo(
    () => rangeesProposees(params, moduleLargeurM),
    [params, moduleLargeurM],
  )
  const aCheval = useMemo(
    () => rangees.filter((r) => rangeeACheval(r, arc.murets)),
    [rangees, arc.murets],
  )
  const recouvrement = useMemo(
    () => recouvrementEvite(moduleLargeurM, arc.rayonExtM, arc.rayonIntM, 0),
    [moduleLargeurM, arc.rayonExtM, arc.rayonIntM],
  )

  // Centre de l'arc : à l'origine en X, au rayon extérieur en Y (l'arc « pend »
  // sous son centre), pour que le secteur tienne dans un viewBox positif.
  const boite = useMemo(
    () => (controle.valide ? boiteArc(arc, CX, arc.rayonExtM) : null),
    [controle.valide, arc],
  )

  const valider = useCallback(() => {
    const c = validerArc(params)
    if (!c.valide) {
      setRefus(c.motifs)
      return
    }
    setRefus(null)
    onValider?.({ ...params, ...decouperArc(params) })
  }, [params, onValider])

  const segmentsTexte = (params.segmentsM ?? []).join(' ')

  return (
    <section className="ao-enveloppe-arc" data-ao-enveloppe="arc">
      <h3>Enveloppe en arc</h3>

      <div className="ao-arc-parametres">
        <label className="ao-champ" htmlFor="ao-arc-rayon">
          <span>Rayon extérieur (m)</span>
          <input
            id="ao-arc-rayon"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.rayonExtM ?? ''}
            onChange={(e) => majChamp('rayonExtM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-largeur">
          <span>Largeur de la bande (m)</span>
          <input
            id="ao-arc-largeur"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.largeurM ?? ''}
            onChange={(e) => majChamp('largeurM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-segments">
          <span>Segments — longueurs développées (m)</span>
          <input
            id="ao-arc-segments"
            className="form-control"
            type="text"
            value={segmentsTexte}
            onChange={(e) => majSegments(e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-muret">
          <span>Épaisseur des murets (m)</span>
          <input
            id="ao-arc-muret"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.muretM ?? ''}
            onChange={(e) => majChamp('muretM', e.target.value)}
          />
        </label>
        <label className="ao-champ" htmlFor="ao-arc-rive">
          <span>Rive d’extrémité par segment (m)</span>
          <input
            id="ao-arc-rive"
            className="form-control"
            type="text"
            inputMode="decimal"
            value={params.riveM ?? ''}
            onChange={(e) => majChamp('riveM', e.target.value)}
          />
        </label>
      </div>

      {refus && (
        <ul role="alert" data-ao-arc-refus={refus.length}>
          {refus.map((motif) => (
            <li key={motif}>{motif}</li>
          ))}
        </ul>
      )}

      <p data-ao-arc-developpe={arc.developpeTotal.toFixed(2)}>
        Développé muret-à-muret&nbsp;: {m(arc.developpeTotal)} m — rayon intérieur{' '}
        {m(arc.rayonIntM)} m sur {arc.segments.length} segment
        {arc.segments.length > 1 ? 's' : ''} et {arc.murets.length} muret
        {arc.murets.length > 1 ? 's' : ''}.
      </p>

      <p data-ao-arc-pas={pas.toFixed(4)}>
        Pas de pose corrigé&nbsp;: {pas.toFixed(3).replace('.', ',')} m pour une table de{' '}
        {m(moduleLargeurM)} m — {(recouvrement * 100).toFixed(1).replace('.', ',')} cm de
        recouvrement évité au rayon intérieur par table.
      </p>

      <p data-ao-arc-a-cheval={aCheval.length}>
        {rangees.length} rangée{rangees.length > 1 ? 's' : ''} proposée
        {rangees.length > 1 ? 's' : ''}, {aCheval.length} à cheval sur un muret.
      </p>

      {/* Les deux rendus, CÔTE À CÔTE : le développé sert au relevé, le réel est
          celui que le maître d'ouvrage reconnaît sur sa toiture. */}
      <div className="ao-arc-rendus">
        <figure className="ao-arc-rendu" data-ao-arc-rendu="developpe">
          <figcaption>Rendu développé</figcaption>
          <svg
            viewBox={`-1 -1 ${arc.developpeTotal + 2} ${arc.largeurM + 2}`}
            role="img"
            aria-label={`Développé de ${m(arc.developpeTotal)} mètres`}
            data-ao-canvas="arc-developpe"
          >
            {arc.segments.map((seg) => (
              <rect
                key={`s${seg.index}`}
                x={seg.debut}
                y={0}
                width={seg.longueur}
                height={arc.largeurM}
                className="ao-arc-segment"
                data-ao-arc-segment={seg.index}
              />
            ))}
            {arc.murets.map((mu) => (
              <rect
                key={`m${mu.index}`}
                x={mu.debut}
                y={0}
                width={mu.fin - mu.debut}
                height={arc.largeurM}
                className="ao-arc-muret"
                data-ao-arc-muret={mu.index}
              />
            ))}
            {rangees.map((r) => (
              <rect
                key={`r${r.debut.toFixed(3)}`}
                x={r.debut}
                y={0}
                width={r.fin - r.debut}
                height={arc.largeurM}
                className="ao-arc-rangee"
                fill="none"
              />
            ))}
          </svg>
        </figure>

        <figure className="ao-arc-rendu" data-ao-arc-rendu="reel">
          <figcaption>Rendu réel</figcaption>
          {boite ? (
            <svg
              viewBox={`${boite.x} ${boite.y} ${boite.largeur} ${boite.hauteur}`}
              role="img"
              aria-label={`Arc réel de rayon extérieur ${m(arc.rayonExtM)} mètres`}
              data-ao-canvas="arc-reel"
            >
              {arc.segments.map((seg) => (
                <path
                  key={`rs${seg.index}`}
                  d={cheminSecteur(arc, seg.debut, seg.fin, CX, arc.rayonExtM)}
                  className="ao-arc-segment"
                  data-ao-arc-segment-reel={seg.index}
                />
              ))}
              {arc.murets.map((mu) => (
                <path
                  key={`rm${mu.index}`}
                  d={cheminSecteur(arc, mu.debut, mu.fin, CX, arc.rayonExtM)}
                  className="ao-arc-muret"
                  data-ao-arc-muret-reel={mu.index}
                />
              ))}
            </svg>
          ) : (
            <p>Rendu réel indisponible tant que le rayon et la largeur ne sont pas saisis.</p>
          )}
        </figure>
      </div>

      <button type="button" onClick={valider} data-ao-arc-valider>
        Valider l’enveloppe en arc
      </button>
    </section>
  )
}
