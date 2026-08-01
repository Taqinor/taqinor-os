"""AOF111 — contexte de dossier unique, empreinte et péremption d'artefact.

Tests PURS (aucune base, aucun Django) :
    python -m unittest apps.ao.tests.test_aof_contexte -v
"""
import unittest
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType

from apps.ao.fabrique import contexte as ctx
from apps.ao.fabrique import empreinte as emp


def dossier_frdisi():
    """Le dossier RÉEL du 27/07 — les montants sont ceux du bordereau final."""
    return {
        'identite': {
            'raison_sociale': 'TAQINOR SARL', 'ice': '002345678000091',
            'rc': '123456', 'if_fiscal': '55667788', 'ville': 'Casablanca',
            'signataire': 'Reda Kasri', 'qualite_signataire': 'Gérant',
        },
        'acheteur': {'nom': 'FRDISI', 'ville': 'Casablanca'},
        'marche': {
            'objet': "Fourniture et installation d'une centrale "
                     'photovoltaïque en toiture',
            'reference_acheteur': 'AO 12/2026', 'type_prix': 'unitaires',
            'validite_offre_jours': 75,
        },
        'batiments': [
            {'code': 'A', 'libelle': 'Aile en L', 'ville': 'Casablanca'},
            {'code': 'B', 'libelle': 'Résidence arc', 'ville': 'Casablanca'},
            {'code': 'C', 'libelle': 'École', 'ville': 'Casablanca'},
        ],
        'calepinage': [
            {'batiment': 'A', 'compte_retenu': 152},
            {'batiment': 'B', 'compte_retenu': 120},
            {'batiment': 'C', 'compte_retenu': 288},
        ],
        'equipements': [
            {'role': 'module', 'designation': 'Module 625 Wc', 'quantite': 560},
        ],
        'montants': {
            'sous_total_ht': Decimal('4166600'),
            'total_ht': Decimal('4166600'), 'taux_tva': Decimal('20'),
            'tva': Decimal('833320'), 'total_ttc': Decimal('4999920'),
        },
        'clauses': {'reserve_quantites': 'Les quantités du présent bordereau…'},
        'dates': {'remise_offre': date(2026, 8, 20)},
        'engagements': [{'batiment': 'A', 'modules': 152}],
    }


class TestConstruction(unittest.TestCase):

    def test_contexte_gele_en_profondeur(self):
        c = ctx.construire_contexte(dossier_frdisi())
        self.assertTrue(ctx.est_gele(c))
        self.assertIsInstance(c, MappingProxyType)
        with self.assertRaises(TypeError):
            c['montants'] = {}
        with self.assertRaises(TypeError):
            c['montants']['total_ttc'] = Decimal('1')
        with self.assertRaises(AttributeError):
            c['batiments'].append({'code': 'D'})

    def test_toutes_les_sections_sont_presentes(self):
        c = ctx.construire_contexte(dossier_frdisi())
        for section in ctx.SECTIONS:
            self.assertIn(section, c, section)
        self.assertEqual(c['version_contexte'], ctx.VERSION_CONTEXTE)

    def test_aucune_section_hors_perimetre(self):
        """TRIPWIRE : une section non classée ferait une empreinte aveugle."""
        c = ctx.construire_contexte(dossier_frdisi())
        self.assertEqual(emp.cles_hors_perimetre(c), ())

    def test_montants_en_decimal_jamais_en_float(self):
        c = ctx.construire_contexte(dossier_frdisi())
        for cle, val in c['montants'].items():
            if cle == 'devise':
                continue
            self.assertIsInstance(val, Decimal, cle)

    def test_montants_acceptent_une_chaine_sans_perdre_le_centime(self):
        d = dossier_frdisi()
        d['montants']['total_ttc'] = '4999920.07'
        c = ctx.construire_contexte(d)
        self.assertEqual(c['montants']['total_ttc'], Decimal('4999920.07'))

    def test_refuse_une_cle_de_cout_dans_les_montants(self):
        """L'économie est RÉSERVÉE au directeur : elle n'entre pas ici."""
        for interdite in ('cout_revient', 'marge', 'benefice', 'prix_achat'):
            d = dossier_frdisi()
            d['montants'][interdite] = Decimal('1500000')
            with self.assertRaises(ctx.ContexteIncomplet, msg=interdite):
                ctx.construire_contexte(d)

    def test_strict_exige_les_donnees_qui_feraient_mentir_une_piece(self):
        d = dossier_frdisi()
        d['montants']['total_ttc'] = None
        with self.assertRaises(ctx.ContexteIncomplet):
            ctx.construire_contexte(d, strict=True)
        # Sans strict, la construction passe : la pièce qui en a besoin
        # échouera à SON niveau, pas ici.
        self.assertIsNone(
            ctx.construire_contexte(d)['montants']['total_ttc'])


