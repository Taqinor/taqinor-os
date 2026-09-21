/* AOF82 — Porte n°3 : reprise du contour depuis le lecteur de cartes EXISTANT.
   ----------------------------------------------------------------------------
   AUCUNE troisième pile cartographique n'est introduite. L'ERP n'a que Leaflet
   (afficheur de marqueurs, incapable de tracer un polygone) ; le seul outil de
   tracé cartographique du dépôt est `apps/web/src/scripts/roofPro11/captureBoot.ts`
   (MapLibre + géocodage MapTiler + gardes anti-auto-intersection + débounce et
   AbortController). On le MONTE tel quel, via l'alias `@roofpro` déjà déclaré
   dans `frontend/vite.config.js` (avec `server.fs.allow` déjà élargi au parent et
   le plugin `roofbuilder-ts-transpile` qui transpile les .ts du builder). Aucun
   fichier d'`apps/web` n'est lu autrement qu'en import — jamais modifié.

   TROIS GARDES, parce qu'un montage cross-projet peut casser :
     1. l'import est DYNAMIQUE et sous try/catch — un échec de résolution ou de
        transpilation ne fait pas écrouler l'atelier ;
     2. la clé MapTiler vient de l'endpoint de config EXISTANT (`/ventes/roof-config/`,
        même endpoint que `pages/ventes/ToitureDesign.jsx`, le précédent d'intégration
        propre) ; absente → message clair, pas de carte muette ;
     3. dans les deux cas, l'écran DÉGRADE vers le tracé manuel (`onTracerAlaMain`).

   Le contour rendu par `bootCaptureOnly` est en [lat, lng] (l'ordre de
   `roof_outline` du lead CRM), alors que l'outil manipule des `LngLat` en
   interne : on ne devine RIEN ici, on transmet le contour à l'appelant en le
   nommant explicitement `contour_latlng` — la conversion en mètres locaux est
   l'affaire de `repere.js` (AOF83), qui déclare l'ordre des axes. */
import { useCallback, useEffect, useRef, useState } from 'react'
import '../../../styles/roofbuilder.css'

const MSG_SANS_CLE =
  'Carte indisponible : la clé MapTiler n’est pas configurée sur le serveur. ' +
  'Vous pouvez tracer la toiture à la main, ou importer un plan.'

const MSG_MONTAGE =
  'Le lecteur de cartes n’a pas pu démarrer sur ce poste. ' +
  'Vous pouvez tracer la toiture à la main, ou importer un plan — rien n’est perdu.'

// Chargeur par défaut de la config carte : le MÊME endpoint que la page
// ToitureDesign (même origine, session cookie). Injectable pour les tests et
// pour un atelier qui préférerait passer la clé lui-même.
async function chargerConfigParDefaut() {
  const { default: api } = await import('../../../api/axios')
  const reponse = await api.get('/ventes/roof-config/')
  return reponse?.data ?? null
}

