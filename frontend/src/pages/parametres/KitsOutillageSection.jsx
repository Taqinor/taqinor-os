import { useEffect, useState } from 'react'
import stockApi from '../../api/stockApi'
import installationsApi from '../../api/installationsApi'

// F2 — éditeur des kits d'outillage (Paramètres). Un kit = liste ordonnée
// d'outils du catalogue Outillage, sélectionnable par type d'intervention.
// Ajout / renommage / réordre / désactivation comme tout autre référentiel ;
// un kit système (protégé) se désactive plutôt que se supprimer.

const inputBase = {
  border: '1px solid #cbd5e1', borderRadius: 8, padding: '6px 10px',
  fontSize: 13.5, outline: 'none',
}
const SectionTitle = ({ label }) => (
  <h3 style={{ margin: '0 0 0.4rem', fontSize: 15, color: '#0d9488', display: 'flex', alignItems: 'center', gap: 8 }}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
    </svg>
    {label}
  </h3>
)

export default function KitsOutillageSection() {
  const [kits, setKits]   = useState([])
  const [tools, setTools] = useState([])
  const [types, setTypes] = useState([])
  const [newKit, setNewKit] = useState('')

  const loadKits = () => stockApi.getKitsOutillage()
    .then(r => setKits(r.data.results ?? r.data)).catch(() => {})

  useEffect(() => {
    loadKits()
    stockApi.getOutillage().then(r => setTools(r.data.results ?? r.data)).catch(() => {})
    installationsApi.getTypesIntervention?.()
      .then(r => setTypes(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const addKit = async () => {
    const nom = newKit.trim()
    if (!nom) return
    try { await stockApi.saveKitOutillage(null, { nom, ordre: kits.length }) } catch { /* */ }
    setNewKit(''); loadKits()
  }
  const renameKit = async (kit, nom) => {
    if (nom.trim() && nom !== kit.nom) {
      try { await stockApi.saveKitOutillage(kit.id, { nom: nom.trim() }) } catch { /* */ }
    }
  }
  const setKitType = async (kit, type_intervention) => {
    try { await stockApi.saveKitOutillage(kit.id, { type_intervention }); loadKits() } catch { /* */ }
  }
  const toggleActif = async (kit) => {
    try { await stockApi.saveKitOutillage(kit.id, { actif: !kit.actif }); loadKits() } catch { /* */ }
  }
  const delKit = async (kit) => {
    try { await stockApi.deleteKitOutillage(kit.id); loadKits() } catch { /* */ }
  }

  // Items : on renvoie la liste complète (le serveur remplace) avec ordre recalculé.
  const saveItems = async (kit, items) => {
    const payload = items.map((it, i) => ({ outil: it.outil, ordre: i }))
    try { await stockApi.saveKitOutillage(kit.id, { items: payload }); loadKits() } catch { /* */ }
  }
  const addTool = (kit, outilId) => {
    if (!outilId) return
    if ((kit.items ?? []).some(it => String(it.outil) === String(outilId))) return
    saveItems(kit, [...(kit.items ?? []), { outil: Number(outilId) }])
  }
  const removeTool = (kit, idx) =>
    saveItems(kit, (kit.items ?? []).filter((_, i) => i !== idx))
  const moveTool = (kit, idx, dir) => {
    const items = [...(kit.items ?? [])]
    const j = idx + dir
    if (j < 0 || j >= items.length) return
    ;[items[idx], items[j]] = [items[j], items[idx]]
    saveItems(kit, items)
  }

  return (
    <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
      <SectionTitle label="Outillage — Kits" />
      <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
        Modèles réutilisables d'outils (tirés du catalogue Outillage),
        sélectionnables par type d'intervention. Désactivez un kit pour le
        retirer des nouvelles sélections sans toucher aux interventions
        passées ; les kits système sont protégés.
      </p>

      {kits.map(kit => (
        <div key={kit.id} style={{ border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 12px', marginBottom: 10, opacity: kit.actif ? 1 : 0.6 }}>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            <input style={{ ...inputBase, flex: '1 1 160px', fontWeight: 600 }}
                   defaultValue={kit.nom} onBlur={e => renameKit(kit, e.target.value)} />
            <select className="form-control" style={{ maxWidth: 190 }} value={kit.type_intervention || ''}
                    onChange={e => setKitType(kit, e.target.value)}>
              <option value="">Tous types d'intervention</option>
              {types.map(t => <option key={t.id} value={t.cle}>{t.libelle}</option>)}
            </select>
            <button type="button" onClick={() => toggleActif(kit)}
                    style={{ border: 'none', background: kit.actif ? '#dcfce7' : '#e2e8f0', color: kit.actif ? '#15803d' : '#64748b', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>
              {kit.actif ? 'Actif' : 'Inactif'}
            </button>
            {kit.protege
              ? <span style={{ fontSize: 10, color: '#0d9488', fontWeight: 600 }}>système</span>
              : <button type="button" onClick={() => delKit(kit)}
                        style={{ border: 'none', background: '#fee2e2', color: '#b91c1c', borderRadius: 6, padding: '4px 9px', cursor: 'pointer' }}>✕</button>}
          </div>

          <div style={{ marginTop: 8, paddingLeft: 4 }}>
            {(kit.items ?? []).length === 0 && (
              <p style={{ margin: '2px 0 6px', fontSize: 11.5, color: '#94a3b8' }}>Aucun outil — ajoutez-en ci-dessous.</p>
            )}
            {(kit.items ?? []).map((it, idx) => (
              <div key={it.id ?? `${it.outil}-${idx}`} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                <span style={{ fontSize: 12, color: '#94a3b8', width: 18 }}>{idx + 1}.</span>
                <span style={{ flex: 1, fontSize: 13 }}>{it.outil_nom ?? tools.find(t => t.id === it.outil)?.nom ?? `Outil ${it.outil}`}</span>
                <button type="button" onClick={() => moveTool(kit, idx, -1)} disabled={idx === 0}
                        style={{ border: 'none', background: '#f1f5f9', borderRadius: 6, padding: '2px 7px', cursor: idx === 0 ? 'default' : 'pointer' }}>↑</button>
                <button type="button" onClick={() => moveTool(kit, idx, 1)} disabled={idx === (kit.items.length - 1)}
                        style={{ border: 'none', background: '#f1f5f9', borderRadius: 6, padding: '2px 7px', cursor: 'pointer' }}>↓</button>
                <button type="button" onClick={() => removeTool(kit, idx)}
                        style={{ border: 'none', background: '#fee2e2', color: '#b91c1c', borderRadius: 6, padding: '2px 7px', cursor: 'pointer' }}>✕</button>
              </div>
            ))}
            <select className="form-control" style={{ maxWidth: 260, marginTop: 4 }} value=""
                    onChange={e => { addTool(kit, e.target.value); e.target.value = '' }}>
              <option value="">＋ Ajouter un outil…</option>
              {tools.map(t => <option key={t.id} value={t.id}>{t.nom}</option>)}
            </select>
          </div>
        </div>
      ))}

      <div style={{ display: 'flex', gap: 6 }}>
        <input style={{ ...inputBase, flex: 1 }} placeholder="Nouveau kit" value={newKit}
               onChange={e => setNewKit(e.target.value)}
               onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addKit() } }} />
        <button type="button" onClick={addKit}
                style={{ border: 'none', background: '#0d9488', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>＋</button>
      </div>
    </div>
  )
}
