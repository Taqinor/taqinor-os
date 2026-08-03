import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* ============================================================================
   AOF180 — équipements retenus, bascule et rapport.
   ----------------------------------------------------------------------------
   Cas réel de la session : la bascule batterie BOS-G → BOS-B Pro-A3 a exigé 23
   remplacements cohérents, et son rapport a rattrapé le défaut « la
   justification dit 2 800 DH HT/kWh alors que le bordereau est à 2 600 ».

   **Les fixtures de ce fichier ne s'inventent plus.** La version précédente
   mockait la forme SUPPOSÉE par l'écran (`approvisionnement.statut`,
   `aucun_appro_nouveau`, `emplacements_suspects`, `fiches_ajoutees`,
   `produit.reference`…) : neuf clés qu'aucun module serveur ne produit. Les
   tests étaient verts et l'écran aurait été MUET en production. Chaque clé
   ci-dessous est désormais relue dans sa source — `EquipementAO`,
   `fabrique/approvisionnement.py`, `fabrique/bascule_rapport.py`,
   `stock/serializers.py` — par la section « contrat serveur » en fin de
   fichier, qui tombe si l'une des deux moitiés bouge.
   ========================================================================== */

const mocks = vi.hoisted(() => ({ list: vi.fn(), bascule: vi.fn(), getProduits: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { equipements: { list: mocks.list, bascule: mocks.bascule } },
}))
vi.mock('../../../api/stockApi', () => ({ default: { getProduits: mocks.getProduits } }))

import EquipementsPage from './EquipementsPage'
import { payloadBascule } from './BasculeAssistant.utils'
import { ROLES, GRAVITE_TONE, MOTIF_SUSPECT_LABEL, libelleEmplacement } from './EquipementsPage.utils'

const here = dirname(fileURLToPath(import.meta.url))
const RACINE = join(here, '..', '..', '..', '..', '..')
const fichierBackend = (...morceaux) =>
  join(RACINE, 'backend', 'django_core', 'apps', ...morceaux)
const MODELS_PY = fichierBackend('ao', 'models.py')
const APPRO_PY = fichierBackend('ao', 'fabrique', 'approvisionnement.py')
const BASCULE_PY = fichierBackend('ao', 'fabrique', 'bascule_rapport.py')
const PRODUIT_PY = fichierBackend('stock', 'serializers.py')

/* ── Fixtures CONFORMES au serveur ─────────────────────────────────────────
   `quantite` est un DecimalField → DRF le sérialise en CHAÎNE ('560.000') ;
   `approvisionnement` est le CONSTAT d'AOF119 (`{gravite, motif}`), la seule
   forme que `fabrique/approvisionnement.py` sache produire. */
const EQUIPEMENTS = [
  {
    id: 1, appel_offre: 3, batiment: 8, role: 'module', produit: 41,
    designation: 'Module 625 Wc', marque: 'JA Solar',
    reference_constructeur: 'JAM72D40-625',
    caracteristiques: { puissance: '625 Wc', dimensions: '2382 × 1134 mm' },
    quantite: '560.000', unite: 'U', fiche_technique: 12, remplace: null,
    actif: true, snapshot_le: '2026-07-27T09:00:00Z',
    approvisionnement: {
      gravite: 'info', motif: 'couvert par le stock : Module 625 Wc',
    },
  },
  {
    id: 2, appel_offre: 3, batiment: 8, role: 'batterie', produit: 55,
    designation: 'Batterie lithium BOS-G 16,08 kWh', marque: 'BOS',
    reference_constructeur: 'BOS-G',
    caracteristiques: { kwh_pack: '16.08' },
    quantite: '12.000', unite: 'U', fiche_technique: 13, remplace: null,
    actif: true, snapshot_le: '2026-07-27T09:00:00Z',
    approvisionnement: {
      gravite: 'avertissement',
      motif: 'produit ARCHIVÉ retenu dans le dossier : Batterie lithium BOS-G 16,08 kWh',
    },
  },
]

