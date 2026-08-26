/**
 * WIR264/ZFSM2 — Page PUBLIQUE du compte-rendu d'intervention signé.
 * Route /intervention-rapport/:token — autonome (aucun login, aucun layout
 * ERP), jeton DISTINCT de celui du suivi « en route ».
 *
 * Le jeton et l'endpoint existaient sans aucune page ; l'action `lien-rapport`
 * renvoyait un chemin amputé. Cette page rend le payload servi par le serveur
 * (photos, matériel consommé, réserves, signature) et propose le PDF via le
 * `pdf_url` du MÊME jeton. Aucun coût d'achat, aucune marge : le serveur n'en
 * envoie pas et la page n'en fabrique pas.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import installationsApi from '../../api/installationsApi'
// VX75 — toute date passe par lib/format.js (jamais un toLocaleDateString nu).
import { formatDate } from '../../lib/format'

const fmtDate = (iso) => {
  if (!iso) return null
  const rendu = formatDate(iso)
  return rendu === '—' ? null : rendu
}

const PHASES = [
  ['avant', 'Avant'],
  ['pendant', 'Pendant'],
  ['apres', 'Après'],
]

export default function InterventionRapportPublicPage() {
  const { token } = useParams()
  const [etat, setEtat] = useState('loading') // loading|ok|invalide
  const [data, setData] = useState(null)

  useEffect(() => {
    let vivant = true
    installationsApi.getInterventionRapportPublic(token)
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
      <div className="ui-root page" style={{ maxWidth: 640, margin: '40px auto' }}>
        <p>Chargement…</p>
      </div>
    )
  }

  if (etat === 'invalide') {
    return (
      <div className="ui-root page" style={{ maxWidth: 640, margin: '40px auto' }}>
        <h2>Compte-rendu d’intervention</h2>
        <p role="alert" className="page-error">
          Ce lien est introuvable ou a été révoqué — contactez-nous pour en
          recevoir un nouveau.
        </p>
      </div>
    )
  }

  const photos = data?.photos ?? {}
  const consommation = data?.consommation ?? []
  const reserves = data?.reserves ?? []

  return (
    <div className="ui-root page" style={{ maxWidth: 640, margin: '40px auto' }}>
      <h2>Compte-rendu d’intervention</h2>
      <p>
        {data?.type_intervention_display ?? '—'}
        {data?.chantier_reference ? ` · ${data.chantier_reference}` : ''}
        {data?.site_ville ? ` · ${data.site_ville}` : ''}
      </p>
      {fmtDate(data?.date_realisee) && (
        <p>Réalisée le {fmtDate(data.date_realisee)}</p>
      )}

      {data?.pdf_url && (
        <p>
          <a href={data.pdf_url} target="_blank" rel="noreferrer">
            Télécharger le compte-rendu (PDF)
          </a>
        </p>
      )}

      {PHASES.map(([cle, libelle]) => (
        (photos[cle] ?? []).length > 0 && (
          <section key={cle} data-testid={`rapport-photos-${cle}`}>
            <h3>Photos — {libelle}</h3>
            <ul>
              {photos[cle].map((p, i) => (
                <li key={p.url ?? i}>
                  <a href={p.url} target="_blank" rel="noreferrer">
                    {p.libelle || 'Photo'}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )
      ))}

      {consommation.length > 0 && (
        <section data-testid="rapport-consommation">
          <h3>Matériel posé</h3>
          <ul>
            {consommation.map((l, i) => (
              <li key={`${l.designation}-${i}`}>
                {l.designation} — {l.quantite_utilisee ?? 0}
              </li>
            ))}
          </ul>
        </section>
      )}

      {reserves.length > 0 && (
        <section data-testid="rapport-reserves">
          <h3>Réserves</h3>
          <ul>
            {reserves.map((r, i) => (
              <li key={`${r.description}-${i}`}>
                {r.description} — {r.statut}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data?.signataire_nom && (
        <p data-testid="rapport-signature">
          Signé par {data.signataire_nom}
          {fmtDate(data?.signe_le) ? ` le ${fmtDate(data.signe_le)}` : ''}.
        </p>
      )}
    </div>
  )
}
