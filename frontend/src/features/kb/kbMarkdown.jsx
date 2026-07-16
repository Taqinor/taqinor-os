/* eslint-disable react-refresh/only-export-components --
   Module utilitaire (parseur + composant de rendu) volontairement dans le
   même fichier, comme `messaging/richText.jsx` : `extractHeadings` (XKB10
   sommaire) DOIT rester en phase avec les slugs générés par `KbMarkdownBody`
   pour que les ancres du sommaire pointent toujours au bon endroit — les
   séparer risquerait une dérive silencieuse entre les deux parseurs. */
/* ============================================================================
   XKB10 — Rendu Markdown SANITIZÉ d'un article (titres/gras/italique/code/
   listes/liens). Même contrat de sécurité que ``messaging/richText.jsx`` :
   on ne produit JAMAIS de HTML brut (aucun ``dangerouslySetInnerHTML``) — le
   texte est parsé en un ARBRE d'éléments React construits nœud par nœud, donc
   un payload ``<script>`` tapé dans le corps reste du texte littéral, jamais
   exécuté. Aucune nouvelle dépendance (pas de ``react-markdown``/``marked``) :
   un parseur de ligne suffit pour les besoins d'un article de base de
   connaissances (SOP/FAQ), pas pour du CommonMark complet.
   ========================================================================== */

import ExternalLink from '../../ui/ExternalLink'

const ATX_RE = /^(#{1,6})\s+(.+)$/

// Réutilise le même tokenizer inline que le chat (gras *x*/italique _x_/
// `code`/liens nus) — cohérence de syntaxe dans tout l'ERP.
function tokenizeInline(line) {
  const tokens = []
  const codeSplit = line.split(/(`[^`]+`)/g)
  for (const seg of codeSplit) {
    if (!seg) continue
    if (seg.startsWith('`') && seg.endsWith('`') && seg.length > 1) {
      tokens.push({ type: 'code', value: seg.slice(1, -1) })
      continue
    }
    const boldSplit = seg.split(/(\*[^*]+\*)/g)
    for (const bseg of boldSplit) {
      if (!bseg) continue
      if (bseg.startsWith('*') && bseg.endsWith('*') && bseg.length > 1) {
        tokens.push({ type: 'bold', value: bseg.slice(1, -1) })
        continue
      }
      const italicSplit = bseg.split(/(_[^_]+_)/g)
      for (const iseg of italicSplit) {
        if (!iseg) continue
        if (iseg.startsWith('_') && iseg.endsWith('_') && iseg.length > 1) {
          tokens.push({ type: 'italic', value: iseg.slice(1, -1) })
          continue
        }
        const urlSplit = iseg.split(/(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g)
        for (const useg of urlSplit) {
          if (!useg) continue
          if (/^https?:\/\//.test(useg)) tokens.push({ type: 'link', value: useg })
          else tokens.push({ type: 'text', value: useg })
        }
      }
    }
  }
  return tokens
}

// Retire les diacritiques (accents) après décomposition NFD — plage Unicode
// standard des marques combinantes (̀-ͯ), sans dépendance externe.
const COMBINING_MARKS_RE = /[̀-ͯ]/g

function slugify(text, seen) {
  const base = (text || '')
    .toLowerCase()
    .normalize('NFD').replace(COMBINING_MARKS_RE, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '') || 'section'
  let slug = base
  let n = 2
  while (seen.has(slug)) { slug = `${base}-${n}`; n += 1 }
  seen.add(slug)
  return slug
}

// Découpe le corps en blocs { type: 'heading', niveau, texte, slug }
// | { type: 'list', items } | { type: 'line', tokens }.
function parseBlocks(corps) {
  const lines = (corps || '').split('\n')
  const blocks = []
  const seenSlugs = new Set()
  let currentList = null
  for (const raw of lines) {
    const line = raw
    const heading = ATX_RE.exec(line.trim())
    if (heading) {
      currentList = null
      const texte = heading[2].trim()
      blocks.push({
        type: 'heading',
        niveau: heading[1].length,
        texte,
        slug: slugify(texte, seenSlugs),
      })
      continue
    }
    const isItem = /^[-*]\s+/.test(line)
    if (isItem) {
      const value = line.replace(/^[-*]\s+/, '')
      if (!currentList) { currentList = { type: 'list', items: [] }; blocks.push(currentList) }
      currentList.items.push(value)
      continue
    }
    currentList = null
    blocks.push({ type: 'line', value: line })
  }
  return blocks
}

function renderTokens(tokens, keyPrefix) {
  return tokens.map((tok, i) => {
    const key = `${keyPrefix}-${i}`
    switch (tok.type) {
      case 'bold': return <strong key={key}>{tok.value}</strong>
      case 'italic': return <em key={key}>{tok.value}</em>
      case 'code': return <code key={key} className="kb-inline-code">{tok.value}</code>
      case 'link':
        return (
          <ExternalLink key={key} href={tok.value}>
            {tok.value}
          </ExternalLink>
        )
      default: return tok.value
    }
  })
}

const HEADING_TAG = { 1: 'h1', 2: 'h2', 3: 'h3', 4: 'h4', 5: 'h5', 6: 'h6' }

/** XKB10 — Sommaire (TOC) dérivé du même parseur que le rendu, pour rester
 * toujours cohérent avec les ancres réellement produites. */
export function extractHeadings(corps) {
  return parseBlocks(corps)
    .filter((b) => b.type === 'heading')
    .map((b) => ({ niveau: b.niveau, texte: b.texte, slug: b.slug }))
}

/** Rend le corps Markdown d'un article en éléments React sûrs. */
export function KbMarkdownBody({ corps }) {
  const blocks = parseBlocks(corps)
  return (
    <div className="kb-markdown-body flex flex-col gap-2">
      {blocks.map((block, bi) => {
        if (block.type === 'heading') {
          const Tag = HEADING_TAG[block.niveau] || 'h6'
          return (
            <Tag key={`h-${bi}`} id={block.slug} className="font-display font-semibold tracking-tight scroll-mt-20">
              {block.texte}
            </Tag>
          )
        }
        if (block.type === 'list') {
          return (
            <ul key={`b-${bi}`} className="list-disc pl-5">
              {block.items.map((item, ii) => (
                <li key={`b-${bi}-${ii}`}>{renderTokens(tokenizeInline(item), `b-${bi}-${ii}`)}</li>
              ))}
            </ul>
          )
        }
        if (!block.value) return <br key={`b-${bi}`} />
        return (
          <p key={`b-${bi}`} className="leading-relaxed">
            {renderTokens(tokenizeInline(block.value), `b-${bi}`)}
          </p>
        )
      })}
    </div>
  )
}

export default KbMarkdownBody
