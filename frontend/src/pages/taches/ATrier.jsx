import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Ellipsis } from 'lucide-react'

import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import TrierUneParUne from '../../features/taches/atrier/TrierUneParUne'
import { frenchError } from '../../lib/frenchError'
import {
  annulerGeste, classerErreur, convertirActivites, creerProjet, listerToutesLesTaches,
  listerTousLesProjets, saisieRapide, traiterLot, lireAujourdhui } from '../../api/tachesApi'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../ui/DropdownMenu'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import { accord, aujourdhuiIso, jourCourt } from '../../features/taches/lib/textes'
import SelecteurQuand, { ajouterJours } from '../../features/taches/ui/SelecteurQuand'

/* ============================================================================
   TCH86 — Écran « À trier » (`/taches/a-trier`) : la boîte de réception des tâches sans jour ni
   projet. Bandeau « {n} à-faire personnels dans Activités · Tout convertir · Voir » ; par ligne
   Aujourd'hui · Demain · Projet… · ⋯ (Choisir un jour · En réserve · Garder sans projet · Supprimer) ;
   ⋯ de l'écran : Trier une par une · Ranger avec le Copilote (≥ 5 lignes) ; « Tout ranger » applique le
   rangement proposé ; « En réserve » = les tâches gardées sans jour.
   UN seul chemin d'écriture : `taches/lot/` (une action, `ids`), la ligne quitte la liste TOUT DE SUITE et
   revient à sa place si le serveur refuse ; la liste ne se vide jamais sur un échec de lecture et un geste ne
   la relit pas. « Suggéré par l'ERP » vient en F4 (TCH167).
   Maquette : docs/taches/maquettes/ecran-a-trier.html. Source : textes.md §2.5.
   ========================================================================== */

const SEUIL_COPILOTE = 5
const REFUS_CONVERSION = {
  assignee_a_un_collegue: 'Assigné à un collègue : reste dans Activités.',
  deja_convertie: 'Déjà convertie.',
  close: 'Déjà faite dans Activités.',
  introuvable: 'Introuvable.',
}

/** Une ligne : titre, repère du rangement proposé, gestes en puces, menu ⋯. */
function LigneATrier({ tache, propose, reserve, actions, onChoisirJour, onProjet }) {
  const [menu, setMenu] = useState(false)
  return (
    <div className="atrier-ligne" role="listitem" data-ligne={`tache:${tache.id}`}>
      <div className="atrier-titre">
        <span className="titre">{tache.titre}</span>
        {propose === undefined ? null : (
          <span className="atrier-repere">{propose ? 'Rangée par le Copilote' : 'Non rangée'}</span>
        )}
      </div>
      {propose ? <span className="puce lue">{`Projet suggéré : ${propose.nom}`}</span> : null}
      <div className="puces">
        <button type="button" className="puce" onClick={() => actions.aujourdhui(tache)}>Aujourd'hui</button>
        <button type="button" className="puce" onClick={() => actions.demain(tache)}>Demain</button>
        <button type="button" className="puce" onClick={() => onProjet(tache)}>Projet…</button>
        <DropdownMenu open={menu} onOpenChange={setMenu}>
          <DropdownMenuTrigger asChild>
            <button type="button" className="bouton-icone" aria-label={`Autres gestes pour « ${tache.titre} »`}>
              <Ellipsis className="i" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => onChoisirJour(tache)}>Choisir un jour</DropdownMenuItem>
            {reserve ? null : <DropdownMenuItem onSelect={() => actions.reserve(tache)}>En réserve</DropdownMenuItem>}
            {reserve ? null : <DropdownMenuItem onSelect={() => actions.sansProjet(tache)}>Garder sans projet</DropdownMenuItem>}
            <DropdownMenuSeparator />
            <DropdownMenuItem destructive onSelect={() => actions.supprimer(tache)}>Supprimer</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}

