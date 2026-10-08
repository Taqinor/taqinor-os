"""APAR28 — chaque écriture de réglage laisse une ligne dans le journal.

Constat C-APAR-039 : taux de TVA (dont ``set_defaut``), conditions de
paiement, unités, cadence de relance, réalisations, et le CRUD DIRECT des
statuts et des e-mails écrivaient sans aucune ligne ``SettingsAuditLog`` ; la
réinitialisation d'un message effaçait le texte Darija sans trace.

Test-du-test : retirer ``SettingsAuditedMixin`` d'un ViewSet ⇒ le geste de ce
ViewSet est NOMMÉ dans l'échec.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models import MessageTemplate, SettingsAuditLog
from apps.parametres.models_realisations import Realisation
from apps.parametres.models_relance import CadenceRelanceEtape, CanalRelance
from apps.parametres.models_taxes import TauxTVA
from apps.parametres.statuses_defaults import default_statuses
from authentication.models import Company

BASE = '/api/django/parametres/'


class AuditEcrituresTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR28', slug='apar28-co')
        self.admin = get_user_model().objects.create_user(
            username='apar28-admin', password='x', company=self.company,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _lignes(self):
        return SettingsAuditLog.objects.filter(company=self.company)

    def _geste(self, nom, appel, statut):
        avant = self._lignes().count()
        r = appel()
        self.assertEqual(r.status_code, statut, f'{nom} : {getattr(r, "data", r)}')
        self.assertGreater(self._lignes().count(), avant,
                           f'geste non journalisé : {nom}')
        ligne = self._lignes().order_by('-id').first()
        self.assertEqual(ligne.user_id, self.admin.pk, nom)
        return r

    def test_chaque_ecriture_journalisee(self):
        api = self.api
        r = self._geste('taux-tva POST', lambda: api.post(
            f'{BASE}taux-tva/',
            {'code': 'apar28', 'libelle': 'TVA APAR28', 'taux': '7'},
            format='json'), 201)
        tid = r.data['id']
        self._geste('taux-tva PATCH', lambda: api.patch(
            f'{BASE}taux-tva/{tid}/', {'libelle': 'TVA APAR28 bis'},
            format='json'), 200)
        modif = self._lignes().order_by('-id').first()
        self.assertIn('TVA APAR28', modif.old_value)
        self.assertIn('TVA APAR28 bis', modif.new_value)
        self._geste('taux-tva set_defaut', lambda: api.post(
            f'{BASE}taux-tva/{tid}/set_defaut/', {}, format='json'), 200)
        autre = TauxTVA.objects.create(
            company=self.company, code='apar28-b', libelle='À supprimer',
            taux='3')
        self._geste('taux-tva DELETE', lambda: api.delete(
            f'{BASE}taux-tva/{autre.pk}/'), 204)

        self._geste('conditions-paiement POST', lambda: api.post(
            f'{BASE}conditions-paiement/',
            {'libelle': '45 jours APAR28', 'delai_jours': 45},
            format='json'), 201)
        self._geste('unites-mesure POST', lambda: api.post(
            f'{BASE}unites-mesure/', {'code': 'apar28', 'libelle': 'Lot'},
            format='json'), 201)

        etape = CadenceRelanceEtape.objects.create(
            company=self.company, delai_jours=3,
            canal=CanalRelance.values[0], libelle='Étape APAR28')
        self._geste('cadence-relance PATCH', lambda: api.patch(
            f'{BASE}cadence-relance/{etape.pk}/', {'delai_jours': 5},
            format='json'), 200)

        real = Realisation.objects.create(
            company=self.company, titre='Villa APAR28', ville='Casablanca',
            url_page='https://example.invalid/realisations/villa-apar28/')
        self._geste('realisations PATCH', lambda: api.patch(
            f'{BASE}realisations/{real.pk}/', {'titre': 'Villa APAR28 bis'},
            format='json'), 200)
        self._geste('realisations DELETE', lambda: api.delete(
            f'{BASE}realisations/{real.pk}/'), 204)

        cle_statut = default_statuses('chantier')[0][0]
        self._geste('statuts POST (hors bulk)', lambda: api.post(
            f'{BASE}statuts/',
            {'domaine': 'chantier', 'cle': cle_statut,
             'libelle': 'Libellé APAR28'},
            format='json'), 201)
        self._geste('email-templates POST (hors bulk)', lambda: api.post(
            f'{BASE}email-templates/',
            {'cle': 'envoi_devis', 'sujet': 'Devis {reference}',
             'corps': 'Bonjour'},
            format='json'), 201)

    def test_reset_message_journalise_le_darija_efface(self):
        MessageTemplate.objects.create(
            company=self.company, cle='facture', corps_fr='FR perso {lien}',
            corps_darija='Darija perso {lien}')
        self._geste('messages reset', lambda: self.api.put(
            f'{BASE}messages/', {'cle': 'facture', 'reset': True},
            format='json'), 200)
        self.assertTrue(self._lignes().filter(
            section='messages', old_value='Darija perso {lien}').exists())
