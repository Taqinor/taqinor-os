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
  // N100(b) — formulaire « Nouveau tenant ». Le mot de passe provisoire n'est
  // renvoyé qu'UNE fois par le serveur : on le garde en mémoire le temps que
  // le fondateur le copie, jamais persisté.
  const [creation, setCreation] = useState({ nom: '', email: '' })
  const [creationEnCours, setCreationEnCours] = useState(false)
  const [nouveauTenant, setNouveauTenant] = useState(null)

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

  const creerTenant = async (e) => {
    e.preventDefault()
    const nom = creation.nom.trim()
    const email = creation.email.trim()
    if (!nom || !email) {
      setErreur('Nom de société et email de l’administrateur sont requis.')
      return
    }
    setCreationEnCours(true)
    try {
      const { data } = await api.post('/auth/console/tenants/creer/', {
        nom, email,
      })
      setNouveauTenant(data)
      setCreation({ nom: '', email: '' })
      setErreur('')
      await charger()
    } catch (e2) {
      setErreur(
        e2?.response?.data?.detail
        || 'Échec de la création du tenant.'
      )
    } finally {
      setCreationEnCours(false)
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

      {/* N100(b) — provisionnement administré d'une nouvelle société. */}
      <form onSubmit={creerTenant} data-testid="tenant-creation-form">
        <h3>Nouveau tenant</h3>
        <label htmlFor="tenant-nom">Nom de la société</label>
        <input
          id="tenant-nom"
          value={creation.nom}
          onChange={(e) => setCreation((c) => ({ ...c, nom: e.target.value }))}
          placeholder="Installateur Nord"
        />
        <label htmlFor="tenant-email">Email de l&apos;administrateur</label>
        <input
          id="tenant-email"
          type="email"
          value={creation.email}
          onChange={(e) => setCreation((c) => ({ ...c, email: e.target.value }))}
          placeholder="chef@exemple.ma"
        />
        <button type="submit" disabled={creationEnCours}>
          Créer le tenant
        </button>
      </form>

      {nouveauTenant && (
        <div role="status" data-testid="tenant-cree">
          {nouveauTenant.deja_existant ? (
            <p>
              La société « {nouveauTenant.nom} » existait déjà — rien n&apos;a
              été recréé.
            </p>
          ) : (
            <>
              <p>
                Société « {nouveauTenant.nom} » créée. Transmettez ces accès à
                son administrateur : le mot de passe devra être changé à la
                première connexion.
              </p>
              <p>
                Identifiant : <code>{nouveauTenant.admin?.username}</code>
                {' — '}
                Mot de passe provisoire :{' '}
                <code data-testid="mot-de-passe-provisoire">
                  {nouveauTenant.mot_de_passe_provisoire}
                </code>
              </p>
              <p className="text-muted">
                Ce mot de passe n&apos;est affiché qu&apos;une seule fois.
              </p>
            </>
          )}
        </div>
      )}

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
