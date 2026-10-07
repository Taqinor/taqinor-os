import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import { toastWarning } from '../../lib/toast'
import { reviserEtOuvrir } from '../ventes/reviserDevis'
import {
  LIBELLE_CHAMP, MESSAGE_DEROGATION_RESERVEE, MESSAGE_MOTIF_OBLIGATOIRE,
  bloquageElectrique, refusServeur, texteBloquant,
} from './refusDevis'

/* ============================================================================
   CAL38 — LA SORTIE VERS LE DEVIS d'un calepinage, et elle n'existait nulle
   part.
   ----------------------------------------------------------------------------
   DÉCISION FONDATEUR D3 : un calepinage SANS devis est de première classe. Il
   lui faut donc une sortie EXPLICITE — sans elle, une conception dessinée dans
   le module autonome n'a aucun moyen de devenir un chiffrage, et l'écran est
   une impasse.

   DEUX GESTES, JAMAIS DEUX BOUTONS EN MÊME TEMPS :
   * aucun devis lié  → « Générer le devis » (CAL24, `generer-devis`) ;
   * un devis lié     → « Resynchroniser le devis » (CAL25, `sync-devis`).
   C'est l'état SERVEUR (`calepinage.devis` de l'agrégat de détail) qui tranche,
   jamais une supposition d'écran.

   AUCUN TEXTE DE REFUS N'EST FABRIQUÉ ICI. Le pré-vol de composition (422) et
   le conflit « devis déjà envoyé » (409) portent déjà leur phrase FRANÇAISE,
   écrite par le serveur ventes et propagée MOT POUR MOT par
   `services/devis.py::_refus_devis`. La réécrire côté client, c'est apprendre
   deux règles différentes à l'utilisateur pour un seul comportement. Le seul
   texte que ce fichier écrit lui-même est celui des cas où le serveur n'a RIEN
   dit (panne réseau) — et il le dit.

   L'ERREUR NOMME SON CHAMP (règle fondateur 08/09) : le refus serveur est une
   paire `{champ: message}` ; le bandeau NOMME le champ en français et le
   message s'affiche dessous, tel quel. Jamais un « non enregistré » générique.
   ========================================================================== */

/* Lot 2 critique #23 / #29 — le décodeur des refus (libellés de champ,
   refus électrique 422, refus serveur) est PARTAGÉ avec la route devis
   (`refusDevis.js`) : une seule lecture des refus du pont devis. */
export { MESSAGE_DEROGATION_RESERVEE, MESSAGE_MOTIF_OBLIGATOIRE } from './refusDevis'

/* Le verdict INDÉTERMINÉ d'un succès : les manquantes, sans rien bloquer. */
function manquantesElectriques(data) {
  const electrique = data?.electrique
  if (!electrique || electrique.verdict !== 'indetermine') return []
  return (Array.isArray(electrique.manquantes) ? electrique.manquantes : [])
    .filter((m) => typeof m === 'string' && m.trim()).map((m) => m.trim())
}

/* ACAL95 — CE QUE LA GÉNÉRATION ET LA RESYNCHRO N'ONT PAS PU FAIRE se lit à
   l'écran AVANT toute navigation ou rechargement (contrat
   `calepinage_publication.json`) : avertissements et marques manquantes du
   serveur, MOT POUR MOT ; lignes de kit ajoutées ; « Aucun changement ». Sans
   rien à dire, le geste reste celui d'aujourd'hui (navigation / rechargement). */
function messagesDuServeur(data) {
  const messages = []
  for (const cle of ['avertissements', 'marques_manquantes']) {
    for (const m of Array.isArray(data?.[cle]) ? data[cle] : []) {
      if (typeof m === 'string' && m.trim()) messages.push(m.trim())
    }
  }
  return messages
}

function libelleLignesAjoutees(n) {
  const nombre = Number(n) || 0
  if (nombre <= 0) return null
  return nombre === 1 ? '1 ligne ajoutée au devis' : `${nombre} lignes ajoutées au devis`
}

