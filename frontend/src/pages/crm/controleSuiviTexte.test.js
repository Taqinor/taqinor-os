import { describe, it, expect } from 'vitest'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { PARCOURS, reponsesDeLEtape } from '../../features/crm/relances/parcours'
import {
  LIBELLES_ISSUE, comparaisonPrecedent, decimal, duree, familleType, heureCasa, jjmm, jourCourt,
  jourLong, joursOuvres, libelleJour, libelleReponse, nomType, noteJoursOuvres, numeroJour,
  phraseExceptions, phrasePeriode, phrasePremierContact, phraseReportee, phraseResultats, pl,
  typeDeLaTable, typeEstTache,
} from './controleSuiviTexte'

/* COCKPIT-CONTRÔLE — les phrases du bloc « Contrôle du suivi », en fonctions
   pures. Les entrées sont l'exemple COMMITTÉ du contrat (PACT10) ; les cas
   limites (singulier, pluriel, null) modifient ce SEUL champ. */
const CONTROLE = exempleContrat('crm', 'controle_suivi')
const VIDE = exempleContrat('crm', 'controle_suivi', 'exemple_vide')

describe('accords et formats', () => {
  it('pl : 0 et 1 au singulier, 2 et plus au pluriel', () => {
    expect([0, 1, 2, 10].map((n) => pl(n, 'jour', 'jours')))
      .toEqual(['jour', 'jour', 'jours', 'jours'])
  })

  it('decimal : virgule française, une décimale au plus, « — » pour null', () => {
    expect(decimal(27.5)).toBe('27,5')
    expect(decimal(24)).toBe('24')
    expect(decimal(2.04)).toBe('2')
    expect(decimal(null)).toBe('—')
    expect(decimal(undefined)).toBe('—')
  })

  it('duree : minutes puis heures, « — » pour null', () => {
    expect(duree(42)).toBe('42 min')
    expect(duree(60)).toBe('1 h')
    expect(duree(135)).toBe('2 h 15')
    expect(duree(65)).toBe('1 h 05')
    expect(duree(null)).toBe('—')
  })

  it('jjmm : jour/mois lu sur la chaîne, sans fuseau', () => {
    expect(jjmm('2026-09-27')).toBe('27/09')
    expect(jjmm('2026-01-05')).toBe('05/01')
    expect(jjmm(null)).toBe('—')
    expect(jjmm('pas une date')).toBe('—')
  })

  it('jours de la frise : long, court (sans point), numéro', () => {
    expect(jourLong('2026-09-29')).toBe('mardi 29 septembre')
    expect(jourCourt('2026-09-29')).toBe('mar')
    expect(jourCourt('2026-09-30')).toBe('mer')
    expect(numeroJour('2026-09-05')).toBe(5)
    expect(jourLong(undefined)).toBe('—')
  })

  it('heureCasa : heure de Casablanca (UTC+1 en septembre), jamais celle du navigateur', () => {
    expect(heureCasa('2026-09-07T07:32:10Z')).toBe('08:32')
    expect(heureCasa(null)).toBe(null)
    expect(heureCasa('nimporte quoi')).toBe(null)
  })
})

