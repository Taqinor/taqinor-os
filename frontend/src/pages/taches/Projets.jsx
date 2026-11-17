import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, FolderPlus } from 'lucide-react'
import { creerProjet, listerProjets, modifierProjet, reordonnerProjet, restaurerProjet, trierProjetsParPriorite } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import CoquilleTaches, { EVENEMENT_SAISIR } from '../../features/taches/coquille/CoquilleTaches'
import { DialogueSupprimer } from '../../features/taches/projets/Dialogues'
import LigneProjet from '../../features/taches/projets/LigneProjet'
import { annoncer, proposerAnnuler } from '../../features/taches/lib/gestes'
import { accord, aujourdhuiIso, jourLong } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH88 — Écran Projets (`/taches/projets`). Maquette : docs/taches/maquettes/projets-liste.html.
   Textes : reference/textes.md §2.6. Contrat : `projets_liste.json` (liste paginée + `constat`).
   Règles de maison : un geste (priorité, pause, « Mettre en haut », tri) met la liste à jour SUR PLACE
   puis réconcilie avec la réponse du serveur — jamais de relecture complète ; un échec remet la ligne
   comme avant et le DIT ; une liste ne se vide jamais sur un rafraîchissement raté.
   ========================================================================== */

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

export default function Projets() {
  const navigate = useNavigate()
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const [actifs, setActifs] = useState([])
  const [enPause, setEnPause] = useState([])
  const [constat, setConstat] = useState(null)
  const [charge, setCharge] = useState(false)
  const [erreur, setErreur] = useState('')
  const [pauseOuverte, setPauseOuverte] = useState(false)
  const [nouveau, setNouveau] = useState(false)
  const [asupprimer, setAsupprimer] = useState(null)

  const lire = useCallback(async () => {
    try {
      const [a, p] = await Promise.all([listerProjets({ statut: 'actif' }), listerProjets({ statut: 'en_pause' })])
      setActifs(lignes(a))
      setConstat(a?.data?.constat ?? null)
      setEnPause(lignes(p))
      setErreur('')
    } catch (err) {
      // la liste déjà à l'écran reste : on dit seulement que le rafraîchissement a échoué
      setErreur(frenchError(err, 'La liste n\'a pas pu être mise à jour. Réessaie.'))
    } finally {
      setCharge(true)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'écran (D-ENF22)
  useEffect(() => { lire() }, [lire])

  const remplacer = (projet) => {
    const maj = (liste) => liste.map((p) => (p.id === projet.id ? { ...p, ...projet } : p))
    setActifs(maj)
    setEnPause(maj)
  }

  const poserPriorite = async (projet, valeur) => {
    if (valeur === projet.priorite) return
    remplacer({ ...projet, priorite: valeur })
    try {
      const { data } = await modifierProjet(projet.id, { priorite: valeur, lock_version: projet.lock_version })
      remplacer(data)
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
    proposerAnnuler({
      message: `« ${projet.nom} » en pause`,
      onAnnuler: async () => {
        const { data } = await modifierProjet(projet.id, { statut: 'actif', lock_version: maj.lock_version })
        setEnPause((l) => l.filter((x) => x.id !== projet.id))
        setActifs((l) => [{ ...projet, ...data }, ...l].sort(parPriorite))
      },
    })
  }

  const reprendre = async (projet) => {
    const sortir = (p) => { setEnPause((l) => l.filter((x) => x.id !== p.id)); setActifs((l) => [{ ...p, statut: 'actif' }, ...l]) }
    const revenir = (p) => { setActifs((l) => l.filter((x) => x.id !== p.id)); setEnPause((l) => [p, ...l]) }
    const maj = await changerStatut(projet, 'actif', sortir, revenir)
    if (maj) setActifs((l) => l.map((x) => (x.id === maj.id ? { ...x, ...maj } : x)))
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
  }

  const creer = async (nom) => {
    const { data } = await creerProjet({ nom })
    const cree = data?.projet ?? data // POST projets/ rend `projet_ecrit` : { projet, deplacees, … }
    setNouveau(false)
    navigate(`/taches/projets/${cree.id}?planifier=1`)
  }

  const ouvrir = (projet) => navigate(`/taches/projets/${projet.id}`)
  const actionsEcran = [
    { libelle: 'Trier par priorité', onSelect: trier },
    { libelle: 'Archive', onSelect: () => navigate('/taches/projets/archive') },
    { libelle: 'Modèles', onSelect: () => navigate('/taches/projets/modeles') },
  ]

  const vide = charge && actifs.length === 0 && enPause.length === 0
  return (
    <CoquilleTaches
      ecran="projets"
      titre="Projets"
      sousTitre={jourLong(aujourdhui)}
      actionsEcran={actionsEcran}
      feuille={{
        ouverte: nouveau,
        onFermer: () => setNouveau(false),
        titre: 'Nouveau projet',
        children: <FormulaireNouveau onCreer={creer} onModeles={() => navigate('/taches/projets/modeles')} />,
      }}
    >
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      {actifs.length > 0 && constat ? <p className="ep-constat chiffres">{constatTexte(constat)}</p> : null}

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
              <LigneProjet key={p.id} projet={p} aujourdhui={aujourdhui} onOuvrir={ouvrir} onPriorite={poserPriorite} onAction={surAction} />
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
                <LigneProjet key={p.id} projet={p} aujourdhui={aujourdhui} enPause onOuvrir={ouvrir} onAction={surAction} />
              ))}
            </div>
          ) : null}
        </section>
      ) : null}
      {asupprimer ? <DialogueSupprimer projet={asupprimer} onFermer={() => setAsupprimer(null)} onFait={() => supprime(asupprimer)} /> : null}
    </CoquilleTaches>
  )
}
