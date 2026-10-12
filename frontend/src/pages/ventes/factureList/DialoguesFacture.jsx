// VNT102 — dialogues de la liste des factures (marquage sec « payée », paiement,
// aperçu PDF, note de débit, paiement en ligne, avoir, abandon du solde, retour
// client, consolidation, encaissement groupé, aperçu WhatsApp), déplacés tels quels
// (move only) depuis FactureList.jsx. Le dialogue d'annulation n'y est plus monté :
// l'annulation vit dans FactureRow (VNT46, `AnnulationFactureDialog`).
import { MessageCircle } from 'lucide-react'
import { fetchFactures, marquerPayeeFacture } from '../../../features/ventes/store/ventesSlice'
import {
  Button, Input, Checkbox, Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  FormField, FormActions, Select, SelectTrigger, SelectValue, SelectContent, SelectItem, toast,
} from '../../../ui'
import { formatMAD, toNumber } from '../../../lib/format'
import { ConfirmDialog } from '../../../ui/ConfirmDialog'
import PdfPreviewSheet from '../../../features/ventes/PdfPreviewSheet'
import PaiementEnLigneDialog from '../../../features/ventes/PaiementEnLigneDialog'
import PaiementDialog from '../PaiementDialog'
import NoteDebitDialog from '../NoteDebitDialog'

// ATOT36 — types d'avoir choisis à l'émission (contrat `avoir.json`) ; le
// « retour » est posé par l'action retour-client, jamais ici.
const TYPES_AVOIR = [
  ['geste_commercial', 'Geste commercial (réduit le dû de cette facture)'],
  ['correction', 'Correction d’erreur (le montant reste dû : remis au solde de l’échéancier)'],
]

