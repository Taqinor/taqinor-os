import { useState } from 'react'
import { ChevronDown, GripVertical, X } from 'lucide-react'
import { duree as dureeTexte } from '../lib/textes'

/* ============================================================================
   TCH105 — le volet « À placer ({n}) » de l'Agenda : trois groupes « Aujourd'hui ({n}) » ·
   « À revoir ({n}) » · « Mes projets ({n}) » (replié, puis « ● {projet} ({n}) »), chaque tâche
   avec sa durée (« 30 min », « 1 h »). Toucher une tâche la CHOISIT (une seule à la fois,
   `aria-pressed`) : la page rend alors les créneaux « Placer à {HH:MM} » ; la glisser sur un
   créneau la pose aussi. Vide : « Tout est placé ». Maquettes : agenda-placer-heure.html,
   agenda-placer-heure-duree.html, agenda-jour.html (aside « À placer ») ; textes.md §2.8.
   Le volet ne parle jamais au serveur : `onChoisir(item | null)`.
   `aRevoir(item)` : reportée (motif posé) ou prévue avant aujourd'hui.
   ========================================================================== */

const DUREE_AFFICHEE = 30

function grouper(aPlacer, aujourdhui) {
  const aRevoir = (it) => Boolean(it.motif) || (it.jour_prevu && it.jour_prevu < aujourdhui)
  return { jour: aPlacer.filter((it) => !aRevoir(it)), revoir: aPlacer.filter(aRevoir) }
}

function LignePlacer({ item, choisie, detail, onChoisir }) {
  const presse = choisie === item.id
  return (
    <button
      type="button"
      className="ag-lp"
      data-p={item.projet?.couleur || undefined}
      aria-pressed={presse}
      draggable
      onDragStart={(e) => { e.dataTransfer?.setData('text/plain', String(item.id)); onChoisir(item) }}
      onClick={() => onChoisir(presse ? null : item)}
    >
      <span className="pt"><GripVertical className="i i-16" aria-hidden="true" /></span>
      <span className="t">
        {item.titre}
        {detail && item.explication ? <small>{item.explication}</small> : null}
      </span>
      <span className="d chiffres">{dureeTexte(item.estimation_minutes || DUREE_AFFICHEE)}</span>
    </button>
  )
}

function Groupe({ titre, items, ...props }) {
  if (!items.length) return null
  return (
    <div role="group" aria-label={`${titre} (${items.length})`}>
      <div className="ag-groupe"><span className="projet-nom">{titre}</span><span className="compte chiffres">{items.length}</span></div>
      {items.map((it) => <LignePlacer key={it.id} item={it} {...props} />)}
    </div>
  )
}

function MesProjets({ groupes, ouvertAuDepart, ...props }) {
  const [ouvert, setOuvert] = useState(ouvertAuDepart)
  const total = groupes.reduce((n, g) => n + g.items.length, 0)
  if (!total) return null
  return (
    <div role="group" aria-label={`Mes projets (${total})`}>
      <button type="button" className="ag-groupe replie" aria-expanded={ouvert} onClick={() => setOuvert((o) => !o)}>
        <span className="projet-nom">Mes projets</span><span className="compte chiffres">{total}</span>
        <ChevronDown className="i i-16" aria-hidden="true" />
      </button>
      {ouvert ? groupes.filter((g) => g.items.length).map((g) => (
        <div key={g.projet.id} role="group" aria-label={`${g.projet.nom} (${g.items.length})`}>
          <div className="ag-groupe titre-mes" data-p={g.projet.couleur || undefined}>
            <span className="projet-nom">{`● ${g.projet.nom} (${g.items.length})`}</span>
          </div>
          {g.items.map((it) => <LignePlacer key={it.id} item={it} {...props} />)}
        </div>
      )) : null}
    </div>
  )
}

/**
 * `aPlacer` : `agenda.json` → `a_placer` ; `mesProjets` : → `mes_projets` ; `choisie` : l'id de la
 * tâche choisie (ou nul) ; `aide` : la phrase du pied (Jour : glisser sur un créneau).
 */
export default function VoletAPlacer({
  aPlacer = [], mesProjets = [], choisie = null, aujourdhui, onChoisir, projetsOuverts = false,
  consigne = (titre) => `Touche un créneau pour ${titre}`,
  aide = 'Glisse une tâche sur un créneau pour lui donner une heure.',
}) {
  const { jour, revoir } = grouper(aPlacer, aujourdhui)
  const total = aPlacer.length + mesProjets.reduce((n, g) => n + g.items.length, 0)
  const tous = [...aPlacer, ...mesProjets.flatMap((g) => g.items)]
  const choisi = tous.find((it) => it.id === choisie) ?? null
  const props = { choisie, detail: true, onChoisir }
  return (
    <aside className="ag-aside" aria-label="À placer">
      <div className="ag-aside-tete">
        <h2>À placer <span className="chiffres">{`· ${total}`}</span></h2>
      </div>
      {choisi ? (
        <div className="ag-consigne" role="status">
          <span>{consigne(choisi.titre)}</span>
          <button type="button" className="bouton" aria-label="Annuler la sélection" onClick={() => onChoisir(null)}>
            <X className="i" aria-hidden="true" />
          </button>
        </div>
      ) : null}
      {total === 0 ? <p className="ag-av-vide">Tout est placé</p> : null}
      <Groupe titre="Aujourd'hui" items={jour} {...props} />
      <Groupe titre="À revoir" items={revoir} {...props} />
      <MesProjets groupes={mesProjets} ouvertAuDepart={projetsOuverts} {...props} />
      {total > 0 ? <p className="ag-aside-pied">{aide}</p> : null}
    </aside>
  )
}
