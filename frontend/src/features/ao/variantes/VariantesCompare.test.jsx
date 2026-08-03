import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* ============================================================================
   AOF102 — Comparateur de variantes : les 3 contrats non négociables.
   ----------------------------------------------------------------------------
   1. La bande CONFORMITÉ AO se rend TOUJOURS (sans elle, l'écran n'est qu'un
      comparateur technique de plus — c'est le différenciateur revendiqué).
   2. UNE SEULE variante retenue à la fois, marquée partout, et c'est elle qui
      alimente bordereau et planches.
   3. Sans `ao_rentabilite_voir` : aucune donnée de marge affichée NI PRÉSENTE
      DANS LE PAYLOAD remis au rendu — testé avec un serveur HOSTILE qui en
      renvoie quand même.

   `VarianteColonne` est remplacé par un ESPION DE PROPS pour auditer ce que le
   comparateur remet réellement au rendu (le DOM seul ne prouverait pas
   l'absence dans le payload) ; le dernier bloc remonte le VRAI composant via
   `importActual` pour les contrats de rendu de la colonne.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  retenir: vi.fn(),
  hasPermission: vi.fn(),
  colonneProps: [],
}))

vi.mock('../../../api/aoApi', () => ({
  default: {
    variantes: {
      list: mocks.list, create: mocks.create, update: mocks.update,
      retenir: mocks.retenir,
    },
  },
}))

vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

// Libellés VOLONTAIREMENT distincts de `variante.nom` : la fieldset de
// sélection affiche déjà les noms, un doublon rendrait toute requête ambiguë.
vi.mock('./VarianteColonne', () => ({
  default: (props) => {
    mocks.colonneProps.push(props)
    return (
      <div data-testid={`col-${props.variante.id}`}>
        <span>{`Colonne ${props.variante.nom}`}</span>
        {props.variante.retenue && <span>Colonne retenue</span>}
        <span>{`miniature:${props.miniatureIndisponible}`}</span>
        <button type="button" onClick={() => props.onDefinirRetenue?.(props.variante)}>
          {`Retenir ${props.variante.nom}`}
        </button>
      </div>
    )
  },
}))

import VariantesCompare, { CLES_ECONOMIE, retirerEconomie } from './VariantesCompare'
import { champsServeur } from '../../../test/contratServeur'

const technique = (compte) => ({
  compte_modules: compte,
  puissance_kwc: compte * 0.55,
  kits: [{ nom: 'Kit 4x2', compte: Math.round(compte / 8) }],
  allee_m: 1.2,
  // Grandeur TECHNIQUE portant le mot « marge » : elle ne doit JAMAIS être
  // filtrée par le nettoyage d'économie.
  marges_robustesse: [{ libelle: 'Marge de robustesse', valeur_affichee: '+6 modules' }],
  verdict: {
    statut: 'confirme',
    libelle_statut: 'Confirmé',
    libelle: 'Capacité au-dessus de l’engagement.',
    engagement_modules: 300,
  },
})

const conformite = {
  caution: { statut: 'ok', detail: 'Caution valable jusqu’au 30/09.' },
  delai_execution: { statut: 'ok', detail: '90 jours.' },
  clauses_cps: { statut: 'bloquant', detail: 'Article 12 non satisfait.' },
  marge_engagement: { statut: 'avertissement', detail: '+2 modules seulement.' },
}

/* RÉPARATION 03/08/2026 — les champs SERVEUR (`VarianteCalepinageSerializer`)
   sont `est_retenue`, `total_modules`, `puissance_kwc`, `score`, `statut`… Le
   comparateur lisait `retenue`, qui n'existe pas : la colonne « retenue »
   était donc TOUJOURS vide, et l'écran filtrait sur `affaire`, un paramètre
   ignoré par le ViewSet (il remontait les variantes de TOUS les dossiers).

   `technique`, `conformite`, `miniature_svg` et `epinglee` restent des champs
   que le serveur NE PRODUIT PAS : la bande conformité et la miniature sont une
   dette de conception assumée et NOMMÉE (garde ci-dessous), pas quelque chose
   que ce correctif prétend avoir résolu. */
const VARIANTES = [
  { id: 1, nom: 'Variante A', toiture: 3, appel_offre: 7, role: 'ALTERNATIVE', statut: 'calculee', est_retenue: false, est_recommandee: false, total_modules: 314, puissance_kwc: 172.7, score: 0.9, epinglee: false, miniature_svg: '<svg/>', technique: technique(314), conformite },
  { id: 2, nom: 'Variante B', toiture: 3, appel_offre: 7, role: 'RETENUE', statut: 'publiable', est_retenue: true, est_recommandee: true, total_modules: 302, puissance_kwc: 166.1, score: 0.8, epinglee: false, miniature_svg: '<svg/>', technique: technique(302), conformite },
  { id: 3, nom: 'Variante C', toiture: 3, appel_offre: 7, role: 'ALTERNATIVE', statut: 'brouillon', est_retenue: false, est_recommandee: false, total_modules: 288, puissance_kwc: 158.4, score: 0.6, epinglee: false, miniature_svg: null, technique: technique(288), conformite },
]

