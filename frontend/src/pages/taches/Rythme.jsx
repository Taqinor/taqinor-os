import { useCallback, useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ChevronDown, ChevronUp, Minus, Plus } from 'lucide-react'
import {
  annulerGeste, classerErreur, lireRythme, modifierReglages, poserMode, poserPreference, repondreProposition,
  lireAujourdhui } from '../../api/tachesApi'
import { EVENEMENT_OUVRIR } from '../../features/ia/copilotMessages'
import { frenchError } from '../../lib/frenchError'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { useGeste } from '../../features/taches/lib/gestes'
import { ABR_JOURS, accord, aujourdhuiIso, jourNomme } from '../../features/taches/lib/textes'
import MesJours from '../../features/taches/rythme/MesJours'
import InterrupteurRythme from '../../features/taches/ui/InterrupteurRythme'

/* ============================================================================
   TCH107 — Écran « Mon rythme » (route /taches/rythme, atteignable par la ligne de progression
   d'Aujourd'hui et par le menu ⋯) : aujourd'hui, objectif et sa source, la proposition de rythme,
   les 10 derniers jours travaillés, ce que j'ai remarqué, les 3 modes, Mes jours (replié),
   Comprendre mon rythme (replié), « Parler de mon rythme ». Tout vient de `GET rythme/` (RYTHME,
   `contract_samples/rythme.json`) ; chaque geste renvoie le RYTHME à jour (aucune relecture de la
   page) et pose son toast « … · Annuler » (`lib/gestes`). Un échec de lecture garde l'écran et
   dit « Pas à jour » ; une erreur de geste s'affiche sous le champ fautif.
   Textes : textes.md §2.11, §4.1, §4.2, §4.4. Maquettes : rythme.html, premier-usage-4-rythme.html.
   ========================================================================== */

const MODES = [
  ['pousser', 'En faire plus', "Un objectif, et je te propose d'aller plus loin quand tu le tiens."],
  ['tenir', 'Garder ce rythme', "Je ne te pousse plus ; je te préviens si tu t'en éloignes."],
  ['libre', 'Sans objectif', 'Pas de nombre visé ; tes faites restent affichées.'],
]
/** R3-089 (M6) — la source de l'objectif n'est dite que lorsqu'elle compte pour Reda : la valeur par défaut, pas encore
 *  calculée sur lui. « (accepté) », « (ta journée type) », « (ton choix) » étaient du vocabulaire du système. */
const SOURCE_DITE = { defaut: 'valeur par défaut, pas encore calculée sur toi' }
const COMPRENDRE = "Allumé : l'ERP calcule ton rythme et tes habitudes à partir de tes tâches. Éteint : plus rien n'est calculé ni gardé."
const COMPRENDRE_ETEINT = "C'est éteint : plus rien n'est calculé ni gardé sur ton rythme."
const JOURS_VOULUS = 10
/** Jours évalués qu'il faut pour FIXER la référence de « Garder ce rythme » (regles.md §6.6, `JOURS_REFERENCE`). */
const JOURS_REFERENCE = 14
/** Jours évalués à partir desquels « Garder ce rythme » mesure le pas réel (regles.md §6.6, R3-004) ; lus dans la série
 *  servie (les 10 derniers jours travaillés). */
const JOURS_MESURE = 5
const A_CONFIRMER = `à confirmer sur ${JOURS_REFERENCE} jours travaillés.`
const OBJECTIF_INVALIDE = 'Entre 1 et 12.'

const messageErreur = (err, champ) => {
  const brut = err?.response?.data?.[champ]
  return Array.isArray(brut) && brut.length > 0 ? String(brut[0]) : frenchError(err, 'Réessaie dans un instant.')
}

const entier = (n) => String(n).replace('.', ',')

