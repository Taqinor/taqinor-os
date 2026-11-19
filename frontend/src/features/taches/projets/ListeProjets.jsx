/* eslint-disable react-refresh/only-export-components -- la liste des projets : hooks, événement et composants d'une même fonction, partagés par Projets et Projet */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronDown, Ellipsis, FolderPlus } from 'lucide-react'
import { creerProjet, listerProjets, listerTousLesProjets, modifierProjet } from '../../../api/tachesApi'
import { reordonnerProjet, restaurerProjet, trierProjetsParPriorite } from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import { EVENEMENT_SAISIR } from '../coquille/CoquilleTaches'
import { DialogueSupprimer } from './Dialogues'
import LigneProjet from './LigneProjet'
import FeuilleACrans, { naviguerApresFeuille } from '../ui/FeuilleACrans'
import ChargementTardif from '../ui/ChargementTardif'
import { annoncer, proposerAnnuler } from '../lib/gestes'
import { accord, aujourdhuiIso } from '../lib/textes'
import { estEnLigne, useCompteTaches } from '../lib/enLigne'
import { ecrireProjetsCache, lireProjetsCache, viderCacheProjetsALaDeconnexion } from '../horsligne/cacheProjets'

/* ============================================================================
   La LISTE des projets, une seule pour les deux écrans qui la montrent :
     · `/taches/projets` (iPhone et largeurs < 1024 px : la liste, puis le projet) ;
     · le projet ouvert, au bureau (≥ 1024 px) : maître-détail (R2-067) — la liste à gauche, le projet à droite,
       comme Things, Todoist et Linear (maquette projets-liste.html, vue bureau).
   Règles de maison : un geste (priorité, pause, « Mettre en haut », tri) met la liste à jour SUR PLACE puis réconcilie
   avec la réponse du serveur — jamais de relecture complète ; un échec remet la ligne comme avant et le DIT ; une
   liste ne se vide jamais sur un rafraîchissement raté ; jamais « Aucun projet » sans réponse du serveur (R2-070).
   ========================================================================== */

/** Seuil du maître-détail : le même que celui des panneaux de Tâches (fiche, bilan, Alléger). */
const REQUETE_MAITRE_DETAIL = '(min-width: 1024px)'

/** Vrai au bureau (≥ 1024 px) ; suit le redimensionnement. Sans `matchMedia` (tests nus), jamais le bureau. */
export function useMaitreDetail() {
  const lire = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(REQUETE_MAITRE_DETAIL).matches
  const [large, setLarge] = useState(lire)
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined
    const mq = window.matchMedia(REQUETE_MAITRE_DETAIL)
    const maj = () => setLarge(mq.matches)
    mq.addEventListener?.('change', maj)
    return () => mq.removeEventListener?.('change', maj)
  }, [])
  return large
}

/** Le projet ouvert (à droite) et la liste (à gauche) se tiennent à jour l'un l'autre : un projet écrit d'un côté est
 *  signalé à l'autre (`detail = { projet, source }`, `source` : 'detail' ou 'liste'). */
export const EVENEMENT_PROJET_ECRIT = 'taqinor:taches:projet-ecrit'

export function signalerProjetEcrit(projet, source) {
  window.dispatchEvent(new CustomEvent(EVENEMENT_PROJET_ECRIT, { detail: { projet, source } }))
}

/** Écoute les projets écrits par l'AUTRE côté ; `surEcrit(projet)` reçoit les champs écrits (toujours `id`). */
export function useProjetEcrit(source, surEcrit) {
  const rappel = useRef(surEcrit)
  useEffect(() => { rappel.current = surEcrit })
  useEffect(() => {
    const ecoute = (e) => { if (e.detail?.source !== source && e.detail?.projet) rappel.current?.(e.detail.projet) }
    window.addEventListener(EVENEMENT_PROJET_ECRIT, ecoute)
    return () => window.removeEventListener(EVENEMENT_PROJET_ECRIT, ecoute)
  }, [source])
}

