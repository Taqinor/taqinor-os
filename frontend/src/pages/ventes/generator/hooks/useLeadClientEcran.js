// SPL50 — LE LIEN LEAD / CLIENT DU DEVIS, déplacé tel quel de
// DevisGenerator.jsx : `applyLead`, `applySiteProfile`, `applyClient`,
// `sitePrefillDone` + l'effet `?client=`, `runAutoQuote`. Corps verbatim ;
// `ctx` porte, nom par nom, ce que le corps lit du composant. L'effet
// d'arrivée du lead reste dans la coquille (après le chargeur `?edit=`).
import { LEAD_TYPE_TO_MODE, createAutoQuote } from '../../../../features/ventes/autoQuote'
import crmApi from '../../../../api/crmApi'
import { estimerMois } from '../../../../features/ventes/solar'
import ventesApi from '../../../../api/ventesApi'
import { useEffect, useRef } from 'react'

export function useLeadClientEcran(ctx) {
  const {
    leads, structuresCatalogue, setSaving, setErrors, dispatchSizing, finish, leadId,
    setLeadId, clientId, setClientId, setFHiver, setFEte, setMonthly,
    setConsoMensuelle, setHorsReseau, horsReseauTouched, setPompeCv, setPompeHmt, setPompeDebit,
    appliquerEntreesPompage,
    facturesProtegeesRef, reinitialiserFactures, setAvisFactures, consoMensuelle,
    pompeCv, pompeHmt, pompeDebit, baremeSociete,
  } = ctx
  const vide = (v) => v == null || String(v).trim() === ''

  // AGNR19 — `leadLu` : le lead déjà relu par son id (arrivée `?lead=`,
  // prop `leadId`) ; à défaut, la liste chargée (sélecteur).
  const applyLead = (id, leadLu = null) => {
    setLeadId(id)
    if (!id) return
    setClientId('') // le client est résolu côté serveur depuis le lead
    const lead = leadLu || leads.find(l => String(l.id) === String(id))
    if (!lead) return
    // QJR99 — les SEPT écritures gardées (mode, scénario, structure, tension,
    // alimentation pompe, taille souhaitée, dimensionnement par facture) sont
    // devenues UNE transition `LEAD_APPLIQUE`. Chaque garde-fou « intact » y
    // est écrit une fois, testé, et le bug QJR38 (« brancher sur le mode du
    // rendu PRÉCÉDENT ») ne peut plus revenir : le mode visé EST dans l'état
    // que la transition produit.
    //
    // Ce qui reste ICI est tout ce que le reducer ne modélise PAS : le type
    // d'installation (autoconsommation par défaut), les champs pompe, la
    // consommation, les factures affichées, et la RÉSOLUTION du balayage local
    // — un reducer pur ne va jamais chercher un chiffre au catalogue.
    // Lead agricole : les ENTRÉES de pompage déclarées ou mesurées
    // (`entrees_pompage`, AGR404) — l'alimentation, elle, suit le
    // raccordement DANS la transition ci-dessous. Rien n'est inventé.
    if (LEAD_TYPE_TO_MODE[lead.type_installation] === 'agricole') {
      // La liste des leads ne porte pas `entrees_pompage` (détail seulement) :
      // on relit le lead ; une panne reste silencieuse (états laissés vides).
      Promise.resolve().then(() => crmApi.getLead(lead.id))
        .then((rep) => appliquerEntreesPompage(rep?.data))
        .catch(() => { /* lead illisible : aucune entrée reprise */ })
    }
    // AGNR17 — un changement de lead repart d'un état VIDE : la conso et les
    // factures d'un lead précédent ne survivent jamais au lead suivant (sauf
    // une saisie du vendeur, protégée).
    if (lead.conso_mensuelle_kwh) setConsoMensuelle(String(lead.conso_mensuelle_kwh))
    else if (!facturesProtegeesRef.current) setConsoMensuelle('')
    const hiver = parseFloat(lead.facture_hiver) || 0
    // bascule OFF → la valeur unique vaut hiver ET été
    const ete = (lead.ete_differente && lead.facture_ete)
      ? parseFloat(lead.facture_ete) : hiver
    // CIQ126 — plus aucun balayage local : le résidentiel attend le moteur
    // horaire, le C&I le moteur C&I serveur, l'agricole son kit serveur.
    const sizingLocal = null
    // STKCAT10 — la liste des structures RÉELLEMENT sélectionnables voyage
    // avec l'action : le reducer valide contre ELLE l'id épinglé sur le lead
    // (`lead.structure_produit`, STKCAT9) et n'applique jamais un produit
    // archivé, dépricé, détypé ou d'une autre société. Un module pur ne va
    // chercher aucun catalogue lui-même — c'est l'appelant qui l'apporte.
    dispatchSizing({
      type: 'LEAD_APPLIQUE',
      lead,
      sizingLocal,
      structuresEligibles: structuresCatalogue.map((p) => p.id),
    })
    // OFFGRID — défaut dérivé du raccordement du lead : « aucun » (site
    // isolé) bascule le devis en hors réseau tant que le vendeur n'a pas
    // choisi lui-même (même garde « touché » que pompeAlim/structure/tension
    // ci-dessus dans le reducer — ici en état simple, voir sa déclaration).
    if (!horsReseauTouched) setHorsReseau(lead.raccordement === 'aucun')
    if (facturesProtegeesRef.current) {
      if (hiver > 0) setAvisFactures('Factures du lead non appliquées : des factures sont déjà saisies.')
    } else if (hiver > 0) {
      setFHiver(String(lead.facture_hiver))
      setFEte(lead.ete_differente && lead.facture_ete ? String(lead.facture_ete) : '')
      setMonthly(estimerMois(hiver, ete))
    } else {
      reinitialiserFactures()
    }
  }

  // ── WIR99/DC12 — Pré-remplissage d'un devis SANS LEAD depuis le profil
  // site/énergie réutilisable du client (`crm.SiteProfile`, résolu côté
  // serveur par `/ventes/devis/prefill-site/`). Miroir EXACT d'`applyLead` :
  // mêmes champs, mêmes garde-fous « touched » — un champ que l'utilisateur a
  // déjà réglé n'est JAMAIS écrasé. Aucun profil (ou aucun client) → no-op
  // strict : le comportement historique est inchangé.
  const applySiteProfile = (p) => {
    if (!p) return
    // QJR99 — miroir d'`applyLead` : une SEULE transition
    // (`PROFIL_SITE_APPLIQUE`) porte le mode, l'alimentation pompe et le
    // dimensionnement par facture. QJR38 — le mode RÉELLEMENT visé est calculé
    // ici comme dans le reducer (et non lu sur le rendu précédent) : c'est ce
    // bug-là qui faisait armer au résidentiel une attente que le moteur
    // résidentiel-only ne satisferait jamais pour un profil industriel.
    if (LEAD_TYPE_TO_MODE[p.type_installation] === 'agricole') {
      // AGR420 — la pompe du profil est la pompe ACTUELLE (information).
      // AGNR17 — un pré-remplissage n'écrase jamais une valeur déjà saisie.
      if (p.pompe_actuelle_cv != null && p.pompe_actuelle_cv !== '' && vide(pompeCv)) setPompeCv(String(p.pompe_actuelle_cv))
      if (p.pompe_hmt_m != null && p.pompe_hmt_m !== '' && vide(pompeHmt)) setPompeHmt(String(p.pompe_hmt_m))
      if (p.pompe_debit_m3h != null && p.pompe_debit_m3h !== '' && vide(pompeDebit)) setPompeDebit(String(p.pompe_debit_m3h))
    }
    if (p.conso_mensuelle_kwh && vide(consoMensuelle)) setConsoMensuelle(String(p.conso_mensuelle_kwh))
    const hiver = parseFloat(p.facture_hiver) || 0
    const ete = (p.ete_differente && p.facture_ete) ? parseFloat(p.facture_ete) : hiver
    // CIQ126 — plus aucun balayage local (voir applyLead) : le résidentiel
    // attend le moteur horaire SERVEUR (U3-900), le C&I le moteur C&I serveur.
    const sizingLocal = null
    dispatchSizing({ type: 'PROFIL_SITE_APPLIQUE', profil: p, sizingLocal })
    if (hiver > 0 && facturesProtegeesRef.current) {
      // AGNR17 — des factures déjà saisies gagnent : le profil ne les écrase pas.
      setAvisFactures('Profil de site non appliqué aux factures déjà saisies.')
    } else if (hiver > 0) {
      setFHiver(String(p.facture_hiver))
      setFEte(p.ete_differente && p.facture_ete ? String(p.facture_ete) : '')
      setMonthly(estimerMois(hiver, ete))
    }
  }

  // Sélection d'un client (chemin SANS lead) : pose l'id puis va chercher son
  // profil site. Best-effort — une absence de profil ou une erreur réseau ne
  // doit jamais empêcher de sélectionner le client.
  const applyClient = (v) => {
    const id = v ? String(v) : ''
    setClientId(id)
    if (!id || leadId) return
    ventesApi.getPrefillSite(id)
      .then((res) => applySiteProfile(res?.data?.profil))
      .catch(() => {})
  }

  // Client pré-sélectionné par ?client=<id> : même pré-remplissage, une seule
  // fois au montage (jamais rejoué ensuite).
  const sitePrefillDone = useRef(false)
  useEffect(() => {
    if (sitePrefillDone.current || !clientId || leadId) return
    sitePrefillDone.current = true
    ventesApi.getPrefillSite(clientId)
      .then((res) => applySiteProfile(res?.data?.profil))
      .catch(() => {})
    // Pré-remplissage au montage uniquement (garde `sitePrefillDone`) ;
    // rejouer à chaque changement d'état écraserait la saisie en cours.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- montage seul
  }, [clientId, leadId])

  // ── Devis automatique (bouton « ⚡ Devis auto » du lead) ──
  // Sensible au marché du lead : résidentiel (comportement historique),
  // agricole (pompage, mêmes appels que le flux manuel) ou industriel
  // (dimensionnement factures + étude d'autoconsommation comme en manuel).
  // On lit le lead DIRECTEMENT (l'état posé par applyLead est asynchrone).
  const runAutoQuote = async (lead, discountStr) => {
    setSaving(true)
    // QJR602 suivi (D-QJR5-13) — une taille explicite est respectée telle
    // quelle : plus d'arrondi au palier de 5 kWc, donc plus d'avis de palier.
    try {
      // Chemin partagé avec le panneau devis inline (autoQuote.js). CIQ127 —
      // les quatre marchés sont créés par le SERVEUR, qui lit lui-même le
      // catalogue, les marques épinglées (PVMRQ) et l'ordre des lignes de la
      // société (PVORD) : rien de cela ne part d'ici.
      const devisId = await createAutoQuote({ lead, discountStr, bareme: baremeSociete })
      finish(devisId)
    } catch (err) {
      const msg = typeof err?.detail === 'string'
        ? err.detail
        : 'Le devis automatique a échoué — vérifiez le lead et réessayez.'
      setErrors(prev => ({ ...prev, submit: msg }))
      setSaving(false)
    }
  }

  return {
    applyLead, applyClient, runAutoQuote,
  }
}
