import { useEffect, useRef, useState } from 'react'
import { Link2, Search } from 'lucide-react'
import {
  Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  Input, IconButton, Spinner,
} from '../../ui'
import reportingApi from '../../api/reportingApi'
import messagesApi from '../../api/messagesApi'
import { toastError } from '../../lib/toast'

/* S19 — Action « partager un enregistrement » du composer. Ouvre un sélecteur
   (Dialog) qui réutilise la recherche existante (`reportingApi.search`),
   restreinte aux types partageables (lead / devis / chantier), puis envoie un
   message portant `record_type` / `record_id` via `messagesApi.shareRecord`.
   Le serveur renvoie le message avec `shared_label` / `shared_url` ; il s'affiche
   ensuite comme une carte cliquable (RecordCard). */

// Types partageables et leur libellé + mappage de groupe vers record_type.
const SHAREABLE = {
  lead: { label: 'Leads', recordType: 'lead' },
  devis: { label: 'Devis', recordType: 'devis' },
  chantier: { label: 'Chantiers', recordType: 'chantier' },
}

export default function ShareRecord({ conversationId, onShared, disabled = false }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [failed, setFailed] = useState(false)
  const [sending, setSending] = useState(false)
  const inputRef = useRef(null)

  const term = q.trim()

  // Débounce : recherche ~250 ms après la dernière frappe, comme la barre globale.
  useEffect(() => {
    if (!open) return undefined
    // eslint-disable-next-line react-hooks/set-state-in-effect -- piloter l'état de recherche débouncée depuis la saisie
    if (term.length < 2) { setGroups([]); setLoading(false); setFailed(false); return undefined }
    setLoading(true); setFailed(false)
    const t = setTimeout(() => {
      reportingApi.search(term)
        .then((res) => {
          const all = res.data?.groups ?? []
          setGroups(all.filter((g) => SHAREABLE[g.type]))
        })
        .catch(() => { setGroups([]); setFailed(true) })
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(t)
  }, [q, open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Réinitialise à l'ouverture et focalise le champ.
  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialiser le sélecteur à l'ouverture du Dialog
      setQ(''); setGroups([]); setFailed(false)
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  const share = async (groupType, result) => {
    const recordType = SHAREABLE[groupType]?.recordType
    if (!recordType || !conversationId) return
    setSending(true)
    try {
      const res = await messagesApi.shareRecord({
        conversation: conversationId,
        record_type: recordType,
        record_id: result.id,
      })
      onShared?.(res?.data)
      setOpen(false)
    } catch (err) {
      toastError(err.response?.data?.detail || 'Échec du partage')
    } finally {
      setSending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <IconButton
          type="button"
          aria-label="Partager un enregistrement"
          disabled={disabled || !conversationId}
          className="chat-share-btn"
        >
          <Link2 size={18} aria-hidden="true" />
        </IconButton>
      </DialogTrigger>
      <DialogContent className="chat-share-dialog">
        <DialogHeader>
          <DialogTitle>Partager un enregistrement</DialogTitle>
          <DialogDescription>
            Recherchez un lead, un devis ou un chantier à partager dans la conversation.
          </DialogDescription>
        </DialogHeader>

        <div className="chat-share-search">
          <Search size={16} aria-hidden="true" />
          <Input
            ref={inputRef}
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher (lead, devis, chantier…)"
            aria-label="Rechercher un enregistrement"
            autoComplete="off"
          />
        </div>

        <div className="chat-share-results" role="listbox" aria-label="Résultats">
          {term.length < 2 && (
            <p className="chat-share-hint">Saisissez au moins 2 caractères.</p>
          )}
          {term.length >= 2 && loading && <div className="chat-share-loading"><Spinner size="sm" /></div>}
          {term.length >= 2 && !loading && failed && (
            <p className="chat-share-error" role="alert">Recherche indisponible, réessayez.</p>
          )}
          {term.length >= 2 && !loading && !failed && groups.length === 0 && (
            <p className="chat-share-empty">Aucun résultat pour « {term} ».</p>
          )}
          {term.length >= 2 && !loading && !failed && groups.map((g) => (
            <div key={g.type} className="chat-share-group">
              <div className="chat-share-group-title">{SHAREABLE[g.type]?.label || g.label}</div>
              {(g.results || []).map((r) => (
                <button
                  key={`${g.type}-${r.id}`}
                  type="button"
                  role="option"
                  className="chat-share-result"
                  disabled={sending}
                  onClick={() => share(g.type, r)}
                >
                  <span className="chat-share-result-label">{r.label}</span>
                  {r.sublabel && <span className="chat-share-result-sub">{r.sublabel}</span>}
                </button>
              ))}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
