"""AOF5 — référence AO auto (``core.numbering``) + ``reference_acheteur``.

Constat : ``AppelOffre`` portait déjà ``UniqueConstraint(company, reference)``
mais AUCUNE génération automatique, et le dépôt a déjà payé une collision de
production sur ``count() + 1`` (une suppression fait rétrécir le compte alors
que le plus haut numéro utilisé, lui, reste).

Invariants verrouillés ici :
  1. création sans référence → ``AO-YYYYMM-0001`` puis ``-0002`` ;
  2. après suppression du dernier, le suivant est ``-0003`` — JAMAIS ``-0002``
     (le bug ``count() + 1``) ;
  3. une course (``IntegrityError`` sur la référence) est absorbée : le perdant
     prend simplement le numéro suivant, aucune exception ne remonte ;
  4. une référence explicitement fournie est RESPECTÉE (reprise de dossier) ;
  5. la référence de l'acheteur est un champ DISTINCT, visible et filtrable,
     qui n'entre jamais dans notre séquence ;
  6. les séquences sont scopées société.

Run :
    python manage.py test apps.ao.tests.test_numerotation_ao -v2
"""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import AppelOffre
from apps.ao.services import creer_appel_offre_avec_reference
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

MOTIF_REFERENCE = re.compile(r'^AO-\d{6}-\d{4}$')
URL = '/api/django/ao/appels-offres/'


class TestNumerotationService(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF5 Co', slug='aof5-co')

    def _creer(self, **kwargs):
        return creer_appel_offre_avec_reference(
            self.company,
            lambda reference: AppelOffre.objects.create(
                company=self.company, reference=reference, **kwargs),
        )

    def test_format_et_incrementation(self):
        premier = self._creer(objet='Premier')
        second = self._creer(objet='Second')
        self.assertRegex(premier.reference, MOTIF_REFERENCE)
        self.assertTrue(premier.reference.endswith('-0001'), premier.reference)
        self.assertTrue(second.reference.endswith('-0002'), second.reference)

    def test_suppression_ne_recycle_jamais_un_numero(self):
        """Le bug historique ``count() + 1`` : un trou ne se rebouche pas."""
        self._creer(objet='A')
        second = self._creer(objet='B')
        second.delete()
        troisieme = self._creer(objet='C')
        self.assertTrue(
            troisieme.reference.endswith('-0003'), troisieme.reference)

    def test_course_absorbee_sans_collision(self):
        """Le perdant d'une course prend le numéro suivant, sans exception."""
        self._creer(objet='Existant')
        appels = {'n': 0}
        vrai_create = AppelOffre.objects.create

        def save_fn(reference):
            appels['n'] += 1
            if appels['n'] == 1:
                raise IntegrityError(
                    'duplicate key value violates unique constraint '
                    '"uniq_appel_offre_reference" (reference)')
            return vrai_create(
                company=self.company, reference=reference, objet='Course')

        obj = creer_appel_offre_avec_reference(self.company, save_fn)
        self.assertEqual(appels['n'], 2)
        self.assertRegex(obj.reference, MOTIF_REFERENCE)

    def test_sequence_scopee_societe(self):
        autre = Company.objects.create(nom='AOF5 Autre', slug='aof5-autre')
        self._creer(objet='Chez nous')
        chez_eux = creer_appel_offre_avec_reference(
            autre,
            lambda reference: AppelOffre.objects.create(
                company=autre, reference=reference, objet='Chez eux'),
        )
        self.assertTrue(chez_eux.reference.endswith('-0001'),
                        chez_eux.reference)

    def test_jamais_de_count_plus_un(self):
        """Garde-fou explicite : le service passe par ``core.numbering``."""
        with mock.patch('apps.ao.services.create_with_reference') as fabrique:
            fabrique.return_value = 'sentinelle'
            resultat = creer_appel_offre_avec_reference(
                self.company, lambda reference: None)
        self.assertEqual(resultat, 'sentinelle')
        self.assertEqual(fabrique.call_args[0][0], AppelOffre)
        self.assertEqual(fabrique.call_args[0][1], 'AO')


class TestNumerotationAPI(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF5 API', slug='aof5-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof5_dir', password='x', company=self.company, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_creation_sans_reference_genere_la_notre(self):
        r = self.api.post(
            URL, {'objet': 'Centrale PV 500 kWc'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertRegex(r.data['reference'], MOTIF_REFERENCE)

    def test_reference_fournie_est_respectee(self):
        r = self.api.post(URL, {
            'objet': 'Dossier repris', 'reference': 'AO-HISTO-42',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['reference'], 'AO-HISTO-42')

    def test_les_deux_references_sont_visibles_et_distinctes(self):
        r = self.api.post(URL, {
            'objet': 'Lot 3 — photovoltaïque',
            'reference_acheteur': 'AOO N° 12/2026/DRE',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['reference_acheteur'], 'AOO N° 12/2026/DRE')
        self.assertRegex(r.data['reference'], MOTIF_REFERENCE)
        self.assertNotEqual(r.data['reference'], r.data['reference_acheteur'])

    def test_reference_acheteur_filtrable_par_recherche(self):
        self.api.post(URL, {
            'objet': 'Marché A', 'reference_acheteur': 'AOO-2026-777',
        }, format='json')
        self.api.post(URL, {'objet': 'Marché B'}, format='json')
        r = self.api.get(URL, {'search': 'AOO-2026-777'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['reference_acheteur'], 'AOO-2026-777')

    def test_creations_successives_sans_collision(self):
        references = set()
        for i in range(5):
            r = self.api.post(URL, {'objet': f'Lot {i}'}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
            references.add(r.data['reference'])
        self.assertEqual(len(references), 5)
