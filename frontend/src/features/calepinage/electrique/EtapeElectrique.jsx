import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import useResource from '../../../hooks/useResource'
import { formatNumber } from '../../../lib/format'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, ErrorBoundary, Spinner } from '../../../ui'
import { SurCarte } from '../atelier/coque/emplacements'
import { CarteFlottante, Icone, Indicateur } from '../atelier/coque/primitives'
import { PARAM_ONGLET, ongletParCle } from '../atelier/onglets'
import { PARAM_CHAMP } from '../atelier/ouvrirChamp'
import PretAEnvoyer from '../commun/PretAEnvoyer'
import AffectationChaines, { BarreRaccordement } from '../plan/AffectationChaines'
import ConfigurationsOnduleur from './ConfigurationsOnduleur'
import DevisRetenu from './DevisRetenu'
import { refusParChamp } from './entreeElectrique'
import { ROLES } from './MaterielElectrique.helpers'
import { casesPastille, chainesServies, libelleChaine } from './resumeRaccordement'
import { totalPose } from '../surfacePose'

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
    typeof panneaux === 'number' && panneaux > 0 ? `proposé pour ${panneaux} panneau${panneaux > 1 ? 'x' : ''}` : null,
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
      {/* ACAL1952 — le devis dont vient l'onduleur, nommé ici : « Repris du devis DEV-… (option …) », avec l'écart d'une saisie contraire. */}
      {entree?.devis_retenu && (
        <DevisRetenu retenu={entree.devis_retenu} testId="cal-elec-devis-retenu" className="cel-devis-retenu" classeEcart="cel-devis-ecart" />
      )}
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

/* T4-U4-018 — le raccordement (serveur : `services/electrique.py::conception_du_calepinage`, qui ne lit que les pans du
   document) ne câble ni les champs au sol ni les ombrières (`poseSurfaces[]`), et ce plan ne dessine que les pans : on le
   DIT, avec le nom et le nombre de modules de chaque surface, au lieu de laisser croire qu'ils sont raccordés. */
const nomsSurfaces = (surfaces) => surfaces
  .map((s) => `${s.libelle} (${nb(s.modules)} module${s.modules > 1 ? 's' : ''})`).join(' et ')
function phraseSurfacesNonRaccordees(surfaces) {
  if (!surfaces.length) return null
  return `${nomsSurfaces(surfaces)} : pas encore raccordé${surfaces.length > 1 ? 's' : ''}. Le raccordement automatique `
    + 'ne câble aujourd’hui que les panneaux posés sur les pans de toit, et ce plan ne dessine que les pans.'
}
const motifSansToit = (pose) => (pose && pose.toit.panneaux === 0 && pose.surfaces.length > 0
  ? `Aucun panneau de toit à raccorder : ${nomsSurfaces(pose.surfaces)} ne se raccorde${pose.surfaces.length > 1 ? 'nt' : ''} pas encore automatiquement.`
  : null)

/** Sur la carte : la pastille du haut, la légende des chaînes (seulement si le constructeur les
    colore), la barre d'actions du bas. */