export default function RepriseCarte({
  chargerConfigCarte = chargerConfigParDefaut,
  onContour,
  onTracerAlaMain,
  reducedMotion = false,
}) {
  const [etat, setEtat] = useState('demarrage') // demarrage | carte | degrade
  const [message, setMessage] = useState('')
  const [contour, setContour] = useState(null)
  const [adresse, setAdresse] = useState('')
  const captureRef = useRef(null)

  // `onContour` est appelé depuis le callback du builder : on garde la dernière
  // référence dans un ref pour ne pas re-booter la carte à chaque rendu du parent.
  const onContourRef = useRef(onContour)
  useEffect(() => {
    onContourRef.current = onContour
  }, [onContour])

  useEffect(() => {
    let annule = false

    const demarrer = async () => {
      // 1) la clé — sans elle, aucune carte possible.
      let cle = ''
      let mapbox
      try {
        const cfg = await chargerConfigCarte()
        if (cfg?.available && cfg?.maptilerKey) {
          cle = cfg.maptilerKey
          mapbox = cfg.mapboxToken || undefined
        }
      } catch {
        /* message ci-dessous — jamais d'exception remontée à l'atelier */
      }
      if (annule) return
      if (!cle) {
        setEtat('degrade')
        setMessage(MSG_SANS_CLE)
        return
      }

      // 2) le montage du lecteur de cartes existant.
      try {
        const mod = await import('@roofpro/captureBoot')
        if (annule) return
        mod.bootCaptureOnly({
          maptilerKey: cle,
          mapboxToken: mapbox,
          reducedMotion: Boolean(reducedMotion),
          captureOnly: true,
          onCaptureChange: ({ pin, outline, address }) => {
            // `outline` est en [lat, lng] — on le nomme comme tel, sans conversion.
            const contourLatLng = Array.isArray(outline) && outline.length >= 3 ? outline : null
            setContour(contourLatLng)
            if (address) setAdresse(address)
            captureRef.current = { pin, contour_latlng: contourLatLng, adresse: address || null }
          },
        })
        if (annule) return
        setEtat('carte')
      } catch {
        if (annule) return
        setEtat('degrade')
        setMessage(MSG_MONTAGE)
      }
    }

    demarrer()
    return () => {
      annule = true
    }
  }, [chargerConfigCarte, reducedMotion])

  const reprendre = useCallback(() => {
    const capture = captureRef.current
    if (!capture?.contour_latlng) return
    onContourRef.current?.({
      // Ordre des axes DÉCLARÉ dans le nom du champ : aucune ambiguïté possible
      // pour le convertisseur ENU (AOF83).
      contour_latlng: capture.contour_latlng,
      repere_latlng: capture.pin ? [capture.pin.lat, capture.pin.lng] : null,
      adresse: capture.adresse,
      provenance: 'carte',
    })
  }, [])

  if (etat === 'degrade') {
    return (
      <section className="ao-carte ao-carte-degrade" role="alert" data-ao-reprise-carte="degrade">
        <p>{message}</p>
        <button type="button" onClick={() => onTracerAlaMain?.()} data-ao-carte-repli>
          Tracer la toiture à la main
        </button>
      </section>
    )
  }

  return (
    <section className="ao-carte" data-ao-reprise-carte={etat}>
      <p className="ao-carte-aide">
        Cherchez l&apos;adresse, posez le repère puis tracez le contour du bâtiment. Le contour
        repris peut ensuite être recalé à la main dans l&apos;atelier.
      </p>

      {/* Échafaudage minimal attendu par `bootCaptureOnly` : il ne cherche que
          ces cinq identifiants (`rp9-map`, `rp9-status`, `rp9-finish`,
          `rp9-clear`, `rp9-undo-point`, `rp9-area-value`). */}
      <div className="rp9-host ao-carte-host">
        <div id="rp9-map" className="ao-carte-map" />
        <p id="rp9-status" className="ao-carte-statut" role="status" />
        <div className="ao-carte-actions">
          <button type="button" id="rp9-finish" className="rp9-chip" disabled>
            Terminer le tracé
          </button>
          <button type="button" id="rp9-undo-point" className="rp9-chip" hidden>
            Annuler le dernier point
          </button>
          <button type="button" id="rp9-clear" className="rp9-chip">
            Effacer
          </button>
          <p className="ao-carte-surface">
            Surface&nbsp;: <span id="rp9-area-value">—</span>
          </p>
        </div>
      </div>

      {adresse && <p className="ao-carte-adresse">Adresse repérée&nbsp;: {adresse}</p>}

      <button
        type="button"
        onClick={reprendre}
        disabled={!contour}
        data-ao-carte-reprendre
      >
        Reprendre ce contour
      </button>
      {!contour && (
        <p className="ao-hint">
          Le bouton s&apos;active dès qu&apos;un contour fermé d&apos;au moins trois points existe.
        </p>
      )}
    </section>
  )
}
