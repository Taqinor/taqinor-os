/**
 * WIR264/XFSM7 — Page PUBLIQUE de suivi d'une intervention (« technicien en
 * route »), route `/intervention/:token`, hors coquille authentifiée.
 *
 * L'action serveur `lien-client` exposait un jeton et un chemin, mais aucune
 * page ne les recevait : le lien partagé au client menait à du JSON. C'est la
 * destination manquante.
 *
 * Read-only, aucune donnée interne : ni coût, ni marge, ni position GPS live.
 * Jeton inconnu/révoqué/expiré → message français, jamais du JSON.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { interventionPublicApi } from '../../api/installationsApi'
import { frenchError } from '../../lib/frenchError'
import NoIndex from '../../components/NoIndex'

const heure = (iso) => {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

export default function InterventionSuiviPublicPage() {
  const { token } = useParams()
  const [etat, setEtat] = useState('chargement')
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let vivant = true
    interventionPublicApi.suivi(token)
      .then((res) => { if (vivant) { setData(res.data || {}); setEtat('valide') } })
      .catch((err) => {
        if (!vivant) return
        setErreur(frenchError(err, 'Ce lien de suivi est introuvable ou a expiré.'))
        setEtat('invalide')
      })
    return () => { vivant = false }
  }, [token])

  if (etat === 'chargement') {
    return (
      <div className="ui-root page mx-auto max-w-lg p-4">
        <NoIndex /><p>Chargement du suivi…</p>
      </div>
    )
  }

  if (etat === 'invalide') {
    return (
      <div className="ui-root page mx-auto max-w-lg p-4">
        <NoIndex />
        <h1 className="mb-2 text-lg font-semibold">Suivi indisponible</h1>
        <p role="alert">{erreur}</p>
      </div>
    )
  }

  const fenetre = heure(data.fenetre_debut)
  const fenetreFin = heure(data.fenetre_fin)

  return (
    <div className="ui-root page mx-auto max-w-lg p-4">
      <NoIndex />
      <h1 className="mb-1 text-lg font-semibold">Suivi de votre intervention</h1>
      <p className="mb-3 text-sm text-muted-foreground">
        {data.statut_display ?? data.statut ?? '—'}
        {data.site_ville ? ` · ${data.site_ville}` : ''}
      </p>

      <ul className="flex flex-col gap-1 text-sm">
        {data.technicien_nom && (
          <li className="flex items-center gap-2">
            {data.technicien_avatar_url && (
              <img src={data.technicien_avatar_url} alt=""
                   className="size-8 rounded-full object-cover" />
            )}
            <span>Technicien : {data.technicien_nom}</span>
          </li>
        )}
        {fenetre && (
          <li>
            Créneau prévu : {fenetre}{fenetreFin ? ` — ${fenetreFin}` : ''}
          </li>
        )}
        {!fenetre && heure(data.date_prevue) && (
          <li>Date prévue : {heure(data.date_prevue)}</li>
        )}
        {/* L'ETA n'est servie QUE lorsque le technicien est en route et que
            les positions sont connues : on ne fabrique jamais d'estimation. */}
        {data.eta_minutes != null && (
          <li className="font-medium">
            Arrivée estimée dans {data.eta_minutes} minute(s)
            {data.distance_km != null ? ` (~${data.distance_km} km)` : ''}
          </li>
        )}
      </ul>

      {data.eta_minutes == null && (
        <p className="mt-3 text-sm text-muted-foreground">
          L'heure d'arrivée sera estimée dès que le technicien sera en route.
        </p>
      )}
    </div>
  )
}
