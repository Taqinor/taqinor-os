import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  STATUT_AFFAIRE, STATUT_PIECE, STATUT_VARIANTE, STATUT_CONTROLE,
  StatutAffaire, StatutPiece, StatutVariante, StatutControle,
} from './statusAo'

/* AOF10 — Pastilles d'état AO : affaire, pièce, variante, contrôle. */

const HERE = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = join(HERE, '..', '..', '..', '..')
const ALLOWED_TONES = new Set(['neutral', 'info', 'success', 'warning', 'danger'])

const MAPS = {
  affaire: { map: STATUT_AFFAIRE, Pill: StatutAffaire },
  piece: { map: STATUT_PIECE, Pill: StatutPiece },
  variante: { map: STATUT_VARIANTE, Pill: StatutVariante },
  controle: { map: STATUT_CONTROLE, Pill: StatutControle },
}

describe.each(Object.keys(MAPS))('STATUT_%s', (name) => {
  const { map, Pill } = MAPS[name]

  it('chaque état porte un libellé FR non vide et un ton connu de StatusPill', () => {
    for (const [key, entry] of Object.entries(map)) {
      expect(entry.label.length, `libellé vide pour ${key}`).toBeGreaterThan(0)
      expect(ALLOWED_TONES.has(entry.tone), `ton inconnu "${entry.tone}" pour ${key}`).toBe(true)
    }
  })

  it('la fabrique statusPill() rend chaque état avec son libellé (identique clair/sombre — aucune couleur posée en dur)', () => {
    for (const [key, entry] of Object.entries(map)) {
      const { unmount } = render(<Pill status={key} />)
      expect(screen.getByText(entry.label)).toBeInTheDocument()
      unmount()
    }
  })

  it('un statut inconnu retombe sur la clé brute (jamais une exception)', () => {
    render(<Pill status="__inconnu__" />)
    expect(screen.getByText('__inconnu__')).toBeInTheDocument()
  })
})

// ── Garde anti-drift : STATUT_AFFAIRE MIROIRE apps/ao/models.py ────────────
// Un état ajouté côté backend (`AppelOffre.Statut`) sans libellé ici doit
// faire rougir CE test — pas un test manuel oublié.
function parseAppelOffreStatutChoices() {
  const src = readFileSync(
    join(REPO_ROOT, 'backend', 'django_core', 'apps', 'ao', 'models.py'),
    'utf8',
  )
  // Ligne à ligne (jamais `\n\n` : le fichier est en CRLF, une ligne vide
  // s'écrit `\r\n\r\n` — un `indexOf('\n\n')` ne la trouverait JAMAIS et
  // capturerait tout le reste du fichier).
  const lines = src.split(/\r?\n/)
  const classLineIdx = lines.findIndex((l) => l.includes('class AppelOffre('))
  expect(classLineIdx, 'class AppelOffre introuvable dans apps/ao/models.py').toBeGreaterThan(-1)
  let statutLineIdx = -1
  for (let i = classLineIdx; i < lines.length; i += 1) {
    if (lines[i].includes('class Statut(models.TextChoices):')) { statutLineIdx = i; break }
  }
  expect(statutLineIdx, 'AppelOffre.Statut introuvable').toBeGreaterThan(-1)
  // Les membres du choix sont les lignes indentées qui suivent IMMÉDIATEMENT
  // (`NOM = 'valeur', 'Libellé'`) — on s'arrête à la première ligne qui ne
  // correspond plus à ce patron (le champ `company` qui suit la classe).
  const values = []
  for (let i = statutLineIdx + 1; i < lines.length; i += 1) {
    const m = lines[i].match(/^\s+[A-Z][A-Z0-9_]*\s*=\s*'([a-z_]+)'/)
    if (!m) break
    values.push(m[1])
  }
  expect(values.length, 'aucune valeur de choix extraite — le parseur a divergé du format réel').toBeGreaterThan(0)
  return values
}

describe('STATUT_AFFAIRE — garde anti-drift backend', () => {
  it('couvre EXACTEMENT les valeurs de AppelOffre.Statut (backend/django_core/apps/ao/models.py)', () => {
    const backendValues = parseAppelOffreStatutChoices().sort()
    const frontendValues = Object.keys(STATUT_AFFAIRE).sort()
    expect(frontendValues).toEqual(backendValues)
  })
})

// ── Garde anti-invention : aucun `statusPill()` local dans features/ao/ ────
function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) {
      walk(full, out)
    } else if (/\.jsx?$/.test(entry) && entry !== 'statusAo.js' && !entry.endsWith('.test.jsx')) {
      out.push(full)
    }
  }
  return out
}

describe('aucun statusPill local dans features/ao/', () => {
  it('seule statusAo.js appelle statusPill() — aucun autre fichier ne réinvente la fabrique', () => {
    const localFactoryRe = /\bfunction\s+statusPill\s*\(|\bconst\s+statusPill\s*=/
    const offenders = walk(HERE)
      .filter((file) => localFactoryRe.test(readFileSync(file, 'utf8')))
    expect(offenders).toEqual([])
  })
})