function phraseObjectif(objectif) {
  if (objectif.mode === 'libre' || objectif.nb == null) return 'Sans objectif'
  if (objectif.mode === 'tenir' && Array.isArray(objectif.zone)) {
    return `Ton rythme : environ ${accord(objectif.nb, 'tâche')} (${objectif.zone[0]} à ${objectif.zone[1]})`
  }
  const source = SOURCE_DITE[objectif.source]
  return source ? `Objectif du jour : ${objectif.nb} (${source})` : `Objectif du jour : ${objectif.nb}`
}

/** R3-089 — le toast d'un changement de mode ou d'objectif tient en une ligne (« Objectif : 6 · Annuler », « Garder ce
 *  rythme : 4 à 5 · Annuler ») ; ce que le mode fait est écrit dans la PAGE, sous chaque mode (`MODES`), et le
 *  « provisoire » de Garder ce rythme sous l'objectif — plus jamais un toast de sept lignes. */
function confirmation(rythme) {
  const { objectif } = rythme
  if (rythme.mode === 'libre' || objectif.nb == null) return 'Sans objectif'
  if (rythme.mode === 'tenir') {
    const [bas, haut] = objectif.zone ?? [objectif.nb, objectif.nb]
    return `Garder ce rythme : ${bas} à ${haut}`
  }
  return `Objectif : ${objectif.nb}`
}

function BandeauPasAJour({ onReessayer }) {
  return (
    <div className="bandeau" role="status">
      <span className="bandeau-texte">
        <span className="bandeau-titre">Pas à jour</span>
      </span>
      <button type="button" className="bouton lien" onClick={onReessayer}>Réessayer</button>
    </div>
  )
}

/* Le jour COURANT n'est pas dans `RYTHME.serie` (elle ne porte que les jours travaillés déjà évalués par la nuit) :
   « {faites} sur {objectif} aujourd'hui · essentiel {ef}/{ep} » (textes.md §2.11) se lit dans la progression du jour,
   là où Aujourd'hui la lit. L'écran la cherchait dans la série et ne l'y trouvait jamais : la ligne n'apparaissait pas. */
function Aujourdhui({ rythme, progression }) {
  const { objectif } = rythme
  if (!progression) return null
  const jour = {
    faites: progression.faites ?? 0,
    essentiel_faites: progression.essentiel_faites ?? 0,
    essentiel_prevues: progression.essentiel_prevues ?? 0,
  }
  const visees = objectif.nb ?? 0
  const segments = Math.max(visees, jour.faites)
  return (
    <div className="ep-jour">
      <div className="ep-jour-ligne">
        <span className="ep-jour-chiffre chiffres">
          {objectif.nb == null
            ? <>{jour.faites} <small>{`${jour.faites >= 2 ? 'faites' : 'faite'} aujourd'hui`}</small></>
            : <>{jour.faites} <small>{`sur ${objectif.nb} aujourd'hui`}</small></>}
        </span>
        {jour.essentiel_prevues > 0 ? (
          <span className="ep-jour-detail chiffres">{`essentiel ${jour.essentiel_faites}/${jour.essentiel_prevues}`}</span>
        ) : null}
      </div>
      <span className="segments plein" aria-hidden="true">
        {Array.from({ length: segments }, (_, i) => <i key={i} className={i < jour.faites ? 'fait' : ''} />)}
      </span>
    </div>
  )
}

function Proposition({ proposition, onRepondre, erreur }) {
  if (!proposition || !Array.isArray(proposition.boutons) || proposition.boutons.length === 0) return null
  return (
    <div className="carte ep-proposition">
      <p className="carte-texte">{proposition.texte}</p>
      <div className="carte-actions">
        {proposition.boutons.map((bouton, rang) => (
          <button
            key={bouton.reponse}
            type="button"
            className={`bouton ${rang === 0 ? 'second' : 'discret'}`}
            onClick={() => onRepondre(proposition, bouton.reponse)}
          >
            {bouton.libelle}
          </button>
        ))}
      </div>
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
    </div>
  )
}