export default function ATrier({ aujourdhui = aujourdhuiIso() }) {
  const navigate = useNavigate()
  const [vue, setVue] = useState('boite')
  const [lignes, setLignes] = useState([])
  const [charge, setCharge] = useState(false)
  const [echec, setEchec] = useState('')
  const [erreur, setErreur] = useState('')
  const [aConvertir, setAConvertir] = useState(0)
  const [refus, setRefus] = useState([])
  const [projets, setProjets] = useState([])
  const [cible, setCible] = useState(null)
  const [projetPour, setProjetPour] = useState(null)
  const [jourPour, setJourPour] = useState(null)
  const [propositions, setPropositions] = useState(null)
  const [uneParUne, setUneParUne] = useState(false)

  // une autre liste : on ne montre jamais les lignes de l'ancienne le temps de la lecture
  const changerVue = (nom) => { if (nom !== vue) { setLignes([]); setCharge(false); setPropositions(null); setVue(nom) } }

  const lire = useCallback((nom) => listerToutesLesTaches({ vue: nom })
    .then((taches) => { setLignes(taches); setEchec(''); setCharge(true) })
    .catch((err) => { setEchec(frenchError(err)); setCharge(true) }), [])

  useEffect(() => { lire(vue) }, [vue, lire])

  useEffect(() => {
    lireAujourdhui({ jour: aujourdhui })
      .then((r) => setAConvertir(r.data?.a_trier?.a_convertir ?? 0))
      .catch(() => setAConvertir(0))
  }, [aujourdhui])

  const chargerProjets = useCallback(() => {
    if (projets.length === 0) listerTousLesProjets().then((l) => setProjets(l)).catch((err) => setErreur(frenchError(err)))
  }, [projets.length])

  /** Un geste sur une ligne : elle part TOUT DE SUITE, revient à sa place si le serveur refuse. */
  const appliquer = useCallback(async (tache, action, valeurs, message) => {
    const index = lignes.findIndex((l) => l.id === tache.id)
    setErreur('')
    setLignes((liste) => liste.filter((l) => l.id !== tache.id))
    const remettre = () => setLignes((liste) => {
      if (liste.some((l) => l.id === tache.id)) return liste
      const suite = [...liste]
      suite.splice(Math.max(index, 0), 0, tache)
      return suite
    })
    try {
      const { data } = await traiterLot({ ids: [tache.id], action, valeurs })
      if ((data?.refusees ?? []).some((r) => r.id === tache.id)) { remettre(); setErreur('Cette tâche a changé : elle est restée dans la liste.'); return }
      proposerAnnuler({
        message,
        onAnnuler: data?.geste_id ? async () => { await annulerGeste(data.geste_id); remettre() } : undefined,
      })
    } catch (err) {
      remettre()
      setErreur(classerErreur(err).code === 'reseau' ? 'Pas de réseau : la tâche est restée dans la liste.' : frenchError(err))
    }
  }, [lignes])

  const actions = {
    aujourdhui: (t) => appliquer(t, 'planifier', { jour_prevu: aujourdhui }, 'Mise à aujourd\'hui'),
    demain: (t) => { const jour = ajouterJours(aujourdhui, 1); return appliquer(t, 'planifier', { jour_prevu: jour }, `Prévue ${jourCourt(jour, aujourdhui)}`) },
    reserve: (t) => appliquer(t, 'planifier', { quelque_jour: true }, 'En réserve'),
    sansProjet: (t) => appliquer(t, 'garder_sans_projet', {}, 'Gardée sans projet'),
    supprimer: (t) => appliquer(t, 'supprimer', {}, 'Supprimée'),
    projet: (t, projetId) => {
      const projet = projets.find((p) => p.id === projetId)
      return appliquer(t, 'deplacer', { projet_id: projetId }, `Déplacée dans « ${projet?.nom ?? 'ce projet'} »`)
    },
  }

  const nouveauProjet = async (tache, nom) => {
    try {
      const { data } = await creerProjet({ nom })
      setProjets((liste) => [...liste, data])
      await appliquer(tache, 'deplacer', { projet_id: data.id }, `Déplacée dans « ${data.nom} »`)
    } catch (err) {
      setErreur(frenchError(err))
    }
  }

  const convertir = async () => {
    try {
      const { data } = await convertirActivites({ toutes: true })
      const n = data.converties?.length ?? 0
      setRefus([...new Set((data.refusees ?? []).map((r) => REFUS_CONVERSION[r.raison]).filter(Boolean))])
      setAConvertir((c) => Math.max(c - n, 0))
      if (n > 0) {
        await lire(vue)
        proposerAnnuler({
          message: n > 1 ? `${n} tâches créées` : 'Ajoutée',
          onAnnuler: data.geste_id ? async () => { await annulerGeste(data.geste_id); await lire(vue) } : undefined,
        })
      }
    } catch (err) {
      setErreur(frenchError(err))
    }
  }

  const rangerAvecCopilote = async () => {
    try {
      const { data } = await saisieRapide({ ids: lignes.map((l) => l.id), apercu: true }, { cle: null })
      const trouvees = {}
      ;(data.lignes ?? []).forEach((l) => {
        const projet = l.projet_suggere ?? (l.champs?.projet_id ? projets.find((p) => p.id === l.champs.projet_id) : null)
        if (l.tache_id != null && projet) trouvees[l.tache_id] = { id: projet.id, nom: projet.nom }
      })
      setPropositions(trouvees)
    } catch (err) {
      setErreur(frenchError(err))
    }
  }

  const toutRanger = async () => {
    const parTache = Object.fromEntries(Object.entries(propositions).map(([id, p]) => [id, { projet_id: p.id }]))
    const ids = Object.keys(parTache).map(Number)
    if (ids.length === 0) return
    const avant = lignes
    setLignes((liste) => liste.filter((l) => !ids.includes(l.id)))
    try {
      const { data } = await traiterLot({ ids, action: 'deplacer', valeurs: { par_tache: parTache } })
      setPropositions(null)
      proposerAnnuler({
        message: `${accord(data?.appliquees?.length ?? ids.length, 'tâche')} rangée${ids.length > 1 ? 's' : ''}`,
        onAnnuler: data?.geste_id ? async () => { await annulerGeste(data.geste_id); await lire(vue) } : undefined,
      })
    } catch (err) {
      setLignes(avant)
      setErreur(frenchError(err))
    }
  }

  const ouvrirProjet = (tache) => { chargerProjets(); setCible(tache); setProjetPour(true) }
  const choisirJour = (tache) => { setCible(tache); setJourPour(true) }
  const poserJour = (quand) => {
    const tache = cible
    setJourPour(null)
    if (!tache) return
    if (quand.quelque_jour) actions.reserve(tache)
    else if (quand.jour_prevu) appliquer(tache, 'planifier', { jour_prevu: quand.jour_prevu, ...(quand.heure_debut ? { heure_debut: quand.heure_debut } : {}) }, `Prévue ${jourCourt(quand.jour_prevu, aujourdhui)}`)
  }

  const actionsEcran = []
  if (lignes.length > 0) actionsEcran.push({ libelle: 'Trier une par une', onSelect: () => { chargerProjets(); setUneParUne(true) } })
  if (lignes.length >= SEUIL_COPILOTE && vue === 'boite') actionsEcran.push({ libelle: 'Ranger avec le Copilote', onSelect: rangerAvecCopilote })

  const proposees = propositions ? Object.keys(propositions).length : 0
  const reserve = vue === 'quelque_jour'

  return (
    <CoquilleTaches
      ecran="a-trier"
      titre="À trier"
      actionsEcran={actionsEcran}
      selecteurProjet={{
        ouverte: Boolean(projetPour), onFermer: () => setProjetPour(null), projets, sansProjet: false,
        onChoisir: (projetId) => { setProjetPour(null); if (cible) actions.projet(cible, projetId) },
        onNouveau: (nom) => { setProjetPour(null); if (cible) nouveauProjet(cible, nom) },
      }}
      feuille={{
        ouverte: Boolean(jourPour), onFermer: () => setJourPour(null), titre: 'Choisir un jour',
        children: <SelecteurQuand aujourdhui={aujourdhui} onChoisir={poserJour} />,
      }}
    >
      {aConvertir > 0 ? (
        <div className="bandeau" role="region" aria-label="Activités personnelles">
          <span className="bandeau-texte">{`${accord(aConvertir, 'à-faire personnel', 'à-faire personnels')} dans Activités`}</span>
          <button type="button" className="bouton discret" onClick={convertir}>Tout convertir</button>
          <button type="button" className="bouton discret" onClick={() => navigate('/activites')}>Voir</button>
        </div>
      ) : null}
      {refus.map((phrase) => <p key={phrase} className="apercu-note" role="status">{phrase}</p>)}

      <div className="segmente" role="radiogroup" aria-label="Liste">
        <button type="button" role="radio" aria-checked={!reserve} onClick={() => changerVue('boite')}>À trier</button>
        <button type="button" role="radio" aria-checked={reserve} onClick={() => changerVue('quelque_jour')}>En réserve</button>
      </div>

      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}
      {echec ? <p className="erreur-champ" role="alert">{echec}</p> : null}

      {uneParUne ? (
        <TrierUneParUne
          taches={lignes}
          actions={actions}
          projets={projets}
          onNouveauProjet={nouveauProjet}
          onFin={() => setUneParUne(false)}
        />
      ) : null}

      {propositions && proposees > 0 ? (
        <div className="carte-actions">
          <button type="button" className="bouton plein" onClick={toutRanger}>Tout ranger</button>
        </div>
      ) : null}

      {!uneParUne ? (
        <section className="section" aria-label={reserve ? 'En réserve' : 'À trier'}>
          {reserve ? <h2 className="section-titre"><span>En réserve</span></h2> : null}
          <div className="liste" role="list">
            {lignes.map((tache) => (
              <LigneATrier
                key={tache.id}
                tache={tache}
                reserve={reserve}
                propose={propositions ? (propositions[tache.id] ?? null) : undefined}
                actions={actions}
                onChoisirJour={choisirJour}
                onProjet={ouvrirProjet}
              />
            ))}
          </div>
          {charge && !echec && lignes.length === 0 ? (
            <div className="vide-etat">
              <p className="vide-phrase">{reserve ? 'Rien en réserve' : 'Rien à trier'}</p>
              {reserve ? null : <button type="button" className="bouton second" onClick={() => navigate('/taches/projets')}>Voir mes projets</button>}
            </div>
          ) : null}
        </section>
      ) : null}
    </CoquilleTaches>
  )
}
