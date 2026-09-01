"""QJR134 — l'aval de l'acceptation devient atomique, verrouillé et rejouable.

Trois constats frères de l'audit du 30/08/2026, traités ensemble parce qu'ils
décrivent le MÊME défaut : la vente n'était pas enregistrée d'un bloc.

  · ES3 — le ``with transaction.atomic()`` se refermait juste après le
    ``save`` du statut : chatter, signature, attribution, effondrement des
    sœurs et ``devis_accepted.send`` s'exécutaient hors transaction et hors
    verrou, sans ``ATOMIC_REQUESTS``. Un échec chez UN abonné (``send()``
    propage la première exception) laissait un devis « accepté » SANS bon de
    commande ni facture — et la garde d'idempotence rendait le rejeu
    impossible : l'état partiel était PERMANENT et SILENCIEUX.
  · ES14 — le verrou ne portait que sur LA ligne du devis accepté ;
    l'effondrement des sœurs s'exécutait hors de lui et sans
    ``select_for_update`` : deux POST concurrents sur deux jetons du même
    groupe de variantes acceptaient les DEUX.
  · ES11 — l'échec de ``_create_esign_record`` est avalé en WARNING, et
    l'email affirmait quand même au client « Votre signature électronique a
    été enregistrée ».

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr134_acceptation_atomique -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis, DevisSignature, EmailLog
from apps.ventes.services import AcceptError, accept_devis
from authentication.models import Company
from core.events import devis_accepted

PHRASE_SIGNATURE = 'Votre signature électronique a été enregistrée'

RESEAU = 'Onduleur réseau Huawei 10kW Monophasé'
PANNEAU = 'Panneau Canadian Solar 710W'


class _BaseAcceptation(TestCase):
    """Un groupe de VARIANTES : la racine et sa sœur, toutes deux envoyées."""

    slug = 'qjr134'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR134',
            email='qjr134-%s@example.com' % self.slug)
        self._sku = 0
        self.racine = self._devis('DEV-QJR134-A')
        self.soeur = self._devis('DEV-QJR134-B', parent=self.racine)

    def _devis(self, ref, *, parent=None):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            mode_installation='residentiel', is_active=True,
            version=(parent.version + 1 if parent else 1),
            version_parent=parent)
        for nom, qte, pu in ((PANNEAU, '10', '1166.67'),
                             (RESEAU, '1', '15000.00')):
            self._sku += 1
            produit = Produit.objects.create(
                company=self.company, nom=nom,
                sku='QJR134-%d-%s' % (self._sku, self.company.pk),
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=50)
            creer_ligne(devis, produit=produit, designation=nom,
                        quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                        remise=Decimal('0'))
        return devis


class _AbonneEnEchec:
    """Un abonné à ``devis_accepted`` qui lève — connecté le temps du bloc."""

    UID = 'qjr134-abonne-en-echec'

    def __enter__(self):
        devis_accepted.connect(self._boom, dispatch_uid=self.UID, weak=False)
        return self

    def __exit__(self, *exc):
        devis_accepted.disconnect(dispatch_uid=self.UID)
        return False

    @staticmethod
    def _boom(sender, **kwargs):
        raise RuntimeError('abonné en échec (simulé)')


class LAvalEstDansLaMemeTransaction(_BaseAcceptation):
    """ES3 — soit la vente entière est enregistrée, soit RIEN ne l'est."""

    slug = 'qjr134-atomique'

    def test_un_abonne_en_echec_annule_toute_la_vente(self):
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client',
                             ip='81.0.0.1')

        self.racine.refresh_from_db()
        self.assertEqual(
            self.racine.statut, Devis.Statut.ENVOYE,
            "le statut a été commité SEUL : c'est exactement l'état partiel "
            'permanent et silencieux que QJR134 ferme.')
        self.assertEqual(self.racine.option_acceptee or '', '')
        self.assertIsNone(self.racine.date_acceptation)

    def test_la_preuve_de_signature_est_annulee_avec_le_reste(self):
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 0)

    def test_l_effondrement_des_soeurs_est_annule_avec_le_reste(self):
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.soeur.refresh_from_db()
        self.assertEqual(self.soeur.statut, Devis.Statut.ENVOYE)
        self.assertTrue(self.soeur.is_active)

    def test_aucun_email_ne_part_pour_une_vente_annulee(self):
        """Les entrées-sorties restent APRÈS le commit, donc jamais atteintes
        sur un rollback : un email annonçant une vente annulée serait pire que
        pas d'email du tout."""
        with _AbonneEnEchec():
            with self.assertRaises(RuntimeError):
                accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(EmailLog.objects.filter(devis=self.racine).count(), 0)

    def test_le_chemin_nominal_enregistre_tout(self):
        """Le TÉMOIN : sans abonné en échec, l'acceptation complète passe."""
        accept_devis(devis=self.racine, user=None, nom='M. Client',
                     ip='81.0.0.1')
        self.racine.refresh_from_db()
        self.soeur.refresh_from_db()
        self.assertEqual(self.racine.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(self.racine.accepte_par_nom, 'M. Client')
        self.assertEqual(self.soeur.statut, Devis.Statut.REFUSE)
        self.assertFalse(self.soeur.is_active)
        self.assertEqual(self.soeur.motif_refus, 'variante non retenue')
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 1)