export default function DialoguesFacture({ g, d, l, factures, dispatch, setDernierEncaissement }) {
  const {
    noteDebitTarget, setNoteDebitTarget, paiementEnLigneTarget, setPaiementEnLigneTarget,
    wir183Busy, MOTIFS_ABANDON, abandonTarget, setAbandonTarget, abandonMotif, setAbandonMotif,
    handleAbandonnerSolde, retourTarget, setRetourTarget, retourMotif, setRetourMotif,
    retourRestocker, setRetourRestocker, retourQtes, setRetourQtes, lignesRetournables,
    handleRetourClient, consoliderOpen, setConsoliderOpen, consoliderDevis, consoliderSel,
    setConsoliderSel, handleConsolider, avoirTarget, setAvoirTarget, avoirMotif, setAvoirMotif,
    avoirSaving, avoirQtes, setAvoirQtes, avoirType, setAvoirType, handleCreerAvoir,
    payTarget, setPayTarget, doAction, payeeSecheTarget, setPayeeSecheTarget,
    payeeSecheMotif, setPayeeSecheMotif,
  } = g
  const {
    previewFacture, setPreviewFacture, fetchFacturePreviewBlob, waLangue, waPreview,
    setWaPreview, ouvrirWhatsApp,
  } = d
  const {
    facturesEncaissables, facturesEcartees, encaissementOpen, setEncaissementOpen,
    encaissementForm, setEncaissementForm, encaissementRepartition, setEncaissementRepartition,
    handleEncaissementGroupe,
  } = l
  return (
    <>
      {/* EZ13 — le marquage sec explique CE QU'ON PERD, et offre le chemin
          riche en échappatoire (« Encaisser » capture mode/date/référence). */}
      <ConfirmDialog
        open={!!payeeSecheTarget}
        onOpenChange={(o) => { if (!o) { setPayeeSecheTarget(null); setPayeeSecheMotif('') } }}
        severity="medium"
        title={`Marquer ${payeeSecheTarget?.reference ?? ''} payée sans détail ?`}
        description="Le MODE de règlement, la DATE et la RÉFÉRENCE ne seront pas enregistrés : la facture passera à « payée » sans trace d'encaissement. Préférez « Encaisser » si vous avez ces informations."
        confirmLabel="Marquer payée quand même"
        onConfirm={() => {
          const f = payeeSecheTarget
          const motif = payeeSecheMotif.trim()
          setPayeeSecheTarget(null)
          setPayeeSecheMotif('')
          if (!motif) {
            toast.error('Motif obligatoire : dites pourquoi cette facture est soldée sans encaissement.')
            return
          }
          if (f) doAction(marquerPayeeFacture, { id: f.id, motif })
        }}
      >
        {/* AUD124 — sans motif, ce geste faisait disparaître une créance de
            la balance âgée sans que rien ne dise qui, quand ni pourquoi. */}
        <FormField label="Motif (obligatoire)" htmlFor="motif-payee-seche">
          <Input
            id="motif-payee-seche"
            value={payeeSecheMotif}
            onChange={(e) => setPayeeSecheMotif(e.target.value)}
            placeholder="Ex. : virement encaissé hors ERP, constaté au relevé"
          />
        </FormField>
      </ConfirmDialog>

      {/* ── Modale d'enregistrement de paiement (VX230 — composant partagé) ── */}
      <PaiementDialog
        facture={payTarget}
        onOpenChange={(o) => { if (!o) setPayTarget(null) }}
        onSaved={() => { dispatch(fetchFactures()); setDernierEncaissement(payTarget) }}
      />

      {/* APX14 — aperçu du PDF de la facture, INLINE. Source = le PDF LEGACY
          propre aux factures ; le moteur `/proposal` reste réservé au PDF de
          DEVIS (règle #4), et aucun chemin nouveau n'est créé. */}
      <PdfPreviewSheet
        open={!!previewFacture}
        onOpenChange={(o) => { if (!o) setPreviewFacture(null) }}
        title={`Aperçu — ${previewFacture?.reference ?? ''}`}
        description="Facture. Téléchargeable ou ouvrable dans un onglet."
        filename={previewFacture ? `${previewFacture.reference}.pdf` : undefined}
        fetchBlob={fetchFacturePreviewBlob}
      />

      {/* ── WIR103/ZFAC4 — Modale « Note de débit » (création + PDF) ── */}
      <NoteDebitDialog
        facture={noteDebitTarget
          ? (factures.find(x => x.id === noteDebitTarget.id) ?? noteDebitTarget)
          : null}
        onChanged={() => dispatch(fetchFactures())}
        open={!!noteDebitTarget}
        onOpenChange={(o) => { if (!o) setNoteDebitTarget(null) }}
      />

      {/* ── PACT121 — Modale « Payer en ligne » (core.PaymentTransaction) ── */}
      <PaiementEnLigneDialog
        facture={paiementEnLigneTarget}
        open={!!paiementEnLigneTarget}
        onOpenChange={(o) => { if (!o) setPaiementEnLigneTarget(null) }}
      />

      {/* ── Modale d'avoir (total ou partiel par ligne) ── */}
      <Dialog open={!!avoirTarget} onOpenChange={(o) => { if (!o) setAvoirTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer un avoir — {avoirTarget?.reference}</DialogTitle>
            <DialogDescription>
              Avoir total (toute la facture) ou partiel (quantités à créditer par ligne).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <FormField label="Motif (optionnel)" htmlFor="avoir-motif" fullWidth>
              <Input id="avoir-motif" type="text" value={avoirMotif}
                     onChange={e => setAvoirMotif(e.target.value)} />
            </FormField>
            <fieldset className="grid gap-1" data-testid="avoir-type">
              <legend className="text-sm font-medium">Type d’avoir</legend>
              {TYPES_AVOIR.map(([value, label]) => (
                <label key={value} className="flex items-center gap-2 text-sm">
                  <input type="radio" name="avoir-type" value={value}
                         checked={avoirType === value}
                         onChange={() => setAvoirType(value)} />
                  {label}
                </label>
              ))}
            </fieldset>
            {(avoirTarget?.lignes?.length ?? 0) > 0 && (
              <div className="overflow-x-auto">
                <table className="data-table text-sm">
                  <thead>
                    <tr>
                      <th>Désignation</th>
                      <th className="ta-right">Qté facturée</th>
                      <th className="ta-right">Qté à créditer</th>
                    </tr>
                  </thead>
                  <tbody>
                    {avoirTarget.lignes.map(l => (
                      <tr key={l.id}>
                        <td data-label="Désignation">{l.designation}</td>
                        <td className="ta-right tabular-nums" data-label="Qté facturée">{l.quantite}</td>
                        <td className="ta-right" data-label="Qté à créditer">
                          <Input
                            type="number" min="0" step="any"
                            className="w-24"
                            value={avoirQtes[l.id] ?? ''}
                            max={l.quantite}
                            onChange={e => setAvoirQtes(q => ({ ...q, [l.id]: e.target.value }))}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setAvoirTarget(null)}>Annuler</Button>
            {(avoirTarget?.lignes?.length ?? 0) > 0 && (
              <Button type="button" variant="outline" loading={avoirSaving}
                      onClick={() => handleCreerAvoir('partiel')}>
                Avoir partiel
              </Button>
            )}
            <Button type="button" loading={avoirSaving}
                    onClick={() => handleCreerAvoir('total')}>
              Avoir total
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {/* ══ WIR183/XFAC13 — Abandon du solde (motif OBLIGATOIRE serveur) ══ */}
      <Dialog open={!!abandonTarget} onOpenChange={(o) => { if (!o) setAbandonTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Abandonner le solde — {abandonTarget?.reference}</DialogTitle>
            <DialogDescription>
              Le résiduel est soldé (écriture d’abandon) et la facture sort des
              impayés et de la balance âgée. Le motif est obligatoire.
            </DialogDescription>
          </DialogHeader>
          <FormField label="Motif d’abandon" htmlFor="abandon-motif" fullWidth>
            <Select value={abandonMotif} onValueChange={setAbandonMotif}>
              <SelectTrigger id="abandon-motif" aria-label="Motif d’abandon">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MOTIFS_ABANDON.map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setAbandonTarget(null)}>
              Annuler
            </Button>
            <Button type="button" variant="destructive" loading={wir183Busy}
                    onClick={handleAbandonnerSolde}>
              Abandonner le solde
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {/* ══ WIR183/XPOS7 — Retour client (avoir + re-stockage optionnel) ══ */}
      <Dialog open={!!retourTarget} onOpenChange={(o) => { if (!o) setRetourTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Retour client — {retourTarget?.reference}</DialogTitle>
            <DialogDescription>
              Un avoir est créé contre cette facture pour les quantités
              retournées. Seules les lignes portant un produit sont
              retournables (le re-stockage s’appuie dessus).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <FormField label="Motif du retour (obligatoire)" htmlFor="retour-motif" fullWidth>
              <Input id="retour-motif" type="text" value={retourMotif}
                     onChange={e => setRetourMotif(e.target.value)} />
            </FormField>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={retourRestocker}
                        onCheckedChange={(v) => setRetourRestocker(!!v)}
                        aria-label="Remettre en stock" />
              Remettre les articles retournés en stock
            </label>
            {lignesRetournables.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucune ligne de cette facture ne porte de produit : aucun retour
                n’est possible ici (utilisez un avoir).
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table text-sm">
                  <thead>
                    <tr>
                      <th>Désignation</th>
                      <th className="ta-right">Qté facturée</th>
                      <th className="ta-right">Qté retournée</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lignesRetournables.map(l => (
                      <tr key={l.id}>
                        <td data-label="Désignation">{l.designation}</td>
                        <td className="ta-right tabular-nums" data-label="Qté facturée">{l.quantite}</td>
                        <td className="ta-right" data-label="Qté retournée">
                          <Input
                            type="number" min="0" step="any" className="w-24"
                            max={l.quantite}
                            value={retourQtes[l.id] ?? ''}
                            onChange={e => setRetourQtes(q => ({ ...q, [l.id]: e.target.value }))}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setRetourTarget(null)}>
              Annuler
            </Button>
            <Button type="button" loading={wir183Busy}
                    disabled={!retourMotif.trim() || lignesRetournables.length === 0}
                    onClick={handleRetourClient}>
              Enregistrer le retour
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {/* ══ WIR183/XFAC11 — Consolider plusieurs devis acceptés en UNE facture ══ */}
      <Dialog open={consoliderOpen} onOpenChange={setConsoliderOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Consolider des devis</DialogTitle>
            <DialogDescription>
              Une seule facture est créée à partir de plusieurs devis ACCEPTÉS
              du MÊME client. Le serveur refuse un mélange de clients.
            </DialogDescription>
          </DialogHeader>
          {consoliderDevis.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun devis accepté disponible.</p>
          ) : (
            <div className="max-h-72 overflow-y-auto">
              <table className="data-table text-sm">
                <thead>
                  <tr>
                    <th aria-label="Sélection" />
                    <th>Référence</th>
                    <th>Client</th>
                    <th className="ta-right">Total TTC</th>
                  </tr>
                </thead>
                <tbody>
                  {consoliderDevis.map(d => (
                    <tr key={d.id}>
                      <td>
                        <Checkbox
                          checked={consoliderSel.includes(d.id)}
                          aria-label={`Sélectionner le devis ${d.reference}`}
                          onCheckedChange={(v) => setConsoliderSel(sel => (
                            v ? [...sel, d.id] : sel.filter(x => x !== d.id)))}
                        />
                      </td>
                      <td data-label="Référence">{d.reference}</td>
                      <td data-label="Client">{d.client_nom ?? d.client}</td>
                      <td className="ta-right tabular-nums" data-label="Total TTC">
                        {formatMAD(toNumber(d.total_ttc ?? 0))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setConsoliderOpen(false)}>
              Annuler
            </Button>
            <Button type="button" loading={wir183Busy}
                    disabled={consoliderSel.length < 2}
                    onClick={handleConsolider}>
              Consolider ({consoliderSel.length})
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {/* ══ WIR183/ZFAC6 — Encaissement groupé (FIFO, ou répartition forcée) ══ */}
      <Dialog open={encaissementOpen} onOpenChange={setEncaissementOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Encaissement groupé</DialogTitle>
            <DialogDescription>
              Un seul règlement réparti sur les {facturesEncaissables.length} facture(s)
              encaissables, de la plus ancienne échéance à la plus récente.
              {facturesEcartees.length > 0 && (
                <> Écartée(s) car non encaissable(s) : {facturesEcartees.map(f => f.reference).join(', ')}.</>
              )}
              Renseignez la répartition ci-dessous pour la forcer.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField label="Montant reçu (MAD)" htmlFor="eg-montant" fullWidth>
                <Input id="eg-montant" type="number" step="any"
                       value={encaissementForm.montant}
                       onChange={e => setEncaissementForm(f => ({ ...f, montant: e.target.value }))} />
              </FormField>
              <FormField label="Date" htmlFor="eg-date" fullWidth>
                <Input id="eg-date" type="date" value={encaissementForm.date}
                       onChange={e => setEncaissementForm(f => ({ ...f, date: e.target.value }))} />
              </FormField>
              <FormField label="Mode" htmlFor="eg-mode" fullWidth>
                <Select value={encaissementForm.mode}
                        onValueChange={v => setEncaissementForm(f => ({ ...f, mode: v }))}>
                  <SelectTrigger id="eg-mode" aria-label="Mode"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="virement">Virement</SelectItem>
                    <SelectItem value="cheque">Chèque</SelectItem>
                    <SelectItem value="especes">Espèces</SelectItem>
                    <SelectItem value="carte">Carte</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
              <FormField label="Référence" htmlFor="eg-reference" fullWidth>
                <Input id="eg-reference" type="text" value={encaissementForm.reference}
                       onChange={e => setEncaissementForm(f => ({ ...f, reference: e.target.value }))} />
              </FormField>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table text-sm">
                <thead>
                  <tr>
                    <th>Facture</th>
                    <th className="ta-right">Reste dû</th>
                    <th className="ta-right">Montant affecté</th>
                  </tr>
                </thead>
                <tbody>
                  {facturesEncaissables.map(f => (
                    <tr key={f.id}>
                      <td data-label="Facture">{f.reference}</td>
                      <td className="ta-right tabular-nums" data-label="Reste dû">
                        {formatMAD(toNumber(f.montant_du ?? 0))}
                      </td>
                      <td className="ta-right" data-label="Montant affecté">
                        <Input
                          type="number" min="0" step="any" className="w-28"
                          aria-label={`Montant affecté à ${f.reference}`}
                          value={encaissementRepartition[f.id] ?? ''}
                          onChange={e => setEncaissementRepartition(r => ({ ...r, [f.id]: e.target.value }))}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setEncaissementOpen(false)}>
              Annuler
            </Button>
            <Button type="button" loading={wir183Busy}
                    disabled={toNumber(encaissementForm.montant) <= 0}
                    onClick={handleEncaissementGroupe}>
              Encaisser
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>

      {/* ── L852 — Aperçu du message WhatsApp avant ouverture de wa.me ── */}
      <Dialog open={!!waPreview} onOpenChange={(o) => { if (!o) setWaPreview(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aperçu du message WhatsApp — {waPreview?.reference}</DialogTitle>
            <DialogDescription>
              {waLangue === 'darija' ? 'Variante Darija' : 'Variante Français'}
              {' '}— vérifiez le texte et le lien, puis ouvrez WhatsApp.
            </DialogDescription>
          </DialogHeader>
          <pre className="m-0 whitespace-pre-wrap break-words rounded-lg bg-muted p-3 text-sm"
               style={{ fontFamily: 'inherit' }}>
            {waPreview?.message}
          </pre>
          {waPreview?.url && (
            <p className="mt-2 break-words text-xs text-muted-foreground">
              Lien public : {waPreview.url}
            </p>
          )}
          <FormActions sticky={false}>
            <Button type="button" variant="ghost" onClick={() => setWaPreview(null)}>Annuler</Button>
            <Button type="button" variant="success" disabled={!waPreview?.wa_url}
                    onClick={ouvrirWhatsApp}>
              <MessageCircle /> Ouvrir WhatsApp
            </Button>
          </FormActions>
        </DialogContent>
      </Dialog>
    </>
  )
}
