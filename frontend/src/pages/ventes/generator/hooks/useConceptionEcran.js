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
//: E7d (M2) — l'échec sans phrase du serveur (5xx, réseau) ; l'écran offre « Réessayer ».
export const APERCU_INDISPONIBLE = 'Aperçu indisponible — Réessayer'

const tape = (v) => (v === null || v === undefined ? '' : String(v).trim())

/** Le corps de `POST conception/apercu/` pour ce que l'écran a TAPÉ, ou `null`
 *  (rien de tapé, ou marché agricole : son aperçu est celui du pompage).
 *  E7d (revue lot 4, B2) — `consommation` : celle que le devis ENREGISTRE
 *  (`etatDevis.consommationImposeeDeEtat`, le sélecteur de l'enregistrement),
 *  imposée au moteur (`imposes.consommation`) ; `null` ⇒ celle du lead. */
export function corpsApercuConception({
  leadId, modeInstallation, fHiver, fEte, nbPanneaux, consommation = null, investissement = null,
}) {
  if (!modeInstallation || modeInstallation === 'agricole') return null
  const entrees = {}
  if (tape(fHiver)) entrees.facture_hiver = tape(fHiver)
  if (modeInstallation === 'residentiel' && tape(fEte) && Number(fEte) > 0) {
    entrees.facture_ete = tape(fEte)
    entrees.ete_differente = true
  }
  const lead = leadId ? Number(leadId) : null
  const imposes = modeInstallation === 'residentiel' && nbPanneaux > 0 ? { nb_panneaux: nbPanneaux } : {}
  if (consommation) imposes.consommation = consommation
  if (!lead && !Object.keys(entrees).length && !consommation) return null
  if (lead && !Object.keys(entrees).length && !Object.keys(imposes).length) return null
  // Sans lead, le marché du devis est une valeur tapée de l'écran.
  if (!lead) entrees.type_installation = modeInstallation
  // E7d (M1) — le TTC de vente des lignes de chaque option (> 0 seulement) : le
  // prix du payback servi ; il ne déclenche jamais à lui seul un aperçu.
  const prix = Object.fromEntries(Object.entries(investissement || {})
    .filter(([, v]) => Number.isFinite(Number(v)) && Number(v) > 0).map(([k, v]) => [k, Number(v)]))
  return { lead, calepinage: null, entrees, imposes, ...(Object.keys(prix).length ? { investissement: prix } : {}) }
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
 *  `erreur` (message du serveur, en français).
 *  E7d (M3) — les clés de la garde de péremption du dimensionnement
 *  (`decisionSizing`) : `cleCourante` (ce qui est à l'écran), `cleServie` /
 *  `cleErreur` (ce qui a produit la réponse ou l'échec) ; un lead SANS version
 *  rangée (404) est prévisualisé sur ses seules colonnes (corps vide). */
export function useConceptionEcran({ leadId, corps }) {
  const [rangee, setRangee] = useState({ lead: null, donnees: null })
  const [apercu, setApercu] = useState({ donnees: null, chargement: false, erreur: null, cle: '' })
  const [essai, setEssai] = useState(0)  // E7d (M2) — « Réessayer » relance le même corps

  useEffect(() => {
    let vivant = true
    const lire = async () => {
      if (!leadId) { setRangee({ lead: null, donnees: null }); return }
      try {
        const { data } = await ventesApi.getConceptionLead(leadId)
        if (vivant) setRangee({ lead: leadId, donnees: data?.etat ? data : null })
      } catch {
        if (vivant) setRangee({ lead: leadId, donnees: null })  // 404 « conception_absente » : rien de rangé
      }
    }
    lire()
    return () => { vivant = false }
  }, [leadId])

  const servie = rangee.lead === leadId ? rangee.donnees : null
  const sansVersion = Boolean(leadId) && rangee.lead === leadId && !rangee.donnees
  const corpsEffectif = corps
    ?? (sansVersion ? { lead: Number(leadId), calepinage: null, entrees: {}, imposes: {} } : null)
  const cle = corpsEffectif ? JSON.stringify(corpsEffectif) : ''
  useEffect(() => {
    const ctrl = new AbortController()
    let minuterie = null
    const demander = async () => {
      try {
        const { data } = await ventesApi.apercuConception(JSON.parse(cle), { signal: ctrl.signal })
        if (!ctrl.signal.aborted) setApercu({ donnees: data?.etat ? data : null, chargement: false, erreur: null, cle })
      } catch (err) {
        if (ctrl.signal.aborted) return
        const detail = err?.response?.data?.detail
        setApercu({ donnees: null, chargement: false, cle, champ: err?.response?.data?.champ || null,
          erreur: typeof detail === 'string' ? detail : APERCU_INDISPONIBLE })
      }
    }
    const lancer = async () => {
      if (!cle) { setApercu({ donnees: null, chargement: false, erreur: null, cle: '' }); return }
      setApercu((a) => ({ ...a, chargement: true, erreur: null }))
      minuterie = setTimeout(demander, DELAI_APERCU_MS)
    }
    lancer()
    return () => { if (minuterie) clearTimeout(minuterie); ctrl.abort() }
  }, [cle, essai])

  const surRangee = !cle && Boolean(servie)
  // E7d (revue lot 4, M2) — une saisie dont l'aperçu a ÉCHOUÉ ne retombe jamais sur la
  // version rangée comme si elle était à jour : aucune conception, l'erreur est dite.
  const echec = Boolean(cle) && Boolean(apercu.erreur) && apercu.cle === cle
  return {
    conception: echec ? null : (apercu.donnees ?? servie), servie, chargement: apercu.chargement,
    erreur: apercu.erreur, champErreur: echec ? (apercu.champ || null) : null,
    reessayer: echec ? () => setEssai((n) => n + 1) : null,
    cleCourante: cle || (surRangee ? 'rangee' : null),
    cleServie: apercu.donnees ? apercu.cle : (surRangee ? 'rangee' : null),
    cleErreur: apercu.erreur ? apercu.cle : null,
  }
}
