"""ACAL91 (C-ACAL-115) — « Réviser » émet l'événement de domaine
``core.events.devis_revise(ancien, nouveau, user)`` APRÈS le commit, une fois,
en best-effort, sans toucher aucun statut (règle #4).

Source réelle : le bus synchrone ``core.events`` et ``reviser_devis`` réels
(aucun des deux n'est mocké ; seul un abonné de test est branché).
Test-du-test : retirer l'émission de ``reviser_devis`` rend le premier test
rouge (aucun appel reçu).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_devis_revise_evenement"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company
from core import event_catalog
from core.events import devis_revise

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class ReviserEmetDevisRevise(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACAL91 Co', slug='acal91-co')
        self.user = User.objects.create_user(
            username='acal91_resp', password='x', role_legacy='responsable',
            company=self.company)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ACAL91',
            email='acal91@example.test', telephone='+212600009110')
        produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='ACAL91-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.v1 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-91010',
            client=client, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user)
        LigneDevis.objects.create(
            devis=self.v1, produit=produit, designation=produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        self.recus = []

    def _abonner(self, recepteur):
        devis_revise.connect(recepteur, weak=False,
                             dispatch_uid='acal91-test-%s' % id(recepteur))
        self.addCleanup(devis_revise.disconnect,
                        dispatch_uid='acal91-test-%s' % id(recepteur))

    def test_reviser_emet_devis_revise_une_fois_apres_commit(self):
        def _recepteur(sender, ancien, nouveau, user, **kwargs):
            self.recus.append((ancien.pk, nouveau.pk, user))

        self._abonner(_recepteur)
        with self.captureOnCommitCallbacks(execute=False) as rappels:
            v2 = reviser_devis(self.v1, user=self.user)
            # Rien n'est émis tant que la transaction n'a pas commité.
            self.assertEqual(self.recus, [])
        self.assertEqual(self.recus, [])
        for rappel in rappels:
            rappel()

        self.assertEqual(self.recus, [(self.v1.pk, v2.pk, self.user)])
        self.v1.refresh_from_db()
        # Règle #4 : le statut de la V1 n'est jamais écrit.
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)
        self.assertFalse(self.v1.is_active)
        self.assertEqual(self.v1.superseded_by_id, v2.pk)
        # Catalogué (NTPLT12) avec ses clés de payload.
        self.assertEqual(event_catalog.CATALOG['devis_revise']['payload'],
                         ['ancien', 'nouveau', 'user'])

    def test_abonne_en_echec_ne_casse_pas_la_revision(self):
        def _boum(sender, **kwargs):
            raise RuntimeError('abonné en panne')

        def _temoin(sender, ancien, nouveau, user, **kwargs):
            self.recus.append(nouveau.pk)

        self._abonner(_boum)
        self._abonner(_temoin)
        with self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user)

        self.assertTrue(Devis.objects.filter(pk=v2.pk).exists())
        self.assertEqual(self.recus, [v2.pk])
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)
        self.assertFalse(self.v1.is_active)
        self.assertEqual(self.v1.superseded_by_id, v2.pk)


def espionner_etudes(test, journal, mesure=None):
    """R6-N1 — enveloppe (sans le remplacer) LE calcul des études appelé par
    le clonage ET par la révision : chaque appel inscrit ``('etudes', pk,
    force, mesure(devis))`` dans ``journal`` puis appelle la vraie fonction."""
    from unittest import mock

    from apps.ventes.domain import creation_clone, revision
    from apps.ventes.domain.etudes import rafraichir_etudes_du_devis as reelle

    def _espion(devis, **kwargs):
        journal.append(('etudes', devis.pk, kwargs.get('force'),
                        mesure(devis) if mesure else None))
        return reelle(devis, **kwargs)

    for module in (creation_clone, revision):
        patch = mock.patch.object(module, 'rafraichir_etudes_du_devis',
                                  side_effect=_espion)
        patch.start()
        test.addCleanup(patch.stop)


def hors_transaction(test):
    """R6-N1 — rejoue le chemin de la vue « Réviser » (appel hors de toute
    transaction) sous un ``TestCase`` : la décision seule est forcée."""
    from unittest import mock

    from apps.ventes.domain import revision
    patch = mock.patch.object(revision, '_hors_transaction', return_value=True)
    patch.start()
    test.addCleanup(patch.stop)


class EtudesDeLaRevision(TestCase):
    """R6-N1 — sans calepinage, les études de la V2 sont celles d'hier ; hors
    transaction (la vue), elles sont calculées UNE fois, APRÈS les abonnés de
    ``devis_revise`` (le calepinage y est re-lié), hors du verrou de la V1."""

    setUp = ReviserEmetDevisRevise.setUp
    _abonner = ReviserEmetDevisRevise._abonner

    def _jumelle(self):
        """Une seconde V1, mêmes lignes et même étude (numéro voisin)."""
        jumelle = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-91011',
            client=self.v1.client, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user,
            etude_params=self.v1.etude_params)
        for ligne in self.v1.lignes.all():
            LigneDevis.objects.create(
                devis=jumelle, produit=ligne.produit,
                designation=ligne.designation, quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire, remise=ligne.remise)
        return jumelle

    def _abonne_temoin(self, journal):
        def _temoin(sender, ancien, nouveau, user, **kwargs):
            journal.append(('abonne', nouveau.pk))
        self._abonner(_temoin)

    def test_dans_une_transaction_un_seul_calcul_comme_hier(self):
        journal = []
        espionner_etudes(self, journal)
        self._abonne_temoin(journal)
        with self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user)
        self.assertEqual(journal, [('etudes', v2.pk, True, None),
                                   ('abonne', v2.pk)])

    def test_hors_transaction_un_seul_calcul_apres_les_abonnes(self):
        journal = []
        espionner_etudes(self, journal)
        self._abonne_temoin(journal)
        hors_transaction(self)
        with self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user)
        self.assertEqual(journal, [('abonne', v2.pk),
                                   ('etudes', v2.pk, True, None)])

    def test_sans_calepinage_la_v2_porte_les_etudes_d_hier(self):
        """Mêmes études qu'une V2 révisée par le chemin d'hier (sous
        transaction, calcul dans le clonage), à l'octet."""
        jumelle = self._jumelle()
        with self.captureOnCommitCallbacks(execute=True):
            hier = reviser_devis(jumelle, user=self.user)
        hors_transaction(self)
        with self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user)
        hier.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(v2.etude_params, hier.etude_params)

        def _lignes(devis):
            return list(devis.lignes.order_by('ordre', 'id').values_list(
                'designation', 'quantite', 'prix_unitaire', 'remise'))
        self.assertEqual(_lignes(v2), _lignes(hier))

    def test_etudes_en_echec_journalisees_revision_actee(self):
        from unittest import mock

        from apps.ventes.domain import revision

        hors_transaction(self)
        with mock.patch.object(revision, 'rafraichir_etudes_du_devis',
                               side_effect=RuntimeError('PVGIS en panne')), \
                self.assertLogs('apps.ventes.services', 'ERROR') as sortie, \
                self.captureOnCommitCallbacks(execute=True):
            v2 = reviser_devis(self.v1, user=self.user)
        self.assertTrue(any('R6-N1' in ligne and v2.reference in ligne
                            for ligne in sortie.output), sortie.output)
        self.v1.refresh_from_db()
        self.assertFalse(self.v1.is_active)
        self.assertEqual(self.v1.superseded_by_id, v2.pk)
        self.assertEqual(self.v1.statut, Devis.Statut.ENVOYE)
