"""APAR30 — export ∘ import = identité sur tous les textes de l'écran.

Constat C-APAR-047 : l'export de configuration oubliait ``bpa_mention``,
``acceptance_stamp`` et ``cgv_par_mode`` (liste ``DOCUMENT_TEMPLATE_FIELDS``
tenue à la main), tous les ``EmailTemplate`` et les textes EN/AR des
messages ; l'import n'appliquait pas la liste blanche de l'écran et
n'incrémentait pas ``DocumentTemplates.version``.

Test-du-test : retirer ``bpa_mention`` de la dérivation
(``champs_textes_documents``) ⇒ ``test_aller_retour_identique`` rouge.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models import MessageTemplate
from apps.parametres.models_documents import DEVIS_TEXT_KEYS, DocumentTemplates
from apps.parametres.models_email import EmailTemplate
from apps.roles.models import Role
from apps.roles.permissions_registre import ADMIN_PERMISSIONS
from authentication.models import Company

EXPORT = '/api/django/parametres/config-export/'
IMPORT = '/api/django/parametres/config-import/'

CGV_PAR_MODE = {'commercial': {'titre': 'CG commerce',
                               'bullets': ['Paiement 30 j', 'Garantie 2 ans']}}


def _admin_api(company, suffixe):
    role = Role.objects.create(
        company=company, nom='Administrateur',
        permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
    user = get_user_model().objects.create_user(
        username=f'apar30-{suffixe}', password='x', company=company,
        role_legacy='admin', role=role)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ExportAllerRetourTests(TestCase):
    def setUp(self):
        self.src = Company.objects.create(nom='APAR30 src', slug='apar30-src')
        self.dst = Company.objects.create(nom='APAR30 dst', slug='apar30-dst')
        self.api_src = _admin_api(self.src, 'src')
        self.api_dst = _admin_api(self.dst, 'dst')
        DocumentTemplates.objects.create(
            company=self.src, bpa_mention='Lu et approuvé — APAR30',
            acceptance_stamp='Accepté le', cgv_titre='CG APAR30',
            cgv_bullets=['Acompte {acompte}'], cgv_par_mode=CGV_PAR_MODE)
        MessageTemplate.objects.create(
            company=self.src, cle='facture', corps_fr='Bonjour {nom} {lien}',
            corps_darija='Salam {nom}', corps_en='Hello {nom} {lien}',
            corps_ar='مرحبا {nom}')
        EmailTemplate.objects.create(
            company=self.src, cle='envoi_devis', sujet='Devis {reference}',
            corps='Bonjour {nom}', sujet_en='Quote {reference}',
            corps_en='Hello {nom}')

    def test_aller_retour_identique(self):
        bundle = self.api_src.get(EXPORT).data
        self.assertEqual(bundle['version'], 2)
        r = self.api_dst.post(f'{IMPORT}?mode=overwrite', bundle,
                              format='json')
        self.assertEqual(r.status_code, 200, r.data)
        src = DocumentTemplates.objects.get(company=self.src)
        dst = DocumentTemplates.objects.get(company=self.dst)
        for champ in list(DEVIS_TEXT_KEYS) + ['cgv_par_mode']:
            with self.subTest(champ=champ):
                self.assertEqual(getattr(dst, champ), getattr(src, champ))
        self.assertGreaterEqual(dst.version, 2)  # version + 1 à l'import
        m = MessageTemplate.objects.get(company=self.dst, cle='facture')
        self.assertEqual((m.corps_fr, m.corps_darija, m.corps_en, m.corps_ar),
                         ('Bonjour {nom} {lien}', 'Salam {nom}',
                          'Hello {nom} {lien}', 'مرحبا {nom}'))
        e = EmailTemplate.objects.get(company=self.dst, cle='envoi_devis')
        self.assertEqual((e.sujet, e.corps, e.sujet_en, e.corps_en),
                         ('Devis {reference}', 'Bonjour {nom}',
                          'Quote {reference}', 'Hello {nom}'))

    def test_placeholder_inconnu_refuse(self):
        corps = {'message_templates': [
            {'cle': 'facture', 'corps_fr': 'Bonjour {foo}'}]}
        r = self.api_dst.post(f'{IMPORT}?mode=overwrite', corps,
                              format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('message_templates[0].corps_fr', r.data)
        self.assertFalse(MessageTemplate.objects.filter(
            company=self.dst, cle='facture').exists())
        r2 = self.api_dst.post(f'{IMPORT}?mode=overwrite', {
            'email_templates': [{'cle': 'envoi_devis', 'sujet': 'x',
                                 'corps': 'Total 5 }'}]}, format='json')
        self.assertEqual(r2.status_code, 400, r2.data)

    def test_ancien_bundle_v1_reste_lisible(self):
        r = self.api_dst.post(f'{IMPORT}?mode=overwrite', {
            'version': 1,
            'message_templates': [{'cle': 'facture',
                                   'corps_fr': 'Bonjour {nom}',
                                   'corps_darija': ''}],
            'document_templates': {'cgv_titre': 'Titre v1'}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            DocumentTemplates.objects.get(company=self.dst).cgv_titre,
            'Titre v1')
