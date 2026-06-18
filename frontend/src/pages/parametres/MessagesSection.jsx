// Onglet « Messages & relances » de la page Paramètres (niveaux de relance,
// modèles WhatsApp FR/Darija). JSX, champs, libellés et styles identiques à
// l'ancien bloc monolithique.
import { SectionTitle, Field } from './peComponents'
import { inputBase, cardStyle } from './peConstants'

export default function MessagesSection({
  niveaux, setNiveau, saveNiveaux, niveauxSaved,
  messages, setMsgField, saveMessage, msgSavedCle,
}) {
  return (
    <>
      {/* Niveaux de relance */}
      <div style={cardStyle}>
        <SectionTitle color="#dc2626" label="Niveaux de relance" icon={<><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Seuils de retard (en jours) pour relancer les factures impayées.
          Vue / consigne / impression uniquement — aucun envoi automatique.
        </p>
        {niveaux.map(n => (
          <div key={n.id} className="pe-grid-relance" style={{ marginBottom: '0.6rem' }}>
            <Field label={`Niveau ${n.ordre}`}>
              <input style={inputBase} value={n.nom}
                     onChange={e => setNiveau(n.id, 'nom', e.target.value)} />
            </Field>
            <Field label="Jours (J+)">
              <input style={inputBase} type="number" min="0" value={n.delai_jours}
                     onChange={e => setNiveau(n.id, 'delai_jours', e.target.value)} />
            </Field>
          </div>
        ))}
        {niveaux.length === 0 && (
          <p style={{ fontSize: 12, color: '#94a3b8' }}>Aucun niveau configuré.</p>
        )}
        <button type="button" onClick={saveNiveaux}
                style={{ marginTop: 4, padding: '8px 18px', borderRadius: 8, border: 'none', background: niveauxSaved ? '#10b981' : '#dc2626', color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
          {niveauxSaved ? 'Niveaux enregistrés ✓' : 'Enregistrer les niveaux'}
        </button>
      </div>

      {/* Messages WhatsApp */}
      <div style={cardStyle}>
        <SectionTitle color="#16a34a" label="Messages WhatsApp" icon={<><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.38 8.38 0 0 1-4-1L3 21l1-5.5a8.38 8.38 0 0 1-1-4A8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5z"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Modèles du message « Envoyer par WhatsApp » (devis, facture,
          rappel). Variantes Français et Darija. Placeholders disponibles :
          {' '}<code>{'{civilite}'}</code> <code>{'{nom}'}</code>{' '}
          <code>{'{reference}'}</code> <code>{'{lien}'}</code>{' '}
          <code>{'{n}'}</code>. Le lien envoyé est public, en lecture seule,
          expire après 30 jours et ne montre que le PDF client.
        </p>
        {messages.map(m => (
          <div key={m.cle} style={{ borderTop: '1px solid #f1f5f9', paddingTop: 10, marginTop: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
              {m.label}
              {m.placeholders?.length > 0 && (
                <span style={{ fontWeight: 400, color: '#94a3b8', marginLeft: 6 }}>
                  ({m.placeholders.join(' ')})
                </span>
              )}
            </div>
            <Field label="Français">
              <textarea style={{ ...inputBase, minHeight: 54, resize: 'vertical' }}
                        value={m.corps_fr}
                        onChange={e => setMsgField(m.cle, 'corps_fr', e.target.value)} />
            </Field>
            <Field label="Darija (laisser vide = utiliser le Français)">
              <textarea style={{ ...inputBase, minHeight: 54, resize: 'vertical' }}
                        value={m.corps_darija}
                        onChange={e => setMsgField(m.cle, 'corps_darija', e.target.value)} />
            </Field>
            <button type="button" onClick={() => saveMessage(m)}
                    style={{ marginTop: 2, padding: '6px 14px', borderRadius: 8, border: 'none', background: msgSavedCle === m.cle ? '#10b981' : '#16a34a', color: '#fff', fontWeight: 600, fontSize: 12.5, cursor: 'pointer' }}>
              {msgSavedCle === m.cle ? 'Enregistré ✓' : 'Enregistrer'}
            </button>
          </div>
        ))}
        {messages.length === 0 && (
          <p style={{ fontSize: 12, color: '#94a3b8' }}>Chargement…</p>
        )}
      </div>
    </>
  )
}
