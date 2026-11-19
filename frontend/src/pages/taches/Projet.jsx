import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ChevronDown, ChevronRight, Diamond, TriangleAlert } from 'lucide-react'
import {
  annulerGeste, classerErreur, listerProjets, modifierProjet, modifierTache, reordonnerProjet, restaurerProjet, rouvrirProjet,
  reordonnerTache, rouvrirTache, terminerTache, listerToutesLesTaches, lireVueProjet } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import BarreRetourProjets from '../../features/taches/ui/BarreRetourProjets'
import CoquilleTaches, { EVENEMENT_SAISIR } from '../../features/taches/coquille/CoquilleTaches'
import { useApresCreation, useOuvrirFiche } from '../../features/taches/lib/fiche'
import { PuchePriorite, avancementDe, echeanceProjet, jourProjet } from '../../features/taches/projets/LigneProjet'
import {
  DialogueCouleur, DialogueDecaler, DialogueEcheance, DialogueEnregistrerModele, DialogueSupprimer, DialogueTerminer,
  DialogueRenommerProjet, DialogueUtiliser,
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
import { annoncer, annulerToast, proposerAnnuler } from '../../features/taches/lib/gestes'
import { useClavierListe } from '../../features/taches/lib/clavierListe'
import { annulerEtRecaler, versionDe } from '../../features/taches/lib/versions'
import { accord, aujourdhuiIso } from '../../features/taches/lib/textes'

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

/** Les tâches ouvertes d'une étape (`null` : « Sans étape »). */
const listeDe = (vue, sectionId) => (sectionId == null
  ? (vue.sans_section ?? [])
  : ((vue.sections ?? []).find((s) => s.id === sectionId)?.taches ?? []))

const avecListe = (vue, sectionId, taches) => (sectionId == null
  ? { ...vue, sans_section: taches }
  : { ...vue, sections: (vue.sections ?? []).map((s) => (s.id === sectionId ? { ...s, taches } : s)) })

/**
 * R2-063 — place la tâche `id` à la position `vers` de SON étape (retirée puis insérée : `arrayMove`). Rend la vue
 * suivante, les deux voisines que le serveur attend (`avant_id` la précède, `apres_id` la suit) et les voisines d'AVANT
 * (de quoi la remettre à sa place), ou `null` si rien ne bouge.
 */
function deplacerDans(vue, id, vers) {
  const place = placeDe(vue, id)
  if (!place) return null
  const liste = [...listeDe(vue, place.sectionId)]
  const cible = Math.max(0, Math.min(liste.length - 1, vers))
  if (cible === place.rang) return null
  const anciennes = { avant: liste[place.rang - 1]?.id ?? null, apres: liste[place.rang + 1]?.id ?? null }
  const [item] = liste.splice(place.rang, 1)
  liste.splice(cible, 0, item)
  return {
    vue: avecListe(vue, place.sectionId, liste),
    avant: liste[cible - 1]?.id ?? null,
    apres: liste[cible + 1]?.id ?? null,
    anciennes,
    de: place.rang,
    vers: cible,
    total: liste.length,
  }
}

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

/** Santé courte de l'en-tête (textes.md §2.6) : signal (d) d'`echeance_menacee` → « À ce rythme : … » ; sinon la phrase. */
function santeCourte(signal) {
  const d = signal?.donnees
  if (signal?.code === 'echeance_menacee' && d?.signal === 'd' && d.besoin != null && d.reste != null) {
    return `À ce rythme : ${d.besoin} jours travaillés, il en reste ${d.reste}`
  }
  return signal?.phrase ?? ''
}

/** R2-061 — « Fini quand… » se lit et se corrige sur place : toucher le texte ouvre le champ ; Entrée ou la sortie
 *  enregistre, Échap annule ; un refus du serveur s'affiche sous le champ et le texte tapé reste. */
function Objectif({ objectif, onEnregistrer }) {
  const [edition, setEdition] = useState(false)
  const [texte, setTexte] = useState('')
  const [erreur, setErreur] = useState('')
  const fini = useRef(false)
  const commencer = () => { fini.current = false; setTexte(objectif ?? ''); setErreur(''); setEdition(true) }
  const valider = async () => {
    if (fini.current) return
    fini.current = true
    if (texte.trim() === (objectif ?? '').trim()) { setEdition(false); return }
    const retour = await onEnregistrer(texte.trim())
    if (retour.ok) setEdition(false)
    else { fini.current = false; setErreur(retour.message) }
  }
  const touche = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); fini.current = true; setEdition(false) }
    else if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); valider() }
  }
  if (!edition) {
    return (
      <button type="button" className={`ep-objectif${objectif ? '' : ' vide'}`} aria-label="Modifier « Fini quand… »" onClick={commencer}>
        {objectif ? (/^fini quand/i.test(objectif) ? objectif : `Fini quand : ${objectif}`) : 'Ce sera fini quand…'}
      </button>
    )
  }
  return (
    <div className="ep-groupe">
      <textarea className="champ ep-zone" rows={2} value={texte} autoFocus aria-label="Fini quand…" placeholder="Une phrase"
        onChange={(e) => setTexte(e.target.value)} onKeyDown={touche} onBlur={valider}
        aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-objectif-erreur' : undefined} />
      {erreur ? <p id="ep-objectif-erreur" className="ep-erreur" role="alert">{erreur}</p> : null}
    </div>
  )
}

