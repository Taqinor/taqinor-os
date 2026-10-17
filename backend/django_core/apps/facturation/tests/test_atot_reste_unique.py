"""ATOT7 (C-ATOT-005) — `solde_devis.restant` et l'annulation « rembourser /
transférer » lisent la définition unique du payé et du reste
(`Facture.montant_paye`, `montant_du`) : plus d'avoir de révision compté deux
fois, plus de paiement rejeté remboursé.

Rejoue les sondes V1 TFAC-5 (restant 120 000 au lieu de 135 000 après une
révision à la baisse) et TFAC-9 (paiement négatif −45 000 d'un chèque jamais
encaissé). Services et endpoints réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_reste_unique"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class ResteUniqueTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT7 Co', slug=f'atot7-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Reste', prenom='ATOT7',
            email=f'atot7-{_nxt()}@example.invalid')
        self.admin = User.objects.create_user(
            username=f'atot7_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        # La ligne produit du devis porte son produit du catalogue
        # (`LigneFacture.produit` est NOT NULL : sans lui, facturer-complet → 500).
        from apps.stock.models import Produit
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit ATOT7', sku=f'ATOT7-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _devis(self):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT7-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        self.ligne = LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _complete(self, devis):
        from apps.ventes.models import Facture
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
            {'paiements': []}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Facture.objects.get(pk=r.data['facture_id'])

    def _solde(self, devis):
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import solde_devis
        return solde_devis(Devis.objects.get(pk=devis.pk))

    def test_restant_revision_baisse(self):
        from apps.ventes.models import Avoir, Facture
        devis = self._devis()
        for _ in range(3):
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/',
                {}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
        solde_facture = Facture.objects.filter(devis=devis).order_by('-id')[0]
        # Révision V2 : 112 500 HT = 135 000 TTC ; avoir de révision 15 000.
        self.ligne.prix_unitaire = Decimal('112500')
        self.ligne.save(update_fields=['prix_unitaire'])
        Avoir.objects.create(
            company=self.company, reference=f'AV-ATOT7-{_nxt()}',
            facture=solde_facture, client=self.client_obj,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=Decimal('12500.00'), montant_tva=Decimal('2500.00'),
            montant_ttc=Decimal('15000.00'), motif='Révision V2')
        solde = self._solde(devis)
        self.assertEqual(solde['total_ttc'], Decimal('135000.00'))
        self.assertEqual(solde['restant'], Decimal('135000.00'))

    def test_restant_note_debit_et_ras(self):
        from apps.ventes.models import NoteDebit, RetenueSubie
        devis = self._devis()
        facture = self._complete(devis)
        NoteDebit.objects.create(
            company=self.company, reference=f'ND-ATOT7-{_nxt()}',
            facture=facture, client=self.client_obj,
            statut=NoteDebit.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=Decimal('1000.00'), montant_tva=Decimal('200.00'),
            montant_ttc=Decimal('1200.00'), motif='Pénalité')
        self.assertEqual(self._solde(devis)['restant'], Decimal('151200.00'))
        RetenueSubie.objects.create(
            company=self.company, facture=facture, taux=Decimal('75.00'),
            base=Decimal('4000.00'), montant=Decimal('3000.00'))
        facture.refresh_from_db()
        solde = self._solde(devis)
        self.assertEqual(solde['restant'], Decimal('148200.00'))
        self.assertEqual(solde['restant'], facture.montant_du)

    def _rejeter(self, facture, montant):
        from apps.ventes.domain.recouvrement import rejeter_paiement
        from apps.ventes.models import Paiement
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=date.today(), mode='cheque')
        rejeter_paiement(paiement=paiement, motif='Chèque impayé',
                         user=self.admin)
        return paiement

    def test_rembourser_ignore_paiement_rejete(self):
        from apps.ventes.models import Facture, Paiement
        facture = self._complete(self._devis())
        self._rejeter(facture, '45000')
        self.api.post(
            f'/api/django/ventes/factures/{facture.id}/annuler/',
            {'acompte': {'action': 'rembourser'}}, format='json')
        facture = Facture.objects.get(pk=facture.pk)
        self.assertFalse(Paiement.objects.filter(
            facture=facture, montant__lt=0).exists())
        self.assertEqual(Decimal(str(facture.montant_paye)), Decimal('0.00'))

    def test_transferer_ignore_paiement_rejete(self):
        from apps.ventes.models import Devis, Facture, Paiement
        devis = self._devis()
        acompte_r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')
        materiel_r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')
        acompte = Facture.objects.get(pk=acompte_r.data['id'])
        cible = Facture.objects.get(pk=materiel_r.data['id'])
        rejete = self._rejeter(acompte, '45000')
        bon = Paiement.objects.create(
            company=self.company, facture=acompte, montant=Decimal('10000'),
            date_paiement=date.today(), mode='virement')
        r = self.api.post(
            f'/api/django/ventes/factures/{acompte.id}/annuler/',
            {'acompte': {'action': 'transferer', 'facture_cible': cible.id}},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        rejete.refresh_from_db()
        bon.refresh_from_db()
        self.assertEqual(rejete.facture_id, acompte.id)
        self.assertEqual(bon.facture_id, cible.id)
        cible = Facture.objects.get(pk=cible.pk)
        self.assertEqual(Decimal(str(cible.montant_paye)), Decimal('10000.00'))
        self.assertTrue(Devis.objects.filter(pk=devis.pk).exists())


class EtatVenteVNT23Tests(TestCase):
    """VNT23 — ``vente_facturation.etat_vente`` (contrat
    ``ventes/contract_samples/vente_etat.json``) : toute la chaîne, brouillon
    = prévu, révision en cours ⇒ tous gestes fermés, ``peut`` = même
    prédicat que les permissions des vues."""

    def setUp(self):
        from apps.crm.models import Lead
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.lead = Lead.objects.create(company=self.company, nom='VNT23')

    def _devis(self, statut='accepte', **champs):
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        return creer_devis_388(self.company, self.user, self.client_obj,
                               f'DEV-VNT23-{_nxt()}', statut=statut,
                               lead=self.lead, **champs)

    def _reviser(self, v1, statut='accepte'):
        from apps.ventes.models import Devis
        v2 = self._devis(statut=statut, version=v1.version + 1,
                         version_parent=v1.version_parent or v1)
        Devis.objects.filter(pk=v1.pk).update(is_active=False,
                                              superseded_by=v2)
        return Devis.objects.get(pk=v2.pk)

    def _facture(self, devis, cle, ttc, statut='emise', reference=None):
        from apps.ventes.tests.test_echeancier_somme_total import (
            facture_tranche)
        ht = (Decimal(ttc) / Decimal('1.18')).quantize(Decimal('0.01'))
        return facture_tranche(
            devis, reference or f'FAC-VNT23-{_nxt()}', cle, ttc, str(ht),
            str(Decimal(ttc) - ht), statut=statut)

    def _contrat(self):
        import json
        from pathlib import Path
        chemin = (Path(__file__).resolve().parents[2] / 'ventes'
                  / 'contract_samples' / 'vente_etat.json')
        return json.loads(chemin.read_text(encoding='utf-8'))

    def test_chaine_kharbachi_et_cles_du_contrat(self):
        from apps.ventes.models import Devis, Paiement
        from apps.ventes.vente_facturation import etat_vente
        v367 = self._devis(remise_globale=Decimal('0'))
        v387 = self._reviser(v367)
        v388 = self._reviser(v387)
        f6 = self._facture(v367, 'materiel', '32700.00')
        f7 = self._facture(v387, 'acompte', '14700.00', statut='payee')
        Paiement.objects.create(
            company=self.company, facture=f7, montant=Decimal('14700'),
            date_paiement=date(2026, 10, 12), mode='virement')
        f8 = self._facture(v388, 'solde', '1600.00')
        v389 = self._devis()
        self._facture(v389, 'acompte', '14700.00')
        etat = etat_vente(Devis.objects.get(pk=v388.pk), self.user)
        self.assertEqual(etat['prix_convenu_ttc'], '49000.00')
        self.assertEqual({f['id'] for f in etat['factures']},
                         {f6.pk, f7.pk, f8.pk})
        self.assertEqual(etat['paye_ttc'], '14700.00')
        self.assertEqual(etat['reste_a_payer_ttc'], '34300.00')
        self.assertEqual([v['id'] for v in etat['versions']],
                         [v367.pk, v387.pk, v388.pk])
        self.assertTrue(etat['est_tete'])
        exemple = self._contrat()['exemple_acompte_paye_solde_a_faire']
        self.assertEqual(set(etat), set(exemple['vente']))
        facture = exemple['vente']['factures'][0]
        servie = next(f for f in etat['factures'] if f['id'] == f7.pk)
        self.assertEqual(set(servie), set(facture))
        self.assertEqual(set(servie['peut']), set(facture['peut']))
        self.assertEqual(set(servie['paiements'][0]),
                         set(facture['paiements'][0]))
        self.assertEqual(set(etat['peut']), set(exemple['vente']['peut']))
        ancienne = etat_vente(Devis.objects.get(pk=v387.pk), self.user)
        self.assertFalse(ancienne['est_tete'])
        self.assertEqual(ancienne['tete_id'], v388.pk)
        self.assertFalse(any(ancienne['peut'].values()))
        self.assertIn('remplacée', ancienne['raison_bloquee'])

    def test_un_brouillon_ne_bloque_rien(self):
        from apps.ventes.tests.test_echeancier_somme_total import (
            ECHEANCIER_LIBRE)
        from apps.ventes.vente_facturation import etat_vente
        devis = self._devis(echeancier=ECHEANCIER_LIBRE)
        brouillon = self._facture(devis, 'acompte', '15000.00',
                                  statut='brouillon',
                                  reference=f'BROUILLON-{_nxt()}')
        etat = etat_vente(devis, self.user)
        self.assertEqual(etat['brouillons_ttc'], '15000.00')
        self.assertEqual(etat['emis_ttc'], '0.00')
        self.assertEqual(etat['reste_a_facturer_ttc'], '34000.00')
        self.assertEqual(etat['reste_a_payer_ttc'], '49000.00')
        # VNT62 / VNT82 (nocturne #726) : le brouillon d'acompte ne ferme pas
        # « Facturer l'acompte » — le geste REPREND ce brouillon (AMET4).
        self.assertTrue(etat['peut']['facturer_acompte'])
        self.assertFalse(etat['peut']['facturer_solde'])
        self.assertEqual(etat['factures'][0]['id'], brouillon.pk)
        self.assertTrue(etat['factures'][0]['peut']['emettre'])
        self.assertTrue(etat['factures'][0]['peut']['supprimer'])
        self.assertEqual(etat['raison_bloquee'],
                         "L'acompte est en brouillon : émettez-le.")
        self.assertEqual(
            [(e['libelle'], e['montant_ttc'])
             for e in etat['prochaines_echeances']],
            [('Livraison du matériel', '29400.00'), ('Solde', '4600.00')])

    def test_revision_en_cours_ferme_tous_les_gestes(self):
        from apps.ventes.vente_facturation import etat_vente
        v1 = self._devis()
        v2 = self._reviser(v1, statut='brouillon')
        v1.refresh_from_db()
        etat = etat_vente(v1, self.user)
        self.assertEqual(etat['revision_en_cours'],
                         {'id': v2.pk, 'reference': v2.reference})
        self.assertTrue(etat['est_tete'])
        self.assertEqual(etat['tete_id'], v1.pk)
        self.assertFalse(any(etat['peut'].values()))
        self.assertEqual(etat['prochaine_action'], 'aucune')
        self.assertTrue(etat['raison_bloquee'].startswith(
            f'Révision {v2.reference} en cours'))

    def test_parite_des_peut_sur_quatre_roles(self):
        from types import SimpleNamespace
        from apps.ventes.vente_facturation import etat_vente
        from apps.ventes.views.facture import FactureViewSet
        from authentication.permissions import (
            IsAdminOrResponsableTier, IsResponsableOrAdmin)
        devis = self._devis()
        self._facture(devis, 'acompte', '14700.00')
        self._facture(devis, 'materiel', '29400.00', statut='brouillon',
                      reference=f'BROUILLON-{_nxt()}')
        roles = [User.objects.create_user(
            username=f'vnt23_{role}_{_nxt()}', password='x',
            role_legacy=role, company=self.company)
            for role in ('admin', 'responsable', 'normal')]
        su = User.objects.create_superuser(
            username=f'vnt23_su_{_nxt()}', password='x', email='')
        su.company = self.company
        su.save(update_fields=['company'])
        for user in roles + [su]:
            with self.subTest(user=user.username):
                req = SimpleNamespace(user=user, method='POST')
                vue = FactureViewSet()
                attendu = (
                    IsAdminOrResponsableTier().has_permission(req, vue)
                    and IsResponsableOrAdmin().has_permission(req, vue))
                etat = etat_vente(devis, user)
                emise, brouillon = etat['factures']
                self.assertEqual(emise['peut']['annuler'], attendu)
                self.assertEqual(brouillon['peut']['supprimer'], attendu)
                self.assertEqual(brouillon['peut']['modifier_montant'],
                                 attendu)
                self.assertEqual(etat['peut']['prix_negocie'], attendu)
        normal = etat_vente(devis, roles[2])
        self.assertFalse(normal['factures'][0]['peut']['annuler'])
