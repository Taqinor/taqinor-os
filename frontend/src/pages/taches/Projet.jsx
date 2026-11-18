import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ChevronDown, Diamond, TriangleAlert } from 'lucide-react'
import {
  annulerGeste, classerErreur, modifierProjet, modifierTache, restaurerProjet, rouvrirProjet,
  rouvrirTache, terminerTache, listerToutesLesTaches, lireVueProjet } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import BarreRetourProjets from '../../features/taches/ui/BarreRetourProjets'
import CoquilleTaches, { EVENEMENT_SAISIR } from '../../features/taches/coquille/CoquilleTaches'
import { useApresCreation, useOuvrirFiche } from '../../features/taches/lib/fiche'
import { PuchePriorite, avancementDe } from '../../features/taches/projets/LigneProjet'
import {
  DialogueDecaler, DialogueEnregistrerModele, DialogueSupprimer, DialogueTerminer, DialogueUtiliser,
} from '../../features/taches/projets/Dialogues'
import { naviguerApresFeuille } from '../../features/taches/ui/FeuilleACrans'
import PlanifierProjet from '../../features/taches/projets/PlanifierProjet'
import VueListe from '../../features/taches/projets/VueListe'
import VueChronologie, { Burnup } from '../../features/taches/projets/VueChronologie'
import FeuilleACrans from '../../features/taches/ui/FeuilleACrans'
import SelecteurVue from '../../features/taches/ui/SelecteurVue'
import Tableau from '../../features/taches/ui/Tableau'
import { CODES_VUES, compteursApresDeplacement, compteursApresStatut, nomsDesEtapes } from '../../features/taches/lib/projets'
import ChargementTardif from '../../features/taches/ui/ChargementTardif'
import { useActionsLigne } from '../../features/taches/ui/ActionsLigne'
import { annoncer, proposerAnnuler } from '../../features/taches/lib/gestes'
import { annulerEtRecaler, versionDe } from '../../features/taches/lib/versions'
import { accord, aujourdhuiIso, jourCourt } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH89 — Écran « Un projet », vue Liste (`/taches/projets/:id`). Maquette : docs/taches/maquettes/projet-liste.html.
   Textes : reference/textes.md §2.6 (« {faites} sur {total} · échéance {jj/mm} », « Prochain jalon : {titre} · {jour} »,
   santé si signal, Détails « Fini quand : {objectif} » · « dernière faite le {jj/mm} »). Contrat : `projet_vue.json`.
   TCH90 (fusion F4, l'avancé replié) — Tableau et Chronologie se choisissent au sélecteur discret (`?vue=`), la
   dernière vue est MÉMORISÉE côté serveur (`projet.affichage.vue`, PATCH) ; « Avancement par semaine » (burn-up)
   est dans le ⋯. Une vue simple reste la Liste : rien de l'avancé ne s'ajoute d'emblée.
   Un geste (cocher, ajouter, priorité, pause) met l'écran à jour sur place et ne relit jamais la vue entière.
   ========================================================================== */

const jjmm = (iso) => {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(String(iso ?? ''))
  return m ? `${m[2]}/${m[1]}` : ''
}

/** Remplace une tâche partout dans la vue (sections et « Sans étape »). */
function remplacerTache(vue, tache) {
  const maj = (liste) => (liste ?? []).map((t) => (t.id === tache.id ? { ...t, ...tache } : t))
  return { ...vue, sections: (vue.sections ?? []).map((s) => ({ ...s, taches: maj(s.taches) })), sans_section: maj(vue.sans_section) }
}

/** Où est la tâche (étape, rang) : de quoi la remettre à sa place après un « Annuler ». */
function placeDe(vue, id) {
  for (const s of vue.sections ?? []) {
    const rang = (s.taches ?? []).findIndex((t) => t.id === id)
    if (rang >= 0) return { sectionId: s.id, rang, tache: s.taches[rang] }
  }
  const rang = (vue.sans_section ?? []).findIndex((t) => t.id === id)
  return rang >= 0 ? { sectionId: null, rang, tache: vue.sans_section[rang] } : null
}

const sansTache = (vue, id) => ({
  ...vue,
  sections: (vue.sections ?? []).map((s) => ({ ...s, taches: (s.taches ?? []).filter((t) => t.id !== id) })),
  sans_section: (vue.sans_section ?? []).filter((t) => t.id !== id),
})

function remettreTache(vue, place) {
  if (!place) return vue
  const inserer = (liste) => { const suite = [...(liste ?? [])]; suite.splice(Math.min(place.rang, suite.length), 0, place.tache); return suite }
  if (place.sectionId == null) return { ...vue, sans_section: inserer(vue.sans_section) }
  return { ...vue, sections: (vue.sections ?? []).map((s) => (s.id === place.sectionId ? { ...s, taches: inserer(s.taches) } : s)) }
}

/** Place la tâche `item` à la fin de l'étape `sectionId` (null : « Sans étape »), où qu'elle soit. */
function versEtape(vue, item, sectionId) {
  const origine = placeDe(vue, item.id)
  const sans = sansTache(vue, item.id)
  const place = sectionId == null
    ? { ...sans, sans_section: [...(sans.sans_section ?? []), item] }
    : { ...sans, sections: (sans.sections ?? []).map((s) => (s.id === sectionId ? { ...s, taches: [...(s.taches ?? []), item] } : s)) }
  // les compteurs des deux étapes suivent la carte (règle du serveur : lib/projets.js `compteursApresDeplacement`)
  return origine ? compteursApresDeplacement(place, origine.tache, origine.sectionId, sectionId) : place
}

function Entete({ vue, aujourdhui, onPriorite }) {
  const [details, setDetails] = useState(false)
  const { projet, avancement, prochain_jalon: jalon } = vue
  const { texte, part } = avancementDe({ compteurs: { faites: avancement.faites, ouvertes: avancement.total - avancement.faites } })
  const sante = projet.sante?.[0]?.phrase
  const jalonJour = jalon ? (jalon.jour_prevu ?? jalon.echeance) : null
  return (
    <div className="ep-tete" data-p={projet.couleur}>
      <div className="ep-ligne-info">
        <PuchePriorite projet={projet} onChoisir={onPriorite} />
        <span className="chiffres">{`${texte}${projet.echeance ? ` · échéance ${jjmm(projet.echeance)}` : ''}`}</span>
      </div>
      <div className="ep-avance">
        <div className="ep-barre-avance" role="img" aria-label={texte}><i style={{ '--avance': part.toFixed(3) }} /></div>
        {jalon ? (
          <span className="ep-jalon-proche">
            <Diamond className="i i-14 ep-losange" aria-hidden="true" />
            {`Prochain jalon : ${jalon.titre}${jalonJour ? ` · ${jourCourt(jalonJour, aujourdhui)}` : ''}`}
          </span>
        ) : null}
      </div>
      {sante ? (
        <p className="ep-sante-ligne surveiller">
          <TriangleAlert className="i i-14" aria-hidden="true" /><span>{sante}</span>
        </p>
      ) : null}
      <button type="button" className="ep-details" aria-expanded={details} onClick={() => setDetails((o) => !o)}>
        <b>Détails</b>
        <ChevronDown className="i i-16" aria-hidden="true" />
      </button>
      {details ? (
        <div className="ep-details-corps">
          {projet.objectif ? (
            <p>{/^fini quand/i.test(projet.objectif) ? projet.objectif : `Fini quand : ${projet.objectif}`}</p>
          ) : null}
          {avancement.derniere_faite_le ? <p className="chiffres">{`dernière faite le ${jjmm(avancement.derniere_faite_le)}`}</p> : null}
        </div>
      ) : null}
    </div>
  )
}

export default function Projet() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const planifier = params.get('planifier') === '1'
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const [vue, setVue] = useState(null)
  const [erreur, setErreur] = useState('')
  const [introuvable, setIntrouvable] = useState(false)
  const [dialogue, setDialogue] = useState(null)
  const projetRef = useRef(null)
  const chaineVue = useRef(Promise.resolve())

  const charger = useCallback(async () => {
    try {
      const { data } = await lireVueProjet(id, { vue: 'liste' })
      setVue(data)
      setErreur('')
      setIntrouvable(false)
    } catch (err) {
      if (classerErreur(err).code === 'introuvable') setIntrouvable(true)
      else setErreur(frenchError(err, 'Le projet n\'a pas pu être chargé. Réessaie.'))
    }
  }, [id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'écran (D-ENF22)
  useEffect(() => { charger() }, [charger])

  // Le dernier projet lu (verrou de version) : les écritures de vue en file le relisent ici.
  useEffect(() => { projetRef.current = vue?.projet ?? null })

  // La vue montrée : celle de l'adresse (`?vue=`), sinon la dernière MÉMORISÉE par le serveur (`affichage.vue`), sinon Liste.
  const vueUrl = params.get('vue')
  const vueCode = CODES_VUES.includes(vueUrl) ? vueUrl : (CODES_VUES.includes(vue?.projet?.affichage?.vue) ? vue.projet.affichage.vue : 'liste')

  // Choisir une vue la mémorise (`affichage.vue`, PATCH sous verrou) ; les écritures se suivent une à une (la version change à chacune).
  const memoriserVue = (code) => {
    chaineVue.current = chaineVue.current.then(async () => {
      const projet = projetRef.current
      if (!projet || projet.affichage?.vue === code) return // déjà mémorisée : rien à écrire
      const affichage = { ...(projet.affichage ?? {}), vue: code }
      setVue((v) => (v ? { ...v, projet: { ...v.projet, affichage } } : v))
      try {
        const { data } = await modifierProjet(projet.id, { affichage, lock_version: projet.lock_version })
        setVue((v) => (v ? { ...v, projet: { ...v.projet, ...data } } : v))
      } catch (err) {
        setVue((v) => (v ? { ...v, projet } : v))
        setErreur(frenchError(err, 'La vue n\'a pas été mémorisée. Réessaie.'))
      }
    })
  }
  const choisirVue = (code) => {
    if (code !== vueUrl) setParams((p) => { const s = new URLSearchParams(p); s.set('vue', code); return s }, { replace: true })
    memoriserVue(code) // sans effet si le serveur la garde déjà
  }

  const majTache = (tache) => setVue((v) => (v ? remplacerTache(v, tache) : v))
  // L'avancement du projet ET le compteur de l'étape de la carte suivent le geste (même règle que le serveur).
  const ajusterFaites = (delta, item) => setVue((v) => {
    if (!v) return v
    const suite = { ...v, avancement: { ...v.avancement, faites: v.avancement.faites + delta } }
    const place = item ? placeDe(v, item.id) : null
    return place ? compteursApresStatut(suite, place.tache, place.sectionId, delta > 0) : suite
  })

  const terminer = async (item, suivant) => {
    const { data } = suivant ? await terminerTache(item.id) : await rouvrirTache(item.id)
    majTache(data.tache ?? { ...item, statut: suivant ? 'fait' : 'a_faire' })
    ajusterFaites(suivant ? 1 : -1, item)
    if (suivant) {
      proposerAnnuler({
        message: 'Faite',
        annonce: `Fait : ${item.titre}`,
        onAnnuler: async () => {
          const retour = await rouvrirTache(item.id)
          majTache(retour.data.tache ?? { ...item, statut: 'a_faire' })
          ajusterFaites(-1, item)
        },
      })
    }
  }

  // Raccord F2 — « + » (coquille) et « Ajouter une tâche » (étape) ouvrent LA feuille de saisie avec ce projet
  // (et cette étape) en contexte ; après la création, la vue se relit une fois (sans recharger la page).
  const contexteSaisie = useMemo(() => (vue ? { projet_id: vue.projet.id, projet_nom: vue.projet.nom } : null), [vue])
  const ajouter = (sectionId) => {
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: { ...contexteSaisie, section_id: sectionId } }))
  }
  useApresCreation(useCallback(() => { charger() }, [charger]))
  const ouvrirFiche = useOuvrirFiche()
  // « Faites (n) » déplié : toutes les pages des faites du projet, dernières faites d'abord (lue à la demande)
  const chargerFaites = useCallback(() => listerToutesLesTaches({ projet: Number(id), statut: 'fait', tri: 'fait_le' }), [id])

  // Raccord F2 — le gestionnaire commun des actions de ligne (Choisir un jour, En réserve, Déplacer, En attente de,
  // Priorité, ★, Supprimer) : optimiste, annulable, sans relire la vue. Déplacée hors du projet, la ligne part.
  const actions = useActionsLigne({
    aujourdhui,
    maj: (id, champs) => setVue((v) => (v ? remplacerTache(v, { id, ...champs }) : v)),
    retirer: (item) => {
      let place = null
      setVue((v) => { place = v ? placeDe(v, item.id) : null; return v ? sansTache(v, item.id) : v })
      return () => setVue((v) => (v ? remettreTache(v, place) : v))
    },
    sortApres: (code, item, valeurs) => code === 'deplacer' && valeurs.projet_id !== Number(id),
  })

  // Tableau — la carte change d'étape : la colonne bouge à l'instant, le serveur confirme (verrou de la tâche),
  // « Annuler » la remet ; un échec la ramène d'où elle vient. La vue n'est jamais relue.
  const deplacerVersEtape = async (item, sectionId) => {
    const avant = vue
    const nom = sectionId == null ? 'Sans étape' : (avant.sections ?? []).find((s) => s.id === sectionId)?.nom ?? 'Étape'
    setVue((v) => (v ? versEtape(v, item, sectionId) : v))
    try {
      const { data } = await modifierTache(item.id, { section_id: sectionId, lock_version: item.lock_version })
      majTache(data.tache ?? { ...item })
      proposerAnnuler({
        message: `Déplacée dans « ${nom} »`,
        onAnnuler: async () => {
          // « Annuler » change la version de la tâche côté serveur : la carte remise garde celle que le serveur rend
          const retour = data.geste_id ? await annulerEtRecaler(data.geste_id, [item.id]) : null
          const remise = { ...item, lock_version: versionDe(retour, item.id, item.lock_version) }
          setVue((v) => (v ? versEtape(v, remise, placeDe(avant, item.id)?.sectionId ?? null) : v))
        },
      })
    } catch (err) {
      setVue(avant)
      setErreur(frenchError(err, 'La tâche n\'a pas été déplacée. Réessaie.'))
    }
  }

  const poserPriorite = async (projet, valeur) => {
    if (valeur === projet.priorite) return
    setVue((v) => ({ ...v, projet: { ...v.projet, priorite: valeur } }))
    try {
      const { data } = await modifierProjet(projet.id, { priorite: valeur, lock_version: projet.lock_version })
      setVue((v) => ({ ...v, projet: { ...v.projet, ...data } }))
    } catch (err) {
      setVue((v) => ({ ...v, projet }))
      setErreur(frenchError(err, 'La priorité n\'a pas été changée. Réessaie.'))
    }
  }

  const mettreEnPause = async () => {
    const projet = vue.projet
    try {
      const { data } = await modifierProjet(projet.id, { statut: 'en_pause', lock_version: projet.lock_version })
      setVue((v) => ({ ...v, projet: { ...v.projet, ...data } }))
      proposerAnnuler({
        message: `« ${projet.nom} » en pause`,
        onAnnuler: async () => {
          const retour = await modifierProjet(projet.id, { statut: 'actif', lock_version: data.lock_version })
          setVue((v) => ({ ...v, projet: { ...v.projet, ...retour.data } }))
        },
      })
    } catch (err) {
      setErreur(frenchError(err, 'Le projet n\'a pas été mis en pause. Réessaie.'))
    }
  }

  const fermerPlanification = () => setParams((p) => { const s = new URLSearchParams(p); s.delete('planifier'); return s }, { replace: true })
  const planifie = async () => {
    fermerPlanification()
    annoncer('Projet planifié')
    await charger() // une fois, après le rituel : il a créé des étapes et des tâches
  }

  const noms = useMemo(() => {
    const taches = {}
    const sections = {}
    for (const s of vue?.sections ?? []) {
      sections[s.id] = s.nom
      for (const t of s.taches ?? []) taches[t.id] = t.titre
    }
    for (const t of vue?.sans_section ?? []) taches[t.id] = t.titre
    return { taches, sections }
  }, [vue])

  const decale = async (reponse) => {
    setDialogue(null)
    const n = reponse.changements.length
    proposerAnnuler({
      message: `${accord(n, 'date changée', 'dates changées')}`,
      onAnnuler: async () => { if (reponse.geste_id) await annulerGeste(reponse.geste_id); await charger() },
    })
    await charger() // le décalage touche des dates partout : une relecture, une fois
  }

  // TCH157 — « Dupliquer » : le double s'ouvre, « Projet créé · Annuler » le supprime ; « Modèle… » enregistre sans quitter l'écran.
  const duplique = (reponse) => {
    const retour = vue.projet.id
    setDialogue(null)
    proposerAnnuler({
      message: 'Projet créé',
      onAnnuler: async () => { if (reponse.geste_id) await annulerGeste(reponse.geste_id); navigate(`/taches/projets/${retour}`) },
    })
    navigate(`/taches/projets/${reponse.projet.id}`)
  }
  const modeleEnregistre = (modele) => {
    setDialogue(null)
    annoncer(`« ${modele.nom} » enregistré comme modèle`)
  }

  const termine = () => {
    setDialogue(null)
    proposerAnnuler({
      message: `« ${vue.projet.nom} » terminé`,
      onAnnuler: async () => { await rouvrirProjet(vue.projet.id); await charger() },
    })
    naviguerApresFeuille(navigate, '/taches/projets')
  }

  const supprime = () => {
    const { id: projetId, nom } = vue.projet
    setDialogue(null)
    proposerAnnuler({
      message: `« ${nom} » et ses ${accord((vue.projet.compteurs?.ouvertes ?? 0) + (vue.projet.compteurs?.faites ?? 0), 'tâche')} supprimés`,
      onAnnuler: async () => { await restaurerProjet(projetId); navigate(`/taches/projets/${projetId}`) },
    })
    naviguerApresFeuille(navigate, '/taches/projets')
  }

  const projet = vue?.projet
  const actionsEcran = projet ? [
    { libelle: 'Planifier le projet', onSelect: () => setParams((p) => { const s = new URLSearchParams(p); s.set('planifier', '1'); return s }) },
    { libelle: "Voir dans l'agenda", onSelect: () => navigate(`/taches/agenda?projet=${projet.id}`) },
    { libelle: 'Avancement par semaine', onSelect: () => setDialogue('burnup') },
    { libelle: 'Décaler les dates…', onSelect: () => setDialogue('decaler') },
    { libelle: 'Dupliquer', onSelect: () => setDialogue('dupliquer') },
    { libelle: 'Modèle…', onSelect: () => setDialogue('modele') },
    ...(projet.statut === 'actif' ? [{ libelle: 'Mettre en pause', onSelect: mettreEnPause }] : []),
    { libelle: 'Terminer le projet…', onSelect: () => setDialogue('terminer') },
    { libelle: 'Supprimer le projet…', onSelect: () => setDialogue('supprimer') },
  ] : []

  return (
    <CoquilleTaches ecran="projet" titre={projet?.nom ?? 'Projet'} actionsEcran={actionsEcran}
      feuille={actions.feuille} selecteurProjet={actions.selecteurProjet} conflit={actions.conflit} contexteSaisie={contexteSaisie}>
      <BarreRetourProjets />
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      {introuvable ? <p className="ep-alerte-ligne" role="alert">Ce projet n'existe plus.</p> : null}
      <ChargementTardif actif={!vue && !erreur && !introuvable} />
      {vue && planifier ? (
        <PlanifierProjet projet={projet} aujourdhui={aujourdhui} onTermine={planifie} onPasser={fermerPlanification} />
      ) : null}
      {vue && !planifier ? (
        <>
          {projet.statut === 'en_pause' ? <p className="ep-constat">En pause</p> : null}
          <SelecteurVue vue={vueCode} onChoisir={choisirVue} />
          <Entete vue={vue} aujourdhui={aujourdhui} onPriorite={poserPriorite} />
          {vueCode === 'tableau' ? (
            <Tableau
              vue={vue}
              aujourdhui={aujourdhui}
              onDeplacer={deplacerVersEtape}
              onTerminer={terminer}
              onOuvrir={(t) => ouvrirFiche(t.id)}
              onAction={actions.surAction}
              onAjouter={ajouter}
              onAnnonce={annoncer}
            />
          ) : null}
          {vueCode === 'chronologie' ? <VueChronologie vue={vue} aujourdhui={aujourdhui} /> : null}
          {vueCode === 'liste' ? (
            <VueListe
              vue={vue}
              aujourdhui={aujourdhui}
              onTerminer={terminer}
              onOuvrir={(t) => ouvrirFiche(t.id)}
              onAction={actions.surAction}
              chargerFaites={chargerFaites}
              onAjouter={ajouter}
              onAnnonce={annoncer}
            />
          ) : null}
        </>
      ) : null}
      {vue && dialogue === 'decaler' ? (
        <DialogueDecaler projet={vue.projet} noms={noms} aujourdhui={aujourdhui} onFait={decale} onFermer={() => setDialogue(null)} />
      ) : null}
      {vue && dialogue === 'dupliquer' ? (
        <DialogueUtiliser source={{ type: 'projet', id: vue.projet.id, nom: vue.projet.nom }} etapes={nomsDesEtapes(vue)}
          aujourdhui={aujourdhui} onFait={duplique} onFermer={() => setDialogue(null)} />
      ) : null}
      {vue && dialogue === 'modele' ? (
        <DialogueEnregistrerModele projet={vue.projet} onFait={modeleEnregistre} onFermer={() => setDialogue(null)} />
      ) : null}
      {vue && dialogue === 'burnup' ? (
        <FeuilleACrans ouverte onFermer={() => setDialogue(null)} titre="Avancement par semaine">
          <Burnup vue={vue} aujourdhui={aujourdhui} />
        </FeuilleACrans>
      ) : null}
      {vue && dialogue === 'terminer' ? <DialogueTerminer projet={vue.projet} onFait={termine} onFermer={() => setDialogue(null)} /> : null}
      {vue && dialogue === 'supprimer' ? <DialogueSupprimer projet={vue.projet} onFait={supprime} onFermer={() => setDialogue(null)} /> : null}
    </CoquilleTaches>
  )
}
