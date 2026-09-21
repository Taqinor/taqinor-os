/* eslint-disable react-refresh/only-export-components --
   `positionsInitiales`/`coinsDepuisMarqueurs` sont des fonctions PURES
   (géométrie, zéro React) : la tâche exige un « test unitaire des maths de
   calage », qui doit pouvoir les appeler sans monter Leaflet — même
   dérogation que `PlanImporteCalage.jsx` (CAL63) du même module. */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import calepinageApi from '../../api/calepinageApi'
import {
  Button, Card, FileUpload, Input, Label, Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue, Spinner,
} from '../../ui'
import { warpImageToQuad, boundingBox } from '../../lib/roofTextureWarp'

/* ============================================================================
   CAL53 — CALER LA PHOTO DE SITE (drone/oblique/sol, CAL52) SUR LA CARTE.
   ----------------------------------------------------------------------------
   Constat de la tâche : le drapage par transformation affine existe déjà
   (`roofTextureWarp.js`, VT11) mais n'était câblé que sur la photo de visite
   terrain (`CalageToitPage.jsx`). Ce composant reprend EXACTEMENT le même
   mécanisme — 4 poignées de coins déplaçables sur une carte Leaflet,
   drapage par transformation affine par triangles — pour UNE photo de site
   du module calepinage. AUCUNE reconstruction 3D : un aperçu 2D drapé, rien
   de plus (même limite que VT11).

   LE CALAGE EST PERSISTÉ DANS LE CALEPINAGE (colonne `PhotoSite.calage`,
   posée par CAL52), relu tel quel à la réouverture — jamais recalculé côté
   écran. `PATCH .../photos/<id>/calage/` (CAL53, ce fichier lui donne son
   premier appelant) ne touche QUE cette colonne : aucun statut ne bouge
   (règle #4), et la bascule photo terrain existante (`ToitureDesign.jsx`,
   `rp9-photo-toit-toggle`) n'est PAS modifiée — chemin entièrement séparé.

   LE TRACÉ DE RÉFÉRENCE, quand il existe (`contexte_geographique.outline`,
   CAL15), est dessiné comme un polygone AU-DESSUS du calque drapé — la photo
   reste visible SOUS le tracé, exactement le contraire d'un calque qui
   masquerait le contour déjà connu.
   ========================================================================== */

const DEFAULT_CENTER = [31.7917, -7.0926] // Maroc — repli si rien n'est connu.
const DELTA = 0.00012 // ≈13 m — écart initial des 4 poignées autour du centre.

/* CALX38 — LE DÉPÔT D'UNE PHOTO DE SITE, EN TÊTE DU PANNEAU DE CALAGE.
   ----------------------------------------------------------------------------
   Constat : `calepinageApi.js` expose déjà `ajouterPhoto` (servie par
   `views/photos.py:40-70`) mais AUCUN écran ne l'appelait — ce panneau
   invitait pourtant à « déposer une photo drone/oblique/sol avant de la
   caler », un geste qui n'existait nulle part.

   `genre` ET `prise_le` sont REFUSÉS avant tout envoi, champ pointé — même
   si le serveur, lui, retombe sur `drone` faute de genre : un genre choisi
   EN SILENCE serait une valeur inventée par l'écran, pas une saisie
   (règle « zéro chiffre inventé »). La date de prise de vue, elle, EST
   obligatoire côté serveur aussi (`services/photos.py::_date_saisie`).

   Les 3 genres viennent EXACTEMENT de `PhotoSite.Genre` (models.py) — en
   inventer un quatrième produirait un `genre` que le serveur refuse. */
const GENRES_PHOTO = [
  ['drone', 'Drone'],
  ['oblique', 'Oblique (aérienne)'],
  ['sol', 'Depuis le sol'],
]
const TAILLE_MAX_OCTETS = 15 * 1024 * 1024 // MAX_OCTETS, services/photos.py

/**
 * Les 4 positions `[lat, lng]` de départ des poignées : celles d'un calage
 * déjà enregistré (relecture EXACTE, jamais recalculée), sinon un petit carré
 * autour du `centre` donné. Fonction PURE — testable sans monter la carte.
 */
