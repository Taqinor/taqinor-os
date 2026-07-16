// Onglet « Société & identité » de la page Paramètres.
// Restylé sur le système de design (@/ui) ; champs, libellés et comportement
// identiques. Le champ Email reste <Input name="email" type="email"> (contrat
// e2e : input[name="email"]). La couleur d'accent (donnée utilisateur) pilote
// encore les aperçus de couleur via styles en ligne.
import { useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react'
import {
  uploadLogo, deleteLogo,
  uploadSignature, deleteSignature,
} from '../../features/parametres/store/parametresSlice'
import { Card, CardContent, Input, Textarea } from '../../ui'
import { Ic, SectionTitle, Field, UploadZone } from './peComponents'
import { mediaUrl } from './peConstants'
import DemoResetButton from './DemoResetButton'

// L773 — validation de format des identifiants marocains, NON bloquante : on
// affiche un indice si la longueur en chiffres ne correspond pas, sans rejeter
// la saisie. { len } = nombre de chiffres attendu.
const ID_FORMATS = {
  ice: { len: 15, nom: 'ICE' },
  identifiant_fiscal: { len: 8, nom: 'IF' },
  rc: { len: null, nom: 'RC' },
  patente: { len: 8, nom: 'Patente' },
  cnss: { len: 7, nom: 'CNSS' },
}
function idHint(field, value) {
  const f = ID_FORMATS[field]
  if (!f || !f.len) return null
  const digits = String(value || '').replace(/\D/g, '')
  if (!digits) return null
  if (digits.length !== f.len) {
    return `${f.nom} : ${f.len} chiffres attendus (${digits.length} saisi${digits.length > 1 ? 's' : ''}).`
  }
  return null
}

export default function SocieteSection({ accent, profile, form, set, uploading, dispatch }) {
  // L772 — bloc « Champs hérités (France) » (SIRET / TVA intra) replié par défaut.
  const [showLegacyFr, setShowLegacyFr] = useState(false)
  return (
    <>
      {/* NTDMO7 — réinitialisation des données de démo (sociétés démo seules). */}
      <DemoResetButton />
      {/* ── Carte d'aperçu en direct ── */}
      <div
        className="overflow-hidden rounded-xl border shadow-ui-sm"
        style={{ borderColor: `${accent}30` }}
      >
        <div
          className="flex flex-wrap items-center gap-4 border-b px-6 py-4"
          style={{
            background: `linear-gradient(135deg, ${accent}12 0%, ${accent}06 100%)`,
            borderColor: `${accent}20`,
          }}
        >
          {/* Logo ou initiale */}
          <div
            className="flex size-[52px] shrink-0 items-center justify-center overflow-hidden rounded-xl border"
            style={{ background: profile?.logo_url ? 'transparent' : `${accent}20`, borderColor: `${accent}30` }}
          >
            {mediaUrl(profile?.logo_url)
              ? <img src={mediaUrl(profile.logo_url)} alt="logo" className="size-full object-contain p-1" />
              : <span className="text-xl font-extrabold" style={{ color: accent }}>
                  {(form.nom || '?')[0].toUpperCase()}
                </span>
            }
          </div>

          <div className="min-w-0 flex-1">
            <h3 className="font-display text-[1.05rem] font-extrabold tracking-tight" style={{ color: accent }}>
              {form.nom || 'Nom de votre entreprise'}
            </h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {[form.adresse, form.email, form.telephone].filter(Boolean).join(' · ') || 'Adresse · Email · Téléphone'}
            </p>
          </div>

          {/* Aperçu de la couleur */}
          <div className="flex shrink-0 items-center gap-2">
            <div className="size-[22px] rounded-full" style={{ background: accent, boxShadow: `0 0 0 3px ${accent}30` }} />
            <span className="font-mono text-[11.5px] text-muted-foreground">{accent}</span>
          </div>

          <div
            className="rounded-full border px-2.5 py-1 text-[11px] font-semibold"
            style={{ background: `${accent}20`, borderColor: `${accent}30`, color: accent }}
          >
            Aperçu PDF
          </div>
        </div>
      </div>

      <div className="pe-main">
        {/* ─── Champs du formulaire ─── */}
        <div className="flex flex-col gap-[1.1rem]">

          {/* Identité */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Identité" icon={<><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></>}/>
              <div className="flex flex-col gap-3">
                <Field label="Nom de l'entreprise" required htmlFor="pe-nom">
                  <Input id="pe-nom" name="nom" value={form.nom} onChange={set} required placeholder="TAQINOR SARL"/>
                </Field>
                <Field label="Adresse" htmlFor="pe-adresse">
                  <Textarea id="pe-adresse" className="min-h-[68px] resize-y" name="adresse" value={form.adresse} onChange={set} placeholder="12 rue Mohammed V, Casablanca" rows={2}/>
                </Field>
              </div>
            </CardContent>
          </Card>

          {/* Coordonnées */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Coordonnées" icon={<><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.61 3.5 2 2 0 0 1 3.6 1.32h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9a16 16 0 0 0 6 6l1.27-.95a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></>}/>
              <div className="pe-grid-2">
                <Field label="Email" htmlFor="pe-email">
                  <Input id="pe-email" name="email" type="email" value={form.email} onChange={set} placeholder="contact@entreprise.ma"/>
                </Field>
                <Field label="Téléphone" htmlFor="pe-telephone">
                  <Input id="pe-telephone" name="telephone" value={form.telephone} onChange={set} placeholder="+212 6 XX XX XX XX"/>
                </Field>
              </div>
            </CardContent>
          </Card>

          {/* Légal — coordonnées bancaires (Maroc) + champs hérités France repliés */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Informations légales" icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>}/>
              <div className="pe-grid-2">
                <Field label="RIB / IBAN" htmlFor="pe-rib">
                  <Input id="pe-rib" name="rib" value={form.rib} onChange={set} placeholder="RIB 24 chiffres / IBAN"/>
                </Field>
                <Field label="Banque" htmlFor="pe-banque">
                  <Input id="pe-banque" name="banque" value={form.banque} onChange={set} placeholder="CIH, Attijariwafa…"/>
                </Field>
              </div>
              {/* L772 — SIRET & TVA intra (inutiles au Maroc) repliés par défaut. */}
              <button type="button"
                      onClick={() => setShowLegacyFr(v => !v)}
                      className="mt-3 flex items-center gap-1.5 text-[12px] font-medium text-muted-foreground hover:text-foreground">
                {showLegacyFr
                  ? <ChevronDown className="size-3.5" aria-hidden="true" />
                  : <ChevronRight className="size-3.5" aria-hidden="true" />}
                Champs hérités (France)
              </button>
              {showLegacyFr && (
                <div className="pe-grid-2 mt-2.5">
                  <Field label="SIRET" htmlFor="pe-siret">
                    <Input id="pe-siret" name="siret" value={form.siret} onChange={set} placeholder="14 chiffres"/>
                  </Field>
                  <Field label="N° TVA intracommunautaire" htmlFor="pe-tva-intra">
                    <Input id="pe-tva-intra" name="tva_intra" value={form.tva_intra} onChange={set} placeholder="FR12345678901"/>
                  </Field>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Paiement & conditions (factures) — Feature B */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Paiement & conditions (factures)" icon={<><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></>}/>
              <p className="mb-3.5 text-[11.5px] text-muted-foreground">
                Texte libre affiché sur vos factures, juste sous le RIB. Tant qu'un champ est vide, rien ne s'affiche : vos factures restent identiques jusqu'à ce que vous les renseigniez. (Ces blocs ne concernent que les factures, pas les devis premium.)
              </p>
              <div className="flex flex-col gap-3">
                <Field label="Instructions de paiement" htmlFor="pe-instructions-paiement">
                  <Textarea
                    id="pe-instructions-paiement" className="min-h-[68px] resize-y"
                    name="instructions_paiement" value={form.instructions_paiement} onChange={set}
                    placeholder="Ex : Acompte de 30 % à la commande, solde à la mise en service. Paiement par virement ou chèque."
                    rows={3}
                  />
                </Field>
                <Field label="Conditions générales" htmlFor="pe-conditions-generales">
                  <Textarea
                    id="pe-conditions-generales" className="min-h-[88px] resize-y"
                    name="conditions_generales" value={form.conditions_generales} onChange={set}
                    placeholder="Ex : Garantie 10 ans sur les panneaux, 5 ans onduleur. Réclamations sous 8 jours…"
                    rows={4}
                  />
                </Field>
              </div>
            </CardContent>
          </Card>

          {/* Identifiants légaux (Maroc) */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Identifiants légaux (Maroc)" icon={<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>}/>
              <p className="mb-2.5 text-[11.5px] text-muted-foreground">
                L'ICE, l'IF et le RC apparaissent en pied de page de vos factures.
              </p>
              {/* L771 — ICE obligatoire pour la facturation : bannière non bloquante. */}
              {!String(form.ice || '').trim() && (
                <div className="mb-3.5 flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
                  <p className="text-[11.5px] leading-relaxed text-warning">
                    L'ICE est <strong>obligatoire au Maroc</strong> sur les
                    factures. Renseignez-le pour des factures conformes (vous
                    pouvez tout de même enregistrer sans).
                  </p>
                </div>
              )}
              <div className="pe-grid-2">
                <Field label="ICE" required htmlFor="pe-ice">
                  <Input id="pe-ice" name="ice" value={form.ice} onChange={set} placeholder="000000000000000"/>
                  {idHint('ice', form.ice) && (
                    <p className="text-[11px] text-muted-foreground">{idHint('ice', form.ice)}</p>
                  )}
                </Field>
                <Field label="IF (Identifiant Fiscal)" htmlFor="pe-if">
                  <Input id="pe-if" name="identifiant_fiscal" value={form.identifiant_fiscal} onChange={set} placeholder="00000000"/>
                  {idHint('identifiant_fiscal', form.identifiant_fiscal) && (
                    <p className="text-[11px] text-muted-foreground">{idHint('identifiant_fiscal', form.identifiant_fiscal)}</p>
                  )}
                </Field>
                <Field label="RC (Registre de Commerce)" htmlFor="pe-rc">
                  <Input id="pe-rc" name="rc" value={form.rc} onChange={set} placeholder="N° RC"/>
                </Field>
                <Field label="Patente / Taxe professionnelle" htmlFor="pe-patente">
                  <Input id="pe-patente" name="patente" value={form.patente} onChange={set} placeholder="00000000"/>
                  {idHint('patente', form.patente) && (
                    <p className="text-[11px] text-muted-foreground">{idHint('patente', form.patente)}</p>
                  )}
                </Field>
                <Field label="CNSS" htmlFor="pe-cnss">
                  <Input id="pe-cnss" name="cnss" value={form.cnss} onChange={set} placeholder="N° affiliation CNSS"/>
                  {idHint('cnss', form.cnss) && (
                    <p className="text-[11px] text-muted-foreground">{idHint('cnss', form.cnss)}</p>
                  )}
                </Field>
              </div>
            </CardContent>
          </Card>

          {/* Couleur PDF */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Apparence PDF" icon={<><circle cx="12" cy="12" r="10"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></>}/>
              <Field label="Couleur principale" htmlFor="pe-couleur-hex">
                <div className="flex items-center gap-2.5">
                  <input
                    type="color" name="couleur_principale" value={form.couleur_principale} onChange={set}
                    aria-label="Sélecteur de couleur principale"
                    className="size-[42px] w-[46px] shrink-0 cursor-pointer rounded-md border border-input bg-card p-[3px]"
                  />
                  <Input
                    id="pe-couleur-hex" className="w-[130px] font-mono"
                    name="couleur_principale" value={form.couleur_principale} onChange={set}
                    placeholder="#1d4ed8"
                  />
                  <div
                    className="flex h-[42px] flex-1 items-center justify-center rounded-md border"
                    style={{ background: `linear-gradient(135deg, ${accent}, ${accent}99)`, borderColor: `${accent}40` }}
                  >
                    <span className="text-[11.5px] font-semibold text-white drop-shadow">Aperçu</span>
                  </div>
                </div>
              </Field>
            </CardContent>
          </Card>
        </div>

        {/* ─── Médias ─── */}
        <div className="flex flex-col gap-[1.1rem]">

          {/* Logo */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Logo de l'entreprise" icon={<><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></>}/>
              <UploadZone
                label="Affiché en en-tête du PDF"
                hint="PNG, JPEG, WebP — max 2 Mo"
                currentUrl={profile?.logo_url}
                onUpload={f => dispatch(uploadLogo(f))}
                onDelete={() => dispatch(deleteLogo())}
                uploading={uploading}
              />
            </CardContent>
          </Card>

          {/* Signature */}
          <Card>
            <CardContent className="pt-4 sm:pt-5">
              <SectionTitle label="Signature électronique" icon={<><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></>}/>
              <UploadZone
                label="Apposée en bas du PDF"
                hint="PNG, JPEG, WebP — max 2 Mo"
                currentUrl={profile?.signature_url}
                onUpload={f => dispatch(uploadSignature(f))}
                onDelete={() => dispatch(deleteSignature())}
                uploading={uploading}
              />
            </CardContent>
          </Card>

          {/* Info PDF */}
          <div
            className="flex items-start gap-2.5 rounded-xl border p-3.5"
            style={{ background: `linear-gradient(135deg, ${accent}08, ${accent}14)`, borderColor: `${accent}25` }}
          >
            <Ic size={16} color={accent} sw={1.8}>
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </Ic>
            <p className="text-[12.5px] leading-relaxed" style={{ color: accent }}>
              <strong>Aperçu PDF :</strong> le logo, la signature et les informations ci-contre apparaissent automatiquement dans l'en-tête et le pied de page de tous vos devis et factures.
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
