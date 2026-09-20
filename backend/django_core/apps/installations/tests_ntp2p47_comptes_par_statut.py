"""NTP2P47 — ``apps.installations.selectors.comptes_demandes_achat_par_statut``.

Point d'entrée cross-app en LECTURE SEULE qui comble le trou documenté par
``apps.reporting.p2p_kpi`` (``taux_conversion_pct`` restait ``None`` faute
d'un compte par statut de ``DemandeAchat``)."""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.installations.models import DemandeAchat
from apps.installations.selectors import comptes_demandes_achat_par_statut
from authentication.models import Company


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class ComptesDemandesAchatParStatutTests(TestCase):
    def setUp(self):
        self.company = make_company('ntp2p47-co', 'NTP2P47 Co')

    def test_toutes_les_cles_de_statut_sont_toujours_presentes(self):
        comptes = comptes_demandes_achat_par_statut(self.company)
        self.assertEqual(set(comptes), {
            'brouillon', 'soumise', 'approuvee', 'refusee', 'commandee'})
        self.assertEqual(list(comptes.values()), [0, 0, 0, 0, 0])

    def test_compte_correctement_par_statut(self):
        DemandeAchat.objects.create(
            company=self.company, reference='DA-1', objet='x',
            statut=DemandeAchat.Statut.COMMANDEE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-2', objet='x',
            statut=DemandeAchat.Statut.COMMANDEE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-3', objet='x',
            statut=DemandeAchat.Statut.REFUSEE)
        DemandeAchat.objects.create(
            company=self.company, reference='DA-4', objet='x',
            statut=DemandeAchat.Statut.BROUILLON)

        comptes = comptes_demandes_achat_par_statut(self.company)
        self.assertEqual(comptes['commandee'], 2)
        self.assertEqual(comptes['refusee'], 1)
        self.assertEqual(comptes['brouillon'], 1)
        self.assertEqual(comptes['soumise'], 0)
        self.assertEqual(comptes['approuvee'], 0)

    def test_isolation_societe(self):
        autre = make_company('ntp2p47-autre', 'NTP2P47 Autre')
        DemandeAchat.objects.create(
            company=autre, reference='DA-X', objet='x',
            statut=DemandeAchat.Statut.COMMANDEE)
        comptes = comptes_demandes_achat_par_statut(self.company)
        self.assertEqual(comptes['commandee'], 0)

    def test_borne_par_date_creation(self):
        da = DemandeAchat.objects.create(
            company=self.company, reference='DA-OLD', objet='x',
            statut=DemandeAchat.Statut.COMMANDEE)
        DemandeAchat.objects.filter(pk=da.pk).update(
            date_creation=timezone.now() - timedelta(days=90))

        hier = date.today() - timedelta(days=1)
        comptes = comptes_demandes_achat_par_statut(self.company, debut=hier)
        self.assertEqual(comptes['commandee'], 0)

        comptes_sans_borne = comptes_demandes_achat_par_statut(self.company)
        self.assertEqual(comptes_sans_borne['commandee'], 1)
