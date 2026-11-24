import { useEffect, useState } from 'react'
import { FileText } from 'lucide-react'
import parametresApi from '../../../api/parametresApi.js'
import {
  Button,
  RadioGroup, RadioGroupItem, Checkbox, Label, Input,
} from '../../../ui/index.js'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { libelleFormatComplet } from './devisListHelpers.js'

// ── ARC49 — Modale de génération PDF de la LISTE (formats du simulateur). ──
// Extraite telle quelle de DevisList (« lignes divisées ») : mêmes contrôles,
// mêmes libellés, MÊMES options envoyées à `generer-pdf`/`clean_pdf_options`
// (règle #4 — la migration ne touche QUE le découpage du rendu, jamais le flux
// PDF). Toute la logique de valeur reste dans `buildPdfOptions` côté parent.
/* T4-U1-009 — le « Devis final (paiement + RIB) » d'une société IDENTIFIÉE sans RIB ni banque sort sans RIB, en
   silence (`quote_engine/identite.py::ligne_rib` rend "" ; un profil entièrement vide garde, lui, la ligne historique).
   L'écran le dit AVANT de générer, en interne ; le PDF n'est jamais touché (règle #4). Champs lus sur le profil servi
   (GET /parametres/, toute personne connectée) — les mêmes que `CHAMPS_IDENTITE`. */
const IDENTITE_SOCIETE = ['nom', 'adresse', 'email', 'telephone', 'ice', 'rc', 'identifiant_fiscal', 'patente']
const rempli = (v) => typeof v === 'string' && v.trim() !== ''
function ribSocieteManquant(profil) {
  if (!profil || typeof profil !== 'object' || Array.isArray(profil)) return false
  return !rempli(profil.rib) && !rempli(profil.banque) && IDENTITE_SOCIETE.some((k) => rempli(profil[k]))
}

