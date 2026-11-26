import { Link, useLocation } from 'react-router-dom'
import { Icone } from '../atelier/coque/primitives'
import { DEPUIS_RELEVE } from './vueClient.helpers'

/* ============================================================================
   « MONTRER AU CLIENT » — LES PIÈCES PARTAGÉES de la vue 3D (l'atelier en mode
   présentation, `HabillageClient`) et de son repli 2D (`VueClient2D`).
   CHIFFRES : document enregistré + résultat publié seulement (vueClient.helpers) ;
   jamais un montant. PARTAGE : le lien client est celui de la proposition du DEVIS,
   préparé depuis la fiche du lead (niveau et sections choisis là, L-SECT) — le bouton
   dit pourquoi il est désactivé ici ; aucune porte publique neuve (D-ACAL-69).
   Deux dispositions, mêmes pièces : le téléphone (390 px, feuille du bas) et le BUREAU
   (≥ 1024 px, maquette Presentation : scène plein écran, carte héros à droite, barre du soleil en bas).
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
      aria-label={`Le toit vu de dessus : ${plan.pans.length} pan${plan.pans.length > 1 ? 's' : ''}${plan.sansModules ? '' : `, ${plan.modules.length} panneau${plan.modules.length > 1 ? 'x' : ''} dessiné${plan.modules.length > 1 ? 's' : ''}`}`}>
      {plan.pans.map((pan, i) => <polygon key={`p${i}`} className="cal-client-pan" points={pan.map(pt).join(' ')} />)}
      {plan.modules.map((q, i) => <polygon key={`m${i}`} className="cal-client-module" points={q.map(pt).join(' ')} />)}
    </svg>
  )
}

/** ACAL1837 — l'attente de la 3D, présentable : un ciel et la silhouette d'une maison (aucune donnée, aucun plan technique).
 *  Le plan dessus reste pour l'échec de la 3D et pour un navigateur sans WebGL. */
