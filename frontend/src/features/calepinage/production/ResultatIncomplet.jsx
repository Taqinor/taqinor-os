import { Link } from 'react-router-dom'
import { formatNumber, formatPercent } from '../../../lib/format'
import { Stat } from '../../../ui'
import { PARAM_ONGLET } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'
import { BandeauBorneHaute } from './BandeauProvenanceProduction'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'

/* ACAL700 — L'ÉTAT « RÉSULTAT INCOMPLET » (maquette ResultatsIncomplet.dc.html) :
   un plafond, pas un résultat. Tout est SERVI (`production.total`,
   `cascade.a_renseigner`, `cascade.postes_lisibles`, `pose`, parcours) — aucune
   valeur chiffrée n'est écrite ici. Résultat complet : rien. Sans lignes
   `a_renseigner` servies, repli sur l'ancien bandeau « borne haute ».
   Niveau essentiel. « Renseigner » ouvre le champ par le mécanisme d'ACAL397. */

const RAISON = {
  reglage_societe: 'Aucune valeur pour votre société',
  fiche_panneau: 'Absent de la fiche du panneau',
}

function lienRenseigner(calepinageId, cible) {
  const onglet = cible?.onglet || ''
  const champ = cible?.champ || ''
  if (onglet === 'reglages') {
    return champ ? `/calepinage/reglages#${champ}` : '/calepinage/reglages'
  }
  const p = new URLSearchParams()
  if (onglet) p.set(PARAM_ONGLET, onglet)
  if (champ) p.set(PARAM_CHAMP, champ)
  const q = p.toString()
  return `/calepinage/${calepinageId}${q ? `?${q}` : ''}`
}

function CeQuiEstSur({ data, parcours }) {
  const electrique = (parcours?.etapes || []).find((e) => e.cle === 'electrique')
  const ombres = (data?.cascade?.postes_lisibles?.postes || [])
    .find((p) => p.poste === 'ombres_proches' && p.statut === 'compte')
  const modules = data?.pose?.total_modules
  const kwc = data?.production?.total?.kwc
  return (
    <section className="rounded-md border border-border/60 p-3" data-testid="acal700-sur">
      <h3 className="text-sm font-medium">Ce qui est déjà sûr</h3>
      <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {modules !== null && modules !== undefined && (
          <Stat label="Panneaux" value={formatNumber(modules, { decimals: 0 })} />
        )}
        {kwc !== null && kwc !== undefined && (
          <Stat label="Puissance" value={`${formatNumber(kwc, { decimals: 2 })} kWc`} />
        )}
        {electrique?.etat === 'fait' && <Stat label="Raccordement" value="Conforme" />}
        {ombres && (
          <Stat label="Ombres proches" value={`− ${formatPercent(ombres.perte_pct, { decimals: 1 })}`} />
        )}
      </div>
    </section>
  )
}

export default function ResultatIncomplet({ calepinageId, data, parcours = null }) {
  const total = data?.production?.total
  if (!estIncomplet(total)) return null
  const aRenseigner = data?.cascade?.a_renseigner
  const lignes = Array.isArray(aRenseigner?.lignes) ? aRenseigner.lignes : []
  if (lignes.length === 0) return <BandeauBorneHaute total={total} />
  return (
    <div className="flex flex-col gap-3" data-testid="acal700-incomplet">
      <p className="text-sm font-medium" data-testid="acal700-etiquette">
        Production la première année · au plus
      </p>
      <p className="text-sm" data-testid="acal700-plafond">
        {`C'est un plafond : ${lignes.length} ${lignes.length > 1 ? 'pertes ne sont pas encore comptées' : 'perte n\'est pas encore comptée'}. Le chiffre réel sera plus bas.`}
      </p>
      <p className="text-xs text-muted-foreground" data-testid="acal700-jauge">
        {`${aRenseigner.etapes_comptees} étapes sur ${aRenseigner.etapes_a_compter}`}
      </p>
      <section data-testid="acal700-liste">
        <h3 className="text-sm font-medium">Pour un résultat complet</h3>
        <ol className="mt-1 list-decimal pl-5">
          {lignes.map((ligne) => (
            <li key={`${ligne.etape}-${ligne.cle}`} className="py-1" data-testid="acal700-ligne">
              <div className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 basis-48">
                  <span className="block text-sm">{ligne.libelle}</span>
                  {RAISON[ligne.nature] && (
                    <span className="block text-xs text-muted-foreground">{RAISON[ligne.nature]}</span>
                  )}
                </span>
                <Link
                  to={lienRenseigner(calepinageId, ligne.cible)}
                  className="inline-flex min-h-11 items-center rounded-md border border-border px-3 text-sm font-medium text-primary"
                  data-testid="acal700-renseigner"
                >
                  Renseigner
                </Link>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <section className="rounded-md border border-border/60 p-3" data-testid="acal700-demarrage">
        <h3 className="text-sm font-medium">Démarrage rapide</h3>
        <Link
          to="/calepinage/reglages"
          className="mt-1 inline-flex min-h-11 items-center text-sm text-primary underline"
          data-testid="acal700-lien-reglages"
        >
          Ouvrir les réglages de simulation
        </Link>
      </section>
      <CeQuiEstSur data={data} parcours={parcours} />
      <p className="text-xs text-muted-foreground" data-testid="acal700-note">
        Les années basses et l'indice de performance s'affichent dès que le résultat est complet.
      </p>
    </div>
  )
}
