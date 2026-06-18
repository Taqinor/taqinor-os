// Onglet « Avancé » de la page Paramètres (hypothèses ROI, logique de devis,
// types d'intervention, checklist d'exécution, champs personnalisés). JSX,
// champs, libellés et styles identiques à l'ancien bloc monolithique.
import { SectionTitle, Field } from './peComponents'
import { inputBase, cardStyle } from './peConstants'

export default function AvanceSection({
  form, set,
  typesItv, newType, setNewType, addType, renameType, delType,
  checklistEtapes, newEtape, setNewEtape, addEtape, renameEtape, toggleEtapeActif, delEtape,
  cfModule, setCfModule, cfDefs, newCf, setNewCf, addCf, delCf, loadCfDefs,
}) {
  return (
    <>
      {/* ROI — hypothèses (tarif ONEE, productible) */}
      <div style={cardStyle}>
        <SectionTitle color="#0e7490" label="Hypothèses ROI" icon={<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Constantes utilisées pour les estimations d'économies/rentabilité.
          Les valeurs par défaut reprennent l'historique du simulateur — rien
          ne change tant que vous ne les modifiez pas.
        </p>
        <div className="pe-grid-2">
          <Field label="Tarif ONEE moyen (MAD/kWh)">
            <input style={inputBase} type="number" min="0" step="0.001"
                   name="onee_tarif_kwh" value={form.onee_tarif_kwh} onChange={set} />
          </Field>
          <Field label="Productible (kWh/kWc/an)">
            <input style={inputBase} type="number" min="0" step="1"
                   name="productible_kwh_kwc" value={form.productible_kwh_kwc} onChange={set} />
          </Field>
          <Field label="Seuil d'approbation de remise (%)">
            <input style={inputBase} type="number" min="0" max="100" step="0.01"
                   name="discount_approval_threshold" placeholder="vide = désactivé"
                   value={form.discount_approval_threshold} onChange={set} />
          </Field>
          <Field label="Seuil régime « Déclaration » (kWc)">
            <input style={inputBase} type="number" min="0" step="0.01"
                   name="seuil_regime_declaration_kwc"
                   value={form.seuil_regime_declaration_kwc} onChange={set} />
          </Field>
          <Field label="Seuil régime « Autorisation ANRE » (kWc)">
            <input style={inputBase} type="number" min="0" step="0.01"
                   name="seuil_regime_anre_kwc"
                   value={form.seuil_regime_anre_kwc} onChange={set} />
          </Field>
        </div>
        <p style={{ margin: '0.5rem 0 0', fontSize: 11, color: '#94a3b8' }}>
          Seuils loi 82-21 proposés à la création d'un chantier (régime
          suggéré, modifiable) : sous le 1er seuil = Déclaration, entre les
          deux = Accord de raccordement, au-dessus du 2nd = Autorisation ANRE.
        </p>
        <p style={{ margin: '0.5rem 0 0', fontSize: 11, color: '#94a3b8' }}>
          Au-delà de ce seuil de remise, un devis exige l'approbation d'un
          administrateur avant l'envoi. Vide = désactivé (défaut).
        </p>
      </div>

      {/* Logique de devis (avancé) — paramètres implicites du simulateur (D5) */}
      <div style={cardStyle}>
        <SectionTitle color="#7c3aed" label="Logique de devis (avancé)" icon={<><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Paramètres implicites du générateur de devis, rendus modifiables.
          Les valeurs par défaut reprennent EXACTEMENT les constantes du
          simulateur — le devis reste identique tant que vous ne les
          modifiez pas. Chaque changement est tracé (journal d'audit).
        </p>
        <div className="pe-grid-2">
          <Field label="Rendement global (0–1)">
            <input style={inputBase} type="number" min="0" max="1" step="0.01"
                   name="rendement_global" value={form.rendement_global} onChange={set} />
          </Field>
          <Field label="Panneaux par tranche de 900 MAD (auto-remplir)">
            <input style={inputBase} type="number" min="1" step="1"
                   name="panneaux_par_900mad" value={form.panneaux_par_900mad} onChange={set} />
          </Field>
          <Field label="Prix cible /kWc par défaut (MAD)">
            <input style={inputBase} type="number" min="0" step="any"
                   name="prix_cible_kwc_defaut" placeholder="vide = aucun"
                   value={form.prix_cible_kwc_defaut} onChange={set} />
          </Field>
          <Field label="Limite de remise conseillée (%)">
            <input style={inputBase} type="number" min="0" max="100" step="0.01"
                   name="remise_max_pct" placeholder="vide = aucune"
                   value={form.remise_max_pct} onChange={set} />
          </Field>
        </div>
        <p style={{ margin: '0.5rem 0 0', fontSize: 11, color: '#94a3b8' }}>
          Le rendement et le tarif ONEE (ci-dessus) pilotent les économies
          estimées ; le ratio de dimensionnement pilote la suggestion de
          panneaux du devis auto ; le prix cible pré-remplit le générateur ;
          la limite de remise affiche un repère (sans bloquer la saisie).
          Les tables tarifaires ONEE par tranche et les facteurs de
          production par région restent un raffinement futur (modèle de
          calcul à valider avec le founder).
        </p>
      </div>

      {/* Chantiers — Types d'intervention */}
      <div style={cardStyle}>
        <SectionTitle color="#0d9488" label="Chantiers — Types d'intervention" icon={<><path d="M14.7 6.3a4 4 0 0 0-5.6 5.6l-6 6 2 2 6-6a4 4 0 0 0 5.6-5.6l-2.5 2.5-2-2 2.5-2.5z"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Types d'intervention proposés sur les chantiers. Les types système
          sont protégés ; un type déjà utilisé ne peut pas être supprimé.
        </p>
        {typesItv.map(t => (
          <div key={t.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
            <input style={{ ...inputBase, flex: 1 }} defaultValue={t.libelle}
                   onBlur={e => renameType(t, e.target.value)} />
            {t.protege
              ? <span style={{ fontSize: 10, color: '#0d9488', fontWeight: 600 }}>système</span>
              : (
                <button type="button" onClick={() => delType(t)}
                        disabled={t.en_usage > 0}
                        style={{ border: 'none', background: t.en_usage > 0 ? '#e2e8f0' : '#fee2e2', color: t.en_usage > 0 ? '#94a3b8' : '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: t.en_usage > 0 ? 'not-allowed' : 'pointer' }}>✕</button>
              )}
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6 }}>
          <input style={{ ...inputBase, flex: 1 }} placeholder="Nouveau type" value={newType}
                 onChange={e => setNewType(e.target.value)}
                 onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addType() } }} />
          <button type="button" onClick={addType}
                  style={{ border: 'none', background: '#0d9488', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
        </div>
      </div>

      {/* Chantiers — Checklist d'exécution */}
      <div style={cardStyle}>
        <SectionTitle color="#2563eb" label="Chantiers — Checklist d'exécution" icon={<><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Étapes proposées sur la checklist des chantiers. Désactivez une
          étape pour la retirer des nouveaux chantiers sans toucher aux
          chantiers existants ; les étapes système sont protégées.
        </p>
        {checklistEtapes.map(et => (
          <div key={et.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
            <input style={{ ...inputBase, flex: 1, opacity: et.actif ? 1 : 0.5 }} defaultValue={et.libelle}
                   onBlur={e => renameEtape(et, e.target.value)} />
            {et.capture_serie && <span style={{ fontSize: 10, color: '#2563eb' }} title="Saisie de n° de série">série</span>}
            <button type="button" onClick={() => toggleEtapeActif(et)}
                    title={et.actif ? 'Désactiver' : 'Activer'}
                    style={{ border: 'none', background: et.actif ? '#dcfce7' : '#e2e8f0', color: et.actif ? '#15803d' : '#64748b', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>
              {et.actif ? 'Actif' : 'Inactif'}
            </button>
            {et.protege
              ? <span style={{ fontSize: 10, color: '#2563eb', fontWeight: 600 }}>système</span>
              : (
                <button type="button" onClick={() => delEtape(et)}
                        style={{ border: 'none', background: '#fee2e2', color: '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>✕</button>
              )}
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6 }}>
          <input style={{ ...inputBase, flex: 1 }} placeholder="Nouvelle étape" value={newEtape}
                 onChange={e => setNewEtape(e.target.value)}
                 onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEtape() } }} />
          <button type="button" onClick={addEtape}
                  style={{ border: 'none', background: '#2563eb', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
        </div>
      </div>

      {/* Champs personnalisés */}
      <div style={cardStyle}>
        <SectionTitle color="#9333ea" label="Champs personnalisés" icon={<><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/></>}/>
        <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
          Ajoutez vos propres champs aux fiches (leads, clients, produits).
          Ils apparaissent dans le formulaire ; rien n'est perdu si vous en
          retirez un.
        </p>
        <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
          <select className="form-control" style={{ maxWidth: 140 }} value={cfModule}
                  onChange={e => { setCfModule(e.target.value); loadCfDefs(e.target.value) }}>
            <option value="lead">Leads</option>
            <option value="client">Clients</option>
            <option value="produit">Produits</option>
          </select>
        </div>
        {cfDefs.map(d => (
          <div key={d.id} style={{ display: 'flex', gap: 6, marginBottom: 5, alignItems: 'center' }}>
            <span style={{ flex: 1, fontSize: 13 }}>{d.libelle}</span>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>{d.type}</span>
            <button type="button" onClick={() => delCf(d)}
                    style={{ border: 'none', background: '#fee2e2', color: '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>✕</button>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <input style={{ ...inputBase, flex: '1 1 140px' }} placeholder="Libellé du champ"
                 value={newCf.libelle} onChange={e => setNewCf(c => ({ ...c, libelle: e.target.value }))} />
          <select className="form-control" style={{ maxWidth: 120 }} value={newCf.type}
                  onChange={e => setNewCf(c => ({ ...c, type: e.target.value }))}>
            <option value="text">Texte</option>
            <option value="number">Nombre</option>
            <option value="date">Date</option>
            <option value="choice">Choix</option>
            <option value="boolean">Oui/Non</option>
          </select>
          {newCf.type === 'choice' && (
            <input style={{ ...inputBase, flex: '1 1 160px' }} placeholder="Options (a, b, c)"
                   value={newCf.options} onChange={e => setNewCf(c => ({ ...c, options: e.target.value }))} />
          )}
          <button type="button" onClick={addCf}
                  style={{ border: 'none', background: '#9333ea', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
        </div>
      </div>
    </>
  )
}