function ChangerObjectif({ onChanger }) {
  const [choix, setChoix] = useState(false)
  const [saisie, setSaisie] = useState('')
  const [erreur, setErreur] = useState('')

  const valider = async () => {
    const nombre = Number(saisie.trim())
    if (!saisie.trim() || !Number.isInteger(nombre) || nombre < 1 || nombre > 12) { setErreur(OBJECTIF_INVALIDE); return }
    setErreur('')
    try { await onChanger({ objectif: nombre }, 'nombre'); setChoix(false); setSaisie('') } catch (err) {
      setErreur(messageErreur(err, 'objectif'))
    }
  }
  const pas = async (sens) => {
    setErreur('')
    try { await onChanger({ sens }, sens) } catch (err) { setErreur(messageErreur(err, 'objectif')) }
  }

  // Passe visuelle n° 44 — rythme.html n'a pas de section « Objectif du jour » : l'objectif est la ligne en gras au-dessus ;
  // « Plus · Moins · Choisir un nombre » (textes.md §2.11, « Changer d'objectif ») restent, en une rangée sous elle.
  return (
    <div className="ep-changer-objectif" role="group" aria-label="Changer d'objectif">
      <div className="puces ep-puces">
        <button type="button" className="puce" onClick={() => pas('moins')}>
          <Minus className="i i-16" aria-hidden="true" />Moins
        </button>
        <button type="button" className="puce" onClick={() => pas('plus')}>
          <Plus className="i i-16" aria-hidden="true" />Plus
        </button>
        <button type="button" className="puce" aria-expanded={choix} onClick={() => setChoix(!choix)}>
          Choisir un nombre (1 à 12)
        </button>
      </div>
      {choix ? (
        <div className="ep-champs ep-champs-objectif">
          <input
            className="es-champ"
            type="text"
            inputMode="numeric"
            autoComplete="off"
            aria-label="Objectif du jour"
            aria-describedby="err-objectif"
            aria-invalid={Boolean(erreur) || undefined}
            value={saisie}
            onChange={(e) => setSaisie(e.target.value)}
          />
          <button type="button" className="bouton second" onClick={valider}>OK</button>
        </div>
      ) : null}
      {erreur ? <p id="err-objectif" className="es-erreur" role="alert">{erreur}</p> : null}
    </div>
  )
}

/** « lun. 9 » : le jour de la semaine ÉCRIT (une lettre confond mardi et mercredi) et le quantième. */
const nomDuJour = (iso) => {
  const date = new Date(`${iso}T12:00:00Z`)
  return `${ABR_JOURS[date.getUTCDay()]} ${date.getUTCDate()}`
}

