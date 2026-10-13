# -*- coding: utf-8 -*-
"""VNT47 (D-VNT-4, D-VNT-5) — ``manage.py reparer_vente_active``.

Nouveau fichier car : commande neuve sans module de test (patron
``test_reparer_devis_deux_options.py``).

Réplique du dossier Kharbachi (lead 1594, prod 12/10/2026) : chaîne
367 (V1) → 387 (V2) → 388 (V3, en vigueur) + chaîne neuve 389 (acceptée par
lien public, signature gardée) ; FAC-0005 acompte 16 350 annulée, 0006
matériel 32 700 émise (avoir 50 annulé), 0007 acompte 14 700 PAYÉE (saisie
14 700, le client a viré 15 000), 0008 solde 1 600 émise, 0009 acompte
14 700 émise sur 389. Cible : 388 seule vente, 389 dés-acceptée + archivée,
0006-0009 annulées par avoir, saisie 14 700 annulée, acompte 15 000 émis et
payé (HT 12 720,41 / TVA 2 279,59), reste 34 000 = 29 400 + 4 600.

Run :
    DB_NAME=erp_ventes python manage.py test \\
        apps.ventes.tests.test_reparer_vente_active -v 2
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client, Lead
from apps.ventes.models import (
    Avoir, BonCommande, Devis, DevisSignature, EmailLog, Facture, Paiement,
)
from apps.ventes.tests._quote_engine_common import make_company
from apps.ventes.tests.test_echeancier_somme_total import (
    creer_devis_388, facture_tranche)

User = get_user_model()
MOIS = '202610'


def _ref(numero):
    return f'FAC-{MOIS}-{numero:04d}'


class TestReparerVenteActive(TestCase):

    def setUp(self):
        self.company = make_company(slug='vnt47-co', nom='VNT47 Co')
        self.user = User.objects.create_user(
            username='vnt47_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Kharbachi', prenom='Tijani',
            email='tijani@example.com', telephone='+212600001594')
        self.lead = Lead.objects.create(
            company=self.company, nom='Kharbachi', prenom='Tijani',
            telephone='+212600001594', ville='Casablanca')
        self._chaines()
        self._factures()
        self._effets_389()
        self._autre_societe()

    # ── Réplique ────────────────────────────────────────────────────────────
    def _devis(self, numero, **champs):
        return creer_devis_388(
            self.company, self.user, self.client_obj,
            f'DEV-{MOIS}-{numero:04d}', None, lead=self.lead, **champs)

    def _chaines(self):
        self.d367 = self._devis(367, is_active=False)
        self.d387 = self._devis(387, version=2, is_active=False,
                                version_parent=self.d367)
        self.d388 = self._devis(388, version=3, version_parent=self.d367)
        Devis.objects.filter(pk=self.d367.pk).update(superseded_by=self.d387)
        Devis.objects.filter(pk=self.d387.pk).update(superseded_by=self.d388)
        self.d389 = self._devis(389)
        DevisSignature.objects.create(
            company=self.company, devis=self.d389,
            signataire_nom='Tijani Kharbachi', consentement_explicite=True,
            signed_at=timezone.now())

    def _factures(self):
        d = self.d388
        self.f5 = facture_tranche(d, _ref(5), 'acompte', '16350.00',
                                  '13865.24', '2484.76', statut='annulee')
        self.f6 = facture_tranche(d, _ref(6), 'materiel', '32700.00',
                                  '27730.48', '4969.52',
                                  type_facture='intermediaire')
        self.f7 = facture_tranche(d, _ref(7), 'acompte', '14700.00',
                                  '12466.00', '2234.00', statut='payee')
        self.f8 = facture_tranche(d, _ref(8), 'solde', '1600.00',
                                  '1356.84', '243.16', type_facture='solde')
        self.f9 = facture_tranche(self.d389, _ref(9), 'acompte', '14700.00',
                                  '12466.00', '2234.00')
        self.p7 = Paiement.objects.create(
            company=self.company, facture=self.f7, montant=Decimal('14700'),
            date_paiement=date.today(), mode='virement',
            created_by=self.user)
        self.avoir50 = Avoir.objects.create(
            company=self.company, type=Avoir.Type.CORRECTION,
            reference=f'AV-{MOIS}-0002', facture=self.f6,
            client=self.client_obj, statut=Avoir.Statut.ANNULEE,
            montant_ht=Decimal('42.40'), montant_tva=Decimal('7.60'),
            montant_ttc=Decimal('50.00'))

    def _effets_389(self):
        from apps.installations.services import create_installation_from_devis
        from apps.sav.models import ContratMaintenance
        self.chantier, _ = create_installation_from_devis(
            self.d389, self.user, self.company)
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, actif=True,
            date_debut=date.today(), periodicite='annuel',
            notes=f'[devis:{self.d389.pk}]')

    def _autre_societe(self):
        self.autre = make_company(slug='vnt47-autre', nom='VNT47 Autre')
        user = User.objects.create_user(
            username='vnt47_autre', password='x', role_legacy='admin',
            company=self.autre)
        client = Client.objects.create(company=self.autre, nom='Autre')
        self.lead_autre = Lead.objects.create(
            company=self.autre, nom='Autre', telephone='+212600009999')
        self.autres_devis = [
            creer_devis_388(self.autre, user, client, f'DEV-B-{n}', None,
                            lead=self.lead_autre)
            for n in ('000501', '000502')]
        self.f_autre = facture_tranche(self.autres_devis[0], 'FAC-B-0001',
                                       'acompte', '14700.00', '12466.00',
                                       '2234.00')

    # ── Outils ──────────────────────────────────────────────────────────────
    def _run(self, *args):
        sortie = StringIO()
        call_command('reparer_vente_active', *args, stdout=sortie)
        return sortie.getvalue()

    def _reparer(self, *extra):
        return self._run(
            '--lead', str(self.lead.pk), '--garder', str(self.d388.pk),
            '--refaire-acompte', '15000', '--paiement-recu', '15000',
            '--paiement-date', date.today().isoformat(),
            '--paiement-mode', 'virement', '--utilisateur', 'vnt47_admin',
            *extra)

    def _etat_base(self):
        from apps.installations.models import Installation
        from apps.sav.models import ContratMaintenance
        return (
            sorted(Devis.objects.values_list(
                'pk', 'statut', 'is_active', 'superseded_by_id',
                'echeancier')),
            sorted(Facture.objects.values_list('pk', 'statut', 'reference')),
            sorted(Paiement.objects.values_list('pk', 'statut', 'facture_id')),
            sorted(Avoir.objects.values_list('pk', 'statut')),
            sorted(Installation.objects.values_list('pk', 'annule')),
            sorted(ContratMaintenance.objects.values_list('pk', 'actif')),
        )

    # ── --lister ────────────────────────────────────────────────────────────
    def test_lister_trouve_le_lead_de_sa_societe(self):
        sortie = self._run('--lister', '--societe', self.company.slug)
        self.assertIn(f'Lead {self.lead.pk}', sortie)
        self.assertIn(self.d388.reference, sortie)
        self.assertIn(self.d389.reference, sortie)
        self.assertIn(_ref(9), sortie)
        self.assertNotIn(f'Lead {self.lead_autre.pk} ', sortie)
        toutes = self._run('--lister', '--toutes-societes')
        self.assertIn(f'Lead {self.lead.pk}', toutes)
        self.assertIn(f'Lead {self.lead_autre.pk}', toutes)

    def test_lister_exige_une_societe(self):
        with self.assertRaises(CommandError):
            self._run('--lister')

    # ── DRY-RUN ─────────────────────────────────────────────────────────────
    def test_dry_run_par_defaut_n_ecrit_rien(self):
        avant = self._etat_base()
        with self.captureOnCommitCallbacks() as rappels:
            sortie = self._reparer()
        self.assertEqual(self._etat_base(), avant)
        self.assertEqual(rappels, [])
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('DRY-RUN', sortie)
        self.assertIn('=== DIFF ===', sortie)
        self.assertIn('saisi 14700.00 ≠ virement reçu 15000.00', sortie)
        self.assertIn(f'{self.d389.reference} dés-acceptée et archivée',
                      sortie)
        self.assertIn('HT 12720.41 / TVA 2279.59', sortie)
        self.assertIn('reste à facturer 34000.00', sortie)

    # ── --appliquer ─────────────────────────────────────────────────────────
    def test_appliquer_atteint_l_etat_cible(self):
        from apps.installations.models import Installation
        from apps.ventes.domain.reparation_vente import ventes_en_vigueur
        from apps.ventes.vente_facturation import etat_vente
        self._reparer('--appliquer')
        self.p7.refresh_from_db()
        self.assertEqual(self.p7.statut, Paiement.Statut.ANNULE_SAISIE)
        self.assertIn('saisi 14700.00 ≠ virement reçu 15000.00',
                      self.p7.motif_annulation)
        for f in (self.f6, self.f7, self.f8, self.f9):
            f.refresh_from_db()
            self.assertEqual(f.statut, Facture.Statut.ANNULEE, f.reference)
            self.assertEqual(
                [(a.type, a.total_ttc) for a in
                 f.avoirs.filter(statut=Avoir.Statut.EMISE)],
                [(Avoir.Type.CORRECTION, f.montant_ttc)])
        self.avoir50.refresh_from_db()
        self.assertEqual(self.avoir50.statut, Avoir.Statut.ANNULEE)
        self.d389.refresh_from_db()
        self.assertEqual(self.d389.statut, Devis.Statut.ENVOYE)
        self.assertFalse(self.d389.is_active)
        self.assertIsNone(self.d389.superseded_by_id)
        self.assertTrue(DevisSignature.objects.filter(
            devis=self.d389).exists())
        self.assertTrue(Installation.objects.get(pk=self.chantier.pk).annule)
        self.contrat.refresh_from_db()
        self.assertFalse(self.contrat.actif)
        self.assertEqual([d.pk for d in ventes_en_vigueur(
            self.company, self.lead.pk)], [self.d388.pk])
        self._verifier_acompte_388()
        etat = etat_vente(self.d388)
        self.assertEqual(etat['reste_a_facturer_ttc'], '34000.00')
        self.assertEqual(etat['paye_ttc'], '15000.00')
        self.assertEqual([e['montant_ttc'] for e in
                          etat['prochaines_echeances']],
                         ['29400.00', '4600.00'])

    def _verifier_acompte_388(self):
        from core.numbering import est_reference_provisoire
        self.d388.refresh_from_db()
        self.assertEqual(self.d388.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(self.d388.is_active)
        self.assertEqual(
            [(e['type'], e['unite'], Decimal(str(e['pct_or_montant'])))
             for e in self.d388.echeancier],
            [('acompte', 'montant', Decimal('15000')),
             ('materiel', 'pct', Decimal('60')),
             ('solde', 'montant', Decimal('4600'))])
        acompte = Facture.objects.exclude(statut=Facture.Statut.ANNULEE).get(
            devis=self.d388)
        self.assertFalse(est_reference_provisoire(acompte.reference))
        self.assertEqual(acompte.statut, Facture.Statut.PAYEE)
        self.assertEqual(acompte.type_facture, 'acompte')
        self.assertEqual(acompte.montant_ttc, Decimal('15000.00'))
        self.assertEqual(acompte.montant_ht, Decimal('12720.41'))
        self.assertEqual(acompte.montant_tva, Decimal('2279.59'))
        self.assertEqual(
            list(acompte.paiements.values_list('montant', 'mode', 'statut')),
            [(Decimal('15000.00'), 'virement', Paiement.Statut.ENCAISSE)])

    def test_deuxieme_application_ne_fait_rien(self):
        self._reparer('--appliquer')
        apres = self._etat_base()
        sortie = self._reparer('--appliquer')
        self.assertIn('Rien à réparer', sortie)
        self.assertEqual(self._etat_base(), apres)

    def test_autre_societe_intouchee(self):
        avant = sorted(Devis.objects.filter(company=self.autre).values_list(
            'pk', 'statut', 'is_active', 'echeancier'))
        self._reparer('--appliquer')
        self.assertEqual(sorted(Devis.objects.filter(
            company=self.autre).values_list(
                'pk', 'statut', 'is_active', 'echeancier')), avant)
        self.f_autre.refresh_from_db()
        self.assertEqual(self.f_autre.statut, Facture.Statut.EMISE)
        self.assertFalse(Avoir.objects.filter(company=self.autre).exists())

    # ── Refus nommés : rien n'est écrit ─────────────────────────────────────
    def test_facture_envoyee_exige_le_drapeau(self):
        EmailLog.objects.create(
            company=self.company, facture=self.f9, client=self.client_obj,
            to_email='tijani@example.com', sujet=self.f9.reference)
        avant = self._etat_base()
        with self.assertRaises(CommandError) as ctx:
            self._reparer('--appliquer')
        self.assertIn('--avoir-meme-si-envoyee', str(ctx.exception))
        self.assertIn(self.f9.reference, str(ctx.exception))
        self.assertEqual(self._etat_base(), avant)
        self._reparer('--appliquer', '--avoir-meme-si-envoyee')
        self.f9.refresh_from_db()
        self.assertEqual(self.f9.statut, Facture.Statut.ANNULEE)

    def test_bon_de_commande_de_l_autre_vente_refuse(self):
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MOIS}-0389',
            devis=self.d389, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        avant = self._etat_base()
        with self.assertRaises(CommandError) as ctx:
            self._reparer('--appliquer')
        self.assertIn(bc.reference, str(ctx.exception))
        self.assertEqual(self._etat_base(), avant)
