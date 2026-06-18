// Onglet « Société & identité » de la page Paramètres.
// JSX, champs, libellés et styles identiques à l'ancien bloc monolithique.
import {
  uploadLogo, deleteLogo,
  uploadSignature, deleteSignature,
} from '../../features/parametres/store/parametresSlice'
import { Ic, SectionTitle, Field, UploadZone } from './peComponents'
import { inputBase, onFocus, onBlur, cardStyle, mediaUrl } from './peConstants'

export default function SocieteSection({ accent, profile, form, set, uploading, dispatch }) {
  return (
    <>
      {/* ── Live preview card ── */}
      <div style={{
        borderRadius: 14, overflow: 'hidden',
        border: `1px solid ${accent}30`,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
      }}>
        <div style={{
          background: `linear-gradient(135deg, ${accent}12 0%, ${accent}06 100%)`,
          borderBottom: `1px solid ${accent}20`,
          padding: '1rem 1.5rem',
          display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        }}>
          {/* Logo or initials */}
          <div style={{
            width: 52, height: 52, borderRadius: 12, flexShrink: 0,
            background: profile?.logo_url ? 'transparent' : accent + '20',
            border: `1.5px solid ${accent}30`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden',
          }}>
            {mediaUrl(profile?.logo_url)
              ? <img src={mediaUrl(profile.logo_url)} alt="logo" style={{ width: '100%', height: '100%', objectFit: 'contain', padding: 4 }}/>
              : <span style={{ fontSize: 20, fontWeight: 800, color: accent }}>
                  {(form.nom || '?')[0].toUpperCase()}
                </span>
            }
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: accent, letterSpacing: '0.01em' }}>
              {form.nom || 'Nom de votre entreprise'}
            </h3>
            <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748b' }}>
              {[form.adresse, form.email, form.telephone].filter(Boolean).join(' · ') || 'Adresse · Email · Téléphone'}
            </p>
          </div>

          {/* Color preview */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <div style={{ width: 22, height: 22, borderRadius: '50%', background: accent, boxShadow: `0 0 0 3px ${accent}30` }}/>
            <span style={{ fontSize: 11.5, color: '#64748b', fontFamily: 'monospace' }}>{accent}</span>
          </div>

          <div style={{ padding: '4px 10px', borderRadius: 20, background: accent + '20', border: `1px solid ${accent}30`, fontSize: 11, color: accent, fontWeight: 600 }}>
            Aperçu PDF
          </div>
        </div>
      </div>

      <div className="pe-main">
        {/* ─── Form fields ─── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

          {/* Identité */}
          <div style={cardStyle}>
            <SectionTitle color="#1d4ed8" label="Identité" icon={<><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></>}/>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <Field label="Nom de l'entreprise" required>
                <input style={inputBase} name="nom" value={form.nom} onChange={set} onFocus={onFocus} onBlur={onBlur} required placeholder="TAQINOR SARL"/>
              </Field>
              <Field label="Adresse">
                <textarea style={{ ...inputBase, resize: 'vertical', minHeight: 68 }} name="adresse" value={form.adresse} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="12 rue Mohammed V, Casablanca" rows={2}/>
              </Field>
            </div>
          </div>

          {/* Contact */}
          <div style={cardStyle}>
            <SectionTitle color="#059669" label="Coordonnées" icon={<><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.61 3.5 2 2 0 0 1 3.6 1.32h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9a16 16 0 0 0 6 6l1.27-.95a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></>}/>
            <div className="pe-grid-2">
              <Field label="Email">
                <input style={inputBase} name="email" type="email" value={form.email} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="contact@entreprise.ma"/>
              </Field>
              <Field label="Téléphone">
                <input style={inputBase} name="telephone" value={form.telephone} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="+212 6 XX XX XX XX"/>
              </Field>
            </div>
          </div>

          {/* Légal */}
          <div style={cardStyle}>
            <SectionTitle color="#7c3aed" label="Informations légales" icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>}/>
            <div className="pe-grid-2">
              <Field label="SIRET">
                <input style={inputBase} name="siret" value={form.siret} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="14 chiffres"/>
              </Field>
              <Field label="N° TVA intracommunautaire">
                <input style={inputBase} name="tva_intra" value={form.tva_intra} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="FR12345678901"/>
              </Field>
              <Field label="RIB / IBAN">
                <input style={inputBase} name="rib" value={form.rib} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="FR76 3000…"/>
              </Field>
              <Field label="Banque">
                <input style={inputBase} name="banque" value={form.banque} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="CIH, Attijariwafa…"/>
              </Field>
            </div>
          </div>

          {/* Identifiants légaux (Maroc) */}
          <div style={cardStyle}>
            <SectionTitle color="#0d9488" label="Identifiants légaux (Maroc)" icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>}/>
            <p style={{ margin: '0 0 0.9rem', fontSize: 11.5, color: '#64748b' }}>
              L'ICE, l'IF et le RC apparaissent en pied de page de vos factures (l'ICE est obligatoire au Maroc).
            </p>
            <div className="pe-grid-2">
              <Field label="ICE">
                <input style={inputBase} name="ice" value={form.ice} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="000000000000000"/>
              </Field>
              <Field label="IF (Identifiant Fiscal)">
                <input style={inputBase} name="identifiant_fiscal" value={form.identifiant_fiscal} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="00000000"/>
              </Field>
              <Field label="RC (Registre de Commerce)">
                <input style={inputBase} name="rc" value={form.rc} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="N° RC"/>
              </Field>
              <Field label="Patente / Taxe professionnelle">
                <input style={inputBase} name="patente" value={form.patente} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="N° patente"/>
              </Field>
              <Field label="CNSS">
                <input style={inputBase} name="cnss" value={form.cnss} onChange={set} onFocus={onFocus} onBlur={onBlur} placeholder="N° affiliation CNSS"/>
              </Field>
            </div>
          </div>

          {/* Couleur PDF */}
          <div style={cardStyle}>
            <SectionTitle color="#ea580c" label="Apparence PDF" icon={<><circle cx="12" cy="12" r="10"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></>}/>
            <Field label="Couleur principale">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ position: 'relative', flexShrink: 0 }}>
                  <input
                    type="color" name="couleur_principale" value={form.couleur_principale} onChange={set}
                    style={{ width: 46, height: 42, borderRadius: 9, border: '1.5px solid #e2e8f0', cursor: 'pointer', padding: 3, background: '#fff' }}
                  />
                </div>
                <input
                  style={{ ...inputBase, width: 130, fontFamily: 'monospace' }}
                  name="couleur_principale" value={form.couleur_principale} onChange={set}
                  onFocus={onFocus} onBlur={onBlur} placeholder="#1d4ed8"
                />
                <div style={{
                  flex: 1, height: 42, borderRadius: 9,
                  background: `linear-gradient(135deg, ${accent}, ${accent}99)`,
                  border: `1.5px solid ${accent}40`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <span style={{ fontSize: 11.5, color: '#fff', fontWeight: 600, textShadow: '0 1px 2px rgba(0,0,0,0.3)' }}>
                    Aperçu
                  </span>
                </div>
              </div>
            </Field>
          </div>
        </div>

        {/* ─── Media ─── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>

          {/* Logo */}
          <div style={cardStyle}>
            <SectionTitle color="#1d4ed8" label="Logo de l'entreprise" icon={<><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></>}/>
            <UploadZone
              label="Affiché en en-tête du PDF"
              hint="PNG, JPEG, WebP — max 2 Mo"
              currentUrl={profile?.logo_url}
              onUpload={f => dispatch(uploadLogo(f))}
              onDelete={() => dispatch(deleteLogo())}
              uploading={uploading}
            />
          </div>

          {/* Signature */}
          <div style={cardStyle}>
            <SectionTitle color="#7c3aed" label="Signature électronique" icon={<><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></>}/>
            <UploadZone
              label="Apposée en bas du PDF"
              hint="PNG, JPEG, WebP — max 2 Mo"
              currentUrl={profile?.signature_url}
              onUpload={f => dispatch(uploadSignature(f))}
              onDelete={() => dispatch(deleteSignature())}
              uploading={uploading}
            />
          </div>

          {/* PDF info */}
          <div style={{
            borderRadius: 12, padding: '0.9rem 1.1rem',
            background: `linear-gradient(135deg, ${accent}08, ${accent}14)`,
            border: `1px solid ${accent}25`,
            display: 'flex', gap: 10, alignItems: 'flex-start',
          }}>
            <Ic size={16} color={accent} sw={1.8}>
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </Ic>
            <p style={{ margin: 0, fontSize: 12.5, color: accent, lineHeight: 1.5 }}>
              <strong>Aperçu PDF :</strong> le logo, la signature et les informations ci-contre apparaissent automatiquement dans l'en-tête et le pied de page de tous vos devis et factures.
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
