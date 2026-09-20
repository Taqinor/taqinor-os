import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import ventesApi from '../../api/ventesApi'

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

/** Les champs que le pont devis peut nommer, en français lisible. */
const LIBELLE_CHAMP = {
  roof_layout: 'Conception de toiture',
  composition: 'Composition',
  client: 'Rattachement client',
  calepinage: 'Calepinage',
  devis: 'Devis',
  taux_tva: 'Taux de TVA',
  remise_globale: 'Remise globale',
  detail: 'Devis',
}

/**
 * Le refus SERVEUR, décomposé en `{champ, message}`. Rien n'est reformulé :
 * on choisit seulement QUEL message montrer quand le serveur en donne
 * plusieurs, et on nomme le champ fautif.
 */
function refusServeur(erreur) {
  const data = erreur?.response?.data
  if (typeof data === 'string' && data.trim()) {
    return { champ: 'detail', message: data.trim() }
  }
  if (data && typeof data === 'object') {
    if (typeof data.detail === 'string' && data.detail.trim()) {
      return { champ: 'detail', message: data.detail.trim() }
    }
    if (Array.isArray(data.errors) && data.errors.length > 0) {
      return { champ: 'composition', message: String(data.errors[0]) }
    }
    const premier = Object.entries(data).find(([, v]) => v)
    if (premier) {
      const [champ, brut] = premier
      const message = Array.isArray(brut) ? brut.join(' ') : String(brut)
      return { champ, message }
    }
  }
  return {
    champ: 'detail',
    message: 'Le serveur n’a pas répondu. Réessayez dans un instant.',
  }
}

export default function BoutonDevis({ calepinageId, lectureSeule = false, onRecharger }) {
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [refus, setRefus] = useState(null)
  const [conflit, setConflit] = useState(null)

  // `relecture` — une relecture DEMANDÉE (après une resynchronisation) passe
  // par l'effet, jamais par un `setState` posé dans le corps de l'effet
  // (react-hooks v7 : cascade de rendus).
  const [relecture, setRelecture] = useState(0)

  // L'ÉTAT VIENT DU SERVEUR : l'agrégat de détail (CAL17) porte le devis lié et
  // le compte des variantes. L'écran ne déduit ni l'un ni l'autre.
  useEffect(() => {
    let annule = false
    // `Promise.resolve` : un client qui ne rendrait pas de promesse ne doit
    // pas faire exploser l'effet — l'écran se contente alors de ne rien
    // afficher, plutôt qu'un bouton qui prétendrait connaître l'état du devis.
    Promise.resolve(calepinageApi.calepinages.get(calepinageId))
      .then((res) => { if (!annule) setDetail(res?.data ?? null) })
      .catch(() => { if (!annule) setDetail(null) })
    return () => { annule = true }
  }, [calepinageId, relecture])

  if (!detail || lectureSeule) return null

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
    setEnCours(true)
    try {
      return await appel()
    } catch (erreur) {
      const statut = erreur?.response?.status
      const data = erreur?.response?.data
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

  const generer = async () => {
    const res = await executer(
      () => calepinageApi.calepinages.genererDevis(calepinageId, {}))
    const nouveau = res?.data?.devis
    if (!nouveau) return
    // On rouvre la conception SUR le devis : c'est là que le commercial
    // continue son geste, exactement comme depuis la fiche lead.
    navigate(`/ventes/devis/${nouveau}/design`)
  }

  const resynchroniser = async () => {
    const res = await executer(
      () => calepinageApi.calepinages.syncDevis(calepinageId, {}))
    if (!res) return
    setRelecture((n) => n + 1)
    await onRecharger?.()
  }

  const reviser = async () => {
    if (!devisLie?.id) return
    const res = await executer(() => ventesApi.reviserDevis(devisLie.id))
    const nouveau = res?.data?.id
    if (!nouveau) return
    navigate(`/ventes/devis/${nouveau}/design`)
  }

  return (
    <div className="space-y-2" data-testid="cal-bouton-devis">
      {devisLie ? (
        <button
          type="button"
          onClick={resynchroniser}
          disabled={desactive}
          data-testid="cal-resynchroniser-devis"
          className="inline-flex items-center gap-2 border border-brass-400 px-5 py-3 text-base font-bold text-brass-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {enCours ? 'Resynchronisation…' : 'Resynchroniser le devis'}
        </button>
      ) : (
        <button
          type="button"
          onClick={generer}
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
