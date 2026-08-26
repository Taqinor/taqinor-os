/**
 * WIR264/XFSM7 — Page PUBLIQUE « technicien en route » d'une intervention.
 * Route /intervention/:token — autonome (aucun login, aucun layout ERP).
 *
 * Le jeton existait et l'endpoint aussi, mais AUCUNE page ne les consommait :
 * l'action `lien-client` renvoyait un chemin amputé qui ne menait nulle part.
 * Même patron que TicketSuiviPage (XSAV10/FG86) : le jeton EST l'autorisation,
 * un jeton inconnu/expiré donne un message FRANÇAIS (jamais du JSON brut), et
 * le payload est celui du serveur — aucune donnée interne, aucun coût.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import installationsApi from '../../api/installationsApi'

const fmtHeure = (iso) => {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

export default function InterventionSuiviPublicPage() {
  const { token } = useParams()
  const [etat, setEtat] = useState('loading') // loading|ok|invalide
  const [data, setData] = useState(null)

  useEffect(() => {
    let vivant = true
    installationsApi.getInterventionPublique(token)
      .then((res) => {
        if (!vivant) return
        setData(res.data || {})
        setEtat('ok')
      })
      .catch(() => { if (vivant) setEtat('invalide') })
    return () => { vivant = false }
  }, [token])

  if (etat === 'loading') {
    return (
      <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
        <p>Chargement…</p>
      </div>
    )
  }

  if (etat === 'invalide') {
    return (
      <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
        <h2>Suivi de votre intervention</h2>
        <p role="alert" className="page-error">
          Ce lien de suivi est introuvable ou a expiré — contactez-nous pour en
          recevoir un nouveau.
        </p>
      </div>
    )
  }

  const fenetreDebut = fmtHeure(data?.fenetre_debut)
  const fenetreFin = fmtHeure(data?.fenetre_fin)

  return (
    <div className="ui-root page" style={{ maxWidth: 480, margin: '40px auto' }}>
      <h2>Suivi de votre intervention</h2>

      <p role="status" data-testid="suivi-statut">
        Statut : <strong>{data?.statut_display ?? data?.statut ?? '—'}</strong>
      </p>

      {data?.technicien_nom && (
        <p>Technicien : {data.technicien_nom}</p>
      )}
      {data?.site_ville && <p>Site : {data.site_ville}</p>}

      {(fenetreDebut || fenetreFin) && (
        <p>
          Créneau prévu : {fenetreDebut ?? '—'}
          {fenetreFin ? ` → ${fenetreFin}` : ''}
        </p>
      )}

      {/* L'ETA n'est servie QUE si le serveur a pu la calculer : jamais une
          estimation inventée côté page. */}
      {data?.eta_minutes != null && (
        <p data-testid="suivi-eta">
          Arrivée estimée dans environ {data.eta_minutes} minutes
          {data?.distance_km != null ? ` (${data.distance_km} km)` : ''}.
        </p>
      )}
    </div>
  )
}