class LeGroupeDeVariantesEstVerrouille(_BaseAcceptation):
    """ES14 — deux POST concurrents sur deux jetons du même groupe."""

    slug = 'qjr134-verrou'

    def test_le_verrou_porte_sur_le_groupe_entier(self):
        with CaptureQueriesContext(connection) as requetes:
            accept_devis(devis=self.racine, user=None, nom='M. Client')
        verrous_groupe = [
            q['sql'] for q in requetes.captured_queries
            if 'FOR UPDATE' in q['sql'] and 'version_parent_id' in q['sql']]
        self.assertTrue(
            verrous_groupe,
            "aucun SELECT ... FOR UPDATE ne couvre le GROUPE : l'effondrement "
            'des sœurs redevient une course entre deux acceptations.')
        # Ordre DÉTERMINISTE : deux acceptations concurrentes prennent les
        # verrous dans le même ordre, donc l'une attend au lieu de bloquer.
        self.assertIn('ORDER BY', verrous_groupe[0])

    def test_une_soeur_effondree_ne_peut_plus_etre_acceptee(self):
        """Le résultat OBSERVABLE que le verrou garantit : le groupe ne produit
        qu'UNE vente."""
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        with self.assertRaises(AcceptError) as leve:
            accept_devis(devis=self.soeur, user=None, nom='M. Client')
        self.assertTrue(leve.exception.conflict)
        self.racine.refresh_from_db()
        self.soeur.refresh_from_db()
        self.assertEqual(self.racine.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(self.soeur.statut, Devis.Statut.REFUSE)

    def test_un_devis_sans_variante_est_inchange(self):
        """Le groupe d'un devis seul, c'est lui-même : rien à effondrer."""
        seul = self._devis('DEV-QJR134-SEUL')
        accept_devis(devis=seul, user=None, nom='M. Client')
        seul.refresh_from_db()
        self.assertEqual(seul.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(seul.is_active)


class LeRejeuDeLAval(_BaseAcceptation):
    """Le drapeau de complétion : « accepté » signifie désormais que l'aval a
    été commité — et l'aval d'un devis accepté AVANT ce lot reste rejouable."""

    slug = 'qjr134-rejeu'

    def setUp(self):
        super().setUp()
        self.publications = []
        devis_accepted.connect(self._compter, dispatch_uid='qjr134-compteur',
                               weak=False)
        self.addCleanup(devis_accepted.disconnect,
                        dispatch_uid='qjr134-compteur')

    def _compter(self, sender, devis, **kwargs):
        self.publications.append(devis.pk)

    def test_le_resubmit_reste_un_no_op_par_defaut(self):
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(len(self.publications), 1)
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(len(self.publications), 1,
                         'un double envoi ne re-publie pas la vente')

    def test_rejouer_aval_republie_et_reeffondre(self):
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        # On reconstitue l'état PARTIEL d'un devis accepté avant ce lot : le
        # statut est là, l'aval n'a pas été fait.
        Devis.objects.filter(pk=self.soeur.pk).update(
            statut=Devis.Statut.ENVOYE, is_active=True, motif_refus='')

        accept_devis(devis=self.racine, user=None, rejouer_aval=True)

        self.assertEqual(len(self.publications), 2)
        self.soeur.refresh_from_db()
        self.assertEqual(self.soeur.statut, Devis.Statut.REFUSE)
        self.assertFalse(self.soeur.is_active)

    def test_rejouer_aval_ne_retouche_ni_le_statut_ni_le_tampon(self):
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.racine.refresh_from_db()
        avant = (self.racine.statut, self.racine.accepte_par_nom,
                 self.racine.date_acceptation, self.racine.option_acceptee)

        accept_devis(devis=self.racine, user=None, nom='QUELQU_UN_D_AUTRE',
                     rejouer_aval=True)

        self.racine.refresh_from_db()
        self.assertEqual(
            (self.racine.statut, self.racine.accepte_par_nom,
             self.racine.date_acceptation, self.racine.option_acceptee), avant)
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 1)


class LEmailNePromentQueLaPreuveQuiExiste(_BaseAcceptation):
    """ES11 — « Votre signature électronique a été enregistrée », affirmé
    inconditionnellement alors que l'enregistrement pouvait ne pas exister."""

    slug = 'qjr134-email'

    def _corps_email(self, devis):
        log = EmailLog.objects.filter(devis=devis).order_by('-id').first()
        self.assertIsNotNone(log, 'aucun email de confirmation envoyé')
        return log.corps or ''

    def test_avec_enregistrement_la_phrase_est_servie(self):
        accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertIn(PHRASE_SIGNATURE, self._corps_email(self.racine))

    def test_sans_enregistrement_la_phrase_disparait(self):
        """``_create_esign_record`` est best-effort : son échec est avalé en
        WARNING. L'email ne doit alors plus rien affirmer."""
        with patch('apps.ventes.domain.cycle_vie._create_esign_record',
                   return_value=None):
            accept_devis(devis=self.racine, user=None, nom='M. Client')
        self.assertEqual(
            DevisSignature.objects.filter(devis=self.racine).count(), 0)
        corps = self._corps_email(self.racine)
        self.assertNotIn(PHRASE_SIGNATURE, corps)
        self.assertNotIn('exemplaire signé', corps)
        # Le reste de l'email — l'accusé de réception — part comme avant.
        self.assertIn('Nous avons bien reçu votre acceptation', corps)
