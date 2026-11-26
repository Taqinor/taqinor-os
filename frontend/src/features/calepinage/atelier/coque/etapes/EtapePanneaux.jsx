import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { couleurAccesActive } from '@rooflib/shadingEngine'
import { MODULE_PAR_DEFAUT_ATELIER } from '@roofpro/moduleSelect'
import { couvertureServie } from '@roofpro/affichageErp' // ACAL1613 — LA part « De la consommation » du constructeur
import calepinageApi from '../../../../../api/calepinageApi'
import useResource from '../../../../../hooks/useResource'
import { formatKwc, formatNumber } from '../../../../../lib/format'
import { cibleAuModule } from '../../cibleAuModule'
import { libelleSourceCible } from '../../contexteAtelier' // T4-X8-012 (une cible) — UNE table de mots pour la source de la cible
import { kwh } from '../../../production/ResultatHeros.helpers'
import { SurCarte } from '../emplacements'
import { BoutonMarine, CarteFlottante, Icone, Indicateur, Segmente } from '../primitives'
import { BESOIN_MAX, gestes, useConstructeur, usePoseVivante } from './panneaux/constructeur'
import { jourMois, ligneModule } from './panneaux/formats'
import { useCibleFactures, useLectureServie } from './panneaux/lectures'
import ValeurUnite from './panneaux/ValeurUnite'
import { fmtKwc, modulesServis, productionPubliee, simulationARefaire } from './panneaux/sources'
import { SIMULATION_A_REFAIRE } from '../../../production/BandeauProvenanceProduction.helpers' // T4-X2-002
import Pourquoi from '../../../commun/Pourquoi' // ACAL1728 — le « ? » unique des chiffres
import { GESTES, lireOutils } from './EtapeToit.helpers' // ACAL1728 — Annuler / Rétablir de la barre de carte

/* ============================================================================
   COQUE — L'ÉCRAN DE L'ÉTAPE « PANNEAUX » (maquettes Panneaux et Tablette).
   ----------------------------------------------------------------------------
   Panneau de droite : le modèle de panneau (liste déroulante), « Combien de
   panneaux ? » (deux cartes), le sens de pose, et l'alerte d'ombrage quand le
   constructeur la sert. Sur la carte : la puce des quatre chiffres, la légende
   d'ensoleillement et le lecteur du soleil. Le pied « Raccorder les panneaux → »
   est celui de la coque (prop `action`) : cet écran ne rend aucun second bouton.

   UNE SOURCE PAR CHIFFRE. La pose affichée est lue sur les contrôles du
   constructeur (`panneaux/constructeur.js`) ; « Couvrir la facture » (taille
   tirée des factures, `cible_factures` du design-context), la production
   publiée (`resultat/`) et le module de l'étude électrique
   (`entree-electrique/`) viennent de `panneaux/sources.js`. Un chiffre absent n'est pas affiché ; chaque geste est
   renvoyé au VRAI contrôle (`rp9-*`), qui reste monté et fait foi.
   ========================================================================== */

// La palette bleu nuit → or de la carte d'accès solaire est posée au DÉMARRAGE de l'atelier (useAtelierBoot,
// ACAL1340), jamais ici : l'étape ne fait que la lire (couleurAccesActive) pour sa légende.

/** ACAL1829 — la ligne d'une carte de taille (« 12 panneaux · 6,96 kWc · ≈ 82 % de la consommation ») : le nombre de chaque
    morceau est dessiné en gras (Archivo), le texte reste celui de la lecture ; le « · » ne se voit pas (l'écart le remplace). */
function Seg({ texte }) {
  const m = /^(≈\s*)?(\d(?:[\d\u00a0\u202f ,.]*\d)?(?:\s%)?)(.*)$/.exec(texte)
  if (!m) return <span>{texte}</span>
  return <span>{m[1]}<b>{m[2]}</b>{m[3]}</span>
}
function Ligne({ texte }) {
  return texte.split(' · ').map((seg, i) => (
    <Fragment key={seg}>
      {i > 0 && <span className="cal-pan-sep"> · </span>}
      <Seg texte={seg} />
    </Fragment>
  ))
}

/** ACAL1829 — la vignette du panneau de la liste (maquette Panneaux) : un module vertical générique, peint aux jetons. */
function Vignette() {
  return (
    <svg className="cal-pan-vignette" width="26" height="44" viewBox="0 0 30 56" aria-hidden="true">
      <rect className="cal-vig-cadre" width="30" height="56" rx="1.5" />
      <rect className="cal-vig-cellules" x="1.4" y="1.4" width="27.2" height="53.2" rx="0.6" />
      <path className="cal-vig-grille" d="M6 1.4v53.2M10.5 1.4v53.2M15 1.4v53.2M19.5 1.4v53.2M24 1.4v53.2M1.4 10h27.2M1.4 19h27.2M1.4 37h27.2M1.4 46h27.2" />
      <path className="cal-vig-barre" d="M1.4 28h27.2" />
      <path className="cal-vig-reflet" d="M1.4 1.4h14L1.4 26z" />
    </svg>
  )
}

const compte = (n) => (n === 1 ? '1 panneau' : `${n} panneaux`)

/** ACAL1749 — des panneaux posés dont la puissance LUE sur le constructeur est nulle (document sans `modules[]`, aucun module
    sur le pan) : jamais « 0,00 kWc » à côté de « 148 panneaux » — la puissance dit « module à choisir » (le choix est
    « Panneau » ci-dessus) ; aucune puissance n'est recalculée ici. */