// Payload HOSTILE : le serveur renvoie de l'économie alors que la permission
// n'est pas portée (cache tiède, régression de sérialiseur…).
const VARIANTES_AVEC_ECONOMIE = VARIANTES.map((v) => ({
  ...v,
  economie: { prix_vente_ht: 1234567, marge_mad: 89012, marge_pct: 7.2 },
  prix_achat: 999999,
}))

beforeEach(() => {
  vi.clearAllMocks()
  mocks.colonneProps.length = 0
  mocks.hasPermission.mockReturnValue(false)
  mocks.list.mockResolvedValue({ data: VARIANTES })
  mocks.update.mockResolvedValue({ data: {} })
  mocks.create.mockResolvedValue({ data: {} })
  mocks.retenir.mockResolvedValue({ data: {} })
})

const renderCompare = (props = {}) => render(<VariantesCompare affaireId={7} {...props} />)

describe('GARDE de contrat — ce que le serveur produit VRAIMENT', () => {
  const champs = () => champsServeur('VarianteCalepinageSerializer')

  it('les champs que le comparateur exploite existent bien côté serveur', () => {
    const declares = champs()
    for (const cle of ['id', 'nom', 'statut', 'est_retenue', 'appel_offre',
      'toiture', 'role', 'total_modules', 'puissance_kwc', 'score']) {
      expect(declares.has(cle), `champ absent du sérialiseur : ${cle}`).toBe(true)
    }
    // Le champ du bug : il n'a jamais existé.
    expect(declares.has('retenue')).toBe(false)
  })

  it('DETTE NOMMÉE — 4 champs lus par la colonne restent absents du sérialiseur', () => {
    // Ce test échouera le jour où le serveur les publiera : c'est voulu, il
    // faudra alors relire la colonne au lieu de la laisser deviner.
    const declares = champs()
    for (const manquant of ['technique', 'conformite', 'miniature_svg', 'epinglee']) {
      expect(declares.has(manquant),
        `${manquant} est désormais servi : réaligner VarianteColonne`).toBe(false)
    }
  })
})

describe('retirerEconomie — le nettoyage pur', () => {
  it('retire les clés d’économie à TOUTE profondeur, sans muter l’entrée', () => {
    const entree = { a: { economie: { marge_mad: 1 }, b: [{ prix_achat: 2, ok: 3 }] } }
    const sortie = retirerEconomie(entree)
    expect(sortie).toEqual({ a: { b: [{ ok: 3 }] } })
    expect(entree.a.economie.marge_mad).toBe(1) // entrée intacte
  })

  it('ne retire AUCUNE grandeur technique portant le mot « marge »', () => {
    const entree = { marges_robustesse: [{ libelle: 'Marge de robustesse' }], marge_engagement: { statut: 'ok' } }
    expect(retirerEconomie(entree)).toEqual(entree)
  })
})

describe('VariantesCompare — colonnes et sélection', () => {
  it('rend 2 à 4 colonnes (jamais plus de 4, même avec 5 variantes)', async () => {
    mocks.list.mockResolvedValue({
      data: [
        ...VARIANTES,
        { ...VARIANTES[0], id: 4, nom: 'Variante D' },
        { ...VARIANTES[0], id: 5, nom: 'Variante E' },
      ],
    })
    renderCompare()
    await screen.findByText('Colonne Variante A')
    const cols = screen.getAllByText(/^Colonne Variante /)
    expect(cols).toHaveLength(4)
  })

  it('refuse de comparer moins de 2 variantes, avec un message explicite', async () => {
    mocks.list.mockResolvedValue({ data: [VARIANTES[0]] })
    renderCompare()
    expect(await screen.findByText('Pas assez de variantes à comparer')).toBeInTheDocument()
  })

  it('décocher jusqu’à une seule variante affiche « Sélection insuffisante », jamais une colonne orpheline', async () => {
    const user = userEvent.setup()
    renderCompare()
    await screen.findByText('Colonne Variante A')
    await user.click(screen.getByRole('checkbox', { name: 'Comparer Variante A' }))
    await user.click(screen.getByRole('checkbox', { name: 'Comparer Variante B' }))
    expect(await screen.findByText('Sélection insuffisante')).toBeInTheDocument()
  })
})

