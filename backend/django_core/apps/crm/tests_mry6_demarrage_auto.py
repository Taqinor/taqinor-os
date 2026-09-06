"""MRY6 — La cadence démarre TOUTE SEULE, mais seulement sur un lead vivant.

Décision d'architecture (D4) : le déclenchement est EXPLICITE, appelé par
chaque créateur de lead. Un `post_save(Lead)` global se déclencherait aussi sur
l'import de fichiers, sur l'import Odoo (930 leads miroir) et sur les tests —
il inonderait la file de Meryem de milliers de touches qui ne correspondent à
aucune demande réelle. Ce fichier prouve les DEUX moitiés : les créateurs qui
démarrent, et ceux qui ne doivent SURTOUT pas démarrer.

Il verrouille aussi les gardes, dont deux qui protègent le client lui-même :
un lead sans numéro exploitable (aucune touche n'est réalisable) et un DOUBLON
d'un lead vivant (deux cadences = deux commerciaux qui appellent le même jour).
Chaque refus est TRACÉ : un refus muet ferait croire que le lead est suivi.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import demarrer_cadence_contact
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class _Base(TestCase):
    slug = 'mry6'

    def setUp(self):
        self.company = _company(self.slug)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, **kw):
        champs = {'company': self.company, 'nom': 'Prospect',
                  'owner': self.acteur, 'telephone': '+212661112233',
                  'source': Lead.Source.OS_NATIVE}
        champs.update(kw)
        return Lead.objects.create(**champs)

    def _touches(self, lead):
        return lead.relance_etapes.filter(cadence='contact').count()

    def _refus_trace(self, lead, fragment):
        return any(fragment in (n.body or '')
                   for n in LeadActivity.objects.filter(lead=lead))


class DemarrageTests(_Base):
    slug = 'mry6-ok'

    def test_un_lead_vivant_recoit_sa_cadence(self):
        lead = self._lead()
        etapes = demarrer_cadence_contact(lead)
        self.assertTrue(etapes)
        self.assertEqual({e.cadence for e in etapes}, {'contact'})
        self.assertEqual(self._touches(lead), len(etapes))

    def test_le_numero_whatsapp_suffit(self):
        lead = self._lead(telephone=None, whatsapp='+212661112233')
        self.assertTrue(demarrer_cadence_contact(lead))

    def test_second_appel_ne_duplique_rien(self):
        lead = self._lead()
        premier = demarrer_cadence_contact(lead)
        demarrer_cadence_contact(lead)
        self.assertEqual(self._touches(lead), len(premier))


class GardesTests(_Base):
    slug = 'mry6-gardes'

    def test_un_lead_sans_numero_est_refuse_et_trace(self):
        """Aucune touche n'est réalisable sans numéro : appel comme WhatsApp.
        Démarrer quand même remplirait la file de Meryem de touches mortes."""
        lead = self._lead(telephone=None, whatsapp=None)
        self.assertEqual(demarrer_cadence_contact(lead), [])
        self.assertTrue(self._refus_trace(lead, 'aucun numéro exploitable'))

    def test_un_doublon_vivant_est_refuse_et_trace(self):
        """Deux cadences sur la même personne = deux commerciaux qui
        l'appellent le même jour."""
        self._lead(nom='Déjà là')
        lead = self._lead(nom='Le même')
        self.assertEqual(demarrer_cadence_contact(lead), [])
        self.assertTrue(self._refus_trace(lead, 'doublon possible'))

    def test_un_doublon_archive_ou_perdu_ne_bloque_pas(self):
        self._lead(nom='Ancien', is_archived=True)
        self._lead(nom='Perdu', perdu=True, motif_perte='Prix')
        lead = self._lead(nom='Nouveau')
        self.assertTrue(demarrer_cadence_contact(lead))

    def test_un_lead_deja_contacte_est_ignore(self):
        from django.utils import timezone
        lead = self._lead(first_contacted_at=timezone.now())
        self.assertEqual(demarrer_cadence_contact(lead), [])

    def test_un_lead_plus_avance_que_NEW_est_ignore(self):
        lead = self._lead(stage=stages.CONTACTED)
        self.assertEqual(demarrer_cadence_contact(lead), [])

    def test_un_lead_ne_plus_contacter_est_ignore(self):
        lead = self._lead(ne_plus_contacter=True)
        self.assertEqual(demarrer_cadence_contact(lead), [])
        self.assertEqual(self._touches(lead), 0)

    def test_un_lead_hors_OS_NATIVE_est_ignore_en_silence(self):
        """Le miroir Odoo n'est PAS une demande : ni cadence, ni note de
        refus (930 notes inutiles dans l'historique)."""
        lead = self._lead(source=Lead.Source.ODOO_IMPORT_TEST)
        self.assertEqual(demarrer_cadence_contact(lead), [])
        self.assertFalse(
            LeadActivity.objects.filter(lead=lead).exists())

    def test_une_exception_ne_casse_jamais_la_creation(self):
        lead = self._lead()
        with mock.patch.object(services, 'initialiser_plan_relance',
                               side_effect=RuntimeError('boum')):
            self.assertEqual(demarrer_cadence_contact(lead), [])