const parPriorite = (a, b) => (b.priorite ?? 0) - (a.priorite ?? 0)

function lignes(reponse) {
  const donnees = reponse?.data
  return Array.isArray(donnees) ? donnees : (donnees?.results ?? [])
}

function constatTexte(constat) {
  if (!constat) return ''
  const { actifs, avances_7j: avances } = constat
  return `${accord(actifs, 'projet actif', 'projets actifs')}, ${accord(avances, 'a avancé', 'ont avancé')} ces 7 jours`
}

function FormulaireNouveau({ onCreer, onModeles }) {
  const [nom, setNom] = useState('')
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const creer = async (e) => {
    e.preventDefault()
    setEnvoi(true)
    setErreur('')
    try {
      await onCreer(nom.trim())
    } catch (err) {
      setErreur(err?.response?.data?.nom?.[0] ?? frenchError(err, 'Le projet n\'a pas été créé. Réessaie.'))
    } finally {
      setEnvoi(false)
    }
  }
  return (
    <form className="ep-formulaire" onSubmit={creer} noValidate>
      <label className="ep-etiquette" htmlFor="ep-nouveau-nom">Nom du projet</label>
      <input
        id="ep-nouveau-nom"
        className="champ"
        value={nom}
        onChange={(e) => setNom(e.target.value)}
        aria-invalid={erreur ? 'true' : undefined}
        aria-describedby={erreur ? 'ep-nouveau-erreur' : undefined}
        autoFocus
      />
      {erreur ? <p id="ep-nouveau-erreur" className="ep-erreur" role="alert">{erreur}</p> : null}
      <div className="carte-actions">
        <button type="submit" className="bouton plein" disabled={envoi || !nom.trim()}>Créer</button>
        <button type="button" className="bouton second ep-modeles-lien" onClick={onModeles}>Depuis un modèle</button>
      </div>
    </form>
  )
}

/**
 * L'état de la liste des projets et ses gestes. `hydrater` : au montage, la dernière liste LUE du compte (cache) tient
 * lieu d'état de départ — le maître-détail remonte à chaque projet ouvert (le routeur de l'ERP remonte la page à chaque
 * adresse) : sans cela, la colonne de gauche clignoterait vide à chaque clic. `surSupprime(projet)` : un projet supprimé
 * d'ici ; l'appelant décide (le projet ouvert supprimé ramène à la liste).
 */
