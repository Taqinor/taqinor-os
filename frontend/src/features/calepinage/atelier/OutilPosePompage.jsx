import { Link } from 'react-router-dom'

/* ACAL1268 (D-ACAL-66 = outil_pose) — l'atelier d'un lead de POMPAGE est un outil de pose : le renvoi clair vers le devis
   agricole, là où le pompage se chiffre. `phrase` dit ce que l'étape ne montre pas ; le lien ouvre l'écran devis du lead
   (le même « devis agricole » que nomme le refus du serveur). Rien n'est calculé ici. */
export default function OutilPosePompage({ contexte, phrase }) {
  const lead = contexte?.calepinage?.lead ?? null
  return (
    <section className="cal-res-carte flex flex-col gap-1" data-zone="pompage-outil-pose" role="status">
      <p className="m-0">{phrase}</p>
      <p className="cal-res-sourdine m-0">Le pompage se chiffre depuis le devis agricole.</p>
      <Link to={lead != null ? `/ventes/devis/nouveau?lead=${lead}` : '/ventes/devis'} className="cal-res-lien"
        style={{ alignSelf: 'flex-start' }}>
        Ouvrir le devis agricole
      </Link>
    </section>
  )
}
