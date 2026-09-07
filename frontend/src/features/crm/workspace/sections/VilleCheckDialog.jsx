import { useEffect, useState } from 'react'
import {
  Button, Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
  Spinner,
} from '../../../../ui'
import crmApi from '../../../../api/crmApi'
import MapView from '../../../../components/MapView'

/* ============================================================================
   VREF (fondateur 07/09/2026) — « Vérifier la ville » : quand la ville tapée
   n'est pas au gazetier (ou résout vers 2+ villes), Meryem voit sur la CARTE
   où le dossier se trouve réellement (repère GPS du lead s'il existe, sinon
   géocodage du nom) et les villes ERP les plus proches, puis tranche :
     - « C'est la même ville »  → le nom est REMPLACÉ par le canonique ;
     - « C'est une ville voisine » → le nom du client est CONSERVÉ et la
       ville ERP choisie devient la ville de RATTACHEMENT (affichée
       « X, près de Y » ; PVGIS et transport lisent Y).
   Résolveur serveur PUR : ce dialogue ne fait que remplir le brouillon —
   l'enregistrement normal persiste et journalise.
   ========================================================================== */

const MODE_MEME = 'meme'
const MODE_VOISINE = 'voisine'

export default function VilleCheckDialog({
  open, onOpenChange, ville, gpsLat, gpsLng, onChoisir,
}) {
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(false)
  const [data, setData] = useState(null)
  const [choix, setChoix] = useState('')
  const [mode, setMode] = useState(MODE_VOISINE)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setErreur(false)
    setData(null)
    setChoix('')
    crmApi.villeStatut({ ville, proches: true, gps_lat: gpsLat || undefined, gps_lng: gpsLng || undefined })
      .then((r) => {
        setData(r.data)
        // Pré-sélection : la ville ERP la plus proche — Meryem confirme
        // d'un clic dans le cas courant.
        const premiere = r.data?.proches?.[0]
        if (premiere) setChoix(premiere.ville)
      })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }, [open, ville, gpsLat, gpsLng])

  const proches = data?.proches ?? []
  const position = data?.position ?? null
  const markers = [
    ...(position ? [{
      id: 'client', lat: position.lat, lng: position.lng,
      label: `« ${ville} » (position estimée)`, color: '#dc2626',
    }] : []),
    ...proches.map((p) => ({
      id: p.ville, lat: p.lat, lng: p.lng,
      label: `${p.ville} · ${p.distance_km} km`,
      color: p.ville === choix ? '#16a34a' : '#2563eb',
    })),
  ]

  const confirmer = () => {
    if (!choix) return
    onChoisir({ mode, ville: choix })
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Vérifier la ville — « {ville} »</DialogTitle>
        </DialogHeader>
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">
            Vérification indisponible pour le moment.
          </p>
        ) : !data ? null : (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              {data.statut === 'ambigue'
                ? `Ce nom correspond à plusieurs villes (${(data.candidats || []).join(', ')}) — choisissez sur la carte.`
                : data.statut === 'inconnue'
                  ? 'Cette ville n’est pas dans notre liste — choisissez la ville ERP la plus proche sur la carte.'
                  : `Reconnue comme « ${data.ville_canonique} ».`}
              {!position && ' (Position introuvable — liste sans carte.)'}
            </p>
            {position && (
              <MapView
                markers={markers}
                center={[position.lat, position.lng]}
                zoom={9}
                height="300px"
                fitToMarkers
                onMarkerClick={(m) => { if (m.id !== 'client') setChoix(m.id) }}
              />
            )}
            {proches.length > 0 && (
              <div className="flex flex-col gap-1" role="radiogroup" aria-label="Villes ERP proches">
                {proches.map((p) => (
                  <label key={p.ville} className="flex items-center gap-2 text-sm">
                    <input
                      type="radio" name="ville-proche" value={p.ville}
                      checked={choix === p.ville}
                      onChange={() => setChoix(p.ville)}
                    />
                    <span>{p.ville}</span>
                    <span className="text-muted-foreground">{p.distance_km} km</span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex flex-col gap-1" role="radiogroup" aria-label="Type de correspondance">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio" name="ville-mode" value={MODE_MEME}
                  checked={mode === MODE_MEME} onChange={() => setMode(MODE_MEME)}
                />
                <span>
                  C’est la <b>même ville</b> — remplacer « {ville} » par la ville choisie
                </span>
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio" name="ville-mode" value={MODE_VOISINE}
                  checked={mode === MODE_VOISINE} onChange={() => setMode(MODE_VOISINE)}
                />
                <span>
                  C’est une <b>ville voisine</b> — garder « {ville} » et rattacher
                  les calculs (PVGIS, transport) à la ville choisie
                </span>
              </label>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annuler</Button>
          <Button disabled={!choix || loading} onClick={confirmer}>Confirmer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
