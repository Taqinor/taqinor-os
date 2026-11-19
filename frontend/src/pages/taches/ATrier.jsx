import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, Ellipsis, Link as LienIcone, ListTodo, Sparkles } from 'lucide-react'

import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { SuggereParLErp } from '../../features/taches/atrier/Suggestions'
import TrierUneParUne from '../../features/taches/atrier/TrierUneParUne'
import CaseRonde from '../../features/taches/ui/CaseRonde'
import ChargementTardif from '../../features/taches/ui/ChargementTardif'
import { useApresCreation, useOuvrirFiche } from '../../features/taches/lib/fiche'
import { useClavierListe } from '../../features/taches/lib/clavierListe'
import { ajusterBadgeATrier, chargerBadgeTaches } from '../../features/taches/useBadgeTaches'
import { frenchError } from '../../lib/frenchError'
import {
  annulerGeste, classerErreur, convertirActivites, creerProjet, listerToutesLesTaches,
  listerTousLesProjets, saisieRapide, traiterLot, lireAujourdhui } from '../../api/tachesApi'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../ui/DropdownMenu'
import { proposerAnnuler } from '../../features/taches/lib/gestes'
import { accord, aujourdhuiIso, echeanceTexte, jourCourt } from '../../features/taches/lib/textes'
import SelecteurQuand, { ajouterJours } from '../../features/taches/ui/SelecteurQuand'

/* ============================================================================
   TCH86 — Écran « À trier » (`/taches/a-trier`) : la boîte de réception des tâches sans jour ni
   projet. Bandeau « {n} à-faire personnels dans Activités · Tout convertir · Voir » ; par ligne
   Aujourd'hui · Demain · Projet… · ⋯ (Choisir un jour · En réserve · Garder sans projet · Supprimer) ;
   ⋯ de l'écran : Trier une par une · Ranger avec le Copilote (≥ 5 lignes) ; « Tout ranger » applique le
   rangement proposé ; « En réserve » = les tâches gardées sans jour.
   UN seul chemin d'écriture : `taches/lot/` (une action, `ids`), la ligne quitte la liste TOUT DE SUITE et
   revient à sa place si le serveur refuse ; la liste ne se vide jamais sur un échec de lecture et un geste ne
   la relit pas. « Suggéré par l'ERP » (TCH167, `atrier/Suggestions.jsx`) ouvre la liste À trier : Ajouter / Pas utile.
   R2-024 — la pastille rouge de l'onglet suit chaque geste : corrigée tout de suite (−1 par carte qui part), puis relue du
   serveur (`chargerBadgeTaches({ force: true })`) ; elle revient (+1) si la carte revient.
   R2-036 — j / k parcourent les cartes, Entrée ouvre la fiche, e · d · m comme sur Aujourd'hui ; aucune touche seule ne
   coche ni ne retire une carte (spec-7 §5).
   Maquette : docs/taches/maquettes/ecran-a-trier.html. Source : textes.md §2.5.
   ========================================================================== */

const SEUIL_COPILOTE = 5
const REFUS_CONVERSION = {
  assignee_a_un_collegue: 'Assigné à un collègue : reste dans Activités.',
  deja_convertie: 'Déjà convertie.',
  close: 'Déjà faite dans Activités.',
  introuvable: 'Introuvable.',
}

/** Les mentions d'une ligne, lues des données servies (aucune inventée) : la source « Suggéré par l'ERP », le lien,
 *  l'échéance, puis le repère du rangement proposé par le Copilote. */
