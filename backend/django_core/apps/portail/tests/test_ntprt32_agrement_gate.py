"""Tests NTPRT32 — l'AGRÉMENT (FG237) commande le droit de soumettre.

Critère d'acceptation : « le statut d'agrément détermine si le partenaire peut
soumettre un lead » — un partenaire non agréé (prospect / en cours d'agrément
/ suspendu) ou désactivé se voit REFUSER NTPRT28, avec un motif qui lui dit
pourquoi. Ce qui NE doit pas changer : son historique reste consultable (on ne
ferme jamais rétroactivement ce qu'il a déjà déposé).

Les champs FG237 (``statut_onboarding``/``numero_agrement``/``zone``) et
l'écran interne d'annuaire existaient déjà (``/crm/partenaires`` PACT102,
``/admin/partenaires-certifies`` NTMIG29) : cette tâche ne rebâtit rien, elle
branche la garde qui manquait.

Run :
    python manage.py test apps.portail.tests.test_ntprt32_agrement_gate -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Partenaire, SoumissionLeadPartenaire
from apps.roles.models import (
    PORTAIL_PARTENAIRE_PERMISSIONS, ROLE_PORTAIL_PARTENAIRE, Role,
)
from authentication.models import Company, CustomUser

URL = '/api/django/portail/mes-soumissions/'

_seq = itertools.count(1)

PROSPECT = {
    'nom_prospect': 'Ferme Doukkala',
    'email_prospect': 'contact@ferme-doukkala.ma',
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, scope_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_PARTENAIRE,
        defaults={'permissions': list(PORTAIL_PARTENAIRE_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_PARTENAIRE
    user.portail_partenaire_id = scope_id
    user.save()
    return user


def make_partenaire(company, statut_onboarding, actif=True):
    n = next(_seq)
    return Partenaire.objects.create(
        company=company, nom=f'Partenaire-{n}', token_acces=f'tok-ntprt32-{n}',
        statut_onboarding=statut_onboarding, actif=actif)


class AgrementGateTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt32-co', 'NTPRT32 Société')
        self.api = APIClient()

    def _api_pour(self, partenaire, username):
        user = make_portal_user(self.company, username, partenaire.id)
        api = APIClient()
        api.force_authenticate(user=user)
        return api

    def test_un_partenaire_agree_peut_soumettre(self):
        p = make_partenaire(self.company, 'agree')
        api = self._api_pour(p, 'ntprt32-agree')
        res = api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_un_prospect_ne_peut_pas_soumettre(self):
        p = make_partenaire(self.company, 'prospect')
        api = self._api_pour(p, 'ntprt32-prospect')
        res = api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 403, res.data)
        self.assertIn('agrément', res.data['detail'])
        self.assertEqual(SoumissionLeadPartenaire.objects.filter(
            partenaire=p).count(), 0)

    def test_un_agrement_en_cours_ne_peut_pas_soumettre(self):
        p = make_partenaire(self.company, 'en_cours')
        api = self._api_pour(p, 'ntprt32-en-cours')
        res = api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 403, res.data)
        self.assertEqual(SoumissionLeadPartenaire.objects.filter(
            partenaire=p).count(), 0)

    def test_un_partenaire_suspendu_ne_peut_pas_soumettre(self):
        p = make_partenaire(self.company, 'suspendu')
        api = self._api_pour(p, 'ntprt32-suspendu')
        res = api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 403, res.data)
        self.assertIn('suspendu', res.data['detail'])

    def test_un_partenaire_desactive_ne_peut_pas_soumettre(self):
        p = make_partenaire(self.company, 'agree', actif=False)
        api = self._api_pour(p, 'ntprt32-inactif')
        res = api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 403, res.data)
        self.assertIn('désactivé', res.data['detail'])

    def test_l_historique_reste_consultable_quand_l_agrement_tombe(self):
        """La garde ferme le DÉPÔT, jamais la lecture de ce qui est déjà là."""
        p = make_partenaire(self.company, 'agree')
        api = self._api_pour(p, 'ntprt32-bascule')
        self.assertEqual(
            api.post(URL, PROSPECT, format='json').status_code, 201)

        p.statut_onboarding = 'suspendu'
        p.save(update_fields=['statut_onboarding'])

        res = api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['results']), 1)
        self.assertEqual(
            api.post(URL, {'nom_prospect': 'Autre',
                           'email_prospect': 'autre@exemple.ma'},
                     format='json').status_code, 403)

    def test_partenaire_inconnu_dans_cette_societe_est_404(self):
        """Introuvable — on ne dit jamais qu'il existe ailleurs."""
        autre = make_company('ntprt32-co-b', 'NTPRT32 Société B')
        p = make_partenaire(autre, 'agree')
        user = make_portal_user(self.company, 'ntprt32-etranger', p.id)
        api = APIClient()
        api.force_authenticate(user=user)
        res = api.post(URL, PROSPECT, format='json')
        self.assertEqual(res.status_code, 404, res.data)
        self.assertEqual(SoumissionLeadPartenaire.objects.filter(
            partenaire=p).count(), 0)


class ChampsFg237PresentsTests(TestCase):
    """NTPRT32 demande d'AJOUTER les champs FG237 « s'ils manquent ». Ils sont
    présents : ce test les épingle pour qu'une migration future ne les
    supprime pas en silence — la garde d'agrément en dépend."""

    def test_les_champs_d_agrement_existent(self):
        noms = {f.name for f in Partenaire._meta.get_fields()}
        for champ in ('statut_onboarding', 'numero_agrement', 'zone',
                      'date_activation'):
            self.assertIn(champ, noms)

    def test_les_statuts_d_agrement_sont_les_quatre_attendus(self):
        choix = dict(Partenaire._meta.get_field('statut_onboarding').choices)
        self.assertEqual(set(choix), {'prospect', 'en_cours', 'agree',
                                      'suspendu'})
