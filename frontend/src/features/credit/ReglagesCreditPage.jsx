import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'

import creditApi from '../../api/creditApi'
import { frenchError } from '../../lib/frenchError'
import { useHasPermission } from '../../hooks/useHasPermission'

/* ============================================================================
   WIR185/NTCRD3 — Réglages crédit de la société.

   Le singleton `ReglageCredit` pilote TOUT le comportement de hold (mode par
   défaut, ce qui compte dans l'encours, les seuils d'alerte, la tolérance de
   dépassement, les rôles qui passent outre) — mais aucun écran ne l'exposait :
   la politique restait figée sur les défauts du modèle, quelle que soit la
   société.

   Lecture ouverte à tout rôle qui atteint le module ; l'ÉCRITURE est réservée
   Directeur/Administrateur — le backend re-vérifie (`IsDirecteurOrAdmin`), la
   garde d'écran n'est qu'un raccourci qui évite d'offrir un bouton qui
   renverrait 403. Un 403 serveur reste affiché en français, jamais du JSON.
   ========================================================================== */

// source-choix: credit.LimiteCredit.ModeHold
const MODES_HOLD = [
  { value: 'aucun', label: 'Aucun — jamais de blocage' },
  { value: 'avertissement', label: 'Avertissement — on prévient, on laisse passer' },
  { value: 'blocage', label: 'Blocage — la vente est arrêtée' },
]

const VIDE = {
  mode_hold_defaut: 'avertissement',
  inclure_bc_non_factures: true,
  inclure_devis_en_cours: false,
  seuil_alerte_pct: '',
  seuil_alerte_exposition_globale: '',
  devise_consolidation: 'MAD',
  seuil_tolerance_depassement: '',
  roles_bypass_hold: [],
}

// `roles_bypass_hold` est un JSONField liste : l'écran l'édite en texte
// séparé par des virgules et le renvoie TOUJOURS en tableau.
const versTexte = (liste) => (Array.isArray(liste) ? liste.join(', ') : '')
const versListe = (texte) => texte.split(',').map(s => s.trim()).filter(Boolean)

