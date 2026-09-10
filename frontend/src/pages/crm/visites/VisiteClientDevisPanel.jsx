// VT7 — Panneau client+devis de l'écran visite. Lecture seule, RIEN d'autre
// que les champs `client_panel`/`devis` de l'agrégat (contrat PACT10) :
// identité/téléphone/WhatsApp/adresse/GPS + devis (numéro/statut/total TTC/
// lignes) SANS `prix_achat` — le serveur ne l'expose déjà pas ici, ce panneau
// n'en ajoute jamais un.
import { Card, Badge } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import { whatsappUrl, mapsUrl } from './visiteHelpers'

const STATUT_DEVIS_LABEL = {
  brouillon: 'Brouillon', envoye: 'Envoyé', accepte: 'Accepté',
  refuse: 'Refusé', expire: 'Expiré',
}

export default function VisiteClientDevisPanel({ clientPanel, devis }) {
  if (!clientPanel) return null
  const wa = whatsappUrl(clientPanel.whatsapp)
  const maps = mapsUrl(clientPanel.gps_lat, clientPanel.gps_lng)

  return (
    <Card className="mb-3 p-3 text-sm" data-testid="visite-client-devis-panel">
      <p className="font-medium">{clientPanel.lead_nom}</p>
      <p className="text-muted-foreground">
        {[clientPanel.adresse, clientPanel.ville].filter(Boolean).join(', ')}
      </p>
      <div className="mt-2 flex flex-wrap gap-3">
        {clientPanel.telephone && (
          <a href={`tel:${clientPanel.telephone}`} className="text-primary underline">
            {clientPanel.telephone}
          </a>
        )}
        {wa && (
          <a href={wa} target="_blank" rel="noreferrer" className="text-primary underline">
            WhatsApp
          </a>
        )}
        {maps && (
          <a href={maps} target="_blank" rel="noreferrer" className="text-primary underline">
            Itinéraire
          </a>
        )}
      </div>

      {Array.isArray(devis) && devis.length > 0 && (
        <div className="mt-3 space-y-2 border-t border-border pt-2">
          {devis.map((d) => (
            <div key={d.id}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{d.numero}</span>
                <Badge tone="neutral">{STATUT_DEVIS_LABEL[d.statut] ?? d.statut}</Badge>
                <span className="ml-auto tabular-nums">{formatMAD(d.total_ttc)}</span>
              </div>
              {Array.isArray(d.lignes) && d.lignes.length > 0 && (
                <ul className="mt-1 space-y-0.5 pl-3 text-xs text-muted-foreground">
                  {d.lignes.map((l, i) => (
                    <li key={`${d.id}-${i}`}>
                      {l.quantite} × {l.designation} — {formatMAD(l.prix_unitaire_ttc)} ({formatMAD(l.total_ttc)})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
