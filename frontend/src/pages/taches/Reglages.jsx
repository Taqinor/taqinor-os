import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'

/* TCH43 — page vide « Réglages » (routes /taches/reglages et /taches/reglages/:rubrique,
   rubriques : notifications, iphone, vie-privee, suggestions, donnees, avance), montée dans la coquille. */
export default function Reglages() {
  return <CoquilleTaches ecran="reglages" titre="Réglages" />
}
