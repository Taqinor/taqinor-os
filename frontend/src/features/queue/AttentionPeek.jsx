// VX217(a) — <AttentionPeek> : aperçu SANS naviguer d'un item cloche/file.
//
// Chaque item était un cul-de-sac de navigation (`goto(n.link)`) : traiter
// 8 relances = 8 allers-retours d'écran. Survoler (desktop) ou appuyer-
// maintenir (mobile) affiche un petit aperçu — client / montant (si présent
// et CLIENT-SAFE — jamais `prix_achat`) / échéance / dernière action — rendu
// EXCLUSIVEMENT depuis les données déjà présentes sur l'item (aucun appel
// réseau supplémentaire), avec un bouton « Ouvrir » qui navigue enfin.
import { useRef, useState } from 'react'
import { Button } from '../../ui'
import { formatDateTime as fmtDateTime } from '../../lib/format'

const LONG_PRESS_MS = 500

function formatDateTime(iso) {
  if (!iso) return null
  return fmtDateTime(iso) || null
}

/**
 * @param {object} item - un item de « Ma file »/de la cloche : au minimum
 *   `{ title, link }` ; utilise `client_nom`/`client`, `montant` (jamais
 *   `prix_achat` — cet objet ne le porte JAMAIS, le backend ne l'expose pas
 *   côté client), `due`/`due_date`, `created_at`/`body` quand présents.
 * @param {(item: object) => void} onOpen - appelé au clic « Ouvrir ».
 */
export default function AttentionPeek({ item, onOpen, children }) {
  const [open, setOpen] = useState(false)
  const timerRef = useRef(null)

  if (!item) return children

  const show = () => setOpen(true)
  const hide = () => setOpen(false)
  const startPress = () => {
    timerRef.current = setTimeout(show, LONG_PRESS_MS)
  }
  const cancelPress = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
  }

  const client = item.client_nom || item.client || null
  // Montant CLIENT-SAFE uniquement — un item porte au plus `montant` (jamais
  // `prix_achat`, absent par construction des payloads consommés ici).
  const montant = item.montant != null ? item.montant : null
  const due = item.due || item.due_date || null
  const derniereAction = formatDateTime(item.created_at)

  return (
    <div className="attention-peek-anchor"
         onMouseEnter={show}
         onMouseLeave={hide}
         onTouchStart={startPress}
         onTouchEnd={cancelPress}
         onTouchMove={cancelPress}>
      {children}
      {open && (
        <div className="attention-peek" role="tooltip">
          <div className="attention-peek-title">{item.title}</div>
          {client && (
            <div className="attention-peek-row">
              <span>Client</span><span>{client}</span>
            </div>
          )}
          {montant !== null && (
            <div className="attention-peek-row">
              <span>Montant</span><span>{montant} DH</span>
            </div>
          )}
          {due && (
            <div className="attention-peek-row">
              <span>Échéance</span><span>{String(due).slice(0, 10)}</span>
            </div>
          )}
          {derniereAction && (
            <div className="attention-peek-row">
              <span>Dernière action</span><span>{derniereAction}</span>
            </div>
          )}
          {!client && !due && item.body && (
            <div className="attention-peek-row">{item.body.slice(0, 140)}</div>
          )}
          {item.link && (
            <div className="attention-peek-actions">
              <Button size="sm" variant="outline"
                      onClick={(e) => { e.stopPropagation(); hide(); onOpen?.(item) }}>
                Ouvrir
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
