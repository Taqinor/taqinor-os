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
/* VT13 (fondateur 10/09/2026) — LA PHOTO RÉELLE DU TOIT SOUS CE TRACÉ.
   Quand la visite terrain du lead a été VALIDÉE et son toit assemblé calé
   (VT9/VT11), la photo réelle se drape ICI, en calque de fond du contour —
   la même image, dans le même repère, que celle de l'atelier 3D. Elle est
   demandée au serveur par la porte VT12 (`crmApi.getLeadPhotoToit`, forme
   {visite_id, url, texture_calage}) : sans visite validée, les trois clés
   sont nulles et RIEN ne s'affiche de plus qu'avant. Une bascule « Photo
   réelle » la masque quand elle gêne la lecture du tracé. */
import { useEffect, useMemo, useState } from 'react'
import crmApi from '../../../../api/crmApi'
import PhotoToitOverlay from '../PhotoToitOverlay'
import { normaliserTextureToit } from '../photoToit'
import {
  dessinerContour, formaterSurface, lienCarte, normaliserEpingle,
} from '../traceToit'

export default function TraceToitClient({ contour, epingle, leadId = null }) {
  const dessin = useMemo(() => dessinerContour(contour), [contour])
  const pin = useMemo(() => normaliserEpingle(epingle), [epingle])
  // Le repère explicite du client PRIME sur le centre calculé du tracé.
  const position = pin || dessin?.centre || null
  const carte = lienCarte(position)
  const surface = dessin ? formaterSurface(dessin.aireM2) : null

  // La texture est mémorisée AVEC l'id du lead auquel elle appartient : aucun
  // `setState` dans le corps de l'effet (react-hooks v7) et jamais la photo
  // d'un lead précédent — un id qui ne correspond plus n'est simplement pas lu.
  const [chargee, setChargee] = useState(null)
  const [photoVisible, setPhotoVisible] = useState(true)
  const texture = chargee && chargee.leadId === leadId ? chargee.texture : null

  useEffect(() => {
    if (!leadId) return undefined
    let vivant = true
    crmApi.getLeadPhotoToit(leadId)
      .then((res) => {
        if (vivant) setChargee({ leadId, texture: normaliserTextureToit(res?.data) })
      })
      // Une texture indisponible ne doit JAMAIS casser la fiche lead : le
      // bloc retombe simplement sur le tracé seul, comme avant VT13.
      .catch(() => { if (vivant) setChargee({ leadId, texture: null }) })
    return () => { vivant = false }
  }, [leadId])

  if (!dessin && !pin) return null

  return (
    <div className="lw-trace-toit" data-lw-trace-toit={dessin ? 'contour' : 'epingle'}>
      <p className="lw-trace-toit-titre">
        {dessin ? 'Toit dessiné par le client' : 'Toit épinglé par le client'}
      </p>

      {dessin && (
        <div className="lw-trace-toit-boite">
          <PhotoToitOverlay dessin={dessin} texture={texture} visible={photoVisible} />
          <svg
            className="lw-trace-toit-forme"
            viewBox={`-2 -2 ${dessin.largeur + 4} ${dessin.hauteur + 4}`}
            role="img"
            aria-label={`Contour du toit tracé par le client : ${dessin.sommets} points`}
            preserveAspectRatio="xMidYMid meet"
          >
            <polygon points={dessin.points} />
          </svg>
        </div>
      )}

      {texture && dessin && (
        <button
          type="button"
          className="lw-trace-toit-photo-bascule"
          aria-pressed={photoVisible}
          onClick={() => setPhotoVisible((v) => !v)}
          data-testid="lw-photo-toit-bascule"
        >
          {photoVisible ? 'Photo réelle : affichée' : 'Photo réelle : masquée'}
        </button>
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