describe('VariantesCompare — une seule variante retenue', () => {
  it('marque exactement UNE variante retenue, même si le payload en marque deux', async () => {
    mocks.list.mockResolvedValue({
      data: VARIANTES.map((v) => ({ ...v, est_retenue: v.id === 1 || v.id === 2 })),
    })
    renderCompare()
    await screen.findByText('Colonne Variante A')
    expect(screen.getAllByText('Colonne retenue')).toHaveLength(1)
  })

  it('« Définir comme retenue » appelle l’ACTION serveur `retenir` — jamais un PATCH', async () => {
    const user = userEvent.setup()
    renderCompare()
    await screen.findByText('Colonne Variante A')
    await user.click(screen.getByRole('button', { name: 'Retenir Variante A' }))
    // C'est `retenir` qui dé-retient la précédente : un PATCH de
    // `est_retenue` laisserait DEUX variantes retenues sur la toiture.
    await waitFor(() => expect(mocks.retenir).toHaveBeenCalledWith(1))
    expect(mocks.update).not.toHaveBeenCalled()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })

  it('rappelle que la variante retenue est la SEULE source du bordereau et des planches', async () => {
    renderCompare()
    await screen.findByText('Colonne Variante A')
    expect(
      screen.getByText(/Seule la variante retenue alimente le bordereau des prix et les planches/),
    ).toBeInTheDocument()
  })
})

describe('VariantesCompare — économie réservée au directeur', () => {
  it('SANS la permission : la requête ne demande jamais l’économie', async () => {
    renderCompare()
    await screen.findByText('Colonne Variante A')
    expect(mocks.hasPermission).toHaveBeenCalledWith('ao_rentabilite_voir')
    const params = mocks.list.mock.calls[0][0]
    // `appel_offre` : le nom du filtre SERVEUR. `affaire` était ignoré, donc
    // la liste mélangeait les variantes de tous les dossiers de la société.
    expect(params).toEqual({ appel_offre: 7 })
    expect(params).not.toHaveProperty('avec_economie')
  })

  it('SANS la permission et avec un serveur HOSTILE : aucune clé d’économie n’atteint le rendu', async () => {
    mocks.list.mockResolvedValue({ data: VARIANTES_AVEC_ECONOMIE })
    renderCompare()
    await screen.findByText('Colonne Variante A')

    const scan = (valeur, trouvees = []) => {
      if (Array.isArray(valeur)) valeur.forEach((v) => scan(v, trouvees))
      else if (valeur && typeof valeur === 'object') {
        for (const [cle, v] of Object.entries(valeur)) {
          if (CLES_ECONOMIE.includes(cle)) trouvees.push(cle)
          scan(v, trouvees)
        }
      }
      return trouvees
    }
    const fuites = mocks.colonneProps.flatMap((p) => scan(p.variante))
    expect(fuites).toEqual([])
    expect(mocks.colonneProps.every((p) => p.peutVoirEconomie === false)).toBe(true)
    expect(screen.queryByText(/1 234 567/)).not.toBeInTheDocument()
  })

  it('le nettoyage NE touche PAS les grandeurs techniques qui portent le mot « marge »', async () => {
    mocks.list.mockResolvedValue({ data: VARIANTES_AVEC_ECONOMIE })
    renderCompare()
    await screen.findByText('Colonne Variante A')
    const col = mocks.colonneProps.find((p) => p.variante.id === 1)
    expect(col.variante.technique.marges_robustesse[0].libelle).toBe('Marge de robustesse')
    expect(col.variante.conformite.marge_engagement.statut).toBe('avertissement')
  })

  it('AVEC la permission : l’économie est demandée ET transmise telle quelle', async () => {
    mocks.hasPermission.mockReturnValue(true)
    mocks.list.mockResolvedValue({ data: VARIANTES_AVEC_ECONOMIE })
    renderCompare()
    await screen.findByText('Colonne Variante A')
    expect(mocks.list.mock.calls[0][0]).toEqual({ appel_offre: 7, avec_economie: 1 })
    const col = mocks.colonneProps.find((p) => p.variante.id === 1)
    expect(col.peutVoirEconomie).toBe(true)
    expect(col.variante.economie.marge_mad).toBe(89012)
  })
})

describe('VariantesCompare — miniature INJECTÉE (svgToPng/AOF75 hors de cette lane)', () => {
  it('sans exporteur : chaque colonne annonce une miniature indisponible NOMMÉE', async () => {
    renderCompare()
    await screen.findByText('Colonne Variante A')
    expect(screen.getAllByText('miniature:Aperçu indisponible sur cet écran').length).toBeGreaterThan(0)
  })

  it('avec exporteur : il est appelé avec le SVG du plan et sa largeur de rendu', async () => {
    const exporterImage = vi.fn().mockResolvedValue('data:image/png;base64,AAA')
    renderCompare({ exporterImage })
    await waitFor(() => expect(exporterImage).toHaveBeenCalled())
    expect(exporterImage).toHaveBeenCalledWith('<svg/>', { largeur: 320 })
  })
})

