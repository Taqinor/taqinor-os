import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Link as LienIcone } from 'lucide-react'

import { frenchError } from '../../../lib/frenchError'
import {
  accepterSuggestion, annulerGeste, classerErreur, listerSuggestions, refuserSuggestion } from '../../../api/tachesApi'
import { proposerAnnuler } from '../lib/gestes'
import { ETATS_LIEN, FAMILLES_SUGGESTIONS } from '../lib/textes'
import { Interrupteur } from '../reglages/Notifications'

/* ============================================================================
   TCH167 — Suggestions de l'ERP : « Suggéré par l'ERP » en tête d'À trier (Ajouter, Pas utile) et
   Réglages → « L'ERP me suggère » (les familles, « Toute la société » pour l'administrateur,
   « Afficher mes activités ERP dans Aujourd'hui »). Source : textes.md §2.5 et §2.14 ; contrat
   `suggestions.json`, `suggestion_refusee.json`, `tache_ecrite.json`.
   Une ligne : le titre proposé (modifiable avant d'ajouter) et « Lié à : {libellé} ». Ajouter et Pas utile
   font partir la ligne TOUT DE SUITE (mise à jour optimiste) ; elle revient à sa place si le serveur refuse
   ou si on annule ; jamais une relecture de la liste. Un lien que le compte ne peut plus lire (`etat` autre
   que `ok`) ne montre ni libellé ni adresse : seulement ce que dit `ETATS_LIEN`.
   ========================================================================== */

function LienSuggestion({ lien }) {
  if (!lien) return null
  const message = ETATS_LIEN[lien.etat]
  if (!message && !lien.libelle) return null
  return (
    <p className="fiche-lien">
      <LienIcone className="i i-16" aria-hidden="true" />
      {message ? <span>{message}</span> : null}
      {!message && lien.url ? <Link to={lien.url}>{`Lié à : ${lien.libelle}`}</Link> : null}
      {!message && !lien.url ? <span>{`Lié à : ${lien.libelle}`}</span> : null}
    </p>
  )
}

function LigneSuggestion({ suggestion, titre, erreur, onTitre, onAjouter, onRefuser }) {
  return (
    <div className="atrier-ligne" role="listitem" data-ligne={`suggestion:${suggestion.id}`}>
      <input
        type="text"
        className="champ-discret"
        aria-label={`Titre : ${suggestion.titre}`}
        aria-invalid={erreur ? true : undefined}
        maxLength={280}
        value={titre}
        onChange={(e) => onTitre(e.target.value)}
      />
      {erreur ? <p className="erreur-champ" role="alert">{erreur}</p> : null}
      <LienSuggestion lien={suggestion.lien} />
      <div className="puces">
        <button type="button" className="puce" onClick={() => onAjouter(suggestion)}>Ajouter</button>
        <button type="button" className="puce" onClick={() => onRefuser(suggestion)}>Pas utile</button>
      </div>
    </div>
  )
}

