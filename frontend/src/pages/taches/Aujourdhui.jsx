import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import CoquilleTaches, { EVENEMENT_SAISIR } from '../../features/taches/coquille/CoquilleTaches'
import Sections, {
  BandeauPasAJour, EtatVide, PHRASE_HORS_LIGNE, Squelette,
} from '../../features/taches/aujourdhui/Sections'
import { FeuilleLier, useLierActivite } from '../../features/taches/aujourdhui/LignesErp'
import Replies, { useARevoir } from '../../features/taches/aujourdhui/Replies'
import FeuilleBilan from '../../features/taches/aujourdhui/FeuilleBilan'
import FeuilleAlleger from '../../features/taches/aujourdhui/FeuilleAlleger'
import { actionsJournee, useModesJournee } from '../../features/taches/aujourdhui/MenuJournee'
import Propose from '../../features/taches/aujourdhui/Propose'
import Progression from '../../features/taches/aujourdhui/Progression'
import CarteDuMoment from '../../features/taches/ui/CarteDuMoment'
import { annoncer, annulerToast, proposerAnnuler } from '../../features/taches/lib/gestes'
import { useClavierListe } from '../../features/taches/lib/clavierListe'
import { useEnLigne } from '../../features/taches/lib/enLigne'
import { accord, aujourdhuiIso, jourCourt, jourLong, jourNomme } from '../../features/taches/lib/textes'
import * as client from '../../api/tachesApi'
import recordsApi from '../../api/recordsApi'
import { frenchError } from '../../lib/frenchError'
import { EVENEMENT_OUVRIR } from '../../features/ia/copilotMessages'

/* ============================================================================
   TCH76 — Écran « Aujourd'hui » (route /taches/aujourdhui) : l'écran que le fondateur ouvre
   chaque jour sur son iPhone. Il lit `GET aujourdhui/` (contract_samples/aujourdhui.json) et
   rend les sections dans l'ordre vertical de regles.md §4.1 (features/taches/aujourdhui/Sections).
   Règles tenues ici, une fois pour toutes :
     · squelette seulement après 1 s sans réponse, jamais sur une liste déjà affichée ;
     · un rafraîchissement en échec GARDE la liste : bandeau « Pas à jour · HH:MM » [Réessayer] ;
     · relecture au retour du focus ; hors ligne, la lecture reste affichée et les gestes sont
       grisés (« Possible une fois connecté ») ;
     · un geste (cocher, reporter, ★) est optimiste puis réconcilié par la réponse du serveur :
       il ne relit jamais toute la liste ; le toast « … · Annuler » défait par `gestes/{id}/annuler/`.
   Maquettes : ecran-aujourdhui-*.html, etat-chargement.html, etat-pas-a-jour.html.
   ========================================================================== */

const DELAI_SQUELETTE_MS = 1000
const cleDe = (item) => `${item.type}:${item.id}`
const heureDe = (iso) => String(iso ?? '').slice(11, 16)

/** Les listes d'items du contrat (hors `propose`), dans l'ordre vertical. */
const LISTES_ITEMS = ['essentiel', 'journee', 'ce_soir', 'a_decider', 'en_attente', 'faites']

/** Applique `fn` à chaque item de la journée (toutes sections, Proposé compris) ; `fn` rend l'item, modifié ou non. */
function mapItems(donnees, fn) {
  if (!donnees) return donnees
  const lire = (liste) => (Array.isArray(liste) ? liste.map(fn) : liste)
  const suite = donnees.propose?.suite_par_projet
  const propose = donnees.propose ? {
    ...donnees.propose,
    pour_objectif: lire(donnees.propose.pour_objectif),
    suite_par_projet: Array.isArray(suite) ? suite.map((groupe) => ({ ...groupe, items: lire(groupe.items) })) : suite,
  } : donnees.propose
  return { ...donnees, ...Object.fromEntries(LISTES_ITEMS.map((cle) => [cle, lire(donnees[cle])])), propose }
}

/** Vrai si la journée ne porte AUCUNE ligne (ni tâche, ni activité, ni obligation, ni rendez-vous, ni proposition). */
function journeeVide(donnees) {
  const rien = (liste) => !Array.isArray(liste) || liste.length === 0
  const propose = donnees.propose ?? {}
  return LISTES_ITEMS.every((cle) => rien(donnees[cle]))
    && rien(donnees.obligations) && rien(donnees.rendez_vous)
    && rien(propose.pour_objectif) && rien(propose.suite_par_projet) && !(propose.reste_nb > 0)
}

