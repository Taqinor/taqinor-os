import { Link } from 'react-router-dom'

/* ACAL1268 (D-ACAL-66 = outil_pose) — l'atelier d'un lead de POMPAGE est un outil de pose : le renvoi clair vers le devis
   agricole, là où le pompage se chiffre. `phrase` dit ce que l'écran ne montre pas. Le lien ouvre le devis agricole dont la
   pose reprend les panneaux (servi : `cible.devis_agricole`) ; sans lui, l'écran de création — et le libellé le dit.
   Rien n'est calculé ici. D-ACAL-106 — à qui ne lit pas les devis, le serveur sert `{id: null, reference: null}` : le
   devis existe, il n'est ni nommé ni lié (jamais « Créer » quand il existe). */
const PHRASE_DEVIS_AGRICOLE_NON_NOMME = 'Un devis agricole du lead porte ce champ (accès réservé aux rôles du module Ventes).'

export default function OutilPosePompage({ contexte, phrase }) {
  const lead = contexte?.calepinage?.lead ?? null
  const devis = contexte?.cible?.devis_agricole ?? null
  const ouvrir = devis?.id != null
  const creation = lead != null ? `/ventes/devis/nouveau?lead=${lead}` : '/ventes/devis'
  return (
    <section className="cal-res-carte flex flex-col gap-1" data-zone="pompage-outil-pose" role="status">
      <p className="m-0">{phrase}</p>
      <p className="cal-res-sourdine m-0">Le pompage se chiffre depuis le devis agricole.</p>
      {devis != null && !ouvrir ? <p className="cal-res-sourdine m-0">{PHRASE_DEVIS_AGRICOLE_NON_NOMME}</p> : (
        <Link to={ouvrir ? `/ventes/devis?devis=${devis.id}` : creation} className="cal-res-lien"
          style={{ alignSelf: 'flex-start' }}>
          {ouvrir ? `Ouvrir le devis agricole${devis.reference ? ` ${devis.reference}` : ''}` : 'Créer le devis agricole'}
        </Link>
      )}
    </section>
  )
}