class TestReproductibilite(unittest.TestCase):

    def test_deux_constructions_identiques(self):
        a = ctx.construire_contexte(dossier_frdisi())
        b = ctx.construire_contexte(dossier_frdisi())
        self.assertEqual(a['empreinte'], b['empreinte'])

    def test_horodatage_et_operateur_ne_periment_rien(self):
        a = ctx.construire_contexte(dossier_frdisi(),
                                    genere_le=datetime(2026, 8, 1, 9, 0),
                                    genere_par='reda')
        b = ctx.construire_contexte(dossier_frdisi(),
                                    genere_le=datetime(2026, 8, 2, 18, 30),
                                    genere_par='sami')
        self.assertEqual(a['empreinte'], b['empreinte'])

    def test_ordre_des_cles_sans_effet(self):
        d = dossier_frdisi()
        inverse = {cle: d[cle] for cle in reversed(list(d))}
        self.assertEqual(ctx.construire_contexte(d)['empreinte'],
                         ctx.construire_contexte(inverse)['empreinte'])

    def test_decimal_normalise(self):
        """2600 et 2600.00 sont le MÊME montant — même empreinte."""
        d1, d2 = dossier_frdisi(), dossier_frdisi()
        d1['montants']['total_ttc'] = Decimal('4999920')
        d2['montants']['total_ttc'] = Decimal('4999920.00')
        self.assertEqual(ctx.construire_contexte(d1)['empreinte'],
                         ctx.construire_contexte(d2)['empreinte'])

    def test_empreinte_stable_hexadecimale(self):
        c = ctx.construire_contexte(dossier_frdisi())
        self.assertEqual(len(c['empreinte']), 64)
        int(c['empreinte'], 16)  # lève si ce n'est pas de l'hexadécimal


class TestDivergence(unittest.TestCase):

    def test_un_chiffre_permute_change_l_empreinte(self):
        """Le défaut réel : 5 143 680 tapé pour 5 413 680."""
        d = dossier_frdisi()
        a = ctx.construire_contexte(d)
        d['montants']['total_ttc'] = Decimal('5143680')
        b = ctx.construire_contexte(d)
        self.assertNotEqual(a['empreinte'], b['empreinte'])
        self.assertEqual(emp.sections_divergentes(a, b), ('montants',))

    def test_un_module_de_plus_change_l_empreinte(self):
        d = dossier_frdisi()
        a = ctx.construire_contexte(d)
        d['calepinage'][2]['compte_retenu'] = 314
        b = ctx.construire_contexte(d)
        self.assertNotEqual(a['empreinte'], b['empreinte'])
        self.assertEqual(emp.sections_divergentes(a, b), ('calepinage',))

    def test_un_centime_change_l_empreinte(self):
        d = dossier_frdisi()
        a = ctx.construire_contexte(d)
        d['montants']['total_ttc'] = Decimal('4999920.01')
        self.assertNotEqual(a['empreinte'],
                            ctx.construire_contexte(d)['empreinte'])


