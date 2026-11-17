import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import LigneTache from '../../features/taches/ui/LigneTache'
import { jourLong } from '../../features/taches/lib/textes'

/* TCH43/TCH44 — page « Aujourd'hui » (route /taches/aujourdhui, `/taches` y mène), montée
   dans la coquille. La liste est VIDE tant que l'écran n'est pas branché sur
   `GET aujourdhui/` (TCH76) ; les lignes sont déjà celles des maquettes (LigneTache). */
const TACHES_DU_JOUR = []

export default function Aujourdhui() {
  return (
    <CoquilleTaches ecran="aujourdhui" titre="Aujourd'hui" sousTitre={jourLong()}>
      <section className="section" aria-label="Aujourd'hui">
        <div className="liste" role="list">
          {TACHES_DU_JOUR.map((item) => <LigneTache key={`${item.type}:${item.id}`} item={item} />)}
        </div>
      </section>
    </CoquilleTaches>
  )
}
