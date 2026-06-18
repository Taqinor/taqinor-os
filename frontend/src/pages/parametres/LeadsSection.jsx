// Onglet « Leads » de la page Paramètres (responsable/installateur par défaut,
// parrainage, étiquettes & motifs CRM, canaux/sources). JSX, champs, libellés
// et styles identiques à l'ancien bloc monolithique.
import { SectionTitle, Field } from './peComponents'
import { inputBase, onFocus, onBlur, cardStyle } from './peConstants'

export default function LeadsSection({
  form, set, setForm, assignables,
  tags, newTag, setNewTag, addTag, renameTag, delTag,
  motifs, newMotif, setNewMotif, addMotif, renameMotif, delMotif,
  canaux, newCanal, setNewCanal, addCanal, renameCanal, delCanal,
}) {
  return (
    <>
      {/* Leads — responsable par défaut */}
      <div style={cardStyle}>
        <SectionTitle color="#0369a1" label="Leads" icon={<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Responsable assigné automatiquement aux nouveaux leads (site web et
          création manuelle) quand aucun responsable n'est choisi.
        </p>
        <Field label="Responsable par défaut des nouveaux leads">
          <select style={inputBase} name="responsable_defaut_leads"
                  value={form.responsable_defaut_leads ?? ''} onChange={set}
                  onFocus={onFocus} onBlur={onBlur}>
            <option value="">— Aucun (laisser non assigné) —</option>
            {assignables.map(u => (
              <option key={u.id} value={u.id}>
                {u.username}{u.poste ? ` — ${u.poste}` : ''}
              </option>
            ))}
          </select>
        </Field>
        <p style={{ margin: '0.9rem 0 0.4rem', fontSize: 12.5, color: '#64748b' }}>
          Installateur (technicien) assigné automatiquement aux nouveaux
          chantiers quand aucun n'est choisi. Laisser vide = le créateur
          du chantier (comportement actuel).
        </p>
        <Field label="Installateur par défaut des nouveaux chantiers">
          <select style={inputBase} name="default_installer"
                  value={form.default_installer ?? ''} onChange={set}>
            <option value="">— Aucun (créateur du chantier) —</option>
            {assignables.map(u => (
              <option key={u.id} value={u.id}>
                {u.username}{u.poste ? ` — ${u.poste}` : ''}
              </option>
            ))}
          </select>
        </Field>
        <p style={{ margin: '0.9rem 0 0.4rem', fontSize: 12.5, color: '#64748b' }}>
          Programme de parrainage : récompense par défaut pré-remplie sur
          chaque nouveau parrainage (écran CRM → Parrainage).
        </p>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginBottom: 8 }}>
          <input type="checkbox" name="referral_enabled"
                 checked={!!form.referral_enabled}
                 onChange={e => setForm(f => ({ ...f, referral_enabled: e.target.checked }))} />
          Activer le programme de parrainage
        </label>
        <Field label="Récompense de parrainage par défaut (DH)">
          <input style={inputBase} type="number" min="0" step="any"
                 name="referral_reward" value={form.referral_reward}
                 onChange={set} />
        </Field>
      </div>

      {/* CRM — Étiquettes & motifs */}
      <div style={cardStyle}>
        <SectionTitle color="#7c3aed" label="CRM — Étiquettes & motifs" icon={<><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Étiquettes et motifs de perte proposés sur les leads. Le texte
          libre reste possible ; les leads existants ne changent pas.
        </p>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>Étiquettes</div>
        {tags.map(t => (
          <div key={t.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
            <input style={{ ...inputBase, flex: 1 }} defaultValue={t.nom}
                   onBlur={e => renameTag(t, e.target.value)} />
            <button type="button" onClick={() => delTag(t)}
                    style={{ border: '1px solid #fca5a5', color: '#ef4444', background: '#fff', borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}>✕</button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          <input style={{ ...inputBase, flex: 1 }} placeholder="Nouvelle étiquette" value={newTag}
                 onChange={e => setNewTag(e.target.value)}
                 onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag() } }} />
          <button type="button" onClick={addTag}
                  style={{ border: 'none', background: '#7c3aed', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
        </div>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 4 }}>Motifs de perte</div>
        {motifs.map(m => (
          <div key={m.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
            <input style={{ ...inputBase, flex: 1 }} defaultValue={m.nom}
                   onBlur={e => renameMotif(m, e.target.value)} />
            <button type="button" onClick={() => delMotif(m)}
                    style={{ border: '1px solid #fca5a5', color: '#ef4444', background: '#fff', borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}>✕</button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6 }}>
          <input style={{ ...inputBase, flex: 1 }} placeholder="Nouveau motif" value={newMotif}
                 onChange={e => setNewMotif(e.target.value)}
                 onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addMotif() } }} />
          <button type="button" onClick={addMotif}
                  style={{ border: 'none', background: '#7c3aed', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
        </div>
      </div>

      {/* CRM — Canaux / sources */}
      <div style={cardStyle}>
        <SectionTitle color="#0891b2" label="CRM — Canaux / sources" icon={<><path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Sources d'où viennent les leads. « Site web » est protégé (utilisé
          par le formulaire du site) et ne peut être ni renommé ni supprimé.
          Un canal déjà utilisé par des leads ne peut pas être supprimé.
        </p>
        {canaux.map(c => (
          <div key={c.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
            <input style={{ ...inputBase, flex: 1 }} defaultValue={c.libelle}
                   onBlur={e => renameCanal(c, e.target.value)} />
            {c.protege
              ? <span style={{ fontSize: 10, color: '#0891b2', fontWeight: 600 }}>protégé</span>
              : (
                <button type="button" onClick={() => delCanal(c)}
                        disabled={c.en_usage > 0}
                        title={c.en_usage > 0 ? `${c.en_usage} lead(s) utilisent ce canal` : 'Supprimer'}
                        style={{ border: 'none', background: c.en_usage > 0 ? '#e2e8f0' : '#fee2e2', color: c.en_usage > 0 ? '#94a3b8' : '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: c.en_usage > 0 ? 'not-allowed' : 'pointer' }}>✕</button>
              )}
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6 }}>
          <input style={{ ...inputBase, flex: 1 }} placeholder="Nouveau canal" value={newCanal}
                 onChange={e => setNewCanal(e.target.value)}
                 onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCanal() } }} />
          <button type="button" onClick={addCanal}
                  style={{ border: 'none', background: '#0891b2', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
        </div>
      </div>
    </>
  )
}
