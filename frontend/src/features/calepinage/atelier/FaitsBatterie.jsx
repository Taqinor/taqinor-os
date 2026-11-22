import { formatNumber } from '../../../lib/format'
import { Badge } from '../../../ui'
import useExpertParUrl from '../production/useExpertParUrl'

/* ============================================================================
   ACAL795 — EN TÊTE DE L'ONGLET BATTERIE (mode expert) : le garde-fou et les
   trois faits de la série, puis le mot du verdict.
   Tout est LU tel que servi sous `batterie.total` (`faits_serie` d'ACAL793,
   `verdict` / `motif_verdict` d'ACAL794, contrat `calepinage_simulation.json`) :
   aucun calcul ici, sinon la mise en pourcentage d'une part servie (0..1).
   Un fait absent se lit « non calculé » ; sans verdict, le motif servi
   remplace le mot, les faits restent. Trois lignes de texte, aucune courbe.
   ========================================================================== */

const MOTS = {
  adaptee: { libelle: 'Adaptée à votre consommation', ton: 'success' },
  trop_petite: { libelle: 'Trop petite', ton: 'warning' },
  trop_grande: { libelle: 'Trop grande', ton: 'warning' },
}

const connu = (v) => v !== null && v !== undefined && Number.isFinite(Number(v))
const entier = (v) => formatNumber(v, { decimals: 0 })
const part = (v) => `${formatNumber(Number(v) * 100, { decimals: 0 })} %`

function Mot({ verdict, motif }) {
  const mot = verdict ? MOTS[verdict.mot] : null
  if (!mot) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="acal795-sans-verdict">
        Pas de verdict : {motif || 'motif non publié'}
      </p>
    )
  }
  return <Badge tone={mot.ton} data-testid="acal795-mot" className="w-fit text-sm">{mot.libelle}</Badge>
}

export default function FaitsBatterie({ batterie }) {
  const expert = useExpertParUrl()
  const total = batterie?.total
  const faits = total?.faits_serie
  if (!expert || !faits) return null
  const sur = connu(faits.jours_total) ? ` sur ${entier(faits.jours_total)}` : ''
  return (
    <section className="flex flex-col gap-2" data-testid="acal795-faits" aria-label="Avant d’ajouter une batterie">
      <p className="text-base font-semibold" data-testid="acal795-garde-fou">
        {connu(faits.taux_autoconsommation_sans_batterie)
          ? `Votre production est déjà consommée à ${part(faits.taux_autoconsommation_sans_batterie)} sans batterie`
          : 'Part de la production déjà consommée sans batterie : non calculé'}
      </p>
      <ul className="space-y-1 text-sm">
        <li data-testid="acal795-pleine">
          {connu(faits.jours_pleine)
            ? `La batterie atteint 100 % ${entier(faits.jours_pleine)} jours${sur}`
            : 'Jours où la batterie atteint 100 % : non calculé'}
        </li>
        <li data-testid="acal795-vide">
          {connu(faits.nuits_au_plancher)
            ? `Elle est vide avant l’aube ${entier(faits.nuits_au_plancher)} nuits${sur}`
            : 'Nuits où elle est vide avant l’aube : non calculé'}
        </li>
        <li data-testid="acal795-surplus">
          {connu(faits.part_surplus_injecte)
            ? `${part(faits.part_surplus_injecte)} du surplus part encore sur le réseau`
            : 'Surplus qui part encore sur le réseau : non calculé'}
        </li>
      </ul>
      <Mot verdict={total.verdict} motif={total.motif_verdict} />
    </section>
  )
}