const PUISSANCE_NULLE = /^0(?:[.,]0+)?\s*kWc$/
const MODULE_A_CHOISIR = 'module à choisir'
function sansPuissanceNulle(figures) {
  return figures?.panneaux > 0 && PUISSANCE_NULLE.test((figures.kwc ?? '').trim())
    ? { ...figures, kwc: MODULE_A_CHOISIR } : figures
}
const selectData = { select: (r) => r?.data ?? null }
const sansParenthese = (t) => (t ?? '').replace(/\s*\([^)]*\)\s*$/, '')

/** Les lectures servies de l'écran, par l'outil commun `useResource` (une lecture chacune ; résultat relu à
    chaque enregistrement). */
function useServi(calepinageId, enregistreLe, servi = null, attendre = false) {
  // La taille des factures : l'accesseur PARTAGÉ avec l'étape Toit (trois états ; le design-context de l'atelier,
  // `ecranProps.contexte`, prime — relu ici seulement sans lui, REP-995).
  const facture = useCibleFactures(calepinageId, servi, { attendre })
  // ACAL1613 — le bloc `chiffrage` du MÊME design-context (lecture partagée, aucune requête de plus).
  const contexte = useLectureServie('contexte', calepinageId, { servi, actif: !attendre })
  const catalogue = useResource((id) => calepinageApi.calepinages.modulesDisponibles(id), calepinageId, selectData).data
  const entree = useResource((id) => calepinageApi.calepinages.entreeElectrique(id), calepinageId, selectData).data
  const resultat = useResource((p) => calepinageApi.calepinages.resultat(p.id), { id: calepinageId, enregistreLe },
    selectData).data
  return {
    leadId: facture.leadId,
    facture,
    chiffrage: contexte.etat === 'ok' ? (contexte.donnees?.chiffrage ?? null) : null,
    cible: facture.cible,
    motifFacture: facture.refus || facture.motif,
    refusFacture: facture.refus,
    tailleSouhaitee: facture.tailleSouhaitee, // R6-N4
    factureSaisie: facture.factureSaisie,
    entrees: Array.isArray(catalogue?.modules) ? catalogue.modules : [],
    // Lane E9 — la taille de la conception comptée dans chaque puissance de la liste (`modules-disponibles/`).
    panneauxSelonWatt: catalogue?.panneaux_selon_watt ?? {},
    kwcSelonWatt: catalogue?.kwc_selon_watt ?? {}, // T4-X8-011 — le kWc de ce compte dans ce module, servi
    servis: modulesServis(entree),
    publiee: productionPubliee(resultat),
    resultat, // ACAL1728 — les valeurs des « ? » de la production publiée
    aRefaire: simulationARefaire(resultat), // T4-X2-002
    // T4-X7-002 — la simulation de la pose a trouvé un ÉCART RÉEL avec la conception (`taux_source: 'autre_installation'` :
    // autre puissance, ou batterie d'un seul côté) : sa part de la consommation ne se lit plus à côté de cette pose. Seul ce
    // signal la tait (`'pose'` = aucun taux de conception, résultat rangé sans clé : comme avant).
    partDeLaConception: resultat?.autoconsommation?.taux_source !== 'autre_installation',
  }
}

/** Ce que la carte du modèle affiche : le choix vivant du constructeur (le module écrit sur le pan). Sans module sur
    le pan : l'état honnête, LE MÊME sur toutes les tailles et quel que soit l'état des lectures (« Aucun panneau
    choisi sur ce toit » + le module par défaut AVEC LEQUEL l'atelier calcule — c'est lui qui fait la puissance de la
    puce) ; ce que l'étude électrique utilise est dit à part, sous la liste (`noteEtude`), quand il est servi — jamais
    le défaut présenté comme le panneau du projet, jamais une phrase qui change selon la vitesse du réseau (H2). */
function moduleAffiche(module, fiches, servis) {
  const fiche = (id) => fiches.get(id)?.module ?? null
  if (module.valeur) {
    const o = module.options.find((x) => x.valeur === module.valeur)
    return { nom: fiche(module.valeur)?.libelle ?? o?.libelle ?? '', ligne: ligneModule(fiche(module.valeur)) }
  }
  const defaut = ligneModule(MODULE_PAR_DEFAUT_ATELIER)
  const utilise = servis.length > 1
    ? `${servis.length} modèles (${servis.map((x) => x.designation).join(' · ')})` : (servis[0]?.designation ?? '')
  return {
    nom: 'Aucun panneau choisi sur ce toit',
    ligne: ['Module par défaut', defaut].filter(Boolean).join(' · '),
    noteEtude: utilise ? `L’étude électrique utilise : ${utilise}.` : '',
    aucun: true,
  }
}

