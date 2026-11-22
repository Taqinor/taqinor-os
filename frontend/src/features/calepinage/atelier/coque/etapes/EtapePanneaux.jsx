import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { solarAccessColorRGB } from '@rooflib/shadingEngine'
import { MODULE_PAR_DEFAUT_ATELIER } from '@roofpro/moduleSelect'
import calepinageApi from '../../../../../api/calepinageApi'
import '../../../../../styles/calepinage/52-etape-panneaux.css'
import { SurCarte } from '../emplacements'
import { BoutonMarine, CarteFlottante, Indicateur, Segmente } from '../primitives'
import { BESOIN_MAX, gestes, useConstructeur } from './panneaux/constructeur'
import { jourMois, ligneModule } from './panneaux/formats'

/* ============================================================================
   COQUE — L'ÉCRAN DE L'ÉTAPE « PANNEAUX » (maquettes Panneaux et Tablette).
   ----------------------------------------------------------------------------
   Panneau de droite : le modèle de panneau (liste déroulante), « Combien de
   panneaux ? » (deux cartes), le sens de pose, et l'alerte d'ombrage quand le
   constructeur la sert. Sur la carte : la puce des quatre chiffres, la légende
   d'ensoleillement et le lecteur du soleil. Le pied « Raccorder les panneaux → »
   est celui de la coque (prop `action`) : cet écran ne rend aucun second bouton.

   RIEN N'EST RECALCULÉ. Chaque chiffre est lu sur les contrôles du constructeur
   (`panneaux/constructeur.js`) ; un chiffre absent n'est pas affiché ; chaque
   geste est renvoyé au VRAI contrôle (`rp9-*`), qui reste monté et fait foi.
   ========================================================================== */

/* Trois pictogrammes des maquettes que `primitives.jsx` n'a pas (demande à l'orchestrateur : les y ajouter). */
const TRACES = {
  chevron: <path d="M6 9l6 6 6-6" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.5" /></>,
  lecture: <path d="M7 4l13 8-13 8z" fill="currentColor" stroke="none" />,
}
function Icone({ nom, taille = 18, epaisseur = 2 }) {
  return (
    <svg width={taille} height={taille} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={epaisseur}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{TRACES[nom]}</svg>
  )
}

const compte = (n) => (n === 1 ? '1 panneau' : `${n} panneaux`)

/** Le lead du calepinage (pour renvoyer vers sa fiche), lu sur le détail servi. */
function useLeadId(calepinageId) {
  const [leadId, setLeadId] = useState(null)
  useEffect(() => {
    if (!calepinageId) return undefined
    let vivant = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.get(calepinageId))
      .then((rep) => { if (vivant) setLeadId(rep?.data?.lead?.id ?? null) })
      .catch(() => { if (vivant) setLeadId(null) })
    return () => { vivant = false }
  }, [calepinageId])
  return leadId
}

/** Le catalogue de modules de la société (fiches servies), pour la ligne « puissance · cotes ». */
function useCatalogue(calepinageId) {
  const [entrees, setEntrees] = useState([])
  useEffect(() => {
    if (!calepinageId) return undefined
    let vivant = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.modulesDisponibles(calepinageId))
      .then((rep) => { if (vivant) setEntrees(Array.isArray(rep?.data?.modules) ? rep.data.modules : []) })
      .catch(() => { if (vivant) setEntrees([]) })
    return () => { vivant = false }
  }, [calepinageId])
  return entrees
}