export function positionsInitiales(calageExistant, centre) {
  const coins = calageExistant?.coins
  if (Array.isArray(coins) && coins.length === 4) return coins
  const [lat, lng] = centre ?? DEFAULT_CENTER
  return [
    [lat + DELTA, lng - DELTA],
    [lat + DELTA, lng + DELTA],
    [lat - DELTA, lng + DELTA],
    [lat - DELTA, lng - DELTA],
  ]
}

/** Les 4 marqueurs Leaflet → `[[lat, lng] × 4]`, dans leur ordre de pose. */
export function coinsDepuisMarqueurs(marqueurs) {
  return marqueurs.map((m) => {
    const ll = m.getLatLng()
    return [ll.lat, ll.lng]
  })
}

function numeroteIcon(n) {
  return L.divIcon({
    html: `<div class="grid size-7 place-items-center rounded-full border-2 border-white bg-primary text-xs font-bold text-primary-foreground shadow">${n}</div>`,
    className: 'cal-photo-calage-pin',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })
}

export default function PhotoSiteCalage({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [photos, setPhotos] = useState([])
  const [contexte, setContexte] = useState(null)
  const [photoId, setPhotoId] = useState(null)
  const [opacite, setOpacite] = useState(0.85)
  const [enregistrement, setEnregistrement] = useState(false)
  const [message, setMessage] = useState(null)
  const [chargement, setChargement] = useState(true)

  // CALX38 — le dépôt d'une photo de site.
  const [genreDepot, setGenreDepot] = useState('')
  const [priseLeDepot, setPriseLeDepot] = useState('')
  const [legendeDepot, setLegendeDepot] = useState('')
  const [erreursDepot, setErreursDepot] = useState({})
  const [depotEnCours, setDepotEnCours] = useState(false)
  const [progressionDepot, setProgressionDepot] = useState(undefined)

  const mapRef = useRef(null)
  const containerRef = useRef(null)
  const markersRef = useRef([])
  const polygonRef = useRef(null)
  const canvasRef = useRef(null)
  const imageRef = useRef(null)

  const recharger = useCallback(() => {
    if (!calepinageId) return
    Promise.all([
      Promise.resolve(calepinageApi.calepinages.photos(calepinageId)),
      Promise.resolve(calepinageApi.calepinages.get(calepinageId)),
    ])
      .then(([resPhotos, resDetail]) => {
        const liste = resPhotos?.data?.photos ?? []
        setPhotos(liste)
        setContexte(resDetail?.data?.contexte_geographique ?? null)
        setPhotoId((courant) => (
          courant && liste.some((p) => p.id === courant)
            ? courant
            : (liste[0]?.id ?? null)
        ))
      })
      .catch(() => { setPhotos([]); setContexte(null) })
      .finally(() => setChargement(false))
  }, [calepinageId])

  useEffect(() => { recharger() }, [recharger])

  // CALX38 — un genre ou une date absents sont REFUSÉS avant tout envoi (le
  // fichier reste choisi côté navigateur, aucun octet n'est parti).
  const deposerPhoto = (fichiers) => {
    const fichier = fichiers?.[0]
    if (!fichier || !calepinageId) return
    const erreurs = {}
    if (!genreDepot) erreurs.genre = 'Le genre de la photo est obligatoire.'
    if (!priseLeDepot) erreurs.prise_le = 'La date de prise de vue est obligatoire.'
    setErreursDepot(erreurs)
    if (Object.keys(erreurs).length) return

    setDepotEnCours(true)
    setProgressionDepot(20)
    setMessage(null)
    const corps = new FormData()
    corps.append('photo', fichier)
    corps.append('genre', genreDepot)
    corps.append('prise_le', priseLeDepot)
    if (legendeDepot) corps.append('legende', legendeDepot)

    setProgressionDepot(60)
    Promise.resolve(calepinageApi.calepinages.ajouterPhoto(calepinageId, corps))
      .then((res) => {
        setProgressionDepot(100)
        setMessage('Photo ajoutée : elle est calable ci-dessous.')
        setGenreDepot(''); setPriseLeDepot(''); setLegendeDepot(''); setErreursDepot({})
        const neuve = res?.data?.photo
        recharger()
        if (neuve?.id) setPhotoId(neuve.id)
      })
      .catch((e) => {
        const donnees = e?.response?.data
        if (donnees && typeof donnees === 'object') setErreursDepot(donnees)
        setMessage(donnees?.detail || 'Le dépôt de la photo a échoué.')
      })
      .finally(() => { setDepotEnCours(false); setProgressionDepot(undefined) })
  }

  const photo = photos.find((p) => p.id === photoId) ?? null

  // Redessine l'aperçu drapé en projetant les 4 poignées CARTE → pixels écran.
  const redessiner = useCallback(() => {
    const canvas = canvasRef.current
    const map = mapRef.current
    const image = imageRef.current
    if (!canvas || !map || !image?.complete) return
    const points = markersRef.current.map((m) => {
      const p = map.latLngToContainerPoint(m.getLatLng())
      return [p.x, p.y]
    })
    if (points.length !== 4) return
    const box = boundingBox(points)
    canvas.width = Math.max(1, Math.round(box.width))
    canvas.height = Math.max(1, Math.round(box.height))
    canvas.style.left = `${box.x}px`
    canvas.style.top = `${box.y}px`
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    const decale = points.map(([x, y]) => [x - box.x, y - box.y])
    ctx.globalAlpha = opacite
    warpImageToQuad(ctx, image, decale)
  }, [opacite])

  // Boot carte (une fois le calepinage/la photo connus) + 4 poignées.
  useEffect(() => {
    if (!photo || mapRef.current || !containerRef.current) return undefined
    const pin = contexte?.pin
    const centre = (pin?.lat != null && pin?.lng != null)
      ? [pin.lat, pin.lng]
      : DEFAULT_CENTER
    const map = L.map(containerRef.current, { center: centre, zoom: 20 })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 21,
    }).addTo(map)

    // Le tracé de référence — le calage doit rester visible SOUS lui.
    const outline = contexte?.outline
    if (Array.isArray(outline) && outline.length >= 3) {
      polygonRef.current = L.polygon(outline, {
        color: '#c9a24b', weight: 2, fill: false,
      }).addTo(map)
    }

    const positions = positionsInitiales(photo.calage, centre)
    markersRef.current = positions.map((pos, i) => {
      const marker = L.marker(pos, { draggable: true, icon: numeroteIcon(i + 1) }).addTo(map)
      marker.on('drag', redessiner)
      return marker
    })
    map.on('move zoom', redessiner)
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      markersRef.current = []
      polygonRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photo?.id])

  useEffect(() => { redessiner() }, [photo?.url, opacite, redessiner])

  const enregistrer = () => {
    if (!photo || markersRef.current.length !== 4) return
    setEnregistrement(true)
    setMessage(null)
    const coins = coinsDepuisMarqueurs(markersRef.current)
    Promise.resolve(calepinageApi.calepinages.calerPhoto(calepinageId, photo.id, coins))
      .then(() => {
        setMessage('Calage enregistré.')
        recharger()
      })
      .catch(() => setMessage('Le calage n’a pas pu être enregistré.'))
      .finally(() => setEnregistrement(false))
  }

  const effacer = () => {
    if (!photo) return
    setEnregistrement(true)
    setMessage(null)
    Promise.resolve(calepinageApi.calepinages.calerPhoto(calepinageId, photo.id, null))
      .then(() => {
        setMessage('Calage effacé.')
        recharger()
      })
      .catch(() => setMessage('L’effacement du calage a échoué.'))
      .finally(() => setEnregistrement(false))
  }

  if (chargement) {
    return (
      <div className="page max-w-[900px]" data-testid="cal-photo-calage">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="page max-w-[900px]" data-testid="cal-photo-calage">
      <p className="tech-label rule-brass text-brass-300">Caler la photo du site</p>

      {/* CALX38 — dépôt d'une photo, EN TÊTE du panneau. */}
      <Card className="mt-3 space-y-3 p-4" data-testid="cal-photo-depot">
        <p className="tech-label text-lune-faint">Déposer une photo</p>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="cal-photo-depot-genre">Genre</Label>
            <Select value={genreDepot} onValueChange={setGenreDepot}>
              <SelectTrigger id="cal-photo-depot-genre" data-testid="cal-photo-depot-genre">
                <SelectValue placeholder="Choisir un genre…" />
              </SelectTrigger>
              <SelectContent>
                {GENRES_PHOTO.map(([valeur, libelle]) => (
                  <SelectItem key={valeur} value={valeur}>{libelle}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {erreursDepot.genre && (
              <p role="alert" className="text-xs text-destructive" data-testid="cal-photo-depot-erreur-genre">
                {erreursDepot.genre}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label htmlFor="cal-photo-depot-date">Prise de vue le</Label>
            <Input
              id="cal-photo-depot-date"
              type="date"
              value={priseLeDepot}
              onChange={(e) => setPriseLeDepot(e.target.value)}
              data-testid="cal-photo-depot-date"
            />
            {erreursDepot.prise_le && (
              <p role="alert" className="text-xs text-destructive" data-testid="cal-photo-depot-erreur-date">
                {erreursDepot.prise_le}
              </p>
            )}
          </div>
        </div>

        <div className="space-y-1">
          <Label htmlFor="cal-photo-depot-legende">Légende (facultatif)</Label>
          <Input
            id="cal-photo-depot-legende"
            value={legendeDepot}
            onChange={(e) => setLegendeDepot(e.target.value)}
            data-testid="cal-photo-depot-legende"
          />
        </div>

        <FileUpload
          accept="image/png,image/jpeg"
          maxSize={TAILLE_MAX_OCTETS}
          busy={depotEnCours}
          progress={progressionDepot}
          onFiles={deposerPhoto}
          data-testid="cal-photo-depot-fichier"
        />
        {erreursDepot.photo && (
          <p role="alert" className="text-xs text-destructive" data-testid="cal-photo-depot-erreur-photo">
            {erreursDepot.photo}
          </p>
        )}
      </Card>

      {photos.length === 0 && (
        <Card className="mt-3 p-4 text-sm text-lune-soft" data-testid="cal-photo-calage-vide">
          Aucune photo de site n’est encore rattachée à ce calepinage : déposez
          une photo drone/oblique/sol avant de la caler.
        </Card>
      )}

      {photos.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Select
            value={photoId ? String(photoId) : undefined}
            onValueChange={(v) => setPhotoId(Number(v))}
          >
            <SelectTrigger className="w-64" data-testid="cal-photo-calage-select">
              <SelectValue placeholder="Choisir une photo…" />
            </SelectTrigger>
            <SelectContent>
              {photos.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {(p.legende || p.filename)} — {p.genre}
                  {p.calage ? ' (calée)' : ''}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <label className="flex items-center gap-2 text-xs text-lune-soft">
            Opacité
            <input
              type="range"
              min="0.1"
              max="1"
              step="0.05"
              value={opacite}
              data-testid="cal-photo-calage-opacite"
              onChange={(e) => setOpacite(Number(e.target.value))}
            />
          </label>
        </div>
      )}

      {photo && (
        <>
          <div className="relative mt-3">
            <div
              ref={containerRef}
              className="h-[60vh] min-h-[360px] w-full rounded-lg border border-border"
              data-testid="cal-photo-calage-carte"
            />
            <canvas
              ref={(node) => { canvasRef.current = node; redessiner() }}
              className="pointer-events-none absolute"
              style={{ zIndex: 300 }}
              data-testid="cal-photo-calage-canvas"
            />
          </div>
          <img
            ref={imageRef}
            src={photo.url}
            alt=""
            hidden
            onLoad={redessiner}
            crossOrigin="anonymous"
          />

          <p className="mt-2 text-xs text-lune-faint">
            Déplacez les 4 poignées numérotées pour aligner la photo sur le
            contour réel du toit. Le calage est rechargé tel quel à la
            réouverture de cette photo.
          </p>

          <div className="mt-3 flex flex-wrap gap-3">
            <Button type="button" onClick={enregistrer} disabled={enregistrement}
              data-testid="cal-photo-calage-enregistrer">
              Enregistrer le calage
            </Button>
            {photo.calage && (
              <Button type="button" variant="ghost" onClick={effacer}
                disabled={enregistrement} data-testid="cal-photo-calage-effacer">
                Effacer le calage
              </Button>
            )}
          </div>

          {message && (
            <p className="mt-3 text-sm text-lune-soft" role="status"
              data-testid="cal-photo-calage-message">{message}</p>
          )}
        </>
      )}
    </div>
  )
}