class TestArtefact(unittest.TestCase):

    def test_artefact_frais_puis_perime(self):
        d = dossier_frdisi()
        c = ctx.construire_contexte(d)
        piece = emp.estampiller(c, 'bordereau', format='pdf')
        self.assertFalse(piece.est_perime(c))
        piece.verifier(c)

        d['montants']['total_ttc'] = Decimal('5219280')  # le bordereau frère
        c2 = ctx.construire_contexte(d)
        self.assertTrue(piece.est_perime(c2))
        with self.assertRaises(emp.ArtefactPerime):
            piece.verifier(c2)

    def test_rafraichi_reprend_l_empreinte_courante(self):
        d = dossier_frdisi()
        piece = emp.estampiller(ctx.construire_contexte(d), 'lettre')
        d['montants']['total_ttc'] = Decimal('5219280')
        c2 = ctx.construire_contexte(d)
        self.assertFalse(piece.rafraichi(c2).est_perime(c2))

    def test_artefacts_perimes_liste_les_pieces_a_regenerer(self):
        d = dossier_frdisi()
        c = ctx.construire_contexte(d)
        pieces = [emp.estampiller(c, code) for code in
                  ('bordereau', 'lettre', 'acte')]
        self.assertEqual(emp.artefacts_perimes(pieces, c), ())
        d['montants']['total_ht'] = Decimal('4000000')
        c2 = ctx.construire_contexte(d)
        self.assertEqual(len(emp.artefacts_perimes(pieces, c2)), 3)


class TestReconstruction(unittest.TestCase):

    def test_reconstruire_ne_touche_pas_l_ancien(self):
        c = ctx.construire_contexte(dossier_frdisi())
        avant = c['empreinte']
        c2 = ctx.reconstruire(c, montants=dict(c['montants'],
                                               total_ttc=Decimal('1')))
        self.assertEqual(c['empreinte'], avant)
        self.assertNotEqual(c2['empreinte'], avant)

    def test_reconstruire_a_l_identique_redonne_la_meme_empreinte(self):
        c = ctx.construire_contexte(dossier_frdisi())
        self.assertEqual(ctx.reconstruire(c)['empreinte'], c['empreinte'])


class TestLecture(unittest.TestCase):

    def test_chemin_pointe(self):
        c = ctx.construire_contexte(dossier_frdisi())
        self.assertEqual(ctx.valeur(c, 'montants.total_ttc'),
                         Decimal('4999920'))
        self.assertEqual(ctx.valeur(c, 'batiments.2.code'), 'C')

    def test_chemin_inconnu_leve(self):
        c = ctx.construire_contexte(dossier_frdisi())
        with self.assertRaises(ctx.CleInconnue):
            ctx.valeur(c, 'montants.total_avec_remise')
        self.assertEqual(ctx.valeur(c, 'montants.inexistant', None), None)

    def test_cles_disponibles_publie_les_chemins(self):
        chemins = ctx.cles_disponibles(ctx.construire_contexte(dossier_frdisi()))
        self.assertIn('montants.total_ttc', chemins)
        self.assertIn('identite.raison_sociale', chemins)
        self.assertIn('batiments.0.code', chemins)


class TestLitterauxDeGabarit(unittest.TestCase):

    def test_un_montant_en_dur_est_detecte(self):
        self.assertTrue(litteraux('<p>Total : 4 999 920,00 DH</p>'))
        self.assertTrue(litteraux('<p>Validité 75 jours</p>'))

    def test_une_reference_de_contexte_ne_l_est_pas(self):
        self.assertEqual(
            litteraux('<p>Total : {{ montants.total_ttc }}</p>'), ())
        self.assertEqual(
            litteraux('{% if montants.remise %}Remise{% endif %}'), ())

    def test_les_normes_et_formats_sont_toleres(self):
        self.assertEqual(litteraux('Conforme NF C 15-100, papier A4'), ())


def litteraux(texte):
    return ctx.litteraux_chiffres(texte)


if __name__ == '__main__':
    unittest.main()
