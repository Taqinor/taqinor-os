import { ArrowRight } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { formatNumber } from '../../../lib/format'
import { PARAM_ONGLET } from '../atelier/onglets'
import { estIncomplet } from './BandeauProvenanceProduction.helpers'
import { libelleAnneeBasse } from './LigneSurLaDuree.helpers'

/* LE PIED de l'étape Résultats (maquette Resultats.dc.html) : « Année basse (9 fois sur 10 au-dessus) :
   … · Dans N ans : … » et le bouton doré de l'étape suivante. La phrase n'est faite que de valeurs
   SERVIES (`production.total.p90_kwh`, dernière ligne de `production.projection`) : un segment dont la
   valeur n'est pas servie (ou pas publiée : résultat incomplet) est omis, jamais « non calculée »
   ni un tiret ; sans aucun segment, pas de phrase. Le bouton est l'action de l'étape reçue du
   shell (`action` = {libelle, onClick}) ; sans elle, il ouvre l'étape Documents par l'URL, comme
   le rail le fait. */
const servi = (v) => typeof v === 'number' && Number.isFinite(v)
const enKwh = (v) => `${formatNumber(v, { decimals: 0 })} kWh`

function phraseSurLaDuree(production, incertitude) {
  const total = production?.total
  const segments = []
  if (!estIncomplet(total) && servi(total?.p90_kwh)) {
    segments.push(`${libelleAnneeBasse(incertitude)} : ${enKwh(total.p90_kwh)}`)
  }
  const projection = Array.isArray(production?.projection) ? production.projection : []
  const derniere = projection[projection.length - 1]
  if (!production?.duree_de_vie?.motif_omission && projection.length >= 2 && servi(derniere?.p50_kwh)) {
    segments.push(`Dans ${derniere.annee} ans : ${enKwh(derniere.p50_kwh)}`)
  }
  return segments.join(' · ')
}

export default function PiedResultats({ production, incertitude = null, action = null }) {
  const [parametres, setParametres] = useSearchParams()
  const phrase = phraseSurLaDuree(production, incertitude)
  const versDocuments = () => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, 'documents')
    setParametres(suivants)
  }
  const libelle = action?.libelle || 'Préparer les documents'
  const contenu = (<>{libelle}<ArrowRight size={18} aria-hidden="true" /></>)
  return (
    <div className="cal-res-pied" data-testid="cal-resultats-pied">
      <span className="cal-res-pied-ligne">{phrase}</span>
      <button type="button" className="cal-res-cta" onClick={action?.onClick ?? versDocuments}>{contenu}</button>
    </div>
  )
}
