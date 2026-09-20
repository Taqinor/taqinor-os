"""
NTP2P38 — Événements domaine Procure-to-Pay sur le bus ``core/events.py``.

CRITÈRE D'ACCEPTATION : approuver une demande d'achat déclenche l'événement,
visible sur le bus et consommable par un abonné de test (le rôle qu'aurait une
``AutomationRule``). Idem pour l'attribution d'une RFQ.

Ce qui est prouvé ici :
  * ``demande_achat_approuvee`` part sur les DEUX chemins d'approbation (le
    guichet unique XKB1 et la dernière étape d'un plan NTP2P2), et JAMAIS sur
    un refus ni sur une étape intermédiaire ;
  * ``rfq_attribuee`` part à l'adjudication, avec le BCF gagnant ;
  * un abonné qui lève n'empêche PAS l'approbation d'aboutir (best-effort) —
    aucun appel HTTP automatique n'est fait par le bus lui-même.

Run :
    python manage.py test apps.installations.test_ntp2p38_evenements_p2p -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.installations import services
from apps.installations.models import (
    RFQ, DemandeAchat, DemandeAchatLigne, EtapeApprobationAchat,
    RFQOffre, RegleApprobationAchat,
)
from apps.stock.models import Fournisseur

from core.events import demande_achat_approuvee, rfq_attribuee

User = get_user_model()
_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ntp2p38-co-{n}', defaults={'nom': f'NTP2P38 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p38-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_demande(company, user, *, montant, soumise=True):
    da = DemandeAchat.objects.create(
        company=company, reference=f'DA-NTP2P38-{next(_seq):04d}',
        objet='Réquisition NTP2P38', created_by=user)
    DemandeAchatLigne.objects.create(
        demande=da, designation='Onduleur', quantite=1, prix_estime=montant)
    if soumise:
        da.statut = DemandeAchat.Statut.SOUMISE
        da.save(update_fields=['statut'])
    return da


class BusMixin:
    """Branche un abonné de test sur un signal, et le débranche à la fin."""

    def abonner(self, signal, uid):
        recus = []

        def recepteur(sender, **kwargs):
            recus.append(kwargs)

        signal.connect(recepteur, dispatch_uid=uid)
        self.addCleanup(signal.disconnect, recepteur, dispatch_uid=uid)
        return recus


class DemandeAchatApprouveeTests(BusMixin, TestCase):
    """Le guichet unique XKB1 (``decider_demande_achat``)."""

    def setUp(self):
        self.company = make_company()
        self.demandeur = make_user(self.company)
        self.decideur = make_user(self.company)
        self.recus = self.abonner(
            demande_achat_approuvee, 'ntp2p38-test-da')

    def test_approbation_emet_levenement_une_fois(self):
        da = make_demande(self.company, self.demandeur, montant=12000)

        services.decider_demande_achat(
            da, approuver=True, user=self.decideur)

        self.assertEqual(len(self.recus), 1)
        charge = self.recus[0]
        self.assertEqual(charge['demande'].pk, da.pk)
        self.assertEqual(charge['company'].pk, self.company.pk)
        self.assertEqual(charge['user'].pk, self.decideur.pk)
        self.assertEqual(Decimal(charge['montant_estime']), Decimal('12000'))
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)

    def test_refus_nemet_rien(self):
        da = make_demande(self.company, self.demandeur, montant=900)

        services.decider_demande_achat(
            da, approuver=False, user=self.decideur, motif_refus='hors budget')

        self.assertEqual(self.recus, [])
        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.REFUSEE)

    def test_decision_invalide_nemet_rien(self):
        da = make_demande(
            self.company, self.demandeur, montant=900, soumise=False)

        with self.assertRaises(services.DecisionError):
            services.decider_demande_achat(
                da, approuver=True, user=self.decideur)

        self.assertEqual(self.recus, [])

    def test_un_abonne_qui_leve_ne_casse_pas_lapprobation(self):
        def casse(sender, **kwargs):
            raise RuntimeError('webhook injoignable')

        demande_achat_approuvee.connect(casse, dispatch_uid='ntp2p38-casse')
        self.addCleanup(
            demande_achat_approuvee.disconnect, casse,
            dispatch_uid='ntp2p38-casse')

        da = make_demande(self.company, self.demandeur, montant=500)
        with self.assertLogs('apps.installations.services',
                             level='WARNING'):
            services.decider_demande_achat(
                da, approuver=True, user=self.decideur)

        da.refresh_from_db()
        self.assertEqual(da.statut, DemandeAchat.Statut.APPROUVEE)


class ApprobationParEtapesTests(BusMixin, TestCase):
    """Un plan à 2 paliers (NTP2P2) : une SEULE émission, à la fin."""

    def setUp(self):
        self.company = make_company()
        self.demandeur = make_user(self.company)
        self.premier = make_user(self.company)
        self.second = make_user(self.company)
        RegleApprobationAchat.objects.create(
            company=self.company, libelle='Direction ×2',
            montant_min=1000, nombre_approbateurs=2, actif=True)
        self.da = make_demande(self.company, self.demandeur, montant=50000)
        self.etapes = services.lancer_workflow_approbation_achat(self.da)
        self.recus = self.abonner(
            demande_achat_approuvee, 'ntp2p38-test-etapes')

    def test_etape_intermediaire_nemet_rien_la_derniere_emet(self):
        self.assertEqual(len(self.etapes), 2)

        services.approuver_etape_achat(
            self.etapes[0], approbateur=self.premier)
        self.assertEqual(self.recus, [])
        self.da.refresh_from_db()
        self.assertNotEqual(self.da.statut, DemandeAchat.Statut.APPROUVEE)

        services.approuver_etape_achat(
            self.etapes[1], approbateur=self.second)
        self.assertEqual(len(self.recus), 1)
        self.assertEqual(self.recus[0]['demande'].pk, self.da.pk)
        self.assertEqual(self.recus[0]['user'].pk, self.second.pk)
        self.da.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.APPROUVEE)

    def test_rejet_detape_nemet_rien(self):
        services.rejeter_etape_achat(
            self.etapes[0], approbateur=self.premier, commentaire='non')

        self.assertEqual(self.recus, [])
        self.da.refresh_from_db()
        self.assertEqual(self.da.statut, DemandeAchat.Statut.REFUSEE)
        restantes = self.da.etapes_approbation.filter(
            statut=EtapeApprobationAchat.Statut.EN_ATTENTE).count()
        self.assertEqual(restantes, 0)


class RfqAttribueeTests(BusMixin, TestCase):

    def setUp(self):
        self.company = make_company()
        self.acheteur = make_user(self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P38')
        self.rfq = RFQ.objects.create(
            company=self.company, reference=f'RFQ-NTP2P38-{next(_seq):04d}',
            objet='Consultation NTP2P38', created_by=self.acheteur)
        self.offre = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq,
            fournisseur=self.fournisseur, montant_ht=Decimal('8000'),
            retenue=True)
        self.recus = self.abonner(rfq_attribuee, 'ntp2p38-test-rfq')

    def test_attribution_emet_la_rfq_loffre_et_le_bcf(self):
        services.marquer_rfq_attribuee(
            self.rfq, self.offre, user=self.acheteur, bon_commande_id=4242)

        self.assertEqual(len(self.recus), 1)
        charge = self.recus[0]
        self.assertEqual(charge['rfq'].pk, self.rfq.pk)
        self.assertEqual(charge['offre'].pk, self.offre.pk)
        self.assertEqual(charge['company'].pk, self.company.pk)
        self.assertEqual(charge['user'].pk, self.acheteur.pk)
        self.assertEqual(charge['bon_commande_id'], 4242)

    def test_un_abonne_qui_leve_ne_remonte_jamais(self):
        def casse(sender, **kwargs):
            raise RuntimeError('webhook injoignable')

        rfq_attribuee.connect(casse, dispatch_uid='ntp2p38-rfq-casse')
        self.addCleanup(
            rfq_attribuee.disconnect, casse,
            dispatch_uid='ntp2p38-rfq-casse')

        with self.assertLogs('apps.installations.services', level='WARNING'):
            services.marquer_rfq_attribuee(
                self.rfq, self.offre, user=self.acheteur)
