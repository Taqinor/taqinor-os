import { useEffect, useState } from 'react'
import { HardHat } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import {
  Badge, Button, Card, EmptyState, Spinner,
} from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   NTPRT14 — « Mes chantiers » (portail client authentifié).
   ----------------------------------------------------------------------------
   Timeline réutilisant la timeline PORTAIL déjà synchronisée (CHT10/CHT11,
   `apps.portail.selectors.jalons_du_chantier` — lecture seule) + galerie
   photos avant/pendant/après filtrée sur `records.Attachment`
   (`apps.installations.selectors.photos_chantier_client_portail`). AUCUNE
   donnée financière (BOM/prix exclus, contrat testé côté serveur). Le
   détail (jalons) et les photos sont chargés à la demande, quand le client
   ouvre le suivi d'un chantier — même patron que « Voir la preuve de
   livraison » (PortailClientLivraisons.jsx).
   ========================================================================== */

const TON_STATUT = {
  signe: 'neutral',
  materiel_commande: 'info',
  planifie: 'info',
  en_cours: 'warning',
  installe: 'info',
  receptionne: 'success',
  cloture: 'neutral',
}

const LABEL_PHASE = { avant: 'Avant', pendant: 'Pendant', apres: 'Après' }
const ORDRE_PHASE = ['avant', 'pendant', 'apres']

function Timeline({ jalons }) {
  if (jalons.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucun jalon publié pour ce chantier pour le moment.
      </p>
    )
  }
  return (
    <ol className="flex flex-col gap-2">
      {jalons.map((j) => (
        <li key={j.id} className="flex items-center gap-2 text-sm">
          <span
            className="size-2.5 shrink-0 rounded-full"
            style={{
              background: j.atteint ? 'var(--success)' : 'var(--border)',
            }}
            aria-hidden="true"
          />
          <span className={j.atteint ? 'text-foreground' : 'text-muted-foreground'}>
            {j.libelle}
          </span>
          {j.date_jalon && (
            <span className="text-xs text-muted-foreground">
              {formatDate(j.date_jalon)}
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}

function Galerie({ photos }) {
  if (photos.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune photo pour ce chantier pour le moment.
      </p>
    )
  }
  const parPhase = ORDRE_PHASE
    .map((phase) => ({ phase, items: photos.filter((p) => p.phase === phase) }))
    .concat([{ phase: null, items: photos.filter((p) => !p.phase) }])
    .filter((g) => g.items.length > 0)

  return (
    <div className="flex flex-col gap-3">
      {parPhase.map((groupe) => (
        <div key={groupe.phase || 'autre'}>
          {groupe.phase && (
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              {LABEL_PHASE[groupe.phase] || groupe.phase}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {groupe.items.map((p) => (
              <img
                key={p.id}
                src={p.url}
                alt={p.filename}
                loading="lazy"
                className="size-24 rounded border border-border object-cover"
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function PortailClientChantiers() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  // État par chantier : { etat: 'chargement'|'ok'|'erreur', jalons, photos }.
  const [suivis, setSuivis] = useState({})

  const charger = () => {
    setLoading(true)
    portailApi.chantiers.liste()
      .then((r) => { setRows(r.data?.results ?? []); setErreur(false) })
      .catch(() => setErreur(true))
      .finally(() => setLoading(false))
  }

  const voirSuivi = (id) => {
    setSuivis((etat) => ({ ...etat, [id]: { etat: 'chargement' } }))
    Promise.all([
      portailApi.chantiers.detail(id),
      portailApi.chantiers.photos(id),
    ])
      .then(([detail, photos]) => setSuivis((etat) => ({
        ...etat,
        [id]: {
          etat: 'ok',
          jalons: detail.data?.jalons ?? [],
          photos: photos.data?.results ?? [],
        },
      })))
      .catch(() => setSuivis((etat) => (
        { ...etat, [id]: { etat: 'erreur' } })))
  }

  useEffect(() => {
    // Différé d'un microtask : même patron que PortailClientDevis/Factures/
    // Livraisons (évite react-hooks/set-state-in-effect).
    Promise.resolve().then(charger)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de vos chantiers…
      </div>
    )
  }

  if (erreur) {
    return (
      <EmptyState
        title="Chantiers indisponibles"
        description="Vos chantiers n’ont pas pu être chargés. Réessayez plus tard."
      />
    )
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <HardHat className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Mes chantiers
        </h1>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="Aucun chantier"
          description="Vous n’avez aucun chantier pour le moment."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((c) => (
            <Card key={c.id} className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{c.reference}</p>
                  <p className="text-xs text-muted-foreground">
                    {c.site_ville || 'Ville non renseignée'}
                    {' — '}
                    Créé le {formatDate(c.date_creation)}
                  </p>
                </div>
                <Badge tone={TON_STATUT[c.statut] || 'neutral'}>
                  {c.statut_display}
                </Badge>
              </div>

              {!suivis[c.id] && (
                <div>
                  <Button variant="outline" size="sm"
                          onClick={() => voirSuivi(c.id)}>
                    Voir le suivi
                  </Button>
                </div>
              )}
              {suivis[c.id]?.etat === 'chargement' && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner /> Chargement du suivi…
                </div>
              )}
              {suivis[c.id]?.etat === 'erreur' && (
                <p className="text-sm text-muted-foreground">
                  Le suivi de ce chantier n’a pas pu être affiché.
                </p>
              )}
              {suivis[c.id]?.etat === 'ok' && (
                <div className="flex flex-col gap-4">
                  <Timeline jalons={suivis[c.id].jalons} />
                  <Galerie photos={suivis[c.id].photos} />
                </div>
              )}
            </Card>
          ))}
        </ul>
      )}
    </>
  )
}
