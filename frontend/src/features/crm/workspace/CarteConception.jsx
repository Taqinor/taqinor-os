// ALEA71 (D-ACAL-97, contrôle C4-E7) — la carte « Conception » de la fiche du
// lead : ce que le moteur UNIQUE a rangé pour ce lead (taille, production,
// économies, retour sur investissement avec la source du prix, suppositions
// avec leur champ, « Recalcul en cours », phrase du dernier recalcul).
//
// Aucun calcul ici : des lectures de `GET ventes/conception/<lead>/` (contrat
// `apps/ventes/contract_samples/conception_lead.json`). La carte n'écrit rien.
// Un lead tout neuf n'a pas encore de conception (404 quelques secondes) :
// la carte le dit et relit d'elle-même, un nombre BORNÉ de fois.
import { useEffect, useState } from 'react'
import ventesApi from '../../../api/ventesApi'
import { formatKwc, formatMAD, formatNumber } from '../../../lib/format'

const OPTIONS = [['sans', 'Sans batterie'], ['avec', 'Avec batterie']]

/** Une valeur servie `{valeur, unite, source}` → sa valeur, ou `null`. */
const lire = (table, cle) => table?.[cle]?.valeur ?? null

function Ligne({ libelle, children, testId }) {
  return (
    <div className="flex justify-between gap-2" data-testid={testId}>
      <dt className="text-muted-foreground">{libelle}</dt>
      <dd className="m-0 text-right text-foreground">{children}</dd>
    </div>
  )
}

function Colonne({ option, titre, table, payback }) {
  const panneaux = lire(table, 'nb_panneaux')
  const kwc = lire(table, 'puissance_kwc')
  const production = lire(table, 'production_annuelle')
  const economies = lire(table, 'economies_annuelles')
  const m3 = lire(table, 'm3_jour')
  const retour = lire(table, 'payback')
  return (
    <div className="min-w-0 flex-1" data-testid={`carte-conception-option-${option}`}>
      {titre && <div className="mb-1 text-xs font-semibold text-foreground">{titre}</div>}
      <dl className="m-0 flex flex-col gap-1">
        {panneaux != null && (
          <Ligne libelle="Taille">
            {panneaux} panneaux{kwc != null ? ` · ${formatKwc(kwc)}` : ''}
          </Ligne>
        )}
        {production != null && (
          <Ligne libelle="Production">{formatNumber(production, { decimals: 0 })} kWh/an</Ligne>
        )}
        {m3 != null && <Ligne libelle="Eau pompée">{formatNumber(m3, { maxDecimals: 1 })} m³/jour</Ligne>}
        {economies != null && (
          <Ligne libelle="Économies">{formatMAD(economies, { decimals: 0 })}/an</Ligne>
        )}
        {table?.payback !== undefined && (
          <Ligne libelle="Retour">
            {retour != null
              ? <>
                {`${formatNumber(retour, { maxDecimals: 1 })} ans`}
                {payback?.devis_ref && (
                  <span className="block text-xs text-muted-foreground">
                    d'après le devis {payback.devis_ref}
                  </span>
                )}
              </>
              : <span className="text-xs text-muted-foreground">{payback?.motif || '—'}</span>}
          </Ligne>
        )}
      </dl>
    </div>
  )
}

/** Les phrases `verdicts.non_calcule` (fiche technique incomplète), sans doublon. */
function phrasesNonCalcule(valeurs) {
  const vues = new Set()
  for (const table of Object.values(valeurs || {})) {
    const phrase = table?.verdicts?.valeur?.non_calcule
    if (phrase) vues.add(phrase)
  }
  return [...vues]
}

