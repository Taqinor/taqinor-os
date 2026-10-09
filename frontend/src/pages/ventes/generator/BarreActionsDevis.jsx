// EDC4 — LA BARRE D'ACTIONS EN TÊTE de l'écran devis (embarqué ET pleine page).
// ---------------------------------------------------------------------------
// Fondateur 09/10/2026 : « l'ouvrier doit descendre trop loin pour voir la
// fin ». Les actions n'existaient qu'au PIED du formulaire-fleuve (13 cartes) :
// cette barre reste COLLÉE en haut du défileur réel (`.ldp-edit` dans le
// panneau, `.layout-content` en page) et porte, à toute hauteur de l'écran :
// la référence + le statut du devis, la pastille « Modifications non
// enregistrées », le total TTC courant (même `kpiTotal` que le rail),
// Annuler, Enregistrer et — en Édition complète embarquée — « Voir le PDF ».
//
// Le pied `gen-actions-sticky` RESTE (leçon Xero, idée #47767379 : un
// Enregistrer SEULEMENT en tête échoue sur 30-50 lignes) : les deux coexistent.
//
// AUCUNE règle métier ici : la barre ne calcule rien, elle rend et remonte les
// gestes. Son bouton Enregistrer est un `type="submit" form="gen-form"` : il
// passe par la MÊME validation et le MÊME chemin d'écriture que le pied.
//
// Libellés COURTS (« Enregistrer » / « Créer ») : ceux du pied (« Enregistrer
// les modifications » / « Créer le devis ») sont les ancres des tests RTL et
// e2e (`getByRole('button', { name: /Enregistrer les modifications/ })`) — un
// second bouton au même nom les rendrait ambiguës.
import { useEffect, useRef } from 'react'
import { Eye, Sun } from 'lucide-react'
import { Badge, Button, StatusPill } from '../../../ui'
import { formatMoney } from '../../../features/ventes/solar'
import { libelleStatutDevis } from '../../../features/ventes/devisStatuts'

// Les flèches déplacent le focus entre les commandes de la barre (motif
// « toolbar » WAI-ARIA) ; Tab continue de les parcourir normalement.
const TOUCHES_BARRE = ['ArrowLeft', 'ArrowRight', 'Home', 'End']

/**
 * Barre d'actions collante en tête du générateur.
 *
 * @param {string|null} reference  Référence du devis édité (null en création)
 * @param {string|null} statut     Statut DOCUMENT (brouillon/envoye/…), jamais un stage CRM
 * @param {boolean}     chargement Devis existant en cours de lecture
 * @param {boolean}     enEdition  Devis existant (libellé « Enregistrer » vs « Créer »)
 * @param {boolean}     dirty      Écart avec la référence enregistrée (pastille)
 * @param {number}      totalTtc   Total TTC courant (même valeur que le rail)
 * @param {boolean}     saving     Enregistrement en cours (même `loading` que le pied)
 * @param {function}    onAnnuler  Même geste que « Annuler » du pied
 * @param {function}    onVoirPdf  Optionnel : « Voir le PDF » (panneau, devis existant)
 */
export default function BarreActionsDevis({
  reference = null, statut = null, chargement = false, enEdition = false,
  dirty = false, totalTtc = 0, saving = false,
  onAnnuler, onVoirPdf = null, formId = 'gen-form',
}) {
  const barreRef = useRef(null)

  // `--gen-barre-h` (hauteur réelle de la barre) et `--gen-colle-decalage`
  // (padding haut du défileur, compté en négatif) sont posés sur la racine
  // `.gen-root` : le rail, l'en-tête de table collant (EDC3) et la navigation
  // de sections (EDC9) se collent SOUS la barre. Écriture DOM directe : la
  // mesure ne re-rend jamais les 5 500 lignes du générateur.
  // Le décalage existe parce que Chromium mesure `top` d'un élément collant
  // depuis le bord INTÉRIEUR du padding du défileur : sans lui, en page
  // (`.layout-content`, 2 rem de padding), la barre collerait 32 px sous le
  // haut et le contenu défilerait, visible, au-dessus d'elle.
  useEffect(() => {
    const barre = barreRef.current
    const racine = barre?.closest('.gen-root')
    if (!barre || !racine) return undefined
    const defileur = racine.closest('.ldp-edit, .layout-content')
    const mesurer = () => {
      const h = barre.getBoundingClientRect().height
      if (h > 0) racine.style.setProperty('--gen-barre-h', `${Math.ceil(h)}px`)
      if (defileur) {
        const padding = parseFloat(window.getComputedStyle(defileur).paddingTop) || 0
        racine.style.setProperty('--gen-colle-decalage', `${-padding}px`)
      }
    }
    mesurer()
    if (typeof ResizeObserver === 'undefined') return undefined
    const observateur = new ResizeObserver(mesurer)
    observateur.observe(barre)
    if (defileur) observateur.observe(defileur)
    return () => observateur.disconnect()
  }, [])

  const onKeyDown = (e) => {
    if (!TOUCHES_BARRE.includes(e.key)) return
    const commandes = [...(barreRef.current?.querySelectorAll('button:not([disabled])') ?? [])]
    const i = commandes.indexOf(document.activeElement)
    if (i < 0 || commandes.length < 2) return
    e.preventDefault()
    let cible = i
    if (e.key === 'ArrowLeft') cible = (i - 1 + commandes.length) % commandes.length
    else if (e.key === 'ArrowRight') cible = (i + 1) % commandes.length
    else if (e.key === 'Home') cible = 0
    else cible = commandes.length - 1
    commandes[cible].focus()
  }

  const libelleReference = reference
    || (chargement ? 'Ouverture du devis…' : 'Nouveau devis')

  return (
    <div
      ref={barreRef}
      className="gen-barre-actions"
      role="toolbar"
      aria-label="Actions du devis"
      data-testid="gen-barre-actions"
      onKeyDown={onKeyDown}
    >
      <div className="gen-barre-identite">
        <span className="gen-barre-ref" title={reference || undefined}>{libelleReference}</span>
        {statut && <StatusPill status={statut} label={libelleStatutDevis(statut)} />}
        {/* Région vivante TOUJOURS montée : l'apparition de la pastille est
            annoncée poliment ; sa place est prise dans l'espace libre de la
            zone d'identité (base flex fixe) — rien d'autre ne bouge. */}
        <span className="gen-barre-saisie" role="status" aria-live="polite">
          {dirty && (
            <Badge tone="warning" className="gen-barre-pastille"
                   data-testid="gen-barre-non-enregistre">
              <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-warning" />
              <span className="truncate">Modifications non enregistrées</span>
            </Badge>
          )}
        </span>
      </div>
      <div className="gen-barre-droite">
        <p className="gen-barre-total">
          <span>Total TTC</span>
          <strong data-testid="gen-barre-total">{formatMoney(totalTtc)}</strong>
        </p>
        <div className="gen-barre-boutons">
          {onVoirPdf && (
            <Button type="button" size="sm" variant="outline" onClick={onVoirPdf}>
              <Eye /> Voir le PDF
            </Button>
          )}
          {/* Sur téléphone, « Annuler » reste au pied (et « Retour aux
              devis ») : la barre garde une seule rangée d'actions. */}
          <Button type="button" size="sm" variant="ghost" className="gen-barre-annuler"
                  onClick={onAnnuler}>
            Annuler
          </Button>
          <Button type="submit" form={formId} size="sm" loading={saving}>
            {saving
              ? 'Enregistrement...'
              : <><Sun /> {enEdition ? 'Enregistrer' : 'Créer'}</>}
          </Button>
        </div>
      </div>
    </div>
  )
}