/* ACAL94 — l'écran est ENREGISTRÉ avant « Générer / Resynchroniser » (prop
   `enregistrerAvant`, l'UNIQUE fonction d'enregistrement de l'atelier) : le
   serveur compose sur la conception que l'on VOIT, jamais sur l'ancienne.
   Échec d'enregistrement ⇒ aucun geste serveur, aucun rechargement. « Réviser »
   prévient des retouches non enregistrées (`aDesRetouches`) sans jamais
   refuser (D-QJR5-2). */
export const MESSAGE_ENREGISTREMENT_ECHOUE = 'La conception à l’écran n’a pas pu être '
  + 'enregistrée : rien n’a été envoyé au devis. Corrigez puis réessayez.'
export const MESSAGE_RETOUCHES_NON_ENREGISTREES = 'Retouches non enregistrées : elles ne '
  + 'seront pas reprises dans la V2.'

export default function BoutonDevis({
  calepinageId, detail = null, lectureSeule = false, onRecharger, onRelire,
  enregistrerAvant = null, aDesRetouches = null, revisionPossible = false,
}) {
  const navigate = useNavigate()
  // ACAL171 — le droit SERVI par l'agrégat (`permissions.peut_deroger`,
  // calepinage_approuver), jamais deviné côté écran.
  const peutDeroger = !!detail?.permissions?.peut_deroger
  const [enCours, setEnCours] = useState(false)
  // ACAL171 — le refus électrique : `{geste, detail, bloquants, derogationPossible}`.
  const [bloquage, setBloquage] = useState(null)
  const [motif, setMotif] = useState('')
  const [motifErreur, setMotifErreur] = useState(null)
  const [refus, setRefus] = useState(null)
  const [conflit, setConflit] = useState(null)
  // ACAL95 — le retour du serveur à LIRE avant de poursuivre :
  // `{messages, lignes, inchange, devisId, suite: 'recharger' | 'ouvrir' | null}`.
  const [retour, setRetour] = useState(null)
  // ACAL94 — avertissement (jamais un refus) avant une révision.
  const [retouches, setRetouches] = useState(false)

  // L'ÉTAT VIENT DU SERVEUR, et d'UNE SEULE lecture : l'agrégat de détail
  // (CAL17) est chargé par `AtelierPanneaux` et descendu ici en prop. Le
  // charger une seconde fois ferait deux appels pour la même vérité — et deux
  // vérités le jour où l'une des deux serait périmée.
  // ACAL93 — en LECTURE SEULE, le seul geste offert est « Réviser (v2) », quand
  // le serveur le dit possible (jamais masqué par rôle ni refusé).
  if (!detail || (lectureSeule && !(revisionPossible && detail?.devis?.id))) return null

  const devisLie = detail.devis ?? null
  const variantes = detail.variantes ?? {}
  const totalVariantes = Number(variantes.total) || 0
  // GARDE DES VARIANTES (CAL38) : quand ce calepinage porte PLUSIEURS options
  // et qu'AUCUNE n'est retenue, chiffrer reviendrait à choisir à la place du
  // commercial. Sans aucune variante, c'est la conception du calepinage
  // elle-même que le serveur chiffre (`services/devis.py::_exiger_layout`) —
  // il n'y a alors rien à choisir, et bloquer là ferait un bouton mort.
  const varianteManquante = totalVariantes > 0 && !variantes.retenue_id
  const desactive = enCours || varianteManquante

  const executer = async (appel) => {
    if (enCours) return
    setRefus(null)
    setConflit(null)
    setRetour(null)
    setEnCours(true)
    try {
      return await appel()
    } catch (erreur) {
      const statut = erreur?.response?.status
      const data = erreur?.response?.data
      const electrique = bloquageElectrique(erreur)
      if (electrique) {
        setBloquage((avant) => ({ ...electrique, geste: avant?.geste ?? null }))
        return null
      }
      // ACAL171 — un motif refusé par le serveur se lit SOUS le champ.
      if (statut === 400 && data?.derogation_electrique) {
        setMotifErreur(refusServeur(erreur).message)
        return null
      }
      if (statut === 409) {
        setConflit({
          detail: refusServeur(erreur).message,
          revision_possible: !!data?.revision_possible,
        })
        return null
      }
      setRefus(refusServeur(erreur))
      return null
    } finally {
      setEnCours(false)
    }
  }

  // ACAL94 — range l'écran d'abord ; `false` = rien ne part au serveur.
  const enregistrerDabord = async () => {
    if (typeof enregistrerAvant !== 'function') return true
    setRefus(null)
    setConflit(null)
    setRetour(null)
    let ok = false
    try {
      ok = (await enregistrerAvant()) !== false
    } catch {
      ok = false
    }
    if (!ok) setRefus({ champ: 'roof_layout', message: MESSAGE_ENREGISTREMENT_ECHOUE })
    return ok
  }

  const generer = async (corps = {}) => {
    if (enCours || !(await enregistrerDabord())) return
    if (!corps.derogation_electrique) setBloquage({ geste: 'generer' })
    const res = await executer(
      () => calepinageApi.calepinages.genererDevis(calepinageId, corps))
    const nouveau = res?.data?.devis
    if (!nouveau) return
    setBloquage(null)
    setMotif('')
    // ACAL95 — ce que la composition n'a pas pu faire se lit AVANT de partir :
    // pas de navigation immédiate, un lien « Ouvrir le devis » à la place.
    // ACAL171 — un verdict INDÉTERMINÉ (manquantes) se lit de même.
    const messages = messagesDuServeur(res.data)
    const manquantes = manquantesElectriques(res.data)
    if (messages.length > 0 || manquantes.length > 0) {
      setRetour({
        messages, manquantes, lignes: null, inchange: false, devisId: nouveau, suite: 'ouvrir',
      })
      return
    }
    // On rouvre la conception SUR le devis : c'est là que le commercial
    // continue son geste, exactement comme depuis la fiche lead.
    navigate(`/ventes/devis/${nouveau}/design`)
  }

  const relireEtRecharger = async () => {
    // On RELIT l'agrégat plutôt que de deviner le nouvel état du devis.
    await onRelire?.()
    await onRecharger?.()
  }

  const resynchroniser = async (corps = {}) => {
    if (enCours || !(await enregistrerDabord())) return
    if (!corps.derogation_electrique) setBloquage({ geste: 'sync' })
    const res = await executer(
      () => calepinageApi.calepinages.syncDevis(calepinageId, corps))
    if (!res) return
    setBloquage(null)
    setMotif('')
    const data = res?.data ?? {}
    const messages = messagesDuServeur(data)
    const manquantes = manquantesElectriques(data)
    const lignes = libelleLignesAjoutees(data.lignes_ajoutees)
    // ACAL95 — « Aucun changement » se DIT ; rien n'a bougé, rien à recharger.
    if (data.inchange) {
      setRetour({ messages, manquantes, lignes: null, inchange: true, devisId: null, suite: null })
      return
    }
    // Quelque chose à lire : le rechargement attend « J'ai lu ».
    if (messages.length > 0 || manquantes.length > 0 || lignes) {
      setRetour({ messages, manquantes, lignes, inchange: false, devisId: null, suite: 'recharger' })
      return
    }
    await relireEtRecharger()
  }

  // ACAL171 — « Passer outre et générer » : le MÊME geste, relancé avec
  // `derogation_electrique: {motif}` ; un motif vide est refusé sous le champ.
  const passerOutre = async () => {
    const saisi = motif.trim()
    if (!saisi) {
      setMotifErreur(MESSAGE_MOTIF_OBLIGATOIRE)
      return
    }
    setMotifErreur(null)
    const corps = { derogation_electrique: { motif: saisi } }
    if (bloquage?.geste === 'sync') await resynchroniser(corps)
    else await generer(corps)
  }

  const confirmerLecture = async () => {
    setRetour(null)
    await relireEtRecharger()
  }

  const reviser = async () => {
    if (!devisLie?.id) return
    // ACAL94 — avertir des retouches non enregistrées, et réviser QUAND MÊME.
    let nonEnregistrees = false
    try { nonEnregistrees = typeof aDesRetouches === 'function' && !!aDesRetouches() } catch { nonEnregistrees = false }
    setRetouches(nonEnregistrees)
    if (nonEnregistrees) toastWarning(MESSAGE_RETOUCHES_NON_ENREGISTREES)
    // ACAL93 — UNE seule fonction de révision (`reviserEtOuvrir`) ; la V2
    // s'ouvre sur sa CONCEPTION.
    if (enCours) return
    setEnCours(true)
    let v2 = null
    try {
      await reviserEtOuvrir({
        devis: devisLie,
        onApres: (nouveau) => { v2 = nouveau },
        navigate: () => { if (v2?.id != null) navigate(`/ventes/devis/${v2.id}/design`) },
      })
    } finally {
      setEnCours(false)
    }
  }

  if (lectureSeule) {
    return (
      <div className="space-y-2" data-testid="cal-bouton-devis">
        <button
          type="button"
          onClick={reviser}
          disabled={enCours}
          data-testid="cal-devis-reviser-lecture-seule"
          className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Réviser (v2)
        </button>
        {retouches && (
          <p className="text-xs text-brass-300" role="status" data-testid="cal-devis-retouches">
            {MESSAGE_RETOUCHES_NON_ENREGISTREES}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-2" data-testid="cal-bouton-devis">
      {devisLie ? (
        <button
          type="button"
          onClick={() => resynchroniser()}
          disabled={desactive}
          data-testid="cal-resynchroniser-devis"
          className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {enCours ? 'Resynchronisation…' : 'Resynchroniser le devis'}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => generer()}
          disabled={desactive}
          data-testid="cal-generer-devis"
          className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {enCours ? 'Génération…' : 'Générer le devis'}
        </button>
      )}

      {devisLie?.reference && (
        <p className="text-xs text-lune-faint">
          Devis lié : <span className="text-lune-soft">{devisLie.reference}</span>
        </p>
      )}

      {/* ACAL109 (D-ACAL-2) — ce que « Générer le devis » chiffre, DIT : la
          conception courante, dont la variante retenue fait partie. */}
      {totalVariantes > 0 && variantes.retenue_id && (
        <p className="text-xs text-lune-faint" data-testid="cal-devis-ce-qui-est-chiffre">
          Générer le devis chiffre la conception courante : la variante retenue en
          fait partie (la retenir l’y a écrite).
        </p>
      )}

      {/* La raison de la désactivation, TOUJOURS dite : un bouton grisé sans
          explication est une impasse silencieuse. */}
      {varianteManquante && (
        <p className="text-xs text-lune-faint" role="status"
          data-testid="cal-devis-variante-manquante">
          Choisissez d’abord une variante retenue.
        </p>
      )}

      {/* REFUS SERVEUR — le bandeau NOMME le champ, le message est celui du
          serveur, mot pour mot. */}
      {refus && (
        <div className="border border-alert-300/40 p-3" data-testid="cal-devis-refus">
          <p className="tech-label text-alert-300">
            {LIBELLE_CHAMP[refus.champ] || refus.champ}
          </p>
          <p className="mt-1 text-sm text-alert-300" role="alert">{refus.message}</p>
        </div>
      )}

      {/* ACAL171 — refus ÉLECTRIQUE : les bloquants du serveur, mot pour mot ;
          la dérogation n'est offerte qu'à un approbateur. */}
      {bloquage?.bloquants && (
        <div className="border border-alert-300/40 p-3" data-testid="cal-devis-bloquants">
          {bloquage.detail && (
            <p className="text-sm text-alert-300" role="alert">{bloquage.detail}</p>
          )}
          <ul className="mt-1 space-y-1 text-sm text-alert-300">
            {bloquage.bloquants.map((b, i) => (
              <li key={`${b?.code ?? 'b'}-${i}`} data-testid="cal-devis-bloquant">
                {texteBloquant(b)}
                {b?.detail && <span className="block text-xs text-lune-faint">{b.detail}</span>}
              </li>
            ))}
          </ul>
          {bloquage.derogationPossible && (peutDeroger ? (
            <div className="mt-3 space-y-2">
              <label className="block text-xs text-lune-soft" htmlFor="cal-devis-motif">
                Motif de la dérogation
              </label>
              <textarea
                id="cal-devis-motif"
                value={motif}
                onChange={(e) => { setMotif(e.target.value); setMotifErreur(null) }}
                data-testid="cal-devis-motif"
                className="w-full border border-lune-faint/40 bg-transparent p-2 text-sm"
              />
              {motifErreur && (
                <p className="text-xs text-alert-300" role="alert" data-testid="cal-devis-motif-erreur">
                  {motifErreur}
                </p>
              )}
              <button
                type="button"
                onClick={passerOutre}
                disabled={enCours}
                data-testid="cal-devis-passer-outre"
                className="inline-flex items-center gap-2 border border-alert-300 px-4 py-2 text-sm font-bold text-alert-300 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {bloquage.geste === 'sync' ? 'Passer outre et resynchroniser' : 'Passer outre et générer'}
              </button>
            </div>
          ) : (
            <p className="mt-2 text-xs text-lune-faint" data-testid="cal-devis-derogation-reservee">
              {MESSAGE_DEROGATION_RESERVEE}
            </p>
          ))}
        </div>
      )}

      {/* ACAL94 — la révision part, mais les retouches non enregistrées sont DITES. */}
      {retouches && (
        <p className="text-xs text-brass-300" role="status" data-testid="cal-devis-retouches">
          {MESSAGE_RETOUCHES_NON_ENREGISTREES}
        </p>
      )}

      {/* ACAL95 — le retour du serveur, LU avant de poursuivre. */}
      {retour && (
        <div className="border border-brass-400/40 p-3" data-testid="cal-devis-avertissements">
          {retour.inchange && (
            <p className="text-sm text-lune-soft" role="status">Aucun changement</p>
          )}
          {retour.lignes && (
            <p className="text-sm text-lune-soft" role="status">{retour.lignes}</p>
          )}
          {retour.manquantes?.length > 0 && (
            <div data-testid="cal-devis-indetermine">
              <p className="text-sm text-lune-soft" role="status">
                Verdict électrique indéterminé — à compléter :
              </p>
              <ul className="mt-1 space-y-1 text-sm text-brass-300">
                {retour.manquantes.map((m) => <li key={m}>{m}</li>)}
              </ul>
            </div>
          )}
          {retour.messages.length > 0 && (
            <ul className="mt-1 space-y-1 text-sm text-brass-300" role="status">
              {retour.messages.map((m) => <li key={m}>{m}</li>)}
            </ul>
          )}
          {retour.suite === 'recharger' && (
            <button
              type="button"
              onClick={confirmerLecture}
              data-testid="cal-devis-j-ai-lu"
              className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-4 py-2 text-sm font-bold text-brass-300"
            >
              J’ai lu
            </button>
          )}
          {retour.suite === 'ouvrir' && retour.devisId && (
            <Link
              to={`/ventes/devis/${retour.devisId}/design`}
              data-testid="cal-devis-ouvrir"
              className="mt-3 inline-block text-sm font-semibold text-brass-300 underline"
            >
              Ouvrir le devis
            </Link>
          )}
        </div>
      )}

      {/* 409 — le document est parti chez le client. Le motif est celui du
          serveur ; l'écran choisit seulement d'offrir, ou non, la révision. */}
      {conflit && (
        <div className="border border-brass-400/40 p-3" data-testid="cal-devis-conflit">
          <p className="text-sm text-lune-soft" role="status">{conflit.detail}</p>
          {conflit.revision_possible && (
            <button
              type="button"
              onClick={reviser}
              disabled={enCours}
              data-testid="cal-devis-reviser"
              className="mt-3 inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Réviser (v2)
            </button>
          )}
        </div>
      )}
    </div>
  )
}