describe('jours ouvrés (contrat notes.retard) : le retard et l\'attente le disent, avec les nombres servis', () => {
  it('joursOuvres : accord au singulier pour 0 et 1, pluriel dès 2', () => {
    expect([0, 1, 2, 4, 12].map(joursOuvres)).toEqual([
      '0 jour ouvré', '1 jour ouvré', '2 jours ouvrés', '4 jours ouvrés', '12 jours ouvrés',
    ])
  })

  it('phraseReportee : « reportée N fois » (fois est invariable)', () => {
    expect(phraseReportee(1)).toBe('reportée 1 fois')
    expect(phraseReportee(2)).toBe('reportée 2 fois')
    expect(phraseReportee(7)).toBe('reportée 7 fois')
  })

  it('noteJoursOuvres : le seuil d\'alerte servi, puis la règle dès qu\'une liste de retard ou d\'attente est là', () => {
    expect(noteJoursOuvres({ alerteJours: 2, listesRetard: true })).toBe(
      'Alerte dès 2 jours ouvrés de retard. Week-ends, jours fériés et absences déclarées ne comptent pas.')
    expect(noteJoursOuvres({ alerteJours: 1, listesRetard: true })).toBe(
      'Alerte dès 1 jour ouvré de retard. Week-ends, jours fériés et absences déclarées ne comptent pas.')
    // Aucune liste de retard ou d'attente : le seuil seul, sans la règle.
    expect(noteJoursOuvres({ alerteJours: 2, listesRetard: false })).toBe('Alerte dès 2 jours ouvrés de retard.')
    // Seuil non servi : la règle seule — jamais un nombre inventé.
    expect(noteJoursOuvres({ alerteJours: null, listesRetard: true })).toBe(
      'Week-ends, jours fériés et absences déclarées ne comptent pas.')
    expect(noteJoursOuvres({ listesRetard: true })).not.toMatch(/\d/)
    // Rien à dire.
    expect(noteJoursOuvres({ alerteJours: null, listesRetard: false })).toBe(null)
  })

  it('la phrase du bandeau dit l\'ancienneté des tâches en jours ouvrés (l\'exemple : 4)', () => {
    expect(CONTROLE.exceptions.taches_en_attente.lignes[0].ouverte_depuis_jours).toBe(4)
    expect(phraseExceptions(CONTROLE.exceptions, 'attention')).toContain('1 tâche en attente depuis 4 jours ouvrés')
    expect(phraseExceptions({
      ...VIDE.exceptions,
      taches_en_attente: { total: 1, lignes: [{ ouverte_depuis_jours: 1 }] },
    }, 'attention')).toBe('1 tâche en attente depuis 1 jour ouvré.')
  })
})

describe('phraseExceptions', () => {
  it('reprend les cinq listes de l\'exemple, retards d\'abord', () => {
    expect(phraseExceptions(CONTROLE.exceptions, 'attention')).toBe(
      '2 étapes en retard, 1 tâche en attente depuis 4 jours ouvrés, '
      + '1 étape reportée plusieurs fois, 1 premier contact hors délai.')
  })

  it('accorde le singulier (« 1 étape en retard ») et le pluriel des tâches', () => {
    const exceptions = {
      ...VIDE.exceptions,
      en_retard: { total: 1, lignes: [] },
      taches_en_attente: {
        total: 3, lignes: [{ ouverte_depuis_jours: 6 }, { ouverte_depuis_jours: 2 }],
      },
      sans_prochaine_etape: { total: 2, lignes: [] },
      premier_contact_hors_delai: { total: 4, lignes: [] },
    }
    expect(phraseExceptions(exceptions, 'alerte')).toBe(
      '1 étape en retard, 3 tâches en attente (la plus ancienne depuis 6 jours ouvrés), '
      + '2 dossiers sans prochaine étape, 4 premiers contacts hors délai.')
  })

  it('aucune exception : une phrase selon le niveau, jamais une liste vide inventée', () => {
    expect(phraseExceptions(VIDE.exceptions, 'ok')).toBe('Rien n\'est en retard ni en attente.')
    expect(phraseExceptions(VIDE.exceptions, 'vide')).toBe('Aucune étape n\'était due sur cette période.')
    expect(phraseExceptions(VIDE.exceptions, 'attention')).toBe('')
    expect(phraseExceptions(undefined, 'ok')).toBe('Rien n\'est en retard ni en attente.')
  })
})

