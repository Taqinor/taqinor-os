"""Tests NTPRT30 — « Mes commissions » du portail PARTENAIRE.

Le critère d'acceptation est ARITHMÉTIQUE : « le total du relevé matche
exactement la somme des lignes ``CommissionPartenaire`` du partenaire sur la
période ». On le vérifie sur le relevé complet ET sur une période bornée, et
on vérifie qu'un autre partenaire (ou une autre société) n'entre jamais dans
la somme.

Le rendu PDF est MOQUÉ (``core.pdf.render_pdf``) : ce qui est testé ici, c'est
que la route existe, qu'elle est gardée et qu'elle sert bien le MÊME relevé —
pas WeasyPrint, dont le rendu réel appartient au gate nocturne.

Run :
    python manage.py test apps.portail.tests.test_ntprt30_mes_commissions -v2
"""
import datetime
import itertools
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import CommissionPartenaire, Partenaire
from apps.roles.models import (
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    PORTAIL_PARTENAIRE_PERMISSIONS,
    ROLE_PORTAIL_FOURNISSEUR,
    ROLE_PORTAIL_PARTENAIRE,
    Role,
)
from authentication.models import Company, CustomUser

URL = '/api/django/portail/mes-commissions/'
URL_PDF = f'{URL}pdf/'

_seq = itertools.count(1)

_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_PARTENAIRE: (
        ROLE_PORTAIL_PARTENAIRE, 'portail_partenaire_id',
        PORTAIL_PARTENAIRE_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def make_partenaire(company, nom='Partenaire'):
    n = next(_seq)
    return Partenaire.objects.create(
        company=company, nom=f'{nom}-{n}', token_acces=f'tok-ntprt30-{n}')


def make_commission(company, partenaire, montant, statut, jours=0):
    c = CommissionPartenaire.objects.create(
        company=company, partenaire=partenaire,
        base_ht=Decimal('10000'), taux=Decimal('5'),
        montant=Decimal(montant), statut=statut)
    if jours:
        # `date_creation` est auto_now_add : on la recule par UPDATE.
        CommissionPartenaire.objects.filter(pk=c.pk).update(
            date_creation=timezone.now() - datetime.timedelta(days=jours))
        c.refresh_from_db()
    return c


class ReleveCommissionsTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt30-co', 'NTPRT30 Société')
        self.p_a = make_partenaire(self.company, 'Alpha')
        self.p_b = make_partenaire(self.company, 'Beta')
        make_commission(self.company, self.p_a, '100',
                        CommissionPartenaire.Statut.DUE)
        make_commission(self.company, self.p_a, '250',
                        CommissionPartenaire.Statut.PAYEE)
        make_commission(self.company, self.p_a, '40',
                        CommissionPartenaire.Statut.ANNULEE)
        # Bruit : un AUTRE partenaire de la même société.
        make_commission(self.company, self.p_b, '9999',
                        CommissionPartenaire.Statut.DUE)
        self.user_a = make_portal_user(
            self.company, 'ntprt30-p-a',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.p_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_le_total_est_la_somme_des_lignes_rendues(self):
        """Critère d'acceptation NTPRT30."""
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        lignes = res.data['lignes']
        self.assertEqual(len(lignes), 3)
        somme = sum(Decimal(ligne['montant']) for ligne in lignes)
        self.assertEqual(Decimal(res.data['totaux']['total']), somme)
        self.assertEqual(Decimal(res.data['totaux']['total']),
                         Decimal('390'))

    def test_les_sous_totaux_s_additionnent_au_total(self):
        totaux = self.api.get(URL).data['totaux']
        self.assertEqual(Decimal(totaux['due']), Decimal('100'))
        self.assertEqual(Decimal(totaux['payee']), Decimal('250'))
        self.assertEqual(Decimal(totaux['annulee']), Decimal('40'))
        self.assertEqual(
            Decimal(totaux['due']) + Decimal(totaux['payee'])
            + Decimal(totaux['annulee']),
            Decimal(totaux['total']))

    def test_les_commissions_d_un_autre_partenaire_n_entrent_pas(self):
        totaux = self.api.get(URL).data['totaux']
        self.assertNotIn('9999', str(totaux))
        self.assertEqual(Decimal(totaux['total']), Decimal('390'))

    def test_periode_bornee(self):
        make_commission(self.company, self.p_a, '500',
                        CommissionPartenaire.Statut.DUE, jours=60)
        aujourdhui = timezone.localdate()
        depuis = (aujourdhui - datetime.timedelta(days=7)).isoformat()

        res = self.api.get(URL, {'debut': depuis})
        lignes = res.data['lignes']
        somme = sum(Decimal(ligne['montant']) for ligne in lignes)
        # La commission vieille de 60 jours est HORS période : ni dans les
        # lignes, ni dans le total.
        self.assertEqual(len(lignes), 3)
        self.assertEqual(Decimal(res.data['totaux']['total']), somme)
        self.assertEqual(Decimal(res.data['totaux']['total']),
                         Decimal('390'))

    def test_borne_invalide_nomme_le_champ_fautif(self):
        res = self.api.get(URL, {'debut': '01/01/2026'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('debut', res.data)

    def test_un_compte_fournisseur_est_refuse(self):
        f = make_portal_user(
            self.company, 'ntprt30-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        api = APIClient()
        api.force_authenticate(user=f)
        self.assertEqual(api.get(URL).status_code, 403)
        self.assertEqual(api.get(URL_PDF).status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))
        self.assertIn(APIClient().get(URL_PDF).status_code, (401, 403))

    def test_partenaire_d_une_autre_societe_voit_un_releve_vide(self):
        autre = make_company('ntprt30-co-b', 'NTPRT30 Société B')
        etranger = make_portal_user(
            autre, 'ntprt30-p-etranger',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.p_a.id)
        api = APIClient()
        api.force_authenticate(user=etranger)
        res = api.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['lignes'], [])
        self.assertEqual(Decimal(res.data['totaux']['total']), Decimal('0'))


class RelevePdfTests(TestCase):
    """Le PDF est servi par ``core.pdf.render_pdf`` (ARC11), jamais par le
    moteur de devis premium (règle #4). Le rendu réel est moqué."""

    def setUp(self):
        self.company = make_company('ntprt30c-co', 'NTPRT30c Société')
        self.partenaire = make_partenaire(self.company, 'Alpha')
        make_commission(self.company, self.partenaire, '100',
                        CommissionPartenaire.Statut.DUE)
        self.user = make_portal_user(
            self.company, 'ntprt30c-p',
            CustomUser.PORTEE_PORTAIL_PARTENAIRE, self.partenaire.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def test_pdf_telechargeable(self):
        with mock.patch('core.pdf.render_pdf',
                        return_value=b'%PDF-1.4 faux') as rendu:
            res = self.api.get(URL_PDF)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(rendu.called)

    def test_le_pdf_porte_le_MEME_total_que_l_ecran(self):
        attendu = self.api.get(URL).data['totaux']['total']
        capture = {}

        def _faux_rendu(html=None, **kwargs):
            capture['html'] = html
            return b'%PDF-1.4 faux'

        with mock.patch('core.pdf.render_pdf', side_effect=_faux_rendu):
            self.api.get(URL_PDF)
        self.assertIn(f'{attendu} MAD', capture['html'])
        self.assertIn(self.partenaire.nom, capture['html'])

    def test_borne_invalide_nomme_le_champ_fautif(self):
        res = self.api.get(URL_PDF, {'fin': '31-12-2026'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('fin', res.data)
