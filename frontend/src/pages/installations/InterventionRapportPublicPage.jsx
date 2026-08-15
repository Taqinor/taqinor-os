/**
 * WIR264/ZFSM2 — Page PUBLIQUE du compte-rendu signé d'une intervention,
 * route `/intervention-rapport/:token`, hors coquille authentifiée. Jeton
 * DISTINCT de celui du suivi « en route ».
 *
 * L'action serveur `lien-rapport` exposait un jeton et un chemin, mais aucune
 * page ne les recevait : le lien partagé menait à du JSON.
 *
 * Le payload serveur ne porte que des quantités (matériel consommé SANS prix
 * d'achat ni marge — règle produit) : cette page n'affiche donc aucun montant,
 * et n'en calcule aucun. Jeton invalide → message français, jamais du JSON.
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { interventionPublicApi } from '../../api/installationsApi'
import { frenchError } from '../../lib/frenchError'
import NoIndex from '../../components/NoIndex'

const jour = (iso) => {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString('fr-FR')
}

export default function InterventionRapportPublicPage() {
  const { token } = useParams()
  const [etat, setEtat] = useState('chargement')
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let vivant = true
    interventionPublicApi.rapport(token)
      .then((res) => { if (vivant) { setData(res.data || {}); setEtat('valide') } })
      .catch((err) => {
        if (!vivant) return
        setErreur(frenchError(
          err, 'Ce compte-rendu est introuvable ou son lien a expiré.'))
        setEtat('invalide')
      })
    return () => { vivant = false }
  }, [token])

  if (etat === 'chargement') {
    return (
      <div className="ui-root page mx-auto max-w-2xl p-4">
        <NoIndex /><p>Chargement du compte-rendu…</p>
      </div>
    )
  }

  if (etat === 'invalide') {
    return (
      <div className="ui-root page mx-auto max-w-2xl p-4">
        <NoIndex />
        <h1 className="mb-2 text-lg font-semibold">Compte-rendu indisponible</h1>
        <p role="alert">{erreur}</p>
      </div>
    )
  }

  const photos = data.photos ?? {}
  const groupes = [
    ['avant', 'Avant'], ['pendant', 'Pendant'], ['apres', 'Après'],
  ].filter(([cle]) => (photos[cle] ?? []).length > 0)

  return (
    <div className="ui-root page mx-auto max-w-2xl p-4">
      <NoIndex />
      <h1 className="mb-1 text-lg font-semibold">Compte-rendu d'intervention</h1>
      <p className="mb-3 text-sm text-muted-foreground">
        {data.type_intervention_display ?? '—'}
        {data.chantier_reference ? ` · ${data.chantier_reference}` : ''}
        {data.site_ville ? ` · ${data.site_ville}` : ''}
        {jour(data.date_realisee) ? ` · réalisée le ${jour(data.date_realisee)}` : ''}
      </p>

      {data.pdf_url && (
        <p className="mb-4">
          <a href={data.pdf_url} target="_blank" rel="noreferrer"
             className="text-info underline">
            Télécharger le compte-rendu (PDF)
          </a>
        </p>
      )}

      {(data.equipe ?? []).length > 0 && (
        <section className="mb-4">
          <h2 className="mb-1 text-sm font-semibold">Intervenants</h2>
          <p className="text-sm">{data.equipe.join(', ')}</p>
        </section>
      )}

      {groupes.map(([cle, libelle]) => (
        <section key={cle} className="mb-4">
          <h2 className="mb-1 text-sm font-semibold">Photos — {libelle}</h2>
          <div className="flex flex-wrap gap-2">
            {photos[cle].map((p, i) => (
              <a key={p.url ?? i} href={p.url} target="_blank" rel="noreferrer"
                 className="text-sm text-info underline">
                {p.libelle || `Photo ${i + 1}`}
              </a>
            ))}
          </div>
        </section>
      ))}

      {(data.consommation ?? []).length > 0 && (
        <section className="mb-4">
          <h2 className="mb-1 text-sm font-semibold">Matériel utilisé</h2>
          {/* QUANTITÉS uniquement : le payload serveur ne porte aucun prix
              d'achat ni marge, et cette page n'en calcule aucun. */}
          <ul className="flex flex-col gap-1 text-sm">
            {data.consommation.map((l, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span>{l.designation}</span>
                <span className="tabular-nums text-muted-foreground">
                  {l.quantite_utilisee ?? '—'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {(data.serials ?? []).length > 0 && (
        <section className="mb-4">
          <h2 className="mb-1 text-sm font-semibold">Numéros de série</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {data.serials.map((s, i) => (
              <li key={i}>{s.designation} — {s.numero_serie}</li>
            ))}
          </ul>
        </section>
      )}

      {(data.reserves ?? []).length > 0 && (
        <section className="mb-4">
          <h2 className="mb-1 text-sm font-semibold">Réserves</h2>
          <ul className="flex flex-col gap-1 text-sm">
            {data.reserves.map((r, i) => (
              <li key={i}>
                {r.description} <span className="text-muted-foreground">({r.statut})</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.signataire_nom && (
        <p className="text-sm text-muted-foreground">
          Signé par {data.signataire_nom}
          {jour(data.signe_le) ? ` le ${jour(data.signe_le)}` : ''}.
        </p>
      )}
    </div>
  )
}