describe('phrasePeriode et comparaisonPrecedent', () => {
  it('la phrase de période de l\'exemple', () => {
    expect(phrasePeriode(CONTROLE.verdict, CONTROLE.periode_jours)).toBe(
      'Sur 14 jours : 36 étapes sur 42 traitées à temps (86 %), '
      + '3 rattrapées en retard, 1 sautée, 2 encore ouvertes.')
  })

  it('singulier partout, et « — » quand le pourcentage est null', () => {
    const v = {
      du: 1, a_temps: 1, en_retard: 1, sautees: 1, ouvert: 1, a_temps_pct: null,
    }
    expect(phrasePeriode(v, 7)).toBe(
      'Sur 7 jours : 1 étape sur 1 traitée à temps (—), 1 rattrapée en retard, 1 sautée, 1 encore ouverte.')
  })

  it('rien de dû : aucune étape, aucun pourcentage', () => {
    expect(phrasePeriode(VIDE.verdict, 14)).toBe('Sur 14 jours : aucune étape n\'était due.')
  })

  it('la comparaison se lit sur les pourcentages tels qu\'affichés (arrondis)', () => {
    expect(comparaisonPrecedent(CONTROLE.verdict)).toEqual({
      sens: 'hausse', fleche: '↑',
      texte: '↑ 8 points par rapport à la période précédente (78 %)',
    })
    expect(comparaisonPrecedent({ a_temps_pct: 85.4, precedent_a_temps_pct: 78.6 }).texte)
      .toBe('↑ 6 points par rapport à la période précédente (79 %)')
    expect(comparaisonPrecedent({ a_temps_pct: 80, precedent_a_temps_pct: 81 }).texte)
      .toBe('↓ 1 point par rapport à la période précédente (81 %)')
    expect(comparaisonPrecedent({ a_temps_pct: 80, precedent_a_temps_pct: 80 }))
      .toEqual({ sens: 'stable', fleche: '→', texte: '→ Stable par rapport à la période précédente (80 %)' })
  })

  it('rien à comparer si l\'un des deux pourcentages est null', () => {
    expect(comparaisonPrecedent({ a_temps_pct: null, precedent_a_temps_pct: 80 })).toBe(null)
    expect(comparaisonPrecedent({ a_temps_pct: 80, precedent_a_temps_pct: null })).toBe(null)
    expect(comparaisonPrecedent(VIDE.verdict)).toBe(null)
  })
})

describe('libelleJour (nom accessible d\'une case)', () => {
  const jour = (surcharge) => ({
    date: '2026-09-29', ouvre: true, aujourdhui: false, du: 0, a_temps: 0, en_retard: 0, sautees: 0, ouvert: 0,
    etat: 'vide', ...surcharge,
  })

  it('les compteurs non nuls seulement, dans l\'ordre dues / à temps / rattrapées / sautées / ouvertes', () => {
    expect(libelleJour(jour({
      du: 9, a_temps: 4, en_retard: 2, sautees: 1, ouvert: 2,
    }))).toBe('mardi 29 septembre : 9 dues, 4 à temps, 2 rattrapées en retard, 1 sautée, 2 encore ouvertes')
    expect(libelleJour(jour({ du: 1, ouvert: 1 }))).toBe('mardi 29 septembre : 1 due, 1 encore ouverte')
  })

  it('rien de dû, jour non ouvré, aujourd\'hui', () => {
    expect(libelleJour(jour({}))).toBe('mardi 29 septembre : rien de dû')
    expect(libelleJour(jour({ ouvre: false })))
      .toBe('mardi 29 septembre (jour non ouvré) : rien de dû')
    expect(libelleJour(jour({ aujourdhui: true, du: 2, ouvert: 2 })))
      .toBe('mardi 29 septembre (aujourd\'hui) : 2 dues, 2 encore ouvertes')
  })
})

describe('lecture de la table du parcours', () => {
  it('nomType / familleType / typeEstTache lisent la table, jamais une liste écrite ici', () => {
    const devis = PARCOURS.etapes.find((t) => t.id === 'devis')
    expect(nomType('devis')).toBe(devis.nom)
    expect(familleType('devis')).toBe(devis.famille)
    expect(typeEstTache('devis')).toBe(true)
    expect(typeEstTache('contact_appel')).toBe(false)
    expect(typeDeLaTable('devis')).toBe(devis)
  })

  it('un type absent de la table : l\'identifiant tel quel, jamais un blanc ; vide → vide', () => {
    expect(nomType('type_inconnu')).toBe('type_inconnu')
    expect(nomType('')).toBe('')
    expect(nomType(undefined)).toBe('')
    expect(familleType('type_inconnu')).toBe('')
    expect(typeEstTache('type_inconnu')).toBe(false)
  })

})

/* Les réponses que la table propose sur une étape d'APPEL (`reponses` +
   `reponses_appel`, même normalisation que l'écran) et qui portent une clé. */
const porteuses = (typeId, cle) => reponsesDeLEtape(typeDeLaTable(typeId), { canal: 'appel' })
  .filter((r) => r.outcome === cle || r.reponse === cle)

