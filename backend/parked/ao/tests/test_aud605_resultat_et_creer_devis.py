"""AUD605 — le résultat d'un AO a UN SEUL chemin, et un AO mort ne fait plus
de devis.

Deux portes ouvertes sur le même modèle :

1. ``ResultatAOViewSet`` était un ``ModelViewSet`` standard : un POST direct
   sur ``/resultats-ao/`` créait un résultat « gagné » SANS faire suivre le
   statut de l'appel d'offres, sans chatter et sans émettre ``ao_gagne`` —
   l'événement auquel le CRM s'abonne pour avancer le lead à SIGNED. Le
   résultat existait, l'AO restait « déposé », le lead ne bougeait pas, et rien
   ne le disait.
2. ``creer-devis`` ne vérifiait AUCUN statut : le bordereau d'un AO PERDU
   produisait un devis, en consommant une référence DEV réelle.

Run :
    python manage.py test apps.ao.tests.test_aud605_resultat_et_creer_devis -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BordereauPrix, LigneBordereau, ResultatAO, SectionBordereau,
)
from apps.ao.permissions import AO_GERER, AO_VOIR
from apps.crm.models import Lead
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/ao/'
CLAUSE = ('Marché à prix unitaires : les quantités portées au présent '
          'bordereau sont prévisionnelles.')


class BaseAO(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD605 Co',
                                              slug='aud605-co')
        self.lead = Lead.objects.create(
            company=self.company, nom='Commune urbaine de Rabat',
            email='marches@rabat.ma')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-605-1',
            objet='Centrale PV 500 kWc', lead_id=self.lead.pk)
        self.bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao, clause_reserve=CLAUSE)
        section = SectionBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=1,
            libelle='Bâtiment A')
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, section=section,
            numero=1, designation='Modules 625 Wc', unite='U',
            quantite=Decimal('100.000'), prix_unitaire=Decimal('1200.00'))
        role = Role.objects.create(company=self.company, nom='AUD605 gestion',
                                   permissions=[AO_VOIR, AO_GERER])
        self.user = User.objects.create_user(
            username='aud605', password='x', company=self.company, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _forcer_statut(self, statut):
        """Pose un statut SANS passer par le service.

        ``AppelOffre.save()`` interdit la mutation directe du statut (AOF13) ;
        ``queryset.update()`` contourne ``save()`` par construction — c'est
        documenté dans le modèle, et c'est le seul moyen de fabriquer un état
        de DÉPART pour un test sans rejouer tout le cycle.
        """
        AppelOffre.objects.filter(pk=self.ao.pk).update(statut=statut)
        self.ao.refresh_from_db()


class TestResultatEnLectureSeule(BaseAO):
    def setUp(self):
        super().setUp()
        # Le résultat d'ouverture des plis n'existe qu'après le dépôt.
        self._forcer_statut(AppelOffre.Statut.DEPOSE)

    def test_post_direct_refuse(self):
        reponse = self.api.post(f'{BASE}resultats-ao/', {
            'appel_offre': self.ao.pk,
            'issue': ResultatAO.Issue.GAGNE,
        }, format='json')
        self.assertEqual(reponse.status_code, 405, reponse.data)
        self.assertEqual(ResultatAO.objects.count(), 0)

    def test_patch_direct_refuse(self):
        resultat = services.enregistrer_resultat_ao(
            self.ao, issue=ResultatAO.Issue.PERDU, user=self.user)
        reponse = self.api.patch(
            f'{BASE}resultats-ao/{resultat.pk}/',
            {'issue': ResultatAO.Issue.GAGNE}, format='json')
        self.assertEqual(reponse.status_code, 405, reponse.data)
        resultat.refresh_from_db()
        self.assertEqual(resultat.issue, ResultatAO.Issue.PERDU)

    def test_delete_direct_refuse(self):
        resultat = services.enregistrer_resultat_ao(
            self.ao, issue=ResultatAO.Issue.PERDU, user=self.user)
        reponse = self.api.delete(f'{BASE}resultats-ao/{resultat.pk}/')
        self.assertEqual(reponse.status_code, 405)
        self.assertTrue(ResultatAO.objects.filter(pk=resultat.pk).exists())

    def test_la_lecture_reste_ouverte(self):
        services.enregistrer_resultat_ao(
            self.ao, issue=ResultatAO.Issue.PERDU, user=self.user)
        reponse = self.api.get(f'{BASE}resultats-ao/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['count'], 1)

    def test_l_action_enregistrer_fait_suivre_le_statut(self):
        """Le SEUL chemin d'écriture — et il fait tout le travail."""
        reponse = self.api.post(f'{BASE}resultats-ao/enregistrer/', {
            'appel_offre': self.ao.pk,
            'issue': ResultatAO.Issue.GAGNE,
        }, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.ao.refresh_from_db()
        self.assertEqual(self.ao.statut, AppelOffre.Statut.GAGNE)


class TestCreerDevisSelonLeStatut(BaseAO):
    def _creer_devis(self):
        return self.api.post(
            f'{BASE}bordereaux-prix/{self.bordereau.pk}/creer-devis/')

    def test_un_ao_perdu_ne_fait_plus_de_devis(self):
        self._forcer_statut(AppelOffre.Statut.PERDU)
        reponse = self._creer_devis()
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('appel_offre', reponse.data)

    def test_un_ao_abandonne_ne_fait_plus_de_devis(self):
        self._forcer_statut(AppelOffre.Statut.ABANDONNE)
        self.assertEqual(self._creer_devis().status_code, 400)

    def test_le_chiffrage_normal_reste_ouvert(self):
        """Le chiffrage PRÉCÈDE le dépôt : l'interdire aurait tué le chemin."""
        for statut in (AppelOffre.Statut.CHIFFRAGE,
                       AppelOffre.Statut.PRET_A_DEPOSER,
                       AppelOffre.Statut.DEPOSE,
                       AppelOffre.Statut.GAGNE):
            with self.subTest(statut=statut):
                self.assertIsNone(
                    services.refus_de_creation_de_devis(
                        AppelOffre(statut=statut)))

    def test_un_ao_vivant_cree_bien_son_devis(self):
        reponse = self._creer_devis()
        self.assertEqual(reponse.status_code, 201, reponse.data)


class TestRegleLisibleHorsDeLaVue(BaseAO):
    """La règle est une DONNÉE : l'écran et les tests la lisent au même endroit."""

    def test_les_statuts_refuses_sont_les_terminaux_negatifs(self):
        self.assertEqual(
            set(services.STATUTS_SANS_DEVIS),
            {AppelOffre.Statut.PERDU, AppelOffre.Statut.ABANDONNE})

    def test_le_motif_nomme_le_statut(self):
        motif = services.refus_de_creation_de_devis(
            AppelOffre(statut=AppelOffre.Statut.PERDU))
        self.assertIn('Perdu', motif)
