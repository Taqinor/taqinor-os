"""Tests YSUBS2 — Beat quotidien : reconduction tacite + diffusion des alertes
contrat.

Couvre : un contrat tacite échu est reconduit par le beat (date injectée via
``date_fin`` déjà dépassée), une alerte de préavis due est diffusée une fois
(idempotence existante), re-run le même jour = 0 doublon, isolation par
société.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats.models import AlerteContrat, Contrat
from apps.contrats.scheduled import reconductions_et_alertes_daily


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_contrat_tacite_echu(company, **kwargs):
    return Contrat.objects.create(
        company=company, objet=kwargs.pop('objet', 'Contrat tacite'),
        statut=Contrat.Statut.ACTIF,
        date_fin=kwargs.pop('date_fin', timezone.localdate() - timedelta(days=1)),
        tacite_reconduction=True, duree_reconduction_mois=12, **kwargs)


def make_contrat_preavis_du(company, **kwargs):
    """Contrat dont l'échéance de préavis (date_fin - preavis_jours) tombe
    EXACTEMENT aujourd'hui — candidat à ``semer_alertes_echeances`` (fenêtre
    ``[today, today+30]`` de ``contrats_a_preavis``) ET immédiatement
    dispatchable par ``declencher_alertes_contrat`` (``date_declenchement
    <= today``)."""
    return Contrat.objects.create(
        company=company, objet=kwargs.pop('objet', 'Contrat préavis'),
        statut=Contrat.Statut.ACTIF,
        date_fin=timezone.localdate() + timedelta(days=10),
        preavis_jours=10, **kwargs)


class ReconductionsEtAlertesBeatTests(TestCase):
    def setUp(self):
        self.company = make_company('ysubs2', 'YSUBS2')

    def test_contrat_tacite_echu_reconduit(self):
        contrat = make_contrat_tacite_echu(self.company)
        ancienne_date_fin = contrat.date_fin

        resultat = reconductions_et_alertes_daily()

        contrat.refresh_from_db()
        self.assertGreater(contrat.date_fin, ancienne_date_fin)
        self.assertEqual(resultat['contrats_reconduits'], 1)

    def test_rerun_meme_jour_ne_reconduit_pas_deux_fois(self):
        make_contrat_tacite_echu(self.company)
        reconductions_et_alertes_daily()
        resultat2 = reconductions_et_alertes_daily()
        self.assertEqual(resultat2['contrats_reconduits'], 0)

    def test_alerte_preavis_due_semee_et_diffusee(self):
        make_contrat_preavis_du(self.company)

        resultat = reconductions_et_alertes_daily()

        self.assertGreaterEqual(resultat['alertes_semees'], 1)
        self.assertGreaterEqual(resultat['alertes_envoyees'], 1)
        self.assertTrue(
            AlerteContrat.objects.filter(
                company=self.company,
                statut=AlerteContrat.Statut.ENVOYEE).exists())

    def test_rerun_meme_jour_pas_de_doublon_alerte(self):
        make_contrat_preavis_du(self.company)
        reconductions_et_alertes_daily()
        nb_avant = AlerteContrat.objects.filter(company=self.company).count()

        resultat2 = reconductions_et_alertes_daily()

        nb_apres = AlerteContrat.objects.filter(company=self.company).count()
        self.assertEqual(nb_avant, nb_apres)
        self.assertEqual(resultat2['alertes_semees'], 0)
        self.assertEqual(resultat2['alertes_envoyees'], 0)

    def test_isolation_societe(self):
        autre = make_company('ysubs2-autre', 'Autre')
        make_contrat_tacite_echu(autre)

        resultat = reconductions_et_alertes_daily()
        self.assertEqual(resultat['contrats_reconduits'], 1)

    def test_contrat_sans_tacite_reconduction_non_reconduit(self):
        Contrat.objects.create(
            company=self.company, objet='Contrat normal',
            statut=Contrat.Statut.ACTIF,
            date_fin=timezone.localdate() - timedelta(days=1),
            tacite_reconduction=False)
        resultat = reconductions_et_alertes_daily()
        self.assertEqual(resultat['contrats_reconduits'], 0)
