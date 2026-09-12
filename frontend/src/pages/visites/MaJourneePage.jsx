// VTA9 — « MA JOURNÉE » : l'ACCUEIL de l'app Visites (`/visites`).
//
// Recherche field-service : l'écran d'un commercial terrain est SA JOURNÉE —
// jamais un tableau de bord. Une liste, au pouce, dans l'ordre où il va rouler.
//
// Tout vient du serveur (contrat `apps/visites/contract_samples/ma_journee.json`) :
// `complet`/`manquants_count` ne sont PAS recalculés ici, et les horodatages
// `en_route_le`/`arrivee_le` affichés sont ceux que le SERVEUR a écrits en
// répondant à `demarrer-route`/`arriver` — l'écran n'horodate rien localement.
//
// La portée est imposée par le serveur (VTA6) : sans `visites_valider`, il ne
// sert que `commercial=self`. Cet écran ne demande donc aucun filtre « mine ».
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Navigation, MapPin } from 'lucide-react'
import visitesApi from '../../api/visitesApi'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Card, Badge, Spinner, EmptyState } from '../../ui'
import { toast } from '../../ui/confirm'
import { STATUT_VISITE_LABEL, geoUrl, mapsUrl, heureServeur } from './visiteHelpers'

export default function MaJourneePage() {
  const navigate = useNavigate()
  const [journee, setJournee] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)
  // Id de la visite dont une action de progression est en vol (bouton occupé).
  const [enVol, setEnVol] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setErreur(null)
    visitesApi.getMaJournee()
      .then((res) => setJournee(res.data ?? null))
      .catch(() => setErreur('Chargement de votre journée impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  // Remplace la visite par l'agrégat renvoyé par l'action (leçon #96 : toutes
  // les actions mutantes renvoient l'agrégat complet) — on ne devine pas
  // l'heure côté client, on prend celle du serveur.
  const appliquer = (id, data) => {
    setJournee((j) => (j ? {
      ...j,
      visites: (j.visites ?? []).map((v) => (v.id === id ? {
        ...v,
        en_route_le: data?.en_route_le ?? v.en_route_le,
        arrivee_le: data?.arrivee_le ?? v.arrivee_le,
        statut: data?.statut ?? v.statut,
      } : v)),
    } : j))
  }

  const progresser = async (visite, etape) => {
    setEnVol(visite.id)
    try {
      const res = etape === 'route'
        ? await visitesApi.demarrerRouteVisite(visite.id)
        : await visitesApi.arriverVisite(visite.id)
      appliquer(visite.id, res.data)
    } catch {
      toast.error(etape === 'route'
        ? 'Impossible d’enregistrer le départ.'
        : 'Impossible d’enregistrer l’arrivée.')
    } finally {
      setEnVol(null)
    }
  }

  const visites = journee?.visites ?? []
  const enRetard = journee?.en_retard_count ?? 0

  return (
    <div className="page max-w-[720px]">
      <PageHeader
        title="Ma journée"
        subtitle={journee?.date ? `Visites du ${journee.date}` : 'Vos visites terrain'}
      />

      {loading ? (
        <Spinner />
      ) : erreur ? (
        <p role="alert" className="text-sm text-destructive">{erreur}</p>
      ) : (
        <>
          {enRetard > 0 && (
            <p role="status" className="mb-3 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning">
              {enRetard === 1
                ? '1 visite en retard est reprise dans la liste.'
                : `${enRetard} visites en retard sont reprises dans la liste.`}
            </p>
          )}

          {visites.length === 0 ? (
            // État vide HONNÊTE : rien n'est planifié aujourd'hui — on ne
            // remplit pas l'écran avec autre chose pour faire joli.
            <EmptyState
              title="Aucune visite aujourd’hui"
              description="Rien n’est planifié pour vous à cette date. Une visite planifiée par le bureau apparaîtra ici."
            />
          ) : (
            <ul className="space-y-3">
              {visites.map((v) => {
                const geo = geoUrl(v.gps_lat, v.gps_lng, v.lead_nom)
                const maps = mapsUrl(v.gps_lat, v.gps_lng)
                const heureRoute = heureServeur(v.en_route_le)
                const heureArrivee = heureServeur(v.arrivee_le)
                return (
                  <li key={v.id}>
                    <Card className="space-y-3 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{v.lead_nom}</p>
                          <p className="text-xs text-muted-foreground">
                            {v.date_prevue ? `${v.date_prevue} · ` : ''}
                            {STATUT_VISITE_LABEL[v.statut] ?? v.statut}
                          </p>
                          {(v.ville || v.adresse) && (
                            <p className="mt-1 flex items-start gap-1 text-xs text-muted-foreground">
                              <MapPin size={13} strokeWidth={1.75} aria-hidden="true" className="mt-0.5 shrink-0" />
                              <span className="min-w-0">
                                {[v.adresse, v.ville].filter(Boolean).join(', ')}
                              </span>
                            </p>
                          )}
                        </div>
                        <Badge tone={v.complet ? 'success' : 'neutral'} className="shrink-0">
                          {v.complet ? 'Complète' : `${v.manquants_count ?? 0} manquant(s)`}
                        </Badge>
                      </div>

                      {(heureRoute || heureArrivee) && (
                        <p className="text-xs text-muted-foreground">
                          {heureRoute ? `En route à ${heureRoute}` : ''}
                          {heureRoute && heureArrivee ? ' · ' : ''}
                          {heureArrivee ? `Arrivé à ${heureArrivee}` : ''}
                        </p>
                      )}

                      <div className="flex flex-wrap items-center gap-2">
                        {!v.en_route_le && (
                          <Button
                            type="button"
                            className="min-h-11 flex-1"
                            disabled={enVol === v.id}
                            onClick={() => progresser(v, 'route')}
                          >
                            En route
                          </Button>
                        )}
                        {v.en_route_le && !v.arrivee_le && (
                          <Button
                            type="button"
                            className="min-h-11 flex-1"
                            disabled={enVol === v.id}
                            onClick={() => progresser(v, 'arrivee')}
                          >
                            Arrivé
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant={v.arrivee_le ? 'default' : 'outline'}
                          className="min-h-11 flex-1"
                          onClick={() => navigate(`/visites/${v.id}`)}
                        >
                          Ouvrir la visite
                        </Button>
                        {/* `geo:` d'abord (sélecteur natif d'appli de
                            navigation), repli Google Maps sur navigateur de
                            bureau. Aucun lien si le lead n'a pas de GPS. */}
                        {geo && (
                          <a
                            href={geo}
                            className="inline-flex min-h-11 items-center gap-1 rounded-md border px-3 text-sm"
                          >
                            <Navigation size={15} strokeWidth={1.75} aria-hidden="true" />
                            Y aller
                          </a>
                        )}
                        {maps && (
                          <a
                            href={maps}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex min-h-11 items-center px-2 text-sm underline"
                          >
                            Google Maps
                          </a>
                        )}
                      </div>
                    </Card>
                  </li>
                )
              })}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
