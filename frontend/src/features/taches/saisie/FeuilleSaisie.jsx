import { useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { Calendar, X } from 'lucide-react'
import { ReactReduxContext } from 'react-redux'

import { frenchError } from '../../../lib/frenchError'
import {
  annulerGeste, classerErreur, definirProprietaire, nouvelleCle, saisieRapide,
} from '../../../api/tachesApi'
import { proposerAnnuler } from '../lib/gestes'
import { jourCourt } from '../lib/textes'
import ChampSaisie from '../ui/ChampSaisie'
import FeuilleACrans from '../ui/FeuilleACrans'
import SelecteurQuand from '../ui/SelecteurQuand'
import ColleListes, { construireLigne } from './ColleListes'

/* ============================================================================
   TCH82 — Feuille de saisie : « ajouter une tâche en une phrase ». La coquille l'ouvre (bouton
   flottant, « Ajouter une tâche », touche `c t`, événement `taqinor:taches:saisir`).
   Le geste le plus fréquent doit tenir au pouce : le champ a le focus à l'ouverture, Entrée
   envoie, et RIEN de ce qui est tapé n'est refusé ni corrigé — l'analyse du serveur
   (`saisie-rapide/` aperçu) ne fait qu'ajouter des puces, chacune retirable.
   BROUILLON : la phrase est gardée dans le navigateur sous `taches:brouillon:<société>:<compte>`
   (fermer la feuille ne la perd pas ; la carte « Reprendre » d'Aujourd'hui, TCH77, et TCH91 la
   relisent par `lireBrouillon`). Il est vidé à la déconnexion (`taqinor:auth-logout`).
   TCH83 — plus d'une ligne collée (ou « Coller encore ») : la feuille montre l'aperçu de la liste
   (`ColleListes`) au lieu des puces d'une phrase ; l'événement `taqinor:taches:saisir` avec
   `detail.liste` ouvre directement ce mode (« Coller mes listes » de l'état vide d'Aujourd'hui).
   Maquettes : ecran-saisie.html, ecran-saisie-nouveau.html, etat-erreur-champ.html,
   ecran-saisie-liste.html.
   ========================================================================== */

export const PREFIXE_BROUILLON = 'taches:brouillon:'
export const EVENEMENT_DECONNEXION = 'taqinor:auth-logout'
/** Annoncé après une création réussie : les listes ouvertes se rafraîchissent d'elles-mêmes. */
export const EVENEMENT_CREEES = 'taqinor:taches:creees'
const EVENEMENT_SAISIR = 'taqinor:taches:saisir'
const DELAI_APERCU_MS = 300

// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, relu par TCH77/TCH91 et testé directement (D-ENF22)
export const cleBrouillon = (societe, compte) => `${PREFIXE_BROUILLON}${societe ?? '0'}:${compte ?? '0'}`

/** Le brouillon `{ texte, quand, collages?, courant? }` de ce compte, ou `null` (stockage absent, illisible, vide). */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, relu par TCH77/TCH91 et testé directement (D-ENF22)
export function lireBrouillon(societe, compte) {
  try {
    const brut = window.localStorage.getItem(cleBrouillon(societe, compte))
    const lu = brut ? JSON.parse(brut) : null
    return lu && typeof lu.texte === 'string' && lu.texte.trim() ? lu : null
  } catch {
    // stockage bloqué (navigation privée) ou JSON abîmé : pas de brouillon, la saisie reste possible
    return null
  }
}

function ecrireBrouillon(cle, brouillon) {
  try {
    if (brouillon) window.localStorage.setItem(cle, JSON.stringify(brouillon))
    else window.localStorage.removeItem(cle)
  } catch {
    // le brouillon est un confort : s'il ne s'écrit pas, la saisie continue sans lui
    return false
  }
  return true
}

function viderBrouillons() {
  try {
    const cles = []
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const cle = window.localStorage.key(i)
      if (cle?.startsWith(PREFIXE_BROUILLON)) cles.push(cle)
    }
    cles.forEach((cle) => window.localStorage.removeItem(cle))
  } catch {
    // stockage bloqué : rien à vider
    return false
  }
  return true
}

/** Compte connecté, lu sans exiger un Provider (la coquille se monte aussi sans store dans les tests). */
function useCompte() {
  const contexte = useContext(ReactReduxContext)
  const user = contexte?.store?.getState?.()?.auth?.user
  return { societe: user?.active_company_id ?? user?.company_id ?? null, compte: user?.id ?? null }
}

/** Message du champ fautif d'un 400 (`{champ: [..]}` ou `{lignes: {n: {champ: [..]}}}`). */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, relu par TCH77/TCH91 et testé directement (D-ENF22)
export function messageChamps(champs) {
  if (!champs || typeof champs !== 'object') return ''
  const premier = (liste) => (Array.isArray(liste) && typeof liste[0] === 'string' ? liste[0] : '')
  for (const cle of ['texte', 'titre', 'projet_id', 'lien']) {
    const m = premier(champs[cle])
    if (m) return m
  }
  const lignes = champs.lignes && typeof champs.lignes === 'object' ? Object.values(champs.lignes) : []
  for (const ligne of lignes) {
    for (const liste of Object.values(ligne ?? {})) {
      const m = premier(liste)
      if (m) return m
    }
  }
  for (const liste of Object.values(champs)) {
    const m = premier(liste)
    if (m) return m
  }
  return ''
}

