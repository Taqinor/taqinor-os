import { useEffect, useState } from 'react'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT31 — Réglages tenant « Marketing » (Paramètres → Marketing).
   ----------------------------------------------------------------------------
   Expéditeur par défaut (nom/email/domaine, XMKT33), fenêtre silencieuse
   additive (au-delà du calendrier ouvré `notifications.WorkingHoursConfig`
   déjà appliqué côté serveur), plafond d'envois/jour anti-spam
   (`plafond_envois_atteint` côté backend — 0/vide = désactivé, comportement
   actuel), langue par défaut des templates (XMKT11).

   DÉROGATION DE PLACEMENT : le fichier vit sous `features/marketing/`
   (jamais `features/parametres/`, hors du périmètre d'écriture de cette
   session CRM_VENTES sur cette lane — une autre app possède ce dossier) ;
   accessible depuis le sous-menu Marketing → « Paramètres marketing »,
   comme le fait déjà `SupportsOffline.jsx` (NTMKT10) pour son propre écran
   lié depuis Paramètres.
   ========================================================================== */

const LANGUES = [
  { key: 'fr', label: 'Français' },
  { key: 'ar', label: 'Arabe' },
  { key: 'darija', label: 'Darija' },
]

export default function MarketingParametres() {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const [ok, setOk] = useState(false)

  useEffect(() => {
    marketingApi.parametres.get()
      .then(r => setForm(r.data))
      .catch(() => setErr('Chargement des réglages impossible.'))
  }, [])

  const champ = (key) => (e) => {
    setOk(false)
    setForm(f => ({ ...f, [key]: e.target.value }))
  }

  const champNombre = (key) => (e) => {
    setOk(false)
    const v = e.target.value
    setForm(f => ({ ...f, [key]: v === '' ? null : Number(v) }))
  }

  const enregistrer = async () => {
    setSaving(true)
    setErr('')
    setOk(false)
    try {
      const r = await marketingApi.parametres.maj(form)
      setForm(r.data)
      setOk(true)
    } catch {
      setErr('Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  if (!form) {
    return (
      <div className="page">
        <p className="page-loading">{err || 'Chargement…'}</p>
      </div>
    )
  }

  return (
    <div className="page" data-testid="marketing-parametres">
      <div className="page-header"><h2>Paramètres marketing</h2></div>
      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {ok && <p style={{ color: '#16a34a' }}>Réglages enregistrés.</p>}

      <section style={{ marginBottom: '1rem' }}>
        <h3>Expéditeur par défaut</h3>
        <input className="form-input" data-testid="parametres-expediteur-nom"
          placeholder="Nom" value={form.expediteur_nom || ''} onChange={champ('expediteur_nom')} />
        <input className="form-input" data-testid="parametres-expediteur-email"
          placeholder="Email" value={form.expediteur_email || ''} onChange={champ('expediteur_email')} />
        <input className="form-input" data-testid="parametres-expediteur-domaine"
          placeholder="Domaine d'envoi" value={form.expediteur_domaine || ''}
          onChange={champ('expediteur_domaine')} />
      </section>

      <section style={{ marginBottom: '1rem' }}>
        <h3>Fenêtre silencieuse (additive)</h3>
        <input className="form-input" type="number" data-testid="parametres-silence-debut"
          placeholder="Aucun envoi avant (heure)" value={form.silence_heure_debut ?? ''}
          onChange={champNombre('silence_heure_debut')} />
        <input className="form-input" type="number" data-testid="parametres-silence-fin"
          placeholder="Aucun envoi après (heure)" value={form.silence_heure_fin ?? ''}
          onChange={champNombre('silence_heure_fin')} />
      </section>

      <section style={{ marginBottom: '1rem' }}>
        <h3>Plafond d&apos;envois par jour (anti-spam)</h3>
        <input className="form-input" type="number" data-testid="parametres-plafond"
          placeholder="0 = désactivé" value={form.plafond_envois_jour ?? ''}
          onChange={champNombre('plafond_envois_jour')} />
      </section>

      <section style={{ marginBottom: '1rem' }}>
        <h3>Langue par défaut des templates</h3>
        <select className="form-input" data-testid="parametres-langue"
          value={form.langue_defaut_templates || 'fr'} onChange={champ('langue_defaut_templates')}>
          {LANGUES.map(l => <option key={l.key} value={l.key}>{l.label}</option>)}
        </select>
      </section>

      <ConformiteCndp />

      <button className="btn btn-primary" data-testid="parametres-enregistrer"
        disabled={saving} onClick={enregistrer}>
        {saving ? 'Enregistrement…' : 'Enregistrer'}
      </button>
    </div>
  )
}

/* AUDV17 — état de conformité loi 09-08 / CNDP.

   Le toggle double opt-in, le pied de déclaration CNDP et la mention STOP
   existaient tous côté services SANS AUCUNE surface : personne, dans l'ERP,
   ne pouvait dire si les campagnes partaient conformes. Lecture seule : cet
   écran DIT l'état, il ne règle rien (le numéro de déclaration se saisit dans
   le profil société). Un pied non configuré est signalé EXPLICITEMENT — c'est
   le cas dangereux, celui où les emails partent sans mention légale. */
export function ConformiteCndp() {
  const [etat, setEtat] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    let vivant = true
    marketingApi.campagnes.conformiteCndp()
      .then((r) => { if (vivant) setEtat(r.data) })
      .catch(() => { if (vivant) setErr('État de conformité indisponible.') })
    return () => { vivant = false }
  }, [])

  return (
    <section style={{ marginBottom: '1rem' }} data-testid="conformite-cndp">
      <h3>Conformité CNDP (loi 09-08)</h3>
      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {etat && (
        <ul>
          <li data-testid="cndp-double-optin">
            Double opt-in : {etat.double_optin_actif ? 'activé' : 'désactivé'}
          </li>
          <li data-testid="cndp-pied">
            {etat.pied_cndp_configure
              ? `Pied des emails : ${etat.pied_cndp}`
              : 'Aucun numéro de déclaration CNDP : les emails partent sans '
                + 'mention légale.'}
          </li>
          <li data-testid="cndp-stop">
            Mention SMS ajoutée automatiquement : «{etat.mention_stop_sms} »
          </li>
        </ul>
      )}
    </section>
  )
}
