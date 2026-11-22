import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber } from '../../../lib/format'
import '../../../styles/calepinage/53-etape-electrique.css'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, ErrorBoundary, Spinner } from '../../../ui'
import { SurCarte } from '../atelier/coque/emplacements'
import { CarteFlottante, Icone, Indicateur } from '../atelier/coque/primitives'
import { PARAM_ONGLET, ongletParCle } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'
import PretAEnvoyer from '../commun/PretAEnvoyer'
import AffectationChaines, { BarreRaccordement } from '../plan/AffectationChaines'
import ConfigurationsOnduleur from './ConfigurationsOnduleur'
import { refusParChamp } from './entreeElectrique'
import { ROLES } from './MaterielElectrique.helpers'
import { casesPastille, chainesServies, libelleChaine } from './resumeRaccordement'

/* ============================================================================
   ACAL1299 / ACAL1300 — L'ÉTAPE « ÉLECTRIQUE » DE LA COQUE (maquette `Electrique.dc.html`).
   ----------------------------------------------------------------------------
   Panneau de droite (sous « Étape 3 sur 5 · Le raccordement », rendu par la coque) : la carte de
   l'onduleur (le VRAI choix : `entree-electrique/`, comme l'onglet Matériel), « Comparer avec N autres
   onduleurs » (`ConfigurationsOnduleur`), « Prêt à envoyer ? » COURT filtré sur l'électrique, la carte
   « Schéma électrique — Voir » (ouvre le sous-écran `?onglet=schema`), puis « Réglages avancés » qui
   range les huit sections d'avant (rien n'est retiré). Le bouton « Voir les résultats → » est le pied
   par défaut de la coque (`action`). Sur la carte : la pastille « Chaînes | Onduleur | Câble côté
   panneaux », la légende des chaînes et la barre « Raccorder automatiquement / Modifier une chaîne ».
   Tout chiffre est LU (`resultat/`, `configurations-onduleur/`) ; une case non servie est omise.
   ========================================================================== */

const SECTIONS_ELECTRIQUES = [
  { cle: 'equipements-electriques', libelle: 'Équipements' },
  { cle: 'verdict-electrique', libelle: 'Verdict' },
  { cle: 'cheminement-cables', libelle: 'Cheminement & câbles' },
  { cle: 'raccordement', libelle: 'Raccordement' },
  { cle: 'materiel-electrique', libelle: 'Matériel' },
  { cle: 'saisies-electriques', libelle: 'Saisies' },
  { cle: 'decisions-electriques', libelle: 'Décisions' },
  { cle: 'controle-chaine', libelle: 'Contrôle rapide d’une chaîne' }, // ACAL628
]
// L'onglet qui OUVRE l'étape (parcoursGuide › ECRANS_ETAPE.electrique.ouverture) : il ne déplie rien.
const OUVERTURE = 'verdict-electrique'
const nb = (v, decimals = 0) => formatNumber(v, { decimals, locale: 'fr' })

/* Les props du rail (calepinageId, builderApi, onRecharger, lectureSeule, documentVivant) sont
   relayées TELLES QUELLES à chaque section avancée. */
function Section({ cle, libelle, propsDuRail }) {
  const Composant = ongletParCle(cle)?.composant
  return (
    <AccordionItem value={cle} data-testid={`cal-electrique-section-${cle}`}>
      <AccordionTrigger>{libelle}</AccordionTrigger>
      <AccordionContent>
        <ErrorBoundary fallback={<p role="alert" className="text-sm text-destructive">{`La section « ${libelle} » n’a pas pu s’afficher.`}</p>}>
          <Suspense fallback={<Spinner />}>
            {Composant && <Composant {...propsDuRail} />}
          </Suspense>
        </ErrorBoundary>
      </AccordionContent>
    </AccordionItem>
  )
}

/** La ligne sous le nom de l'onduleur : puissance et entrées de la configuration RETENUE servie,
    nombre de panneaux du chaînage servi — chaque morceau seulement s'il est servi. */
function ligneOnduleur(retenue, resultat) {
  const kw = retenue?.puissance_ac_totale_kw
  const entrees = retenue?.mppt_disponibles
  const panneaux = resultat?.electrique?.chainage?.modules
  return [
    typeof kw === 'number' ? `${nb(kw, Number.isInteger(kw) ? 0 : 1)} kW` : null,
    typeof entrees === 'number' ? `${entrees} entrée${entrees > 1 ? 's' : ''}` : null,
    typeof panneaux === 'number' && panneaux > 0 ? `pour ${panneaux} panneau${panneaux > 1 ? 'x' : ''}` : null,
  ].filter(Boolean).join(' · ')
}