function CalquesCarte({ id, resultat, couleursDessinees, lectureSeule, onRaccorde, onModifier, pose = null }) {
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
        onRaccorde={onRaccorde} onModifier={onModifier} motifSansChaine={motifSansToit(pose)} />
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
  // T4-U4-018 — la pose du document (pans + surfaces), relue à l'ouverture et après chaque raccordement.
  const pose = useMemo(() => {
    try { return totalPose(builderApi?.serializeLayout?.() ?? null) } catch { return null }
  }, [builderApi, relecture]) // eslint-disable-line react-hooks/exhaustive-deps -- `relecture` : relire le document
  const phraseSurfaces = phraseSurfacesNonRaccordees(pose?.surfaces ?? [])
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
  /* T4-U4-007 — « Régler » mène au point : la section demandée (par l'URL, ou par « Régler » sur « Dossier électrique »
     dont la cible est l'onglet d'OUVERTURE, que l'URL ne peut pas redemander) est dépliée sous « Réglages avancés »,
     amenée à l'écran et reçoit le focus — avant, elle s'ouvrait sous le pli, ou pas du tout. */
  const ecranRef = useRef(null)
  const [avances, setAvances] = useState(demandee ? ['avances'] : [])
  const [sections, setSections] = useState(demandee ? [demandee] : [])
  const [cibleFocus, setCibleFocus] = useState(demandee ? { cle: demandee, n: 0 } : null)
  useEffect(() => {
    if (!cibleFocus) return undefined
    const declencheur = () => ecranRef.current?.querySelector(`[data-testid="cal-electrique-section-${cibleFocus.cle}"] button`)
    declencheur()?.focus?.({ preventScroll: true })
    // Les volets se déplient en animant leur hauteur : la section n'est amenée à l'écran qu'une fois dépliée.
    const id = window.setTimeout(() => declencheur()?.scrollIntoView?.({ block: 'start' }), 320)
    return () => window.clearTimeout(id)
  }, [cibleFocus])
  const reglerIci = (cible) => {
    if (cible?.onglet !== OUVERTURE) return false // les autres cibles changent l'URL : l'écran se remonte dessus
    setAvances((a) => (a.includes('avances') ? a : [...a, 'avances']))
    setSections((s) => (s.includes(OUVERTURE) ? s : [...s, OUVERTURE]))
    setCibleFocus((c) => ({ cle: OUVERTURE, n: (c?.n ?? 0) + 1 }))
    return true
  }
  const calques = (
    <CalquesCarte id={id} resultat={resultat} couleursDessinees={peutColorer} lectureSeule={lectureSeule}
      onRaccorde={relire} onModifier={() => setEditeur(true)} pose={pose} />
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
    <div data-testid="cal-etape-electrique-ecran" className="cel-ecran" ref={ecranRef}>
      {calques}
      {/* ACAL1830 — la carte « Prêt à envoyer ? » est EN TÊTE du panneau (maquette v2), avant l'onduleur. */}
      <PretAEnvoyer key={relecture} calepinageId={id} filtre="electrique" court testIdCompte="cal-electrique-synthese"
        surRegler={reglerIci} />
      {phraseSurfaces && (
        <p role="note" className="cel-surfaces-hors-toit" data-testid="cal-elec-surfaces-non-raccordees">{phraseSurfaces}</p>
      )}
      <CarteOnduleur id={id} entree={entree} configs={configs} resultat={resultat} lectureSeule={lectureSeule}
        onApplique={relire} />
      <section className="cel-schema" data-testid="cal-elec-schema-voir">
        <span className="cel-schema-picto" aria-hidden="true">
          <svg width="26" height="26" viewBox="0 0 26 26" fill="none" stroke="currentColor" strokeWidth="1.8"
            strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 13h4M20 13h4" /><rect x="6" y="8" width="6" height="10" rx="1.5" /><rect x="14" y="8" width="6" height="10" rx="1.5" />
            <path d="M16 16l2-6" />
          </svg>
        </span>
        <span className="cel-schema-texte">
          <span className="cel-schema-titre">Schéma électrique</span>
          <span className="cel-schema-detail">Dessiné tout seul à partir du raccordement</span>
        </span>
        <button type="button" className="cel-bouton-contour" onClick={ouvrirSchema}>Voir</button>
      </section>
      <Accordion type="multiple" className="cel-avances" value={avances} onValueChange={setAvances}>
        <AccordionItem value="avances" data-testid="cal-electrique-avances">
          <AccordionTrigger className="cel-avances-lien">Réglages avancés</AccordionTrigger>
          <AccordionContent>
            <Accordion type="multiple" value={sections} onValueChange={setSections}>
              {SECTIONS_ELECTRIQUES.map((s) => <Section key={s.cle} {...s} propsDuRail={propsDuRail} />)}
            </Accordion>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}