function Graphique({ rythme, aujourdhui }) {
  const { serie, objectif, trace } = rythme
  // R3-003 / C-21 (contrat L1) — un jour NON travaillé où il a quand même fait quelque chose (un samedi) est servi avec
  // `hors_objectif` : une barre grise à sa date, comptée dans les faites de la période, jamais dans « N jours sur 10 »
  // (`trace`, servi) ni comparée à l'objectif
  const hors = (s) => Boolean(s.hors_objectif)
  const evalues = serie.filter((s) => s.statut_jour === 'evalue')
  const total = [...evalues, ...serie.filter(hors)].reduce((somme, s) => somme + s.faites, 0)
  const ferie = serie.filter((s) => !hors(s) && (s.statut_jour === 'non_ouvre' || s.statut_jour === 'conge'))
  const barres = serie.filter((s) => s.statut_jour === 'evalue' || s.statut_jour === 'sans_donnees' || hors(s))
  const vide = (s) => s.statut_jour === 'sans_donnees'
  const lecture = `Tâches faites, jour par jour travaillé : ${barres
    .map((s) => `${nomDuJour(s.jour)} : ${vide(s) ? 'sans données' : s.faites}${hors(s) ? ' (hors objectif)' : ''}`).join(', ')}.`
  const sansDonnees = barres.filter(vide).map((s) => nomDuJour(s.jour))
  const horsObjectif = barres.filter(hors).map((s) => nomDuJour(s.jour))
  const reste = ferie.map((s) => `${jourNomme(s.jour, aujourdhui)} : ${s.statut_jour === 'conge' ? 'congé' : 'férié'}`)
  if (sansDonnees.length > 0) reste.push(`Sans données : ${sansDonnees.join(', ')}`)
  if (horsObjectif.length > 0) reste.push(`Hors objectif : ${horsObjectif.join(', ')}`)
  return (
    <section className="section">
      <h2 className="section-titre">
        <span>{`Les ${JOURS_VOULUS} derniers jours travaillés`}</span>
        <span className="compte chiffres">{`${total} faites`}</span>
      </h2>
      <div className="ep-graph" role="img" aria-label={`${lecture} ${trace}.`}>
        <div className="ep-graph-zone">
          {objectif.nb != null ? (
            <div className="ep-graph-objectif" style={{ '--obj': objectif.nb }}><span>{`obj. ${objectif.nb}`}</span></div>
          ) : null}
          <div className="ep-graph-sem">
            {barres.map((s) => (
              <div
                key={s.jour}
                data-jour={s.jour}
                data-vide={vide(s) ? '' : undefined}
                data-hors-objectif={hors(s) ? '' : undefined}
                className={`ep-b${!hors(s) && s.objectif != null && s.faites >= s.objectif ? ' tenu' : ''}`}
                style={{ '--n': s.faites }}
              >
                <small className="chiffres">{vide(s) ? '–' : s.faites}</small><i />
              </div>
            ))}
          </div>
        </div>
        <div className="ep-graph-axe" aria-hidden="true">
          <div className="ep-graph-sem">
            {barres.map((s) => {
              const date = new Date(`${s.jour}T12:00:00Z`)
              return (
                <div key={s.jour} className="ep-b" data-hors-objectif={hors(s) ? '' : undefined}>
                  {/* un jour hors objectif n'écrit rien sous sa colonne étroite (la légende et la lecture le nomment) ; le
                      jour écrit sans point (« mar »), pour que 14 colonnes tiennent sur iPhone sans se toucher */}
                  {hors(s) ? <small>{' '}<b>{' '}</b></small> : (
                    <small>{ABR_JOURS[date.getUTCDay()].replace('.', '')}<b className="chiffres">{date.getUTCDate()}</b></small>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
      <p className="ep-graph-legende">{[trace, ...reste].filter(Boolean).join(' · ')}</p>
    </section>
  )
}

function Constats({ constats, onRepondre }) {
  return (
    <section className="section">
      <h2 className="section-titre"><span>Ce que j'ai remarqué</span></h2>
      {constats.length === 0 ? <p className="ep-source">Rien de remarqué pour l'instant.</p> : (
        <ul className="ep-remarque">
          {/* R3-088 — le texte servi porte déjà sa question (« … Les revoir maintenant ? », gabarits `_constat`) : on le rend
              tel quel, puis TOUS les boutons servis (« Oui · Pas maintenant »), comme la carte du moment. La question
              n'est plus écrite une seconde fois sur un bouton unique. */}
          {constats.map((constat) => (
            <li key={constat.id}>
              <span aria-hidden="true" />
              <span>
                {constat.texte}
                {(constat.boutons ?? []).length > 0 ? (
                  <span className="ep-remarque-reponses">
                    {constat.boutons.map((bouton) => (
                      <button key={bouton.reponse} type="button" className="action-lien" onClick={() => onRepondre(constat, bouton.reponse)}>
                        {bouton.libelle}
                      </button>
                    ))}
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Modes({ mode, onChoisir }) {
  return (
    <section className="section">
      <h2 className="section-titre"><span>Mode</span></h2>
      <div className="ep-modes" role="radiogroup" aria-label="Mode du rythme">
        {MODES.map(([valeur, libelle, aide]) => (
          <button
            key={valeur}
            type="button"
            className="ep-mode"
            role="radio"
            aria-checked={mode === valeur}
            onClick={() => (mode === valeur ? null : onChoisir(valeur))}
          >
            <span className="radio" aria-hidden="true" />
            <span><b>{libelle}</b><span>{aide}</span></span>
          </button>
        ))}
      </div>
    </section>
  )
}

function Replie({ titre, children }) {
  const [ouvert, setOuvert] = useState(false)
  const Chevron = ouvert ? ChevronUp : ChevronDown
  return (
    <>
      <button type="button" className="replie" aria-expanded={ouvert} onClick={() => setOuvert(!ouvert)}>
        <span>{titre}</span><Chevron className="i i-16" aria-hidden="true" />
      </button>
      {ouvert ? <div className="ep-replie-corps">{children}</div> : null}
    </>
  )
}

function Comprendre({ allume, onBasculer, erreur }) {
  return (
    <div className="es-reglage">
      <span className="txt"><b>Comprendre mon rythme</b><small>{COMPRENDRE}</small></span>
      <InterrupteurRythme allume={allume} onBasculer={onBasculer} />
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
    </div>
  )
}

function Corps({ rythme, progression, aujourdhui, erreurs, actions }) {
  const avantDixJours = rythme.objectif.source === 'defaut'
    && rythme.serie.filter((s) => s.statut_jour === 'evalue').length < JOURS_VOULUS
  const evalues = rythme.serie.filter((s) => s.statut_jour === 'evalue').length
  return (
    <div className="ep-grille-rythme">
      <div>
        <Aujourdhui rythme={rythme} progression={progression} />
        <p className="ep-source"><b>{phraseObjectif(rythme.objectif)}</b></p>
        {rythme.mode === 'tenir' && rythme.tenir?.provisoire ? (
          <p className="ep-source">
            {/* R3-004 (C-15, contrat L1) — dès 5 jours évalués, R part du pas réel (provisoire) ; en dessous, le palier
                est gardé, et la page le dit franchement (textes.md « Garder ce rythme ») */}
            {evalues < JOURS_MESURE
              ? `Pas encore assez de jours pour mesurer ton rythme : je garde ${rythme.objectif.nb} pour l'instant.`
              : `Provisoire : ${A_CONFIRMER}`}
          </p>
        ) : null}
        {rythme.mode === 'pousser' ? <ChangerObjectif onChanger={actions.changerObjectif} /> : null}
        {avantDixJours ? (
          <div className="es-attente-rythme">
            <p>{`${evalues} jour${evalues >= 2 ? 's' : ''} sur ${JOURS_VOULUS} : il m'en faut ${JOURS_VOULUS} pour comprendre ton rythme.`}</p>
          </div>
        ) : null}
        <Proposition proposition={rythme.proposition} onRepondre={actions.repondre} erreur={erreurs.proposition} />
        {evalues > 0 ? <Graphique rythme={rythme} aujourdhui={aujourdhui} /> : null}
        {rythme.repere ? (
          <p className="ep-source">
            {`Repère : 6 de tes journées sur 10 sont à ${entier(rythme.repere.p60)} tâches ou moins (sur ${rythme.repere.jours} jours).`}
          </p>
        ) : null}
      </div>
      <div>
        <Constats constats={rythme.constats} onRepondre={actions.repondre} />
        <Modes mode={rythme.mode} onChoisir={actions.changerMode} />
        <Replie titre="Mes jours">
          <MesJours preferences={rythme.preferences} joursTravailles={rythme.jours_travailles} onPoser={actions.poserPreference} aujourdhui={aujourdhui} />
        </Replie>
        <Replie titre="Comprendre mon rythme">
          <Comprendre allume={rythme.comprendre_mon_rythme} onBasculer={actions.comprendre} erreur={erreurs.comprendre} />
        </Replie>
        <button type="button" className="bouton discret ep-parler" onClick={actions.parler}>Parler de mon rythme</button>
        {erreurs.mode ? <p className="es-erreur" role="alert">{erreurs.mode}</p> : null}
      </div>
    </div>
  )
}

export default function Rythme({ aujourdhui = aujourdhuiIso() }) {
  const { pathname } = useLocation()
  const geste = useGeste()
  const [rythme, setRythme] = useState(null)
  const [progression, setProgression] = useState(null)
  const [echec, setEchec] = useState(false)
  const [lent, setLent] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [essai, setEssai] = useState(0)

  useEffect(() => {
    let actif = true
    const minuteur = setTimeout(() => { if (actif) setLent(true) }, 1000)
    lireRythme()
      .then((reponse) => { if (actif) { setRythme(reponse.data); setEchec(false) } })
      .catch(() => { if (actif) setEchec(true) })
    // la progression du jour : un supplément — si elle ne vient pas, la ligne « aujourd'hui » manque, le reste s'affiche
    lireAujourdhui()
      .then((reponse) => { if (actif) setProgression(reponse.data?.progression ?? null) })
      .catch(() => { if (actif) setProgression(null) })
    return () => { actif = false; clearTimeout(minuteur) }
  }, [essai])

  const recharger = useCallback(() => setEssai((n) => n + 1), [])
  const poserErreur = (champ, texte) => setErreurs((anciennes) => ({ ...anciennes, [champ]: texte }))

  /** Remplace le RYTHME par la réponse du serveur et pose le toast « … · Annuler ». */
  const adopter = useCallback((donnees, message) => {
    setRythme(donnees)
    if (message) {
      const id = donnees.geste_id
      geste.proposerAnnuler({
        message,
        onAnnuler: id ? async () => { await annulerGeste(id); recharger() } : undefined,
      })
    }
  }, [geste, recharger])

  const actions = {
    repondre: async (carte, reponse) => {
      poserErreur('proposition', '')
      try {
        const { data } = await repondreProposition(carte.id, { reponse })
        const palier = carte.type === 'proposition_palier' && reponse === 'oui'
        adopter(data.rythme, palier ? confirmation(data.rythme, 'nombre') : null)
      } catch (err) {
        if (classerErreur(err).code === 'proposition_expiree') { poserErreur('proposition', 'Cette proposition a expiré.'); recharger() } else {
          poserErreur('proposition', messageErreur(err, 'reponse'))
        }
      }
    },
    changerObjectif: async (corps, sorte) => {
      const { data } = await poserMode({ mode: 'pousser', ...corps })
      adopter(data, confirmation(data, sorte))
    },
    changerMode: async (mode) => {
      poserErreur('mode', '')
      try {
        const { data } = await poserMode({ mode })
        adopter(data, confirmation(data, null))
      } catch (err) { poserErreur('mode', messageErreur(err, 'mode')) }
    },
    poserPreference: async (cle, valeur) => {
      const { data } = await poserPreference({ cle, valeur })
      adopter(data, null)
    },
    comprendre: async (allume) => {
      poserErreur('comprendre', '')
      try {
        await modifierReglages({ comprendre_mon_rythme: allume })
        setRythme((actuel) => ({ ...actuel, comprendre_mon_rythme: allume }))
        if (!allume) geste.annoncer(COMPRENDRE_ETEINT)
        recharger()
      } catch (err) { poserErreur('comprendre', messageErreur(err, 'comprendre_mon_rythme')) }
    },
    parler: () => window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: pathname, question: 'Parler de mon rythme', envoyer: false },
    })),
  }

  return (
    <CoquilleTaches ecran="rythme" titre="Mon rythme">
      {echec ? <BandeauPasAJour onReessayer={recharger} /> : null}
      {rythme ? <Corps rythme={rythme} progression={progression} aujourdhui={aujourdhui} erreurs={erreurs} actions={actions} /> : null}
      {!rythme && !echec && lent ? <p className="ep-source" role="status">Chargement</p> : null}
    </CoquilleTaches>
  )
}
