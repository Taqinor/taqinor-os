// VT11 — Calage du toit réaliste : l'image assemblée (ou une photo choisie si
// l'assemblage a échoué) est drapée sur le contour du toit par 4 poignées de
// coins déplaçables sur une carte géo-référencée (transformation perspective
// sur canvas, `roofTextureWarp.js`), sauvegardée comme `texture_calage`
// {coins:[[lat,lng]×4]}. Pendant l'assemblage : état `en_cours` + polling ;
// en échec, le message affiché est TOUJOURS celui du serveur
// (`photo_toit.assemblage_erreur`), jamais un texte inventé ici. Jamais de
// reconstruction 3D — un aperçu 2D drapé, rien de plus.
//
// PORTÉE DE L'INTÉGRATION CARTE/ATELIER (documentée honnêtement) : le builder
// 3D vendored (`@roofbuilder`, ToitureDesign.jsx) n'expose aucune API pour
// recevoir une texture image géo-référencée depuis l'extérieur, et n'est
// JAMAIS édité (source figée) — l'« overlay calé visible dans l'atelier »
// prend donc la forme d'un bandeau/aperçu à côté de la carte (ce fichier),
// pas d'une texture injectée dans la scène three.js du builder.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import visitesApi from '../../api/visitesApi'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Card, Spinner, Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../ui'
import { toast } from '../../ui/confirm'
import { warpImageToQuad, boundingBox } from '../../lib/roofTextureWarp'

const DEFAULT_CENTER = [31.7917, -7.0926] // Maroc — repli si le lead n'a pas de GPS.
const DELTA = 0.00012 // ≈13 m — écart initial des 4 poignées autour du centre.

function numeroteIcon(n) {
  return L.divIcon({
    html: `<div class="grid size-7 place-items-center rounded-full border-2 border-white bg-primary text-xs font-bold text-primary-foreground shadow">${n}</div>`,
    className: 'visite-calage-pin',
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })
}