/** La section « Suggéré par l'ERP » d'À trier ; `onAjoutee(tache)` / `onRetiree(id)` tiennent la liste de l'écran à jour. */
export function SuggereParLErp({ onAjoutee, onRetiree }) {
  const [suggestions, setSuggestions] = useState([])
  const [titres, setTitres] = useState({})
  const [erreurs, setErreurs] = useState({})
  const [echec, setEchec] = useState('')

  useEffect(() => {
    let courant = true
    listerSuggestions()
      // liste fermée, plafonnée par le serveur (20 au plus, vue APIView sans pagination) : jamais de page suivante
      .then((r) => { if (courant) { const { results } = r.data; setSuggestions(results ?? []); setEchec('') } })
      .catch((err) => { if (courant) setEchec(frenchError(err)) })
    return () => { courant = false }
  }, [])

  const erreur = (id, message) => setErreurs((e) => ({ ...e, [id]: message }))

  /** La ligne part tout de suite ; la fonction rendue la remet à sa place. */
  const retirer = (suggestion) => {
    const rang = suggestions.findIndex((s) => s.id === suggestion.id)
    erreur(suggestion.id, '')
    setSuggestions((liste) => liste.filter((s) => s.id !== suggestion.id))
    return () => setSuggestions((liste) => {
      if (liste.some((s) => s.id === suggestion.id)) return liste
      const suite = [...liste]
      suite.splice(Math.max(rang, 0), 0, suggestion)
      return suite
    })
  }

  const ajouter = async (suggestion) => {
    const remettre = retirer(suggestion)
    const saisi = (titres[suggestion.id] ?? suggestion.titre).trim()
    try {
      const { data } = await accepterSuggestion(suggestion.id, saisi && saisi !== suggestion.titre ? { titre: saisi } : {})
      onAjoutee?.(data.tache)
      proposerAnnuler({
        message: 'Ajoutée',
        onAnnuler: data.geste_id ? async () => {
          await annulerGeste(data.geste_id)
          remettre()
          onRetiree?.(data.tache.id)
        } : undefined,
      })
    } catch (err) {
      remettre()
      erreur(suggestion.id, classerErreur(err).champs?.titre?.[0] || frenchError(err))
    }
  }

  const refuser = async (suggestion) => {
    const remettre = retirer(suggestion)
    try {
      const { data } = await refuserSuggestion(suggestion.id)
      proposerAnnuler({
        message: 'Pas utile',
        onAnnuler: data.geste_id ? async () => { await annulerGeste(data.geste_id); remettre() } : undefined,
      })
    } catch (err) {
      remettre()
      erreur(suggestion.id, frenchError(err))
    }
  }

  if (suggestions.length === 0 && !echec) return null
  return (
    <section className="section" aria-label="Suggéré par l'ERP">
      <h2 className="section-titre"><span>Suggéré par l'ERP</span></h2>
      {echec ? <p className="erreur-champ" role="alert">{echec}</p> : null}
      <div className="liste" role="list">
        {suggestions.map((suggestion) => (
          <LigneSuggestion
            key={suggestion.id}
            suggestion={suggestion}
            titre={titres[suggestion.id] ?? suggestion.titre}
            erreur={erreurs[suggestion.id]}
            onTitre={(valeur) => setTitres((t) => ({ ...t, [suggestion.id]: valeur }))}
            onAjouter={ajouter}
            onRefuser={refuser}
          />
        ))}
      </div>
    </section>
  )
}

function LigneReglage({ nom, allume, onBasculer, erreur }) {
  return (
    <>
      <div className="es-reglage">
        <span className="txt"><b>{nom}</b></span>
        <Interrupteur nom={nom} allume={allume} onBasculer={onBasculer} />
      </div>
      {erreur ? <p className="es-erreur" role="alert">{erreur}</p> : null}
    </>
  )
}

/** Réglages → « L'ERP me suggère » : chaque interrupteur écrit `PATCH reglages/` (via `onReglage`) et l'erreur
 *  du serveur s'affiche sous le réglage. */
export function ReglageSuggestions({ reglages, onReglage, erreur }) {
  if (!reglages) return null
  const allumees = reglages.familles_suggestions ?? []
  const basculerFamille = (cle) => onReglage(
    'familles_suggestions',
    allumees.includes(cle) ? allumees.filter((f) => f !== cle) : [...allumees, cle],
  )
  return (
    <div className="es-reglages">
      {FAMILLES_SUGGESTIONS.map(([cle, libelle]) => (
        <LigneReglage key={cle} nom={libelle} allume={allumees.includes(cle)} onBasculer={() => basculerFamille(cle)}
          erreur={erreur.familles_suggestions} />
      ))}
      {reglages.est_admin ? (
        <LigneReglage nom="Toute la société (administrateur)" allume={Boolean(reglages.suggestions_societe)}
          onBasculer={() => onReglage('suggestions_societe', !reglages.suggestions_societe)} erreur={erreur.suggestions_societe} />
      ) : null}
      <LigneReglage nom="Afficher mes activités ERP dans Aujourd'hui" allume={Boolean(reglages.erp_dans_journee)}
        onBasculer={() => onReglage('erp_dans_journee', !reglages.erp_dans_journee)} erreur={erreur.erp_dans_journee} />
    </div>
  )
}