/** R2-061 — le nom du projet, dans le titre : le toucher le rend éditable (Entrée ou la sortie enregistre, Échap annule). */
function ChampNom({ nom, erreur, onEnregistrer, onAbandonner }) {
  const [texte, setTexte] = useState(nom)
  const fini = useRef(false)
  const champ = useRef(null)
  const valider = async () => {
    if (fini.current) return
    const propre = texte.trim()
    fini.current = true
    if (!propre || propre === nom) { onAbandonner(); return }
    const ok = await onEnregistrer(propre)
    if (!ok) { fini.current = false; champ.current?.focus() }
  }
  const touche = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); fini.current = true; onAbandonner() }
    else if (e.key === 'Enter') { e.preventDefault(); valider() }
  }
  return (
    <>
      <input ref={champ} className="ep-titre-champ" type="text" value={texte} maxLength={120} autoFocus aria-label="Nom du projet"
        onChange={(e) => setTexte(e.target.value)} onKeyDown={touche} onBlur={valider} onFocus={(e) => e.target.select()}
        aria-invalid={erreur ? 'true' : undefined} aria-describedby={erreur ? 'ep-nom-erreur' : undefined} />
      {erreur ? <span id="ep-nom-erreur" className="ep-erreur ep-titre-erreur" role="alert">{erreur}</span> : null}
    </>
  )
}

