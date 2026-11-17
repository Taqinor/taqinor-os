"""TCH38-TCH40 — analyseur de saisie rapide : la table de test de reference/regles.md §1.11
(86 phrases : A1-A39, E1-E16, pièges P1-P25, captures C1-C6). `analyser` doit rendre
EXACTEMENT les champs listés (vide = nul, 0 ou absent) ; unittest pur, sans base ni horloge.

Repère §0 : mardi 17/11/2026 10:00 ; projets Polydesign (id 3, actif) et Maison (id 5,
actif, étape Achats id 8) ; aucun férié, aucune étiquette existante.
"""
import unittest
from datetime import date, datetime, time

from apps.taches.saisie.analyseur import analyser, classer_capture
from apps.taches.saisie.grammaire import ProjetConnu

MARDI = (date(2026, 11, 17), time(10, 0))
PROJETS = (ProjetConnu(3, 'Polydesign', 'actif', 1), ProjetConnu(5, 'Maison', 'actif', 2))
SECTIONS = ((5, 8, 'Achats'),)


def j(jour, mois=11, annee=2026):
    return f'{annee}-{mois:02d}-{jour:02d}'


def rec(frequence, n=1, masque='0000000', jour_du_mois=None, rang=None,
        mode='calendrier'):
    return {'frequence': frequence, 'intervalle': n, 'jours_semaine': masque,
            'jour_du_mois': jour_du_mois, 'rang_dans_mois': rang, 'mode': mode,
            'date_debut': '2026-11-17'}