export default function CarteConception({ leadId, delaiRelectureMs = 4000, maxRelectures = 6 }) {
  const [etat, setEtat] = useState({ statut: 'charge', conception: null })

  useEffect(() => {
    let vivant = true
    let minuterie = null
    const relire = async (fait) => {
      let suite = null  // 'attente' | 'perimee' quand une relecture reste utile
      try {
        const { data } = await ventesApi.getConceptionLead(leadId)
        if (!vivant) return
        const conception = data?.etat ? data : null
        suite = conception?.perimee ? 'perimee' : (conception ? null : 'attente')
        setEtat({ statut: conception ? 'ok' : 'absente', conception })
      } catch (err) {
        if (!vivant) return
        if (err?.response?.status === 404) {
          suite = 'attente'
          setEtat({ statut: 'absente', conception: null })
        } else {
          setEtat((e) => (e.conception ? e : { statut: 'erreur', conception: null }))
        }
      }
      if (suite && fait < maxRelectures) {
        minuterie = setTimeout(() => relire(fait + 1), delaiRelectureMs)
      } else if (suite === 'attente') {
        setEtat({ statut: 'vide', conception: null })
      }
    }
    if (leadId) relire(0)
    return () => { vivant = false; if (minuterie) clearTimeout(minuterie) }
  }, [leadId, delaiRelectureMs, maxRelectures])

  const { statut, conception } = etat
  if (!leadId || statut === 'charge') return null
  const boite = 'mb-3 rounded-lg border border-border bg-card p-3 text-sm'
  const titre = <h3 className="mb-2 text-sm font-semibold text-foreground">Conception</h3>

  if (statut === 'absente') {
    return (
      <section className={boite} data-testid="carte-conception-attente">
        {titre}
        <p className="m-0 text-muted-foreground">Conception en cours de calcul…</p>
      </section>
    )
  }
  if (statut === 'vide') {
    return (
      <section className={boite} data-testid="carte-conception-sans-conception">
        {titre}
        <p className="m-0 text-muted-foreground">
          Pas encore de conception : elle apparaît dès que la fiche est assez remplie.
        </p>
      </section>
    )
  }
  if (statut === 'erreur') {
    return (
      <section className={boite} data-testid="carte-conception-indisponible">
        {titre}
        <p className="m-0 text-muted-foreground">Conception indisponible pour le moment.</p>
      </section>
    )
  }

  if (conception.etat === 'refus') {
    const refus = conception.refus || {}
    return (
      <section className={boite} data-testid="carte-conception">
        {titre}
        <p className="m-0 text-warning" data-testid="carte-conception-refus">
          {refus.message}{refus.champ ? ` (champ : ${refus.champ})` : ''}
        </p>
      </section>
    )
  }

  const valeurs = conception.valeurs || {}
  const colonnes = OPTIONS.filter(([cle]) => valeurs[cle])
  const deux = colonnes.length > 1
  const nonCalcules = phrasesNonCalcule(valeurs)
  const raison = conception.declencheur?.raison

  return (
    <section className={boite} data-testid="carte-conception">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="m-0 text-sm font-semibold text-foreground">Conception</h3>
        {conception.perimee && (
          <span className="text-xs text-warning" role="status" data-testid="carte-conception-recalcul">
            Recalcul en cours
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-3">
        {colonnes.map(([cle, libelle]) => (
          <Colonne key={cle} option={cle} titre={deux ? libelle : ''} table={valeurs[cle]}
            payback={conception.payback_devis} />
        ))}
      </div>
      {(conception.suppositions?.length > 0 || nonCalcules.length > 0) && (
        <div className="mt-2 border-t border-border pt-2">
          <div className="text-xs font-semibold text-foreground">Suppositions à vérifier</div>
          <ul className="m-0 mt-1 list-disc pl-4 text-xs text-muted-foreground">
            {(conception.suppositions || []).map((s) => (
              <li key={`${s.code}-${s.champ}`} data-testid={`carte-conception-supposition-${s.champ}`}>
                {s.message}
              </li>
            ))}
            {nonCalcules.map((phrase) => (
              <li key={phrase} data-testid="carte-conception-non-calcule">{phrase}</li>
            ))}
          </ul>
        </div>
      )}
      {raison && (
        <p className="m-0 mt-2 text-xs text-muted-foreground" data-testid="carte-conception-historique">
          {raison}
        </p>
      )}
    </section>
  )
}