function Entete({ vue, aujourdhui, onPriorite, onObjectif }) {
  const [details, setDetails] = useState(false)
  const [detailSante, setDetailSante] = useState(false)
  const { projet, avancement, prochain_jalon: jalon } = vue
  const { texte, part } = avancementDe({ compteurs: { faites: avancement.faites, ouvertes: avancement.total - avancement.faites } })
  const signal = projet.sante?.[0]
  const sante = santeCourte(signal)
  const jalonJour = jalon ? (jalon.jour_prevu ?? jalon.echeance) : null
  const ech = projet.echeance ? echeanceProjet(projet.echeance, aujourdhui) : null
  // Passe visuelle n° 43 — l'en-tête de projet-liste.html : priorité · échéance ; barre, « 12 sur 18 » et le jalon
  // dessous ; la santé en UNE ligne (le détail au toucher) ; « Fini quand… » replié.
  return (
    <div className="ep-tete" data-p={projet.couleur}>
      <div className="ep-ligne-info">
        <PuchePriorite projet={projet} onChoisir={onPriorite} />
        {ech ? <span className={`chiffres ${ech.ton === 'alerte' ? 'alerte' : 'fort'}`}>{ech.texte}</span> : null}
      </div>
      <div className="ep-avance">
        <div className="ep-barre-avance" role="img" aria-label={texte}><i style={{ '--avance': part.toFixed(3) }} /></div>
        <div className="ep-avance-texte">
          <span className="chiffres"><b>{texte}</b></span>
          {jalon ? (
            <span className="ep-jalon-proche">
              <Diamond className="i i-14 ep-losange" aria-hidden="true" />
              {`Prochain jalon : ${jalon.titre}${jalonJour ? ` · ${jourProjet(jalonJour, aujourdhui)}` : ''}`}
            </span>
          ) : null}
        </div>
      </div>
      {sante && sante !== signal.phrase ? (
        <button type="button" className="ep-sante-ligne" aria-expanded={detailSante} onClick={() => setDetailSante((o) => !o)}>
          <TriangleAlert className="i i-14" aria-hidden="true" /><span>{sante}</span>
          <ChevronRight className="i i-14 chev" aria-hidden="true" />
        </button>
      ) : null}
      {sante && sante !== signal.phrase && detailSante ? <p className="ep-sante-detail">{signal.phrase}</p> : null}
      {sante && sante === signal.phrase ? (
        <p className="ep-sante-ligne">
          <TriangleAlert className="i i-14" aria-hidden="true" /><span>{sante}</span>
        </p>
      ) : null}
      <button type="button" className="ep-details" aria-expanded={details} onClick={() => setDetails((o) => !o)}>
        <span className="ep-details-texte"><b>Fini quand…</b></span>
        <ChevronDown className="i i-16" aria-hidden="true" />
      </button>
      {details ? (
        <div className="ep-details-corps">
          <Objectif objectif={projet.objectif} onEnregistrer={onObjectif} />
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

  // R2-061 — écrire des champs du PROJET (nom, couleur, échéance, objectif) : l'écran suit tout de suite, le serveur
  // confirme (verrou de version, écritures en file), « Annuler » remet les valeurs d'avant, un refus remet l'écran
  // comme avant et rend `{ ok: false, message }` (le message du champ fautif, sinon le message français général).
  const ecrireProjet = (champs, message = null, repli = 'Le projet n\'a pas été modifié. Réessaie.') => {
    const suite = chaineVue.current.then(async () => {
      const projet = projetRef.current
      if (!projet) return { ok: false, message: repli }
      const avant = Object.fromEntries(Object.keys(champs).map((c) => [c, projet[c]]))
      setVue((v) => (v ? { ...v, projet: { ...v.projet, ...champs } } : v))
      try {
        const { data } = await modifierProjet(projet.id, { ...champs, lock_version: projet.lock_version })
        projetRef.current = { ...projet, ...champs, ...data }
        setVue((v) => (v ? { ...v, projet: { ...v.projet, ...data } } : v))
        if (message) {
          proposerAnnuler({
            message,
            onAnnuler: async () => {
              const retour = await ecrireProjet(avant, null, 'Le projet n\'a pas été remis comme avant. Réessaie.')
              if (!retour.ok) throw new Error(retour.message)
            },
          })
        }
        return { ok: true }
      } catch (err) {
        projetRef.current = projet
        setVue((v) => (v ? { ...v, projet: { ...v.projet, ...avant } } : v))
        const champ = classerErreur(err).champs ?? err?.response?.data
        const premier = Object.keys(champs).map((c) => champ?.[c]).find((m) => Array.isArray(m) && m.length > 0)
        return { ok: false, message: premier?.[0] ?? frenchError(err, repli) }
      }
    })
    chaineVue.current = suite
    return suite
  }

  const [renommage, setRenommage] = useState(false)
  const [erreurNom, setErreurNom] = useState('')
  const renommer = async (nom) => {
    const retour = await ecrireProjet({ nom }, 'Projet renommé', 'Le projet n\'a pas été renommé. Réessaie.')
    if (retour.ok) { setRenommage(false); setErreurNom('') } else setErreurNom(retour.message)
    return retour.ok
  }
  // « Renommer » du ⋯ : une feuille (le menu qui se referme rendrait le focus à son bouton et ferait « sortir » du champ du titre)
  const renommerParFeuille = async (nom) => {
    const retour = await ecrireProjet({ nom }, 'Projet renommé', 'Le projet n\'a pas été renommé. Réessaie.')
    if (!retour.ok) throw Object.assign(new Error(retour.message), { response: { status: 400, data: { nom: [retour.message] } } })
    setDialogue(null)
  }
  const fermerRenommage = () => { setRenommage(false); setErreurNom('') }
  const changerCouleur = async (couleur) => {
    setDialogue(null)
    if (couleur === vue.projet.couleur) return
    const retour = await ecrireProjet({ couleur }, 'Couleur changée', 'La couleur n\'a pas été changée. Réessaie.')
    if (!retour.ok) setErreur(retour.message)
  }
  const changerEcheance = async (echeance) => {
    const retour = await ecrireProjet({ echeance }, echeance ? 'Échéance changée' : 'Échéance retirée', 'L\'échéance n\'a pas été changée. Réessaie.')
    if (!retour.ok) throw Object.assign(new Error(retour.message), { response: { status: 400, data: { echeance: [retour.message] } } })
    setDialogue(null)
  }
  const changerObjectif = (objectif) => ecrireProjet({ objectif }, 'Objectif enregistré', 'L\'objectif n\'a pas été enregistré. Réessaie.')

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
  // Tant que la vue n'est pas lue (réseau lent), le projet est celui de l'ADRESSE : un « + » touché tôt ne crée
  // jamais une tâche hors du projet (constaté en acceptation : elle partait dans À trier).
  const contexteSaisie = useMemo(() => {
    if (vue) return { projet_id: vue.projet.id, projet_nom: vue.projet.nom }
    return /^\d+$/.test(id ?? '') ? { projet_id: Number(id) } : null
  }, [vue, id])
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

  // R2-063 — l'ORDRE des tâches d'une étape : il décide ce qui remonte dans Proposé. `{ sens: ±1 }` (▲▼, Alt+↑/↓) ou
  // `{ vers }` (glissé) ; l'écran suit tout de suite, le serveur confirme (`reordonner/`, liste « projet » : aucun
  // verrou ne bouge), « Annuler » remet les voisines d'avant, un refus remet l'ordre d'avant et le DIT.
  const [reorganiser, setReorganiser] = useState(false)
  const reordonner = async (item, { sens = 0, vers = null }) => {
    const avant = vue
    const place = placeDe(avant, item.id)
    if (!place) return
    const suite = deplacerDans(avant, item.id, vers ?? place.rang + sens)
    if (!suite) return
    setVue(suite.vue)
    const position = `${item.titre} : position ${suite.vers + 1} sur ${suite.total}`
    try {
      await reordonnerTache(item.id, { liste: 'projet', avant_id: suite.avant, apres_id: suite.apres })
      proposerAnnuler({
        message: 'Ordre changé',
        annonce: position,
        onAnnuler: async () => {
          await reordonnerTache(item.id, { liste: 'projet', avant_id: suite.anciennes.avant, apres_id: suite.anciennes.apres })
          setVue((v) => (v ? (deplacerDans(v, item.id, suite.de)?.vue ?? v) : v))
        },
      })
    } catch (err) {
      setVue(avant)
      setErreur(frenchError(err, 'L\'ordre n\'a pas été changé. Réessaie.'))
    }
  }

  // Clavier des listes (spec-7 §5) : j/k, Espace, Alt+↑/↓ … ; jamais une touche seule qui fait disparaître une ligne (R2-036)
  const racine = useClavierListe((action, { cle }) => {
    if (action === 'annuler') { annulerToast(); return }
    const id = cle?.startsWith('tache:') ? Number(cle.slice(6)) : null
    const place = id && vue ? placeDe(vue, id) : null
    if (!place) return
    const tache = place.tache
    if (action === 'monter') reordonner(tache, { sens: -1 })
    else if (action === 'descendre') reordonner(tache, { sens: 1 })
    else if (action === 'terminer') terminer(tache, tache.statut !== 'fait').catch((err) => { if (err?.response) annoncer(frenchError(err)) })
    else if (action === 'essentiel') actions.essentiel(tache)
    else if (action === 'quand') actions.surAction('choisir_jour', tache)
    else if (action === 'deplacer') actions.surAction('deplacer', tache, { clavier: true })
    else if (['renommer', 'heure'].includes(action)) ouvrirFiche(tache.id)
  }, { actif: Boolean(vue) && !planifier && !dialogue && !actions.feuille && !actions.selecteurProjet })

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

  // R2-060 — « Mettre en haut » : le projet passe devant le premier projet actif (même geste que la liste Projets)
  const mettreEnHaut = async () => {
    const projet = vue.projet
    try {
      const { data } = await listerProjets({ statut: 'actif' })
      const premier = (Array.isArray(data) ? data : (data?.results ?? []))[0]
      if (!premier || premier.id === projet.id) { annoncer(`« ${projet.nom} » est déjà en haut`); return }
      await reordonnerProjet(projet.id, { avant_id: premier.id })
      annoncer(`« ${projet.nom} » en haut`)
    } catch (err) {
      setErreur(frenchError(err, "L'ordre n'a pas été changé. Réessaie."))
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
    // la feuille « Dupliquer » se ferme dans le même geste : la navigation remplace son entrée d'historique
    naviguerApresFeuille(navigate, `/taches/projets/${reponse.projet.id}`)
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
    { libelle: 'Renommer', onSelect: () => setDialogue('renommer') },
    { libelle: 'Couleur…', onSelect: () => setDialogue('couleur') },
    { libelle: 'Échéance…', onSelect: () => setDialogue('echeance') },
    { libelle: 'Planifier le projet', onSelect: () => setParams((p) => { const s = new URLSearchParams(p); s.set('planifier', '1'); return s }) },
    { libelle: "Voir dans l'agenda", onSelect: () => navigate(`/taches/agenda?projet=${projet.id}`) },
    { libelle: 'Avancement par semaine', onSelect: () => setDialogue('burnup') },
    ...(vueCode === 'liste' ? [{ libelle: 'Réorganiser', onSelect: () => setReorganiser((v) => !v) }] : []),
    { libelle: 'Décaler les dates…', onSelect: () => setDialogue('decaler') },
    { libelle: 'Dupliquer', onSelect: () => setDialogue('dupliquer') },
    { libelle: 'Modèle…', onSelect: () => setDialogue('modele') },
    ...(projet.statut === 'actif' ? [{ libelle: 'Mettre en haut', onSelect: mettreEnHaut }, { libelle: 'Mettre en pause', onSelect: mettreEnPause }] : []),
    { libelle: 'Terminer le projet…', onSelect: () => setDialogue('terminer') },
    { libelle: 'Supprimer le projet…', onSelect: () => setDialogue('supprimer') },
  ] : []

  // Passe visuelle n° 43 — le point de couleur du projet devant son nom (projet-liste.html, `.ep-projet-nom`)
  const titre = projet ? (
    <span className="ep-projet-nom" data-p={projet.couleur}>
      <i className="point" aria-hidden="true" />
      {renommage ? (
        <ChampNom nom={projet.nom} erreur={erreurNom} onEnregistrer={renommer} onAbandonner={fermerRenommage} />
      ) : (
        <button type="button" className="ep-titre-nom" aria-label={`Renommer « ${projet.nom} »`}
          onClick={() => { setErreurNom(''); setRenommage(true) }}>{projet.nom}</button>
      )}
    </span>
  ) : 'Projet'
  return (
    <CoquilleTaches ecran="projet" titre={titre} actionsEcran={actionsEcran}
      feuille={actions.feuille} selecteurProjet={actions.selecteurProjet} conflit={actions.conflit} contexteSaisie={contexteSaisie}>
      {/* Passe visuelle n° 43 — « ‹ Projets » et la vue (puce sur iPhone, segmenté au bureau) sur UNE rangée */}
      <div className="ep-barre-projet">
        <BarreRetourProjets />
        {vue && !planifier ? <SelecteurVue vue={vueCode} onChoisir={choisirVue} /> : null}
      </div>
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      {introuvable ? <p className="ep-alerte-ligne" role="alert">Ce projet n'existe plus.</p> : null}
      <ChargementTardif actif={!vue && !erreur && !introuvable} />
      {vue && planifier ? (
        <PlanifierProjet projet={projet} aujourdhui={aujourdhui} onTermine={planifie} onPasser={fermerPlanification} />
      ) : null}
      {vue && !planifier ? (
        <>
          {projet.statut === 'en_pause' ? <p className="ep-constat">En pause</p> : null}
          <Entete vue={vue} aujourdhui={aujourdhui} onPriorite={poserPriorite} onObjectif={changerObjectif} />
          {vueCode === 'tableau' ? (
            <Tableau
              vue={vue}
              aujourdhui={aujourdhui}
              onDeplacer={deplacerVersEtape}
              onReordonner={reordonner}
              onTerminer={terminer}
              onOuvrir={(t) => ouvrirFiche(t.id)}
              onAction={actions.surAction}
              onAjouter={ajouter}
              onAnnonce={annoncer}
            />
          ) : null}
          {vueCode === 'chronologie' ? <VueChronologie vue={vue} aujourdhui={aujourdhui} /> : null}
          {vueCode === 'liste' && reorganiser ? (
            <div className="mode-ecran" role="status">
              <span>Réorganiser</span>
              <button type="button" className="bouton lien" onClick={() => setReorganiser(false)}>OK</button>
            </div>
          ) : null}
          {vueCode === 'liste' ? (
            <VueListe
              racine={racine}
              reorganiser={reorganiser}
              onReordonner={reordonner}
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
      {vue && dialogue === 'renommer' ? (
        <DialogueRenommerProjet projet={vue.projet} onEnregistrer={renommerParFeuille} onFermer={() => setDialogue(null)} />
      ) : null}
      {vue && dialogue === 'couleur' ? (
        <DialogueCouleur projet={vue.projet} onChoisir={changerCouleur} onFermer={() => setDialogue(null)} />
      ) : null}
      {vue && dialogue === 'echeance' ? (
        <DialogueEcheance projet={vue.projet} aujourdhui={aujourdhui} onEnregistrer={changerEcheance} onFermer={() => setDialogue(null)} />
      ) : null}
      {vue && dialogue === 'terminer' ? <DialogueTerminer projet={vue.projet} onFait={termine} onFermer={() => setDialogue(null)} /> : null}
      {vue && dialogue === 'supprimer' ? <DialogueSupprimer projet={vue.projet} onFait={supprime} onFermer={() => setDialogue(null)} /> : null}
    </CoquilleTaches>
  )
}
