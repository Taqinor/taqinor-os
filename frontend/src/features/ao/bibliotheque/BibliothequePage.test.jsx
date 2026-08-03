import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import process from 'node:process'

/* ============================================================================
   AOF173 — Bibliothèque : le test parle la langue du SERVEUR.
   ----------------------------------------------------------------------------
   RÉPARATION 03/08/2026. L'ancienne version de ce fichier mockait
   `aoApi.bibliotheque` avec une forme INVENTÉE (`{ id, nom, description,
   dossiers_utilisant_count }`) et une méthode `appliquer()`. Elle était verte
   pendant que l'écran appelait `/ao/bibliotheque/`, une route que le backend
   n'a JAMAIS enregistrée : 404 en production. Un test qui invente sa propre
   réponse ne prouve rien — il prouve seulement qu'il est d'accord avec
   lui-même.

   D'où les deux règles de ce fichier :
   1. les fixtures reproduisent la forme EXACTE des sérialiseurs DRF ;
   2. une GARDE relit `apps/ao/serializers.py` et fait échouer le test dès
      qu'une fixture porte une clé que le serveur ne produit pas (ou que le
      serveur cesse de produire).
   ========================================================================== */

/* Vitest ne garantit pas un `import.meta.url` en `file:` (le module est
   transformé) : on remonte depuis le CWD jusqu'à la racine du dépôt. */
function racineDepot() {
  let dossier = resolve(process.cwd())
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error('Racine du dépôt introuvable depuis ' + process.cwd())
}

const fichierAo = (nom) =>
  join(racineDepot(), 'backend', 'django_core', 'apps', 'ao', nom)

const SERIALIZERS_PY = fichierAo('serializers.py')

/** Champs déclarés par un `Meta.fields = [...]` de sérialiseur DRF. */
function champsServeur(nomClasse) {
  const source = readFileSync(SERIALIZERS_PY, 'utf8')
  const debut = source.indexOf(`class ${nomClasse}(`)
  if (debut < 0) throw new Error(`Sérialiseur introuvable côté serveur : ${nomClasse}`)
  const bloc = source.slice(debut, debut + 4000)
  const champs = bloc.match(/\n\s+fields = \[([\s\S]*?)\]/)
  if (!champs) throw new Error(`Meta.fields introuvable pour ${nomClasse}`)
  return new Set([...champs[1].matchAll(/'([^']+)'/g)].map((m) => m[1]))
}

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  update: vi.fn(),
  create: vi.fn(),
  dossiersImpactes: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  BIBLIOTHEQUE_RESSOURCES: {
    kit: 'kits-calepinage',
    preset: 'presets-calepinage',
    gabarit_pack: 'modeles-pack',
    texte_normalise: 'sections-memoire',
  },
  default: {
    bibliotheque: {
      list: mocks.list,
      get: mocks.get,
      update: mocks.update,
      create: mocks.create,
      dossiersImpactes: mocks.dossiersImpactes,
    },
  },
}))

import BibliothequePage from './BibliothequePage'

/* ── Fixtures = la RÉPONSE DU SERVEUR, champ pour champ ──────────────────── */

// `KitCalepinageSerializer` — un kit n'a pas de `nom` : il a `code`/`libelle`.
const KITS = [{
  id: 1, code: 'K-DOS-2', libelle: 'Table dos-à-dos 2 modules', mode: 'derive',
  modules_par_kit: 2, actif: true,
}]

// `PresetCalepinageSerializer` — le SEUL des quatre à porter un vrai `nom`.
const PRESETS = [{
  id: 2, nom: 'Toiture plate — 15°', portee: 'societe', parametres: {},
  par_defaut: false, description: 'Jeu de paramètres par défaut.',
}]

// `ModelePackSerializer`
const PACKS = [{
  id: 3, code: 'PACK-AO', libelle: 'Pack solaire AO',
  description: 'Neuf pièces, 00 → 08.', actif: true,
}]

// `SectionMemoireSerializer` — `titre`/`corps`, jamais `nom`, et AUCUN
// compteur `dossiers_utilisant_count` (le serveur ne l'a jamais produit :
// les dossiers impactés sont un appel SÉPARÉ).
const TEXTES = [{
  id: 5, code: 'RESERVE', titre: 'Clause de réserve',
  corps: 'Texte normatif initial.', ordre: 10, conditions_inclusion: {},
  actif: true,
}]