// `ProduitSerializer.Meta.fields` : la référence catalogue est `sku`.
const CATALOGUE = [
  {
    id: 77, nom: 'Batterie lithium BOS-B Pro-A3 16,08 kWh', marque: 'BOS',
    sku: 'BOS-B-PRO-A3', prix_vente: '26000.00', is_archived: false,
    // Le catalogue PORTE un prix d'achat (rôle directeur) — il ne doit JAMAIS
    // être affiché ni repartir dans un corps de requête.
    prix_achat: '18500.00',
  },
]

// Sortie EXACTE de `rapport_bascule()` : six clés, pas une de plus.
const RAPPORT = {
  ancien: {
    designation: 'Batterie lithium BOS-G 16,08 kWh', reference: 'BOS-G',
    marque: 'BOS', prix_unitaire: '2800', unite: 'kWh',
    caracteristiques: { kwh_pack: '16.08' },
  },
  nouveau: {
    designation: 'Batterie lithium BOS-B Pro-A3 16,08 kWh',
    reference: 'BOS-B Pro-A3', marque: 'BOS', prix_unitaire: '2600',
    unite: 'kWh', caracteristiques: { kwh_pack: '16.08', cycles: 8000 },
  },
  plan: [
    {
      nature: 'champ', champ: 'designation',
      avant: 'Batterie lithium BOS-G 16,08 kWh',
      apres: 'Batterie lithium BOS-B Pro-A3 16,08 kWh',
    },
    { nature: 'champ', champ: 'reference', avant: 'BOS-G', apres: 'BOS-B Pro-A3' },
    { nature: 'champ', champ: 'prix_unitaire', avant: '2800', apres: '2600' },
    { nature: 'caracteristique', champ: 'cycles', avant: null, apres: 8000 },
    { nature: 'emplacement', emplacement: 'bordereau ligne 12' },
    { nature: 'annexe', retirer: 'BOS-G', ajouter: 'BOS-B Pro-A3' },
  ],
  modifies: ['bordereau ligne 12', 'mémoire technique §4.2'],
  suspects: [
    {
      emplacement: 'À REMPLIR PAR ACCORDIA — parenthèse de justification',
      motif: 'ancien_prix', champ: 'prix_unitaire', valeur: '2800',
      attendu: '2600', extrait: 'batteries 2 800 DH HT/kWh',
    },
  ],
  bloquant: true,
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: EQUIPEMENTS })
  mocks.getProduits.mockResolvedValue({ data: CATALOGUE })
  mocks.bascule.mockResolvedValue({ data: { rapport: RAPPORT } })
})

const ouvrirBascule = async () => {
  render(<EquipementsPage affaireId={3} />)
  await screen.findByText('Batterie lithium BOS-G 16,08 kWh')
  fireEvent.click(screen.getAllByRole('button', { name: 'Basculer' })[1])
  fireEvent.click(await screen.findByRole('button', { name: /BOS-B Pro-A3/ }))
  fireEvent.change(screen.getByLabelText(/Motif de la bascule/), {
    target: { value: 'BOS-G indisponible — remplacée par BOS-B Pro-A3.' },
  })
}