function CarteOnduleur({ id, entree, configs, resultat, lectureSeule, onApplique }) {
  const [comparer, setComparer] = useState(false)
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)
  const choisi = entree?.materiel?.onduleur ?? null
  const candidats = entree?.candidats?.onduleurs ?? []
  const designations = Object.fromEntries(ROLES.map((r) => [
    r.champ, entree?.materiel?.[r.role]?.produit_id ?? entree?.entree?.[r.champ] ?? null]))
  const configurations = configs?.configurations ?? []
  const retenue = configurations.find((c) => c.role === 'retenue') ?? null
  const autres = configurations.filter((c) => c.role !== 'retenue').length
  const ligne = ligneOnduleur(retenue, resultat)

  // Choisir = le geste de l'onglet Matériel / « Appliquer » de la comparaison : les trois désignations
  // de l'entrée, `onduleur_produit` remplacé ; l'écran relit ensuite ce que le serveur a stocké.
  const choisir = (evenement) => {
    const produit = evenement.target.value === '' ? null : Number(evenement.target.value)
    setEnCours(true)
    setRefus(null)
    calepinageApi.calepinages.enregistrerEntreeElectrique(id, { ...designations, onduleur_produit: produit })
      .then(() => onApplique())
      .catch((err) => {
        const parChamp = refusParChamp(err?.response?.data)
        setRefus(parChamp.onduleur_produit || Object.values(parChamp)[0]
          || 'Onduleur non enregistré : le serveur a refusé ce choix.')
      })
      .finally(() => setEnCours(false))
  }

  return (
    <section className="cel-onduleur" data-testid="cal-elec-onduleur">
      <label htmlFor="cel-onduleur-choix" className="cel-libelle">Onduleur</label>
      <div className="cel-choix" data-vide={choisi ? '0' : '1'}>
        <span className="cel-choix-texte" aria-hidden="true">
          <span className="cel-choix-nom">{choisi?.designation || retenue?.libelle || 'Onduleur à désigner'}</span>
          {ligne && <span className="cel-choix-ligne">{ligne}</span>}
        </span>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="cel-choix-chevron">
          <path d="M6 9l6 6 6-6" />
        </svg>
        <select id="cel-onduleur-choix" value={choisi?.produit_id ?? ''} onChange={choisir}
          disabled={lectureSeule || enCours || candidats.length === 0}>
          {!choisi && <option value="">— à désigner —</option>}
          {candidats.map((c) => (
            <option key={c.id} value={c.id} disabled={c.fiche_complete === false}>
              {c.fiche_complete === false
                ? `${c.libelle} — fiche incomplète : ${(c.champs_manquants ?? []).join(', ')}`
                : `${c.libelle}${c.marque ? ` (${c.marque})` : ''}`}
            </option>
          ))}
        </select>
      </div>
      {refus && <p role="alert" className="cel-refus">{refus}</p>}
      {autres > 0 && (
        <button type="button" className="cel-lien" aria-expanded={comparer} onClick={() => setComparer((o) => !o)}>
          {`Comparer avec ${autres} autre${autres > 1 ? 's' : ''} onduleur${autres > 1 ? 's' : ''}`}
        </button>
      )}
      {comparer && (
        <ConfigurationsOnduleur calepinageId={id} designations={designations} lectureSeule={lectureSeule}
          ouvertDOffice donneesInitiales={configs} apresApplication={onApplique} />
      )}
    </section>
  )
}

/** Sur la carte : la pastille du haut, la légende des chaînes (seulement si le constructeur les
    colore), la barre d'actions du bas. */
function CalquesCarte({ id, resultat, couleursDessinees, lectureSeule, onRaccorde, onModifier }) {
  const cases = casesPastille(resultat)
  const chaines = couleursDessinees ? chainesServies(resultat).filter((c) => c.couleur) : []
  const manuelles = (resultat?.electrique?.affectation ?? []).some((l) => l?.source === 'affectation manuelle')
  return (
    <SurCarte>
      {cases.length > 0 && (
        <CarteFlottante className="cel-pastille" data-testid="cal-sur-carte-resume">
          {cases.map((c, i) => (
            <div key={c.libelle} className="cel-pastille-case">
              {i > 0 && <span className="cel-pastille-filet" aria-hidden="true" />}
              <Indicateur libelle={c.libelle} valeur={c.valeur} />
            </div>
          ))}
        </CarteFlottante>
      )}
      {chaines.length > 0 && (
        <CarteFlottante className="cel-legende" role="group" aria-label="Couleurs des chaînes">
          {chaines.map((c) => (
            <span key={c.chaine} className="cel-legende-ligne">
              {/* La couleur est SERVIE (`couleur_chaine`) : la même que la 3D et le plan de câblage. */}
              <span className="cel-legende-puce" style={{ background: c.couleur }} />
              {libelleChaine(c)}
            </span>
          ))}
        </CarteFlottante>
      )}
      <BarreRaccordement calepinageId={id} manuelles={manuelles} lectureSeule={lectureSeule}
        onRaccorde={onRaccorde} onModifier={onModifier} />
    </SurCarte>
  )
}

