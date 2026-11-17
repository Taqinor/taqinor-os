import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'

/* TCH43 — page vide « Supprimées récemment » (route /taches/supprimees), montée dans la coquille. */
export default function Supprimees() {
  return <CoquilleTaches ecran="supprimees" titre="Supprimées récemment" />
}
