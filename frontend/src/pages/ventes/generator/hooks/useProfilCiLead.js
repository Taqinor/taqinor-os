// ADEV100 — le générateur C&I s'ouvre PRÉ-REMPLI depuis la fiche lead (rejeu
// « humain » R1-07). Ce hook tient les champs SEMÉS (badge « repris du lead »),
// sème à l'arrivée du lead (création seulement : l'appelant ne l'invoque pas en
// `?edit=`) et enveloppe les gestes de saisie du profil C&I — une modification
// de la commerciale retire le badge du champ et n'est jamais écrasée.
import { useEffect, useRef, useState } from 'react'
import { LEAD_TYPE_TO_MODE } from '../../../../features/ventes/autoQuote'
import crmApi from '../../../../api/crmApi'
import {
  poserProfilCi, semisCiDepuisLead, cleReprisDuChamp,
} from '../../../../features/ventes/quote/profilCi'

export function useProfilCiLead({
  profilCi, setProfilCi, categorieCommerciale, setCategorieCommerciale,
  commercialAnswers, setCommercialAnswers, tarifSaisie, setTarifSaisie,
}) {
  const [reprisLead, setReprisLead] = useState([])
  const retirerRepris = (cle) => setReprisLead((r) => {
    const reste = r.filter((c) => c !== cle && !(cle === 'categorie' && c.startsWith('reponses.')))
    return reste.length === r.length ? r : reste
  })
  // Ce que l'écran porte AU MOMENT où la réponse du lead arrive (asynchrone).
  const etatCiCourant = useRef({})
  useEffect(() => {
    etatCiCourant.current = {
      profil: profilCi, categorie: categorieCommerciale,
      reponses: commercialAnswers, tarif: tarifSaisie,
    }
  })

  const semer = (detail) => {
    const semis = semisCiDepuisLead(detail, etatCiCourant.current)
    if (!semis) return
    if (semis.profil.length) {
      setProfilCi((p) => semis.profil.reduce((acc, [chemin, valeur]) => poserProfilCi(acc, chemin, valeur), p))
    }
    if (semis.categorie) setCategorieCommerciale(semis.categorie)
    if (semis.reponses) setCommercialAnswers((prev) => ({ ...semis.reponses, ...prev }))
    if (semis.tarif) setTarifSaisie((t) => ({ ...t, ...semis.tarif }))
    setReprisLead((r) => [...new Set([...r, ...semis.marques])])
  }

  // Le DÉTAIL du lead porte les champs pro : la liste paginée n'en a pas, on le
  // relit alors (une panne reste silencieuse : le serveur résout le lead).
  const appliquerProfilCiDuLead = (lead) => {
    const mode = LEAD_TYPE_TO_MODE[lead?.type_installation]
    if (mode !== 'commercial' && mode !== 'industriel') return
    if ('contrat_electricite' in lead || 'categorie_commerciale' in lead) {
      semer(lead)
      return
    }
    Promise.resolve().then(() => crmApi.getLead(lead.id))
      .then((rep) => rep?.data)
      .catch(() => null)
      .then((detail) => { if (detail) semer(detail) })
  }

  return {
    reprisLead,
    appliquerProfilCiDuLead,
    setChampCi: (chemin, valeur) => {
      retirerRepris(cleReprisDuChamp(chemin))
      setProfilCi((p) => poserProfilCi(p, chemin, valeur))
    },
    setTarifChamp: (champ, valeur) => {
      if (champ === 'contrat') retirerRepris('contrat')
      setTarifSaisie((t) => ({ ...t, [champ]: valeur }))
    },
    setCommercialAnswer: (cle, valeur) => {
      retirerRepris(`reponses.${cle}`)
      setCommercialAnswers((prev) => ({ ...prev, [cle]: valeur }))
    },
    choisirCategorieCommerciale: (valeur) => {
      retirerRepris('categorie')
      setCategorieCommerciale(valeur)
    },
  }
}
