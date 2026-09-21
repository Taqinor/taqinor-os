"""AUD612 — une étape d'approbation créée par le flux NORMAL porte un
approbateur.

Les deux relances d'approbation (NTCPQ28 manuelle, NTCPQ33 planifiée) étaient
écrites, testées… et mortes : aucune étape ``en_attente`` ne portait jamais
d'approbateur en production, et les deux chemins sautent explicitement une
étape non assignée. Seule une POSE MANUELLE dans les tests les faisait vivre.

Ce module part donc de bout en bout : un devis remisé, ``lancer_approbation_devis``
(le flux normal), puis la relance planifiée qui doit RETROUVER l'approbateur.

Run :
    python manage.py test apps.cpq.tests.test_aud612_assignation_approbateur -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.cpq import services
from apps.cpq.models import (
    EtapeApprobationDevis, RegleApprobationRemise,
)
from apps.cpq.scheduled import relancer_approbations_en_attente
from apps.notifications.models import Notification
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, DevisFactory, UserFactory


class BaseAssignation(TestCase):
    NIVEAU = RegleApprobationRemise.NiveauApprobation.DIRECTION
    NB_APPROBATEURS = 1

    def setUp(self):
        self.company = CompanyFactory()
        RegleApprobationRemise.objects.create(
            company=self.company, libelle='Remise forte',
            remise_min_pct=Decimal('20'), remise_max_pct=Decimal('100'),
            niveau_approbation=self.NIVEAU,
            nombre_approbateurs=self.NB_APPROBATEURS)
        self.devis = DevisFactory(company=self.company,
                                  remise_globale=Decimal('25'))

    def _admin(self, nom):
        return UserFactory(username=nom, company=self.company,
                           role_legacy=CustomUser.ROLE_ADMIN)


class TestFluxNormal(BaseAssignation):
    def test_l_etape_porte_un_approbateur(self):
        admin = self._admin('aud612_admin')
        etapes = services.lancer_approbation_devis(self.devis)
        self.assertEqual(len(etapes), 1)
        self.assertEqual(etapes[0].approbateur_id, admin.pk)

    def test_sans_habilite_l_etape_reste_creee_sans_approbateur(self):
        """Non-régression : le palier ne disparaît pas faute de destinataire."""
        etapes = services.lancer_approbation_devis(self.devis)
        self.assertEqual(len(etapes), 1)
        self.assertIsNone(etapes[0].approbateur_id)

    def test_l_assignation_est_deterministe(self):
        premier = self._admin('aud612_a')
        self._admin('aud612_b')
        etapes = services.lancer_approbation_devis(self.devis)
        self.assertEqual(etapes[0].approbateur_id, premier.pk)

    def test_le_demandeur_n_approuve_pas_sa_propre_remise(self):
        demandeur = self._admin('aud612_demandeur')
        autre = self._admin('aud612_autre')
        etapes = services.lancer_approbation_devis(self.devis, user=demandeur)
        self.assertEqual(etapes[0].approbateur_id, autre.pk)

    def test_seul_habilite_le_demandeur_reste_assigne(self):
        """Mieux vaut une étape assignée à soi qu'une étape jamais relancée."""
        demandeur = self._admin('aud612_seul')
        etapes = services.lancer_approbation_devis(self.devis, user=demandeur)
        self.assertEqual(etapes[0].approbateur_id, demandeur.pk)


class TestPlusieursNiveaux(BaseAssignation):
    NB_APPROBATEURS = 2

    def test_deux_etapes_deux_approbateurs_distincts(self):
        premier = self._admin('aud612_n1')
        second = self._admin('aud612_n2')
        etapes = services.lancer_approbation_devis(self.devis)
        self.assertEqual(
            [e.approbateur_id for e in etapes], [premier.pk, second.pk])

    def test_un_seul_habilite_porte_les_deux_etapes(self):
        seul = self._admin('aud612_unique')
        etapes = services.lancer_approbation_devis(self.devis)
        self.assertEqual({e.approbateur_id for e in etapes}, {seul.pk})


class TestPalierResponsable(BaseAssignation):
    NIVEAU = RegleApprobationRemise.NiveauApprobation.RESPONSABLE

    def test_un_responsable_est_retenu(self):
        responsable = UserFactory(
            username='aud612_resp', company=self.company,
            role_legacy=CustomUser.ROLE_RESPONSABLE)
        UserFactory(username='aud612_lecteur', company=self.company,
                    role_legacy=CustomUser.ROLE_NORMAL)
        etapes = services.lancer_approbation_devis(self.devis)
        self.assertEqual(etapes[0].approbateur_id, responsable.pk)

    def test_repli_sur_les_admins_si_aucun_responsable(self):
        admin = self._admin('aud612_repli')
        etapes = services.lancer_approbation_devis(self.devis)
        self.assertEqual(etapes[0].approbateur_id, admin.pk)


class TestLaRelanceRetrouveLApprobateur(BaseAssignation):
    """LE point du constat : la relance planifiée cesse d'être du code mort."""

    def test_la_relance_planifiee_notifie_l_approbateur_assigne(self):
        admin = self._admin('aud612_relance')
        etapes = services.lancer_approbation_devis(self.devis)
        # Le seuil par défaut est de 2 jours : on recule la création (le champ
        # est en auto_now_add, donc via update()).
        EtapeApprobationDevis.objects.filter(id=etapes[0].id).update(
            date_creation=timezone.now() - timedelta(days=3))

        self.assertEqual(relancer_approbations_en_attente(), 1)
        self.assertTrue(Notification.objects.filter(
            recipient=admin, event_type='approval_reminder').exists())

    def test_la_relance_manuelle_ne_refuse_plus_l_etape(self):
        self._admin('aud612_manuelle')
        services.lancer_approbation_devis(self.devis)
        _etape, envoyee = services.relancer_etape_approbation(self.devis)
        self.assertTrue(envoyee)