export function useListeProjets({ hydrater = false, surSupprime = null } = {}) {
  const navigate = useNavigate()
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const { userId } = useCompteTaches()
  const depart = useMemo(() => (hydrater ? lireProjetsCache(userId, 'liste')?.donnees ?? null : null), [hydrater, userId])
  const [actifs, setActifs] = useState(() => depart?.actifs ?? [])
  const [enPause, setEnPause] = useState(() => depart?.enPause ?? [])
  const [constat, setConstat] = useState(() => depart?.constat ?? null)
  const [charge, setCharge] = useState(Boolean(depart))
  // R2-070 — `lu` : la liste vient d'une RÉPONSE du serveur (ou, hors ligne, de la dernière lue et gardée) ; sans cela,
  // jamais « Aucun projet » : un écran vide n'est pas une réponse
  const [lu, setLu] = useState(Boolean(depart))
  const luDuServeur = useRef(Boolean(depart))
  const [erreur, setErreur] = useState('')
  const [pauseOuverte, setPauseOuverte] = useState(false)
  // « Nouveau projet » de la palette arrive par `?nouveau=1` : la feuille s'ouvre, le paramètre part à la fermeture
  const [params, setParams] = useSearchParams()
  const demandeNouveau = params.get('nouveau') === '1'
  const [nouveau, setNouveauLocal] = useState(demandeNouveau)
  // eslint-disable-next-line react-hooks/set-state-in-effect -- l'adresse demande la feuille alors que l'écran est déjà monté (palette) (D-ENF22)
  useEffect(() => { if (demandeNouveau) setNouveauLocal(true) }, [demandeNouveau])
  const setNouveau = (ouvert) => {
    setNouveauLocal(ouvert)
    if (!ouvert && params.get('nouveau')) setParams((p) => { const s = new URLSearchParams(p); s.delete('nouveau'); return s }, { replace: true })
  }
  const [asupprimer, setAsupprimer] = useState(null)

  const lire = useCallback(async () => {
    // Liste paginée (50) : la page 1 suffit tant que `next` est vide, sinon on lit tout (api.md §0).
    const lireStatut = async (statut) => {
      const premiere = await listerProjets({ statut })
      if (!premiere?.data?.next) return premiere
      return { data: { ...premiere.data, results: await listerTousLesProjets({ statut }) } }
    }
    try {
      const [a, p] = await Promise.all([lireStatut('actif'), lireStatut('en_pause')])
      const actifsLus = lignes(a)
      const pauseLus = lignes(p)
      const constatLu = a?.data?.constat ?? null
      setActifs(actifsLus)
      setConstat(constatLu)
      setEnPause(pauseLus)
      setErreur('')
      luDuServeur.current = true
      setLu(true)
      ecrireProjetsCache(userId, 'liste', { actifs: actifsLus, enPause: pauseLus, constat: constatLu })
    } catch (err) {
      // la liste déjà à l'écran reste : on dit seulement que le rafraîchissement a échoué ; sans rien à l'écran, la
      // dernière liste LUE du compte (cache) tient lieu de lecture — jamais un écran « vide » inventé
      const cache = luDuServeur.current ? null : lireProjetsCache(userId, 'liste')
      // hors ligne, UN seul signal : la ligne « Hors ligne · dernière synchro » de la coquille ; la phrase rouge « Connexion
      // perdue… » ne la double pas quand une liste (déjà lue, ou la dernière gardée) est à l'écran
      const listeAEcran = luDuServeur.current || Boolean(cache?.donnees)
      setErreur(listeAEcran && !estEnLigne() ? '' : frenchError(err, 'La liste n\'a pas pu être mise à jour. Réessaie.'))
      if (cache?.donnees) {
        setActifs(cache.donnees.actifs ?? [])
        setEnPause(cache.donnees.enPause ?? [])
        setConstat(cache.donnees.constat ?? null)
        luDuServeur.current = true
        setLu(true)
      }
    } finally {
      setCharge(true)
    }
  }, [userId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'écran (D-ENF22)
  useEffect(() => { lire() }, [lire])
  useEffect(() => viderCacheProjetsALaDeconnexion(), [])

  const remplacer = (projet) => {
    const maj = (liste) => liste.map((p) => (p.id === projet.id ? { ...p, ...projet } : p))
    setActifs(maj)
    setEnPause(maj)
  }

  // Le projet OUVERT (à droite, au bureau) a changé de nom, de couleur, d'avancement… : la ligne le suit tout de suite.
  // Un changement de statut (pause, reprise) déplace la ligne d'une liste à l'autre : une relecture, une fois.
  useProjetEcrit('liste', (projet) => {
    const ici = [...actifs, ...enPause].find((p) => p.id === projet.id)
    if (!ici) return
    remplacer(projet)
    if (projet.statut && projet.statut !== ici.statut) lire()
  })

  const poserPriorite = async (projet, valeur) => {
    if (valeur === projet.priorite) return
    remplacer({ ...projet, priorite: valeur })
    try {
      const { data } = await modifierProjet(projet.id, { priorite: valeur, lock_version: projet.lock_version })
      remplacer(data)
      signalerProjetEcrit({ id: data.id, priorite: data.priorite, lock_version: data.lock_version }, 'liste')
    } catch (err) {
      remplacer(projet)
      setErreur(frenchError(err, 'La priorité n\'a pas été changée. Réessaie.'))
    }
  }

  const changerStatut = async (projet, statut, depuis, vers) => {
    depuis(projet)
    try {
      const { data } = await modifierProjet(projet.id, { statut, lock_version: projet.lock_version })
      return data
    } catch (err) {
      vers(projet)
      setErreur(frenchError(err, 'Le projet n\'a pas été modifié. Réessaie.'))
      return null
    }
  }

  const mettreEnPause = async (projet) => {
    const sortir = (p) => { setActifs((l) => l.filter((x) => x.id !== p.id)); setEnPause((l) => [{ ...p, statut: 'en_pause' }, ...l]) }
    const revenir = (p) => { setEnPause((l) => l.filter((x) => x.id !== p.id)); setActifs((l) => [p, ...l].sort(parPriorite)) }
    const maj = await changerStatut(projet, 'en_pause', sortir, revenir)
    if (!maj) return
    setEnPause((l) => l.map((x) => (x.id === maj.id ? { ...x, ...maj } : x)))
    signalerProjetEcrit({ id: maj.id, statut: maj.statut, lock_version: maj.lock_version }, 'liste')
    proposerAnnuler({
      message: `« ${projet.nom} » en pause`,
      onAnnuler: async () => {
        const { data } = await modifierProjet(projet.id, { statut: 'actif', lock_version: maj.lock_version })
        setEnPause((l) => l.filter((x) => x.id !== projet.id))
        setActifs((l) => [{ ...projet, ...data }, ...l].sort(parPriorite))
        signalerProjetEcrit({ id: data.id, statut: data.statut, lock_version: data.lock_version }, 'liste')
      },
    })
  }

  const reprendre = async (projet) => {
    const sortir = (p) => { setEnPause((l) => l.filter((x) => x.id !== p.id)); setActifs((l) => [{ ...p, statut: 'actif' }, ...l]) }
    const revenir = (p) => { setActifs((l) => l.filter((x) => x.id !== p.id)); setEnPause((l) => [p, ...l]) }
    const maj = await changerStatut(projet, 'actif', sortir, revenir)
    if (!maj) return
    setActifs((l) => l.map((x) => (x.id === maj.id ? { ...x, ...maj } : x)))
    signalerProjetEcrit({ id: maj.id, statut: maj.statut, lock_version: maj.lock_version }, 'liste')
  }

  const mettreEnHaut = async (projet) => {
    const avant = actifs
    const premier = avant[0]
    if (!premier || premier.id === projet.id) return
    setActifs([projet, ...avant.filter((p) => p.id !== projet.id)])
    try {
      await reordonnerProjet(projet.id, { avant_id: premier.id })
      annoncer(`« ${projet.nom} » en haut`)
    } catch (err) {
      setActifs(avant)
      setErreur(frenchError(err, 'L\'ordre n\'a pas été changé. Réessaie.'))
    }
  }

  const trier = async () => {
    const avant = actifs
    setActifs([...avant].sort(parPriorite))
    try {
      await trierProjetsParPriorite()
      annoncer('Projets triés par priorité')
    } catch (err) {
      setActifs(avant)
      setErreur(frenchError(err, 'Le tri n\'a pas été appliqué. Réessaie.'))
    }
  }

  const surAction = (code, projet) => {
    if (code === 'en_haut') mettreEnHaut(projet)
    else if (code === 'pause') mettreEnPause(projet)
    else if (code === 'reprendre') reprendre(projet)
    else if (code === 'supprimer') setAsupprimer(projet)
  }

  const supprime = (projet) => {
    setAsupprimer(null)
    setActifs((l) => l.filter((p) => p.id !== projet.id))
    setEnPause((l) => l.filter((p) => p.id !== projet.id))
    proposerAnnuler({
      message: `« ${projet.nom} » et ses ${accord((projet.compteurs?.ouvertes ?? 0) + (projet.compteurs?.faites ?? 0), 'tâche')} supprimés`,
      onAnnuler: async () => {
        const { data } = await restaurerProjet(projet.id)
        const rendu = { ...projet, ...(data?.projet ?? {}) }
        setActifs((l) => [...l, rendu].sort(parPriorite))
      },
    })
    surSupprime?.(projet)
  }

  const creer = async (nom) => {
    const { data } = await creerProjet({ nom }, { erreurSousLeChamp: true })
    const cree = data?.projet ?? data // POST projets/ rend `projet_ecrit` : { projet, deplacees, … }
    setNouveau(false)
    naviguerApresFeuille(navigate, `/taches/projets/${cree.id}?planifier=1`)
  }

  const ouvrir = (projet, options) => navigate(`/taches/projets/${projet.id}`, options)
  const actionsEcran = [
    { libelle: 'Trier par priorité', onSelect: trier },
    { libelle: 'Archive', onSelect: () => navigate('/taches/projets/archive') },
    { libelle: 'Modèles', onSelect: () => navigate('/taches/projets/modeles') },
  ]
  // La feuille « Nouveau projet » : la coquille de l'écran la rend (prop `feuille`) ou la liste du maître-détail elle-même
  const feuilleNouveau = {
    ouverte: nouveau,
    onFermer: () => setNouveau(false),
    titre: 'Nouveau projet',
    children: <FormulaireNouveau onCreer={creer} onModeles={() => naviguerApresFeuille(navigate, '/taches/projets/modeles')} />,
  }

  return {
    aujourdhui, actifs, enPause, constat, charge, lu, erreur, pauseOuverte, setPauseOuverte, asupprimer, setAsupprimer,
    vide: lu && actifs.length === 0 && enPause.length === 0,
    surAction, poserPriorite, supprime, ouvrir, setNouveau, actionsEcran, feuilleNouveau,
  }
}

/** Le corps de la liste : alerte, squelette, constat, lignes actives, « Nouveau projet », « En pause (n) », suppression.
 *  `ouvertId` : le projet ouvert à droite (surligné) ; `compact` : la colonne du maître-détail (sans constat ni « Coller »). */
export function CorpsListeProjets({ liste, ouvertId = null, compact = false }) {
  const {
    aujourdhui, actifs, enPause, constat, charge, erreur, vide, pauseOuverte, setPauseOuverte, asupprimer, setAsupprimer,
    surAction, poserPriorite, supprime, ouvrir, setNouveau,
  } = liste
  const ouvert = (p) => ouvertId !== null && String(p.id) === String(ouvertId)
  return (
    <>
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      <ChargementTardif actif={!charge} />
      {!compact && actifs.length > 0 && constat ? <p className="ep-constat chiffres">{constatTexte(constat)}</p> : null}

      {vide ? (
        <div className="ep-vide">
          <p>Aucun projet</p>
          <button type="button" className="bouton plein" onClick={() => window.dispatchEvent(new CustomEvent(EVENEMENT_SAISIR, { detail: { coller: true } }))}>
            Coller mes listes
          </button>
        </div>
      ) : null}

      {actifs.length > 0 ? (
        <section className="section" aria-label="Projets actifs">
          <div className="liste" role="list">
            {actifs.map((p) => (
              <LigneProjet key={p.id} projet={p} aujourdhui={aujourdhui} ouvert={ouvert(p)} onOuvrir={ouvrir} onPriorite={poserPriorite} onAction={surAction} />
            ))}
          </div>
        </section>
      ) : null}

      <button type="button" className="ep-nouveau" onClick={() => setNouveau(true)}>
        <FolderPlus className="i" aria-hidden="true" />Nouveau projet
      </button>

      {enPause.length > 0 ? (
        <section className="section">
          <button type="button" className="replie" aria-expanded={pauseOuverte} onClick={() => setPauseOuverte((o) => !o)}>
            <span>{`En pause (${enPause.length})`}</span>
            <ChevronDown className="i i-16" aria-hidden="true" />
          </button>
          {pauseOuverte ? (
            <div className="liste" role="list">
              {enPause.map((p) => (
                <LigneProjet key={p.id} projet={p} aujourdhui={aujourdhui} enPause ouvert={ouvert(p)} onOuvrir={ouvrir} onAction={surAction} />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
      {asupprimer ? <DialogueSupprimer projet={asupprimer} onFermer={() => setAsupprimer(null)} onFait={() => supprime(asupprimer)} /> : null}
    </>
  )
}

/** Les actions de l'écran Projets (Trier, Archive, Modèles), dans le ⋯ de la colonne du maître-détail. */
function MenuListe({ actions }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="bouton-icone" aria-label="Plus d'actions sur la liste des projets">
          <Ellipsis className="i" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {actions.map(({ libelle, onSelect }) => <DropdownMenuItem key={libelle} onSelect={onSelect}>{libelle}</DropdownMenuItem>)}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * R2-067 — la colonne de gauche du maître-détail (≥ 1024 px) : tous les projets, celui qui est ouvert surligné.
 * `j`/`k` ou ↓/↑, le focus dans la colonne, passent au projet suivant / précédent (l'adresse suit : `/taches/projets/<id>`).
 */
export function AsideProjets({ ouvertId }) {
  const navigate = useNavigate()
  const lieu = useLocation()
  const liste = useListeProjets({
    hydrater: true,
    // le projet OUVERT supprimé d'ici : l'écran de droite n'a plus rien à montrer, retour à la liste (qui ouvre le premier)
    surSupprime: (projet) => { if (String(projet.id) === String(ouvertId)) navigate('/taches/projets', { replace: true }) },
  })
  const { actifs, enPause, lu, pauseOuverte, setPauseOuverte } = liste
  const racine = useRef(null)

  // le projet ouvert est en pause : sa ligne est dans « En pause (n) », qu'on déplie une fois pour la montrer
  const enPauseOuvert = enPause.some((p) => String(p.id) === String(ouvertId))
  useEffect(() => { if (enPauseOuvert) setPauseOuverte(true) }, [enPauseOuvert, setPauseOuverte])

  // la ligne ouverte reste visible dans une longue liste ; après un passage au clavier, le focus y revient (la page remonte)
  const focusAuClavier = Boolean(lieu.state?.focusListe)
  useEffect(() => {
    if (!lu) return
    const bouton = racine.current?.querySelector(`[data-projet="${ouvertId}"] .ep-ouvrir`)
    if (!bouton) return
    bouton.scrollIntoView?.({ block: 'nearest' })
    if (focusAuClavier) bouton.focus({ preventScroll: true })
  }, [lu, ouvertId, focusAuClavier])

  const navigables = useMemo(() => [...actifs, ...(pauseOuverte ? enPause : [])], [actifs, enPause, pauseOuverte])
  const surTouche = (e) => {
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return
    if (e.target.closest?.('input, textarea, select, [role="menu"], [role="dialog"]')) return
    const suivant = e.key === 'j' || e.key === 'ArrowDown'
    const precedent = e.key === 'k' || e.key === 'ArrowUp'
    if (!suivant && !precedent) return
    e.preventDefault() // le clavier des listes de tâches (document) ne reprend pas la même touche
    if (navigables.length === 0) return
    const rang = navigables.findIndex((p) => String(p.id) === String(ouvertId))
    const cible = navigables[rang < 0 ? 0 : Math.min(Math.max(rang + (suivant ? 1 : -1), 0), navigables.length - 1)]
    if (!cible || String(cible.id) === String(ouvertId)) return
    liste.ouvrir(cible, { replace: true, state: { focusListe: true } })
  }

  return (
    <aside className="ep-md-liste" aria-label="Liste des projets" ref={racine} onKeyDown={surTouche}>
      <div className="ep-md-defile">
        <div className="ep-md-tete">
          <span className="ep-md-titre">Projets</span>
          <MenuListe actions={liste.actionsEcran} />
        </div>
        <CorpsListeProjets liste={liste} ouvertId={ouvertId} compact />
      </div>
      <FeuilleACrans {...liste.feuilleNouveau} />
    </aside>
  )
}
