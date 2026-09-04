import { useEffect, useState } from 'react'
import { Truck } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Spinner,
} from '../../../ui'
import { formatDate, formatDateTime } from '../../../lib/format'

/* ============================================================================
   WIR216 — « Mes livraisons » (portail client authentifié).
   ----------------------------------------------------------------------------
   Le lien de l'email `livraison_en_transit`/`livraison_livree` (FG228/XSTK22,
   apps.installations.livraison_client_notify) pointait vers une section
   INEXISTANTE — 404 systématique. Lecture SEULE, scopée serveur au client
   connecté (jamais un id de client envoyé par le front) via
   `apps.installations.selectors.livraisons_client_portail` : jamais
   `cout_transport` ni un prix d'achat, seulement référence/date prévue/statut/
   numéro de suivi/articles (désignation+quantité) + preuve de livraison (POD)
   une fois livrée.
   ========================================================================== */

const TON_STATUT = {
  planifiee: 'neutral',
  en_transit: 'info',
  livree: 'success',
  annulee: 'neutral',
}

/* ----------------------------------------------------------------------------
   AUD147 — la preuve de livraison s'AFFICHE dans le portail.
   ----------------------------------------------------------------------------
   L'écran rendait `pod_url` en `<a href … target="_blank">` : le lien pointait
   l'endpoint INTERNE `/installations/preuves-livraison/<id>/` (`IsAnyRole`,
   qui exclut explicitement `portee != 'interne'`) — 403 garanti pour tout
   compte portail, sur SON PROPRE document. AUD301 a repointé `pod_url` vers la
   route portail scopée au client connecté, mais celle-ci renvoie un DOCUMENT
   JSON, pas un fichier : ouvert dans un onglet, le client voyait du JSON brut.
   La preuve est donc LUE par l'API et RENDUE ici (signataire, tracé de
   signature, horodatage, note, position, photo relayée par la route portail).
   -------------------------------------------------------------------------- */
function PreuveLivraison({ preuve }) {
  const position = preuve.gps_lat && preuve.gps_lng
    ? `${preuve.gps_lat}, ${preuve.gps_lng}`
    : null
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/30 p-3">
      <p className="text-sm font-medium">Preuve de livraison</p>
      <dl className="flex flex-col gap-1 text-sm text-muted-foreground">
        {preuve.signataire_nom && (
          <div className="flex gap-1">
            <dt>Signée par</dt>
            <dd className="text-foreground">{preuve.signataire_nom}</dd>
          </div>
        )}
        {preuve.horodatage && (
          <div className="flex gap-1">
            <dt>Le</dt>
            <dd className="text-foreground">
              {formatDateTime(preuve.horodatage)}
            </dd>
          </div>
        )}
        {position && (
          <div className="flex gap-1">
            <dt>Position</dt>
            <dd className="text-foreground">{position}</dd>
          </div>
        )}
        {preuve.note && (
          <div className="flex gap-1">
            <dt>Note</dt>
            <dd className="text-foreground">{preuve.note}</dd>
          </div>
        )}
      </dl>
      {preuve.signature_image && (
        <img
          src={preuve.signature_image}
          alt="Signature du client"
          className="max-h-24 w-auto self-start rounded border border-border bg-white"
        />
      )}
      {preuve.photo_url && (
        <img
          src={preuve.photo_url}
          alt="Photo de la livraison"
          loading="lazy"
          className="max-h-64 w-auto self-start rounded border border-border"
        />
      )}
    </div>
  )
}

export default function PortailClientLivraisons() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  // AUD147 — état par livraison : { etat: 'chargement'|'ok'|'erreur', data }.
  const [preuves, setPreuves] = useState({})

  const charger = () => {
    setLoading(true)
    portailApi.livraisons.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  const voirPreuve = (id) => {
    setPreuves((etat) => ({ ...etat, [id]: { etat: 'chargement' } }))
    portailApi.livraisons.preuve(id)
      .then((r) => setPreuves((etat) => (
        { ...etat, [id]: { etat: 'ok', data: r.data } })))
      .catch(() => setPreuves((etat) => (
        { ...etat, [id]: { etat: 'erreur' } })))
  }

  useEffect(() => {
    // Différé d'un microtask : `charger` pose l'état de chargement de façon
    // synchrone, ce qui déclenche un rendu en cascade
    // (react-hooks/set-state-in-effect). Même patron que PortailClientDevis/
    // PortailClientFactures.
    Promise.resolve().then(charger)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos livraisons…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Livraisons indisponibles"
        description="Vos livraisons n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <Truck className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes livraisons
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucune livraison"
          description="Vous n’avez aucune livraison pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((l) => (
            <Card key={l.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{l.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    {l.date_prevue
                      ? `Prévue le ${formatDate(l.date_prevue)}`
                      : 'Date prévue non communiquée'}
                    {l.numero_suivi ? ` — suivi ${l.numero_suivi}` : ''}
                  </p>
                </div>
                <Badge tone={TON_STATUT[l.statut] || 'neutral'}>
                  {l.statut_display}
                </Badge>
              </div>

              {l.articles?.length > 0 && (
                <ul className="flex flex-col gap-1 text-sm">
                  {l.articles.map((a, i) => (
                    <li key={i} className="text-muted-foreground">
                      {a.designation || 'Article'} × {a.quantite}
                    </li>
                  ))}
                </ul>
              )}

              {l.pod_disponible && (
                <div className="flex flex-col gap-2">
                  {!preuves[l.id] && (
                    <div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => voirPreuve(l.id)}
                      >
                        Voir la preuve de livraison
                      </Button>
                    </div>
                  )}
                  {preuves[l.id]?.etat === 'chargement' && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Spinner /> Chargement de la preuve…
                    </div>
                  )}
                  {preuves[l.id]?.etat === 'erreur' && (
                    <p className="text-sm text-muted-foreground">
                      La preuve de livraison n’a pas pu être affichée.
                    </p>
                  )}
                  {preuves[l.id]?.etat === 'ok' && (
                    <PreuveLivraison preuve={preuves[l.id].data} />
                  )}
                </div>
              )}
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
