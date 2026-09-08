import { useEffect, useRef, useState } from 'react'
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

   VREF-CARTE (fondateur 08/09/2026, lead « sidi hashass » sans GPS) : quand
   NI le GPS du lead, NI le gazetier, NI Nominatim ne placent le dossier, le
   serveur rend position=null ET proches=[] (la liste se calcule DEPUIS la
   position) — l'ancien repli « liste sans carte » était donc VIDE : ni
   carte, ni liste, Confirmer grisé. Désormais la carte s'affiche TOUJOURS
   (Maroc entier par défaut) et un clic de Meryem à l'endroit approximatif
   du client relance la recherche des villes ERP proches depuis ce point
   (le chemin GPS existant de l'endpoint). Le point cliqué est une
   estimation d'écran : il n'est JAMAIS écrit dans les champs GPS du lead.
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
  // Ville vide (douar tapé en adresse) : la ville choisie DEVIENT la
  // ville du lead — défaut « même ville » ; sinon défaut « voisine ».
  const [mode, setMode] = useState(ville ? MODE_VOISINE : MODE_MEME)
  // VREF-CARTE — point cliqué sur la carte (null = aucun), requête en cours
  // depuis ce point (la carte reste montée pendant ce temps) et son échec.
  const [pointe, setPointe] = useState(null)
  const [recherche, setRecherche] = useState(false)
  const [rechercheErreur, setRechercheErreur] = useState(false)
  // Numéro de la dernière requête émise : une réponse plus ancienne (deux
  // clics rapprochés, réouverture) est ignorée — jamais une liste périmée.
  const seqRef = useRef(0)

  // Remise à zéro à l'OUVERTURE par le motif « ajuster l'état au rendu »
  // (React officiel, même patron que VX237) — jamais un setState synchrone
  // dans le corps d'un effet (react-hooks v7).
  const [prevOpen, setPrevOpen] = useState(false)
  if (open !== prevOpen) {
    setPrevOpen(open)
    if (open) {
      setLoading(true)
      setErreur(false)
      setData(null)
      setChoix('')
      setMode(ville ? MODE_VOISINE : MODE_MEME)
      setPointe(null)
      setRecherche(false)
      setRechercheErreur(false)
    }
  }

  useEffect(() => {
    if (!open) return
    const seq = ++seqRef.current
    crmApi.villeStatut({ ville, proches: true, gps_lat: gpsLat || undefined, gps_lng: gpsLng || undefined })
      .then((r) => {
        if (seq !== seqRef.current) return
        setData(r.data)
        // Pré-sélection : la ville ERP la plus proche — Meryem confirme
        // d'un clic dans le cas courant.
        const premiere = r.data?.proches?.[0]
        if (premiere) setChoix(premiere.ville)
      })
      .catch(() => { if (seq === seqRef.current) setErreur(true) })
      .finally(() => { if (seq === seqRef.current) setLoading(false) })
  }, [open, ville, gpsLat, gpsLng])

  // VREF-CARTE — clic sur le fond de carte : relance la recherche des villes
  // ERP proches DEPUIS le point cliqué (chemin GPS de l'endpoint, aucune
  // écriture). Gestionnaire d'évènement, pas un effet : la carte reste
  // montée et aucun rendu en cascade.
  const chercherDepuis = ({ lat, lng }) => {
    const seq = ++seqRef.current
    setPointe({ lat, lng })
    setRecherche(true)
    setRechercheErreur(false)
    crmApi.villeStatut({ ville, proches: true, gps_lat: lat, gps_lng: lng })
      .then((r) => {
        if (seq !== seqRef.current) return
        setData(r.data)
        setChoix(r.data?.proches?.[0]?.ville ?? '')
      })
      .catch(() => { if (seq === seqRef.current) setRechercheErreur(true) })
      .finally(() => { if (seq === seqRef.current) setRecherche(false) })
  }

  const proches = data?.proches ?? []
  const position = data?.position ?? null
  const markers = [
    ...(position ? [{
      id: 'client', lat: position.lat, lng: position.lng,
      label: pointe
        ? 'Point cliqué (approximatif)'
        : (ville ? `« ${ville} » (position estimée)` : 'Repère du lead'),
      color: '#dc2626',
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
          <DialogTitle>{ville ? `Vérifier la ville — « ${ville} »` : 'Choisir la ville du lead'}</DialogTitle>
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
              {!position && !pointe && ' Position introuvable — cliquez sur la carte à l’endroit approximatif du client : les villes ERP les plus proches apparaîtront.'}
            </p>
            {data.gps_hors_zone && (pointe ? (
              <p className="text-xs text-warning" role="alert">
                Le point cliqué est hors du Maroc — cliquez à l’intérieur du pays.
              </p>
            ) : (
              <p className="text-xs text-warning" role="alert">
                Le repère GPS enregistré sur ce lead est hors du Maroc — il a
                été ignoré. Vérifiez les champs GPS lat./long. (ou utilisez
                « Lien → GPS » avec le lien Google Maps du client).
              </p>
            ))}
            {rechercheErreur && (
              <p className="text-xs text-warning" role="alert">
                Recherche indisponible — cliquez à nouveau sur la carte.
              </p>
            )}
            <MapView
              markers={markers}
              center={position ? [position.lat, position.lng] : undefined}
              zoom={position ? 9 : undefined}
              height="300px"
              fitToMarkers
              onMarkerClick={(m) => { if (m.id !== 'client') setChoix(m.id) }}
              onMapClick={chercherDepuis}
            />
            {recherche && (
              <p className="text-xs text-muted-foreground" role="status">
                Recherche des villes proches…
              </p>
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
                  C’est la <b>même ville</b> — {ville ? `remplacer « ${ville} » par la ville choisie` : 'la ville choisie devient la ville du lead'}
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
          <Button disabled={!choix || loading || recherche} onClick={confirmer}>Confirmer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