describe('EquipementsPage (AOF180)', () => {
  it('filtre la liste sur `appel_offre` — le champ du modèle, jamais un `projet` inconnu', async () => {
    render(<EquipementsPage affaireId={3} />)
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ appel_offre: 3 }))
    // Un filtre inconnu ne lève pas : le ViewSet l'ignore et renvoie TOUTE la
    // société. C'est plus grave qu'un 404, parce que ça n'a l'air de rien.
    const envoyes = Object.keys(mocks.list.mock.calls[0][0])
    expect(envoyes).toEqual(['appel_offre'])
  })

  it('liste par rôle avec les caractéristiques SNAPSHOT (jamais une relecture catalogue)', async () => {
    render(<EquipementsPage affaireId={3} />)
    expect(await screen.findByText('Modules')).toBeInTheDocument()
    expect(screen.getByText('Batteries')).toBeInTheDocument()
    expect(screen.getByText('Module 625 Wc')).toBeInTheDocument()
    expect(screen.getByText(/JA Solar · réf\. JAM72D40-625 · qté 560\.000 U/)).toBeInTheDocument()
    expect(screen.getByText('625 Wc')).toBeInTheDocument()
  })

  it('affiche la GRAVITÉ du contrôle d’approvisionnement et son motif serveur', async () => {
    render(<EquipementsPage affaireId={3} />)
    await screen.findByText('Module 625 Wc')
    expect(screen.getByText('Approvisionnement contrôlé')).toBeInTheDocument()
    expect(screen.getByText('Avertissement')).toBeInTheDocument()
    expect(screen.getByText(/produit ARCHIVÉ retenu dans le dossier/)).toBeInTheDocument()
  })

  it('un équipement sans contrôle le DIT, au lieu d’un badge vide', async () => {
    mocks.list.mockResolvedValue({
      data: [{ ...EQUIPEMENTS[0], approvisionnement: null }],
    })
    render(<EquipementsPage affaireId={3} />)
    expect(await screen.findByText('approvisionnement non contrôlé')).toBeInTheDocument()
  })

  it('n’affirme JAMAIS « aucun approvisionnement nouveau » : c’est une décision de DOSSIER', async () => {
    // `argument_aucun_approvisionnement()` n'est vraie que si AUCUN équipement
    // du dossier ne la contredit, et son texte est une CONSTANTE. Une liste
    // paginée ne peut pas la prouver — l'affirmer ici serait exactement la
    // phrase « écrite à la main » qu'AOF119 existe pour empêcher.
    render(<EquipementsPage affaireId={3} />)
    await screen.findByText('Module 625 Wc')
    expect(screen.queryByText(/aucun approvisionnement nouveau/i)).toBeNull()
  })

  it('bascule en trois clics, motif OBLIGATOIRE, et AUCUN coût dans le payload', async () => {
    render(<EquipementsPage affaireId={3} />)
    await screen.findByText('Batterie lithium BOS-G 16,08 kWh')

    // Clic 1 — ouvrir l'assistant sur la batterie.
    fireEvent.click(screen.getAllByRole('button', { name: 'Basculer' })[1])
    expect(await screen.findByText(/Basculer « Batterie lithium BOS-G 16,08 kWh »/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmer la bascule' })).toBeDisabled()

    // Clic 2 — choisir le nouveau matériel dans le catalogue (référence = sku).
    fireEvent.click(await screen.findByRole('button', { name: /réf\. BOS-B-PRO-A3/ }))
    // Motif encore vide : la confirmation reste refusée.
    expect(screen.getByRole('button', { name: 'Confirmer la bascule' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Motif de la bascule/), {
      target: { value: 'BOS-G indisponible — remplacée par BOS-B Pro-A3.' },
    })

    // Clic 3 — confirmer. La bascule est une ACTION sur l'équipement.
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la bascule' }))
    await waitFor(() => expect(mocks.bascule).toHaveBeenCalledWith(2, {
      nouveau_produit: 77,
      motif: 'BOS-G indisponible — remplacée par BOS-B Pro-A3.',
    }))

    const corps = JSON.stringify(mocks.bascule.mock.calls[0][1])
    expect(corps).not.toMatch(/prix_achat|cout|coût|marge|benefice|bénéfice/i)
  })

  it('n’affiche JAMAIS le prix d’achat d’un produit du catalogue', async () => {
    render(<EquipementsPage affaireId={3} />)
    await screen.findByText('Batterie lithium BOS-G 16,08 kWh')
    fireEvent.click(screen.getAllByRole('button', { name: 'Basculer' })[1])
    await screen.findByRole('button', { name: /BOS-B Pro-A3/ })
    expect(document.body.textContent).not.toMatch(/18500|18 500/)
  })

  it('le rapport affiche les emplacements SUSPECTS sans les masquer (2 800 vs 2 600)', async () => {
    await ouvrirBascule()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la bascule' }))

    expect(await screen.findByText(/1 emplacement\(s\) SUSPECT\(S\)/)).toBeInTheDocument()
    expect(screen.getByText(/À REMPLIR PAR ACCORDIA/)).toBeInTheDocument()
    expect(screen.getByText(/batteries 2 800 DH HT\/kWh/)).toBeInTheDocument()
    // Le motif est un CODE serveur : l'écran le traduit, il ne l'affiche pas brut.
    expect(screen.getByText(/porte encore l’ancien prix/)).toBeInTheDocument()
    expect(screen.queryByText(/ancien_prix/)).toBeNull()
  })

  it('relaie le VERDICT du serveur (`bloquant`), jamais un calcul d’écran', async () => {
    await ouvrirBascule()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la bascule' }))
    expect(await screen.findByText(/Bascule INCOMPLÈTE/)).toBeInTheDocument()
    expect(screen.queryByText('Aucun emplacement suspect détecté.')).toBeNull()
  })

  it('rend les emplacements modifiés, les changements du PLAN et l’annexe (retirée ET ajoutée)', async () => {
    await ouvrirBascule()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la bascule' }))
    await screen.findByText(/Bascule INCOMPLÈTE/)

    expect(screen.getByText('Emplacements modifiés')).toBeInTheDocument()
    expect(screen.getByText('mémoire technique §4.2')).toBeInTheDocument()
    // Les entrées `nature: 'champ'`/`'caracteristique'` du plan, avant → après.
    expect(screen.getByText('Prix unitaire')).toBeInTheDocument()
    expect(screen.getByText(/2800 → 2600/)).toBeInTheDocument()
    // L'annexe est UNE entrée du plan : les deux moitiés du même geste.
    expect(screen.getByText('Fiche technique annexée')).toBeInTheDocument()
    expect(screen.getByText(/Fiche retirée/)).toBeInTheDocument()
    expect(screen.getByText(/Fiche ajoutée/)).toBeInTheDocument()
    // Aucun objet brut relâché dans le JSX (le crash déjà vu sur le dashboard).
    expect(screen.queryByText('[object Object]')).toBeNull()
  })

  it('payloadBascule est une ALLOWLIST : rien d’autre ne peut partir sur le réseau', () => {
    expect(payloadBascule({ produitId: 5, motif: '  raison  ' }))
      .toEqual({ nouveau_produit: 5, motif: 'raison' })
    expect(payloadBascule({ produitId: 5, motif: 'r', quantite: 12 }))
      .toEqual({ nouveau_produit: 5, motif: 'r', quantite: 12 })
    expect(Object.keys(payloadBascule({ produitId: 5, motif: 'r' })).sort())
      .toEqual(['motif', 'nouveau_produit'])
  })

  it('libelleEmplacement rend TOUJOURS une chaîne (jamais un objet dans le JSX)', () => {
    expect(libelleEmplacement('bordereau ligne 12')).toBe('bordereau ligne 12')
    expect(libelleEmplacement({ emplacement: 'mémoire §4.2' })).toBe('mémoire §4.2')
    expect(libelleEmplacement(null)).toBe('')
    expect(typeof libelleEmplacement({ inattendu: 1 })).toBe('string')
  })
})

/* ============================================================================
   GARDE DE CONTRAT — les fixtures sont confrontées à la SOURCE serveur.
   ----------------------------------------------------------------------------
   Ces tests lisent des fichiers Python en texte : aucun runtime Python requis,
   donc aucun coût pour la CI front (même patron que `DashboardPage.test.jsx`).
   ========================================================================== */

const lire = (chemin) => readFileSync(chemin, 'utf8')

/* Les commentaires de ces écrans CITENT les mauvaises clés d'hier pour
   expliquer la réparation : sans ce nettoyage, une garde « la source ne
   contient PAS X » se déclencherait sur le commentaire qui documente
   l'invariant qu'elle vérifie (piège déjà payé sur `DashboardPage`). */
function sansCommentaires(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ')
}

function blocClasse(source, nom) {
  const debut = source.indexOf(`class ${nom}(`)
  if (debut < 0) throw new Error(`Classe introuvable côté serveur : ${nom}`)
  const suite = source.slice(debut + 1)
  const fin = suite.indexOf('\nclass ')
  return fin === -1 ? suite : suite.slice(0, fin)
}

/** Les clés de premier niveau du `return {...}` d'une fonction Python. */
function clesRetour(source, nomFonction) {
  const debut = source.indexOf(`def ${nomFonction}(`)
  if (debut < 0) throw new Error(`Fonction introuvable : ${nomFonction}`)
  const corps = source.slice(debut)
  const ouverture = corps.indexOf('return {')
  const bloc = corps.slice(ouverture, corps.indexOf('\n    }', ouverture))
  return [...bloc.matchAll(/^ {8}'([a-z_]+)':/gm)].map((m) => m[1]).sort()
}

/** Le `Meta.fields = [...]` d'un sérialiseur, lu à parenthèses équilibrées. */
function champsSerialiseur(source, nomClasse) {
  const bloc = blocClasse(source, nomClasse)
  const debut = bloc.indexOf('fields = [')
  let fin = debut + 'fields = ['.length
  let profondeur = 1
  while (profondeur > 0 && fin < bloc.length) {
    if (bloc[fin] === '[') profondeur += 1
    else if (bloc[fin] === ']') profondeur -= 1
    fin += 1
  }
  return new Set(
    [...bloc.slice(debut, fin).matchAll(/'([a-z0-9_]+)'/g)].map((m) => m[1]),
  )
}

describe('Contrat serveur — EquipementAO (AOF118)', () => {
  const bloc = blocClasse(lire(MODELS_PY), 'EquipementAO')
  const champsModele = new Set(
    [...bloc.matchAll(/^ {4}([a-z_]+) = models\./gm)].map((m) => m[1]),
  )

  it('chaque champ non dérivé du mock existe sur le modèle', () => {
    const derives = new Set(['id', 'approvisionnement'])
    const inconnus = Object.keys(EQUIPEMENTS[0])
      .filter((cle) => !derives.has(cle) && !champsModele.has(cle))
    expect(inconnus).toEqual([])
  })

  it('chaque champ LU par l’écran existe sur le modèle', () => {
    const lus = ['role', 'designation', 'marque', 'reference_constructeur',
      'caracteristiques', 'quantite', 'unite']
    lus.forEach((cle) => expect([...champsModele]).toContain(cle))
  })

  it('`produit_designation` n’existe pas : le snapshot figé est la seule source', () => {
    // Le repli sur une relecture catalogue rouvrirait le défaut qu'AOF118
    // ferme : un re-seed qui fait bouger un dossier déjà déposé.
    expect(champsModele.has('produit_designation')).toBe(false)
    const ecran = sansCommentaires(lire(join(here, 'EquipementsPage.jsx')))
    const assistant = sansCommentaires(lire(join(here, 'BasculeAssistant.jsx')))
    expect(ecran).not.toMatch(/produit_designation/)
    expect(assistant).not.toMatch(/produit_designation/)
  })

  it('ROLES est le miroir EXACT de `EquipementAO.Role` (mêmes clés, même ordre)', () => {
    const blocRole = bloc.slice(bloc.indexOf('class Role('),
      bloc.indexOf('appel_offre = models.ForeignKey'))
    const valeurs = [...blocRole.matchAll(/^ {8}[A-Z_]+ = '([a-z_]+)'/gm)].map((m) => m[1])
    expect(valeurs).toHaveLength(12)
    expect(ROLES.map(([cle]) => cle)).toEqual(valeurs)
  })
})

describe('Contrat serveur — contrôle d’approvisionnement (AOF119)', () => {
  const py = lire(APPRO_PY)

  it('les gravités de l’écran sont EXACTEMENT celles du module', () => {
    const gravites = ['INFO', 'AVERTISSEMENT', 'BLOCAGE'].map((nom) => {
      const m = py.match(new RegExp(`^${nom} = '([a-z]+)'`, 'm'))
      expect(m).not.toBeNull()
      return m[1]
    })
    expect(Object.keys(GRAVITE_TONE).sort()).toEqual([...gravites].sort())
    expect(EQUIPEMENTS.map((e) => e.approvisionnement.gravite)
      .every((g) => gravites.includes(g))).toBe(true)
  })

  it('le constat par équipement porte `gravite` + `motif` (et jamais un statut inventé)', () => {
    expect(py).toMatch(/'gravite': self\.gravite/)
    expect(py).toMatch(/'motif': self\.motif/)
    for (const invente of ['aucun_appro_nouveau', 'statut', 'libelle']) {
      expect(py.includes(`'${invente}': `)).toBe(false)
    }
  })

  it('l’argument « aucun approvisionnement nouveau » est une décision de DOSSIER', () => {
    // `argument_disponible` est porté par le RAPPORT complet, pas par un
    // équipement : l'écran de liste ne peut donc pas le calculer.
    expect(py).toMatch(/def argument_aucun_approvisionnement\(rapport\)/)
    expect(py).toMatch(/PHRASE_ARGUMENT/)
    const ecran = sansCommentaires(lire(join(here, 'EquipementsPage.jsx')))
    expect(ecran).not.toMatch(/aucun_appro_nouveau|argumentAppro/)
  })
})

describe('Contrat serveur — rapport de bascule (AOF142)', () => {
  const py = lire(BASCULE_PY)

  it('le mock a EXACTEMENT les clés de `rapport_bascule()`', () => {
    const cles = clesRetour(py, 'rapport_bascule')
    expect(cles).toEqual(['ancien', 'bloquant', 'modifies', 'nouveau', 'plan',
      'suspects'])
    expect(Object.keys(RAPPORT).sort()).toEqual(cles)
  })

  it('les six clés inventées par l’ancien écran ne sont dans aucun rapport', () => {
    const rendu = sansCommentaires(lire(join(here, 'RapportBascule.jsx')))
    for (const invente of ['emplacements_modifies', 'emplacements_suspects',
      'fiches_retirees', 'fiches_ajoutees', 'ancien_libelle', 'nouveau_libelle']) {
      expect(rendu.includes(invente)).toBe(false)
    }
  })

  it('les motifs de suspect traduits par l’écran sont ceux du module', () => {
    const codes = [...py.matchAll(/'motif': '([a-z_]+)'/g)].map((m) => m[1])
    expect(new Set(codes)).toEqual(new Set(Object.keys(MOTIF_SUSPECT_LABEL)))
  })

  it('`modifies` est une liste de CHAÎNES, `plan` porte l’annexe en UNE entrée', () => {
    expect(py).toMatch(/'modifies': list\(emplacements_modifies or \(\)\)/)
    expect(py).toMatch(/'nature': 'annexe', 'retirer':/)
    expect(RAPPORT.modifies.every((e) => typeof e === 'string')).toBe(true)
  })
})

describe('Contrat serveur — catalogue produit (BasculeAssistant)', () => {
  const champs = champsSerialiseur(lire(PRODUIT_PY), 'ProduitSerializer')

  it('la référence catalogue est `sku` — `reference` n’existe pas sur stock.Produit', () => {
    expect(champs.has('sku')).toBe(true)
    expect(champs.has('reference')).toBe(false)
    const assistant = sansCommentaires(lire(join(here, 'BasculeAssistant.jsx')))
    expect(assistant).toMatch(/produit\.sku/)
    expect(assistant).not.toMatch(/produit\.reference/)
  })

  it('chaque champ produit lu par l’assistant existe côté sérialiseur', () => {
    ['nom', 'marque', 'sku', 'prix_vente', 'is_archived']
      .forEach((cle) => expect([...champs]).toContain(cle))
  })
})

/* ── Garde de source : aucun coût ne peut sortir de ces trois écrans ──────── */
describe('Écrans équipements — contrat de source', () => {
  const fichiers = ['EquipementsPage.jsx', 'BasculeAssistant.jsx', 'RapportBascule.jsx']

  it('aucun écran ne lit `prix_achat`, une marge ou un coût de revient', () => {
    fichiers.forEach((nom) => {
      const code = sansCommentaires(lire(join(here, nom)))
      expect(code).not.toMatch(/prix_achat|marge_pct|cout_revient/)
    })
  })

  it('la liste passe par `aoApi.equipements`, jamais un axios direct', () => {
    const code = sansCommentaires(lire(join(here, 'EquipementsPage.jsx')))
    expect(code).toMatch(/aoApi\.equipements\.list/)
    expect(code).toMatch(/aoApi\.equipements\.bascule/)
    expect(code).not.toMatch(/axios\.|api\.get\(/)
  })

  it('le filtre de liste est `appel_offre`, plus jamais `projet`', () => {
    const code = sansCommentaires(lire(join(here, 'EquipementsPage.jsx')))
    expect(code).toMatch(/appel_offre:/)
    expect(code).not.toMatch(/projet:|projetId/)
  })
})