export default function CalageToitPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [visite, setVisite] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [photoChoisieId, setPhotoChoisieId] = useState(null)
  const [enregistrement, setEnregistrement] = useState(false)
  const [assemblage, setAssemblage] = useState(false)

  const mapRef = useRef(null)
  const containerRef = useRef(null)
  const markersRef = useRef([])
  const canvasRef = useRef(null)
  const imageRef = useRef(null)
  const pollRef = useRef(null)

  const recharger = useCallback(() => {
    visitesApi.getVisite(id).then((res) => setVisite(res.data)).catch(() => setErreur('Visite introuvable.'))
  }, [id])

  useEffect(() => { recharger() }, [recharger])

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  // Polling pendant l'assemblage serveur (Celery) — VT9/VT11.
  useEffect(() => {
    if (visite?.photo_toit?.assemblage_etat !== 'en_cours') return undefined
    pollRef.current = setInterval(recharger, 4000)
    return () => clearInterval(pollRef.current)
  }, [visite?.photo_toit?.assemblage_etat, recharger])

  const photosToiture = (visite?.checklist ?? [])
    .find((c) => c.categorie === 'toiture')?.slots
    .flatMap((s) => s.photos) ?? []

  const assemblageEtat = visite?.photo_toit?.assemblage_etat ?? 'aucun'
  const sourceUrl = assemblageEtat === 'ok'
    ? visite.photo_toit.url
    : (photosToiture.find((p) => p.id === photoChoisieId)?.url
      ?? (photosToiture.length === 1 ? photosToiture[0].url : null))

  const lancerAssemblage = async () => {
    setAssemblage(true)
    try {
      const res = await visitesApi.assemblerPhotosVisite(id)
      setVisite(res.data)
    } catch {
      toast.error('Lancement de l’assemblage impossible.')
    } finally {
      setAssemblage(false)
    }
  }

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
    ctx.globalAlpha = 0.85
    warpImageToQuad(ctx, image, decale)
  }, [])

  // Boot carte (une fois le lead/visite connu) + 4 poignées déplaçables.
  useEffect(() => {
    if (!visite || mapRef.current || !containerRef.current) return undefined
    const centre = (visite.client_panel?.gps_lat != null && visite.client_panel?.gps_lng != null)
      ? [visite.client_panel.gps_lat, visite.client_panel.gps_lng]
      : DEFAULT_CENTER
    const map = L.map(containerRef.current, { center: centre, zoom: 20 })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap',
      maxZoom: 21,
    }).addTo(map)

    const coinsExistants = visite.photo_toit?.texture_calage?.coins
    const positions = Array.isArray(coinsExistants) && coinsExistants.length === 4
      ? coinsExistants
      : [
        [centre[0] + DELTA, centre[1] - DELTA],
        [centre[0] + DELTA, centre[1] + DELTA],
        [centre[0] - DELTA, centre[1] + DELTA],
        [centre[0] - DELTA, centre[1] - DELTA],
      ]

    markersRef.current = positions.map((pos, i) => {
      const marker = L.marker(pos, { draggable: true, icon: numeroteIcon(i + 1) }).addTo(map)
      marker.on('drag', redessiner)
      return marker
    })
    map.on('move zoom', redessiner)
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visite])

  useEffect(() => { redessiner() }, [sourceUrl, redessiner])

  const enregistrer = async () => {
    if (markersRef.current.length !== 4) return
    setEnregistrement(true)
    const coins = markersRef.current.map((m) => {
      const ll = m.getLatLng()
      return [ll.lat, ll.lng]
    })
    try {
      const res = await visitesApi.patchVisiteCalage(id, coins)
      setVisite(res.data)
      toast.success('Calage enregistré.')
    } catch {
      toast.error('Enregistrement du calage impossible.')
    } finally {
      setEnregistrement(false)
    }
  }

  if (erreur) return <div className="page"><p role="alert" className="text-sm text-destructive">{erreur}</p></div>
  if (!visite) return <div className="page"><Spinner /></div>

  return (
    <div className="page max-w-[900px]">
      <PageHeader
        title="Calage du toit"
        subtitle={visite.client_panel?.lead_nom}
        actions={<Button type="button" variant="ghost" onClick={() => navigate(`/visites/${id}`)}>Retour</Button>}
      />

      {assemblageEtat === 'en_cours' && (
        <Card className="mb-3 p-3 text-sm" role="status">Assemblage des photos en cours…</Card>
      )}
      {assemblageEtat === 'echec' && (
        <Card className="mb-3 p-3 text-sm" role="alert">
          <p className="font-medium">Assemblage échoué</p>
          <p className="text-muted-foreground">{visite.photo_toit.assemblage_erreur}</p>
        </Card>
      )}
      {assemblageEtat !== 'ok' && assemblageEtat !== 'en_cours' && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" onClick={lancerAssemblage} disabled={assemblage}>
            Assembler les photos
          </Button>
          {photosToiture.length > 1 && (
            <Select value={photoChoisieId ? String(photoChoisieId) : undefined} onValueChange={(v) => setPhotoChoisieId(Number(v))}>
              <SelectTrigger className="w-56"><SelectValue placeholder="Ou choisir une photo…" /></SelectTrigger>
              <SelectContent>
                {photosToiture.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.filename}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
        </div>
      )}

      <div className="relative">
        <div ref={containerRef} className="h-[60vh] min-h-[360px] w-full rounded-lg border border-border" />
        {sourceUrl && (
          <canvas
            ref={(node) => { canvasRef.current = node; redessiner() }}
            className="pointer-events-none absolute"
            data-testid="visite-calage-canvas"
          />
        )}
      </div>
      {sourceUrl && (
        <img
          ref={imageRef}
          src={sourceUrl}
          alt=""
          hidden
          onLoad={redessiner}
          crossOrigin="anonymous"
        />
      )}

      <p className="mt-2 text-xs text-muted-foreground">
        Déplacez les 4 poignées numérotées pour aligner l’aperçu drapé sur le contour réel du toit.
      </p>

      <Button type="button" className="mt-3" onClick={enregistrer} disabled={enregistrement}>
        Enregistrer le calage
      </Button>
    </div>
  )
}
