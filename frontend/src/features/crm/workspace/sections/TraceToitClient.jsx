/* L-DESSIN (ordre fondateur 25/08/2026) — LE DESSIN DU CLIENT, VISIBLE.
   ---------------------------------------------------------------------------
   Bloc LECTURE SEULE en tête de « Toiture & site » : le contour que le client
   a tracé sur la carte satellite du tunnel public s'affiche ENFIN tel qu'il
   l'a dessiné (polygone SVG, nord en haut), avec ses mesures calculées sur ses
   propres sommets et un lien carte vers le centre du tracé.

   Aucune dépendance : pas de MapLibre, pas de Leaflet, pas de clé MapTiler,
   aucun appel réseau — donc jamais un cadre vide sur un poste sans clé (le
   piège de `RepriseCarte.jsx`, qui dégrade en message d'erreur sans carte).

   RIEN N'EST INVENTÉ : sans contour ET sans épingle, le composant rend `null`
   (aucun cadre, aucun « toit non renseigné »). Avec l'épingle seule, il dit
   exactement ça — « repère posé, aucun contour tracé ». */
import { useMemo } from 'react'
import {
  dessinerContour, formaterSurface, lienCarte, normaliserEpingle,
} from '../traceToit'

export default function TraceToitClient({ contour, epingle }) {
  const dessin = useMemo(() => dessinerContour(contour), [contour])
  const pin = useMemo(() => normaliserEpingle(epingle), [epingle])
  // Le repère explicite du client PRIME sur le centre calculé du tracé.
  const position = pin || dessin?.centre || null
  const carte = lienCarte(position)
  const surface = dessin ? formaterSurface(dessin.aireM2) : null

  if (!dessin && !pin) return null

  return (
    <div className="lw-trace-toit" data-lw-trace-toit={dessin ? 'contour' : 'epingle'}>
      <p className="lw-trace-toit-titre">
        {dessin ? 'Toit dessiné par le client' : 'Toit épinglé par le client'}
      </p>

      {dessin && (
        <svg
          className="lw-trace-toit-forme"
          viewBox={`-2 -2 ${dessin.largeur + 4} ${dessin.hauteur + 4}`}
          role="img"
          aria-label={`Contour du toit tracé par le client : ${dessin.sommets} points`}
          preserveAspectRatio="xMidYMid meet"
        >
          <polygon points={dessin.points} />
        </svg>
      )}

      <ul className="lw-trace-toit-faits">
        {dessin ? (
          <>
            <li>{`${dessin.sommets} points tracés`}</li>
            {surface && <li>{`≈ ${surface} au sol`}</li>}
            <li>
              {`emprise ≈ ${Math.round(dessin.largeurM)} × ${Math.round(dessin.hauteurM)} m`}
            </li>
          </>
        ) : (
          <li>Repère posé sur la carte — aucun contour tracé.</li>
        )}
        {position && (
          <li>{`${position.lat.toFixed(5)}, ${position.lng.toFixed(5)}`}</li>
        )}
      </ul>

      {carte && (
        <a
          className="lw-trace-toit-lien"
          href={carte}
          target="_blank"
          rel="noopener noreferrer"
        >
          📍 Voir sur la carte
        </a>
      )}
      {dessin && (
        <p className="lw-trace-toit-note">
          Mesures calculées sur les sommets tracés par le client. Le contour est déjà chargé
          dans « Concevoir la toiture (3D) ».
        </p>
      )}
    </div>
  )
}
