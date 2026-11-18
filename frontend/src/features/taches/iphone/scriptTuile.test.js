import { describe, expect, it } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { SCRIPT_TUILE, scriptPour } from './scriptTuile'

/* TCH110 — le script de la tuile est EXÉCUTÉ par un faux runtime Scriptable (Request, ListWidget,
   Keychain, FileManager, Alert…) sur tuile.json ; on vérifie les lignes qu'il produit
   (textes.md §8), jamais le texte du script. */

const AsyncFunction = Object.getPrototypeOf(async () => {}).constructor
const tuile = () => structuredClone(exempleContrat('taches', 'tuile'))
const BASE = 'https://erp.example'

// `reponse` : le corps rendu (une Error = panne de réseau, sans réponse HTTP) ; `statut` : le code HTTP
// de la réponse (Scriptable le pose sur `request.response.statusCode`) ; une liste = un appel chacun.
async function lancer({ reponse = tuile(), statut = 200, jeton = 'tqt_secret', famille = 'large', enApp = false, saisie = '', fichiers = {}, trousseau } = {}) {
  const suite = Array.isArray(reponse) ? [...reponse] : null
  const statuts = Array.isArray(statut) ? [...statut] : null
  const sortie = { lignes: [], requetes: [], widget: null, alertes: [], fichiers, trousseau: trousseau ?? (jeton ? { taqinor_tuile: jeton } : {}) }
  class Color {
    constructor(hex) { this.hex = hex }
    static dynamic(clair, sombre) { return { clair, sombre } }
  }
  class ListWidget {
    constructor() { sortie.widget = this; this.presente = false }
    addText(texte) { const x = { texte }; sortie.lignes.push(x); return x }
    addSpacer() {}
    async presentLarge() { this.presente = true }
  }
  class Request {
    constructor(url) { this.url = url; sortie.requetes.push(this) }
    async loadJSON() {
      const corps = suite ? suite.shift() : reponse
      const code = statuts ? statuts.shift() : statut
      if (corps instanceof Error && code === 200) throw corps // panne de réseau : aucune réponse HTTP
      this.response = { statusCode: code }
      if (corps instanceof Error) throw corps // corps illisible (pas du JSON) d'une vraie réponse
      return corps
    }
  }
  class Alert {
    constructor() { sortie.alertes.push(this) }
    addTextField() {}
    addAction() {}
    async present() {}
    textFieldValue() { return saisie }
  }
  const Keychain = {
    contains: (cle) => cle in sortie.trousseau,
    get: (cle) => sortie.trousseau[cle],
    set: (cle, valeur) => { sortie.trousseau[cle] = valeur },
  }
  const FileManager = { local: () => ({
    documentsDirectory: () => '/doc',
    joinPath: (a, b) => `${a}/${b}`,
    writeString: (chemin, texte) => { sortie.fichiers[chemin] = texte },
    fileExists: (chemin) => chemin in sortie.fichiers,
    readString: (chemin) => sortie.fichiers[chemin],
    remove: (chemin) => { delete sortie.fichiers[chemin] },
  }) }
  const Font = { boldSystemFont: (t) => ({ t, gras: true }), systemFont: (t) => ({ t }) }
  const Script = { setWidget: () => {}, complete: () => {} }
  const executer = new AsyncFunction('Request', 'ListWidget', 'Keychain', 'FileManager', 'Color', 'Font', 'Alert', 'config', 'Script',
    scriptPour(BASE))
  await executer(Request, ListWidget, Keychain, FileManager, Color, Font, Alert, { runsInApp: enApp, widgetFamily: famille }, Script)
  return { ...sortie, textes: sortie.lignes.map((l) => l.texte) }
}