describe('libelleReponse — une réponse qui porte SEULE la clé dit son libellé de la table', () => {
  it('outcome, `reponse` (et non outcome), libellé propre au type', () => {
    // outcome
    expect(porteuses('contact_appel', 'joint')).toHaveLength(1)
    expect(libelleReponse('contact_appel', 'joint')).toBe('Client joint')
    // `reponse` (et non outcome)
    expect(porteuses('contact_appel', 'plus_tard')).toHaveLength(1)
    expect(libelleReponse('contact_appel', 'plus_tard')).toBe('Plus tard — pas maintenant')
    // libellé PROPRE au type, différent du générique (« À rappeler »)
    expect(porteuses('devis', 'rappel')).toHaveLength(1)
    expect(libelleReponse('devis', 'rappel')).toBe('Pas encore — à rappeler le…')
    expect(libelleReponse('contact_appel', 'rappel')).toBe('À rappeler le…')
  })

  it('sans_issue → « Fait », même sur un type que la table ne connaît pas', () => {
    expect(libelleReponse('devis', 'sans_issue')).toBe('Fait')
    expect(libelleReponse('type_inconnu', 'sans_issue')).toBe('Fait')
  })
})

describe('libelleReponse — une clé PARTAGÉE par plusieurs réponses dit le libellé générique de l\'issue', () => {
  it('generique : `non_joint` est portée par quatre réponses d\'appel, la première est « Répondeur » (trompeur)', () => {
    // La prémisse, lue dans la table : `reponses_appel` de `generique` (objets
    // `{ modele, effet, suite… }`) porte `non_joint` quatre fois.
    const partagees = porteuses('generique', 'non_joint')
    expect(partagees.map((r) => r.label)).toEqual(['Répondeur', 'Occupé', 'Numéro invalide', 'A bloqué / signalé'])
    // … le libellé lisible est donc le générique, pas celui de la première.
    expect(libelleReponse('generique', 'non_joint')).toBe('Pas de réponse')
    expect(libelleReponse('generique', 'non_joint')).not.toBe(partagees[0].label)
  })

  it('les types d\'appel dont `non_joint` est partagée disent « Pas de réponse » (même quand la première est « Sans réponse »)', () => {
    ;['contact_appel', 'appel_apres_reponse', 'dernier_appel', 'rappel_convenu',
      'suivi_appel', 'debrief', 'reveil_appel'].forEach((typeId) => {
      expect(porteuses(typeId, 'non_joint').length).toBeGreaterThan(1)
      expect(libelleReponse(typeId, 'non_joint')).toBe('Pas de réponse')
    })
  })

  it('un type de MESSAGE où une seule réponse porte `non_joint` garde SON libellé (« Sans réponse »)', () => {
    expect(porteuses('suivi_message', 'non_joint')).toHaveLength(1)
    expect(libelleReponse('suivi_message', 'non_joint')).toBe('Sans réponse')
    expect(libelleReponse('suivi_message', 'non_joint')).not.toBe(LIBELLES_ISSUE.non_joint)
  })

  it('accepte dans `reponses_appel` des identifiants de modèle (chaînes) comme des objets', () => {
    const type = typeDeLaTable('suivi_message')
    expect(type.reponses_appel).toBeUndefined()
    expect(libelleReponse('suivi_message', 'non_joint')).toBe('Sans réponse')
    type.reponses_appel = ['repondeur', 'occupe'] // identifiants de modèle, sans objet
    try {
      // Trois réponses partagent maintenant `non_joint` : le générique l'emporte.
      expect(porteuses('suivi_message', 'non_joint')).toHaveLength(3)
      expect(libelleReponse('suivi_message', 'non_joint')).toBe('Pas de réponse')
    } finally {
      delete type.reponses_appel
    }
    expect(libelleReponse('suivi_message', 'non_joint')).toBe('Sans réponse')
  })

  it('propriété sur TOUTE la table : clé partagée → générique (ou 1er libellé sans générique), clé seule → son libellé', () => {
    PARCOURS.etapes.forEach((type) => {
      const reponses = reponsesDeLEtape(type, { canal: 'appel' })
      const cles = new Set(reponses.flatMap((r) => [r.outcome, r.reponse]).filter(Boolean))
      cles.forEach((cle) => {
        const portees = reponses.filter((r) => r.outcome === cle || r.reponse === cle)
        const attendu = portees.length === 1
          ? portees[0].label
          : (LIBELLES_ISSUE[cle] ?? portees[0].label)
        expect(libelleReponse(type.id, cle), `${type.id} / ${cle}`).toBe(attendu)
      })
    })
  })
})

