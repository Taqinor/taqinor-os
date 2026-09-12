"""NTGRC35 — sous-traitants RGPD (art. 28) & suivi des clauses.

Garanties : un sous-traitant SANS clause signée remonte dans le sélecteur (les
plus risqués d'abord) et peut être relié à son questionnaire de conformité par
string-FK vérifiée ; une clause déclarée signée doit dire QUAND ; tout reste
scopé société.
"""
from datetime import date

from django.test import TestCase

from apps.grc.models import QuestionnaireFournisseur, SousTraitantRGPD
from apps.grc.selectors import sous_traitants_sans_clause
from authentication.models import Company
from testkit.base import TenantAPITestCase


def _sous_traitant(company, nom='Hébergeur', **kw):
    return SousTraitantRGPD.objects.create(company=company, nom=nom, **kw)


class SelectorSansClauseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC35 SA', slug='ntgrc35')

    def test_un_sous_traitant_sans_clause_remonte(self):
        st = _sous_traitant(self.company)
        self.assertEqual(list(sous_traitants_sans_clause(self.company)), [st])

    def test_un_sous_traitant_avec_clause_ne_remonte_pas(self):
        _sous_traitant(self.company, clause_signee=True,
                       date_clause=date(2026, 3, 12))
        self.assertEqual(list(sous_traitants_sans_clause(self.company)), [])

    def test_une_date_sans_signature_reste_dans_la_liste(self):
        """C'est la SIGNATURE qui engage, pas la date qu'on a notée."""
        st = _sous_traitant(self.company, date_clause=date(2026, 3, 12))
        self.assertEqual(list(sous_traitants_sans_clause(self.company)), [st])

    def test_les_plus_risques_arrivent_en_tete(self):
        faible = _sous_traitant(
            self.company, nom='A', niveau_risque=SousTraitantRGPD.RISQUE_FAIBLE)
        eleve = _sous_traitant(
            self.company, nom='Z', niveau_risque=SousTraitantRGPD.RISQUE_ELEVE)
        moyen = _sous_traitant(
            self.company, nom='M', niveau_risque=SousTraitantRGPD.RISQUE_MOYEN)
        self.assertEqual(
            list(sous_traitants_sans_clause(self.company)),
            [eleve, moyen, faible])

    def test_le_selector_est_borne_a_la_societe(self):
        autre = Company.objects.create(nom='Autre', slug='ntgrc35-autre')
        _sous_traitant(autre)
        self.assertEqual(list(sous_traitants_sans_clause(self.company)), [])


class EndpointSousTraitantTests(TenantAPITestCase):
    BASE = '/api/django/grc/sous-traitants-rgpd/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_la_societe(self):
        r = self._admin().post(
            self.BASE,
            {'nom': 'Hébergeur UE', 'finalites': ['hébergement'],
             'localisation_donnees': 'France',
             'niveau_risque': 'eleve'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        st = SousTraitantRGPD.objects.get(pk=r.data['id'])
        self.assertEqual(st.company, self.company)
        self.assertFalse(st.clause_signee)

    def test_un_nom_vide_nomme_le_champ(self):
        r = self._admin().post(self.BASE, {'nom': '  '}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('nom', r.data)

    def test_une_clause_signee_doit_dire_quand(self):
        r = self._admin().post(
            self.BASE, {'nom': 'X', 'clause_signee': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('date_clause', r.data)

    def test_liaison_au_questionnaire_de_conformite(self):
        questionnaire = QuestionnaireFournisseur.objects.create(
            company=self.company, fournisseur_ref='')
        r = self._admin().post(
            self.BASE,
            {'nom': 'Cabinet paie',
             'questionnaire_ref': str(questionnaire.pk)},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        st = SousTraitantRGPD.objects.get(pk=r.data['id'])
        self.assertEqual(st.questionnaire_ref, str(questionnaire.pk))

    def test_un_questionnaire_d_une_autre_societe_est_refuse(self):
        etranger = QuestionnaireFournisseur.objects.create(
            company=self.other_company, fournisseur_ref='')
        r = self._admin().post(
            self.BASE,
            {'nom': 'X', 'questionnaire_ref': str(etranger.pk)},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('questionnaire_ref', r.data)

    def test_un_fournisseur_inconnu_est_refuse(self):
        r = self._admin().post(
            self.BASE, {'nom': 'X', 'fournisseur_ref': '999999'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('fournisseur_ref', r.data)

    def test_endpoint_sans_clause(self):
        _sous_traitant(self.company, nom='Sans clause')
        _sous_traitant(self.company, nom='Avec clause', clause_signee=True,
                       date_clause=date(2026, 3, 12))
        r = self._admin().get(f'{self.BASE}sans-clause/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['results']), 1)
        self.assertEqual(r.data['results'][0]['nom'], 'Sans clause')

    def test_liste_scopee_societe(self):
        _sous_traitant(self.other_company)
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