describe('VariantesCompare — deux actions RETIRÉES faute d’endpoint', () => {
  it('ne propose ni duplication ni épinglage : aucun appel réseau ne peut les honorer', async () => {
    renderCompare()
    await screen.findByText('Colonne Variante A')
    // `dupliquer_de`/`epinglee` n'existent nulle part côté serveur ; un PATCH
    // d'un champ inconnu répond 200 SANS RIEN ÉCRIRE — le bouton mentait.
    expect(mocks.colonneProps.every((p) => p.onDupliquer === undefined)).toBe(true)
    expect(mocks.colonneProps.every((p) => p.onEpingler === undefined)).toBe(true)
    expect(mocks.create).not.toHaveBeenCalled()
  })
})

/* ── VarianteColonne RÉELLE — les contrats de rendu de la colonne ────────── */
describe('VarianteColonne (composant réel)', () => {
  let VarianteColonne
  beforeEach(async () => {
    ({ default: VarianteColonne } = await vi.importActual('./VarianteColonne'))
  })

  it('rend TOUJOURS les 4 contrôles de la bande CONFORMITÉ AO', () => {
    render(<VarianteColonne variante={VARIANTES[0]} />)
    const section = screen.getByRole('region', { name: 'Variante Variante A' })
    expect(within(section).getByText('Conformité AO')).toBeInTheDocument()
    expect(within(section).getByText(/Caution constituée et non expirée/)).toBeInTheDocument()
    expect(within(section).getByText(/Délai d’exécution tenable|Délai d'exécution tenable/)).toBeInTheDocument()
    expect(within(section).getByText(/Clauses CPS bloquantes/)).toBeInTheDocument()
    expect(within(section).getByText(/Marge d’engagement|Marge d'engagement/)).toBeInTheDocument()
  })

  it('rend la bande CONFORMITÉ même quand le serveur n’a rien évalué (jamais un vide silencieux)', () => {
    render(<VarianteColonne variante={{ ...VARIANTES[0], conformite: undefined }} />)
    expect(screen.getByText('Conformité AO')).toBeInTheDocument()
    expect(screen.getAllByText('Avertissement')).toHaveLength(4)
  })

  it('sans permission : AUCUNE bande interne, aucun chiffre de prix ou de marge', () => {
    render(<VarianteColonne variante={{ ...VARIANTES[0], economie: { prix_vente_ht: 1234567, marge_mad: 89012 } }} peutVoirEconomie={false} />)
    expect(screen.queryByText(/Interne — non communicable/)).not.toBeInTheDocument()
    expect(screen.queryByText(/1 234 567/)).not.toBeInTheDocument()
  })

  it('avec permission : la bande interne est ÉTIQUETÉE et visuellement séparée', () => {
    render(<VarianteColonne variante={{ ...VARIANTES[0], economie: { prix_vente_ht: 1234567, marge_mad: 89012, marge_pct: 7.2 } }} peutVoirEconomie />)
    expect(screen.getByText(/Interne — non communicable/)).toBeInTheDocument()
    expect(screen.getByText(/Prix de vente HT/)).toBeInTheDocument()
  })

  it('porte le hook de contrat `data-ao-variante` et signale la variante retenue', () => {
    // `retenue` est une prop DÉRIVÉE par le comparateur (unicité garantie au
    // rendu), pas un champ serveur — le champ serveur est `est_retenue`.
    const { container } = render(
      <VarianteColonne variante={{ ...VARIANTES[1], retenue: true }} />)
    const carte = container.querySelector('[data-ao-variante="publiable"]')
    expect(carte).not.toBeNull()
    expect(carte.getAttribute('aria-current')).toBe('true')
    expect(screen.getByText('Alimente le bordereau et les planches.')).toBeInTheDocument()
  })

  it('n’affiche « Dupliquer »/« Épingler » que si un gestionnaire est fourni', () => {
    const { unmount } = render(<VarianteColonne variante={VARIANTES[0]} />)
    expect(screen.queryByRole('button', { name: /Dupliquer/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Épingler/ })).toBeNull()
    unmount()
    render(
      <VarianteColonne
        variante={VARIANTES[0]}
        onDupliquer={() => {}}
        onEpingler={() => {}}
      />)
    expect(screen.getByRole('button', { name: /Dupliquer/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Épingler/ })).toBeInTheDocument()
  })

  it('le verdict affiche le LIBELLÉ SERVEUR, jamais une phrase rédigée côté front', () => {
    render(<VarianteColonne variante={VARIANTES[0]} />)
    expect(screen.getByText('Confirmé')).toBeInTheDocument()
    expect(screen.getByText('Capacité au-dessus de l’engagement.')).toBeInTheDocument()
  })
})
