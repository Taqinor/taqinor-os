/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState } from 'react'
import marketingApi from '../../api/marketingApi'
import HeatmapEnvoi from './HeatmapEnvoi'

/* ============================================================================
   NTMKT2/NTMKT3 — Formulaire de création/édition d'une campagne.
   ----------------------------------------------------------------------------
   Objet/corps par canal email/sms/whatsapp, listes de diffusion ciblées
   (XMKT5, `marketing/listes-diffusion/`), variantes de langue (XMKT11,
   `variantes_langue` JSON — vide par défaut = comportement actuel FR
   uniquement), aperçu de variables de fusion (XMKT8, `apercu_fusion` avec
   `?lead_id=`) et — NTMKT3 — configuration du test A/B (XMKT14, `ab_test`
   JSON : variante B, % d'échantillon, fenêtre de décision, critère). Rien
   n'est envoyé depuis ce composant : la sauvegarde crée/met à jour la
   `Campagne` en `brouillon` (comportement backend inchangé).
   ========================================================================== */

const CANAUX = [
  { key: 'email', label: 'Email' },
  { key: 'sms', label: 'SMS' },
  { key: 'whatsapp', label: 'WhatsApp' },
]

const LANGUES_VARIANTES = [
  { key: 'ar', label: 'Arabe' },
  { key: 'darija', label: 'Darija' },
]

// XMKT14 — critères de décision du gagnant A/B (backend `ab_test.critere`).
const AB_CRITERES = [
  { key: 'ouvertures', label: 'Ouvertures' },
  { key: 'clics', label: 'Clics' },
]

export function emptyForm() {
  return {
    nom: '', canal: 'email', objet: '', corps: '', planifiee_le: '',
    listes: [], variantes_langue: {}, ab_test: {},
  }
}

// Construit le form à partir d'une campagne existante (édition).
export function formFromCampagne(c) {
  return {
    nom: c.nom || '', canal: c.canal || 'email', objet: c.objet || '',
    corps: c.corps || '',
    planifiee_le: c.planifiee_le ? c.planifiee_le.slice(0, 16) : '',
    listes: (c.listes || []).map(l => (typeof l === 'object' ? l.id : l)),
    variantes_langue: c.variantes_langue || {},
    ab_test: c.ab_test || {},
  }
}

