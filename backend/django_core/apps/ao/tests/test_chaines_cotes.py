"""AOF23 — chaînes de cotes, fermetures, statut porté par la DONNÉE.

Cas ÉCOLE reproduit à l'identique : 51,10 − (19,36 + 7,92 + 4,50 + 10,50) =
8,82 m déduits, alors que le terrain annonçait « ≈ 8,5 ». La règle métier
gravée veut que la valeur DÉDUITE d'une fermeture exacte PRIME sur la valeur
annoncée arrondie et bascule en ``A_CONFIRMER`` — et que l'écart de 0,32 m se
PUBLIE au lieu d'être gommé.

Les autres invariants :
  * la tolérance est PAR CHAÎNE (0,02 à 0,30 m constatés) — pas globale ;
  * les résidus sont CALCULÉS et PERSISTÉS (le rapport doit les citer) ;
  * la compensation au prorata est PROPOSÉE, jamais appliquée en silence.

Run :
    python manage.py test apps.ao.tests.test_chaines_cotes -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, ChaineCotes, StatutCote, ToitureAO,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/chaines-cotes/'

#: Le cas ÉCOLE : quatre segments mesurés + un cinquième annoncé « ≈ 8,5 ».
SEGMENTS_ECOLE = [
    {'libelle': 'A→B', 'valeur_m': 19.36, 'statut': 'MESURE'},
    {'libelle': 'B→C', 'valeur_m': 7.92, 'statut': 'MESURE'},
    {'libelle': 'C→D', 'valeur_m': 4.50, 'statut': 'MESURE'},
    {'libelle': 'D→E', 'valeur_m': 10.50, 'statut': 'MESURE'},
    {'libelle': 'E→F', 'valeur_m': 8.50, 'statut': 'PLAN_OU_DEDUIT'},
]


class TestStatutCote(SimpleTestCase):
    def test_trois_statuts_portes_par_la_donnee(self):
        valeurs = {v for v, _ in StatutCote.choices}
        self.assertEqual(valeurs,
                         {'MESURE', 'A_CONFIRMER', 'PLAN_OU_DEDUIT'})


class TestFermeture(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF23 Co', slug='aof23-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-23-1', objet='Cotes')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def _chaine(self, segments, totale='51.100', tolerance='0.050'):
        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture,
            libelle='Façade sud', segments=[dict(s) for s in segments],
            mesure_totale_m=Decimal(totale),
            tolerance_m=Decimal(tolerance))
        chaine.recalculer_fermeture()
        chaine.save()
        return chaine

    def test_somme_des_segments(self):
        chaine = self._chaine(SEGMENTS_ECOLE)
        self.assertEqual(chaine.somme_segments_m, Decimal('50.780'))

    def test_residu_en_metres_et_en_pourcent(self):
        chaine = self._chaine(SEGMENTS_ECOLE)
        self.assertEqual(chaine.residu_m, Decimal('0.320'))
        self.assertEqual(chaine.residu_pct, Decimal('0.626'))
        self.assertEqual(chaine.verdict, ChaineCotes.Verdict.ECART)

    def test_tolerance_par_chaine(self):
        """0,05 m → écart ; 0,30 m → OK. La tolérance N'EST PAS globale."""
        serree = self._chaine(SEGMENTS_ECOLE, tolerance='0.050')
        self.assertEqual(serree.verdict, ChaineCotes.Verdict.ECART)
        large = self._chaine(SEGMENTS_ECOLE, tolerance='0.300')
        self.assertEqual(large.verdict, ChaineCotes.Verdict.OK)

    def test_chaine_sans_mesure_totale_est_incomplete(self):
        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, libelle='Sans total',
            segments=[dict(s) for s in SEGMENTS_ECOLE])
        chaine.recalculer_fermeture()
        self.assertEqual(chaine.verdict, ChaineCotes.Verdict.INCOMPLETE)
        self.assertIsNone(chaine.residu_m)

    def test_residus_persistes(self):
        chaine = self._chaine(SEGMENTS_ECOLE)
        chaine.refresh_from_db()
        self.assertEqual(chaine.residu_m, Decimal('0.320'))
        self.assertEqual(chaine.verdict, 'ecart')