describe('libelleReponse — clé absente du type : repli générique, sinon la clé', () => {
  it('une issue connue mais que le type ne porte pas, ou un type inconnu, dit le générique', () => {
    expect(porteuses('devis', 'non_joint')).toHaveLength(0)
    expect(libelleReponse('devis', 'non_joint')).toBe('Pas de réponse')
    expect(libelleReponse('type_inconnu', 'joint')).toBe('Client joint')
    expect(libelleReponse(undefined, 'refuse')).toBe('Refus')
  })

  it('une clé que personne ne connaît s\'affiche telle quelle', () => {
    expect(libelleReponse('contact_appel', 'rien_de_connu')).toBe('rien_de_connu')
    expect(libelleReponse('type_inconnu', 'rien_de_connu')).toBe('rien_de_connu')
  })
})

describe('LIBELLES_ISSUE — le repli unique', () => {
  it('les six issues, avec les libellés attendus', () => {
    expect(LIBELLES_ISSUE).toEqual({
      non_joint: 'Pas de réponse',
      joint: 'Client joint',
      rappel: 'À rappeler',
      refuse: 'Refus',
      visite_acceptee: 'Visite acceptée',
      sans_issue: 'Fait',
    })
  })

  it('reste rattaché à la table du parcours : un libellé qui y change fait rougir ce test', () => {
    const m = PARCOURS.modeles
    expect(LIBELLES_ISSUE.non_joint).toBe(m.pas_de_reponse.label)
    expect(LIBELLES_ISSUE.joint).toBe(m.joint.label)
    expect(LIBELLES_ISSUE.refuse).toBe(m.refus.label)
    expect(LIBELLES_ISSUE.visite_acceptee).toBe(m.visite.label)
    // « À rappeler le… » dans la table (le champ date suit) ; le repli n'en garde que le verbe.
    expect(m.rappel.label.startsWith(LIBELLES_ISSUE.rappel)).toBe(true)
    // « Fait — passer à la suite » dans la table.
    expect(m.fait.label.startsWith(LIBELLES_ISSUE.sans_issue)).toBe(true)
  })

  it('chaque issue de la table a son repli (aucune ne tombe sur la clé brute)', () => {
    const issues = new Set(Object.values(PARCOURS.modeles).map((m) => m.outcome).filter(Boolean))
    issues.forEach((issue) => expect(LIBELLES_ISSUE[issue], issue).toBeTruthy())
  })
})

describe('phrasePremierContact et phraseResultats', () => {
  it('reprend l\'exemple : dans le délai, médiane, plus longue attente', () => {
    expect(phrasePremierContact(CONTROLE.premier_contact)).toBe(
      '8 sur 9 dans le délai (24 h) · médiane 42 min · plus longue attente 27,5 h')
  })

  it('aucun nouveau lead / aucun lead en attente / médiane inconnue', () => {
    expect(phrasePremierContact(VIDE.premier_contact)).toBe('Aucun nouveau lead sur la période.')
    expect(phrasePremierContact({
      ...CONTROLE.premier_contact, mediane_minutes: null, plus_longue_attente_heures: null,
    })).toBe('8 sur 9 dans le délai (24 h) · médiane — · aucun lead en attente')
  })

  it('résultats : accord au pluriel / singulier', () => {
    expect(phraseResultats(CONTROLE.resultats))
      .toBe('3 visites planifiées · 4 devis envoyés · 1 devis accepté')
    expect(phraseResultats(VIDE.resultats))
      .toBe('0 visite planifiée · 0 devis envoyé · 0 devis accepté')
    expect(phraseResultats({ visites_planifiees: 2, devis_envoyes: 2, devis_acceptes: 2 }))
      .toBe('2 visites planifiées · 2 devis envoyés · 2 devis acceptés')
  })
})