export default function CampagneForm({ initial, onSave, onCancel, editing }) {
  const [form, setForm] = useState(initial || emptyForm())
  const [listesDispo, setListesDispo] = useState([])
  // NTMKT23 — blocs de contenu réutilisables + bloc sélectionné.
  const [blocs, setBlocs] = useState([])
  const [blocChoisi, setBlocChoisi] = useState('')
  const [err, setErr] = useState('')
  const [saving, setSaving] = useState(false)
  // XMKT8 — aperçu de fusion (jamais sauvegardé, lecture seule).
  const [leadIdApercu, setLeadIdApercu] = useState('')
  const [corpsApercu, setCorpsApercu] = useState('')
  const [apercuLoading, setApercuLoading] = useState(false)
  const [apercuErr, setApercuErr] = useState('')
  // ── WIR258/XMKT34 — Assistant IA (repris de CampagnesScreen, l'unique hôte
  //    de la fonctionnalité, qui n'était routé nulle part). `iaDisponible`
  //    reste FALSE tant que la sonde n'a pas confirmé une clé LLM : sans clé,
  //    aucune trace de la fonctionnalité dans l'UI.
  const [iaDisponible, setIaDisponible] = useState(false)
  const [iaOptions, setIaOptions] = useState(
    { segment_label: '', offre: '', instruction: '', langue: 'fr' })
  const [iaLoading, setIaLoading] = useState(false)
  const [iaErr, setIaErr] = useState('')

  useEffect(() => {
    let vivant = true
    // Sonde de GATING : aucun appel LLM n'est fait ici.
    marketingApi.campagnes.genererIaDisponible()
      .then(r => { if (vivant) setIaDisponible(!!r.data?.configured) })
      .catch(() => { if (vivant) setIaDisponible(false) })
    return () => { vivant = false }
  }, [])

  const genererIa = async () => {
    setIaLoading(true)
    setIaErr('')
    try {
      const r = await marketingApi.campagnes.genererIa(iaOptions)
      if (r.data?.ok) {
        // SUGGESTION éditable : remplit objet/corps, ne sauvegarde rien.
        setForm(f => ({
          ...f,
          objet: r.data.objet || f.objet,
          corps: r.data.corps || f.corps,
        }))
      } else {
        setIaErr('Génération indisponible.')
      }
    } catch {
      setIaErr('Génération impossible.')
    } finally {
      setIaLoading(false)
    }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- resync le formulaire quand la prop initial change
  useEffect(() => { setForm(initial || emptyForm()) }, [initial])

  useEffect(() => {
    marketingApi.listes.list()
      .then(r => setListesDispo(marketingApi.unwrapList(r)))
      .catch(() => setListesDispo([]))
  }, [])

  // NTMKT23 — bibliothèque de blocs de contenu réutilisables.
  useEffect(() => {
    marketingApi.blocsContenu.list({ actif: true })
      .then(r => setBlocs(marketingApi.unwrapList(r)))
      .catch(() => setBlocs([]))
  }, [])

  const insererBloc = () => {
    const bloc = blocs.find(b => String(b.id) === String(blocChoisi))
    if (!bloc) return
    // COPIE du fragment (snapshot) : aucune référence vivante au bloc source.
    setForm(f => ({
      ...f,
      corps: f.corps ? `${f.corps}\n${bloc.contenu || ''}` : (bloc.contenu || ''),
    }))
  }

  const setField = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const toggleListe = (id) => setForm(f => {
    const has = f.listes.includes(id)
    return { ...f, listes: has ? f.listes.filter(x => x !== id) : [...f.listes, id] }
  })

  const setVarianteLangue = (langue, champ) => (e) => setForm(f => ({
    ...f,
    variantes_langue: {
      ...f.variantes_langue,
      [langue]: { ...(f.variantes_langue[langue] || {}), [champ]: e.target.value },
    },
  }))

  // ── NTMKT3 — configuration du test A/B (XMKT14) ──
  // Actif = présence d'une config A/B (jamais la troncature des valeurs : les
  // champs objet_b/corps_b sont seedés VIDES à l'activation → tester leur
  // vérité laisserait abActif=false juste après avoir activé le test).
  const abActif = Object.keys(form.ab_test || {}).length > 0
  const setAbField = (champ) => (e) => setForm(f => ({
    ...f, ab_test: { ...f.ab_test, [champ]: e.target.value },
  }))
  const toggleAb = () => setForm(f => ({
    ...f,
    ab_test: Object.keys(f.ab_test || {}).length > 0
      ? {}
      : {
        objet_b: '', corps_b: '', pct_echantillon: 20, fenetre_heures: 4,
        critere: 'ouvertures',
      },
  }))

  const apercuFusion = async () => {
    if (!leadIdApercu) return
    setApercuLoading(true)
    setApercuErr('')
    try {
      const r = await marketingApi.campagnes.apercuFusion(
        initial?.id, { lead_id: leadIdApercu })
      setCorpsApercu(r.data?.corps_fusionne || '')
    } catch {
      setApercuErr('Aperçu impossible (lead introuvable ou champ invalide).')
    } finally {
      setApercuLoading(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setErr('')
    setSaving(true)
    const payload = {
      ...form,
      planifiee_le: form.planifiee_le
        ? new Date(form.planifiee_le).toISOString() : null,
      ab_test: abActif ? form.ab_test : {},
    }
    try {
      await onSave(payload)
    } catch {
      setErr('Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="campagne-form"
      style={{ display: 'grid', gap: '0.6rem', maxWidth: 760 }}>
      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
        <input className="form-input" data-testid="campagne-nom"
          placeholder="Nom de la campagne" required
          value={form.nom} onChange={setField('nom')}
          style={{ flex: '2 1 220px' }} />
        <select className="form-input" data-testid="campagne-canal"
          value={form.canal} onChange={setField('canal')}
          style={{ flex: '1 1 140px' }}>
          {CANAUX.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
        </select>
        <input type="datetime-local" className="form-input"
          data-testid="campagne-planifiee-le" value={form.planifiee_le}
          onChange={setField('planifiee_le')} style={{ flex: '1 1 200px' }} />
      </div>
      {/* NTMKT24 — suggestion informative de moment d'envoi (ne bloque rien) */}
      <HeatmapEnvoi />
      <input className="form-input" data-testid="campagne-objet"
        placeholder="Objet (email)" value={form.objet}
        onChange={setField('objet')} />
      <textarea className="form-input" data-testid="campagne-corps"
        placeholder="Corps du message ({{prenom}}, {{ville}}…)" rows={5}
        value={form.corps} onChange={setField('corps')} />

      {/* WIR258/XMKT34 — Assistant IA. Le bloc vivait dans CampagnesScreen,
          l'unique hôte de la fonctionnalité… qui n'était routé nulle part :
          la génération IA était donc inatteignable. Il est ici, dans le
          formulaire réellement monté.
          GATING : la sonde `generer-ia-disponible` ne fait AUCUN appel LLM ;
          sans clé configurée, rien n'est rendu — pas même un bouton grisé. */}
      {iaDisponible && (
        <fieldset
          data-testid="campagne-ia"
          style={{ border: '1px dashed #cbd5e1', borderRadius: 8,
            padding: '0.6rem', display: 'grid', gap: '0.5rem' }}>
          <legend style={{ fontSize: '0.8rem', color: '#475569', padding: '0 6px' }}>
            Assistant IA (suggestion éditable — jamais envoyée seule)
          </legend>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input className="form-input" data-testid="campagne-ia-segment"
              placeholder="Segment ciblé (ex. leads froids résidentiel)"
              value={iaOptions.segment_label}
              onChange={e => setIaOptions(o => ({ ...o, segment_label: e.target.value }))}
              style={{ flex: '1 1 220px' }} />
            <input className="form-input" data-testid="campagne-ia-offre"
              placeholder="Offre / contexte (ex. -20% panneaux)"
              value={iaOptions.offre}
              onChange={e => setIaOptions(o => ({ ...o, offre: e.target.value }))}
              style={{ flex: '1 1 220px' }} />
            <select className="form-input" data-testid="campagne-ia-langue"
              value={iaOptions.langue}
              onChange={e => setIaOptions(o => ({ ...o, langue: e.target.value }))}
              style={{ flex: '0 1 120px' }}>
              <option value="fr">Français</option>
              <option value="ar">Arabe</option>
            </select>
          </div>
          <input className="form-input" data-testid="campagne-ia-instruction"
            placeholder="Consigne (ton, longueur, réécriture…)"
            value={iaOptions.instruction}
            onChange={e => setIaOptions(o => ({ ...o, instruction: e.target.value }))} />
          <div>
            <button type="button" className="btn btn-light"
              data-testid="campagne-ia-generer"
              disabled={iaLoading} onClick={genererIa}>
              {iaLoading ? 'Génération…' : "Générer avec l'IA"}
            </button>
          </div>
          {iaErr && <p style={{ color: '#dc2626', margin: 0 }}>{iaErr}</p>}
        </fieldset>
      )}

      {/* NTMKT23 — insertion d'un bloc réutilisable : COPIE du fragment dans
          le corps (snapshot) — modifier le bloc source ne rétro-modifie
          jamais une campagne déjà écrite/envoyée. */}
      {blocs.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ fontSize: '0.8rem', color: '#475569' }}>
            Bloc réutilisable
            <select className="form-input" data-testid="campagne-bloc-select"
              value={blocChoisi} onChange={e => setBlocChoisi(e.target.value)}>
              <option value="">—</option>
              {blocs.map(b => (
                <option key={b.id} value={b.id}>{b.nom}</option>
              ))}
            </select>
          </label>
          <button type="button" className="btn btn-light"
            data-testid="campagne-bloc-inserer" onClick={insererBloc}>
            Insérer le bloc
          </button>
        </div>
      )}

      {listesDispo.length > 0 && (
        <fieldset style={{ border: '1px solid #e2e8f0', borderRadius: 8,
          padding: '0.5rem 0.75rem' }}>
          <legend style={{ fontSize: '0.8rem', color: '#475569' }}>
            Listes de diffusion ciblées
          </legend>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {listesDispo.map(l => (
              <label key={l.id} style={{ display: 'flex', alignItems: 'center',
                gap: 4, fontSize: '0.85rem' }}>
                <input type="checkbox" data-testid={`campagne-liste-${l.id}`}
                  checked={form.listes.includes(l.id)}
                  onChange={() => toggleListe(l.id)} />
                {l.nom}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <fieldset style={{ border: '1px dashed #cbd5e1', borderRadius: 8,
        padding: '0.5rem 0.75rem' }}>
        <legend style={{ fontSize: '0.8rem', color: '#475569' }}>
          Variantes de langue (XMKT11 — optionnel, FR par défaut ci-dessus)
        </legend>
        {LANGUES_VARIANTES.map(l => (
          <div key={l.key} style={{ display: 'flex', gap: '0.4rem',
            marginBottom: 4 }}>
            <span style={{ fontSize: '0.78rem', color: '#64748b',
              minWidth: 60 }}>{l.label}</span>
            <input className="form-input" placeholder="Objet"
              data-testid={`campagne-variante-${l.key}-objet`}
              value={form.variantes_langue?.[l.key]?.objet || ''}
              onChange={setVarianteLangue(l.key, 'objet')}
              style={{ flex: 1 }} />
            <input className="form-input" placeholder="Corps"
              data-testid={`campagne-variante-${l.key}-corps`}
              value={form.variantes_langue?.[l.key]?.corps || ''}
              onChange={setVarianteLangue(l.key, 'corps')}
              style={{ flex: 2 }} />
          </div>
        ))}
      </fieldset>

      {initial?.id && (
        <fieldset style={{ border: '1px solid #e2e8f0', borderRadius: 8,
          padding: '0.5rem 0.75rem' }}>
          <legend style={{ fontSize: '0.8rem', color: '#475569' }}>
            Aperçu fusionné (XMKT8)
          </legend>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input className="form-input" placeholder="Id du lead d'exemple"
              data-testid="campagne-apercu-lead-id" value={leadIdApercu}
              onChange={e => setLeadIdApercu(e.target.value)}
              style={{ flex: 1 }} />
            <button type="button" className="btn btn-light"
              data-testid="campagne-apercu-btn" disabled={apercuLoading}
              onClick={apercuFusion}>
              {apercuLoading ? 'Aperçu…' : 'Prévisualiser fusionné'}
            </button>
          </div>
          {apercuErr && <p style={{ color: '#dc2626' }}>{apercuErr}</p>}
          {corpsApercu && (
            <p data-testid="campagne-apercu-resultat"
              style={{ whiteSpace: 'pre-wrap', background: '#f8fafc',
                padding: '0.5rem', borderRadius: 6, marginTop: 6 }}>
              {corpsApercu}
            </p>
          )}
        </fieldset>
      )}

      <fieldset style={{ border: '1px dashed #cbd5e1', borderRadius: 8,
        padding: '0.5rem 0.75rem' }}>
        <legend style={{ fontSize: '0.8rem', color: '#475569' }}>
          Test A/B (XMKT14)
        </legend>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6,
          fontSize: '0.85rem' }}>
          <input type="checkbox" data-testid="campagne-ab-toggle"
            checked={abActif} onChange={toggleAb} />
          Activer un test A/B sur cette campagne
        </label>
        {abActif && (
          <div style={{ display: 'grid', gap: '0.4rem', marginTop: 6 }}>
            <input className="form-input" placeholder="Objet — variante B"
              data-testid="campagne-ab-objet-b"
              value={form.ab_test.objet_b || ''} onChange={setAbField('objet_b')} />
            <textarea className="form-input" placeholder="Corps — variante B"
              rows={3} data-testid="campagne-ab-corps-b"
              value={form.ab_test.corps_b || ''} onChange={setAbField('corps_b')} />
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
                % échantillon
                <input type="number" min={1} max={100} className="form-input"
                  data-testid="campagne-ab-pct"
                  value={form.ab_test.pct_echantillon ?? 20}
                  onChange={setAbField('pct_echantillon')} />
              </label>
              <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
                Fenêtre de décision (h)
                <input type="number" min={1} className="form-input"
                  data-testid="campagne-ab-fenetre"
                  value={form.ab_test.fenetre_heures ?? 4}
                  onChange={setAbField('fenetre_heures')} />
              </label>
              <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
                Critère
                <select className="form-input" data-testid="campagne-ab-critere"
                  value={form.ab_test.critere || 'ouvertures'}
                  onChange={setAbField('critere')}>
                  {AB_CRITERES.map(c => (
                    <option key={c.key} value={c.key}>{c.label}</option>))}
                </select>
              </label>
            </div>
          </div>
        )}
      </fieldset>

      {err && <p style={{ color: '#dc2626', margin: 0 }}>{err}</p>}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button type="submit" className="btn btn-primary"
          data-testid="campagne-save" disabled={saving}>
          {editing ? 'Enregistrer' : 'Créer la campagne'}
        </button>
        {onCancel && (
          <button type="button" className="btn btn-light" onClick={onCancel}>
            Annuler
          </button>
        )}
      </div>
    </form>
  )
}
