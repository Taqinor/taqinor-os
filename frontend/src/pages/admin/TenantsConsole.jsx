import { useCallback, useEffect, useState } from 'react'
import api from '../../api/axios'

/**
 * SCA22 — Console fondateur des tenants (superuser uniquement, SANS billing).
 *
 * Écran français minimal : liste des sociétés + compteurs d'usage simples
 * (utilisateurs / devis / factures), changement de statut (actif / suspendu /
 * fermeture) et note libre `plan_flag`. La sécurité est portée par le SERVEUR
 * (endpoints staff-only : un non-staff reçoit 403) — cet écran ne fait
 * qu'afficher ce que l'API autorise.
 */
const STATUTS = [
  { value: 'actif', label: 'Actif' },
  { value: 'suspendu', label: 'Suspendu' },
  { value: 'fermeture', label: 'En fermeture' },
]

export default function TenantsConsole() {
  const [tenants, setTenants] = useState([])
  const [erreur, setErreur] = useState('')
  const [chargement, setChargement] = useState(true)
  const [notes, setNotes] = useState({})

  // NB : fetch en chaîne de promesses (pas de setState synchrone dans l'effet,
  // règle react-hooks) — l'état « chargement » démarre à true et n'est éteint
  // qu'à la fin du premier fetch.
  const charger = useCallback(() => (
    api.get('/auth/console/tenants/')
      .then(({ data }) => {
        setTenants(data)
        setNotes(Object.fromEntries(data.map((t) => [t.id, t.plan_flag || ''])))
        setErreur('')
      })
      .catch((e) => {
        setErreur(
          e?.response?.status === 403
            ? 'Accès réservé à la console fondateur.'
            : 'Impossible de charger les sociétés.'
        )
      })
      .finally(() => setChargement(false))
  ), [])

  useEffect(() => { charger() }, [charger])

  const changerStatut = async (tenant, statut) => {
    if (statut === tenant.statut) return
    try {
      await api.post(`/auth/console/tenants/${tenant.id}/statut/`, { statut })
      await charger()
    } catch {
      setErreur(`Échec du changement de statut pour « ${tenant.nom} ».`)
    }
  }

  const enregistrerNote = async (tenant) => {
    try {
      await api.post(`/auth/console/tenants/${tenant.id}/note/`, {
        plan_flag: notes[tenant.id] ?? '',
      })
      await charger()
    } catch {
      setErreur(`Échec de l'enregistrement de la note pour « ${tenant.nom} ».`)
    }
  }

  if (chargement) return <div className="page-pad">Chargement…</div>
  if (erreur && tenants.length === 0) {
    return <div className="page-pad" role="alert">{erreur}</div>
  }

  return (
    <div className="page-pad">
      <h2>Console des sociétés</h2>
      <p className="text-muted">
        Pilotage fondateur : statut d'accès et annotations. Suspendre une
        société bloque immédiatement sa connexion et son API.
      </p>
      {erreur && <div role="alert" className="text-danger">{erreur}</div>}
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table" data-testid="tenants-console-table">
          <thead>
            <tr>
              <th>Société</th>
              <th>Statut</th>
              <th>Utilisateurs</th>
              <th>Devis</th>
              <th>Factures</th>
              <th>Note (plan)</th>
              <th>Créée le</th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id}>
                <td>
                  <strong>{t.nom}</strong>
                  <div className="text-muted">{t.slug}</div>
                </td>
                <td>
                  <select
                    aria-label={`Statut de ${t.nom}`}
                    value={t.statut}
                    onChange={(e) => changerStatut(t, e.target.value)}
                  >
                    {STATUTS.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </td>
                <td>{t.usage?.users ?? '—'}</td>
                <td>{t.usage?.devis ?? '—'}</td>
                <td>{t.usage?.factures ?? '—'}</td>
                <td>
                  <input
                    aria-label={`Note de plan de ${t.nom}`}
                    value={notes[t.id] ?? ''}
                    onChange={(e) =>
                      setNotes((n) => ({ ...n, [t.id]: e.target.value }))}
                    onBlur={() => enregistrerNote(t)}
                    placeholder="Note libre…"
                  />
                </td>
                <td>
                  {t.date_creation
                    ? new Date(t.date_creation).toLocaleDateString('fr-FR')
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