/** Lit `aujourdhui/` : squelette tardif, liste gardée sur échec, relecture au focus. */
function useAujourdhui(tout) {
  const [donnees, setDonnees] = useState(null)
  const [erreur, setErreur] = useState(false)
  const [derniere, setDerniere] = useState('')
  const [squelette, setSquelette] = useState(false)
  const enLigne = useEnLigne()
  const vivant = useRef(true)
  const presentes = useRef(false)
  const vuFait = useRef(false)

  const charger = useCallback(async () => {
    const minuteur = presentes.current ? null : setTimeout(() => setSquelette(true), DELAI_SQUELETTE_MS)
    try {
      const { data } = await client.lireAujourdhui(tout ? { tout: 1 } : undefined)
      if (!vivant.current) return
      presentes.current = true
      setDonnees(data)
      setErreur(false)
      setDerniere(heureDe(data.maintenant))
    } catch {
      if (vivant.current) setErreur(true)
    } finally {
      if (minuteur) clearTimeout(minuteur)
      if (vivant.current) setSquelette(false)
    }
  }, [tout])

  useEffect(() => {
    vivant.current = true
    // « vu » d'abord : il crée la carte `retour` que la lecture suivante porte (api.md §4 `vu/`) ; un échec ne bloque pas la lecture
    const vu = vuFait.current || navigator.onLine === false ? Promise.resolve() : Promise.resolve(client.marquerVu({ ecran: 'aujourdhui' }))
    vuFait.current = true
    vu.then(charger, charger)
    return () => { vivant.current = false }
  }, [charger])

  useEffect(() => {
    const relire = () => { if (document.visibilityState !== 'hidden' && navigator.onLine !== false) charger() }
    window.addEventListener('focus', relire)
    document.addEventListener('visibilitychange', relire)
    return () => {
      window.removeEventListener('focus', relire)
      document.removeEventListener('visibilitychange', relire)
    }
  }, [charger])

  return { donnees, setDonnees, erreur, derniere, squelette: squelette && !donnees, enLigne, charger }
}

/** L'item de la journée portant cette clé (`tache:20`), dans n'importe quelle section. */
function chercher(donnees, cle) {
  let trouve = null
  mapItems(donnees, (it) => { if (cleDe(it) === cle && !trouve) trouve = it; return it })
  return trouve
}

/** Retire un item de sa liste ; rend la journée amputée et de quoi le remettre (Annuler). */
function retirer(donnees, cle) {
  for (const liste of LISTES_ITEMS) {
    const rang = (donnees[liste] ?? []).findIndex((it) => cleDe(it) === cle)
    if (rang >= 0) {
      const item = donnees[liste][rang]
      return { suite: { ...donnees, [liste]: donnees[liste].filter((_, i) => i !== rang) }, liste, rang, item }
    }
  }
  return { suite: mapItems(donnees, (it) => it), liste: null, rang: -1, item: null }
}

function remettre(donnees, { liste, rang, item }) {
  if (!liste || !item) return donnees
  const suite = [...(donnees[liste] ?? [])]
  suite.splice(Math.min(rang, suite.length), 0, item)
  return { ...donnees, [liste]: suite }
}

/** « Choisir un jour » : un champ date, une seule action (la tâche est prévue ce jour-là). */
function ChoisirJour({ item, minimum, onChoisir }) {
  const [jour, setJour] = useState('')
  return (
    <div className="choisir-jour">
      <p className="carte-source">{item.titre}</p>
      <label className="fiche-label" htmlFor="tch-choisir-jour">Jour</label>
      <input id="tch-choisir-jour" type="date" className="champ-date" min={minimum} value={jour} onChange={(e) => setJour(e.target.value)} />
      <button type="button" className="bouton plein large" disabled={!jour} onClick={() => onChoisir(jour)}>
        {jour ? `Prévue ${jourCourt(jour, minimum)}` : 'Choisis un jour'}
      </button>
    </div>
  )
}

function ConfirmerSuppression({ item, onConfirmer }) {
  return (
    <div className="choisir-jour">
      <p className="carte-texte">{`Supprimer « ${item.titre} » ?`}</p>
      <button type="button" className="bouton plein large" onClick={onConfirmer}>Supprimer</button>
    </div>
  )
}

