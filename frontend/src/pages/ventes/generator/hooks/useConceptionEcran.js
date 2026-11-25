// AGEN11 (D-ACAL-97, contrôle C4-E7) — L'ÉCRAN DEVIS LIT LE MOTEUR UNIQUE.
//
// Plus aucun calcul de production, d'économie ni de payback dans le
// navigateur : avec un lead, l'écran montre d'abord la conception RANGÉE
// (`GET conception/<lead>/`) ; dès qu'une valeur est tapée (facture, kWh,
// nombre de panneaux), l'aperçu SANS écriture du même moteur
// (`POST conception/apercu/`, ADEV152) est demandé — un devis sans lead
// l'obtient sur ses seules valeurs tapées. « Calcul en cours » pendant l'appel.
// Forme : `apps/ventes/contract_samples/conception_lead.json`. Les nombres
// partent TELS QUE TAPÉS (jamais arrondis, jamais corrigés ici).
import { useEffect, useState } from 'react'
import ventesApi from '../../../../api/ventesApi'

//: Délai avant l'appel d'aperçu (la frappe reste instantanée).
export const DELAI_APERCU_MS = 500

const tape = (v) => (v === null || v === undefined ? '' : String(v).trim())

/** Le corps de `POST conception/apercu/` pour ce que l'écran a TAPÉ, ou `null`
 *  (rien de tapé, ou marché agricole : son aperçu est celui du pompage). */
export function corpsApercuConception({
  leadId, modeInstallation, fHiver, fEte, realBillMode, realBillKwh, nbPanneaux,
}) {
  if (!modeInstallation || modeInstallation === 'agricole') return null
  const entrees = {}
  if (tape(fHiver)) entrees.facture_hiver = tape(fHiver)
  if (modeInstallation === 'residentiel' && tape(fEte) && Number(fEte) > 0) {
    entrees.facture_ete = tape(fEte)
    entrees.ete_differente = true
  }
  if (realBillMode === 'kwh' && tape(realBillKwh)) entrees.conso_mensuelle_kwh = tape(realBillKwh)
  const lead = leadId ? Number(leadId) : null
  if (!lead && !Object.keys(entrees).length) return null
  // Sans lead, le marché du devis est une valeur tapée de l'écran.
  if (!lead) entrees.type_installation = modeInstallation
  const imposes = modeInstallation === 'residentiel' && nbPanneaux > 0 ? { nb_panneaux: nbPanneaux } : {}
  if (lead && !Object.keys(entrees).length && !Object.keys(imposes).length) return null
  return { lead, calepinage: null, entrees, imposes }
}

const valeur = (table, cle) => table?.[cle]?.valeur ?? null

/** Les chiffres AFFICHÉS d'une conception servie (aucun calcul : des lectures).
 *  `null` tant qu'elle n'est pas complète. */
export function chiffresConception(conception) {
  if (!conception || conception.etat !== 'complet') return null
  const valeurs = conception.valeurs || {}
  const cles = Object.keys(valeurs)
  if (!cles.length) return null
  const sans = valeurs.sans || valeurs[cles[0]]
  const avec = valeurs.avec || sans
  return {
    productionSans: valeur(sans, 'production_annuelle'),
    productionAvec: valeur(avec, 'production_annuelle'),
    ecoSans: valeur(sans, 'economies_annuelles'),
    ecoAvec: valeur(avec, 'economies_annuelles'),
    paybackSans: valeur(sans, 'payback'),
    paybackAvec: valeur(avec, 'payback'),
  }
}

/** La conception de l'écran : `conception` (l'aperçu dès qu'il a répondu,
 *  sinon la version rangée du lead), `servie` (la version rangée seule : son
 *  payback est celui du devis de référence, comme le PDF), `chargement`,
 *  `erreur` (message du serveur, en français). */
export function useConceptionEcran({ leadId, corps }) {
  const [servie, setServie] = useState(null)
  const [apercu, setApercu] = useState({ donnees: null, chargement: false, erreur: null })

  useEffect(() => {
    let vivant = true
    const lire = async () => {
      if (!leadId) { setServie(null); return }
      try {
        const { data } = await ventesApi.getConceptionLead(leadId)
        if (vivant) setServie(data?.etat ? data : null)
      } catch {
        if (vivant) setServie(null)  // 404 « conception_absente » : rien de rangé
      }
    }
    lire()
    return () => { vivant = false }
  }, [leadId])

  const cle = corps ? JSON.stringify(corps) : ''
  useEffect(() => {
    const ctrl = new AbortController()
    let minuterie = null
    const demander = async () => {
      try {
        const { data } = await ventesApi.apercuConception(JSON.parse(cle), { signal: ctrl.signal })
        if (!ctrl.signal.aborted) setApercu({ donnees: data?.etat ? data : null, chargement: false, erreur: null })
      } catch (err) {
        if (ctrl.signal.aborted) return
        const detail = err?.response?.data?.detail
        setApercu({ donnees: null, chargement: false,
          erreur: typeof detail === 'string' ? detail : 'Aperçu du moteur indisponible.' })
      }
    }
    const lancer = async () => {
      if (!cle) { setApercu({ donnees: null, chargement: false, erreur: null }); return }
      setApercu((a) => ({ ...a, chargement: true, erreur: null }))
      minuterie = setTimeout(demander, DELAI_APERCU_MS)
    }
    lancer()
    return () => { if (minuterie) clearTimeout(minuterie); ctrl.abort() }
  }, [cle])

  return { conception: apercu.donnees ?? servie, servie, chargement: apercu.chargement, erreur: apercu.erreur }
}