function MetaATrier({ tache, propose, aujourdhui }) {
  const ech = tache.echeance ? echeanceTexte(tache.echeance, aujourdhui) : null
  const mentions = []
  if (tache.source === 'suggestion') {
    mentions.push(<span key="erp" className="marque-erp"><Sparkles className="i i-14" aria-hidden="true" />Suggéré par l'ERP</span>)
  }
  if (tache.lien?.libelle) {
    mentions.push(<span key="lien"><LienIcone className="i i-14" aria-hidden="true" /><span className="sr">Lié à : </span>{tache.lien.libelle}</span>)
  }
  if (ech) mentions.push(<span key="ech" className={ech.ton === 'alerte' ? 'alerte chiffres' : 'fort chiffres'}>{ech.texte}</span>)
  // une tâche gardée en réserve peut avoir un projet (« Comparer deux devis d'impression » · ● Salon Solaire Expo)
  if (tache.projet) {
    mentions.push(<span key="projet" data-p={tache.projet.couleur}><i className="point" aria-hidden="true" /><span className="projet-nom">{tache.projet.nom}</span></span>)
  }
  if (propose !== undefined) {
    mentions.push(<span key="repere" className="atrier-repere">{propose ? 'Rangée par le Copilote' : 'Non rangée'}</span>)
    if (propose) mentions.push(<span key="suggere" className="fort">{`Projet suggéré : ${propose.nom}`}</span>)
  }
  return mentions.length > 0 ? <div className="meta">{mentions}</div> : null
}

/** Une ligne (ecran-a-trier.html) : case ronde, titre, mentions, puis les gestes en LIENS (Aujourd'hui · Demain ·
 *  Projet… · ⋯) — jamais de grosses pilules. Cocher = `lot/` `terminer`, comme les autres gestes. */
function LigneATrier({ tache, propose, reserve, actions, aujourdhui, onChoisirJour, onProjet, onOuvrir }) {
  const [menu, setMenu] = useState(false)
  return (
    <div className="ligne tri" role="listitem" data-ligne={`tache:${tache.id}`}>
      <CaseRonde titre={tache.titre} onBasculer={() => actions.terminer(tache)} />
      <div className="ligne-corps">
        {/* le titre est un bouton (la fiche s'ouvre d'un toucher ou d'Entrée) : c'est aussi ce que j / k focalisent */}
        <button type="button" className="ligne-corps-bouton" onClick={() => onOuvrir(tache)}>
          <span className="titre">{tache.titre}</span>
        </button>
        <MetaATrier tache={tache} propose={propose} aujourdhui={aujourdhui} />
        <div className="tri-gestes">
          <button type="button" className="geste" onClick={() => actions.aujourdhui(tache)}>Aujourd'hui</button>
          <button type="button" className="geste" onClick={() => actions.demain(tache)}>Demain</button>
          <button type="button" className="geste" onClick={() => onProjet(tache)}>Projet…</button>
          <DropdownMenu open={menu} onOpenChange={setMenu}>
            <DropdownMenuTrigger asChild>
              <button type="button" className="geste icone" aria-label={`Autres gestes pour « ${tache.titre} »`}>
                <Ellipsis className="i i-16" aria-hidden="true" />
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
      <div className="ligne-fin" />
    </div>
  )
}

export default function ATrier({ aujourdhui = aujourdhuiIso() }) {
  const navigate = useNavigate()
  const [lignes, setLignes] = useState([])
  const [reserveLignes, setReserveLignes] = useState([])
  const [reserveLue, setReserveLue] = useState(false)
  const [reserveOuverte, setReserveOuverte] = useState(false)
  const [echecReserve, setEchecReserve] = useState('')
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

  const lire = useCallback(() => listerToutesLesTaches({ vue: 'boite' })
    .then((taches) => { setLignes(taches); setEchec(''); setCharge(true) })
    .catch((err) => { setEchec(frenchError(err)); setCharge(true) }), [])
  // « En réserve {n} » est replié en bas de la liste (ecran-a-trier.html) : son compte se lit dès l'ouverture ;
  // une lecture en échec laisse les lignes déjà lues (jamais une fausse réserve vide)
  const lireReserve = useCallback(() => listerToutesLesTaches({ vue: 'quelque_jour' })
    .then((taches) => { setReserveLignes(taches); setReserveLue(true); setEchecReserve('') })
    .catch((err) => setEchecReserve(frenchError(err))), [])

  useEffect(() => { lire(); lireReserve() }, [lire, lireReserve])
  // une création ailleurs (saisie, collage, file rejouée) : les listes se relisent une fois, sans recharger la page
  useApresCreation(useCallback(() => { lire(); lireReserve() }, [lire, lireReserve]))
  const ouvrirFiche = useOuvrirFiche()
  const relirePastille = useCallback(() => chargerBadgeTaches({ force: true }), [])

  useEffect(() => {
    lireAujourdhui({ jour: aujourdhui })
      .then((r) => setAConvertir(r.data?.a_trier?.a_convertir ?? 0))
      .catch(() => setAConvertir(0))
  }, [aujourdhui])

  const chargerProjets = useCallback(() => {
    if (projets.length === 0) listerTousLesProjets().then((l) => setProjets(l)).catch((err) => setErreur(frenchError(err)))
  }, [projets.length])

  /** Un geste sur une ligne (de la boîte ou de la réserve dépliée) : elle part TOUT DE SUITE, revient à sa place si
   *  le serveur refuse ; mise en réserve depuis la boîte, elle rejoint aussitôt « En réserve ». */
  const appliquer = useCallback(async (tache, action, valeurs, message) => {
    const enReserve = reserveLignes.some((l) => l.id === tache.id)
    const setSource = enReserve ? setReserveLignes : setLignes
    const index = (enReserve ? reserveLignes : lignes).findIndex((l) => l.id === tache.id)
    const versReserve = !enReserve && action === 'planifier' && Boolean(valeurs?.quelque_jour)
    setErreur('')
    setSource((liste) => liste.filter((l) => l.id !== tache.id))
    if (!enReserve) ajusterBadgeATrier(-1) // R2-024 : la carte quitte la boîte, la pastille la suit tout de suite
    if (versReserve) setReserveLignes((liste) => (liste.some((l) => l.id === tache.id) ? liste : [...liste, { ...tache, quelque_jour: true }]))
    const remettre = () => {
      if (!enReserve) ajusterBadgeATrier(1)
      if (versReserve) setReserveLignes((liste) => liste.filter((l) => l.id !== tache.id))
      setSource((liste) => {
        if (liste.some((l) => l.id === tache.id)) return liste
        const suite = [...liste]
        suite.splice(Math.max(index, 0), 0, tache)
        return suite
      })
    }
    try {
      const { data } = await traiterLot({ ids: [tache.id], action, valeurs })
      if ((data?.refusees ?? []).some((r) => r.id === tache.id)) { remettre(); setErreur('Cette tâche a changé : elle est restée dans la liste.'); return }
      proposerAnnuler({
        message,
        onAnnuler: data?.geste_id ? async () => { await annulerGeste(data.geste_id); remettre(); relirePastille() } : undefined,
      })
    } catch (err) {
      remettre()
      setErreur(classerErreur(err).code === 'reseau' ? 'Possible une fois connecté' : frenchError(err))
    } finally {
      relirePastille()
    }
  }, [lignes, reserveLignes, relirePastille])

  const actions = {
    aujourdhui: (t) => appliquer(t, 'planifier', { jour_prevu: aujourdhui }, 'Mise à aujourd\'hui'),
    demain: (t) => { const jour = ajouterJours(aujourdhui, 1); return appliquer(t, 'planifier', { jour_prevu: jour }, `Prévue ${jourCourt(jour, aujourdhui)}`) },
    reserve: (t) => appliquer(t, 'planifier', { quelque_jour: true }, 'En réserve'),
    sansProjet: (t) => appliquer(t, 'garder_sans_projet', {}, 'Gardée sans projet'),
    supprimer: (t) => appliquer(t, 'supprimer', {}, 'Supprimée'),
    terminer: (t) => appliquer(t, 'terminer', {}, 'Faite'),
    projet: (t, projetId) => {
      const projet = projets.find((p) => p.id === projetId)
      return appliquer(t, 'deplacer', { projet_id: projetId }, `Déplacée dans « ${projet?.nom ?? 'ce projet'} »`)
    },
  }

  const nouveauProjet = async (tache, nom) => {
    try {
      const { data } = await creerProjet({ nom }, { erreurSousLeChamp: true })
      const cree = data?.projet ?? data // POST projets/ rend `projet_ecrit` : { projet, deplacees, … }
      setProjets((liste) => [...liste, cree])
      await appliquer(tache, 'deplacer', { projet_id: cree.id }, `Déplacée dans « ${cree.nom} »`)
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
        await lire()
        proposerAnnuler({
          message: n > 1 ? `${n} tâches créées` : 'Ajoutée',
          onAnnuler: data.geste_id ? async () => { await annulerGeste(data.geste_id); await lire(); relirePastille() } : undefined,
        })
      }
    } catch (err) {
      setErreur(frenchError(err))
    } finally {
      relirePastille()
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
    ajusterBadgeATrier(-ids.length)
    try {
      const { data } = await traiterLot({ ids, action: 'deplacer', valeurs: { par_tache: parTache } })
      setPropositions(null)
      const n = data?.appliquees?.length ?? ids.length
      proposerAnnuler({
        message: n >= 2 ? `${n} tâches rangées` : `${n} tâche rangée`, // accord sur le même nombre que l'affiché
        onAnnuler: data?.geste_id ? async () => { await annulerGeste(data.geste_id); await lire(); relirePastille() } : undefined,
      })
    } catch (err) {
      setLignes(avant)
      ajusterBadgeATrier(ids.length)
      setErreur(frenchError(err))
    } finally {
      relirePastille()
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

  // R2-036 — j / k, Entrée, e · d · m : jamais Espace ni une touche qui coche ou retire une carte
  const racine = useClavierListe((action, { cle }) => {
    const id = Number(String(cle ?? '').split(':')[1])
    const tache = [...lignes, ...reserveLignes].find((l) => l.id === id)
    if (!tache) return
    if (action === 'renommer' || action === 'heure') ouvrirFiche(tache.id)
    else if (action === 'quand') choisirJour(tache)
    else if (action === 'deplacer') ouvrirProjet(tache)
  }, { actif: !jourPour && !projetPour && !uneParUne })

  const actionsEcran = []
  if (lignes.length > 0) actionsEcran.push({ libelle: 'Trier une par une', onSelect: () => { chargerProjets(); setUneParUne(true) } })
  if (lignes.length >= SEUIL_COPILOTE) actionsEcran.push({ libelle: 'Ranger avec le Copilote', onSelect: rangerAvecCopilote })

  const proposees = propositions ? Object.keys(propositions).length : 0
  const ligneDe = (tache, reserve) => (
    <LigneATrier
      key={tache.id}
      tache={tache}
      reserve={reserve}
      propose={!reserve && propositions ? (propositions[tache.id] ?? null) : undefined}
      actions={actions}
      aujourdhui={aujourdhui}
      onChoisirJour={choisirJour}
      onProjet={ouvrirProjet}
      onOuvrir={(t) => ouvrirFiche(t.id)}
    />
  )

  return (
    <CoquilleTaches
      ecran="a-trier"
      titre="À trier"
      // ecran-a-trier.html : « 5 sans jour ni projet » — le compte des lignes de la boîte, dit dès qu'elle est lue
      sousTitre={charge && !echec && lignes.length > 0 ? `${lignes.length} sans jour ni projet` : null}
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
        // la phrase sur UNE ligne, les deux gestes en liens dessous (jamais écrasée par deux boutons à droite)
        <div className="bandeau atrier-bandeau" role="region" aria-label="Activités personnelles">
          <span className="bandeau-icone" aria-hidden="true"><ListTodo className="i i-16" /></span>
          <div className="bandeau-texte">
            <p className="bandeau-titre">{`${accord(aConvertir, 'à-faire personnel', 'à-faire personnels')} dans Activités`}</p>
            <div className="tri-gestes">
              <button type="button" className="geste" onClick={convertir}>Tout convertir</button>
              <button type="button" className="geste" onClick={() => navigate('/activites')}>Voir</button>
            </div>
          </div>
        </div>
      ) : null}
      {refus.map((phrase) => <p key={phrase} className="apercu-note" role="status">{phrase}</p>)}

      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}
      {echec ? <p className="erreur-champ" role="alert">{echec}</p> : null}
      {echecReserve && !echec ? <p className="erreur-champ" role="alert">{echecReserve}</p> : null}
      <ChargementTardif actif={!charge} />

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
        <SuggereParLErp
          onAjoutee={(tache) => { setLignes((liste) => (liste.some((l) => l.id === tache.id) ? liste : [...liste, tache])); relirePastille() }}
          onRetiree={(id) => { setLignes((liste) => liste.filter((l) => l.id !== id)); relirePastille() }}
        />
      ) : null}

      {/* `display: contents` : le clavier a sa racine sans toucher à la mise en page des sections */}
      <div ref={racine} style={{ display: 'contents' }}>
      {!uneParUne ? (
        <section className="section premiere" aria-label="À trier">
          <div className="liste" role="list">{lignes.map((tache) => ligneDe(tache, false))}</div>
          {charge && !echec && lignes.length === 0 ? (
            <div className="vide-etat">
              <p className="vide-phrase">Rien à trier</p>
              <button type="button" className="bouton second" onClick={() => navigate('/taches/projets')}>Voir mes projets</button>
            </div>
          ) : null}
        </section>
      ) : null}

      {/* « En réserve {n} ⌄ » replié EN BAS de la liste (ecran-a-trier.html), jamais un commutateur en tête */}
      {!uneParUne && reserveLue && (reserveLignes.length > 0 || reserveOuverte) ? (
        <div className="replies">
          <button type="button" className="replie" aria-expanded={reserveOuverte} onClick={() => setReserveOuverte((v) => !v)}>
            <span>En réserve</span>
            <span className="compte chiffres">{reserveLignes.length}</span>
            <ChevronDown className="i i-16" aria-hidden="true" />
          </button>
          {reserveOuverte ? (
            <section className="section" aria-label="En réserve">
              <div className="liste" role="list">{reserveLignes.map((tache) => ligneDe(tache, true))}</div>
              {reserveLignes.length === 0 ? <div className="vide-etat"><p className="vide-phrase">Rien en réserve</p></div> : null}
            </section>
          ) : null}
        </div>
      ) : null}
      </div>
    </CoquilleTaches>
  )
}
