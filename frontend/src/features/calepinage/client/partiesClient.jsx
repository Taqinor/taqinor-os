import { Link } from 'react-router-dom'
import { Icone } from '../atelier/coque/primitives'

/* ============================================================================
   « MONTRER AU CLIENT » — LES PIÈCES PARTAGÉES de la vue 3D (l'atelier en mode
   présentation, `HabillageClient`) et de son repli 2D (`VueClient2D`).
   CHIFFRES : document enregistré + résultat publié seulement (vueClient.helpers) ;
   jamais un montant. PARTAGE : le lien client est celui de la proposition du DEVIS,
   préparé depuis la fiche du lead (niveau et sections choisis là, L-SECT) — le bouton
   dit pourquoi il est désactivé ici ; aucune porte publique neuve (D-ACAL-69).
   ========================================================================== */

const RAISON_LIEN = 'Le lien se prépare depuis la fiche du lead, onglet Devis, « Envoyer au client » : '
  + 'le niveau et les sections du devis s’y choisissent.'

/** Le toit enregistré vu de dessus (pans + modules du document). */
export function PlanDessus({ plan }) {
  const marge = 2
  const larg = plan.maxX - plan.minX + 2 * marge
  const haut = plan.maxY - plan.minY + 2 * marge
  const pt = (p) => `${(p.x - plan.minX + marge).toFixed(2)},${(plan.maxY - p.y + marge).toFixed(2)}`
  return (
    <svg className="cal-client-plan" viewBox={`0 0 ${larg.toFixed(2)} ${haut.toFixed(2)}`}
      preserveAspectRatio="xMidYMid meet" role="img" data-testid="client-plan"
      aria-label={`Le toit vu de dessus : ${plan.pans.length} pan${plan.pans.length > 1 ? 's' : ''}, ${plan.modules.length} panneau${plan.modules.length > 1 ? 'x' : ''} dessiné${plan.modules.length > 1 ? 's' : ''}`}>
      {plan.pans.map((pan, i) => <polygon key={`p${i}`} className="cal-client-pan" points={pan.map(pt).join(' ')} />)}
      {plan.modules.map((q, i) => <polygon key={`m${i}`} className="cal-client-module" points={q.map(pt).join(' ')} />)}
    </svg>
  )
}

/** La flèche circulaire des maquettes (« tourner autour », « voir la 3D »). */
export function IconeTourner() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 11-3-6.7" /><path d="M21 4v5h-5" /></svg>
  )
}

/** La 3D n'a pas démarré (atelier en échec, chunk du constructeur introuvable) : dit sur la scène, avec « Réessayer »
 *  (relire la page : des GET seulement). Le toit enregistré dessiné de dessus reste dessous. */
export function AvisEchec3D({ onReessayer }) {
  return (
    <p className="cal-client-repli-retard" role="status" data-testid="client-3d-retard">
      {'La vue 3D n’a pas pu démarrer. '}
      <button type="button" className="cal-client-repli-reessayer" onClick={onReessayer}>Réessayer</button>
    </p>
  )
}

/** J1 — pendant le démarrage de la 3D : dit AU CLIENT, en mots simples (aucun « atelier »). */
export function PastilleAttente() {
  return (
    <span className="cal-client-pastille" role="status" data-testid="client-voir-3d">
      <IconeTourner />
      La vue 3D se prépare…
    </span>
  )
}

/** La puce du projet (titre ; ville · pan), en haut à gauche de la scène. */
export function PuceProjet({ titre, sousTitre }) {
  if (!titre && !sousTitre) return null
  return (
    <div className="cal-client-puce" data-testid="client-projet">
      {titre && <span className="cal-client-puce-titre">{titre}</span>}
      {sousTitre && <span className="cal-client-puce-ligne">{sousTitre}</span>}
    </div>
  )
}

/** Les trois tuiles (médiane marine) et la mention, seulement avec leurs données servies. */
export function TuilesClient({ tuiles, ville }) {
  return (
    <>
      {tuiles.length > 0 && (
        <div className={`cal-client-tuiles cal-client-tuiles-${tuiles.length}`} data-testid="client-tuiles">
          {tuiles.map((t) => (
            <div key={t.cle} className={t.marine ? 'cal-client-tuile cal-client-tuile-marine' : 'cal-client-tuile'}
              data-testid={`client-tuile-${t.cle}`}>
              <span className="cal-client-tuile-valeur">{t.valeur}</span>
              <span className="cal-client-tuile-libelle">{t.libelle}</span>
            </div>
          ))}
        </div>
      )}
      {tuiles.some((t) => t.cle === 'kwh' && !t.nature) && (
        <span className="cal-client-mention">
          {`Estimation pour une année moyenne${ville ? ` à ${ville}` : ''}. Les montants figurent dans le devis.`}
        </span>
      )}
      {tuiles.some((t) => t.nature === 'estimation') && (
        <span className="cal-client-mention" data-testid="client-mention-estimation">
          {'Estimation de la pose, avant le calcul complet. Les montants figurent dans le devis.'}
        </span>
      )}
      <p id="client-lien-raison" className="cal-client-mention" data-testid="client-lien-raison">{RAISON_LIEN}</p>
    </>
  )
}

/** Le pied : « Retour au relevé » + « Envoyer le lien » doré, désactivé avec sa raison. */
export function PiedClient({ id }) {
  return (
    <footer className="cal-tel-pied" data-vue-client="">
      <Link to={`/calepinage/${id}/releve`} className="cal-tel-pied-secondaire" data-testid="client-retour-releve">Retour au relevé</Link>
      <button type="button" className="cal-tel-pied-or" disabled aria-describedby="client-lien-raison"
        data-testid="client-envoyer-lien">
        <Icone nom="partager" taille={18} epaisseur={2} />
        Envoyer le lien
      </button>
    </footer>
  )
}
