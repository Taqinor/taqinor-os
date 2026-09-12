"""NTDOC21 — Templates riches avec variables conditionnelles.

Couvre :
  * une section conditionnelle est OMISE quand la condition est fausse et
    INCLUSE quand elle est vraie ;
  * un modèle SANS section se comporte exactement comme avant (le corps
    assemblé est byte-identique à `fusionner_modele(corps_html, contexte)`) ;
  * une section sans `conditions` est toujours incluse ;
  * un arbre de conditions malformé est refusé À L'ÉCRITURE (serializer), et
    tolérant au rendu (jamais d'exception) ;
  * la substitution reste SÛRE (aucune exécution de code) dans les sections ;
  * ce chemin n'est jamais celui d'un devis client (rule #4 — modèle interne).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.ged import services
from apps.ged.models import ModeleDocument
from apps.ged.serializers import ModeleDocumentSerializer

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


CLAUSE_RGPD = "<p>Clause RGPD applicable.</p>"
SECTION_RGPD = {
    'titre': 'Protection des données',
    'corps_html': CLAUSE_RGPD,
    'conditions': {
        'op': 'and',
        'conditions': [
            {'field': 'pays', 'operator': 'eq', 'value': 'France'},
        ],
    },
}


class NtDoc21Base(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc21-a', 'Ntdoc21 A')

    def _modele(self, **kwargs):
        defaults = {
            'company': self.co_a, 'nom': 'Lettre de mission',
            'corps_html': '<p>Bonjour {{ nom }},</p>',
        }
        defaults.update(kwargs)
        return ModeleDocument.objects.create(**defaults)


class AssemblageConditionnelTests(NtDoc21Base):
    def test_section_incluse_quand_la_condition_est_vraie(self):
        modele = self._modele(sections=[SECTION_RGPD])
        corps = services.fusionner_document_modele(
            modele, {'nom': 'Alice', 'pays': 'France'})
        self.assertIn('Bonjour Alice', corps)
        self.assertIn('Clause RGPD applicable', corps)
        self.assertIn('Protection des données', corps)

    def test_section_omise_quand_la_condition_est_fausse(self):
        modele = self._modele(sections=[SECTION_RGPD])
        corps = services.fusionner_document_modele(
            modele, {'nom': 'Alice', 'pays': 'Maroc'})
        self.assertIn('Bonjour Alice', corps)
        self.assertNotIn('Clause RGPD applicable', corps)
        self.assertNotIn('Protection des données', corps)

    def test_champ_absent_omet_la_section(self):
        """Un champ manquant vaut False (core.rules) — jamais une exception."""
        modele = self._modele(sections=[SECTION_RGPD])
        corps = services.fusionner_document_modele(modele, {'nom': 'Alice'})
        self.assertNotIn('Clause RGPD applicable', corps)

    def test_section_sans_condition_toujours_incluse(self):
        modele = self._modele(sections=[
            {'titre': 'Mentions', 'corps_html': '<p>Toujours là.</p>'},
        ])
        corps = services.fusionner_document_modele(modele, {'nom': 'Alice'})
        self.assertIn('Toujours là.', corps)

    def test_ordre_des_sections_preserve(self):
        modele = self._modele(sections=[
            {'corps_html': '<p>UN</p>'},
            {'corps_html': '<p>DEUX</p>'},
        ])
        corps = services.fusionner_document_modele(modele, {})
        self.assertLess(corps.index('UN'), corps.index('DEUX'))

    def test_jetons_fusionnes_dans_les_sections(self):
        modele = self._modele(sections=[
            {'titre': 'Dossier {{ reference }}',
             'corps_html': '<p>Client : {{ nom }}</p>'},
        ])
        corps = services.fusionner_document_modele(
            modele, {'nom': 'Alice', 'reference': 'REF-9'})
        self.assertIn('Dossier REF-9', corps)
        self.assertIn('Client : Alice', corps)


class RetroCompatibiliteTests(NtDoc21Base):
    def test_modele_sans_section_byte_identique(self):
        modele = self._modele()
        contexte = {'nom': 'Alice'}
        self.assertEqual(
            services.fusionner_document_modele(modele, contexte),
            services.fusionner_modele(modele.corps_html, contexte))

    def test_sections_par_defaut_liste_vide(self):
        modele = self._modele()
        self.assertEqual(modele.sections, [])
        self.assertEqual(services.sections_modele(modele), [])

    def test_sections_malformees_tolerees_au_rendu(self):
        """Une valeur aberrante en base ne casse JAMAIS un rendu."""
        modele = self._modele()
        modele.sections = 'pas une liste'
        self.assertEqual(services.sections_modele(modele), [])
        corps = services.fusionner_document_modele(modele, {'nom': 'Alice'})
        self.assertIn('Bonjour Alice', corps)

    def test_conditions_malformees_omettent_la_section(self):
        """Un opérateur de feuille inconnu vaut False — jamais d'exception."""
        modele = self._modele(sections=[
            {'corps_html': '<p>SECRET</p>',
             'conditions': {'field': 'pays', 'operator': 'inconnu',
                            'value': 'France'}},
        ])
        corps = services.fusionner_document_modele(modele, {'pays': 'France'})
        self.assertNotIn('SECRET', corps)

    def test_html_complet_integre_les_sections(self):
        modele = self._modele(sections=[SECTION_RGPD])
        html = services._modele_html_document(
            modele, {'nom': 'Alice', 'pays': 'France'})
        self.assertIn('Clause RGPD applicable', html)
        self.assertTrue(html.startswith('<!DOCTYPE html>'))


class ValidationSerializerTests(NtDoc21Base):
    def _valide(self, sections):
        serializer = ModeleDocumentSerializer(data={
            'nom': 'Lettre', 'corps_html': '<p>x</p>', 'sections': sections,
        })
        return serializer.is_valid(), serializer.errors

    def test_arbre_valide_accepte(self):
        ok, erreurs = self._valide([SECTION_RGPD])
        self.assertTrue(ok, erreurs)

    def test_arbre_malforme_refuse_a_l_ecriture(self):
        ok, erreurs = self._valide([
            {'corps_html': '<p>x</p>',
             'conditions': {'op': 'xor', 'conditions': []}},
        ])
        self.assertFalse(ok)
        self.assertIn('sections', erreurs)

    def test_operateur_de_feuille_inconnu_refuse_a_l_ecriture(self):
        ok, erreurs = self._valide([
            {'corps_html': '<p>x</p>',
             'conditions': {'field': 'pays', 'operator': 'inconnu',
                            'value': 'France'}},
        ])
        self.assertFalse(ok)
        self.assertIn('sections', erreurs)

    def test_section_non_objet_refusee(self):
        ok, _ = self._valide(['pas un objet'])
        self.assertFalse(ok)

    def test_sections_vides_acceptees(self):
        ok, erreurs = self._valide([])
        self.assertTrue(ok, erreurs)


class SubstitutionSureTests(NtDoc21Base):
    def test_aucune_execution_de_code_dans_une_section(self):
        modele = self._modele(sections=[
            {'corps_html': "<p>{{ danger }}</p>"},
        ])
        corps = services.fusionner_document_modele(
            modele, {'danger': '{% load %}'})
        # La valeur est rendue TELLE QUELLE, jamais interprétée.
        self.assertIn('{% load %}', corps)

    def test_jeton_inconnu_rendu_vide(self):
        modele = self._modele(sections=[
            {'corps_html': "<p>[{{ inconnu }}]</p>"},
        ])
        corps = services.fusionner_document_modele(modele, {})
        self.assertIn('[]', corps)