describe('TCH110 — script de la grande tuile', () => {
  it('grande tuile sur tuile.json : le compte, l\'essentiel, les tâches, le reste, l\'échéance, l\'heure de mise à jour', async () => {
    const r = await lancer()
    expect(r.textes).toHaveLength(6)
    expect(r.textes.slice(0, 3)).toEqual(['1 sur 5', 'Essentiel 0/1', '10:00  Devis Settat'])
    expect(r.textes[3]).toBe('+ 1 autres')
    expect(r.textes[4]).toMatch(/^Échéance .*19.* : Devis Settat$/)
    expect(r.textes[5]).toBe('maj 09:41')
    expect(r.widget.url).toBe('https://erp.example/taches/aujourdhui')
    expect(r.widget.refreshAfterDate).toBeInstanceOf(Date)
  })

  it('appelle la tuile avec le jeton du Trousseau en Bearer, et garde la réponse pour le hors ligne', async () => {
    const r = await lancer({ jeton: 'tqt_abc' })
    expect(r.requetes).toHaveLength(1)
    expect(r.requetes[0].url).toBe(`${BASE}/api/django/taches/tuile/`)
    expect(r.requetes[0].headers).toEqual({ Authorization: 'Bearer tqt_abc' })
    expect(JSON.parse(r.fichiers['/doc/taches-tuile.json']).jour).toBe('2026-11-17')
  })

  it('sans objectif : « {faites} faites » ; sans essentiel prévu : pas de ligne ; sans heure : « • titre »', async () => {
    const donnees = tuile()
    donnees.objectif = null
    donnees.essentiel = { faites: 0, prevues: 0 }
    donnees.reste = 0
    donnees.top = [{ id: 1, titre: 'Tâche confidentielle', heure: null, priorite: 0 }]
    const r = await lancer({ reponse: donnees })
    expect(r.textes.slice(0, 2)).toEqual(['1 faites', '• Tâche confidentielle'])
    expect(r.textes.some((t) => t.startsWith('Essentiel'))).toBe(false)
    expect(r.textes.some((t) => t.startsWith('+ '))).toBe(false)
  })

  it('rien de gardé : « Rien de gardé aujourd\'hui. » et pas d\'échéance', async () => {
    const donnees = tuile()
    donnees.top = []
    donnees.reste = 0
    donnees.prochaine_echeance = null
    const r = await lancer({ reponse: donnees })
    expect(r.textes).toContain("Rien de gardé aujourd'hui.")
    expect(r.textes.some((t) => t.startsWith('Échéance'))).toBe(false)
  })

  it('garde 6 tâches en grande taille et 3 en moyenne, dans l\'ordre reçu', async () => {
    const donnees = tuile()
    donnees.top = Array.from({ length: 8 }, (_, i) => ({ id: i, titre: `T${i}`, heure: null, priorite: 0 }))
    const grande = await lancer({ reponse: structuredClone(donnees), famille: 'large' })
    const moyenne = await lancer({ reponse: structuredClone(donnees), famille: 'medium' })
    expect(grande.textes.filter((t) => t.startsWith('• '))).toEqual(['• T0', '• T1', '• T2', '• T3', '• T4', '• T5'])
    expect(moyenne.textes.filter((t) => t.startsWith('• '))).toEqual(['• T0', '• T1', '• T2'])
  })

  it('hors ligne : relit la dernière réponse et le dit dans le pied', async () => {
    const hors = await lancer({ reponse: new Error('réseau'), fichiers: { '/doc/taches-tuile.json': JSON.stringify(tuile()) } })
    expect(hors.textes[0]).toBe('1 sur 5')
    expect(hors.textes.at(-1)).toBe('Hors ligne · maj 09:41')
  })

  it('hors ligne sans réponse gardée, ou réponse refusée : « Pas de données » ; sans jeton : « Jeton absent »', async () => {
    const vide = await lancer({ reponse: new Error('réseau') })
    expect(vide.textes).toEqual(['Pas de données', 'Ouvre le script dans Scriptable.'])
    const refus = await lancer({ reponse: { error: 'non' } })
    expect(refus.textes[0]).toBe('Pas de données')
    const sansJeton = await lancer({ jeton: '' })
    expect(sansJeton.textes).toEqual(['Jeton absent', 'Ouvre le script dans Scriptable.'])
    expect(sansJeton.requetes).toHaveLength(0)
  })

  it('revue F3 n° 12 — jeton refusé (401) : rien d\'ancien n\'est montré, la réponse gardée est effacée, la tuile dit quoi faire', async () => {
    const gardee = { '/doc/taches-tuile.json': JSON.stringify(tuile()) }
    const refus = await lancer({ reponse: { detail: 'Informations d\'authentification non fournies.' }, statut: 401, fichiers: gardee })
    expect(refus.textes).toEqual(['Pas de données', 'Perdu ? Régénère-le.', 'Ouvre le script dans Scriptable.'])
    expect(refus.textes.some((t) => t.startsWith('Hors ligne'))).toBe(false)
    expect(refus.fichiers).not.toHaveProperty('/doc/taches-tuile.json')
    expect(refus.trousseau.taqinor_tuile).toBe('tqt_secret') // le jeton n'est jamais jeté d'office
    // Corps illisible d'un refus (pas du JSON) : même chose.
    const illisible = await lancer({ reponse: new Error('JSON'), statut: 401, fichiers: { '/doc/taches-tuile.json': JSON.stringify(tuile()) } })
    expect(illisible.textes[0]).toBe('Pas de données')
    expect(illisible.fichiers).not.toHaveProperty('/doc/taches-tuile.json')
    // Une panne de réseau, elle, garde la dernière réponse et le dit (« Hors ligne »).
    const panne = await lancer({ reponse: new Error('réseau'), fichiers: { '/doc/taches-tuile.json': JSON.stringify(tuile()) } })
    expect(panne.textes.at(-1)).toBe('Hors ligne · maj 09:41')
  })

  it('revue F3 n° 12 — refusé, lancé dans l\'app : redemande le jeton, le garde et relit la tuile avec lui', async () => {
    const r = await lancer({ reponse: [{ detail: 'refusé' }, tuile()], statut: [401, 200], enApp: true, saisie: 'tqt_nouveau' })
    expect(r.alertes).toHaveLength(1)
    expect(r.trousseau.taqinor_tuile).toBe('tqt_nouveau')
    expect(r.requetes.map((q) => q.headers.Authorization)).toEqual(['Bearer tqt_secret', 'Bearer tqt_nouveau'])
    expect(r.textes[0]).toBe('1 sur 5')
  })

  it('lancé dans l\'app sans jeton : demande « Jeton de la tuile », le garde dans le Trousseau et présente la tuile', async () => {
    const r = await lancer({ jeton: '', enApp: true, saisie: '  tqt_colle  ' })
    expect(r.alertes).toHaveLength(1)
    expect(r.alertes[0].title).toBe('Jeton de la tuile')
    expect(r.alertes[0].message).toBe('Colle le jeton copié depuis Mon iPhone.')
    expect(r.trousseau.taqinor_tuile).toBe('tqt_colle')
    expect(r.requetes[0].headers).toEqual({ Authorization: 'Bearer tqt_colle' })
    expect(r.widget.presente).toBe(true)
  })

  it('le script tient en 90 lignes, ne contient aucun jeton ni adresse écrite en dur, et prend l\'adresse de l\'ERP', () => {
    expect(SCRIPT_TUILE.trimEnd().split('\n').length).toBeLessThanOrEqual(90)
    expect(SCRIPT_TUILE).not.toMatch(/tq[cft]_[A-Za-z0-9]{8}/)
    expect(SCRIPT_TUILE).not.toMatch(/https?:\/\//)
    const pret = scriptPour('https://erp.example/')
    expect(pret).toContain('const BASE = "https://erp.example";')
    expect(pret).not.toContain('__BASE__')
  })
})