export function AttenteScene() {
  return (
    <div className="cal-client-attente" data-testid="client-attente" aria-hidden="true">
      <svg viewBox="0 0 320 200" preserveAspectRatio="xMidYMax meet" focusable="false">
        <path className="cal-client-attente-colline" d="M0 200V164c70-14 140-18 210-8s80 2 110-4v48z" />
        <path className="cal-client-attente-maison" d="M88 176V116h144v60z" />
        <path className="cal-client-attente-toit" d="M72 118L160 62l88 56z" />
      </svg>
    </div>
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

/** ACAL1353 — le moteur du toit (chargé à part) n'a pas pu se charger : les panneaux ne sont pas dessinés et la production
 *  n'est pas montrée. Dit en mots simples ; « Réessayer » RECHARGE LA PAGE (un nouvel `import()` peut retomber sur l'échec
 *  gardé en cache par le navigateur). */
export function AvisMoteurEchec() {
  return (
    <p className="cal-client-repli-retard" role="status" data-testid="cal-client-moteur-echec">
      {'Les panneaux n’ont pas pu s’afficher. '}
      <button type="button" className="cal-client-repli-reessayer" onClick={() => window.location.reload()}>Réessayer</button>
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

/** La puce du projet (pictogramme maison sur carré bleu nuit ; titre ; ville · pan), en haut à gauche de la scène. */
export function PuceProjet({ titre, sousTitre }) {
  if (!titre && !sousTitre) return null
  return (
    <div className="cal-client-puce" data-testid="client-projet">
      <span className="cal-client-puce-icone" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round"><path d="M3 11.5L12 4l9 7.5" /><path d="M5.5 10v9.5h13V10" /></svg>
      </span>
      <span className="cal-client-puce-texte">
        {titre && <span className="cal-client-puce-titre">{titre}</span>}
        {sousTitre && <span className="cal-client-puce-ligne">{sousTitre}</span>}
      </span>
    </div>
  )
}

/** La mention sous les chiffres, seulement avec ses données servies (jamais un montant). */
function Mentions({ tuiles, ville }) {
  const miseAJour = tuiles.find((t) => t.cle === 'miseajour')
  return (
    <>
      {miseAJour && <span className="cal-client-mention" data-testid="client-mention-miseajour">{miseAJour.libelle}</span>}
      {tuiles.some((t) => t.cle === 'kwh' && !t.nature) && (
        <span className="cal-client-mention">
          {`Estimation pour une année moyenne${ville ? ` à ${ville}` : ''}. Les montants figurent dans le devis.`}
        </span>
      )}
      {tuiles.some((t) => t.nature === 'pertes') && (
        <span className="cal-client-mention" data-testid="client-mention-pertes">
          {'Estimation : pertes par défaut. Les montants figurent dans le devis.'}
        </span>
      )}
    </>
  )
}

/** Un chiffre de la carte bleu nuit : la valeur, son libellé (le « % » est une unité, plus petite). */
function Chiffre({ tuile }) {
  const pourcent = /^(.*\S)\s%$/.exec(tuile.valeur)
  const [nombre, unite] = pourcent ? [pourcent[1], '%'] : [tuile.valeur, null]
  return (
    <div className="cal-client-marine-chiffre" data-testid={`client-tuile-${tuile.cle}`}>
      <span className="cal-client-marine-valeur">{nombre}{unite && <small>{` ${unite}`}</small>}</span>
      <span className="cal-client-marine-libelle">{tuile.libelle}</span>
    </div>
  )
}

/**
 * ACAL1837 — LA CARTE BLEU NUIT (maquette TelephoneClient : 358 × 178 r22) : la production en grand (46 px ; 72 px au
 * bureau) avec sa pilule « Estimation », puis les autres chiffres SERVIS (panneaux, couverture ou puissance) ; une
 * donnée non servie est omise, jamais fabriquée. Au bureau, le sur-titre et les mentions entrent dans la carte.
 */
export function TuilesClient({ tuiles, ville, bureau = false }) {
  const kwh = tuiles.find((t) => t.cle === 'kwh') ?? null
  const autres = tuiles.filter((t) => t.cle !== 'kwh' && t.cle !== 'miseajour')
  return (
    <>
      {tuiles.length > 0 && (
        <div className="cal-client-marine-bloc">
          <section className="cal-client-nuit" data-testid="client-tuiles" aria-label="Votre installation en trois chiffres">
            {kwh && (
              <div className="cal-client-marine-kwh" data-testid="client-tuile-kwh">
                {bureau && <span className="cal-client-marine-sur">Votre toit produirait</span>}
                <div className="cal-client-marine-tete">
                  <span className="cal-client-marine-gros">{kwh.valeur}</span>
                  <span className="cal-client-pilule"><i aria-hidden="true" />Estimation</span>
                </div>
                <span className="cal-client-marine-unite">{kwh.libelle.split(' · ')[0]}</span>
              </div>
            )}
            {kwh && autres.length > 0 && <hr className="cal-client-marine-filet" />}
            {autres.length > 0 && (
              <div className="cal-client-marine-grille">
                {autres.map((t) => <Chiffre key={t.cle} tuile={t} />)}
              </div>
            )}
            {bureau && <div className="cal-client-marine-mentions"><Mentions tuiles={tuiles} ville={ville} /></div>}
          </section>
          {!bureau && <Mentions tuiles={tuiles} ville={ville} />}
        </div>
      )}
      <p id="client-lien-raison" className="cal-client-mention cal-client-raison" data-testid="client-lien-raison">{RAISON_LIEN}</p>
    </>
  )
}

/** Le pied : « Retour » là d'où l'on vient (T4-X8-007 — du relevé : « Retour au relevé » ; de l'atelier ou d'une adresse
    ouverte directement : « Retour à l'atelier », au téléphone comme au bureau) + « Envoyer le lien » doré, désactivé avec
    sa raison. */
export function PiedClient({ id }) {
  const depuisReleve = useLocation().state?.depuis === DEPUIS_RELEVE.depuis
  return (
    <footer className="cal-tel-pied" data-vue-client="">
      {!depuisReleve ? (
        <Link to={`/calepinage/${id}`} className="cal-tel-pied-secondaire" data-testid="client-retour-atelier">
          <Icone nom="retour" taille={18} epaisseur={2} />
          {'Retour à l’atelier'}
        </Link>
      ) : (
        <Link to={`/calepinage/${id}/releve`} className="cal-tel-pied-secondaire" data-testid="client-retour-releve">
          <Icone nom="retour" taille={18} epaisseur={2} />
          Retour au relevé
        </Link>
      )}
      <button type="button" className="cal-tel-pied-or" disabled aria-describedby="client-lien-raison"
        data-testid="client-envoyer-lien">
        <Icone nom="partager" taille={18} epaisseur={2} />
        Envoyer le lien
      </button>
    </footer>
  )
}
