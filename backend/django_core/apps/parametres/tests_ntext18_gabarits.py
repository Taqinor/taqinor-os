"""NTEXT18 — gabarits de DOCUMENT custom (hors devis, règle #4).

Couvre :
  * le rendu d'un gabarit « fiche de visite chantier » : placeholders
    substitués LITTÉRALEMENT, valeurs échappées, puis délégation à
    ``core.pdf.render_pdf`` (ARC11 — aucun WeasyPrint importé ici) ;
  * la RÈGLE #4 : toute cible « devis » est refusée — à la création ORM brute,
    à la validation ``full_clean``, et au rendu ;
  * l'isolation société + l'unicité ``(company, code)`` ;
  * la NON-INTERFÉRENCE avec ``parametres.DocumentTemplates`` (singleton
    préexistant des textes du devis premium) : deux modèles distincts.
"""
import itertools
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company

from apps.parametres import gabarits
from apps.parametres.models import GabaritDocumentCustom
from apps.parametres.models_documents import DocumentTemplates

_seq = itertools.count(1)

CORPS_FICHE = (
    '<h1>Fiche de visite — {{ chantier.nom }}</h1>'
    '<p>Client : {{ client.nom }}</p>'
    '<p>Adresse : {{ chantier.adresse }}</p>'
    '<p>Observation : {{ observation }}</p>'
)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT18 Co {next(_seq)}')


def make_gabarit(company, **kwargs):
    kwargs.setdefault('code', f'fiche-visite-{next(_seq)}')
    kwargs.setdefault('nom', 'Fiche de visite chantier')
    kwargs.setdefault('cible', GabaritDocumentCustom.Cible.CHANTIER)
    kwargs.setdefault('corps', CORPS_FICHE)
    return GabaritDocumentCustom.objects.create(company=company, **kwargs)


class RenduTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT18 Rendu')
        self.gabarit = make_gabarit(self.company, code='fiche_visite_chantier')
        self.contexte = {
            'chantier': {'nom': 'Villa Anfa', 'adresse': '12 rue des Palmiers'},
            'client': {'nom': 'SARL Soleil'},
            'observation': 'Toiture accessible',
        }

    def test_placeholders_are_substituted_literally(self):
        html = gabarits.rendre_html(self.gabarit, self.contexte)
        self.assertIn('Villa Anfa', html)
        self.assertIn('12 rue des Palmiers', html)
        self.assertIn('SARL Soleil', html)
        self.assertIn('Toiture accessible', html)
        self.assertNotIn('{{', html)
        # Le HTML du GABARIT est conservé tel quel (mise en forme voulue).
        self.assertIn('<h1>', html)

    def test_missing_variable_is_empty_not_an_error(self):
        html = gabarits.rendre_html(self.gabarit, {})
        self.assertNotIn('{{', html)
        self.assertIn('<h1>Fiche de visite — </h1>', html)

    def test_strict_mode_keeps_the_unknown_placeholder_visible(self):
        html = gabarits.rendre_html(self.gabarit, {}, strict=True)
        self.assertIn('{{ chantier.nom }}', html)

    def test_substituted_values_are_html_escaped(self):
        html = gabarits.rendre_html(
            self.gabarit, {'observation': '<script>alert(1)</script>'})
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_no_code_is_ever_executed(self):
        gabarit = make_gabarit(
            self.company, corps='{{ danger }}',
            code='corps-dangereux')
        html = gabarits.rendre_html(
            gabarit, {'danger': '{{ chantier.nom }}'})
        # La valeur substituée n'est PAS re-rendue : substitution en UNE passe.
        self.assertEqual(html, '{{ chantier.nom }}')

    def test_variables_of_the_template_are_listed(self):
        self.assertEqual(
            gabarits.variables_du_gabarit(self.gabarit),
            ['chantier.nom', 'client.nom', 'chantier.adresse', 'observation'])

    def test_pdf_is_delegated_to_core_pdf_render_pdf(self):
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.4') as rendu:
            pdf = gabarits.rendre_pdf(self.gabarit, self.contexte)
        self.assertEqual(pdf, b'%PDF-1.4')
        self.assertEqual(rendu.call_count, 1)
        _args, kwargs = rendu.call_args
        self.assertIn('Villa Anfa', kwargs['html'])
        self.assertEqual(kwargs['company'], self.company)


class RegleQuatreTests(TestCase):
    """Règle #4 — le devis client passe UNIQUEMENT par /proposal."""

    def setUp(self):
        self.company = make_company('NTEXT18 Regle4')

    def test_devis_is_not_an_offered_choice(self):
        valeurs = {v for v, _ in GabaritDocumentCustom.Cible.choices}
        self.assertNotIn('devis', valeurs)
        self.assertEqual(
            valeurs, {'chantier', 'client', 'ticket', 'objet_custom'})

    def test_raw_orm_create_with_devis_target_is_rejected(self):
        with self.assertRaises(ValidationError):
            GabaritDocumentCustom.objects.create(
                company=self.company, code='devis-pirate', nom='Pirate',
                cible='devis', corps='<p>{{ x }}</p>')
        self.assertFalse(
            GabaritDocumentCustom.objects.filter(code='devis-pirate').exists())

    def test_switching_an_existing_template_to_devis_is_rejected(self):
        gabarit = make_gabarit(self.company)
        gabarit.cible = 'DEVIS'   # casse/espaces ne contournent pas la garde
        with self.assertRaises(ValidationError):
            gabarit.save()

    def test_full_clean_also_rejects_the_devis_target(self):
        gabarit = GabaritDocumentCustom(
            company=self.company, code='x', nom='X', cible='devis')
        with self.assertRaises(ValidationError):
            gabarit.full_clean()

    def test_rendering_refuses_a_forced_devis_target(self):
        gabarit = make_gabarit(self.company)
        gabarit.cible = 'devis'   # forcé EN MÉMOIRE, jamais persisté
        with self.assertRaises(ValidationError):
            gabarits.rendre_html(gabarit, {})
        with self.assertRaises(ValidationError):
            gabarits.rendre_pdf(gabarit, {})


class ScopingTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT18 Scope')
        self.autre = make_company('NTEXT18 Scope Autre')

    def test_code_is_unique_per_company_not_globally(self):
        make_gabarit(self.company, code='fiche_visite')
        # La MÊME clé dans une AUTRE société est légitime.
        make_gabarit(self.autre, code='fiche_visite')
        self.assertEqual(
            GabaritDocumentCustom.objects.filter(code='fiche_visite').count(),
            2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_gabarit(self.company, code='fiche_visite')


class NonInterferenceTests(TestCase):
    """Le singleton PRÉEXISTANT des textes du devis premium reste intouché."""

    def test_document_templates_is_a_separate_model(self):
        self.assertIsNot(GabaritDocumentCustom, DocumentTemplates)
        self.assertNotEqual(
            GabaritDocumentCustom._meta.db_table,
            DocumentTemplates._meta.db_table)
        self.assertFalse(
            issubclass(GabaritDocumentCustom, DocumentTemplates))

    def test_creating_a_custom_template_does_not_touch_document_templates(self):
        company = make_company('NTEXT18 NonInterference')
        make_gabarit(company)
        self.assertEqual(
            DocumentTemplates.objects.filter(company=company).count(), 0)