export default function EtapeElectrique(props) {
  // Reçus de la coque, non relayés aux sections (le pied « Voir les résultats → » est celui de la coque).
  const {
    parcours: _parcours, action: _action, enregistreLe: _enregistreLe, actionDevis: _actionDevis,
    ouvert = null, ...propsDuRail
  } = props
  const id = propsDuRail.calepinageId
  const { builderApi = null, lectureSeule = false } = propsDuRail
  const [parametres, setParametres] = useSearchParams()
  const [relecture, setRelecture] = useState(0)
  const [editeur, setEditeur] = useState(false)
  const relire = () => setRelecture((n) => n + 1)
  const cle = { id, relecture }
  const { data: resultat } = useResource((p) => calepinageApi.calepinages.resultat(p.id), cle, { select: (r) => r?.data ?? null })
  const { data: entree } = useResource((p) => calepinageApi.calepinages.entreeElectrique(p.id), cle, { select: (r) => r?.data ?? null })
  const { data: configs } = useResource((p) => calepinageApi.calepinages.configurationsOnduleur(p.id), cle, { select: (r) => r?.data ?? null })

  // Les couleurs de chaîne sont dessinées par le constructeur (`scene3d`, ACAL286) à partir de la table
  // SERVIE : l'étape la lui repousse à l'ouverture et après chaque raccordement (la carte d'ensoleillement
  // de l'étape Panneaux écrit le même canal).
  const peutColorer = typeof builderApi?.setAffectationChaines === 'function'
  const lignes = resultat?.electrique?.affectation
  useEffect(() => {
    if (peutColorer && Array.isArray(lignes)) builderApi.setAffectationChaines(lignes, 'chaine')
  }, [peutColorer, builderApi, lignes])

  const ouvrirSchema = () => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, 'schema')
    suivants.delete(PARAM_CHAMP)
    setParametres(suivants)
  }

  const demandee = ouvert !== OUVERTURE && SECTIONS_ELECTRIQUES.some((s) => s.cle === ouvert) ? ouvert : null
  const calques = (
    <CalquesCarte id={id} resultat={resultat} couleursDessinees={peutColorer} lectureSeule={lectureSeule}
      onRaccorde={relire} onModifier={() => setEditeur(true)} />
  )

  if (editeur) {
    return (
      <div data-testid="cal-etape-electrique-ecran" className="cel-ecran">
        {calques}
        <button type="button" className="cel-retour" onClick={() => { setEditeur(false); relire() }}>
          <Icone nom="retour" taille={18} epaisseur={2} />
          Raccordement
        </button>
        <AffectationChaines calepinageId={id} lectureSeule={lectureSeule} />
      </div>
    )
  }

  return (
    <div data-testid="cal-etape-electrique-ecran" className="cel-ecran">
      {calques}
      <CarteOnduleur id={id} entree={entree} configs={configs} resultat={resultat} lectureSeule={lectureSeule}
        onApplique={relire} />
      <PretAEnvoyer key={relecture} calepinageId={id} filtre="electrique" court testIdCompte="cal-electrique-synthese" />
      <section className="cel-schema" data-testid="cal-elec-schema-voir">
        <span className="cel-schema-texte">
          <span className="cel-schema-titre">Schéma électrique</span>
          <span className="cel-schema-detail">Dessiné tout seul à partir du raccordement</span>
        </span>
        <button type="button" className="cel-bouton-contour" onClick={ouvrirSchema}>Voir</button>
      </section>
      <Accordion type="multiple" className="cel-avances" defaultValue={demandee ? ['avances'] : []}>
        <AccordionItem value="avances" data-testid="cal-electrique-avances">
          <AccordionTrigger className="cel-avances-lien">Réglages avancés</AccordionTrigger>
          <AccordionContent>
            <Accordion type="multiple" defaultValue={demandee ? [demandee] : []}>
              {SECTIONS_ELECTRIQUES.map((s) => <Section key={s.cle} {...s} propsDuRail={propsDuRail} />)}
            </Accordion>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}
