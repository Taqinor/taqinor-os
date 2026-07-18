import { Badge, Button, Avatar, AvatarFallback } from '../../../ui'
import { initials } from '../../../ui/Avatar'
import { normalizeMaPhone } from '../../../lib/format'
import { getField } from './draftCore'

// LW14 — Rail identité (zone gauche, 288px) : tout ce qu'on regarde AVANT
// d'appeler. Identité + contact cliquable + chips de préparation QX28 +
// pile d'actions. La triade (LW15), l'étape (LW16 StageControl), le score
// (LW17) et les bannières (LW18) se greffent ici dans les tâches suivantes.
//
// Contrat de props (blueprint D4 / lane 1) : { state, onAction, users,
// archiveBusy }. Lecture des champs via getField (brouillon-sur-serveur) ; les
// richesses serveur brutes (devis_auto, roof_point, client…) sur state.server.
// TOUTES les sorties/mutations passent par onAction (routé leaveGuard par le
// shell) — jamais de navigation/patch direct ici. Les liens tel:/wa.me
// n'altèrent pas le lead et n'entrent donc pas dans le garde de sortie.

export default function IdentityRail({ state, onAction, users = [], archiveBusy = false }) {
  const server = state.server || {}

  // ── Identité ───────────────────────────────────────────────────────────────
  const prenom = getField(state, 'prenom') || ''
  const nom = `${getField(state, 'nom') || ''} ${prenom}`.trim() || 'Lead'
  const societe = getField(state, 'societe')
  const ville = getField(state, 'ville')
  const sub = [societe, ville].filter(Boolean).join(' · ')
  const archived = !!server.is_archived

  // ── Contact (liens directs — jamais de mutation du lead) ────────────────────
  const telephone = (getField(state, 'telephone') || '').trim()
  const whatsapp = (getField(state, 'whatsapp') || '').trim()
  const email = (getField(state, 'email') || '').trim()
  const gpsLat = getField(state, 'gps_lat')
  const gpsLng = getField(state, 'gps_lng')
  const hasGps = gpsLat != null && gpsLat !== '' && gpsLng != null && gpsLng !== ''
  const callPhone = telephone || whatsapp
  // LW7 — bouton WhatsApp armé UNIQUEMENT sur un numéro normalisable (sinon null).
  const waPhone = normalizeMaPhone(whatsapp || telephone)

  // ── Préparation (chips QX28) ────────────────────────────────────────────────
  const roofReady = !!server.roof_point
  const factureReady = server.facture_hiver != null && server.facture_hiver !== ''
  const devisReady = !!(server.devis_auto && server.devis_auto.pret)
  const devisNotReadyMsg = (server.devis_auto && server.devis_auto.message)
    || 'Renseignez la facture du lead pour activer le devis automatique.'

  // ── Actions ─────────────────────────────────────────────────────────────────
  const alreadyClient = !!server.client
  const openWhatsApp = () => {
    if (waPhone) window.open(`https://wa.me/${waPhone}`, '_blank', 'noopener')
  }
  const call = () => {
    if (callPhone) window.location.href = `tel:${callPhone}`
  }

  return (
    <aside className="lw-zone lw-rail-identity" data-testid="lw-identity-rail">
      {/* Identité */}
      <header className="lw-rail-head">
        <Avatar size="lg" className="lw-rail-avatar">
          <AvatarFallback>{initials(nom)}</AvatarFallback>
        </Avatar>
        <div className="lw-rail-headtext">
          <p className="lw-rail-name">
            {nom}
            {archived && <span className="lw-rail-archived">Archivé</span>}
          </p>
          {sub && <p className="lw-rail-sub">{sub}</p>}
        </div>
      </header>

      {/* Contact cliquable */}
      {(callPhone || email || hasGps) && (
        <div className="lw-rail-contact">
          {callPhone && (
            <a className="lw-rail-contact-link" href={`tel:${callPhone}`}>
              ☎ {callPhone}
            </a>
          )}
          {email && (
            <a className="lw-rail-contact-link" href={`mailto:${email}`}>
              ✉ {email}
            </a>
          )}
          {hasGps && (
            <a
              className="lw-rail-contact-link lw-gps-link"
              href={`https://www.google.com/maps?q=${gpsLat},${gpsLng}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              📍 Voir sur la carte
            </a>
          )}
        </div>
      )}

      {/* Chips de préparation QX28 (ui/Badge — tokens uniquement, dark-safe) */}
      {(roofReady || factureReady || devisReady) && (
        <div className="lw-rail-chips">
          {roofReady && (
            <Badge tone="success" title="Un repère GPS de toiture a été capturé (site ou 3D)">
              📍 Toit épinglé
            </Badge>
          )}
          {factureReady && (
            <Badge tone="info" title="Une facture d'électricité a été saisie">
              🧾 Facture saisie
            </Badge>
          )}
          {devisReady && (
            <Badge tone="success" title="Toutes les données nécessaires sont réunies pour générer un devis">
              ⚡ Prêt à deviser
            </Badge>
          )}
        </div>
      )}

      {/* Pile d'actions — WhatsApp et « Devis auto » sont les 2 CTA premiers. */}
      <div className="lw-rail-actions">
        <Button
          type="button"
          variant="success"
          disabled={!waPhone}
          onClick={openWhatsApp}
          title={waPhone ? 'Ouvrir WhatsApp avec ce contact' : 'Numéro de téléphone invalide'}
        >
          🟢 Envoyer WhatsApp
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={!callPhone}
          onClick={call}
          title={callPhone ? 'Appeler ce contact' : 'Aucun numéro de téléphone'}
        >
          ☎ Appeler
        </Button>
        <Button
          type="button"
          disabled={!devisReady}
          onClick={() => onAction('open-devis', 'auto')}
          title={devisReady ? 'Créer le devis automatique (affiché ici)' : devisNotReadyMsg}
        >
          ⚡ Devis automatique
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => onAction('toiture-3d')}
          title="Ouvrir l'outil de conception 3D avec ce lead déjà chargé"
        >
          Concevoir la toiture (3D){hasGps ? ' 📍' : ''}
        </Button>
        {!alreadyClient && (
          <Button
            type="button"
            variant="outline"
            onClick={() => onAction('convert')}
            title="Convertir ce lead en client (nouveau, existant, ou aucun)"
          >
            Convertir en client
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          disabled={archiveBusy}
          onClick={() => onAction('archive')}
          title={archived ? 'Restaurer ce lead' : 'Archiver ce lead'}
        >
          {archived ? 'Restaurer' : 'Archiver'}
        </Button>
      </div>
    </aside>
  )
}
