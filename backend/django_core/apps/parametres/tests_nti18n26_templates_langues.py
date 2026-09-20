"""NTI18N26 — traduction des modèles de message (WhatsApp/e-mail) au-delà de
fr/darija.

Câblage du sélecteur de langue par modèle dans l'écran Paramètres → Messages
& relances (frontend) : HORS périmètre de cette lane (pas
frontend/src/i18n) — non couvert ici. Ce fichier couvre le backend
(``MessageTemplate.get_corps`` / ``EmailTemplate.get_template``/``render``).
"""
from django.test import TestCase

from authentication.models import Company
from apps.parametres.models_messages import MessageTemplate
from apps.parametres.models_email import EmailTemplate


def _company(slug='nti18n26-co', nom='NTI18N26 Co'):
    return Company.objects.create(nom=nom, slug=slug)


class MessageTemplateLanguesTests(TestCase):
    def test_en_body_used_when_present(self):
        company = _company()
        MessageTemplate.objects.create(
            company=company, cle='facture',
            corps_fr='Voici votre facture', corps_en='Here is your invoice')
        self.assertEqual(
            MessageTemplate.get_corps(company, 'facture', 'en'),
            'Here is your invoice')

    def test_ar_body_used_when_present(self):
        company = _company('nti18n26-co-2', 'NTI18N26 Co 2')
        MessageTemplate.objects.create(
            company=company, cle='facture', corps_ar='إليك فاتورتك')
        self.assertEqual(
            MessageTemplate.get_corps(company, 'facture', 'ar'),
            'إليك فاتورتك')

    def test_missing_en_falls_back_to_fr_body_never_silent_failure(self):
        company = _company('nti18n26-co-3', 'NTI18N26 Co 3')
        MessageTemplate.objects.create(
            company=company, cle='facture', corps_fr='Voici votre facture')
        self.assertEqual(
            MessageTemplate.get_corps(company, 'facture', 'en'),
            'Voici votre facture')

    def test_missing_everything_falls_back_to_class_default(self):
        company = _company('nti18n26-co-4', 'NTI18N26 Co 4')
        result = MessageTemplate.get_corps(company, 'facture', 'ar')
        self.assertTrue(result)  # jamais vide (repli sur le défaut FR de la clé)

    def test_darija_behaviour_unchanged_by_this_task(self):
        company = _company('nti18n26-co-5', 'NTI18N26 Co 5')
        MessageTemplate.objects.create(
            company=company, cle='identite', corps_darija='صباح الخير')
        self.assertEqual(
            MessageTemplate.get_corps(company, 'identite', 'darija'),
            'صباح الخير')

    def test_ar_and_darija_are_distinct_fields(self):
        company = _company('nti18n26-co-6', 'NTI18N26 Co 6')
        row = MessageTemplate.objects.create(
            company=company, cle='facture',
            corps_darija='دارجة', corps_ar='فصحى')
        self.assertEqual(row.corps_darija, 'دارجة')
        self.assertEqual(row.corps_ar, 'فصحى')
        self.assertEqual(
            MessageTemplate.get_corps(company, 'facture', 'darija'), 'دارجة')
        self.assertEqual(
            MessageTemplate.get_corps(company, 'facture', 'ar'), 'فصحى')


class EmailTemplateLanguesTests(TestCase):
    def test_get_template_en_and_ar(self):
        company = _company('nti18n26-co-7', 'NTI18N26 Co 7')
        EmailTemplate.objects.create(
            company=company, cle='devis',
            sujet='Votre devis', corps='Bonjour,',
            sujet_en='Your quote', corps_en='Hello,',
            sujet_ar='عرض السعر الخاص بك', corps_ar='مرحبا،')
        self.assertEqual(
            EmailTemplate.get_template(company, 'devis', 'en'),
            {'sujet': 'Your quote', 'corps': 'Hello,'})
        self.assertEqual(
            EmailTemplate.get_template(company, 'devis', 'ar'),
            {'sujet': 'عرض السعر الخاص بك', 'corps': 'مرحبا،'})

    def test_get_template_default_langue_still_fr_backward_compatible(self):
        company = _company('nti18n26-co-8', 'NTI18N26 Co 8')
        EmailTemplate.objects.create(
            company=company, cle='devis', sujet='Votre devis', corps='Bonjour,')
        self.assertEqual(
            EmailTemplate.get_template(company, 'devis'),
            {'sujet': 'Votre devis', 'corps': 'Bonjour,'})

    def test_get_template_en_falls_back_to_fr_when_not_translated(self):
        company = _company('nti18n26-co-9', 'NTI18N26 Co 9')
        EmailTemplate.objects.create(
            company=company, cle='devis', sujet='Votre devis', corps='Bonjour,')
        self.assertEqual(
            EmailTemplate.get_template(company, 'devis', 'en'),
            {'sujet': 'Votre devis', 'corps': 'Bonjour,'})

    def test_render_accepts_langue_kwarg(self):
        company = _company('nti18n26-co-10', 'NTI18N26 Co 10')
        EmailTemplate.objects.create(
            company=company, cle='notification',
            sujet='Bonjour {nom}', corps='Bonjour {nom}',
            sujet_en='Hello {nom}', corps_en='Hello {nom}')
        out = EmailTemplate.render(company, 'notification', 'en', nom='Reda')
        self.assertEqual(out['sujet'], 'Hello Reda')

    def test_render_without_langue_still_works_positional_callers(self):
        # Non-régression : les appelants existants (installations, sav,
        # ventes) appellent `render(company, cle, **ctx)` sans `langue` —
        # ce doit rester un rendu FR strictement identique.
        company = _company('nti18n26-co-11', 'NTI18N26 Co 11')
        EmailTemplate.objects.create(
            company=company, cle='notification',
            sujet='Bonjour {nom}', corps='Bonjour {nom}')
        out = EmailTemplate.render(company, 'notification', nom='Reda')
        self.assertEqual(out['sujet'], 'Bonjour Reda')
