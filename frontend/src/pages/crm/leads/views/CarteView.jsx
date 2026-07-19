/**
 * FG37 — Lead pipeline map view (CarteView).
 *
 * 5ème vue du pipeline CRM. Affiche les leads filtrés qui ont des coordonnées
 * GPS (gps_lat/gps_lng) sur une carte Leaflet/OpenStreetMap :
 *   - Épingle colorée par étape (couleurs STAGE_COLORS).
 *   - Clic → ouvre la fiche complète du lead via onOpenLead.
 *   - Les leads sans GPS sont listés dans un bandeau sous la carte (0 GPS).
 *
 * Réutilise le composant MapView (N85 / src/components/MapView.jsx) qui pilote
 * Leaflet de façon impérative, sans react-leaflet.
 */
import { useMemo } from 'react'
import { Map } from 'lucide-react'
import MapView, { escapeHtml } from '../../../../components/MapView'
import { STAGE_COLORS, STAGE_LABELS } from '../../../../features/crm/stages'
import { EmptyState } from '../../../../ui'

// LB29 — Couleur de l'épingle selon l'étape (repli neutre tokenisé — recon-05
// hex hunt : STAGE_COLORS renvoie déjà des `var(--stage-*)`, seul CE repli
// pour une étape inconnue/absente restait un hex brut).
function pinColor(stage) {
  return STAGE_COLORS[stage] ?? 'var(--muted-foreground)'
}

// LB29 — HTML du popup Leaflet (tous les champs sont échappés) : re-basé sur
// un token (`var(--muted-foreground)`) au lieu du hex `#6b7280` — le popup
// est injecté en HTML brut dans le DOM du document (Leaflet, pas de shadow
// DOM), donc une variable CSS custom property y cascade normalement.
function buildPopupHtml(lead) {
  const stage = escapeHtml(STAGE_LABELS[lead.stage] ?? lead.stage ?? '—')
  const tel = lead.telephone ? `<br><span style="color:var(--muted-foreground)">${escapeHtml(lead.telephone)}</span>` : ''
  return `<br><em style="font-size:0.85em;color:var(--muted-foreground)">${stage}</em>${tel}`
}

export default function CarteView({ leads = [], onOpenLead }) {
  // Séparer les leads avec et sans GPS.
  const { withGps, withoutGps } = useMemo(() => {
    const withGps = []
    const withoutGps = []
    for (const lead of leads) {
      const lat = parseFloat(lead.gps_lat)
      const lng = parseFloat(lead.gps_lng)
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        withGps.push({ lead, lat, lng })
      } else {
        withoutGps.push(lead)
      }
    }
    return { withGps, withoutGps }
  }, [leads])

  // Construire les marqueurs pour MapView.
  const markers = useMemo(
    () =>
      withGps.map(({ lead, lat, lng }) => ({
        id: lead.id,
        lat,
        lng,
        label: [lead.nom, lead.prenom].filter(Boolean).join(' ') || `Lead #${lead.id}`,
        color: pinColor(lead.stage),
        popupHtml: buildPopupHtml(lead),
        _lead: lead,
      })),
    [withGps],
  )

  const handleMarkerClick = (marker) => {
    if (onOpenLead) onOpenLead(marker._lead)
  }

  // VX147 — « 0 lead » unifié sur `EmptyState` (calqué sur ChartsView) au lieu
  // de la légende + bandeau « sans GPS » qui n'a pas de sens quand il n'y a
  // aucun lead du tout (distinct du cas « des leads existent mais sans GPS »
  // ci-dessous, conservé tel quel).
  if (!leads || leads.length === 0) {
    return (
      <EmptyState
        icon={Map}
        title="Aucun lead"
        description="Aucun lead ne correspond à ces filtres."
      />
    )
  }

  return (
    <div className="carte-view">
      {/* Légende des étapes */}
      <div className="carte-legend" role="list" aria-label="Légende des étapes">
        {Object.entries(STAGE_COLORS).map(([key, color]) => (
          <span key={key} className="carte-legend-item" role="listitem">
            <span
              className="carte-legend-dot"
              style={{ background: color }}
              aria-hidden="true"
            />
            <span className="carte-legend-label">
              {STAGE_LABELS[key] ?? key}
            </span>
          </span>
        ))}
        <span className="carte-legend-item carte-legend-total" role="listitem">
          <strong>{withGps.length}</strong> / {leads.length} avec GPS
        </span>
      </div>

      {/* Carte Leaflet */}
      {withGps.length > 0 ? (
        <MapView
          markers={markers}
          onMarkerClick={handleMarkerClick}
          height="65vh"
          fitToMarkers
        />
      ) : (
        <div className="carte-no-gps" role="status" aria-live="polite">
          <p>
            Aucun lead dans cette sélection n'a de coordonnées GPS.
            Renseignez <em>gps_lat</em> / <em>gps_lng</em> dans la fiche lead pour le voir ici.
          </p>
        </div>
      )}

      {/* Bandeau des leads sans GPS */}
      {withoutGps.length > 0 && (
        <details className="carte-no-gps-list">
          <summary>
            {withoutGps.length} lead{withoutGps.length > 1 ? 's' : ''} sans GPS (non affiché{withoutGps.length > 1 ? 's' : ''})
          </summary>
          {/* LB29 — recon-01 : `hoveredId` était posé ici (survol d'un lead
              SANS GPS) mais ne pilotait plus rien qu'un `aria-current` sur
              CE MÊME bouton (donc jamais visible ni utile — un lead sans GPS
              n'a, par définition, aucune épingle à mettre en avant sur la
              carte). Décision locale : supprimé plutôt que « réparé » — un
              vrai câblage exigerait d'étendre `MapView` (composant partagé
              hors du périmètre de cette lane, CartePage/ParcInstallePage en
              dépendent aussi) pour une fonctionnalité qui, même câblée,
              resterait sans effet visible sur cette liste précise. */}
          <ul>
            {withoutGps.map((lead) => (
              <li key={lead.id}>
                <button
                  type="button"
                  className="carte-no-gps-btn"
                  onClick={() => onOpenLead?.(lead)}
                >
                  {[lead.nom, lead.prenom].filter(Boolean).join(' ') || `Lead #${lead.id}`}
                  {lead.stage && (
                    <span
                      className="carte-no-gps-stage"
                      style={{ background: pinColor(lead.stage) }}
                    />
                  )}
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