function ChoixModule({ etat, entrees, lectureSeule, g }) {
  const [ouvert, setOuvert] = useState(false)
  const { module } = etat
  const fiches = new Map(entrees.map((e) => [e.module.id, e]))
  const options = module.present ? module.options
    : [{ valeur: '', libelle: MODULE_PAR_DEFAUT_ATELIER.libelle, grise: false }]
  const fiche = (valeur) => (valeur ? fiches.get(valeur)?.module : MODULE_PAR_DEFAUT_ATELIER)
  const nom = (o) => fiches.get(o.valeur)?.module.libelle ?? o.libelle
  const choisie = options.find((o) => o.valeur === module.valeur) ?? options[0]
  const choisir = (valeur) => {
    g.module(valeur)
    setOuvert(false)
  }
  return (
    <div className="cal-pan-section" data-testid="cal-panneaux-module">
      <span id="cal-pan-module-etiquette" className="cal-pan-titre">Panneau</span>
      <div className="cal-pan-liste-hote">
        <button id="cal-pan-module" type="button" className="cal-pan-module" aria-haspopup="listbox" aria-labelledby="cal-pan-module-etiquette cal-pan-module"
          aria-expanded={ouvert} disabled={lectureSeule || !module.present}
          onClick={() => setOuvert((o) => !o)}
          onKeyDown={(e) => { if (e.key === 'Escape') setOuvert(false) }}>
          <span className="cal-pan-module-texte">
            <span className="cal-pan-module-nom">{choisie ? nom(choisie) : ''}</span>
            {ligneModule(fiche(choisie?.valeur)) && (
              <span className="cal-pan-module-ligne">{ligneModule(fiche(choisie?.valeur))}</span>
            )}
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
      {module.mention && <p className="cal-pan-note">{module.mention}</p>}
      {module.erreur && <p role="alert" className="cal-pan-erreur">{module.erreur}</p>}
    </div>
  )
}

/** La ligne de chiffres d'une option, avec ce qui est réellement lu : « 12 panneaux · 6,96 kWc · 82 % … ». */
function ligneOption(fig, { couvre }) {
  if (!fig?.panneaux) return ''
  const parts = [compte(fig.panneaux)]
  if (fig.kwc) parts.push(fig.kwc)
  if (couvre === 'facture' && fig.couverture) parts.push(`${fig.couverture} de la facture`)
  if (couvre === 'max' && fig.couverturePct >= 100) parts.push('dépasse la consommation')
  return parts.join(' · ')
}