export default function Aujourdhui() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tout = params.get('tout') === '1'
  const { donnees, setDonnees, erreur, derniere, squelette, enLigne, charger } = useAujourdhui(tout)
  const [estampilles, setEstampilles] = useState({})
  const [feuille, setFeuille] = useState(null)
  const [conflit, setConflit] = useState(null)
  const [invite, setInvite] = useState(false)
  const [focusPrevu, setFocusPrevu] = useState(0)

  const garde = useCallback(() => {
    if (enLigne) return
    annoncer(PHRASE_HORS_LIGNE)
    throw new Error(PHRASE_HORS_LIGNE)
  }, [enLigne])

  const patcher = useCallback((cle, fn) => {
    setDonnees((d) => (d ? mapItems(d, (it) => (cleDe(it) === cle ? fn(it) : it)) : d))
  }, [setDonnees])

  const poserProgression = useCallback((progression) => {
    if (progression && typeof progression.faites === 'number') setDonnees((d) => (d ? { ...d, progression } : d))
  }, [setDonnees])

  const terminer = useCallback(async (item, suivant) => {
    garde()
    const cle = cleDe(item)
    if (item.type === 'activite') {
      if (!suivant) throw new Error('Une activité de l’ERP close ne se rouvre pas ici.')
      await recordsApi.markActivityDone(item.id)
      patcher(cle, (it) => ({ ...it, statut: 'fait' }))
      proposerAnnuler({ message: "Close dans l'ERP" })
      return
    }
    const avant = donnees?.progression
    const { data } = suivant ? await client.terminerTache(item.id) : await client.rouvrirTache(item.id)
    patcher(cle, (it) => ({ ...it, statut: data.tache?.statut ?? (suivant ? 'fait' : 'a_faire'), lock_version: data.tache?.lock_version ?? it.lock_version }))
    poserProgression(data.progression)
    if (!suivant) return
    const prochaine = data.suivante?.jour_prevu
    proposerAnnuler({
      message: prochaine ? `Faite · prochaine ${jourNomme(prochaine, donnees?.jour)}` : 'Faite',
      annonce: `Fait : ${item.titre}`,
      onAnnuler: async () => {
        await client.annulerGeste(data.geste_id)
        patcher(cle, (it) => ({ ...it, statut: 'a_faire' }))
        poserProgression(avant)
      },
    })
  }, [garde, donnees, patcher, poserProgression])

  const poserJour = useCallback(async (item, jour, message, lockVersion = item.lock_version) => {
    const cle = cleDe(item)
    try {
      const { data } = await client.planifierTache(item.id, { jour_prevu: jour, lock_version: lockVersion })
      setConflit(null)
      setEstampilles((e) => ({ ...e, [cle]: `→ ${jourNomme(jour, donnees?.jour)}` }))
      patcher(cle, (it) => ({ ...it, lock_version: data.tache?.lock_version ?? it.lock_version }))
      proposerAnnuler({
        message,
        onAnnuler: async () => {
          await client.annulerGeste(data.geste_id)
          setEstampilles((e) => Object.fromEntries(Object.entries(e).filter(([k]) => k !== cle)))
        },
      })
    } catch (err) {
      if (err?.response?.status === 409 && err.response.data?.code === 'conflit_version') {
        const actuel = err.response.data.actuel ?? {}
        setConflit({
          heure: heureDe(actuel.updated_at),
          onGarder: () => poserJour(item, jour, message, err.response.data.lock_version ?? actuel.lock_version),
          onPrendre: () => { patcher(cle, (it) => ({ ...it, ...actuel })); setConflit(null) },
        })
        return
      }
      annoncer(frenchError(err))
    }
  }, [donnees, patcher])

  const reporter = useCallback((item) => {
    try { garde() } catch { return }
    const jour = donnees?.prochain_jour_ouvre
    if (jour) poserJour(item, jour, `Reportée à ${jourNomme(jour, donnees.jour)}`)
  }, [garde, donnees, poserJour])

  const basculerEssentiel = useCallback(async (item, suivant) => {
    try { garde() } catch { return }
    try {
      const { data } = await client.marquerEssentiel({ tache_id: item.id, essentielle: suivant })
      setDonnees((d) => {
        const { suite, item: trouve } = retirer(d, cleDe(item))
        if (!trouve) return d
        const change = { ...trouve, essentielle: suivant, lock_version: data.tache?.lock_version ?? trouve.lock_version }
        return suivant
          ? { ...suite, essentiel: [...(suite.essentiel ?? []), change] }
          : { ...suite, journee: [change, ...(suite.journee ?? [])] }
      })
      proposerAnnuler({
        message: suivant ? 'Essentielle' : 'Plus essentielle',
        onAnnuler: async () => {
          await client.annulerGeste(data.geste_id)
          setDonnees((d) => {
            const { suite, item: trouve } = retirer(d, cleDe(item))
            if (!trouve) return d
            const retour = { ...trouve, essentielle: !suivant }
            return suivant ? { ...suite, journee: [retour, ...(suite.journee ?? [])] } : { ...suite, essentiel: [...(suite.essentiel ?? []), retour] }
          })
        },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [garde, setDonnees])

  const supprimer = useCallback(async (item) => {
    setFeuille(null)
    try { garde() } catch { return }
    try {
      const { suite, ...origine } = retirer(donnees, cleDe(item))
      await client.supprimerTache(item.id)
      setDonnees(suite)
      proposerAnnuler({
        message: 'Supprimée',
        onAnnuler: async () => {
          await client.restaurerTache(item.id)
          setDonnees((d) => remettre(d, origine))
        },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [garde, donnees, setDonnees])

  const garder = useCallback(async (items) => {
    try { garde() } catch { return }
    try {
      const lignes = items.map((it) => ({ type: it.type, id: it.id }))
      const { data } = await client.garderJournee({ jour: donnees.jour, mode: 'express', lignes, essentielles: [], triage: [] })
      setDonnees(data.aujourdhui)
      setInvite(true)
      setFocusPrevu((v) => v + 1)
      proposerAnnuler({
        message: `${accord(items.length, 'gardée')}`,
        onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [garde, donnees, setDonnees, charger])

  const repondre = useCallback(async (proposition, reponse) => {
    try { garde() } catch { return }
    try {
      const { data } = await client.repondreProposition(proposition.id, { reponse })
      setDonnees((d) => ({ ...d, carte_du_moment: null, objectif: data.rythme?.objectif ?? d.objectif }))
      if (proposition.type === 'retour' && reponse === 'remettre_dans_propose') {
        const n = proposition.donnees?.taches ?? 0
        proposerAnnuler({
          message: `${n} ${n >= 2 ? 'remises' : 'remise'} dans Proposé`,
          onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
        })
        await charger()
      }
    } catch (err) {
      if (err?.response?.status === 409 && err.response.data?.code === 'proposition_expiree') {
        setDonnees((d) => ({ ...d, carte_du_moment: null }))
        return
      }
      annoncer(frenchError(err))
    }
  }, [garde, setDonnees, charger])

  const alleger = useCallback(async (ids) => {
    try { garde() } catch { return }
    try {
      const { data } = await client.alleger({ jour: donnees.jour, garder: ids })
      setDonnees(data.aujourdhui)
      setFeuille(null)
      const n = data.renvoyees?.length ?? 0
      proposerAnnuler({
        message: `${n} ${n >= 2 ? 'retournées' : 'retournée'} aux projets`,
        onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
      })
    } catch (err) {
      annoncer(frenchError(err))
    }
  }, [garde, donnees, setDonnees, charger])

  const modes = useModesJournee({ donnees, setDonnees, garde, setEstampilles })
  const revoir = useARevoir({ donnees, setDonnees, garde, charger })
  const lier = useLierActivite({ donnees, setDonnees, garde, charger })

  const ouvrirFiche = useCallback((id) => {
    setParams((actuels) => { const suite = new URLSearchParams(actuels); suite.set('tache', String(id)); return suite })
  }, [setParams])

  const geste = useMemo(() => ({
    terminer,
    reporter,
    choisirJour: (item) => setFeuille({ type: 'jour', item }),
    ouvrir: (item) => (item.type === 'activite' ? (item.lien?.url ? navigate(item.lien.url) : null) : ouvrirFiche(item.id)),
    action: (code, item) => {
      if (code === 'essentiel') basculerEssentiel(item, !item.essentielle)
      else if (code === 'choisir_jour') setFeuille({ type: 'jour', item })
      else if (code === 'supprimer') setFeuille({ type: 'supprimer', item })
      else if (code === 'lier') setFeuille({ type: 'lier', item })
      else ouvrirFiche(item.id)
    },
    essentiel: (item, suivant) => { setInvite(false); return basculerEssentiel(item, suivant) },
    deplacer: modes.deplacer,
    selectionner: modes.selectionner,
    garder,
    voirTout: (ouvert) => setParams((actuels) => {
      const suite = new URLSearchParams(actuels)
      if (ouvert) suite.set('tout', '1')
      else suite.delete('tout')
      return suite
    }, { replace: true }),
    copilote: (question) => {
      if (enLigne) window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, { detail: { ecran: '/taches/aujourdhui', question, envoyer: true } }))
    },
    refusEssentiel: () => annoncer('3 au plus.'),
    annoncer,
    naviguer: (url) => navigate(url),
  }), [terminer, reporter, basculerEssentiel, garder, enLigne, navigate, ouvrirFiche, setParams, modes.deplacer, modes.selectionner])

  const contexte = useMemo(() => ({
    donnees,
    estampilles,
    nbEssentielles: donnees?.essentiel?.length ?? 0,
    gardee: Boolean(donnees?.plan?.planifie_le),
    invite,
    focusPrevu,
    reorganiser: modes.reorganiser,
    selection: modes.selection,
  }), [donnees, estampilles, invite, focusPrevu, modes.reorganiser, modes.selection])

  // Clavier (spec-7 §5) : j/k, Espace, * … ; jamais une touche seule qui fait disparaître une ligne
  const racine = useClavierListe((action, { cle }) => {
    const item = cle ? chercher(donnees, cle) : null
    if (action === 'annuler') annulerToast()
    else if (!item) return
    else if (action === 'terminer') terminer(item, item.statut !== 'fait').catch((err) => { if (err?.response) annoncer(frenchError(err)) })
    else if (action === 'essentiel' && item.type === 'tache') basculerEssentiel(item, !item.essentielle)
    else if (action === 'quand' && item.type === 'tache') setFeuille({ type: 'jour', item })
    else if (action === 'selectionner' && item.type === 'tache') modes.selectionner(item)
    else if (action === 'monter') modes.deplacer(item, -1)
    else if (action === 'descendre') modes.deplacer(item, 1)
    else if (item.type === 'tache' && ['renommer', 'deplacer', 'heure'].includes(action)) ouvrirFiche(item.id)
  }, { actif: !feuille })

  const ouvrirSaisie = useCallback((detail) => {
    window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail }))
  }, [])

  const jourFeuille = donnees?.jour ?? aujourdhuiIso()

  // Bilan du soir : ouvert par la carte du moment, ou par `?ouvrir=bilan` (notification du soir)
  const bilanDemande = feuille?.type === 'bilan' || params.get('ouvrir') === 'bilan'
  const fermerBilan = () => {
    setFeuille(null)
    setParams((actuels) => { const suite = new URLSearchParams(actuels); suite.delete('ouvrir'); return suite }, { replace: true })
  }
  const bilanEnregistre = (data) => {
    fermerBilan()
    setDonnees((d) => ({ ...d, carte_du_moment: null, plan: { ...d.plan, cloture_le: data.plan?.cloture_le ?? d.plan?.cloture_le } }))
    proposerAnnuler({
      message: 'Bilan enregistré',
      onAnnuler: async () => { await client.annulerGeste(data.geste_id); await charger() },
    })
    charger()
  }

  let laFeuille = null
  if (bilanDemande && donnees) {
    laFeuille = {
      ouverte: true,
      titre: feuille?.jour && feuille.jour !== donnees.jour ? "Bilan d'hier" : 'Bilan du soir',
      cranInitial: '85',
      onFermer: fermerBilan,
      children: (
        <FeuilleBilan
          jour={feuille?.type === 'bilan' ? feuille.jour : null}
          aujourdhui={donnees.jour}
          maintenant={donnees.maintenant}
          enLigne={enLigne}
          onValide={bilanEnregistre}
          onPasser={fermerBilan}
        />
      ),
    }
  } else if (feuille?.type === 'jour') {
    laFeuille = {
      ouverte: true,
      titre: 'Choisir un jour',
      onFermer: () => setFeuille(null),
      children: (
        <ChoisirJour
          item={feuille.item}
          minimum={jourFeuille}
          onChoisir={(jour) => { setFeuille(null); poserJour(feuille.item, jour, `Prévue ${jourCourt(jour, jourFeuille)}`) }}
        />
      ),
    }
  } else if (feuille?.type === 'alleger' && donnees) {
    laFeuille = {
      ouverte: true,
      titre: 'Alléger ma journée',
      cranInitial: '85',
      onFermer: () => setFeuille(null),
      children: <FeuilleAlleger donnees={donnees} enLigne={enLigne} onGarder={alleger} />,
    }
  } else if (feuille?.type === 'lier') {
    laFeuille = {
      ouverte: true,
      titre: 'Lier une tâche',
      onFermer: () => setFeuille(null),
      children: <FeuilleLier item={feuille.item} onLier={(titre) => { setFeuille(null); lier(feuille.item, titre) }} />,
    }
  } else if (feuille?.type === 'jour_lot') {
    laFeuille = {
      ouverte: true,
      titre: 'Quand',
      onFermer: () => setFeuille(null),
      children: (
        <ChoisirJour
          item={{ titre: accord(modes.selection.ids.size, 'tâche sélectionnée', 'tâches sélectionnées') }}
          minimum={jourFeuille}
          onChoisir={(jour) => { setFeuille(null); modes.lot('planifier', { jour_prevu: jour }) }}
        />
      ),
    }
  } else if (feuille?.type === 'supprimer') {
    laFeuille = {
      ouverte: true,
      titre: 'Supprimer',
      onFermer: () => setFeuille(null),
      children: <ConfirmerSuppression item={feuille.item} onConfirmer={() => supprimer(feuille.item)} />,
    }
  }

  const sousTitre = donnees && donnees.jour_ouvre === false ? 'Jour non travaillé' : jourLong(donnees?.jour)
  const ouvrirFeuille = (type, parametres = {}) => setFeuille({ type, ...parametres })
  const actionsEcran = actionsJournee({
    enLigne,
    onAlleger: () => ouvrirFeuille('alleger'),
    onReorganiser: () => modes.setReorganiser((v) => !v),
    onSelectionner: modes.basculerSelection,
  })
  const barreSelection = modes.selection.actif ? {
    n: modes.selection.ids.size,
    actions: [{ code: 'planifier', libelle: 'Quand' }, { code: 'terminer', libelle: 'Terminer' }],
    onAction: (code) => (code === 'planifier' ? setFeuille({ type: 'jour_lot' }) : modes.lot(code)),
    onFermer: modes.quitterSelection,
  } : null
  const bandeau = erreur ? <BandeauPasAJour derniere={derniere} onReessayer={charger} /> : null

  return (
    <CoquilleTaches
      ecran="aujourdhui"
      titre="Aujourd'hui"
      sousTitre={sousTitre}
      derniereSynchro={derniere}
      conflit={conflit}
      feuille={laFeuille}
      actionsEcran={actionsEcran}
      selection={barreSelection}
    >
      {modes.reorganiser || modes.selection.actif ? (
        <div className="mode-ecran" role="status">
          <span>{modes.reorganiser ? 'Réorganiser' : 'Sélectionner'}</span>
          <button type="button" className="bouton lien" onClick={() => { modes.setReorganiser(false); modes.quitterSelection() }}>OK</button>
        </div>
      ) : null}
      {squelette ? <Squelette /> : null}
      {donnees && !journeeVide(donnees) ? <Progression donnees={donnees} onRythme={() => navigate('/taches/rythme')} /> : null}
      {bandeau}
      {donnees && !journeeVide(donnees) ? (
        <CarteDuMoment
          carte={donnees.carte_du_moment}
          jour={donnees.jour}
          maintenant={donnees.maintenant}
          objectif={donnees.objectif?.nb}
          enLigne={enLigne}
          onRepondre={repondre}
          onGarder={() => garder(donnees.propose?.pour_objectif ?? [])}
          onAlleger={() => ouvrirFeuille('alleger')}
          onBilan={(jourBilan) => ouvrirFeuille('bilan', { jour: jourBilan })}
          onNaviguer={navigate}
          onCopilote={geste.copilote}
        />
      ) : null}
      {donnees && journeeVide(donnees) ? (
        <EtatVide
          donnees={donnees}
          onColler={() => ouvrirSaisie({ coller: true })}
          onDicter={() => ouvrirSaisie({ dicter: true })}
          onTrier={() => navigate('/taches/a-trier')}
        />
      ) : null}
      {donnees && !journeeVide(donnees) ? (
        <div ref={racine}>
        <Sections
          donnees={donnees}
          contexte={contexte}
          geste={geste}
          repliees={<Replies donnees={donnees} contexte={contexte} geste={geste} revoir={revoir} enLigne={enLigne} />}
          propose={(
            <Propose
              donnees={donnees}
              contexte={contexte}
              geste={geste}
              enLigne={enLigne}
              tout={tout}
              carteGarder={donnees.carte_du_moment?.type === 'garder'}
            />
          )}
        />
        </div>
      ) : null}
    </CoquilleTaches>
  )
}
