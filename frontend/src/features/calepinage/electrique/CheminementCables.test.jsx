/* CALX229 — le panneau « Cheminement & câbles » de l'atelier.

   Ce qui est prouvé ici :
     1. une ligne par tronçon de l'exemple COMMITTÉ (`calepinage_troncons.json`,
        CALX203, relu par `node:fs` — jamais recopié à la main) ;
     2. une valeur `null` rend un TIRET, jamais un `0` (`ch5`, sans norme
        électrique choisie) ;
     3. les omissions du serveur sont recopiées SANS reformulation ;
     4. un 404 de la porte (route pas encore posée côté serveur, CALX224-226)
        affiche l'état « pas encore calculable », jamais une erreur générique. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const ICI = dirname(fileURLToPath(import.meta.url))

function racineDepot() {
  let dossier = resolve(ICI)
  for (let i = 0; i < 10; i += 1) {
    try {
      readFileSync(join(dossier, 'backend', 'django_core', 'manage.py'))
      return dossier
    } catch { dossier = dirname(dossier) }
  }
  throw new Error(`Racine du depot introuvable depuis ${ICI}`)
}

const CONTRAT = JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
  'contract_samples', 'calepinage_troncons.json'), 'utf8'))

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { troncons: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import CheminementCables, { celluleLongueur, libelleCote, libelleOrigine } from './CheminementCables'

const servir = (data) => { calepinageApi.calepinages.troncons.mockResolvedValue({ data }) }
const refuser404 = () => {
  calepinageApi.calepinages.troncons.mockRejectedValue({ response: { status: 404 } })
}

const rendre = () => render(
  <MemoryRouter><CheminementCables calepinageId={12} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CheminementCables (CALX229)', () => {
  it('une ligne par tronçon de l’exemple committé', async () => {
    servir(CONTRAT.exemple)

    rendre()

    for (const t of CONTRAT.exemple.troncons) {
      expect(await screen.findByTestId(`calx229-troncon-${t.id}`)).toBeInTheDocument()
    }
    expect(CONTRAT.exemple.troncons).toHaveLength(5)
  })

  it('ch5 (section/chute non calculables) rend un TIRET, jamais un 0', async () => {
    servir(CONTRAT.exemple)

    rendre()

    expect(await screen.findByTestId('calx229-chute-ch5')).toHaveTextContent('—')
    expect(screen.getByTestId('calx229-section-ch5')).toHaveTextContent('—')
    expect(screen.getByTestId('calx229-chute-ch5')).not.toHaveTextContent('0')
    expect(screen.getByTestId('calx229-section-ch5')).not.toHaveTextContent('0')
  })

  it('celluleLongueur publie TOUJOURS le nombre ET son origine', () => {
    expect(celluleLongueur({ longueur_m: 18.4, longueur_origine: 'plan' }))
      .toBe('18,4 m (tracé sur le plan)')
    expect(celluleLongueur({ longueur_m: 12, longueur_origine: 'saisie' }))
      .toBe('12,0 m (saisie au clavier)')
    expect(celluleLongueur({ longueur_m: null, longueur_origine: 'plan' })).toBe('—')
  })

  it('libelleCote/libelleOrigine NOMMENT un code inconnu, ne le masquent jamais', () => {
    expect(libelleCote('dc')).toBe('DC')
    expect(libelleCote('hydraulique')).toBe('côté « hydraulique »')
    expect(libelleOrigine('mixte')).toBe('tracé + saisie (mixte)')
    expect(libelleOrigine('devinee')).toBe('origine « devinee »')
  })

  it('les omissions du serveur sont recopiées SANS reformulation', async () => {
    servir(CONTRAT.exemple)

    rendre()

    const omission = CONTRAT.exemple.omissions[0]
    expect(await screen.findByTestId('calx229-omission-0')).toHaveTextContent(omission.motif)
  })

  it('métré par section : une ligne par section, section absente NOMMÉE', async () => {
    servir(CONTRAT.exemple)

    rendre()

    const bloc = await screen.findByTestId('calx229-metre-section')
    expect(bloc).toHaveTextContent('Section non déterminée')
    expect(bloc).toHaveTextContent('6,0 mm²')
    expect(bloc).toHaveTextContent('10,0 mm²')
  })

  it('totaux DC/AC recopiés du serveur, jamais recalculés', async () => {
    servir(CONTRAT.exemple)

    rendre()

    expect(await screen.findByTestId('calx229-total-dc')).toHaveTextContent('0,70 %')
    expect(screen.getByTestId('calx229-total-ac')).toHaveTextContent('1,18 %')
  })

  it('aucun tracé : l’exemple_vide du contrat, une omission qui le dit', async () => {
    servir(CONTRAT.exemple_vide)

    rendre()

    expect(await screen.findByTestId('calx229-vide')).toBeInTheDocument()
    expect(await screen.findByTestId('calx229-omission-0')).toHaveTextContent(
      CONTRAT.exemple_vide.omissions[0].motif,
    )
  })

  it('404 (route pas encore posée) : état « pas encore calculable », jamais une erreur générique', async () => {
    refuser404()

    rendre()

    expect(await screen.findByTestId('calx229-non-calcule')).toBeInTheDocument()
    expect(screen.queryByTestId('calx229-erreur')).toBeNull()
  })
})
