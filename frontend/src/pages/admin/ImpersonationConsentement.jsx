import { useCallback, useEffect, useState } from 'react'
import adminopsApi from '../../api/adminopsApi'

/**
 * NTADM22 — écran de CONSENTEMENT du tenant (Administrateur).
 *
 * C'est l'unique endroit où une session de support peut être autorisée. Tant
 * qu'« Autoriser » n'est pas cliqué, la demande reste inerte et le support
 * n'obtient aucun accès. Un refus est définitif, et une demande expirée ne
 * peut plus être autorisée (le serveur le refuse également).
 */
const LIBELLES_STATUT = {
  en_attente: 'En attente de votre décision',
  active: 'Autorisée',
  refusee: 'Refusée',
  expiree: 'Expirée',
  terminee: 'Terminée',
}

export default function ImpersonationConsentement() {
  const [demandes, setDemandes] = useState([])
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)

  const charger = useCallback(() => (
    adminopsApi.impersonationsEnAttente()
      .then(({ data }) => {
        setDemandes(Array.isArray(data) ? data : [])
        setErreur('')
      })
      .catch((e) => {
        setErreur(
          e?.response?.status === 403
            ? "Réservé à l'Administrateur de la société."
            : 'Impossible de charger les demandes.'
        )
      })
      .finally(() => setChargement(false))
  ), [])

  useEffect(() => { charger() }, [charger])

  const decider = async (demande, action) => {
    try {
      if (action === 'autoriser') {
        await adminopsApi.consentirImpersonation(demande.id)
      } else {
        await adminopsApi.refuserImpersonation(demande.id)
      }
      await charger()
    } catch (e) {
      setErreur(e?.response?.data?.detail || 'Action impossible.')
    }
  }

  if (chargement) return <div className="page-pad">Chargement…</div>

  return (
    <div className="page-pad">
      <h2>Demandes de session support</h2>
      <p className="text-muted">
        Le support de l&apos;éditeur ne peut accéder à votre société
        qu&apos;avec votre autorisation explicite, et pour la durée indiquée.
        Toutes ses actions sont marquées dans le journal d&apos;audit.
      </p>
      {erreur && <div role="alert" className="text-danger">{erreur}</div>}

      {demandes.length === 0 ? (
        <p data-testid="impersonation-aucune">Aucune demande.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table
            className="data-table"
            data-testid="impersonation-consentement-table"
          >
            <thead>
              <tr>
                <th>Utilisateur visé</th>
                <th>Motif</th>
                <th>Demandée par</th>
                <th>Statut</th>
                <th>Décision</th>
              </tr>
            </thead>
            <tbody>
              {demandes.map((d) => (
                <tr key={d.id}>
                  <td data-label="Utilisateur visé">{d.cible_nom}</td>
                  <td data-label="Motif">{d.motif}</td>
                  <td data-label="Demandée par">{d.support_nom}</td>
                  <td data-label="Statut">
                    {LIBELLES_STATUT[d.statut] || d.statut}
                  </td>
                  <td data-label="Décision">
                    {d.statut === 'en_attente' ? (
                      <>
                        <button
                          type="button"
                          onClick={() => decider(d, 'autoriser')}
                          aria-label={`Autoriser la demande pour ${d.cible_nom}`}
                        >
                          Autoriser
                        </button>
                        <button
                          type="button"
                          onClick={() => decider(d, 'refuser')}
                          aria-label={`Refuser la demande pour ${d.cible_nom}`}
                        >
                          Refuser
                        </button>
                      </>
                    ) : d.statut === 'active' ? (
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await adminopsApi.terminerImpersonation(d.id)
                            await charger()
                          } catch {
                            setErreur('Impossible de terminer la session.')
                          }
                        }}
                        aria-label={`Terminer la session pour ${d.cible_nom}`}
                      >
                        Terminer
                      </button>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