function CombienDePanneaux({ etat, leadId, lectureSeule, g }) {
  const { besoin, mode, memoire, figures } = etat
  const memoFacture = memoire.facture
  const factureDispo = mode === 'facture' || !!memoFacture
  const figuresFacture = mode === 'facture' ? figures : memoFacture
  const figuresMax = mode === 'max' ? figures
    : (memoire.max ?? (besoin?.tiennent ? { panneaux: besoin.tiennent } : null))
  const raison = besoin && !besoin.valeur && besoin.note
    ? besoin.note
    : 'Le besoin d’après la facture n’est plus connu : modifiez la facture du lead pour le recalculer.'
  const poserFacture = () => {
    if (mode !== 'facture' && memoFacture?.besoin) g.besoin(memoFacture.besoin)
  }
  const poserMax = () => { if (mode !== 'max') g.besoin(BESOIN_MAX) }
  return (
    <section className="cal-pan-section">
      <h2 className="cal-pan-titre">Combien de panneaux ?</h2>
      <button type="button" className="cal-pan-option-pose" aria-pressed={mode === 'facture'}
        disabled={lectureSeule || !factureDispo} onClick={poserFacture}
        data-testid="cal-panneaux-option-facture">
        <span className="cal-pan-option-tete">
          <span className="cal-pan-option-nom">Couvrir la facture</span>
          {factureDispo && <span className="cal-pan-badge">Recommandé</span>}
        </span>
        {ligneOption(figuresFacture, { couvre: 'facture' }) && (
          <span className="cal-pan-option-ligne">{ligneOption(figuresFacture, { couvre: 'facture' })}</span>
        )}
      </button>
      {!factureDispo && (
        <p className="cal-pan-note">
          {raison}
          {leadId && (
            <>{' '}<Link to={`/crm/leads/${leadId}`} className="cal-pan-lien">Renseigner la facture du lead</Link></>
          )}
        </p>
      )}
      <button type="button" className="cal-pan-option-pose" aria-pressed={mode === 'max'}
        disabled={lectureSeule || !besoin} onClick={poserMax} data-testid="cal-panneaux-option-max">
        <span className="cal-pan-option-nom">Le plus de panneaux</span>
        {ligneOption(figuresMax, { couvre: 'max' }) && (
          <span className="cal-pan-option-ligne">{ligneOption(figuresMax, { couvre: 'max' })}</span>
        )}
      </button>
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

/** La puce de la carte : les chiffres de la pose posée, ceux qui sont lus seulement. */
function PuceResume({ figures }) {
  const indicateurs = [
    ['Panneaux', figures.panneaux ? String(figures.panneaux) : null],
    ['Puissance', figures.kwc],
    ['Production · estimation', figures.production],
    ['De la facture', figures.couverture],
  ].filter(([, valeur]) => valeur)
  if (indicateurs.length === 0) return null
  return (
    <CarteFlottante className="cal-pan-puce" data-testid="cal-sur-carte-resume">
      {indicateurs.map(([libelle, valeur]) => (
        <Indicateur key={libelle} libelle={libelle} valeur={valeur} />
      ))}
    </CarteFlottante>
  )
}

/** Le dégradé de la légende : les couleurs MÊMES que la carte d'accès solaire (lues de `shadingEngine`). */
const degrade = () => `linear-gradient(to right, ${[0, 0.25, 0.5, 0.75, 1].map((a) => {
  const c = solarAccessColorRGB(a)
  return `rgb(${Math.round(c.r * 255)},${Math.round(c.g * 255)},${Math.round(c.b * 255)})`
}).join(', ')})`

function LegendeSoleil({ carte, g }) {
  return (
    <CarteFlottante className="cal-pan-legende">
      <button type="button" className="cal-pan-legende-titre" aria-pressed={!!carte?.active}
        disabled={!carte} onClick={g.carteSoleil}>
        Ensoleillement de chaque panneau
      </button>
      <div className="cal-pan-degrade" style={{ background: degrade(), opacity: carte?.active ? 1 : 0.45 }} />
      <div className="cal-pan-legende-bornes"><span>Ombragé</span><span>Plein soleil</span></div>
      {carte && !carte.active && <p className="cal-pan-legende-note">Touchez le titre pour colorer les panneaux.</p>}
    </CarteFlottante>
  )
}

function LecteurSoleil({ soleil, g }) {
  const { heure, date, saison, lecture } = soleil
  const jour = jourMois(date)
  const quand = [jour, heure == null ? '' : `${heure} h`].filter(Boolean).join(' · ')
  return (
    <CarteFlottante className="cal-pan-lecteur">
      <button type="button" className="cal-pan-lecture" aria-label="Lire la journée" aria-pressed={!!lecture?.active}
        disabled={!lecture} onClick={g.lecture}>
        <Icone nom="lecture" taille={18} />
      </button>
      <div className="cal-pan-curseur">
        <div className="cal-pan-curseur-tete"><span>6 h</span><strong>{quand}</strong><span>18 h</span></div>
        <input type="range" min="6" max="18" step="1" className="rp9-range" value={heure ?? 12}
          disabled={heure == null} aria-label="Heure du soleil"
          onChange={(e) => g.heure(e.target.value)} />
      </div>
      <Segmente libelle="Saison" grand valeur={saison}
        options={[{ valeur: 'winter', libelle: 'Hiver' }, { valeur: 'summer', libelle: 'Été' }]}
        onChange={g.saison} />
    </CarteFlottante>
  )
}

export default function EtapePanneaux({ calepinageId, lectureSeule = false }) {
  const [etat, rafraichir] = useConstructeur()
  // Chaque geste part au vrai contrôle, puis la lecture est refaite tout de suite (sinon elle suit 0,4 s plus tard).
  const g = Object.fromEntries(Object.entries(gestes).map(([nom, geste]) => [
    nom, (...args) => { geste(...args); rafraichir() },
  ]))
  const entrees = useCatalogue(calepinageId)
  const leadId = useLeadId(calepinageId)
  return (
    <div className="cal-pan">
      <ChoixModule etat={etat} entrees={entrees} lectureSeule={lectureSeule} g={g} />
      <CombienDePanneaux etat={etat} leadId={leadId} lectureSeule={lectureSeule} g={g} />
      <section className="cal-pan-section">
        <h2 className="cal-pan-titre">Sens de pose</h2>
        <div data-testid="cal-panneaux-sens-pose">
          <Segmente libelle="Sens de pose" grand className="cal-segmente-pose" options={SENS_DE_POSE}
            valeur={etat.orientation} onChange={(v) => { if (v !== etat.orientation) g.orientation(v) }} />
        </div>
      </section>
      <AlerteOmbre key={etat.ombre?.n ?? 0} ombre={etat.ombre} g={g} />
      <SurCarte>
        <PuceResume figures={etat.figures} />
        <div className="cal-carte-soleil" data-testid="cal-carte-soleil">
          <LegendeSoleil carte={etat.soleil.carte} g={g} />
          <LecteurSoleil soleil={etat.soleil} g={g} />
        </div>
      </SurCarte>
    </div>
  )
}