# (identifiant, saisie, titre attendu, champs attendus hors priorite 0, alertes, repère, porte,
# `dans` de la capture). Repère par défaut : MARDI. Porte par défaut : rapide.
LIGNES = [
    ('A1', 'Appeler Karim demain', 'Appeler Karim', {'jour_prevu': j(18)}),
    ('A2', 'Call Karim tomorrow', 'Call Karim', {'jour_prevu': j(18)}),
    ('A3', 'Envoyer le devis lundi #Polydesign', 'Envoyer le devis',
     {'jour_prevu': j(23), 'projet_id': 3}),
    ('A4', 'Relancer banque lundi prochain', 'Relancer banque', {'jour_prevu': j(23)}),
    ('A5', 'Send invoice next monday', 'Send invoice', {'jour_prevu': j(23)}),
    ('A6', 'Payer CNSS dans 3 jours', 'Payer CNSS', {'jour_prevu': j(20)}),
    ('A7', 'Review contract in 3 days', 'Review contract', {'jour_prevu': j(20)}),
    ('A8', 'Réunion fournisseur 25/11 à 15h', 'Réunion fournisseur',
     {'jour_prevu': j(25), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('A9', 'Rapport TVA fin de mois !!!', 'Rapport TVA',
     {'jour_prevu': j(30), 'priorite': 3}),
    ('A10', 'Rapport TVA pour fin de mois', 'Rapport TVA', {'echeance': j(30)}),
    ('A11', 'Préparer offre ce soir', 'Préparer offre',
     {'jour_prevu': j(17), 'moment': 'soir'}),
    ('A12', 'Lire contrat demain matin', 'Lire contrat',
     {'jour_prevu': j(18), 'moment': 'matin'}),
    ('A13', 'Call supplier at 3pm', 'Call supplier',
     {'jour_prevu': j(17), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('A14', 'Point équipe 9h', 'Point équipe',
     {'jour_prevu': j(18), 'heure_debut': '09:00', 'moment': 'matin'}, ('heure_passee',)),
    ('A15', 'Écrire article 2h', 'Écrire article', {'estimation_minutes': 120}),
    ('A16', 'Trier emails 30 min', 'Trier emails', {'estimation_minutes': 30}),
    ('A17', 'Prepare slides for 2h', 'Prepare slides', {'estimation_minutes': 120}),
    ('A18', 'Dossier subvention pour vendredi', 'Dossier subvention', {'echeance': j(20)}),
    ('A19', 'Finish report due friday 15:00', 'Finish report',
     {'echeance': j(20), 'echeance_heure': '15:00'}),
    ('A20', 'Préparer visite jeudi pour vendredi', 'Préparer visite',
     {'jour_prevu': j(19), 'echeance': j(20)}),
    ('A21', 'Arroser plantes tous les 2 jours', 'Arroser plantes',
     {'jour_prevu': j(17), 'recurrence': rec('quotidien', 2)}),
    ('A22', 'Rapport hebdo chaque lundi #Polydesign', 'Rapport hebdo',
     {'jour_prevu': j(23), 'projet_id': 3, 'recurrence': rec('hebdo', 1, '1000000')}),
    ('A23', 'Check bank every weekday', 'Check bank',
     {'jour_prevu': j(17), 'recurrence': rec('jours_ouvres')}),
    ('A24', 'Payer loyer chaque mois le 5', 'Payer loyer',
     {'jour_prevu': j(5, 12), 'recurrence': rec('mensuel', 1, jour_du_mois=5)}),
    ('A25', 'Changer filtre tous les 3 mois après fait', 'Changer filtre',
     {'jour_prevu': j(17), 'recurrence': rec('mensuel', 3, mode='apres_fait')}),
    ('A26', 'Water plants every! 3 days', 'Water plants',
     {'jour_prevu': j(17), 'recurrence': rec('quotidien', 3, mode='apres_fait')}),
    ('A27', 'Acheter câbles #Maison /Achats %magasin', 'Acheter câbles',
     {'projet_id': 5, 'section_id': 8, 'etiquettes': [{'nom': 'magasin'}]}),
    ('A28', 'Maquette #SiteWeb !!', 'Maquette',
     {'nouveau_projet': {'nom': 'SiteWeb', 'priorite': 2}, 'priorite': 2}),
    ('A29', 'Plan lancement #Nouveau_site p1', 'Plan lancement',
     {'nouveau_projet': {'nom': 'Nouveau site', 'priorite': 2}, 'priorite': 3}),
    ('A30', "Lire « Demain dès l'aube »", "Lire « Demain dès l'aube »", {}),
    ('A31', 'Rappeler Ali 5/6', 'Rappeler Ali', {'jour_prevu': j(5, 6, 2027)}),
    ('A32', 'Meeting 3/1', 'Meeting', {'jour_prevu': j(3, 1, 2027)}),
    ('A33', 'Appeler Karim demain rappel 9h', 'Appeler Karim',
     {'jour_prevu': j(18),
      'rappel': {'ancre': 'jour_prevu', 'decalage_jours': 0, 'heure': '09:00'}}),
    ('A34', 'Envoyer rapport monthly', 'Envoyer rapport monthly', {}),
    ('A35', 'Remise 10% pour facture #12 !', 'Remise 10% pour facture #12 !', {}),
    ('A36', 'Dîner ce soir 9h', 'Dîner',
     {'jour_prevu': j(17), 'heure_debut': '21:00', 'moment': 'soir'}),
    ('A37', "Apprendre l'arabe classique un jour", "Apprendre l'arabe classique",
     {'quelque_jour': True}),
    ('A38', 'Fix bug Nov 25 at 10am', 'Fix bug',
     {'jour_prevu': j(25), 'heure_debut': '10:00', 'moment': 'matin'}),
    ('A39', 'Inventaire ce week-end', 'Inventaire', {'jour_prevu': j(21)}),
    ('E1', 'Email the accountant tomorrow at 9am #Polydesign', 'Email the accountant',
     {'jour_prevu': j(18), 'heure_debut': '09:00', 'moment': 'matin', 'projet_id': 3}),
    ('E2', 'Book flight to London next friday', 'Book flight to London',
     {'jour_prevu': j(20)}),
    ('E3', 'Call Lydec this afternoon', 'Call Lydec',
     {'jour_prevu': j(17), 'moment': 'apres_midi'}),
    ('E4', 'Pay rent every month on the 5', 'Pay rent',
     {'jour_prevu': j(5, 12), 'recurrence': rec('mensuel', 1, jour_du_mois=5)}),
    ('E5', 'Review slides in 2 weeks p2', 'Review slides',
     {'jour_prevu': j(1, 12), 'priorite': 2}),
    ('E6', 'Prepare offer due Nov 30 !!!', 'Prepare offer',
     {'echeance': j(30), 'priorite': 3}),
    ('E7', 'Gym every weekday at 7am', 'Gym',
     {'jour_prevu': j(17), 'heure_debut': '07:00', 'moment': 'matin',
      'recurrence': rec('jours_ouvres')}, ('heure_passee',)),
    ('E8', 'Send quote to Karim by end of week', 'Send quote to Karim',
     {'echeance': j(20)}),
    ('E9', 'Meeting with bank 2026-12-03 at 14:30', 'Meeting with bank',
     {'jour_prevu': j(3, 12), 'heure_debut': '14:30', 'moment': 'apres_midi'}),
    ('E10', 'Appeler Karim tomorrow 10 h', 'Appeler Karim',
     {'jour_prevu': j(18), 'heure_debut': '10:00', 'moment': 'matin'}),
    ('E11', 'Relancer devis Settat tomorrow due friday #Polydesign', 'Relancer devis Settat',
     {'jour_prevu': j(18), 'echeance': j(20), 'projet_id': 3}),
    ('E12', 'Prepare slides for 2h tomorrow morning', 'Prepare slides',
     {'jour_prevu': j(18), 'moment': 'matin', 'estimation_minutes': 120}),
    ('E13', 'Lunch at noon', 'Lunch',
     {'jour_prevu': j(17), 'heure_debut': '12:00', 'moment': 'apres_midi'}),
    ('E14', 'Learn Spanish someday', 'Learn Spanish', {'quelque_jour': True}),
    ('E15', 'Call mum tomorrow remind me at 18:00', 'Call mum',
     {'jour_prevu': j(18),
      'rappel': {'ancre': 'jour_prevu', 'decalage_jours': 0, 'heure': '18:00'}}),
    ('E16', 'Change filter every 3 months', 'Change filter',
     {'jour_prevu': j(17), 'recurrence': rec('mensuel', 3, jour_du_mois=17)}),
    ('P1', 'Réunion 5/6 à 9h', 'Réunion',
     {'jour_prevu': j(5, 6, 2027), 'heure_debut': '09:00', 'moment': 'matin'}),
    ('P2', 'Appel client 15h', 'Appel client',
     {'jour_prevu': j(17), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('P3', 'Réviser 15 min', 'Réviser', {'estimation_minutes': 15}),
    ('P4', 'Atelier pendant 3h', 'Atelier', {'estimation_minutes': 180}),
    ('P5', 'Rapport pour 9h', 'Rapport',
     {'echeance': j(18), 'echeance_heure': '09:00'}, ('heure_passee',)),
    ('P6', 'Rapport pour 6h', 'Rapport', {'estimation_minutes': 360}),
    ('P7', 'Réunion lundi', 'Réunion', {'jour_prevu': j(30)}, (),
     (date(2026, 11, 23), time(10, 0))),
    ('P8', 'Dîner mardi soir', 'Dîner', {'jour_prevu': j(24), 'moment': 'soir'}),
    ('P9', 'Bilan fin de semaine', 'Bilan', {'jour_prevu': j(20)}, (),
     (date(2026, 11, 20), time(10, 0))),
    ('P10', 'Lire Demain dès l\'aube', 'Lire dès l\'aube', {'jour_prevu': j(18)}),
    ('P11', 'Préparer le soir de gala', 'Préparer le soir de gala', {}),
    ('P12', 'Réunion du matin', 'Réunion du matin', {}),
    ('P13', 'Train 6h30 demain', 'Train',
     {'jour_prevu': j(18), 'heure_debut': '06:30', 'moment': 'matin'}),
    ('P14', 'Appel 1h30', 'Appel', {'estimation_minutes': 90}),
    ('P15', 'Appeler aujourd’hui', 'Appeler', {'jour_prevu': j(17)}),
    ('P16', 'Payer le 1er décembre', 'Payer', {'jour_prevu': j(1, 12)}),
    ('P17', 'Payer facture le 31/11', 'Payer facture le 31/11', {}, ('date_invalide',)),
    ('P18', 'Point 10 h 30 demain', 'Point',
     {'jour_prevu': j(18), 'heure_debut': '10:30', 'moment': 'matin'}),
    ('P19', 'Facture #12 pour demain', 'Facture #12', {'echeance': j(18)}),
    ('P20', 'Karim ! demain', 'Karim !', {'jour_prevu': j(18)}),
    ('P21', 'Appeler demain et vendredi', 'Appeler et vendredi',
     {'jour_prevu': j(18)}, ('deux_jour',)),
    ('P22', 'Déjeuner à midi', 'Déjeuner',
     {'jour_prevu': j(17), 'heure_debut': '12:00', 'moment': 'apres_midi'}),
    ('P23', 'Trier emails 2 min', 'Trier emails 2 min', {}, ('duree_hors_bornes',)),
    ('P24', 'Appeler 3pm demain', 'Appeler',
     {'jour_prevu': j(18), 'heure_debut': '15:00', 'moment': 'apres_midi'}),
    ('P25', 'Call May 5', 'Call', {'jour_prevu': j(5, 5, 2027)}),
    ('C1', 'Lait demain #Maison %magasin rappel 9h', 'Lait %magasin rappel',
     {'jour_prevu': j(18), 'heure_debut': '09:00', 'moment': 'matin', 'projet_id': 5},
     (), None, 'capture', 'journee'),
    ('C2', 'Appeler Karim un jour', 'Appeler Karim un jour', {}, (), None, 'capture',
     'a_trier'),
    ('C3', 'Maquette #SiteWeb', 'Maquette #SiteWeb', {}, (), None, 'capture', 'a_trier'),
    ('C4', 'appeler le fournisseur demain 10 h', 'appeler le fournisseur',
     {'jour_prevu': j(18), 'heure_debut': '10:00', 'moment': 'matin'}, (), None,
     'capture', 'journee'),
    ('C5', 'projet Maison acheter du lait demain', 'acheter du lait',
     {'jour_prevu': j(18), 'projet_id': 5}, (), None, 'capture', 'journee'),
    ('C6', 'Rapport pour vendredi', 'Rapport', {'echeance': j(20)}, (), None, 'capture',
     'a_trier'),
]


def _rendre(ligne):
    ident, saisie, titre, champs = ligne[:4]
    alertes = ligne[4] if len(ligne) > 4 else ()
    repere = (ligne[5] if len(ligne) > 5 else None) or MARDI
    porte = ligne[6] if len(ligne) > 6 else 'rapide'
    dans = ligne[7] if len(ligne) > 7 else None
    return ident, saisie, titre, champs, alertes, repere, porte, dans


class TableDeTestTests(unittest.TestCase):
    """Une méthode par ligne de la table (`test_<identifiant>`)."""

    def verifier(self, ligne):
        ident, saisie, titre, champs, alertes, repere, porte, dans = _rendre(ligne)
        analyse = analyser(saisie, repere[0], repere[1], projets=PROJETS,
                           sections=SECTIONS, porte=porte)
        self.assertEqual(analyse.titre, titre, ident)
        self.assertEqual(analyse.champs, {'priorite': 0, **champs}, ident)
        self.assertEqual(set(analyse.alertes), set(alertes), ident)
        self.assertEqual(analyse.erreurs, {}, ident)
        self.verifier_positions(saisie, analyse)
        if dans is not None:
            self.assertEqual(classer_capture(analyse), dans, ident)

    def verifier_positions(self, saisie, analyse):
        """Chaque jeton dit OÙ il a été lu : `debut`/`fin` redonnent `source`, sans chevauchement."""
        fin_precedente = 0
        for jeton in analyse.jetons:
            self.assertEqual(saisie[jeton['debut']:jeton['fin']], jeton['source'])
            self.assertGreaterEqual(jeton['debut'], fin_precedente)
            fin_precedente = jeton['fin']


def _fabriquer(ligne):
    def cas(self):
        self.verifier(ligne)
    cas.__name__ = f'test_{ligne[0]}'
    cas.__doc__ = f'{ligne[0]} — {ligne[1]}'
    return cas


for _ligne in LIGNES:
    setattr(TableDeTestTests, f'test_{_ligne[0]}', _fabriquer(_ligne))


def lire(saisie, repere=MARDI, **kw):
    """`analyser` au repère mardi 17/11/2026 10:00 avec les projets du repère."""
    kw.setdefault('projets', PROJETS)
    kw.setdefault('sections', SECTIONS)
    return analyser(saisie, repere[0], repere[1], **kw)


class SortieEtOptionsTests(unittest.TestCase):
    """Ce que la table ne dit pas : jetons, ignorer, existants, rappel, portes, bornes."""

    def test_jetons_disent_ou_et_quoi(self):
        a = lire('Appeler Karim demain #SiteWeb')
        jour, projet = a.jetons
        self.assertEqual((jour['type'], jour['source'], jour['debut'], jour['fin']),
                         ('jour', 'demain', 14, 20))
        self.assertEqual((jour['valeur'], jour['libelle']), ('2026-11-18', 'mer. 18 nov.'))
        self.assertEqual((projet['type'], projet['debut'], projet['fin']), ('projet', 21, 29))
        self.assertEqual(projet['libelle'], 'Nouveau projet : SiteWeb')
        self.assertEqual(projet['valeur']['priorite'], 2)

    def test_ignorer_remet_le_jeton_dans_le_titre(self):
        a = lire('Appeler Karim demain', ignorer=[{'type': 'jour', 'source': 'demain'}])
        self.assertEqual((a.titre, a.champs, a.jetons),
                         ('Appeler Karim demain', {'priorite': 0}, ()))

    def test_etiquette_existante_par_cle_nom(self):
        a = lire('Acheter %Ma-Gasin %neuve', etiquettes=((2, 'magasin'),))
        self.assertEqual(a.champs['etiquettes'], [2, {'nom': 'neuve'}])
        self.assertEqual(a.titre, 'Acheter')

    def test_plusieurs_projets_le_premier_par_rang(self):
        projets = (ProjetConnu(7, 'Maison', 'actif', 9), ProjetConnu(5, 'Maison', 'actif', 2))
        a = lire('Lait #maison', projets=projets)
        self.assertEqual(a.champs['projet_id'], 5)
        self.assertEqual(a.alertes, ('plusieurs_projets',))

    def test_projet_archive_reste_a_trier(self):
        projets = (ProjetConnu(9, 'Vieux', 'archive', 1),)
        a = lire('Ranger #Vieux', projets=projets)
        self.assertNotIn('projet_id', a.champs)
        self.assertNotIn('nouveau_projet', a.champs)
        self.assertEqual(a.alertes, ('projet_archive',))
        self.assertEqual(a.jetons[0]['libelle'], 'Projet archivé : Vieux')
        self.assertEqual(a.titre, 'Ranger')

    def test_projet_en_pause_est_un_projet_ouvert(self):
        a = lire('Lait #Pause', projets=(ProjetConnu(4, 'Pause', 'en_pause', 1),))
        self.assertEqual(a.champs['projet_id'], 4)

    def test_etape_inconnue_est_creee(self):
        a = lire('Acheter #Maison /Nouvelle')
        self.assertEqual(a.champs['nouvelle_section'], {'nom': 'Nouvelle'})
        self.assertEqual(a.champs['projet_id'], 5)

    def test_etape_sans_projet_reste_du_texte(self):
        a = lire('Acheter /Achats')
        self.assertEqual((a.titre, a.jetons), ('Acheter /Achats', ()))

    def test_titre_vide_est_une_erreur_pas_une_exception(self):
        a = lire('demain')
        self.assertEqual(a.titre, '')
        self.assertEqual(
            a.erreurs, {'titre': ['Le titre est vide une fois la date et le projet retirés.']})

    def test_rappel_avec_sa_propre_date_est_absolu(self):
        a = lire('Appeler Karim rappel demain 9h')
        self.assertEqual(a.champs['rappel'], {'jour': j(18), 'heure': '09:00'})
        self.assertNotIn('jour_prevu', a.champs)
        self.assertEqual(a.titre, 'Appeler Karim')

    def test_rappel_sans_jour_pose_le_jour_prevu(self):
        a = lire('Appeler rappel 9h')
        self.assertEqual(a.champs['rappel'], {'jour': j(18), 'heure': '09:00'})
        self.assertEqual(a.champs['jour_prevu'], j(18))
        b = lire('Appeler rappel 15h')
        self.assertEqual(b.champs['rappel'], {'jour': j(17), 'heure': '15:00'})
        self.assertEqual(b.champs['jour_prevu'], j(17))

    def test_recurrence_prime_sur_le_jour(self):
        a = lire('Appeler demain chaque lundi')
        self.assertEqual(a.champs['jour_prevu'], j(23))
        self.assertEqual(a.titre, 'Appeler demain')
        self.assertEqual(a.alertes, ('deux_jour',))
        self.assertEqual([t['type'] for t in a.jetons], ['recurrence'])

    def test_recurrence_jours_ouvres_lit_est_ouvre_injecte(self):
        def ferie_aujourdhui(d):
            return d.weekday() < 5 and d != date(2026, 11, 17)
        a = lire('Check bank every weekday', est_ouvre=ferie_aujourdhui)
        self.assertEqual(a.champs['jour_prevu'], j(18))

    def test_recurrence_plusieurs_jours_et_libelle(self):
        a = lire('Gym tous les lundis et jeudis')
        self.assertEqual(a.champs['recurrence']['jours_semaine'], '1001000')
        self.assertEqual(a.jetons[0]['libelle'], 'chaque lundi et jeudi')
        self.assertEqual(a.champs['jour_prevu'], j(19))

    def test_recurrence_rang_dans_le_mois(self):
        a = lire('Revue chaque dernier vendredi')
        self.assertEqual(a.champs['recurrence']['rang_dans_mois'], -1)
        self.assertEqual(a.champs['recurrence']['jours_semaine'], '0000100')
        self.assertEqual(a.champs['jour_prevu'], j(27))

    def test_recurrence_intervalle_hors_1_99_non_lu(self):
        a = lire('Payer tous les 100 jours')
        self.assertEqual((a.titre, a.champs), ('Payer tous les 100 jours', {'priorite': 0}))

    def test_capture_ne_lit_ni_recurrence_ni_etape_ni_nouveau_projet(self):
        a = lire('Payer tous les 2 jours #Maison /Achats #Inconnu', porte='capture')
        self.assertEqual(a.titre, 'Payer tous les 2 jours /Achats #Inconnu')
        self.assertEqual(a.champs, {'priorite': 0, 'projet_id': 5})

    def test_capture_projet_en_tete_prend_le_plus_long_nom(self):
        projets = PROJETS + (ProjetConnu(6, 'Maison de campagne', 'actif', 3),)
        a = lire('projet Maison de campagne peindre', projets=projets, porte='capture')
        self.assertEqual((a.titre, a.champs['projet_id']), ('peindre', 6))
        self.assertEqual(a.jetons[0]['source'], 'projet Maison de campagne')

    def test_capture_projet_en_tete_inconnu_reste_du_texte(self):
        a = lire('projet Lune acheter du lait', porte='capture')
        self.assertEqual((a.titre, a.champs), ('projet Lune acheter du lait', {'priorite': 0}))

    def test_rien_n_est_lu_entre_guillemets(self):
        for saisie in ('Lire "demain" tard', 'Lire «demain» tard', 'Lire “demain” tard'):
            with self.subTest(saisie=saisie):
                a = lire(saisie)
                self.assertEqual((a.titre, a.champs, a.jetons), (saisie, {'priorite': 0}, ()))

    def test_une_phrase_incomprise_ne_leve_jamais(self):
        for saisie in ('', ' ', '!!!!', '#', '%', '/', '«', '"demain', '31/02', 'p12 p0',
                       '10%', '#12', '25h', '99:99', 'à 24h', 'x' * 400, 'İ ẞ œ æ demain'):
            with self.subTest(saisie=saisie):
                a = lire(saisie)
                for jeton in a.jetons:
                    self.assertEqual(saisie[jeton['debut']:jeton['fin']], jeton['source'])

    def test_aujourdhui_et_maintenant_sont_des_parametres(self):
        a = analyser('Appeler demain à 9h', date(2030, 5, 3), time(23, 0))
        self.assertEqual(a.champs['jour_prevu'], '2030-05-04')
        self.assertEqual(a.alertes, ())

    def test_maintenant_accepte_un_datetime(self):
        a = analyser('Appel 9h', date(2026, 11, 17), datetime(2026, 11, 17, 10, 0))
        self.assertEqual((a.champs['jour_prevu'], a.alertes), (j(18), ('heure_passee',)))

    def test_date_avec_annee_passee_garde_la_date_et_alerte(self):
        a = lire('Archiver 05/06/2025')
        self.assertEqual(a.champs['jour_prevu'], '2025-06-05')
        self.assertEqual(a.alertes, ('date_passee',))

    def test_heure_passee_aujourdhui_garde_le_jour(self):
        a = lire("Appeler aujourd'hui à 9h")
        self.assertEqual((a.champs['jour_prevu'], a.alertes), (j(17), ('heure_passee',)))

    def test_duree_hors_bornes_pendant_20h(self):
        a = lire('Route pendant 20h')
        self.assertEqual((a.titre, a.alertes), ('Route pendant 20h', ('duree_hors_bornes',)))

    def test_deux_priorites_la_seconde_reste_du_texte(self):
        a = lire('Appeler !! p1')
        self.assertEqual((a.titre, a.champs['priorite'], a.alertes),
                         ('Appeler p1', 2, ('deux_priorite',)))


if __name__ == '__main__':
    unittest.main()
