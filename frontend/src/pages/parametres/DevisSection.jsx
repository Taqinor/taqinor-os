// Onglet « Devis & Factures » de la page Paramètres (échéancier, validité,
// pompage, numérotation, commission, TVA/Taxes). JSX, champs, libellés et
// styles identiques à l'ancien bloc monolithique.
import { SectionTitle, Field } from './peComponents'
import { inputBase, cardStyle, MODE_LABELS, DOC_TYPES } from './peConstants'

export default function DevisSection({ form, set, setPT, setPrefix, setNumbering, numberingPreview }) {
  return (
    <>
      {/* Devis — échéancier, validité, pompage, numérotation */}
      <div style={cardStyle}>
        <SectionTitle color="#1d4ed8" label="Devis" icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Conditions de paiement par marché (acompte / matériel / solde, en %).
          Les factures d'acompte suivent ces valeurs.
        </p>
        {Object.keys(MODE_LABELS).map(mode => (
          <div key={mode} style={{ marginBottom: '0.6rem' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>{MODE_LABELS[mode]}</div>
            <div className="pe-grid-3">
              {['acompte', 'materiel', 'solde'].map(k => (
                <div key={k}>
                  <label style={{ fontSize: 10.5, color: '#64748b', textTransform: 'capitalize' }}>{k} %</label>
                  <input style={inputBase} type="number" min="0" max="100"
                         value={form.payment_terms?.[mode]?.[k] ?? ''}
                         onChange={e => setPT(mode, k, e.target.value)} />
                </div>
              ))}
            </div>
          </div>
        ))}
        <div className="pe-grid-2" style={{ marginTop: '0.6rem' }}>
          <Field label="Validité du devis (jours)">
            <input style={inputBase} type="number" min="1" name="quote_validity_days"
                   value={form.quote_validity_days} onChange={set} />
          </Field>
          <Field label="Heures de pompage / jour (agricole, défaut)">
            <input style={inputBase} type="number" min="0" step="0.5" name="agricole_pump_hours"
                   value={form.agricole_pump_hours} onChange={set} />
          </Field>
        </div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', margin: '0.8rem 0 0.4rem' }}>
          Numérotation des pièces
        </div>
        {DOC_TYPES.map(([k, lbl]) => (
          <div key={k} style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 3 }}>{lbl}</div>
            <div className="pe-grid-3">
              <div>
                <label style={{ fontSize: 10.5, color: '#64748b' }}>Préfixe</label>
                <input style={inputBase} value={form.doc_prefixes?.[k] ?? ''}
                       onChange={e => setPrefix(k, e.target.value)} />
              </div>
              <div>
                <label style={{ fontSize: 10.5, color: '#64748b' }}>Largeur (chiffres)</label>
                <input style={inputBase} type="number" min="1" max="10"
                       value={form.doc_numbering?.[k]?.padding ?? 4}
                       onChange={e => setNumbering(k, 'padding', e.target.value)} />
              </div>
              <div>
                <label style={{ fontSize: 10.5, color: '#64748b' }}>Réinitialisation</label>
                <select style={inputBase} value={form.doc_numbering?.[k]?.reset ?? 'monthly'}
                        onChange={e => setNumbering(k, 'reset', e.target.value)}>
                  <option value="monthly">Mensuelle</option>
                  <option value="yearly">Annuelle</option>
                  <option value="none">Continue</option>
                </select>
              </div>
            </div>
            <div style={{ fontSize: 10.5, color: '#94a3b8', marginTop: 2, fontFamily: 'monospace' }}>
              Aperçu : {numberingPreview(k)}
            </div>
          </div>
        ))}
        <p style={{ margin: '0.6rem 0 0', fontSize: 11, color: '#94a3b8' }}>
          Les numéros déjà émis ne changent pas ; seuls les nouveaux suivent ces
          réglages. « Mensuelle » repart à 1 chaque mois (comportement actuel),
          « Annuelle » chaque année, « Continue » ne repart jamais. La
          numérotation reste sans trou et sans collision.
        </p>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', margin: '1rem 0 0.4rem' }}>
          Commission commerciale
        </div>
        <p style={{ margin: '0 0 0.7rem', fontSize: 11.5, color: '#94a3b8' }}>
          Désactivée par défaut. Calculée sur les devis signés, par
          commercial (responsable du lead, sinon créateur). Visible des
          seuls admins dans Rapports → Commissions commerciales.
        </p>
        <div className="pe-grid-2">
          <Field label="Mode">
            <select style={inputBase} name="commission_mode"
                    value={form.commission_mode} onChange={set}>
              <option value="off">Désactivée</option>
              <option value="pct_devis">% du HT des devis signés</option>
              <option value="par_kwc">MAD par kWc installé</option>
            </select>
          </Field>
          <Field label={form.commission_mode === 'par_kwc'
            ? 'Valeur (MAD/kWc)' : 'Valeur (%)'}>
            <input style={inputBase} type="number" min="0" step="any"
                   name="commission_valeur" value={form.commission_valeur}
                   onChange={set}
                   disabled={form.commission_mode === 'off'} />
          </Field>
        </div>
      </div>

      {/* TVA / Taxes (réglage légal/comptable) */}
      <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #fde68a', padding: '1.25rem 1.4rem' }}>
        <SectionTitle color="#b45309" label="TVA / Taxes" icon={<><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#b45309' }}>
          ⚠ Réglage légal/comptable. Les valeurs par défaut (10 % panneaux,
          20 % standard) correspondent à la réforme marocaine. À vérifier
          avec votre comptable avant toute modification.
        </p>
        <div className="pe-grid-2">
          <Field label="Taux standard (%)">
            <input style={inputBase} type="number" min="0" max="100" step="0.01"
                   name="tva_standard" value={form.tva_standard} onChange={set} />
          </Field>
          <Field label="Taux panneaux PV (%)">
            <input style={inputBase} type="number" min="0" max="100" step="0.01"
                   name="tva_panneaux" value={form.tva_panneaux} onChange={set} />
          </Field>
        </div>
      </div>
    </>
  )
}
