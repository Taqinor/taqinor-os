// XKB29 — Formatage léger des messages (gras/italique/code/listes/liens).
//
// Rendu sûr : on ne produit JAMAIS de HTML brut (pas de
// `dangerouslySetInnerHTML`) — `renderRichText` retourne un ARBRE d'éléments
// React construits nœud par nœud, donc un payload `<script>` ou tout autre
// balisage tapé dans un message reste du texte littéral, jamais exécuté. Le
// corps stocké reste du texte brut markdown-léger (aucun HTML riche en base).
//
// Marqueurs supportés (les plus courants d'un chat, volontairement limités) :
//   *gras*        → <strong>
//   _italique_    → <em>
//   `code`        → <code>
//   - item        → <ul><li> (une ligne commençant par "- " ou "* ")
//   URL nue       → <a> cliquable (http(s)://…)
//
// `applyShortcut` gère les raccourcis clavier du composer : sélectionner du
// texte et taper `*`/`` ` `` l'entoure du marqueur (symétrique à la façon dont
// Slack/Discord traitent la sélection).

const URL_RE = /(https?:\/\/[^\s<>()]+[^\s<>().,;:!?'"])/g

// Découpe une ligne de texte en tokens { type: 'text'|'bold'|'italic'|'code'|'link', value }.
function tokenizeInline(line) {
  const tokens = []
  // Segmente d'abord sur `code`, qui doit ignorer gras/italique à l'intérieur.
  const codeSplit = line.split(/(`[^`]+`)/g)
  for (const seg of codeSplit) {
    if (!seg) continue
    if (seg.startsWith('`') && seg.endsWith('`') && seg.length > 1) {
      tokens.push({ type: 'code', value: seg.slice(1, -1) })
      continue
    }
    // Gras puis italique, en respectant les URLs à l'intérieur des segments.
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
        // Le reste : texte brut avec URLs nues détectées.
        const urlSplit = iseg.split(URL_RE)
        for (const useg of urlSplit) {
          if (!useg) continue
          if (/^https?:\/\//.test(useg)) {
            tokens.push({ type: 'link', value: useg })
          } else {
            tokens.push({ type: 'text', value: useg })
          }
        }
      }
    }
  }
  return tokens
}

// Regroupe les lignes en blocs { type: 'list', items: [line] } | { type: 'line', value }.
function groupBlocks(lines) {
  const blocks = []
  let currentList = null
  for (const line of lines) {
    const isItem = /^[-*]\s+/.test(line)
    if (isItem) {
      const value = line.replace(/^[-*]\s+/, '')
      if (!currentList) { currentList = { type: 'list', items: [] }; blocks.push(currentList) }
      currentList.items.push(value)
    } else {
      currentList = null
      blocks.push({ type: 'line', value: line })
    }
  }
  return blocks
}

// Parse le texte brut markdown-léger en une structure de blocs/tokens pure
// (JSON-serializable), sans dépendre de React — testable indépendamment du
// rendu, et réutilisée par `renderRichText` pour produire les éléments.
export function parseRichText(text) {
  const src = text || ''
  const lines = src.split('\n')
  return groupBlocks(lines).map((block) => (
    block.type === 'list'
      ? { type: 'list', items: block.items.map(tokenizeInline) }
      : { type: 'line', tokens: tokenizeInline(block.value) }
  ))
}

function renderTokens(tokens, keyPrefix) {
  return tokens.map((tok, i) => {
    const key = `${keyPrefix}-${i}`
    switch (tok.type) {
      case 'bold':
        return <strong key={key}>{tok.value}</strong>
      case 'italic':
        return <em key={key}>{tok.value}</em>
      case 'code':
        return <code key={key} className="chat-inline-code">{tok.value}</code>
      case 'link':
        return (
          <a key={key} href={tok.value} target="_blank" rel="noreferrer noopener">
            {tok.value}
          </a>
        )
      default:
        return tok.value
    }
  })
}

// Rend le texte markdown-léger en éléments React sûrs. Import `React` implicite
// via le JSX runtime automatique (comme le reste du repo) — aucun HTML brut.
export function renderRichText(text) {
  const blocks = parseRichText(text)
  return blocks.map((block, bi) => {
    if (block.type === 'list') {
      return (
        <ul key={`b-${bi}`} className="chat-bubble-list">
          {block.items.map((tokens, ii) => (
            <li key={`b-${bi}-${ii}`}>{renderTokens(tokens, `b-${bi}-${ii}`)}</li>
          ))}
        </ul>
      )
    }
    return (
      <span key={`b-${bi}`} className="chat-bubble-line">
        {renderTokens(block.tokens, `b-${bi}`)}
        {bi < blocks.length - 1 && <br />}
      </span>
    )
  })
}

// Raccourci markdown du composer : entoure la sélection `[start, end)` de
// `text` avec `marker` (`*` pour gras, `` ` `` pour code…). Sans sélection,
// insère une paire vide et place le curseur entre les deux marqueurs.
// Retourne { text: nextText, selectionStart, selectionEnd } pour repositionner
// le curseur du <textarea> appelant.
export function applyShortcut(text, start, end, marker) {
  const before = text.slice(0, start)
  const selected = text.slice(start, end)
  const after = text.slice(end)
  const next = `${before}${marker}${selected}${marker}${after}`
  if (selected) {
    return { text: next, selectionStart: start, selectionEnd: end + marker.length * 2 }
  }
  const caret = start + marker.length
  return { text: next, selectionStart: caret, selectionEnd: caret }
}
