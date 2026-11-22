import { Link } from 'react-router-dom'
import { formatNumber, formatPercent } from '../../../lib/format'
import { lienManque } from './lienManque'
import { BandeauBorneHaute } from './BandeauProvenanceProduction'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'
import { nomDePerte } from './nomsPertes'
import { kwh } from './ResultatHeros.helpers'

/* ACAL700 — L'ÉTAT « RÉSULTAT INCOMPLET » (maquette ResultatsIncomplet.dc.html) :
   un plafond, pas un résultat. Tout est SERVI (`production.total`,
   `cascade.a_renseigner`, `cascade.postes_lisibles`, `pose`, parcours) — aucune
   valeur chiffrée n'est écrite ici. Résultat complet : rien. Sans lignes
   `a_renseigner` servies, repli sur l'ancien bandeau « borne haute ».
   Niveau essentiel. « Renseigner » ouvre le champ par le mécanisme d'ACAL397.
   Mise en page de la maquette : carte sombre « au plus » à gauche, « Pour un résultat complet » à
   droite, « Ce qui est déjà sûr » pleine largeur dessous (54-etape-resultats.css). La barre « N étapes
   sur M » n'existe que si le serveur sert les deux nombres (`a_renseigner`). */

const RAISON = {
  reglage_societe: 'Aucune valeur pour votre société',
  fiche_panneau: 'Absent de la fiche du panneau',
}

/* R3-06 — UN seul compte, celui du serveur : les pertes non renseignées sont
   `etapes_a_compter − etapes_comptees` (même ensemble que la mention « borne
   haute ») ; `lignes` n'en est que la part rattachable à un réglage ici. */
function phraseDuCompte(aRenseigner, ici) {
  const total = Math.max(
    (aRenseigner?.etapes_a_compter ?? 0) - (aRenseigner?.etapes_comptees ?? 0), ici)
  const pertes = `${total} ${total > 1 ? 'pertes non renseignées' : 'perte non renseignée'}`
  if (ici === total) return `${pertes}${total > 1 ? ', toutes à renseigner ici.' : ', à renseigner ici.'}`
  return `${pertes}, dont ${ici} à renseigner ici.`
}

function Valeur({ etiquette, valeur }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="cal-res-sourdine">{etiquette}</span>
      <span className="cal-res-tuile-valeur">{valeur}</span>
    </div>
  )
}

export function CeQuiEstSur({ data, parcours }) {
  const electrique = (parcours?.etapes || []).find((e) => e.cle === 'electrique')
  const ombres = (data?.cascade?.postes_lisibles?.postes || [])
    .find((p) => p.poste === 'ombres_proches' && p.statut === 'compte')
  const modules = data?.pose?.total_modules
  const kwc = data?.production?.total?.kwc ?? data?.pose?.kwc // la pose est un fait servi, même sans simulation
  return (
    <section className="cal-res-carte" data-testid="acal700-sur">
      <h2 className="cal-res-titre">Ce qui est déjà sûr</h2>
      <div className="cal-resinc-sur">
        {modules !== null && modules !== undefined && (
          <Valeur etiquette="Panneaux" valeur={formatNumber(modules, { decimals: 0 })} />
        )}
        {kwc !== null && kwc !== undefined && (
          <Valeur etiquette="Puissance" valeur={`${formatNumber(kwc, { decimals: 2 })} kWc`} />
        )}
        {electrique?.etat === 'fait' && <Valeur etiquette="Raccordement" valeur="Conforme" />}
        {ombres && (
          <Valeur etiquette="Ombres proches" valeur={`− ${formatPercent(ombres.perte_pct, { decimals: 1 })}`} />
        )}
      </div>
      <p className="cal-res-sourdine" data-testid="acal700-note">
        Les années basses (9 fois sur 10 au-dessus) et l'indice de performance s'affichent dès que le résultat est complet.
      </p>
    </section>
  )
}

function Progression({ aRenseigner }) {
  const faites = aRenseigner?.etapes_comptees
  const sur = aRenseigner?.etapes_a_compter
  if (typeof faites !== 'number' || typeof sur !== 'number' || sur <= 0) return null
  const largeur = Math.max(0, Math.min(100, (faites / sur) * 100))
  return (
    <div className="cal-resinc-progres" data-testid="acal700-progression">
      <div className="cal-resinc-piste" aria-hidden="true"><span style={{ width: `${largeur}%` }} /></div>
      <span>{`${faites} ${faites > 1 ? 'étapes' : 'étape'} sur ${sur}`}</span>
    </div>
  )
}

export default function ResultatIncomplet({ calepinageId, data, parcours = null }) {
  const total = data?.production?.total
  if (!estIncomplet(total)) return null
  const aRenseigner = data?.cascade?.a_renseigner
  const lignes = Array.isArray(aRenseigner?.lignes) ? aRenseigner.lignes : []
  if (lignes.length === 0) return <BandeauBorneHaute total={total} />
  return (
    <div className="cal-resinc" data-testid="acal700-incomplet">
      <div className="cal-resinc-haut">
        <section className="cal-res-tuile cal-resinc-plafond">
          <p className="cal-res-tuile-label m-0" data-testid="acal700-etiquette">
            Production la première année · au plus
          </p>
          <p className="cal-res-tuile-valeur m-0" data-testid="acal700-valeur">{kwh(total.p50_kwh)}</p>
          <p className="cal-resinc-phrase" data-testid="acal700-plafond">
            {`C'est un plafond : ${phraseDuCompte(aRenseigner, lignes.length)} Le chiffre réel sera plus bas.`}
          </p>
          <Progression aRenseigner={aRenseigner} />
        </section>
        <section className="cal-res-carte" data-testid="acal700-liste">
          <h1 className="cal-res-titre">Pour un résultat complet</h1>
          <ol className="cal-resinc-liste">
            {lignes.map((ligne, i) => (
              <li key={`${ligne.etape}-${ligne.cle}`} className="cal-resinc-ligne" data-testid="acal700-ligne">
                <span className="cal-resinc-rang" aria-hidden="true">{i + 1}</span>
                <span className="cal-resinc-texte">
                  <span className="cal-resinc-nom" title={nomDePerte(ligne.etape, ligne.libelle).technique || undefined}>
                    {nomDePerte(ligne.etape, ligne.libelle).nom}
                  </span>
                  {RAISON[ligne.nature] && <span className="cal-resinc-raison">{RAISON[ligne.nature]}</span>}
                </span>
                <Link to={lienManque(calepinageId, ligne.cible)} className="cal-resinc-bouton"
                  data-testid="acal700-renseigner">
                  Renseigner
                </Link>
              </li>
            ))}
          </ol>
          <div className="cal-resinc-demarrage" data-testid="acal700-demarrage">
            <span className="cal-resinc-demarrage-texte">
              <strong>Démarrage rapide</strong>
              <span>
                {`Remplir ${lignes.length > 1 ? `les ${lignes.length} réglages vides` : 'le réglage vide'} avec des valeurs publiées, chacune avec sa source. Vous pourrez les remplacer par vos mesures.`}
              </span>
            </span>
            <Link to="/calepinage/reglages" className="cal-res-cta" style={{ minHeight: 44, fontSize: 14, padding: '0 16px' }}
              data-testid="acal700-lien-reglages">
              Voir les valeurs
            </Link>
          </div>
        </section>
      </div>
      <CeQuiEstSur data={data} parcours={parcours} />
    </div>
  )
}