export default function ReglagesCreditPage() {
  const [form, setForm] = useState(VIDE)
  const [rolesTexte, setRolesTexte] = useState('')
  const [chargement, setChargement] = useState(true)
  const [occupe, setOccupe] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [succes, setSucces] = useState(false)

  // Palier machine « admin » OU rôle fin Directeur/Administrateur : même
  // périmètre que `IsDirecteurOrAdmin` côté serveur.
  const rolePalier = useSelector((s) => s.auth.role)
  const roleFin = useHasPermission(null, ['Directeur', 'Administrateur'])
  const peutEcrire = rolePalier === 'admin' || roleFin

  useEffect(() => {
    let vivant = true
    creditApi.getReglage()
      .then((res) => {
        if (!vivant) return
        const d = res?.data ?? {}
        setForm({
          mode_hold_defaut: d.mode_hold_defaut ?? VIDE.mode_hold_defaut,
          inclure_bc_non_factures: !!d.inclure_bc_non_factures,
          inclure_devis_en_cours: !!d.inclure_devis_en_cours,
          seuil_alerte_pct: d.seuil_alerte_pct ?? '',
          seuil_alerte_exposition_globale: d.seuil_alerte_exposition_globale ?? '',
          devise_consolidation: d.devise_consolidation ?? 'MAD',
          seuil_tolerance_depassement: d.seuil_tolerance_depassement ?? '',
          roles_bypass_hold: Array.isArray(d.roles_bypass_hold) ? d.roles_bypass_hold : [],
        })
        setRolesTexte(versTexte(d.roles_bypass_hold))
      })
      .catch((err) => {
        if (vivant) setErreur(frenchError(err, 'Chargement des réglages impossible.'))
      })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [])

  const set = (champ, valeur) => {
    setForm(f => ({ ...f, [champ]: valeur }))
    setSucces(false)
  }

  async function enregistrer(event) {
    event.preventDefault()
    if (occupe || !peutEcrire) return
    setOccupe(true)
    setErreur(null)
    setSucces(false)
    try {
      const res = await creditApi.updateReglage({
        ...form,
        roles_bypass_hold: versListe(rolesTexte),
      })
      const d = res?.data ?? {}
      // On repart de la réponse serveur : c'est elle qui fait foi après
      // normalisation (décimales, liste de rôles).
      setForm(f => ({
        ...f,
        ...d,
        roles_bypass_hold: Array.isArray(d.roles_bypass_hold) ? d.roles_bypass_hold : [],
      }))
      setRolesTexte(versTexte(d.roles_bypass_hold))
      setSucces(true)
    } catch (err) {
      setErreur(frenchError(
        err, 'Enregistrement impossible (droits Directeur/Administrateur requis).'))
    } finally {
      setOccupe(false)
    }
  }

  if (chargement) {
    return (
      <div className="credit-reglages" data-testid="credit-reglages">
        <h3>Réglages crédit</h3>
        <p>Chargement…</p>
      </div>
    )
  }

  return (
    <div className="credit-reglages" data-testid="credit-reglages">
      <h3>Réglages crédit</h3>
      <p>
        Politique de crédit de la société : ce qui compte dans l'encours d'un
        client, à partir de quel seuil on l'alerte, et ce qui se passe quand sa
        limite est dépassée.
      </p>

      {erreur && <p className="credit-reglages__error" role="alert">{erreur}</p>}
      {succes && <p className="credit-reglages__ok" role="status">Réglages enregistrés.</p>}

      {!peutEcrire && (
        <p className="credit-reglages__readonly">
          Lecture seule : seuls le Directeur et l'Administrateur peuvent
          modifier la politique de crédit de la société.
        </p>
      )}

      <form onSubmit={enregistrer} noValidate>
        <fieldset disabled={!peutEcrire}>
          <div>
            <label htmlFor="rc-mode">Mode de hold par défaut</label>
            <select id="rc-mode" value={form.mode_hold_defaut}
                    onChange={(e) => set('mode_hold_defaut', e.target.value)}>
              {MODES_HOLD.map(m => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="rc-bc">
              <input id="rc-bc" type="checkbox"
                     checked={form.inclure_bc_non_factures}
                     onChange={(e) => set('inclure_bc_non_factures', e.target.checked)} />
              Compter les bons de commande non facturés dans l'encours
            </label>
          </div>

          <div>
            <label htmlFor="rc-devis">
              <input id="rc-devis" type="checkbox"
                     checked={form.inclure_devis_en_cours}
                     onChange={(e) => set('inclure_devis_en_cours', e.target.checked)} />
              Compter les devis en cours dans l'encours
            </label>
          </div>

          <div>
            <label htmlFor="rc-seuil-pct">Seuil d'alerte (% de la limite)</label>
            {/* step="any" : on ne snappe ni ne refuse un nombre saisi. */}
            <input id="rc-seuil-pct" type="number" step="any"
                   value={form.seuil_alerte_pct}
                   onChange={(e) => set('seuil_alerte_pct', e.target.value)} />
          </div>

          <div>
            <label htmlFor="rc-seuil-global">Seuil d'alerte sur l'exposition globale</label>
            <input id="rc-seuil-global" type="number" step="any"
                   value={form.seuil_alerte_exposition_globale}
                   onChange={(e) => set('seuil_alerte_exposition_globale', e.target.value)} />
          </div>

          <div>
            <label htmlFor="rc-devise">Devise de consolidation</label>
            <input id="rc-devise" type="text" maxLength={3}
                   value={form.devise_consolidation}
                   onChange={(e) => set('devise_consolidation', e.target.value)} />
          </div>

          <div>
            <label htmlFor="rc-tolerance">Tolérance de dépassement</label>
            <input id="rc-tolerance" type="number" step="any"
                   value={form.seuil_tolerance_depassement}
                   onChange={(e) => set('seuil_tolerance_depassement', e.target.value)} />
          </div>

          <div>
            <label htmlFor="rc-bypass">
              Rôles autorisés à passer outre le hold (séparés par des virgules)
            </label>
            <input id="rc-bypass" type="text" value={rolesTexte}
                   onChange={(e) => { setRolesTexte(e.target.value); setSucces(false) }} />
          </div>

          {peutEcrire && (
            <button type="submit" disabled={occupe}>
              {occupe ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          )}
        </fieldset>
      </form>
    </div>
  )
}