const PAR_TYPE = {
  kit: KITS, preset: PRESETS, gabarit_pack: PACKS, texte_normalise: TEXTES,
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockImplementation(({ type } = {}) =>
    Promise.resolve({ data: PAR_TYPE[type] ?? [] }))
  mocks.update.mockResolvedValue({ data: {} })
  mocks.dossiersImpactes.mockResolvedValue({
    // `services.dossiers_impactes_par_section` renvoie exactement ces 4 clés.
    data: [
      { id: 1, reference: 'AO-2026-001', objet: 'Toiture A', statut: 'en_cours' },
      { id: 2, reference: 'AO-2026-002', objet: 'Toiture B', statut: 'en_cours' },
    ],
  })
})

describe('GARDE de contrat — les fixtures ne peuvent pas inventer de champ', () => {
  it.each([
    ['KitCalepinageSerializer', KITS],
    ['PresetCalepinageSerializer', PRESETS],
    ['ModelePackSerializer', PACKS],
    ['SectionMemoireSerializer', TEXTES],
  ])('%s — chaque clé mockée est déclarée par le sérialiseur', (classe, fixtures) => {
    const declares = champsServeur(classe)
    for (const objet of fixtures) {
      for (const cle of Object.keys(objet)) {
        expect(
          declares.has(cle),
          `${classe} ne produit pas « ${cle} » : la fixture invente une forme.`,
        ).toBe(true)
      }
    }
  })

  it('les 4 catégories de l’écran pointent 4 ressources RÉELLEMENT routées', async () => {
    const urls = readFileSync(fichierAo('urls.py'), 'utf8')
    const routees = new Set(
      [...urls.matchAll(/router\.register\(\s*r'([^']+)'/g)].map((m) => m[1]),
    )
    const { BIBLIOTHEQUE_RESSOURCES } = await import('../../../api/aoApi')
    for (const chemin of Object.values(BIBLIOTHEQUE_RESSOURCES)) {
      expect(routees.has(chemin), `route absente de urls.py : ${chemin}`).toBe(true)
    }
    // Le chemin du bug : il ne doit JAMAIS revenir.
    expect(Object.values(BIBLIOTHEQUE_RESSOURCES)).not.toContain('bibliotheque')
  })
})

describe('BibliothequePage', () => {
  it('charge les kits par défaut et affiche leur `libelle` serveur', async () => {
    render(<BibliothequePage />)
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ type: 'kit' }))
    expect(await screen.findByText('Table dos-à-dos 2 modules')).toBeInTheDocument()
  })

  it('changer de catégorie recharge avec le bon type', async () => {
    render(<BibliothequePage />)
    await screen.findByText('Table dos-à-dos 2 modules')
    fireEvent.click(screen.getByRole('radio', { name: 'Textes normalisés' }))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ type: 'texte_normalise' }))
    // `titre` — le serveur n'envoie pas de `nom` pour cette ressource.
    expect(await screen.findByText('Clause de réserve')).toBeInTheDocument()
  })

  it('un preset s’affiche par son `nom` et sa `description` serveur', async () => {
    render(<BibliothequePage />)
    await screen.findByText('Table dos-à-dos 2 modules')
    fireEvent.click(screen.getByRole('radio', { name: 'Jeux de paramètres' }))
    expect(await screen.findByText('Toiture plate — 15°')).toBeInTheDocument()
    expect(screen.getByText('Jeu de paramètres par défaut.')).toBeInTheDocument()
  })

  it('aucun bouton « Appliquer » : l’endpoint n’existe pas côté serveur', async () => {
    render(<BibliothequePage />)
    await screen.findByText('Table dos-à-dos 2 modules')
    expect(screen.queryByRole('button', { name: 'Appliquer' })).toBeNull()
  })

  it('« Modifier » un texte partagé affiche les dossiers impactés AVANT toute validation', async () => {
    render(<BibliothequePage />)
    fireEvent.click(await screen.findByRole('radio', { name: 'Textes normalisés' }))
    await screen.findByText('Clause de réserve')
    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    await waitFor(() => expect(mocks.dossiersImpactes).toHaveBeenCalledWith(5))
    expect(await screen.findByText('AO-2026-001')).toBeInTheDocument()
    expect(screen.getByText('AO-2026-002')).toBeInTheDocument()
  })

  it('enregistrer fait un PATCH sur la ressource RÉELLE et le MÊME id — jamais create()', async () => {
    render(<BibliothequePage />)
    fireEvent.click(await screen.findByRole('radio', { name: 'Textes normalisés' }))
    await screen.findByText('Clause de réserve')
    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    await screen.findByText('AO-2026-001') // dossiers impactés chargés
    const textarea = screen.getByLabelText('Corps du texte normalisé')
    fireEvent.change(textarea, { target: { value: 'Texte normatif révisé.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(
      'texte_normalise', 5, { corps: 'Texte normatif révisé.' },
    ))
    expect(mocks.create).not.toHaveBeenCalled()
  })
})
