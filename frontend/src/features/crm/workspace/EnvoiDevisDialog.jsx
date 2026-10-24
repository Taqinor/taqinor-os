import { useState } from 'react'
import { Check, ExternalLink, Eye, Layers3, Link2, Mail, MessageCircle } from 'lucide-react'
import {
  Button, Checkbox, Segmented,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../../ui'
// LANE E (fondateur 28/08/2026, spec_3_options.md) — réutilise TEL QUEL l'écran
// vendeur existant des tailles Éco/Recommandé/Max comme point d'entrée « Modifier
// les options » du dialogue d'envoi — rien n'est réinventé.
import DevisOffresTailles from '../../../pages/ventes/DevisOffresTailles'
import { formatDate } from '../../../lib/format'
import { SECTIONS_ENVOI, optionsCountFromTailles } from './devisTabLogique'
import { optionsTaillesOffertes } from './useEnvoiDevis'

/* ALEA52 — UNE SEULE boîte « Envoyer au client », partagée par la carte devis
   de l'onglet Devis (DevisTab) ET par l'aperçu du panneau devis de la fiche lead
   (LeadDevisPanel). Avant : quatre interfaces d'envoi, dont aucune dans l'aperçu
   (l'ouvrier fermait le PDF pour retrouver la carte). Le commercial choisit un
   CANAL — WhatsApp, e-mail, copier le lien —, les réglages de la page client
   (niveau, code de lecture, sections, options Éco/Max) vivent sous « Avancé ».
   L'état et les gestes (useEnvoiDevis.js) sont ceux de DevisTab, déplacés tels
   quels : seul le regroupement par canal est nouveau. */

// ── Les trois CANAUX : WhatsApp, e-mail, copier le lien ─────────────────────
function CanauxEnvoi({ devis: d, envoi }) {
  const { linkBusy, leadPhoneOk, leadEmail } = envoi
  return (
    <div className="lw-context-devis-links">
      <Button
        type="button" size="sm" variant="outline"
        disabled={!leadPhoneOk || linkBusy === `w-${d.id}`}
        title={leadPhoneOk
          ? 'Envoyer le lien de la page client par WhatsApp'
          : 'Aucun numéro de téléphone exploitable'}
        onClick={() => envoi.envoyerWhatsAppUnique(d)}
      >
        <MessageCircle size={14} aria-hidden="true" /> WhatsApp
      </Button>
      <Button
        type="button" size="sm" variant="outline"
        disabled={!leadEmail || linkBusy === `e-${d.id}`}
        title={leadEmail
          ? `Envoyer la proposition (PDF + lien) à ${leadEmail}`
          : 'Aucune adresse e-mail sur la fiche'}
        onClick={() => envoi.envoyerEmail(d)}
      >
        <Mail size={14} aria-hidden="true" /> E-mail
      </Button>
      <Button
        type="button" size="sm" variant="outline"
        disabled={linkBusy === `l-${d.id}`}
        title="Copier le lien de la page client (page devis web publique)"
        onClick={() => envoi.copierPageClient(d)}
      >
        {envoi.copiedId === d.id
          ? <Check size={14} aria-hidden="true" />
          : <Link2 size={14} aria-hidden="true" />}
        {envoi.copiedId === d.id ? 'Copié' : 'Copier le lien'}
      </Button>
      <Button
        type="button" size="sm" variant="ghost"
        disabled={linkBusy === `o-${d.id}`}
        aria-label={`Ouvrir la page client de ${d.reference} dans un nouvel onglet`}
        title="Ouvrir la VRAIE page client (compte comme une lecture côté suivi — pour regarder sans notifier, utilisez l'aperçu interne ci-dessous)"
        onClick={() => envoi.ouvrirPageClient(d)}
      >
        <ExternalLink size={14} aria-hidden="true" />
      </Button>
    </div>
  )
}

// ALEA55 — « Proposer une relance J+3 » : posée APRÈS l'envoi, via l'API de
// relance existante (la date de relance du lead) ; jamais sur une relance déjà là.
function RelanceJ3({ relance }) {
  if (relance.posee) {
    return <p className="gen-hint" role="status">Relance planifiée le {formatDate(relance.posee)}.</p>
  }
  if (relance.actuelle) {
    return <p className="gen-hint">Relance déjà planifiée le {formatDate(relance.actuelle)} — conservée.</p>
  }
  if (!relance.proposable) return null
  return (
    <label className="lw-context-devis-section" data-testid="envoi-relance-j3">
      <Checkbox
        checked={relance.cochee}
        onCheckedChange={(v) => relance.setCochee(v === true)}
        aria-label="Proposer une relance J+3"
      />
      Proposer une relance J+3 (le {formatDate(relance.date)})
    </label>
  )
}

// L-NIV-UI — niveau de la page client (contrat L-NIV) + code de lecture (OTP).
function ReglagesNiveau({ devis: d, envoi }) {
  const occupe = envoi.linkBusy === `n-${d.id}`
  return (
    <>
      <div className="lw-context-devis-niveau">
        <label className="lw-context-devis-niveau-select">
          <select
            value={envoi.getNiveau(d)}
            disabled={occupe}
            aria-label={`Niveau de la page client de ${d.reference}`}
            onChange={(e) => envoi.onNiveauChange(d, e.target.value)}
          >
            <option value="standard">Client standard</option>
            <option value="confiance">Client de confiance</option>
          </select>
        </label>
        <label className="lw-context-devis-otp">
          <Checkbox
            checked={envoi.getOtp(d)}
            disabled={occupe}
            onCheckedChange={(v) => envoi.onOtpChange(d, !!v)}
            aria-label={`Exiger un code de lecture pour la page client de ${d.reference}`}
          />
          Exiger un code de lecture (OTP)
        </label>
      </div>
      {/* L-NIV-VU (24/08/2026) — le texte DÉCRIT l'inventaire RÉEL des
          dégradations (public_views) et prévient que sur un devis sans lignes
          de pose ni étude électrique il n'y a RIEN à masquer. */}
      <p className="gen-hint lw-context-devis-niveau-hint">
        {envoi.getNiveau(d) === 'confiance'
          ? 'Confiance : dossier technique complet — nomenclature détaillée, calibres et sections de câble, schéma avec sa nomenclature, PDF sans filigrane.'
          : 'Standard : les fournitures de pose sont regroupées en une ligne « kit », les calibres/sections disparaissent du schéma et du détail électrique, et le PDF porte un filigrane au nom du prospect. Marques, modèles et prix restent entièrement visibles. Sur un devis sans lignes de pose ni étude électrique, il n’y a rien à masquer : les deux niveaux rendent alors la même page.'}
      </p>
    </>
  )
}

// L-SECT — les sections servies. Décocher RETIRE la section de la page client ;
// aucun montant du devis ne change jamais.
function ReglagesSections({ devis: d, envoi }) {
  return (
    <div className="lw-context-devis-sections">
      <p className="gen-hint">Ce que le client reçoit :</p>
      {SECTIONS_ENVOI.map(({ key, label }) => (
        <label key={key} className="lw-context-devis-section">
          <Checkbox
            checked={envoi.getSections(d)[key]}
            onCheckedChange={(v) => envoi.onSectionChange(d, key, v)}
            aria-label={`${label} — page client de ${d.reference}`}
          />
          {label}
        </label>
      ))}
      <p className="gen-hint">
        Le comparatif de gammes n’apparaît que sur un devis qui en
        porte une ; décocher les autres cases retire la section de
        la page, jamais un montant du devis.
      </p>
    </div>
  )
}

// LANE E — combien de tailles (Éco/Recommandé/Max) le client voit. Recommandé
// EST le devis : toujours servie, case verrouillée cochée. RÉSIDENTIEL seulement.
function ReglagesTailles({ devis: d, envoi }) {
  const tailles = envoi.getTailles(d)
  return (
    <div className="lw-context-devis-tailles">
      <p className="gen-hint">Options présentées au client :</p>
      <Segmented
        size="sm"
        aria-label={`Nombre d'options présentées — page client de ${d.reference}`}
        options={[1, 2, 3].map((n) => ({ value: n, label: String(n) }))}
        value={optionsCountFromTailles(tailles)}
        onChange={(n) => envoi.onOptionsCountChange(d, n)}
      />
      <label className="lw-context-devis-taille-toggle">
        <Checkbox
          checked
          disabled
          aria-label={`Taille Recommandé — toujours servie — page client de ${d.reference}`}
        />
        Recommandé
      </label>
      <label className="lw-context-devis-taille-toggle">
        <Checkbox
          checked={tailles.taille_eco}
          onCheckedChange={(v) => envoi.onTailleToggle(d, 'taille_eco', v)}
          aria-label={`Taille Éco — page client de ${d.reference}`}
        />
        Éco
      </label>
      <label className="lw-context-devis-taille-toggle">
        <Checkbox
          checked={tailles.taille_max}
          onCheckedChange={(v) => envoi.onTailleToggle(d, 'taille_max', v)}
          aria-label={`Taille Max — page client de ${d.reference}`}
        />
        Max
      </label>
      <Button type="button" size="sm" variant="outline" onClick={() => envoi.setEditTaillesOuvert(d.id)}>
        <Layers3 size={14} aria-hidden="true" /> Modifier les options…
      </Button>
    </div>
  )
}

// L-INTPREV (fondateur 25/08/2026) — MÊME page client publique, un jeton
// INTERNE différent qui ne pose AUCUNE trace (compteur de vues, note chatter,
// funnel, notification). Ne jamais brancher ce lien sur WhatsApp/l'envoi.
function ApercuInterne({ devis: d, envoi }) {
  return (
    <p className="gen-hint lw-context-devis-apercu-interne">
      <button
        type="button"
        className="lw-context-devis-apercu-interne-btn"
        disabled={envoi.linkBusy === `i-${d.id}`}
        title="Copier le lien d'aperçu interne de la page client — le client n'est jamais notifié ni marqué comme ayant consulté sa proposition"
        onClick={() => envoi.copierApercuInterne(d)}
      >
        {envoi.copiedInterneId === d.id
          ? <Check size={12} aria-hidden="true" />
          : <Eye size={12} aria-hidden="true" />}
        {envoi.copiedInterneId === d.id
          ? 'Copié'
          : 'Aperçu interne de la page client (sans notification)'}
      </button>
      {' '}
      <button
        type="button"
        className="lw-context-devis-apercu-interne-open"
        disabled={envoi.linkBusy === `io-${d.id}`}
        aria-label={`Ouvrir l'aperçu interne de la page client de ${d.reference}`}
        title="Ouvrir la page client SANS notifier le lead ni compter comme une consultation"
        onClick={() => envoi.ouvrirApercuInterne(d)}
      >
        <ExternalLink size={12} aria-hidden="true" />
      </button>
    </p>
  )
}

/**
 * La boîte « Envoyer au client » — UNE seule, pour la carte et l'aperçu.
 *
 * @param {object}  devis          { id, reference, share_link? } (share_link = état
 *                                 réel du dernier lien, pour ne pas repartir des défauts)
 * @param {object}  envoi          résultat de :func:`useEnvoiDevis`
 * @param {boolean} ouvert         la boîte est-elle ouverte
 * @param {string}  modeDevis      marché du devis (commercial/industriel/agricole/
 *                                 residentiel) : hors résidentiel, pas d'options 1/2/3
 */
export default function EnvoiDevisDialog({ devis: d, envoi, ouvert, onOuvertChange, modeDevis = null }) {
  const [avance, setAvance] = useState(false)
  const tailles = optionsTaillesOffertes(modeDevis)
  return (
    <>
      <Dialog open={ouvert} onOpenChange={onOuvertChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Envoyer au client</DialogTitle>
            <DialogDescription>
              Devis {d.reference} — choisissez comment envoyer la page du devis au client.
            </DialogDescription>
          </DialogHeader>
          <CanauxEnvoi devis={d} envoi={envoi} />
          <RelanceJ3 relance={envoi.relance} />
          {envoi.actionMsg && <p className="gen-hint" role="status">{envoi.actionMsg}</p>}
          <Button
            type="button" size="sm" variant="link"
            aria-expanded={avance}
            data-testid="envoi-avance"
            onClick={() => setAvance((v) => !v)}
          >
            Avancé {avance ? '▴' : '▾'}
          </Button>
          {avance && (
            <>
              <ReglagesNiveau devis={d} envoi={envoi} />
              <ReglagesSections devis={d} envoi={envoi} />
              {tailles && <ReglagesTailles devis={d} envoi={envoi} />}
              <ApercuInterne devis={d} envoi={envoi} />
            </>
          )}
        </DialogContent>
      </Dialog>
      {/* LANE E — « Modifier les options » ouvre l'écran vendeur EXISTANT
          (DevisOffresTailles.jsx) pour ce devis, AVANT l'envoi. `modeInstallation`
          n'est pas exposé par `Lead.devis[]` : on force 'residentiel' pour
          toujours déclencher le chargement ; un devis non résidentiel se voit
          alors via `block.editable === false` et son message serveur. */}
      {tailles && (
        <Dialog
          open={envoi.editTaillesOuvert === d.id}
          onOpenChange={(o) => envoi.setEditTaillesOuvert(o ? d.id : null)}
        >
          <DialogContent className="lw-context-devis-edit-tailles">
            <DialogHeader>
              <DialogTitle>Modifier les options — {d.reference}</DialogTitle>
              <DialogDescription>
                Ajustez panneaux, batterie et équipements de chaque
                taille avant d’envoyer la page au client.
              </DialogDescription>
            </DialogHeader>
            <DevisOffresTailles
              devisId={d.id}
              modeInstallation="residentiel"
              produits={envoi.produitsCatalogue}
            />
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}
