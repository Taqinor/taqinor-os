import { useState } from 'react'
import { Link } from 'react-router-dom'
import { couleurAccesActive } from '@rooflib/shadingEngine'
import { MODULE_PAR_DEFAUT_ATELIER } from '@roofpro/moduleSelect'
import calepinageApi from '../../../../../api/calepinageApi'
import useResource from '../../../../../hooks/useResource'
import { kwh } from '../../../production/ResultatHeros.helpers'
import { SurCarte } from '../emplacements'
import { BoutonMarine, CarteFlottante, Icone, Indicateur, Segmente } from '../primitives'
import { BESOIN_MAX, gestes, useConstructeur } from './panneaux/constructeur'
import { jourMois, ligneModule } from './panneaux/formats'
import { useCibleFactures } from './panneaux/lectures'
import { fmtKwc, modulesServis, productionPubliee } from './panneaux/sources'

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

const compte = (n) => (n === 1 ? '1 panneau' : `${n} panneaux`)
const selectData = { select: (r) => r?.data ?? null }
const sansParenthese = (t) => (t ?? '').replace(/\s*\([^)]*\)\s*$/, '')

/** Les lectures servies de l'écran, par l'outil commun `useResource` (une lecture chacune ; résultat relu à
    chaque enregistrement). */
function useServi(calepinageId, enregistreLe, servi = null, attendre = false) {
  // La taille des factures : l'accesseur PARTAGÉ avec l'étape Toit (trois états ; le design-context de l'atelier,
  // `ecranProps.contexte`, prime — relu ici seulement sans lui, REP-995).
  const facture = useCibleFactures(calepinageId, servi, { attendre })
  const catalogue = useResource((id) => calepinageApi.calepinages.modulesDisponibles(id), calepinageId, selectData).data
  const entree = useResource((id) => calepinageApi.calepinages.entreeElectrique(id), calepinageId, selectData).data
  const resultat = useResource((p) => calepinageApi.calepinages.resultat(p.id), { id: calepinageId, enregistreLe },
    selectData).data
  return {
    leadId: facture.leadId,
    facture,
    cible: facture.cible,
    motifFacture: facture.motif,
    entrees: Array.isArray(catalogue?.modules) ? catalogue.modules : [],
    servis: modulesServis(entree),
    publiee: productionPubliee(resultat),
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
              return (
                <li key={o.valeur || 'defaut'} role="option" aria-selected={o.valeur === module.valeur}>
                  <button type="button" disabled={o.grise} onClick={() => choisir(o.valeur)}
                    className="cal-pan-option">
                    <span className="cal-pan-module-nom">{nom(o)}</span>
                    <span className="cal-pan-module-ligne">
                      {o.grise ? (entree?.motif || 'fiche produit incomplète') : ligneModule(fiche(o.valeur))}
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

function CombienDePanneaux({ etat, servi, lectureSeule, g }) {
  const { besoin, figures, memoire } = etat
  const { cible } = servi
  // La carte choisie est celle de la cible ACTUELLE ; ni l'une ni l'autre → « Pose actuelle : N panneaux · kWc ».
  const factureChoisie = !!cible && besoin?.valeur === cible.panneaux
  const max = etat.max && !factureChoisie
  // La taille des factures n'est promise que si elle tient sur le toit : « seuls N tiennent » (note du constructeur).
  const tient = cible && besoin?.tiennent != null && besoin.tiennent < cible.panneaux ? besoin.tiennent : null
  const ligneTaille = tient == null ? null : [
    compte(tient), cible.kwc != null ? fmtKwc((cible.kwc * tient) / cible.panneaux) : null, `sur ${cible.panneaux} nécessaires`,
  ].filter(Boolean).join(' · ')
  // Le % n'est dit qu'à côté de la taille pour laquelle il est calculé : production estimée ÷ consommation du lead.
  const part = (fig) => (fig?.couverture ? `≈ ${fig.couverture} de la consommation` : null)
  const ligneFacture = cible && (ligneTaille ?? [
    compte(cible.panneaux), cible.kwc != null ? fmtKwc(cible.kwc) : null,
    factureChoisie && figures.panneaux === cible.panneaux ? part(figures) : null,
  ].filter(Boolean).join(' · '))
  const figuresMax = max ? figures : (memoire.max ?? (besoin?.tiennent ? { panneaux: besoin.tiennent } : null))
  const ligneMax = figuresMax?.panneaux ? [compte(figuresMax.panneaux), figuresMax.kwc, part(figuresMax)]
    .filter(Boolean).join(' · ') : ''
  const raison = servi.motifFacture || 'Aucune taille ne se tire des factures de ce lead.'
  return (
    <section className="cal-pan-section">
      <h2 className="cal-pan-titre">Combien de panneaux ?</h2>
      <button type="button" className="cal-pan-option-pose" aria-pressed={factureChoisie}
        disabled={lectureSeule || !cible || !besoin} onClick={() => { if (!factureChoisie) g.besoin(cible.panneaux) }}
        data-testid="cal-panneaux-option-facture">
        <span className="cal-pan-option-tete">
          <span className="cal-pan-option-nom">Couvrir la facture</span>
          {cible && <span className="cal-pan-badge">Recommandé</span>}
        </span>
        {ligneFacture && <span className="cal-pan-option-ligne">{ligneFacture}</span>}
      </button>
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
      {servi.facture.etat === 'ok' && !cible && (
        <p className="cal-pan-note">
          {raison}
          {servi.leadId && (
            <>{' '}<Link to={`/crm/leads/${servi.leadId}`} className="cal-pan-lien">Renseigner la facture du lead</Link></>
          )}
        </p>
      )}
      <button type="button" className="cal-pan-option-pose" aria-pressed={max}
        disabled={lectureSeule || !besoin} onClick={() => { if (!max) g.besoin(BESOIN_MAX) }} data-testid="cal-panneaux-option-max">
        <span className="cal-pan-option-nom">Le plus de panneaux</span>
        {ligneMax && <span className="cal-pan-option-ligne">{ligneMax}</span>}
      </button>
      {!factureChoisie && !max && figures.panneaux > 0 && (
        <p className="cal-pan-note" data-zone="pose-actuelle">
          {['Pose actuelle : ' + compte(figures.panneaux), figures.kwc].filter(Boolean).join(' · ')}
        </p>
      )}
    </section>
  )
}

const SENS_DE_POSE = [
  { valeur: 'portrait', libelle: 'Portrait' },
  { valeur: 'landscape', libelle: 'Paysage' },
  { valeur: 'auto', libelle: 'Au mieux' },
]

/** L'alerte bleu-gris : seulement quand l'avis d'ombrage du constructeur propose de retirer des modules. */
function AlerteOmbre({ ombre, g }) {
  const [garde, setGarde] = useState(false)
  if (!ombre || garde) return null
  const { n, origine } = ombre
  return (
    <section className="cal-pan-alerte" data-testid="cal-panneaux-ombre">
      <h2 className="cal-pan-alerte-titre">
        <Icone nom="info" taille={18} epaisseur={2} />
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
    Résultats ; sinon la pose du constructeur, son estimation nommée « estimation » et la part de la consommation
    (production estimée ÷ consommation du lead : jamais « de la facture »). */
function PuceResume({ figures, publiee }) {
  const indicateurs = publiee
    ? [
      ['Panneaux', publiee.panneaux != null ? String(publiee.panneaux) : null],
      ['Puissance', publiee.kwc],
      [publiee.libelle, kwh(publiee.p50)],
    ]
    : [
      ['Panneaux', figures.panneaux ? String(figures.panneaux) : null],
      ['Puissance', figures.kwc],
      ['Production · estimation de la pose', figures.production],
      ['De la consommation', figures.couverture ? `≈ ${figures.couverture}` : null],
    ]
  const lus = indicateurs.filter(([, valeur]) => valeur)
  if (lus.length === 0) return null
  return (
    <CarteFlottante className="cal-pan-puce" data-testid="cal-sur-carte-resume">
      {lus.map(([libelle, valeur]) => (
        <Indicateur key={libelle} libelle={libelle} valeur={valeur} />
      ))}
    </CarteFlottante>
  )
}

/** Le dégradé de la légende : les couleurs MÊMES que la carte d'accès solaire (palette active de `shadingEngine`),
    aux arrêts de la rampe de la maquette. */
const degrade = () => `linear-gradient(90deg, ${[0, 0.3, 0.5, 0.72, 1].map((a) => {
  const c = couleurAccesActive(a)
  return `rgb(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)}) ${Math.round(a * 100)}%`
}).join(', ')})`

function LegendeSoleil({ carte, g }) {
  return (
    <CarteFlottante className="cal-pan-legende">
      <button type="button" className="cal-pan-legende-titre" aria-pressed={!!carte?.active}
        title={carte?.active ? 'Retirer les couleurs des panneaux' : 'Colorer les panneaux'}
        disabled={!carte} onClick={g.carteSoleil}>
        Ensoleillement de chaque panneau
      </button>
      <div className="cal-pan-degrade" style={{ background: degrade() }} />
      <div className="cal-pan-legende-bornes"><span>Ombragé</span><span>Plein soleil</span></div>
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

export default function EtapePanneaux({ calepinageId, lectureSeule = false, enregistreLe = null, contexte = null, contexteEnCours = false }) {
  const [etat, rafraichir] = useConstructeur()
  // Chaque geste part au vrai contrôle, puis la lecture est refaite tout de suite (sinon elle suit 0,4 s plus tard).
  const g = Object.fromEntries(Object.entries(gestes).map(([nom, geste]) => [
    nom, (...args) => { geste(...args); rafraichir() },
  ]))
  const servi = useServi(calepinageId, enregistreLe, contexte, contexteEnCours)
  return (
    <div className="cal-pan">
      <ChoixModule etat={etat} entrees={servi.entrees} servis={servi.servis} lectureSeule={lectureSeule} g={g} />
      <CombienDePanneaux etat={etat} servi={servi} lectureSeule={lectureSeule} g={g} />
      <section className="cal-pan-section">
        <h2 className="cal-pan-titre">Sens de pose</h2>
        <div data-testid="cal-panneaux-sens-pose">
          <Segmente libelle="Sens de pose" grand className="cal-segmente-pose" options={SENS_DE_POSE}
            valeur={etat.orientation} onChange={(v) => { if (v !== etat.orientation) g.orientation(v) }} />
        </div>
      </section>
      <AlerteOmbre key={etat.ombre?.n ?? 0} ombre={etat.ombre} g={g} />
      <SurCarte>
        <PuceResume figures={etat.figures} publiee={servi.publiee} />
        <div className="cal-carte-soleil" data-testid="cal-carte-soleil">
          <LegendeSoleil carte={etat.soleil.carte} g={g} />
          <LecteurSoleil soleil={etat.soleil} g={g} />
        </div>
      </SurCarte>
    </div>
  )
}