export default function DevisPdfDialog({
  pdfTarget, batchPdf, selectedIds,
  pdfMode, setPdfMode, pdfModeAutoOnepage, targetIsAgricole,
  showMonthly, setShowMonthly,
  targetHasEtude, targetIsCi, targetMode, includeEtude, setIncludeEtude,
  includeCalepinage, setIncludeCalepinage,
  includeNoteCalcul, setIncludeNoteCalcul,
  devisFinal, setDevisFinal,
  paymentMode, setPaymentMode,
  customAcompte, setCustomAcompte,
  onClose, onGenererLot, onGenererUn,
}) {
  const ouvert = !!pdfTarget || batchPdf
  const [profil, setProfil] = useState(null)
  useEffect(() => {
    if (!ouvert || !devisFinal) return undefined
    let vivant = true
    Promise.resolve(parametresApi.getProfile())
      .then((r) => { if (vivant) setProfil(r?.data ?? null) })
      .catch(() => {})
    return () => { vivant = false }
  }, [ouvert, devisFinal])
  const ribManquant = devisFinal && !targetIsCi && !targetIsAgricole && ribSocieteManquant(profil)
  return (
    <ResponsiveDialog
      open={ouvert}
      onOpenChange={(o) => { if (!o) onClose() }}
      title={batchPdf
        ? `Générer le PDF — ${selectedIds.length} devis (format partagé)`
        : `Générer le PDF — ${pdfTarget?.reference}`}
      footer={(
        <>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button onClick={() => (batchPdf ? onGenererLot() : onGenererUn(pdfTarget))}>
            <FileText /> Générer
          </Button>
        </>
      )}
    >
        <div className="flex flex-col gap-4">
          <div className="grid gap-2">
            <Label>Format</Label>
            <RadioGroup value={pdfMode} onValueChange={setPdfMode} className="flex flex-col gap-2">
              <label className="flex items-start gap-2 text-sm">
                <RadioGroupItem value="full" className="mt-0.5" />
                <span>
                  {libelleFormatComplet({ targetIsAgricole, targetMode })}
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm">
                <RadioGroupItem value="onepage" className="mt-0.5" />
                <span>
                  {targetIsAgricole
                    ? 'Version courte (1 page)'
                    : 'Devis une page (liste produits uniquement, sans graphiques)'}
                </span>
              </label>
            </RadioGroup>
            {/* Incident fondateur 01/09 round 2 — hint SEUL (jamais bloquant) :
                le format une page a été présélectionné parce qu'aucune ligne
                de ce devis ne classe d'onduleur (devis « Composition libre »
                ou accessoires/main-d'œuvre). Disparaît dès que l'utilisateur
                choisit lui-même 'full' (règle : jamais un message qui ne
                correspond plus au choix affiché). */}
            {pdfModeAutoOnepage && pdfMode === 'onepage' && !batchPdf && (
              <p className="text-xs text-muted-foreground">
                Options non détectées — format une page présélectionné (aucun onduleur sur ce devis).
              </p>
            )}
          </div>

          {pdfMode === 'full' && !targetIsAgricole && !targetIsCi && (
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={showMonthly} onCheckedChange={v => setShowMonthly(!!v)} className="mt-0.5" />
              <span>Économies mensuelles <span className="text-muted-foreground">(graphique mensuel page 2)</span></span>
            </label>
          )}

          {pdfMode === 'full' && !batchPdf && !targetIsAgricole && !targetIsCi && (
            <label className="flex items-start gap-2 text-sm aria-disabled:opacity-50" aria-disabled={!targetHasEtude}>
              {/* T13 — case désactivée sans données d'étude (note explicative). */}
              <Checkbox
                checked={includeEtude && targetHasEtude}
                disabled={!targetHasEtude}
                onCheckedChange={v => setIncludeEtude(!!v)}
                className="mt-0.5"
              />
              <span>
                Inclure l'étude <span className="text-muted-foreground">(une page d'étude en plus)</span>
                {!targetHasEtude && (
                  <span className="block text-xs text-muted-foreground">
                    Aucune donnée d'étude sur ce devis — option indisponible.
                  </span>
                )}
              </span>
            </label>
          )}

          {/* CAL184 — page « Calepinage » (planche cotée). TRI-ÉTAT : l'écran
              n'invente aucune valeur par défaut, parce qu'il ne sait pas si ce
              devis porte un calepinage dessinable — le serveur, lui, le sait.
              « Automatique » lui laisse la main ; « Oui »/« Non » tranchent et
              priment sur l'auto (whitelist `include_calepinage`, CAL183).
              T4-U3-009 — jamais proposé pour un devis AGRICOLE : son document
              de 3 pages n'a pas de page calepinage (CLAUDE.md « Quote PDFs »,
              builder.py : `include_calepinage` sans effet). L'étude suit la même
              règle plus haut (sans effet en commercial / industriel / agricole). */}
          {pdfMode === 'full' && !targetIsAgricole && (
            <div className="grid gap-2" data-testid="cal184-calepinage">
              <Label>Calepinage</Label>
              <RadioGroup
                value={includeCalepinage}
                onValueChange={setIncludeCalepinage}
                className="flex flex-col gap-2"
              >
                <label className="flex items-start gap-2 text-sm">
                  <RadioGroupItem value="auto" className="mt-0.5" />
                  <span>
                    Automatique
                    <span className="text-muted-foreground"> (page ajoutée si ce devis porte un calepinage)</span>
                  </span>
                </label>
                <label className="flex items-start gap-2 text-sm">
                  <RadioGroupItem value="oui" className="mt-0.5" />
                  <span>Inclure la planche cotée</span>
                </label>
                <label className="flex items-start gap-2 text-sm">
                  <RadioGroupItem value="non" className="mt-0.5" />
                  <span>Ne pas inclure</span>
                </label>
              </RadioGroup>
            </div>
          )}

          {/* AMOT68 — annexe « Note de calcul » (AGR319) : la pièce du dossier
              FDA, demandable depuis l'écran (+1 page, agricole seul). */}
          {pdfMode === 'full' && !batchPdf && targetIsAgricole && setIncludeNoteCalcul && (
            <label className="flex items-start gap-2 text-sm">
              <Checkbox
                checked={!!includeNoteCalcul}
                onCheckedChange={v => setIncludeNoteCalcul(!!v)}
                className="mt-0.5"
                aria-label="Joindre la note de calcul"
              />
              <span>
                Joindre la note de calcul <span className="text-muted-foreground">(annexe technique — une page en plus)</span>
              </span>
            </label>
          )}

          <label className="flex items-start gap-2 text-sm">
            <Checkbox checked={devisFinal} onCheckedChange={v => setDevisFinal(!!v)} className="mt-0.5" />
            <span>Devis Final <span className="text-muted-foreground">{batchPdf ? '(ajoute modalités de paiement + RIB)'
              : targetIsCi ? '(visite faite — retire la mention « Devis préliminaire »)'
                : targetIsAgricole ? '(visite faite — retire « à confirmer par la visite »)'
                  : '(ajoute modalités de paiement + RIB)'}</span></span>
          </label>

          {ribManquant && (
            <p role="status" className="text-xs text-warning" data-testid="pdf-rib-manquant">
              Le RIB de la société n’est pas renseigné : le devis final sortira sans RIB —{' '}
              <a href="/parametres" className="underline">Paramètres → Société</a>
            </p>
          )}

          {devisFinal && (
            <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3">
              <RadioGroup value={paymentMode} onValueChange={setPaymentMode} className="flex flex-col gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <RadioGroupItem value="standard" />
                  <span>Échéancier du devis</span>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <RadioGroupItem value="custom" />
                  <span>Acompte personnalisé <span className="text-muted-foreground">(enregistré dans l'échéancier du devis)</span></span>
                </label>
              </RadioGroup>
              {paymentMode === 'custom' && (
                <div className="grid gap-1.5">
                  <Label htmlFor="pdf-acompte">Montant acompte (MAD)</Label>
                  <Input id="pdf-acompte" type="number" min="0" step="any"
                         value={customAcompte} onChange={e => setCustomAcompte(e.target.value)} />
                </div>
              )}
            </div>
          )}
        </div>
    </ResponsiveDialog>
  )
}
