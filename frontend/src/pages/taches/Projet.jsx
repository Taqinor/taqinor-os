import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ChevronDown, Diamond, TriangleAlert } from 'lucide-react'
import {
  annulerGeste, classerErreur, modifierProjet, restaurerProjet, rouvrirProjet,
  rouvrirTache, terminerTache, listerToutesLesTaches, lireVueProjet } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import BarreRetourProjets from '../../features/taches/ui/BarreRetourProjets'
import CoquilleTaches, { EVENEMENT_SAISIR } from '../../features/taches/coquille/CoquilleTaches'
import { useApresCreation, useOuvrirFiche } from '../../features/taches/lib/fiche'
import { PuchePriorite, avancementDe } from '../../features/taches/projets/LigneProjet'
import { DialogueDecaler, DialogueSupprimer, DialogueTerminer } from '../../features/taches/projets/Dialogues'
import PlanifierProjet from '../../features/taches/projets/PlanifierProjet'
import VueListe from '../../features/taches/projets/VueListe'
import ChargementTardif from '../../features/taches/ui/ChargementTardif'
import { useActionsLigne } from '../../features/taches/ui/ActionsLigne'
import { annoncer, proposerAnnuler } from '../../features/taches/lib/gestes'
import { accord, aujourdhuiIso, jourCourt } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH89 — Écran « Un projet », vue Liste (`/taches/projets/:id`). Maquette : docs/taches/maquettes/projet-liste.html.
   Textes : reference/textes.md §2.6 (« {faites} sur {total} · échéance {jj/mm} », « Prochain jalon : {titre} · {jour} »,
   santé si signal, Détails « Fini quand : {objectif} » · « dernière faite le {jj/mm} »). Contrat : `projet_vue.json`.
   Tableau, Chronologie, Modèle et Dupliquer sont de la fusion F4 : ils n'apparaissent pas ici.
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

  const majTache = (tache) => setVue((v) => (v ? remplacerTache(v, tache) : v))
  const ajusterFaites = (delta) => setVue((v) => (v ? { ...v, avancement: { ...v.avancement, faites: v.avancement.faites + delta } } : v))

  const terminer = async (item, suivant) => {
    const { data } = suivant ? await terminerTache(item.id) : await rouvrirTache(item.id)
    majTache(data.tache ?? { ...item, statut: suivant ? 'fait' : 'a_faire' })
    ajusterFaites(suivant ? 1 : -1)
    if (suivant) {
      proposerAnnuler({
        message: 'Faite',
        annonce: `Fait : ${item.titre}`,
        onAnnuler: async () => {
          const retour = await rouvrirTache(item.id)
          majTache(retour.data.tache ?? { ...item, statut: 'a_faire' })
          ajusterFaites(-1)
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

  const termine = () => {
    setDialogue(null)
    proposerAnnuler({
      message: `« ${vue.projet.nom} » terminé`,
      onAnnuler: async () => { await rouvrirProjet(vue.projet.id); await charger() },
    })
    navigate('/taches/projets')
  }

  const supprime = () => {
    const { id: projetId, nom } = vue.projet
    setDialogue(null)
    proposerAnnuler({
      message: `« ${nom} » et ses ${accord((vue.projet.compteurs?.ouvertes ?? 0) + (vue.projet.compteurs?.faites ?? 0), 'tâche')} supprimés`,
      onAnnuler: async () => { await restaurerProjet(projetId); navigate(`/taches/projets/${projetId}`) },
    })
    navigate('/taches/projets')
  }

  const projet = vue?.projet
  const actionsEcran = projet ? [
    { libelle: 'Planifier le projet', onSelect: () => setParams((p) => { const s = new URLSearchParams(p); s.set('planifier', '1'); return s }) },
    { libelle: "Voir dans l'agenda", onSelect: () => navigate(`/taches/agenda?projet=${projet.id}`) },
    { libelle: 'Décaler les dates…', onSelect: () => setDialogue('decaler') },
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
          <Entete vue={vue} aujourdhui={aujourdhui} onPriorite={poserPriorite} />
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
        </>
      ) : null}
      {vue && dialogue === 'decaler' ? (
        <DialogueDecaler projet={vue.projet} noms={noms} aujourdhui={aujourdhui} onFait={decale} onFermer={() => setDialogue(null)} />
      ) : null}
      {vue && dialogue === 'terminer' ? <DialogueTerminer projet={vue.projet} onFait={termine} onFermer={() => setDialogue(null)} /> : null}
      {vue && dialogue === 'supprimer' ? <DialogueSupprimer projet={vue.projet} onFait={supprime} onFermer={() => setDialogue(null)} /> : null}
    </CoquilleTaches>
  )
}