class PointsDappelTests(_Base):
    """Chaque créateur de lead VIVANT démarre la cadence."""

    slug = 'mry6-points'

    def test_saisie_manuelle_via_lapi(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        resp = api.post('/api/django/crm/leads/', {
            'nom': 'Saisie manuelle', 'telephone': '+212661998877',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lead = Lead.objects.get(pk=resp.data['id'])
        self.assertGreater(self._touches(lead), 0)

    def test_creation_reste_201_meme_si_la_cadence_echoue(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        with mock.patch.object(services, 'initialiser_plan_relance',
                               side_effect=RuntimeError('boum')):
            resp = api.post('/api/django/crm/leads/', {
                'nom': 'Malgré tout', 'telephone': '+212661998866',
            }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_meta_lead_ads(self):
        lead = services.create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='mry6-1', field_data=[
                {'name': 'full_name', 'values': ['Aziz']},
                {'name': 'phone_number', 'values': ['+212651971400']},
            ])
        self.assertGreater(self._touches(lead), 0)

    def test_api_publique(self):
        lead = services.create_lead_from_public_api(
            company=self.company,
            fields={'nom': 'Partenaire', 'telephone': '+212661445566'})
        self.assertGreater(self._touches(lead), 0)

    def test_evenement_marketing(self):
        lead = services.create_lead_from_evenement_marketing(
            company=self.company, nom='Salon',
            telephone='+212661334455', email='salon@example.com')
        self.assertGreater(self._touches(lead), 0)


class PointsExclusTests(_Base):
    """Ceux qui NE DOIVENT PAS démarrer — c'est la moitié qui protège la
    file de Meryem d'un déluge de touches sans demande derrière."""

    slug = 'mry6-exclus'

    def test_import_odoo_nest_pas_une_demande(self):
        lead = self._lead(source=Lead.Source.ODOO_IMPORT_TEST)
        self.assertEqual(
            RelanceEtape.objects.filter(lead=lead).count(), 0)

    def test_creation_en_masse_ne_declenche_rien(self):
        """`bulk_create` ne passe par AUCUN service : c'est justement pourquoi
        le déclenchement est explicite plutôt qu'un signal."""
        Lead.objects.bulk_create([
            Lead(company=self.company, nom=f'Masse {i}',
                 telephone=f'+21266111{i:04d}',
                 source=Lead.Source.OS_NATIVE)
            for i in range(3)])
        self.assertEqual(RelanceEtape.objects.count(), 0)

    def test_lead_depuis_ticket_sav_nest_pas_une_demande_entrante(self):
        from apps.crm.models import Client
        client = Client.objects.create(
            company=self.company, nom='Client', email='c@example.com')
        lead = services.create_lead_depuis_ticket(
            company=self.company, user=self.acteur, client=client,
            contexte='Suite SAV')
        self.assertEqual(
            RelanceEtape.objects.filter(lead=lead).count(), 0)
