"""Décision fondateur (08/10/2026) — ``annuler_acceptation`` (dés-acceptation).

Porte de ``ventes`` appelée quand un lead sort de « Signé » : le devis
repasse « envoyé », ses tampons d'acceptation sont effacés, les variantes
sœurs refusées PAR cette acceptation (et elles seules) reviennent, et un aval
réel (bon de commande, facture…) bloque sans rien écrire.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_desacceptation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes import services
from apps.ventes.models import BonCommande, Devis, DevisActivity
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class TestAnnulerAcceptation(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='desaccept-co', defaults={'nom': 'Désaccept Co'})
        self.user = User.objects.create_user(
            username='desaccept_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Variante',
            email='variante@example.com', telephone='+212600000088')

    def _devis(self, num, parent=None, **kw):
        kw.setdefault('statut', Devis.Statut.ENVOYE)
        kw.setdefault('date_envoi', timezone.now())
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{9100 + num}',
            client=self.client_obj, version_parent=parent,
            taux_tva=Decimal('20'), **kw)

    def _accepter(self, devis):
        return services.accept_devis(
            devis=devis, user=self.user, nom='M. Variante',
            option=Devis.OptionAcceptee.SANS_BATTERIE)

    def test_soeurs_refusees_par_l_acceptation_reviennent_seules(self):
        racine = self._devis(1)
        variante = self._devis(2, parent=racine)
        brouillon = self._devis(3, parent=racine, statut=Devis.Statut.BROUILLON,
                                date_envoi=None)
        refusee_avant = self._devis(
            4, parent=racine, statut=Devis.Statut.REFUSE, is_active=False,
            motif_refus='trop cher', date_refus=timezone.localdate())
        self._accepter(variante)
        racine.refresh_from_db()
        brouillon.refresh_from_db()
        self.assertEqual(racine.statut, Devis.Statut.REFUSE)
        self.assertEqual(brouillon.statut, Devis.Statut.REFUSE)

        services.annuler_acceptation(
            devis=variante, user=self.user, motif='test')

        variante.refresh_from_db()
        racine.refresh_from_db()
        brouillon.refresh_from_db()
        refusee_avant.refresh_from_db()
        self.assertEqual(variante.statut, Devis.Statut.ENVOYE)
        self.assertIsNone(variante.date_acceptation)
        self.assertEqual(variante.accepte_par_nom, '')
        self.assertEqual(variante.option_acceptee, '')
        # Envoyée avant → « envoyé » ; jamais envoyée → « brouillon ».
        self.assertEqual(racine.statut, Devis.Statut.ENVOYE)
        self.assertTrue(racine.is_active)
        self.assertEqual(racine.motif_refus, '')
        self.assertIsNone(racine.date_refus)
        self.assertEqual(brouillon.statut, Devis.Statut.BROUILLON)
        self.assertTrue(brouillon.is_active)
        # Refusée pour une AUTRE raison : jamais rétablie.
        self.assertEqual(refusee_avant.statut, Devis.Statut.REFUSE)
        self.assertFalse(refusee_avant.is_active)
        note = DevisActivity.objects.filter(
            devis=variante, body__contains='Acceptation annulée').first()
        self.assertIsNotNone(note)
        self.assertIn('Sans batterie', note.body)
        self.assertIn('M. Variante', note.body)
        self.assertIn('preuve de signature', note.body)

    def test_bon_de_commande_bloque_sans_rien_ecrire(self):
        devis = self._devis(10)
        self._accepter(devis)
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-9110',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        with self.assertRaises(services.AnnulationAcceptationBloquee) as ctx:
            services.annuler_acceptation(devis=devis, user=self.user)
        self.assertIn(bc.reference, ctx.exception.message)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertIsNotNone(devis.date_acceptation)

    def test_bon_de_commande_annule_ne_bloque_pas(self):
        devis = self._devis(11)
        self._accepter(devis)
        BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-9111',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.ANNULE)
        self.assertIsNone(
            services.raison_blocage_annulation_acceptation(devis))

    def test_devis_non_accepte_no_op(self):
        devis = self._devis(12)
        rendu = services.annuler_acceptation(devis=devis, user=self.user)
        self.assertEqual(rendu.statut, Devis.Statut.ENVOYE)
        self.assertFalse(DevisActivity.objects.filter(
            devis=devis, body__contains='Acceptation annulée').exists())

    def test_reacceptation_est_fraiche(self):
        devis = self._devis(13)
        self._accepter(devis)
        services.annuler_acceptation(devis=devis, user=self.user)
        devis.refresh_from_db()
        self._accepter(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(devis.option_acceptee,
                         Devis.OptionAcceptee.SANS_BATTERIE)
        self.assertEqual(devis.date_acceptation, timezone.now().date())
