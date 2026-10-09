"""ACRM35 (C-ACRM-030) — un geste de cadence à la fois par lead.

Sonde V_VB LSVC1-2 : deux initialisations entrelacées du plan de relance
créaient deux touches ``('contact', 1)`` ouvertes. ``initialiser_plan_relance``,
``materialiser_touche_suivante`` et ``marquer_etape_relance`` (et les jumeaux
``assurer_prochaine_etape_apres_succes``, ``reprendre_cadence_apres_reouverture``)
s'exécutent désormais sous ``transaction.atomic()`` APRÈS un verrou de ligne
sur le lead : la lecture d'idempotence se fait après le verrou.

``TransactionTestCase`` : deux VRAIES transactions (deux threads, deux
connexions) sur la base de test de la session ; aucune doublure du code
testé (l'entrelacement est provoqué en retenant le premier appel dans
``calculer_echeances_cadence``, appelée réellement).
"""
import threading
from collections import Counter

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase

from authentication.models import Company

from apps.crm import services, stages
from apps.crm.models import Lead, RelanceEtape

User = get_user_model()


def _dans_un_thread(fonction, resultats, cle):
    def corps():
        try:
            resultats[cle] = fonction()
        except Exception as exc:  # noqa: BLE001 — remonté au test
            resultats[cle] = exc
        finally:
            connection.close()
    fil = threading.Thread(target=corps)
    fil.start()
    return fil


class CadenceVerrouTests(TransactionTestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM35 Solaire', slug='acrm35-verrou')
        self.user = User.objects.create_user(
            username='acrm35-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Verrou', owner=self.user,
            stage=stages.CONTACTED, telephone='+212661353535')
        RelanceEtape.objects.filter(lead=self.lead).delete()

    def _ouvertes_par_cle(self):
        return Counter(RelanceEtape.objects.filter(
            lead=self.lead, statut=RelanceEtape.Statut.A_FAIRE
        ).values_list('cadence', 'ordre'))

    def _initialiser(self):
        lead = Lead.objects.get(pk=self.lead.pk)
        user = User.objects.get(pk=self.user.pk)
        return services.initialiser_plan_relance(lead, user, cadence='contact')

    def test_entrelacement_un_seul_plan(self):
        """Le premier appel est RETENU au milieu de son calcul pendant
        qu'un second démarre : sans verrou, le second crée le plan puis le
        premier en crée un autre ; avec le verrou, le second attend."""
        vrai_calcul = services.calculer_echeances_cadence
        second_lance = threading.Event()
        resultats = {}
        fils = []

        def calcul_retenu(*args, **kwargs):
            if not second_lance.is_set():
                second_lance.set()
                fils.append(_dans_un_thread(
                    self._initialiser, resultats, 'second'))
                fils[0].join(timeout=1.5)
            return vrai_calcul(*args, **kwargs)

        services.calculer_echeances_cadence = calcul_retenu
        try:
            premier = {}
            fil = _dans_un_thread(self._initialiser, premier, 'premier')
            fil.join(timeout=30)
            for autre in fils:
                autre.join(timeout=30)
        finally:
            services.calculer_echeances_cadence = vrai_calcul
        for valeur in list(premier.values()) + list(resultats.values()):
            self.assertNotIsInstance(valeur, Exception, valeur)
        ouvertes = self._ouvertes_par_cle()
        self.assertEqual(ouvertes[('contact', 1)], 1, ouvertes)

    def test_deux_threads_un_seul_plan(self):
        depart = threading.Barrier(2)
        resultats = {}

        def initialiser_ensemble():
            depart.wait(timeout=10)
            return self._initialiser()

        fils = [_dans_un_thread(initialiser_ensemble, resultats, i)
                for i in range(2)]
        for fil in fils:
            fil.join(timeout=30)
        for valeur in resultats.values():
            self.assertNotIsInstance(valeur, Exception, valeur)
        ouvertes = self._ouvertes_par_cle()
        self.assertEqual(ouvertes[('contact', 1)], 1, ouvertes)

    def test_double_fait_une_suivante(self):
        services.initialiser_plan_relance(
            self.lead, self.user, cadence='contact')
        touche = (RelanceEtape.objects
                  .filter(lead=self.lead, statut=RelanceEtape.Statut.A_FAIRE)
                  .order_by('ordre').first())
        issue = ('pas_de_reponse'
                 if touche.canal == RelanceEtape.Canal.APPEL else '')
        depart = threading.Barrier(2)
        resultats = {}

        def fait():
            etape = RelanceEtape.objects.select_related('lead').get(
                pk=touche.pk)
            user = User.objects.get(pk=self.user.pk)
            depart.wait(timeout=10)
            return services.marquer_etape_relance(
                etape, user, RelanceEtape.Statut.FAIT, outcome=issue)

        fils = [_dans_un_thread(fait, resultats, i) for i in range(2)]
        for fil in fils:
            fil.join(timeout=30)
        for valeur in resultats.values():
            self.assertNotIsInstance(valeur, Exception, valeur)
        ouvertes = self._ouvertes_par_cle()
        self.assertTrue(all(n == 1 for n in ouvertes.values()), ouvertes)