class TestDeductionPrimeSurAnnonce(TestCase):
    """Le cas ÉCOLE : 8,82 déduits contre « ≈ 8,5 » annoncé."""

    def setUp(self):
        self.company = Company.objects.create(nom='AOF23 De', slug='aof23-de')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-23-D', objet='Déduction')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)
        self.chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, libelle='Façade sud',
            segments=[dict(s) for s in SEGMENTS_ECOLE],
            mesure_totale_m=Decimal('51.100'))
        services.recalculer_chaine(self.chaine)

    def test_valeur_deduite_882(self):
        services.deduire_segment(self.chaine, 4)
        self.chaine.refresh_from_db()
        self.assertEqual(self.chaine.segments[4]['valeur_m'], 8.82)

    def test_la_valeur_annoncee_est_conservee(self):
        services.deduire_segment(self.chaine, 4)
        self.chaine.refresh_from_db()
        self.assertEqual(self.chaine.segments[4]['valeur_annoncee_m'], 8.5)

    def test_bascule_automatique_en_a_confirmer(self):
        services.deduire_segment(self.chaine, 4)
        self.chaine.refresh_from_db()
        self.assertEqual(self.chaine.segments[4]['statut'], 'A_CONFIRMER')
        self.assertTrue(self.chaine.segments[4]['deduit'])

    def test_la_fermeture_devient_exacte(self):
        services.deduire_segment(self.chaine, 4)
        self.chaine.refresh_from_db()
        self.assertEqual(self.chaine.residu_m, Decimal('0.000'))
        self.assertEqual(self.chaine.verdict, ChaineCotes.Verdict.OK)

    def test_l_ecart_reste_publiable(self):
        """0,32 m d'écart : la donnée doit permettre de le CITER."""
        avant = self.chaine.residu_m
        services.deduire_segment(self.chaine, 4)
        self.chaine.refresh_from_db()
        annoncee = Decimal(str(self.chaine.segments[4]['valeur_annoncee_m']))
        deduite = Decimal(str(self.chaine.segments[4]['valeur_m']))
        self.assertEqual(avant, Decimal('0.320'))
        self.assertEqual(deduite - annoncee, Decimal('0.32'))

    def test_la_liste_des_cotes_a_confirmer_en_derive(self):
        services.deduire_segment(self.chaine, 4)
        self.chaine.refresh_from_db()
        a_confirmer = self.chaine.cotes_a_confirmer
        self.assertEqual(len(a_confirmer), 1)
        self.assertEqual(a_confirmer[0]['libelle'], 'E→F')

    def test_deduction_journalisee(self):
        from apps.records.services import chatter_qs

        services.deduire_segment(self.chaine, 4)
        entrees = list(chatter_qs(self.ao, company=self.company))
        self.assertEqual(len(entrees), 1)
        self.assertEqual(entrees[0].new_value, '8.820')

    def test_sans_mesure_totale_la_deduction_est_refusee(self):
        nue = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, libelle='Sans total',
            segments=[dict(s) for s in SEGMENTS_ECOLE])
        with self.assertRaises(ValidationError) as ctx:
            services.deduire_segment(nue, 0)
        self.assertIn('mesure_totale_m', ctx.exception.message_dict)

    def test_index_hors_bornes_refuse(self):
        with self.assertRaises(ValidationError):
            services.deduire_segment(self.chaine, 99)


class TestCompensationProposeeJamaisAppliquee(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF23 Cp', slug='aof23-cp')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-23-C', objet='Compensation')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='C')
        toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)
        self.chaine = ChaineCotes.objects.create(
            company=self.company, toiture=toiture, libelle='Façade sud',
            segments=[dict(s) for s in SEGMENTS_ECOLE],
            mesure_totale_m=Decimal('51.100'))
        services.recalculer_chaine(self.chaine)

    def test_la_proposition_couvre_tous_les_segments(self):
        proposition = services.proposer_compensation_prorata(self.chaine)
        self.assertIsNotNone(proposition)
        self.assertEqual(len(proposition['segments']), 5)
        self.assertFalse(proposition['applique'])

    def test_la_proposition_ne_modifie_rien(self):
        avant = [dict(s) for s in self.chaine.segments]
        services.proposer_compensation_prorata(self.chaine)
        self.chaine.refresh_from_db()
        self.assertEqual(self.chaine.segments, avant)
        self.assertEqual(self.chaine.residu_m, Decimal('0.320'))

    def test_repartition_au_prorata(self):
        proposition = services.proposer_compensation_prorata(self.chaine)
        total_delta = sum(s['delta_m'] for s in proposition['segments'])
        self.assertAlmostEqual(total_delta, 0.320, places=2)
        premier = proposition['segments'][0]
        self.assertGreater(premier['delta_m'],
                           proposition['segments'][2]['delta_m'])

    def test_aucune_proposition_sans_residu(self):
        services.deduire_segment(self.chaine, 4)
        self.chaine.refresh_from_db()
        self.assertIsNone(
            services.proposer_compensation_prorata(self.chaine))


class TestApiChaines(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF23 API', slug='aof23-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof23_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-23-API', objet='API')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def test_creation_calcule_la_fermeture(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'libelle': 'Façade sud', 'axe': 'x',
            'segments': SEGMENTS_ECOLE, 'mesure_totale_m': '51.100',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['residu_m'], '0.320')
        self.assertEqual(r.data['verdict'], 'ecart')

    def test_action_deduire(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'libelle': 'Façade sud',
            'segments': SEGMENTS_ECOLE, 'mesure_totale_m': '51.100',
        }, format='json')
        chaine_id = r.data['id']
        r2 = self.api.post(f'{URL}{chaine_id}/deduire/', {'index': 4},
                           format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['segments'][4]['valeur_m'], 8.82)
        self.assertEqual(r2.data['residu_m'], '0.000')
        self.assertEqual(len(r2.data['cotes_a_confirmer']), 1)

    def test_action_compensation_ne_modifie_rien(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'libelle': 'Façade sud',
            'segments': SEGMENTS_ECOLE, 'mesure_totale_m': '51.100',
        }, format='json')
        chaine_id = r.data['id']
        r2 = self.api.get(f'{URL}{chaine_id}/compensation/')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertFalse(r2.data['applique'])
        chaine = ChaineCotes.objects.get(id=chaine_id)
        self.assertEqual(chaine.residu_m, Decimal('0.320'))

    def test_deduire_sans_index_refuse(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'libelle': 'X',
            'segments': SEGMENTS_ECOLE, 'mesure_totale_m': '51.100',
        }, format='json')
        r2 = self.api.post(f'{URL}{r.data["id"]}/deduire/', {}, format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn('index', r2.data)
