// VNT46 (Groupe VNT, D-VNT-1/3) — les gestes d'une facture de la vente, en UN
// crochet réutilisé par la liste des factures (FactureRow) et, en M2, par le
// panneau de vente : annuler (avoir automatique), supprimer (BROUILLON-<id>
// seulement), émettre, reçu d'un paiement, PDF. Aucun toast : l'erreur est
// rendue par l'écran, SOUS la facture (`erreur`), avec le message du serveur
// (règle fondateur « erreurs → le champ fautif »). Aucune règle d'argent ici :
// le serveur reste seul juge (avoir, directive d'acompte, référence légale).
import { useCallback, useContext, useState } from 'react'
import { ReactReduxContext } from 'react-redux'
import ventesApi from '../../../api/ventesApi'
import { fetchFactures } from '../store/ventesSlice'
import { openPdfBlob, messageErreurBlob } from '../../../utils/pdfBlob'
import { aplatirErreurs, bandeau } from './erreursVente'
import { ouvrirPdfFacture } from './facturePdf'

const REPLIS = {
  annuler: "Annulation impossible.",
  supprimer: 'Suppression impossible.',
  emettre: 'Émission impossible.',
  recu: 'Reçu indisponible pour le moment.',
  pdf: 'PDF de la facture indisponible pour le moment.',
  envoyer: 'Envoi impossible.',
}

/** `Quittance_<numero_recu>.pdf` lu de l'en-tête serveur, sinon repli sur le paiement. */
export function nomQuittance(headers, paiement) {
  const brut = headers?.['content-disposition'] || headers?.get?.('content-disposition') || ''
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(String(brut))
  if (m && m[1]) return decodeURIComponent(m[1])
  return `Quittance_${paiement?.numero_recu || paiement?.id}.pdf`
}

/**
 * @returns {{
 *   occupe: string|null,
 *   erreur: {geste: string, factureId: number, message: string, code: string}|null,
 *   effacerErreur: () => void,
 *   facturesChargees: () => Array,
 *   annuler: Function, supprimer: Function, emettre: Function, recu: Function, pdf: Function,
 * }}
 */
export function useActionsVente({ onSucces } = {}) {
  // Contexte redux OPTIONNEL : une ligne rendue hors <Provider> (test, aperçu)
  // fonctionne, sans rafraîchissement de liste.
  const redux = useContext(ReactReduxContext)
  const [occupe, setOccupe] = useState(null)
  const [erreur, setErreur] = useState(null)

  // VNT76 — le panneau de vente (fiche lead) rafraîchit SA source (`onSucces`,
  // le GET détail du lead) ; la liste des factures garde son store redux.
  const rafraichir = useCallback(() => {
    if (onSucces) onSucces()
    else redux?.store?.dispatch?.(fetchFactures())
  }, [redux, onSucces])

  const facturesChargees = useCallback(
    () => redux?.store?.getState?.()?.ventes?.factures ?? [],
    [redux],
  )

  const effacerErreur = useCallback(() => setErreur(null), [])

  const lireErreur = async (err, geste) => {
    let message
    let code = ''
    const data = err?.response?.data
    if (data instanceof Blob) {
      message = await messageErreurBlob(err, { fallback: REPLIS[geste] })
    } else {
      const liste = aplatirErreurs(data)
      message = bandeau(liste)
      code = liste[0]?.code || ''
      if (!err?.response) message = 'Serveur injoignable — vérifiez la connexion puis réessayez.'
    }
    return { message: message || REPLIS[geste], code }
  }

  const executer = async (geste, facture, action, { rafraichirListe = true, cle = facture.id } = {}) => {
    setOccupe(`${geste}:${cle}`)
    setErreur(null)
    try {
      const res = await action()
      if (rafraichirListe) rafraichir()
      return { ok: true, data: res?.data }
    } catch (err) {
      const { message, code } = await lireErreur(err, geste)
      setErreur({ geste, factureId: facture.id, message, code })
      return { ok: false, message, code }
    } finally {
      setOccupe(null)
    }
  }

  /** Annule la facture ; `directive` = `{action, facture_cible?}` si elle porte de l'argent. */
  const annuler = (facture, directive) => executer('annuler', facture, () =>
    ventesApi.annulerFacture(facture.id, directive ? { acompte: directive } : undefined))

  /** Supprime un `BROUILLON-<id>` (le serveur refuse tout numéro légal). */
  const supprimer = (facture) => executer('supprimer', facture, () => ventesApi.supprimerFacture(facture.id))

  const emettre = (facture) => executer('emettre', facture, () => ventesApi.emettreFacture(facture.id))

  /** Ouvre la quittance d'UN paiement (`paiement` = ligne de `facture.paiements`) ;
   *  `occupe` vaut alors `recu:<id du paiement>`. */
  const recu = (facture, paiement) => executer('recu', facture, async () => {
    const res = await ventesApi.recuPdfPaiement(paiement.id)
    await openPdfBlob(res.data, nomQuittance(res.headers, paiement))
    return res
  }, { rafraichirListe: false, cle: paiement.id })

  /** Génère puis ouvre le PDF de la facture (sondage borné de `facturePdf.js`). */
  const pdf = async (facture, options) => {
    setOccupe(`pdf:${facture.id}`)
    setErreur(null)
    try {
      const issue = await ouvrirPdfFacture(facture.id, facture.reference, options)
      if (issue === 'ouvert') return { ok: true }
      const message = issue === 'attente'
        ? 'PDF encore en préparation : réessayez dans quelques instants.'
        : REPLIS.pdf
      setErreur({ geste: 'pdf', factureId: facture.id, message, code: issue })
      return { ok: false, message, code: issue }
    } finally {
      setOccupe(null)
    }
  }

  /** VNT76 — message WhatsApp construit par le serveur (consigné au fil) ;
   *  l'écran montre ensuite le lien wa.me, jamais d'envoi automatique. */
  const whatsapp = (facture, params = { modele: 'facture', langue: 'fr' }) => executer(
    'envoyer', facture, () => ventesApi.whatsappFacture(facture.id, params), { rafraichirListe: false })

  /** VNT76 — envoi par e-mail (destinataire par défaut : le client, côté serveur). */
  const envoyerEmail = (facture) => executer(
    'envoyer', facture, () => ventesApi.envoyerEmailFacture(facture.id), { rafraichirListe: false })

  return {
    occupe, erreur, effacerErreur, facturesChargees,
    annuler, supprimer, emettre, recu, pdf, whatsapp, envoyerEmail,
  }
}

export default useActionsVente
