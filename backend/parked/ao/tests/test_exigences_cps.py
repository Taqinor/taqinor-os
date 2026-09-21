"""AOF14 — ``ExigenceCPS`` : les clauses du CPS deviennent des DONNÉES.

Constat marché encodé ici : le cautionnement DÉFINITIF est un TAUX du montant
initial (3 %) alors que le PROVISOIRE est un MONTANT ABSOLU fixé par le CPS
(10 000 / 25 000 / 30 000 / 50 000 DH). Le provisoire n'est donc JAMAIS
calculable depuis le montant de l'offre — c'est une clause paramétrable, pas
une formule.

Invariant de non-duplication : AUCUNE exigence d'ASSURANCE ici. ``NTASS19`` est
livré, ``apps.assurances.ExigenceAssuranceMarche`` possède ces exigences et se
rattache à l'AO par sa string-FK ``marche_ref``. Un test d'introspection
échoue si un champ d'assurance apparaît sur ``ExigenceCPS``.

Run :
    python manage.py test apps.ao.tests.test_exigences_cps -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import CLAUSES_REFERENCE_CPS, AppelOffre, ExigenceCPS
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/exigences-cps/'

FRAGMENTS_ASSURANCE = (
    'assurance', 'police', 'couverture', 'assureur', 'courtier', 'sinistre',
)


def charger_clauses_reference(company, appel_offre):
    """Fixture reproductible : le jeu de clauses de référence sur un AO."""
    return [
        ExigenceCPS.objects.create(
            company=company, appel_offre=appel_offre, **clause)
        for clause in (dict(c) for c in CLAUSES_REFERENCE_CPS)
    ]


class TestModeleExigenceCPS(SimpleTestCase):
    def test_types_d_exigence_couvrent_les_clauses_chiffrees(self):
        valeurs = {v for v, _ in ExigenceCPS.TypeExigence.choices}
        for attendu in ('ratio_dc_ac', 'puissance_onduleur_max',
                        'caution_provisoire', 'caution_definitive_taux',
                        'validite_offre', 'penalite_retard',
                        'piece_administrative', 'reference_normative'):
            self.assertIn(attendu, valeurs, attendu)

    def test_aucun_champ_d_assurance(self):
        """NTASS19 possède déjà les exigences d'assurance — pas de doublon."""
        fautifs = []
        for champ in list(ExigenceCPS._meta.local_fields):
            nom = champ.name.lower()
            for fragment in FRAGMENTS_ASSURANCE:
                if fragment in nom:
                    fautifs.append(champ.name)
                    break
        self.assertEqual(
            fautifs, [],
            "Les exigences d'assurance vivent dans apps.assurances "
            "(ExigenceAssuranceMarche, rattachée par marche_ref) — jamais "
            f"dupliquées ici. Champs fautifs : {fautifs}")

    def test_la_source_documentaire_est_modelisee(self):
        noms = {f.name for f in ExigenceCPS._meta.local_fields}
        self.assertIn('source_piece', noms)
        self.assertIn('source_page', noms)
        self.assertIn('bloquant', noms)


class TestJeuDeClausesReference(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF14 Co', slug='aof14-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-14-1', objet='Toitures')

    def test_fixture_reproductible(self):
        clauses = charger_clauses_reference(self.company, self.ao)
        self.assertEqual(len(clauses), len(CLAUSES_REFERENCE_CPS))
        self.assertEqual(self.ao.exigences_cps.count(),
                         len(CLAUSES_REFERENCE_CPS))

    def test_ratio_dc_ac_est_un_intervalle(self):
        charger_clauses_reference(self.company, self.ao)
        ratio = self.ao.exigences_cps.get(code='RATIO_DC_AC')
        self.assertEqual(ratio.valeur_num, Decimal('0.7500'))
        self.assertEqual(ratio.valeur_max_num, Decimal('1.0000'))
        self.assertTrue(ratio.est_intervalle)
        self.assertEqual(ratio.source_page, 33)

    def test_plafond_onduleur_60_kwc(self):
        charger_clauses_reference(self.company, self.ao)
        plafond = self.ao.exigences_cps.get(code='ONDULEUR_KWC_MAX')
        self.assertEqual(plafond.valeur_num, Decimal('60.0000'))
        self.assertEqual(plafond.unite, 'kWc')
        self.assertFalse(plafond.est_intervalle)

    def test_les_deux_regimes_de_caution_sont_distincts(self):
        charger_clauses_reference(self.company, self.ao)
        provisoire = self.ao.exigences_cps.get(code='CAUTION_PROVISOIRE')
        definitive = self.ao.exigences_cps.get(code='CAUTION_DEFINITIVE_TAUX')
        # Le provisoire est un MONTANT ABSOLU (jamais un taux, jamais dérivé
        # du montant de l'offre) ; le définitif est un TAUX.
        self.assertEqual(provisoire.unite, 'MAD')
        self.assertEqual(
            provisoire.type_exigence,
            ExigenceCPS.TypeExigence.CAUTION_PROVISOIRE)
        self.assertEqual(definitive.unite, '%')
        self.assertEqual(definitive.valeur_num, Decimal('3.0000'))

    def test_code_unique_par_appel_offre(self):
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='DOUBLON',
            libelle='Première')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ExigenceCPS.objects.create(
                company=self.company, appel_offre=self.ao, code='DOUBLON',
                libelle='Seconde')

    def test_meme_code_possible_sur_un_autre_ao(self):
        autre = AppelOffre.objects.create(
            company=self.company, reference='AO-14-2', objet='Autre')
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao, code='RATIO_DC_AC',
            libelle='Ratio')
        ExigenceCPS.objects.create(
            company=self.company, appel_offre=autre, code='RATIO_DC_AC',
            libelle='Ratio')
        self.assertEqual(
            ExigenceCPS.objects.filter(code='RATIO_DC_AC').count(), 2)


class TestApiExigencesCPS(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF14 API', slug='aof14-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof14_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-14-API', objet='API')

    def _lignes(self, resp):
        data = resp.data
        return data['results'] if isinstance(data, dict) and 'results' in data \
            else data

    def test_crud_scope_societe(self):
        r = self.api.post(URL, {
            'appel_offre': self.ao.id, 'code': 'RATIO_DC_AC',
            'libelle': 'Ratio DC/AC', 'type_exigence': 'ratio_dc_ac',
            'valeur_num': '0.75', 'valeur_max_num': '1.00',
            'source_piece': 'CPS', 'source_page': 33,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        exigence = ExigenceCPS.objects.get(id=r.data['id'])
        self.assertEqual(exigence.company_id, self.company.id)
        self.assertTrue(r.data['est_intervalle'])

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF14 Autre', slug='aof14-autre')
        ao_autre = AppelOffre.objects.create(
            company=autre, reference='AO-14-X', objet='Autre société')
        ExigenceCPS.objects.create(
            company=autre, appel_offre=ao_autre, code='X', libelle='X')
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._lignes(r), [])

    def test_filtre_par_appel_offre_et_par_type(self):
        charger_clauses_reference(self.company, self.ao)
        r = self.api.get(URL, {'appel_offre': self.ao.id,
                               'type_exigence': 'caution_provisoire'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = self._lignes(r)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['code'], 'CAUTION_PROVISOIRE')