function ChoixModule({ etat, entrees, servis, lectureSeule, g }) {
  const [ouvert, setOuvert] = useState(false)
  const { module } = etat
  const fiches = new Map(entrees.map((e) => [e.module.id, e]))
  const options = module.present ? module.options
    : [{ valeur: '', libelle: MODULE_PAR_DEFAUT_ATELIER.libelle, grise: false }]
  const fiche = (valeur) => (valeur ? fiches.get(valeur)?.module : MODULE_PAR_DEFAUT_ATELIER)
  const nom = (o) => fiches.get(o.valeur)?.module.libelle ?? sansParenthese(o.libelle)
  const affiche = moduleAffiche(module, fiches, servis)
  // La mention du script qui répète le module par défaut n'est pas redite ; « à confirmer » et la synthèse le sont.
  const mention = module.mention && !module.mention.startsWith(MODULE_PAR_DEFAUT_ATELIER.libelle) ? module.mention : ''
  const choisir = (valeur) => {
    g.module(valeur)
    setOuvert(false)
  }
  return (
    <div className="cal-pan-section" data-testid="cal-panneaux-module">
      <span id="cal-pan-module-etiquette" className="cal-pan-titre">Panneau</span>
      <div className="cal-pan-liste-hote">
        <button id="cal-pan-module" type="button" className="cal-pan-module" aria-haspopup="listbox" aria-labelledby="cal-pan-module-etiquette cal-pan-module"
          aria-expanded={ouvert} disabled={lectureSeule || !module.present} title={affiche.nom}
          onClick={() => setOuvert((o) => !o)}
          onKeyDown={(e) => { if (e.key === 'Escape') setOuvert(false) }}>
          <Vignette />
          <span className="cal-pan-module-texte">
            <span className="cal-pan-module-nom">{affiche.nom}</span>
            {affiche.ligne && <span className="cal-pan-module-ligne">{affiche.ligne}</span>}
          </span>
          <Icone nom="chevron" taille={18} epaisseur={2} />
        </button>
        {ouvert && (
          <ul role="listbox" aria-label="Modèles de panneaux" className="cal-pan-options"
            onKeyDown={(e) => { if (e.key === 'Escape') setOuvert(false) }}>
            {options.map((o) => {
              const entree = fiches.get(o.valeur)
              const intitule = <span className="cal-pan-module-nom">{nom(o)}</span>
              return (
                <li key={o.valeur || 'defaut'} role="option" aria-selected={o.valeur === module.valeur}>
                  <button type="button" disabled={o.grise} onClick={() => choisir(o.valeur)}
                    className="cal-pan-option">
                    {/* D-ACAL-169 — le panneau par défaut de la société (désigné au stock, servi `par_defaut`) porte une pastille. */}
                    {entree?.par_defaut
                      ? <span className="cal-pan-option-tete">{intitule}<span className="cal-pan-badge" data-testid="cal-pan-par-defaut">Par défaut</span></span>
                      : intitule}
                    <span className="cal-pan-module-ligne">
                      {o.grise ? (entree?.motif || 'fiche produit incomplète') : [entree?.en_stock ? 'En stock' : '', ligneModule(fiche(o.valeur))].filter(Boolean).join(' · ')}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
      {affiche.noteEtude && <p className="cal-pan-note" data-zone="module-etude">{affiche.noteEtude}</p>}
      {affiche.aucun && !lectureSeule && (
        <p className="cal-pan-note" data-zone="aucun-module">Choisissez le panneau de ce toit dans la liste.</p>
      )}
      {mention && <p className="cal-pan-note">{mention}</p>}
      {module.erreur && <p role="alert" className="cal-pan-erreur">{module.erreur}</p>}
    </div>
  )
}

/** Lane E9 (T4-X2-001 / T4-X9-005) — la cible comptée dans le module CHOISI : la conception est une PUISSANCE ; un module
    d'une autre puissance en pose le compte SERVI (`panneaux_selon_watt`, la règle du moteur — jamais calculé ici), et la
    carte dit les deux. Module absent de la table : la puissance seule, aucun compte (`panneaux: null`).
    T4-X8-011 — le compte ET son kWc (`kwc_selon_watt`, servi) vont ensemble : `kwc` devient celui du module posé ; la
    conception est dite dans sa propre phrase (`conception`). Fiche du module pas (encore) lue : la puissance que le
    constructeur POSE (`wattPose`, « 5 × 710 W ») — jamais le compte de la conception sous un module d'une autre taille. */
function cibleDuModule(cible, module, entrees, servi, wattPose) {
  // Aucun module choisi sur le pan : rien à convertir (la carte garde la taille de la conception, comme avant).
  if (!cible || !module?.valeur) return cible
  const fiche = entrees.find((e) => e.module.id === module.valeur)?.module
  const auModule = cibleAuModule({ panneaux: cible.panneaux, kwc: cible.kwc, wattConception: cible.moduleWc },
    fiche?.pmaxWc ?? wattPose, servi.panneauxSelonWatt, servi.kwcSelonWatt)  // T4-X3-009 : LE lecteur unique de l'atelier
  if (!auModule?.convertie) return cible
  // D-ACAL-110 (rejeu R5B, 26/11) — le module choisi n'est pas celui de la conception : la phrase le DIT d'abord, avec ce
  // que cela change au nombre de panneaux (compte SERVI `panneaux_selon_watt`, jamais calculé ici), puis la conception.
  const watt = `${formatNumber(auModule.watt)} W`
  const ecart = auModule.panneaux == null ? `Ce panneau de ${watt} n’est pas celui de la conception du lead.`
    : auModule.panneaux === cible.panneaux
      ? `Ce panneau de ${watt} n’est pas celui de la conception du lead ; le nombre de panneaux reste ${auModule.panneaux}.`
      : `Ce panneau de ${watt} n’est pas celui de la conception du lead : il en faut ${auModule.panneaux} au lieu de ${cible.panneaux}.`
  return { ...cible, panneaux: auModule.panneaux, watt: auModule.watt, kwc: auModule.kwcModule,
    conception: `${ecart} La conception du lead compte ${auModule.conception}${cible.kwc != null ? `, ${formatKwc(cible.kwc)}` : ''}.` }
}

function CombienDePanneaux({ etat, servi, lectureSeule, g }) {
  const { besoin, figures, memoire } = etat
  const cible = cibleDuModule(servi.cible, etat.module, servi.entrees, servi, figures.watt)
  // La carte choisie est celle de la cible ACTUELLE ; ni l'une ni l'autre → « Pose actuelle : N panneaux · kWc ».
  const factureChoisie = !!cible && besoin?.valeur === cible.panneaux
  const max = etat.max && !factureChoisie
  // La taille des factures n'est promise que si elle tient sur le toit : « seuls N tiennent » (note du constructeur).
  const tient = cible && besoin?.tiennent != null && besoin.tiennent < cible.panneaux ? besoin.tiennent : null
  // T4-X8-012 (une cible) — la cible dite comme la note du constructeur (« N posés / T cible (source) · k de moins que la cible ») :
  // ce qui tient, LA cible et sa source (`cible_factures` n'est servie que pour une cible tirée des factures), l'écart.
  const sourceCible = libelleSourceCible('factures')
  const ligneTaille = tient == null ? null : [
    compte(tient), cible.kwc != null ? fmtKwc((cible.kwc * tient) / cible.panneaux) : null,
    `${cible.panneaux} cible (${sourceCible})`, `${cible.panneaux - tient} de moins que la cible`,
  ].filter(Boolean).join(' · ')
  // Le % n'est dit qu'à côté de la taille pour laquelle il est calculé. T4-X7-002 — ce % est la part SERVIE de la conception
  // (`chiffrage.couverture_pct` = énergie AUTOCONSOMMÉE ÷ consommation, la grandeur ET le nom de la tuile « De la consommation »
  // des Résultats), jamais « production ÷ consommation » ; tu quand la simulation dit que la conception décrit une autre pose.
  const part = (fig) => (servi.partDeLaConception && fig?.couverture && servi.chiffrage?.marche !== 'agricole' ? `≈ ${fig.couverture} de la consommation` : null)
  // La part de la consommation de la carte « Couvrir la facture » : lue sur le constructeur tant que cette taille est
  // posée, gardée pour cette taille et ce module quand une autre carte est choisie (jamais déduite d'une autre pose).
  const partLue = factureChoisie && cible && figures.panneaux === cible.panneaux ? part(figures) : null
  const [gardee, setGardee] = useState(null)
  if (partLue && (gardee?.pour !== cible.panneaux || gardee.watt !== figures.watt || gardee.texte !== partLue)) {
    setGardee({ pour: cible.panneaux, watt: figures.watt, texte: partLue })
  }
  // ACAL1613 — la carte non posée dit aussi sa part : la part SERVIE à SA taille, par LA fonction qui écrit « De la
  // consommation » du constructeur (`couvertureServie`, kWc égal à celui de la conception, sinon rien — jamais une autre pose).
  const pctServi = cible && servi.partDeLaConception ? couvertureServie(servi.chiffrage, cible.kwc) : null
  const partFacture = partLue ?? (gardee && cible && gardee.pour === cible.panneaux && gardee.watt === figures.watt
    ? gardee.texte : null) ?? (pctServi != null ? `≈ ${Math.round(pctServi)} % de la consommation` : null)
  // ACAL2022 (T4-X2-001) — la carte dit la taille de la CONCEPTION (son nombre de panneaux et SON kWc, nommée) : jamais un nombre
  // de panneaux à côté du kWc d'un autre module ; la pose posée se dit à part (« Posé : … »).
  // T4-X8-011 — un module d'une autre puissance : la ligne dit LE compte servi pour ce module et SON kWc servi (« 6 panneaux
  // de 710 W · 4,26 kWc »), la conception sa propre phrase complète, sous la ligne ; sans compte servi : la phrase seule.
  const ligneConversion = cible?.conception && cible.panneaux
    ? [`${compte(cible.panneaux)} de ${formatNumber(cible.watt)} W`, cible.kwc != null ? formatKwc(cible.kwc) : null, partFacture]
      .filter(Boolean).join(' · ')
    : null
  const ligneFacture = cible && (cible.conception ? (ligneTaille ?? ligneConversion) : (ligneTaille ?? [
    compte(cible.panneaux), cible.kwc != null ? fmtKwc(cible.kwc) : null, sourceCible,
    partFacture,
  ].filter(Boolean).join(' · ')))
  const posee = factureChoisie && cible && figures.panneaux > 0 && figures.kwc
    && (figures.panneaux !== cible.panneaux || (cible.kwc != null && figures.kwc !== fmtKwc(cible.kwc)))
    ? ['Posé : ' + compte(figures.panneaux), figures.kwc].join(' · ') : null
  // « Le plus de panneaux » : ses chiffres dès l'ouverture — ce que le constructeur dit tenir × la puissance du module
  // qu'il pose (`figures.watt`), jamais une seconde formule ; la mémoire prime quand la carte a été posée.
  const parTenue = besoin?.tiennent ? {
    panneaux: besoin.tiennent,
    kwc: figures.watt ? fmtKwc((besoin.tiennent * figures.watt) / 1000) : null,
  } : null
  const figuresMax = max ? figures : (memoire.max ?? parTenue)
  const ligneMax = figuresMax?.panneaux ? [compte(figuresMax.panneaux), figuresMax.kwc, part(figuresMax)]
    .filter(Boolean).join(' · ') : ''
  // T4-X9-013 (reste) — sans lead, la phrase de repli ne nomme pas « ce lead ».
  // R6-N4 — un lead qui PORTE une facture ne se voit jamais dire « aucune taille ne se tire des factures » (le serveur nomme
  // d'ordinaire la cause dans `refus` : taille souhaitée, C&I…) : à défaut de cause servie, la phrase dit ce qui est vrai.
  const factureSansCause = Boolean(servi.leadId) && servi.factureSaisie && !servi.motifFacture
  const raison = servi.motifFacture || (servi.leadId
    ? (factureSansCause
      ? 'La facture de ce lead est renseignée, mais le moteur n’en a tiré aucune taille pour l’instant. Choisissez le nombre de panneaux à poser.'
      : 'Aucune taille ne se tire des factures de ce lead.')
    : 'Ce calepinage n’a pas de lead : aucune taille n’est tirée d’une facture. Choisissez le nombre de panneaux à poser.')
  return (
    <section className="cal-pan-section">
      <h2 className="cal-pan-titre">Combien de panneaux ?</h2>
      <button type="button" className="cal-pan-option-pose" aria-pressed={factureChoisie}
        disabled={lectureSeule || !cible?.panneaux || !besoin} onClick={() => { if (!factureChoisie) g.besoin(cible.panneaux) }}
        data-testid="cal-panneaux-option-facture">
        <span className="cal-pan-option-tete">
          <span className="cal-pan-option-nom">Couvrir la facture</span>
          {cible && <span className="cal-pan-badge">Recommandé</span>}
        </span>
        {ligneFacture && <span className="cal-pan-option-ligne"><Ligne texte={ligneFacture} /></span>}
        {/* T4-X8-011 — la conception, dite en entier : une phrase qui se replie, jamais coupée au bord de la carte. */}
        {cible?.conception && <span className="cal-pan-option-phrase" data-zone="conception-du-lead">{cible.conception}</span>}
        {/* Relecture E5 B1 — la conception se calcule : jamais « 0 panneau », la cible est dite en cours. */}
        {!ligneFacture && servi.facture.calculEnCours && (
          <span className="cal-pan-option-ligne" data-zone="cible-en-calcul">calcul en cours</span>
        )}
      </button>
      {/* Lane E9 — la conception a été recalculée depuis l'ouverture : la carte le DIT, jamais en silence. */}
      {servi.facture.recalculee && (
        <p className="cal-pan-note" data-zone="conception-recalculee" role="status">
          {servi.facture.recalculee.raison ? `Conception recalculée : ${servi.facture.recalculee.raison}`
            : 'Conception recalculée depuis l’ouverture de l’atelier.'}
        </p>
      )}
      {posee && <p className="cal-pan-note" data-zone="pose-posee">{posee}</p>}
      {besoin?.auto && <p className="cal-pan-note" data-zone="taille-auto" role="status">{besoin.note}</p>}
      {servi.facture.etat === 'chargement' && (
        <p className="cal-pan-note cal-pan-note-attente" data-zone="facture-lecture" aria-live="polite">
          Lecture de la facture du lead…
        </p>
      )}
      {servi.facture.etat === 'echec' && (
        <p className="cal-pan-note" data-zone="facture-echec" role="alert">
          {'Lecture impossible — '}
          <button type="button" className="cal-pan-lien" onClick={servi.facture.reessayer}>réessayer</button>
        </p>
      )}
      {servi.facture.etat === 'ok' && !cible && servi.facture.calculEnCours && (
        <p className="cal-pan-note" data-zone="conception-en-calcul" role="status" aria-live="polite">
          {servi.facture.calculAbandonne
            ? 'La conception du lead n’est toujours pas calculée. Modifiez un champ de la fiche du lead (facture, ville…) '
              + 'pour relancer le calcul, puis cliquez sur « Actualiser ».'
            : 'La conception du lead est en cours de calcul : la taille s’affichera ici dans quelques secondes.'}
          {' '}
          <button type="button" className="cal-pan-lien" onClick={servi.facture.actualiser}
            data-testid="cal-panneaux-actualiser-conception">Actualiser</button>
          {servi.facture.calculAbandonne && servi.leadId && (
            <>{' '}<Link to={`/crm/leads/${servi.leadId}`} className="cal-pan-lien">Ouvrir la fiche du lead</Link></>
          )}
        </p>
      )}
      {servi.facture.etat === 'ok' && !cible && !servi.facture.calculEnCours && (
        <p className="cal-pan-note">
          {raison}
          {servi.leadId && !(servi.refusFacture && servi.factureSaisie) && !factureSansCause && !servi.tailleSouhaitee && (
            <>{' '}<Link to={`/crm/leads/${servi.leadId}`} className="cal-pan-lien">Renseigner la facture du lead</Link></>
          )}
        </p>
      )}
      <button type="button" className="cal-pan-option-pose" aria-pressed={max}
        disabled={lectureSeule || !besoin} onClick={() => { if (!max) g.besoin(BESOIN_MAX) }} data-testid="cal-panneaux-option-max">
        <span className="cal-pan-option-nom">Le plus de panneaux</span>
        {ligneMax && <span className="cal-pan-option-ligne"><Ligne texte={ligneMax} /></span>}
      </button>
      {!factureChoisie && !max && figures.panneaux > 0 && (
        <p className="cal-pan-note" data-zone="pose-actuelle">
          {['Pose actuelle : ' + compte(figures.panneaux), figures.kwc].filter(Boolean).join(' · ')}
        </p>
      )}
    </section>
  )
}

/** T4-X7-012 (décision du 25/11 : « Add a button ») — retirer un panneau en Guidé, sans passer en Expert : le geste du
    script (`gestes.retirerUnPanneau`), qui choisit le panneau ; les chiffres suivent la lecture du constructeur. Grisé
    avec sa raison quand rien ne peut partir. */
function raisonSansRetrait(etat, lectureSeule) {
  if (lectureSeule) return 'Ce calepinage est en lecture seule : la pose ne se modifie pas ici.'
  const pose = etat.figures.panneaux
  if (!(pose > 0)) return 'Aucun panneau posé à retirer.'
  if (pose < 2) return 'Il reste un seul panneau sur ce pan : il ne se retire pas ici.'
  if (!etat.besoin?.editable) return 'Choisissez d’abord une taille ci-dessus.'
  return null
}

function RetirerUnPanneau({ etat, lectureSeule, g }) {
  const raison = raisonSansRetrait(etat, lectureSeule)
  return (
    <div className="cal-pan-section">
      <BoutonMarine disabled={!!raison} title={raison ?? undefined} data-testid="cal-panneaux-retirer-un"
        onClick={() => g.retirerUnPanneau(etat.figures.panneaux)}>
        Retirer un panneau
      </BoutonMarine>
      {raison && <p className="cal-pan-note" data-zone="retrait-impossible">{raison}</p>}
    </div>
  )
}

/** ACAL1728 (reprise d'ACAL869) — « Personnaliser la disposition » en Guidé : l'alignement des rangées, Annuler et
    Rétablir, chacun RENVOYÉ au vrai contrôle du script (`#rp9-alignement-select`, `#rp9-layout-undo` / `-redo` par les
    gestes de la barre de carte, `EtapeToit.helpers.js::GESTES`) ; leur état est LU sur ces contrôles, jamais supposé. */
function PersonnaliserDisposition({ lectureSeule, rafraichir }) {
  const [, relire] = useState(0)
  const liste = document.getElementById('rp9-alignement-select')
  const modes = liste ? Array.from(liste.options).map((o) => ({ valeur: o.value, libelle: sansParenthese(o.textContent) })) : []
  const outils = lireOutils(document)
  const geste = (faire) => () => { faire(); rafraichir(); relire((n) => n + 1) }
  const aligner = (v) => {
    const champ = document.getElementById('rp9-alignement-select')
    if (!champ || champ.disabled || v === champ.value) return
    champ.value = v
    champ.dispatchEvent(new Event('change', { bubbles: true }))
  }
  return (
    <details className="cal-pan-section" data-testid="cal-panneaux-disposition">
      <summary className="cal-pan-titre">Personnaliser la disposition</summary>
      {modes.length > 0 && (
        <Segmente libelle="Alignement des rangées" options={modes} valeur={liste.value}
          onChange={(v) => { if (!lectureSeule) geste(() => aligner(v))() }} />
      )}
      <div className="cal-pan-alerte-actions">
        <BoutonMarine disabled={lectureSeule || !outils.annuler} onClick={geste(() => GESTES.annuler(document))}>Annuler</BoutonMarine>
        <BoutonMarine disabled={lectureSeule || !outils.retablir} onClick={geste(() => GESTES.retablir(document))}>Rétablir</BoutonMarine>
      </div>
    </details>
  )
}

const PICTO_PORTRAIT = (
  <svg width="10" height="16" viewBox="0 0 10 16" aria-hidden="true"><rect x="0.75" y="0.75" width="8.5" height="14.5" rx="1" /></svg>
)
const PICTO_PAYSAGE = (
  <svg width="16" height="10" viewBox="0 0 16 10" aria-hidden="true"><rect x="0.75" y="0.75" width="14.5" height="8.5" rx="1" /></svg>
)
const SENS_DE_POSE = [
  { valeur: 'portrait', libelle: 'Portrait' },
  { valeur: 'landscape', libelle: 'Paysage' },
  { valeur: 'auto', libelle: 'Au mieux' },
]
// ACAL1829 — les pictogrammes ne changent pas les libellés lus ailleurs (SENS_DE_POSE) : ils habillent le segment.
const SENS_AVEC_PICTO = SENS_DE_POSE.map((o) => ({
  ...o, libelle: <>{o.valeur === 'portrait' ? PICTO_PORTRAIT : o.valeur === 'landscape' ? PICTO_PAYSAGE : null}{o.libelle}</>,
}))

/** Item 14 (T4-U1-023) — le toit porte des objets qui font de l'ombre mais l'ombre n'est pas comptée : la phrase SERVIE
    (`parcours.manque`, code `ombres_non_mesurees`) — avant, l'étape n'en disait rien. */
function AvisOmbresNonComptees({ manque }) {
  const ligne = (Array.isArray(manque) ? manque : []).find((m) => m?.code === 'ombres_non_mesurees')
  if (!ligne?.message) return null
  return (
    <section className="cal-pan-alerte" data-testid="cal-panneaux-ombres-non-comptees" role="status">
      <h2 className="cal-pan-alerte-titre">
        <span className="cal-pan-alerte-pastille" aria-hidden="true"><span /><span /></span>
        Ombres à compter
      </h2>
      <p className="cal-pan-alerte-texte">{ligne.message}</p>
    </section>
  )
}

/** L'alerte bleu-gris : seulement quand l'avis d'ombrage du constructeur propose de retirer des modules. */
function AlerteOmbre({ ombre, g }) {
  const [garde, setGarde] = useState(false)
  if (!ombre || garde) return null
  const { n, origine } = ombre
  return (
    <section className="cal-pan-alerte" data-testid="cal-panneaux-ombre">
      <h2 className="cal-pan-alerte-titre">
        <span className="cal-pan-alerte-pastille" aria-hidden="true"><span /><span /></span>
        {n === 1 ? '1 panneau à l’ombre' : `${n} panneaux à l’ombre`}
      </h2>
      <p className="cal-pan-alerte-texte">
        {`${n === 1 ? 'Il reçoit' : 'Ils reçoivent'} moins de soleil que le seuil réglé ${
          origine === 'dossier' ? 'pour ce dossier' : 'par votre société'}.`}
      </p>
      <div className="cal-pan-alerte-actions">
        <BoutonMarine onClick={g.retirerOmbre}>
          {n === 1 ? 'Retirer ce panneau' : `Retirer ces ${n} panneaux`}
        </BoutonMarine>
        <button type="button" className="cal-pan-garder" onClick={() => setGarde(true)}>Garder</button>
      </div>
    </section>
  )
}

/** La puce de la carte. Production publiée FRAÎCHE et COMPLÈTE → la pose simulée et sa production, libellé de l'étape
    Résultats ; sinon la pose du constructeur, son estimation nommée « estimation » et la part de la consommation servie
    (T4-X7-002 : énergie autoconsommée ÷ consommation, le nom et la grandeur des Résultats ; tue par `partDeLaConception`). */
function PuceResume({ figures, publiee, site = null, aRefaire = false, partDeLaConception = true, resultat = null }) {
  // ACAL2022 (T4-X2-009) — le site compte plus que ce pan (champ au sol, autre pan) : la bande dit qu'elle compte CE pan et le total du site est dit.
  const autrePan = !publiee && site?.panneaux > 0 && figures.panneaux > 0 && site.panneaux !== figures.panneaux
  const pan = autrePan ? ' · ce pan' : ''
  // ACAL1728 (reprise d'ACAL876) — chaque chiffre porte son « ? » (phrase du REGISTRE servi, `commun/Pourquoi.jsx`) : la
  // production publiée, celles de l'étape Résultats ; la pose du constructeur, celles de sa carte « Recommandation ».
  const indicateurs = publiee
    ? [
      ['Panneaux', publiee.panneaux != null ? String(publiee.panneaux) : null, <Pourquoi key="?" cle="toit.pose_panneaux" />],
      ['Puissance', publiee.kwc, <Pourquoi key="?" cle="production.kwc" valeurs={resultat} />],
      [publiee.libelle, kwh(publiee.p50), <Pourquoi key="?" cle="production.p50_kwh" valeurs={resultat} />],
    ]
    : [
      [`Panneaux${pan}`, figures.panneaux ? String(figures.panneaux) : null, <Pourquoi key="?" cle="toit.reco_panneaux" />],
      [`Puissance${pan}`, figures.kwc, <Pourquoi key="?" cle="toit.reco_puissance" />],
      ...(autrePan ? [['Total du site', [`${site.panneaux} panneaux`, site.kwc].filter(Boolean).join(' · ')]] : []),
      // ACAL2022 — la production est celle de la conception SERVIE ; pendant le dessin, « au prochain enregistrement ».
      [...(figures.productionKwh != null ? ['Production · conception', figures.production]
        // M5 — la raison est celle que dit le constructeur (`affichageErp.raisonSansValeur`) : « au prochain enregistrement » seulement là où il
        // est vrai, sinon « calculée pour la conception du lead : X kWc — votre pose en compte Y kWc ».
        : ['Production', figures.production ? figures.production.replace(/^production\s+/i, '') : null]),
      <Pourquoi key="?" cle="toit.reco_production" />],
      ['De la consommation', partDeLaConception && figures.couverture ? `≈ ${figures.couverture}` : null,
        <Pourquoi key="?" cle="toit.reco_couverture" />],
    ]
  const lus = indicateurs.filter(([, valeur]) => valeur)
  // T4-X9-006 — tailles différentes : la phrase du constructeur, UNE fois, en texte courant qui revient à la ligne dans la
  // bande (jamais dans une case de chiffre, qui débordait sous la pile de zoom).
  const phrase = publiee ? null : figures.tailles
  // T4-X2-002 — la simulation enregistrée est périmée : DIT, avec le geste pour la refaire (jamais un silence).
  const aRefaireTexte = !publiee && aRefaire ? `${SIMULATION_A_REFAIRE} Relancez-la à l’étape Les résultats.` : null
  if (lus.length === 0 && !phrase && !aRefaireTexte) return null
  return (
    <CarteFlottante className="cal-pan-puce" data-testid="cal-sur-carte-resume">
      {lus.map(([libelle, valeur, aide]) => (
        <Indicateur key={libelle} libelle={aide ? <>{libelle}{aide}</> : libelle} valeur={<ValeurUnite texte={valeur} />} />
      ))}
      {phrase && <p className="cal-pan-puce-phrase">{phrase}</p>}
      {aRefaireTexte && <p className="cal-pan-puce-phrase">{aRefaireTexte}</p>}
    </CarteFlottante>
  )
}

/** Le dégradé de la légende : les couleurs MÊMES que la carte d'accès solaire (palette active de `shadingEngine`),
    aux arrêts de la rampe de la maquette. */
const degrade = () => `linear-gradient(90deg, ${[0, 0.3, 0.5, 0.72, 1].map((a) => {
  const c = couleurAccesActive(a)
  return `rgb(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)}) ${Math.round(a * 100)}%`
}).join(', ')})`

/** La légende de la maquette ; son titre est LE bouton de la carte d'accès solaire. Éteinte, le bouton reste là (sans
    dégradé ni bornes : ils ne décrivent que des panneaux teintés), pour la rallumer sans connaître « Avancé ». */
function LegendeSoleil({ carte, g }) {
  const active = !!carte?.active
  return (
    <CarteFlottante className="cal-pan-legende" data-active={active ? 'oui' : 'non'}>
      <button type="button" className="cal-pan-legende-titre" aria-pressed={active}
        title={active ? 'Retirer les couleurs des panneaux' : 'Colorer les panneaux'}
        disabled={!carte} onClick={g.carteSoleil}>
        Ensoleillement de chaque panneau
      </button>
      {active && <div className="cal-pan-degrade" style={{ background: degrade() }} />}
      {active && <div className="cal-pan-legende-bornes"><span>Ombragé</span><span>Plein soleil</span></div>}
    </CarteFlottante>
  )
}

function LecteurSoleil({ soleil, g }) {
  const { heure, date, saison, lecture, min, max } = soleil
  const jour = jourMois(date)
  const quand = [jour, heure == null ? '' : `${heure} h`].filter(Boolean).join(' · ')
  const valeur = heure ?? min
  const rempli = max > min ? Math.round(((valeur - min) / (max - min)) * 100) : 0
  return (
    <CarteFlottante className="cal-pan-lecteur">
      <button type="button" className="cal-pan-lecture" aria-label="Lire la journée" aria-pressed={!!lecture?.active}
        disabled={!lecture} onClick={g.lecture}>
        <Icone nom="lecture" taille={18} epaisseur={2} />
      </button>
      <div className="cal-pan-curseur">
        <div className="cal-pan-curseur-tete"><span>{`${min} h`}</span><strong>{quand}</strong><span>{`${max} h`}</span></div>
        <input type="range" min={min} max={max} step="1" className="cal-pan-heure" value={valeur}
          style={{ '--cal-pan-rempli': `${rempli}%` }}
          disabled={heure == null} aria-label="Heure du soleil"
          onChange={(e) => g.heure(e.target.value)} />
      </div>
      <Segmente libelle="Saison" grand valeur={saison}
        options={[{ valeur: 'winter', libelle: 'Hiver' }, { valeur: 'summer', libelle: 'Été' }]}
        onChange={g.saison} />
    </CarteFlottante>
  )
}

/** ACAL1981 — l'étape montre l'ensoleillement de chaque panneau (maquette Panneaux) : la carte d'accès est allumée à
    l'entrée et éteinte à la sortie (l'Électrique teint par chaîne, ACAL1621) ; la bascule reste dans « Avancé ». */
function useEnsoleillementALEntree(carteLue, rafraichir) {
  useEffect(() => {
    const allumee = () => document.getElementById('rp9-heatmap-toggle')?.getAttribute('aria-pressed') === 'true'
    if (!carteLue || allumee()) return undefined
    gestes.carteSoleil(); rafraichir()
    return () => { if (allumee()) gestes.carteSoleil() }
  }, [carteLue, rafraichir])
}

export default function EtapePanneaux({
  calepinageId, lectureSeule = false, enregistreLe = null, contexte = null, contexteEnCours = false, parcours = null,
  builderApi = null,
}) {
  const [lu, rafraichir] = useConstructeur()
  const etat = { ...lu, figures: sansPuissanceNulle(lu.figures) } // ACAL1749
  const site = usePoseVivante(true, builderApi)
  // Chaque geste part au vrai contrôle, puis la lecture est refaite tout de suite (sinon elle suit 0,4 s plus tard).
  const g = Object.fromEntries(Object.entries(gestes).map(([nom, geste]) => [
    nom, (...args) => { geste(...args); rafraichir() },
  ]))
  const servi = useServi(calepinageId, enregistreLe, contexte, contexteEnCours)
  useEnsoleillementALEntree(etat.soleil.carte != null, rafraichir)
  // Un clic sur une carte de taille peut faire passer le constructeur d'un sens de pose à l'autre : l'écran le dit.
  const [avant, setAvant] = useState(null)
  const bascule = avant && etat.orientation && etat.orientation !== avant ? { de: avant, vers: etat.orientation } : null
  const libelleSens = (v) => SENS_DE_POSE.find((o) => o.valeur === v)?.libelle ?? v
  const gestesEcran = {
    ...g,
    besoin: (n) => { setAvant(etat.orientation); g.besoin(n) },
    orientation: (v) => { setAvant(null); g.orientation(v) },
  }
  return (
    <div className="cal-pan">
      <ChoixModule etat={etat} entrees={servi.entrees} servis={servi.servis} lectureSeule={lectureSeule} g={g} />
      <CombienDePanneaux etat={etat} servi={servi} lectureSeule={lectureSeule} g={gestesEcran} />
      <RetirerUnPanneau etat={etat} lectureSeule={lectureSeule} g={g} />
      <section className="cal-pan-section">
        <h2 className="cal-pan-titre">Sens de pose</h2>
        <div data-testid="cal-panneaux-sens-pose">
          <Segmente libelle="Sens de pose" grand className="cal-segmente-pose" options={SENS_AVEC_PICTO}
            valeur={etat.orientation} onChange={(v) => { if (v !== etat.orientation) gestesEcran.orientation(v) }} />
        </div>
        {bascule && (
          <p className="cal-pan-note" data-zone="sens-bascule" role="status">
            {`Le sens de pose est passé de ${libelleSens(bascule.de)} à ${libelleSens(bascule.vers)} pour cette taille.`}
          </p>
        )}
      </section>
      <PersonnaliserDisposition lectureSeule={lectureSeule} rafraichir={rafraichir} />
      <AlerteOmbre key={etat.ombre?.n ?? 0} ombre={etat.ombre} g={g} />
      <AvisOmbresNonComptees manque={parcours?.manque} />
      <SurCarte>
        <PuceResume figures={etat.figures} publiee={servi.publiee} site={site} aRefaire={servi.aRefaire}
          partDeLaConception={servi.partDeLaConception} resultat={servi.resultat} />
        <div className="cal-carte-soleil" data-testid="cal-carte-soleil">
          {etat.soleil.carte && <LegendeSoleil carte={etat.soleil.carte} g={g} />}
          <LecteurSoleil soleil={etat.soleil} g={g} />
        </div>
      </SurCarte>
    </div>
  )
}