function libelleQuand(quand) {
  if (!quand) return 'Quand'
  if (quand.quelque_jour) return 'En réserve'
  if (!quand.jour_prevu) return 'Sans jour'
  const jour = quand.moment === 'soir' ? 'ce soir' : jourCourt(quand.jour_prevu)
  return quand.heure_debut ? `${jour} · ${quand.heure_debut.slice(0, 5)}` : jour
}

/** Corps de l'aperçu : un seul texte, ou plusieurs collages (`textes`) quand on a collé encore. */
function corpsApercu(collages, texte, ignorer) {
  const textes = [...collages, ...(texte.trim() ? [texte] : [])]
  return textes.length > 1 ? { textes, ignorer, apercu: true } : { texte: textes[0] ?? '', ignorer, apercu: true }
}

function phraseErreur(err) {
  const classee = classerErreur(err)
  if (classee.code === 'validation') return messageChamps(classee.champs) || frenchError(err)
  if (classee.code === 'reseau') return 'Pas de réseau : ta saisie est gardée, réessaie.'
  if (classee.code === 'autre_compte') return "Une action d'un autre compte a été retirée de la file."
  return frenchError(err)
}

export default function FeuilleSaisie({ ouverte, onFermer }) {
  const { societe, compte } = useCompte()
  const cle = cleBrouillon(societe, compte)
  const [initial] = useState(() => lireBrouillon(societe, compte))
  const [texte, setTexte] = useState(() => (Array.isArray(initial?.collages) ? initial.courant ?? '' : initial?.texte ?? ''))
  const [collages, setCollages] = useState(() => (Array.isArray(initial?.collages) ? initial.collages : []))
  const [quand, setQuand] = useState(() => initial?.quand ?? null)
  const [quandOuvert, setQuandOuvert] = useState(false)
  const [champOuvert, setChampOuvert] = useState(false)
  const [ignorer, setIgnorer] = useState([])
  const [priorites, setPriorites] = useState({})
  const [apercu, setApercu] = useState(null)
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [cid, setCid] = useState(() => nouvelleCle())

  useEffect(() => { if (compte != null) definirProprietaire(compte) }, [compte])

  // le brouillon suit la frappe ; une phrase vide l'efface
  useEffect(() => {
    const tout = [...collages, texte].filter((t) => t.trim()).join('\n\n')
    ecrireBrouillon(cle, tout ? { texte: tout, quand, collages, courant: texte } : null)
  }, [cle, texte, collages, quand])

  const remettreAZero = useCallback(() => {
    setTexte(''); setCollages([]); setQuand(null); setQuandOuvert(false); setChampOuvert(false); setIgnorer([])
    setPriorites({}); setApercu(null); setErreur(''); setCid(nouvelleCle())
  }, [])

  // déconnexion : plus aucune trace de la phrase (écran, stockage)
  useEffect(() => {
    const surDeconnexion = () => { viderBrouillons(); remettreAZero() }
    window.addEventListener(EVENEMENT_DECONNEXION, surDeconnexion)
    return () => window.removeEventListener(EVENEMENT_DECONNEXION, surDeconnexion)
  }, [remettreAZero])

  // « Coller mes listes » (état vide d'Aujourd'hui) : l'événement de la coquille peut porter `liste` ou `texte`
  useEffect(() => {
    const surSaisir = (e) => {
      const detail = e?.detail ?? {}
      if (typeof detail.texte === 'string') setTexte(detail.texte)
      if (detail.liste) setChampOuvert(true)
    }
    window.addEventListener(EVENEMENT_SAISIR, surSaisir)
    return () => window.removeEventListener(EVENEMENT_SAISIR, surSaisir)
  }, [])

  // Échap ferme, même quand le focus n'est pas dans la feuille (le brouillon, lui, reste)
  useEffect(() => {
    if (!ouverte) return undefined
    const surTouche = (e) => { if (e.key === 'Escape') onFermer?.() }
    document.addEventListener('keydown', surTouche)
    return () => document.removeEventListener('keydown', surTouche)
  }, [ouverte, onFermer])

  // l'analyse : une puce par jeton lu. Jamais bloquante : sans réseau, la phrase part quand même.
  useEffect(() => {
    if (!ouverte || ![...collages, texte].some((t) => t.trim())) return undefined
    let vivant = true
    const minuteur = setTimeout(() => {
      saisieRapide(corpsApercu(collages, texte, ignorer), { cle: null })
        .then((r) => { if (vivant) setApercu({ texte, collages, ignorer, donnees: r.data }) })
        .catch((err) => {
          if (!vivant) return
          setApercu(null)
          if (classerErreur(err).code === 'validation') setErreur(phraseErreur(err))
        })
    }, DELAI_APERCU_MS)
    return () => { vivant = false; clearTimeout(minuteur) }
  }, [ouverte, texte, collages, ignorer])

  const frais = apercu && apercu.texte === texte && apercu.collages === collages && apercu.ignorer === ignorer
    ? apercu.donnees : null
  const donneesListe = frais ?? apercu?.donnees ?? null
  const modeListe =collages.length > 0 || texte.includes('\n') || (frais?.lignes?.length ?? 0) > 1
  const ligne = frais?.lignes?.[0] ?? null
  const nouveauxProjets = useMemo(
    () => (frais?.projets_nouveaux ?? []).map((p) => ({ nom: p.nom, priorite: priorites[p.nom] ?? p.priorite })),
    [frais, priorites],
  )

  const surTexte = (valeur) => { setTexte(valeur); setErreur('') }
  const surIgnorer = (jeton) => setIgnorer((liste) => [...liste, jeton])
  const surPriorite = (nom, niveau) => setPriorites((p) => ({ ...p, [nom]: niveau }))
  const collerEncore = () => {
    if (texte.trim()) setCollages((liste) => [...liste, texte])
    setTexte(''); setChampOuvert(true); setErreur('')
  }

  const creer = async (lignes) => {
    setEnvoi(true)
    setErreur('')
    try {
      const { data } = await saisieRapide({ lignes, apercu: false }, { cle: cid })
      const n = data?.creees?.length ?? lignes.length
      const geste = data?.geste_id
      remettreAZero()
      onFermer?.()
      window.dispatchEvent(new CustomEvent(EVENEMENT_CREEES, { detail: { creees: data?.creees ?? [] } }))
      proposerAnnuler({
        message: n > 1 ? `${n} tâches créées` : 'Ajoutée',
        onAnnuler: geste ? () => annulerGeste(geste) : undefined,
      })
    } catch (err) {
      setErreur(phraseErreur(err))
    } finally {
      setEnvoi(false)
    }
  }

  const envoyer = async () => {
    if (!texte.trim() || envoi) return
    setEnvoi(true)
    setErreur('')
    let donnees = frais
    try {
      donnees = donnees ?? (await saisieRapide(corpsApercu(collages, texte, ignorer), { cle: null })).data
    } catch (err) {
      setErreur(phraseErreur(err))
      setEnvoi(false)
      return
    }
    const lignes = (donnees.lignes ?? []).filter((l) => l.cochee !== false)
      .map((l) => construireLigne(l, { cid, quand, priorites }))
    if (lignes.length === 0) {
      setErreur('Aucune ligne lisible.')
      setEnvoi(false)
      return
    }
    await creer(lignes)
  }

  return (
    <FeuilleACrans ouverte={Boolean(ouverte)} onFermer={onFermer} titre="Ajouter une tâche" cranInitial={modeListe ? '85' : '50'}>
      <div className="feuille-saisie">
        {!(modeListe && donneesListe) || champOuvert ? (
          <ChampSaisie
            valeur={texte}
            onChange={surTexte}
            jetons={modeListe ? [] : ligne?.jetons ?? []}
            alertes={modeListe ? [] : ligne?.alertes ?? []}
            nouveauxProjets={modeListe ? [] : nouveauxProjets}
            onPrioriteProjet={surPriorite}
            onIgnorer={surIgnorer}
            onSoumettre={envoyer}
            erreur={modeListe ? '' : erreur}
          />
        ) : null}
        {modeListe && donneesListe ? (
          <ColleListes
            apercu={donneesListe}
            cid={cid}
            priorites={priorites}
            onPriorite={surPriorite}
            onCreer={creer}
            onCollerEncore={collerEncore}
            envoi={envoi}
            erreur={erreur}
          />
        ) : null}
        {modeListe ? null : (
          <>
            {quandOuvert ? <SelecteurQuand valeur={quand ?? undefined} onChoisir={setQuand} /> : null}
            <div className="saisie-pied">
              <span className="puces">
                <button
                  type="button"
                  className={quand ? 'puce lue' : 'puce vide'}
                  aria-expanded={quandOuvert}
                  onClick={() => setQuandOuvert((v) => !v)}
                >
                  <Calendar className="i i-16" aria-hidden="true" />
                  <span className="chiffres">{libelleQuand(quand)}</span>
                </button>
                {quand ? (
                  <button type="button" className="puce vide" aria-label="Retirer le jour choisi" onClick={() => { setQuand(null); setQuandOuvert(false) }}>
                    <X className="i i-14" aria-hidden="true" />
                  </button>
                ) : null}
              </span>
              <button
                type="button"
                className="bouton plein"
                aria-disabled={!texte.trim() || envoi || undefined}
                onClick={envoyer}
              >
                Ajouter
              </button>
            </div>
          </>
        )}
      </div>
    </FeuilleACrans>
  )
}
