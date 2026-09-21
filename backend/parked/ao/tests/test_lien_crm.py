"""AOF17 — le lien AO ↔ lead, SANS couplage de modèles.

``AppelOffre.lead_id`` est un ``PositiveIntegerField`` OPAQUE, PAS une FK vers
``crm.Lead``. Ce n'est pas un oubli : c'est exactement ce qui tient le contrat
import-linter ``ao-models-decoupled`` (``apps.ao.models`` n'importe AUCUN
``models`` du cœur métier). Un agent bien intentionné voudra le « réparer » en
vraie FK — **le premier test de ce module échoue si quelqu'un le fait**.

Le reste vérifie la circulation dans les deux sens :
  * le CRM liste les AO d'un lead via ``apps.ao.selectors`` ;
  * ``ao`` lit le lead via ``apps.crm.selectors`` (jamais ``crm.models``) ;
  * ``?lead=<id>`` filtre la liste des AO ;
  * un lead d'une AUTRE société est refusé au rattachement.

Run :
    python manage.py test apps.ao.tests.test_lien_crm -v2
"""
import inspect

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models as dj_models
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import selectors, services
from apps.ao.models import AppelOffre
from apps.crm.models import Lead
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/appels-offres/'


class TestLeadIdResteOpaque(SimpleTestCase):
    def test_lead_id_n_est_pas_une_fk(self):
        champ = AppelOffre._meta.get_field('lead_id')
        self.assertIsInstance(champ, dj_models.PositiveIntegerField)
        self.assertNotIsInstance(champ, dj_models.ForeignKey)
        self.assertIsNone(getattr(champ, 'remote_field', None))

    def test_aucun_champ_relationnel_vers_crm(self):
        for champ in AppelOffre._meta.local_fields:
            cible = getattr(champ, 'remote_field', None)
            if cible is None:
                continue
            label = cible.model._meta.label_lower
            self.assertFalse(
                label.startswith('crm.'),
                f"{champ.name} pointe {label} : le contrat "
                "``ao-models-decoupled`` interdit une FK vers le CRM.")

    def test_les_modeles_ao_n_importent_pas_crm(self):
        from apps.ao import models as ao_models

        source = inspect.getsource(ao_models)
        self.assertNotIn('apps.crm', source)


class TestSelectorsAoParLead(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF17 Co', slug='aof17-co')
        self.lead = Lead.objects.create(company=self.company, nom='Alaoui')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-17-1', objet='Lié',
            lead_id=self.lead.id)
        AppelOffre.objects.create(
            company=self.company, reference='AO-17-2', objet='Non lié')

    def test_ao_par_lead(self):
        trouves = selectors.ao_par_lead(self.company, self.lead.id)
        self.assertEqual([a.pk for a in trouves], [self.ao.pk])

    def test_compte_ao_par_lead(self):
        self.assertEqual(
            selectors.compte_ao_par_lead(self.company, self.lead.id), 1)

    def test_lead_id_vide_ne_renvoie_pas_tout(self):
        """Un filtre absent ne doit pas se muer en absence de filtre."""
        self.assertEqual(list(selectors.ao_par_lead(self.company, None)), [])
        self.assertEqual(list(selectors.ao_par_lead(self.company, 0)), [])

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF17 Autre', slug='aof17-autre')
        self.assertEqual(
            list(selectors.ao_par_lead(autre, self.lead.id)), [])

    def test_fiche_lead_passe_par_les_selectors_crm(self):
        fiche = selectors.fiche_lead_de_l_ao(self.ao)
        self.assertIsNotNone(fiche)
        self.assertIn('Alaoui', fiche['label'])

    def test_fiche_lead_absente_sans_lead(self):
        sans = AppelOffre.objects.get(reference='AO-17-2')
        self.assertIsNone(selectors.fiche_lead_de_l_ao(sans))


class TestRattachementValide(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF17 Rat', slug='aof17-rat')
        self.autre = Company.objects.create(nom='AOF17 Ext', slug='aof17-ext')
        self.lead = Lead.objects.create(company=self.company, nom='Bennani')
        self.lead_etranger = Lead.objects.create(
            company=self.autre, nom='Étranger')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-17-R', objet='Rattachement')

    def test_rattachement_nominal(self):
        services.rattacher_ao_au_lead(self.ao, self.lead.id)
        self.ao.refresh_from_db()
        self.assertEqual(self.ao.lead_id, self.lead.id)

    def test_lead_d_une_autre_societe_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            services.rattacher_ao_au_lead(self.ao, self.lead_etranger.id)
        self.assertIn('lead', ctx.exception.message_dict)
        self.ao.refresh_from_db()
        self.assertIsNone(self.ao.lead_id)

    def test_detachement(self):
        services.rattacher_ao_au_lead(self.ao, self.lead.id)
        services.rattacher_ao_au_lead(self.ao, None)
        self.ao.refresh_from_db()
        self.assertIsNone(self.ao.lead_id)

    def test_rattachement_journalise_au_chatter(self):
        from apps.records.services import chatter_qs

        services.rattacher_ao_au_lead(self.ao, self.lead.id)
        entrees = list(chatter_qs(self.ao, company=self.company))
        self.assertEqual(len(entrees), 1)
        self.assertEqual(entrees[0].field, 'lead_id')

    def test_resoudre_lead_borne_a_la_societe(self):
        self.assertIsNotNone(services.resoudre_lead(self.company,
                                                    self.lead.id))
        self.assertIsNone(services.resoudre_lead(self.company,
                                                 self.lead_etranger.id))


class TestApiFiltreLead(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF17 API', slug='aof17-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof17_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.lead = Lead.objects.create(company=self.company, nom='Chraibi')
        self.lie = AppelOffre.objects.create(
            company=self.company, reference='AO-17-A', objet='Lié',
            lead_id=self.lead.id)
        AppelOffre.objects.create(
            company=self.company, reference='AO-17-B', objet='Non lié')

    def _lignes(self, resp):
        data = resp.data
        return data['results'] if isinstance(data, dict) and 'results' in data \
            else data

    def test_filtre_lead(self):
        r = self.api.get(URL, {'lead': self.lead.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([x['id'] for x in self._lignes(r)], [self.lie.id])

    def test_filtre_lead_non_numerique_ne_renvoie_rien(self):
        r = self.api.get(URL, {'lead': 'abc'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._lignes(r), [])

    def test_endpoint_lead_renvoie_la_fiche(self):
        r = self.api.get(f'{URL}{self.lie.id}/lead/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['lead_id'], self.lead.id)
        self.assertIn('Chraibi', r.data['fiche']['label'])

    def test_rattacher_lead_refuse_un_lead_etranger(self):
        autre = Company.objects.create(nom='AOF17 X', slug='aof17-x')
        etranger = Lead.objects.create(company=autre, nom='X')
        r = self.api.post(f'{URL}{self.lie.id}/rattacher-lead/',
                          {'lead': etranger.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('lead', r.data)
