import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'

import creditApi from '../../api/creditApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   WIR185/NTCRD3 — Réglages crédit de la société.
   ----------------------------------------------------------------------------
   `GET/PATCH /credit/reglage/` existait depuis NTCRD3 SANS AUCUN ÉCRAN : la
   politique de hold restait donc figée sur ses défauts (jamais bloquante), et
   la seule façon de la changer était l'admin Django. Tout le module crédit —
   les holds, les alertes, la tolérance de dépassement — dépend pourtant de ces
   huit champs.

   GARDE. La LECTURE est ouverte à tout authentifié ; l'ÉCRITURE est réservée
   Directeur / Administrateur (`IsDirecteurOrAdmin` côté serveur : superuser,
   palier admin, ou rôle fin Directeur/Administrateur). L'écran REFLÈTE cette
   règle — champs en lecture seule et explication FR pour les autres rôles —
   plutôt que de laisser partir un PATCH voué au 403. Un refus serveur reste
   affiché TEL QUEL : c'est lui qui fait autorité.

   DÉFAUT NON BLOQUANT PRÉSERVÉ : l'écran n'invente aucune valeur. Il rend ce
   que le serveur sert (`get_or_default`, instance non sauvegardée aux défauts
   tant que rien n'a été configuré) et n'enregistre que sur action explicite.
   ========================================================================== */

// source-choix: credit.LimiteCredit.ModeHold
const MODES_HOLD = [
  { value: 'aucun', label: 'Aucun — aucun blocage, aucune alerte' },
  { value: 'avertissement', label: 'Avertissement — signalé, jamais bloquant' },
  { value: 'blocage', label: 'Blocage — le dépassement arrête l’action' },
]

const ROLES_ECRITURE = ['Directeur', 'Administrateur']

// Les huit champs du réglage, dans l'ordre du formulaire.
const CHAMPS_NUMERIQUES = [
  ['seuil_alerte_pct', 'Seuil d’alerte (% de la limite)'],
  ['seuil_alerte_exposition_globale', 'Seuil d’alerte d’exposition globale (0 = désactivé)'],
  ['seuil_tolerance_depassement', 'Tolérance de dépassement (0 = désactivée)'],
]

const VIDE = {
  mode_hold_defaut: 'avertissement',
  inclure_bc_non_factures: true,
  inclure_devis_en_cours: false,
  seuil_alerte_pct: '80',
  seuil_alerte_exposition_globale: '0',
  devise_consolidation: 'MAD',
  seuil_tolerance_depassement: '0',
  roles_bypass_hold: [],
}

export default function ReglagesCreditPage() {
  const role = useSelector((s) => s.auth?.role)
  const roleNom = useSelector((s) => s.auth?.role_nom) || ''
  const peutEcrire = role === 'admin' || ROLES_ECRITURE.includes(roleNom)

  const [valeurs, setValeurs] = useState(VIDE)
  const [chargement, setChargement] = useState(true)
  const [erreur, setErreur] = useState('')
  const [succes, setSucces] = useState('')
  const [enregistrement, setEnregistrement] = useState(false)

  const setChamp = (cle, v) => {
    setValeurs((s) => ({ ...s, [cle]: v }))
    setSucces('')
  }

  useEffect(() => {
    let vivant = true
    creditApi.getReglage()
      .then((r) => {
        if (!vivant) return
        const d = r?.data || {}
        setValeurs({
          mode_hold_defaut: d.mode_hold_defaut ?? VIDE.mode_hold_defaut,
          inclure_bc_non_factures: !!d.inclure_bc_non_factures,
          inclure_devis_en_cours: !!d.inclure_devis_en_cours,
          seuil_alerte_pct: String(d.seuil_alerte_pct ?? VIDE.seuil_alerte_pct),
          seuil_alerte_exposition_globale: String(
            d.seuil_alerte_exposition_globale ?? VIDE.seuil_alerte_exposition_globale),
          devise_consolidation: d.devise_consolidation ?? VIDE.devise_consolidation,
          seuil_tolerance_depassement: String(
            d.seuil_tolerance_depassement ?? VIDE.seuil_tolerance_depassement),
          // Liste JSON côté serveur : on la rend en texte séparé par virgules.
          roles_bypass_hold: Array.isArray(d.roles_bypass_hold) ? d.roles_bypass_hold : [],
        })
      })
      .catch((err) => { if (vivant) setErreur(frenchError(err, 'Réglages illisibles.')) })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [])

  const enregistrer = async (e) => {
    e.preventDefault()
    setEnregistrement(true)
    setErreur('')
    setSucces('')
    try {
      const r = await creditApi.updateReglage({
        mode_hold_defaut: valeurs.mode_hold_defaut,
        inclure_bc_non_factures: valeurs.inclure_bc_non_factures,
        inclure_devis_en_cours: valeurs.inclure_devis_en_cours,
        seuil_alerte_pct: valeurs.seuil_alerte_pct,
        seuil_alerte_exposition_globale: valeurs.seuil_alerte_exposition_globale,
        devise_consolidation: valeurs.devise_consolidation,
        seuil_tolerance_depassement: valeurs.seuil_tolerance_depassement,
        roles_bypass_hold: valeurs.roles_bypass_hold,
      })
      // On repart de ce que le SERVEUR a réellement enregistré.
      if (r?.data?.mode_hold_defaut) {
        setChamp('mode_hold_defaut', r.data.mode_hold_defaut)
      }
      setSucces('Réglages enregistrés.')
    } catch (err) {
      setErreur(frenchError(err, "L'enregistrement a échoué."))
    } finally {
      setEnregistrement(false)
    }
  }

  if (chargement) {
    return (
      <div className="page">
        <h1>Réglages crédit</h1>
        <p>Chargement…</p>
      </div>
    )
  }

  return (
    <div className="page">
      <h1>Réglages crédit</h1>
      <p>
        Politique de crédit de la société : ce que le module considère comme
        engagé, quand il alerte, et ce qu’il fait d’un dépassement.
      </p>

      {!peutEcrire && (
        <p role="note" data-testid="credit-reglages-lecture-seule">
          Lecture seule — seuls le Directeur et l’Administrateur peuvent
          modifier les réglages crédit de la société.
        </p>
      )}

      {erreur && <p role="alert" data-testid="credit-reglages-erreur">{erreur}</p>}
      {succes && <p role="status" data-testid="credit-reglages-succes">{succes}</p>}

      <form onSubmit={enregistrer} noValidate>
        <fieldset disabled={!peutEcrire}>
          <legend>Hold</legend>
          <label htmlFor="rc-mode">Mode de hold par défaut</label>
          <select
            id="rc-mode"
            value={valeurs.mode_hold_defaut}
            onChange={(e) => setChamp('mode_hold_defaut', e.target.value)}
          >
            {MODES_HOLD.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>

          <label htmlFor="rc-bypass">
            Rôles autorisés à passer outre un blocage (séparés par des virgules)
          </label>
          <input
            id="rc-bypass"
            type="text"
            value={valeurs.roles_bypass_hold.join(', ')}
            onChange={(e) => setChamp(
              'roles_bypass_hold',
              e.target.value.split(',').map((x) => x.trim()).filter(Boolean),
            )}
          />
        </fieldset>

        <fieldset disabled={!peutEcrire}>
          <legend>Assiette de l’encours</legend>
          <label htmlFor="rc-bc">
            <input
              id="rc-bc"
              type="checkbox"
              checked={valeurs.inclure_bc_non_factures}
              onChange={(e) => setChamp('inclure_bc_non_factures', e.target.checked)}
            />
            Inclure les bons de commande non facturés
          </label>
          <label htmlFor="rc-devis">
            <input
              id="rc-devis"
              type="checkbox"
              checked={valeurs.inclure_devis_en_cours}
              onChange={(e) => setChamp('inclure_devis_en_cours', e.target.checked)}
            />
            Inclure les devis en cours
          </label>
        </fieldset>

        <fieldset disabled={!peutEcrire}>
          <legend>Seuils</legend>
          {CHAMPS_NUMERIQUES.map(([cle, libelle]) => (
            <div key={cle}>
              <label htmlFor={`rc-${cle}`}>{libelle}</label>
              <input
                id={`rc-${cle}`}
                type="number"
                step="any"
                min="0"
                value={valeurs[cle]}
                onChange={(e) => setChamp(cle, e.target.value)}
              />
            </div>
          ))}
          <label htmlFor="rc-devise">Devise de consolidation</label>
          <input
            id="rc-devise"
            type="text"
            maxLength={3}
            value={valeurs.devise_consolidation}
            onChange={(e) => setChamp('devise_consolidation', e.target.value.toUpperCase())}
          />
        </fieldset>

        {peutEcrire && (
          <button type="submit" disabled={enregistrement}>
            {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        )}
      </form>
    </div>
  )
}
