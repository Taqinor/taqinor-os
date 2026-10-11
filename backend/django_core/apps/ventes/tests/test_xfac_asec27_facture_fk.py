"""ASEC27 (C-ASEC-005 site (a), C-ASEC-009 volet facture ; frère TFAC-8) —
chaque FK inscriptible de `FactureWriteSerializer` (`client`, `devis`,
`bon_commande`, `lead`, `entite`, `condition_paiement_ref`) et de
`LigneFactureSerializer` (`produit`, `source_devis`) est bornée à la société
de la requête, et les champs posés par le serveur (`statut`, `revue_statut`,
`abandon_*`, `retenue_liberee_le`, `statut_teledeclaration`, `fichier_ubl`,
`pdf_render_meta`, `updated_by`) sont en lecture seule.

Rouge sur 51f22174f (V5 : 200/201, écho `client_nom` du voisin,
`payee`/`validee` sans activité ; V1 TFAC-8 : `solde_devis` d'un devis voisin
0 → 45 000). Endpoints réels, aucun mock.

Appelants front relevés (grep) : `frontend/src/pages/ventes/FactureForm.jsx`
envoie `statut` (sélecteur) — désormais ignoré par le serveur ; le statut ne
bouge que par les actions dédiées (validation, paiement, abandon).

ENF17 — même borne sur la facture d'une ligne, les FK du sérialiseur de
LECTURE (`FactureSerializer`, + `abandon_par`), l'avoir, la note de débit et
leurs lignes, la promesse, l'affectation et la ligne de remise ; les fils
(relances, chatter) sont en lecture seule.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_xfac_asec27_facture_fk"
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class FactureFkEtChampsServeurTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client, Lead
        from apps.entites.models import Entite
        from apps.parametres.models_payment_terms import ConditionPaiement
        from apps.stock.models import Produit
        from apps.ventes.models import BonCommande, Devis, Facture, LigneDevis
        from authentication.models import Company

        self.a = Company.objects.create(nom='ASEC27 A', slug='asec27-a')
        self.b = Company.objects.create(nom='ASEC27 B', slug='asec27-b')
        self.user = User.objects.create_user(
            username='asec27_resp', password='x', role_legacy='responsable',
            company=self.a)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        def _monde(company, suffixe):
            client = Client.objects.create(
                company=company, nom=f'Client {suffixe}', prenom='X',
                email=f'asec27-{suffixe}@example.invalid',
                telephone=f'+21260000{len(suffixe):04d}')
            devis = Devis.objects.create(
                company=company, reference=f'DEV-ASEC27-{suffixe}',
                client=client, statut=Devis.Statut.ACCEPTE,
                taux_tva=Decimal('20.00'), mode_installation='residentiel')
            LigneDevis.objects.create(
                devis=devis, designation='Centrale', quantite=Decimal('1'),
                prix_unitaire=Decimal('125000'), taux_tva=Decimal('20.00'))
            return {
                'client': client,
                'devis': devis,
                # AFAC66 — BC LIBRE (sans devis) : poser le BC d'un devis
                # sur une facture est refusé (seule porte : creer-facture).
                'bon_commande': BonCommande.objects.create(
                    company=company, reference=f'BC-ASEC27-{suffixe}',
                    client=client,
                    statut=BonCommande.Statut.CONFIRME),
                'lead': Lead.objects.create(
                    company=company, nom='Lead', prenom=suffixe),
                'entite': Entite.objects.create(
                    company=company, nom=f'Entité {suffixe}',
                    code=f'E-{suffixe}'),
                'condition_paiement_ref': ConditionPaiement.objects.create(
                    company=company, libelle=f'30 jours {suffixe}'),
                'produit': Produit.objects.create(
                    company=company, nom=f'Produit {suffixe}',
                    sku=f'ASEC27-{suffixe}', prix_vente=Decimal('10'),
                    quantite_stock=1),
            }

        self.ma = _monde(self.a, 'A')
        self.mb = _monde(self.b, 'B')
        self.facture = Facture.objects.create(
            company=self.a, reference='FAC-ASEC27-1',
            client=self.ma['client'], statut=Facture.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), created_by=self.user)

    FK_FACTURE = ('client', 'devis', 'bon_commande', 'lead', 'entite',
                  'condition_paiement_ref')

    def _url(self):
        return f'/api/django/ventes/factures/{self.facture.id}/'

    def test_fk_etrangere_400(self):
        from apps.ventes.models import Facture, LigneFacture
        for champ in self.FK_FACTURE:
            with self.subTest(champ=champ):
                r = self.api.patch(self._url(), {champ: self.mb[champ].pk},
                                   format='json')
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn(champ, r.data)
                self.assertNotIn('Client B', str(r.data))
                # Inexistant → 400, jamais 500.
                r = self.api.patch(self._url(), {champ: 999999},
                                   format='json')
                self.assertEqual(r.status_code, 400, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.client_id, self.ma['client'].pk)
        self.assertIsNone(self.facture.devis_id)
        # Création d'une facture avec un client voisin : refusée.
        avant = Facture.objects.count()
        r = self.api.post('/api/django/ventes/factures/',
                          {'client': self.mb['client'].pk,
                           'taux_tva': '20.00'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Facture.objects.count(), avant)
        # Lignes : produit et devis source voisins refusés.
        for champ, valeur in (('produit', self.mb['produit'].pk),
                              ('source_devis', self.mb['devis'].pk)):
            with self.subTest(ligne=champ):
                corps = {'facture': self.facture.id, 'designation': 'X',
                         'quantite': '1', 'prix_unitaire': '10',
                         'produit': self.ma['produit'].pk}
                corps[champ] = valeur
                r = self.api.post('/api/django/ventes/factures-lignes/',
                                  corps, format='json')
                self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(LigneFacture.objects.filter(
            facture=self.facture).exists())

    def test_patch_statut_sans_effet(self):
        from apps.ventes.models import Facture, FactureActivity
        avant = FactureActivity.objects.filter(facture=self.facture).count()
        r = self.api.patch(self._url(), {
            'statut': 'payee', 'abandon_par': self.user.pk,
            'updated_by': self.user.pk, 'abandon_montant': '10.00',
            'statut_teledeclaration': 'soumise',
            'pdf_render_meta': {'x': 1}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.BROUILLON)
        self.assertIsNone(self.facture.abandon_par_id)
        self.assertEqual(self.facture.statut_teledeclaration, 'non_soumise')
        self.assertFalse(self.facture.pdf_render_meta)
        self.assertEqual(
            FactureActivity.objects.filter(facture=self.facture,
                                           field='statut').count(), 0)
        self.assertGreaterEqual(
            FactureActivity.objects.filter(facture=self.facture).count(),
            avant)

    def test_patch_revue_statut_sans_effet(self):
        avant = self.facture.revue_statut
        r = self.api.patch(self._url(), {'revue_statut': 'validee'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.revue_statut, avant)

    def test_solde_devis_autre_societe_inchange(self):
        from apps.ventes.utils.echeancier import solde_devis
        devis_b = self.mb['devis']
        avant = solde_devis(devis_b)
        r = self.api.patch(self._url(), {'devis': devis_b.pk},
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
        devis_b.refresh_from_db()
        self.assertEqual(solde_devis(devis_b), avant)

    def test_ids_societe_ok(self):
        corps = {champ: self.ma[champ].pk for champ in self.FK_FACTURE}
        r = self.api.patch(self._url(), corps, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.facture.refresh_from_db()
        for champ in self.FK_FACTURE:
            self.assertEqual(getattr(self.facture, f'{champ}_id'),
                             self.ma[champ].pk, champ)
        r = self.api.post('/api/django/ventes/factures-lignes/', {
            'facture': self.facture.id, 'designation': 'Panneau',
            'quantite': '1', 'prix_unitaire': '10',
            'produit': self.ma['produit'].pk,
            'source_devis': self.ma['devis'].pk}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    # ── ENF17 ────────────────────────────────────────────────────────────
    def _facture_b(self):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.b, reference='FAC-ENF17-B', client=self.mb['client'],
            statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20.00'))

    def _avance(self, company, client):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=company, client=client, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('100'), date_paiement=date(2026, 10, 1),
            mode='virement')

    def _assert_borne(self, cls, champ, propre, etranger):
        ctx = {'request': SimpleNamespace(user=self.user)}
        with self.subTest(serializer=cls.__name__, champ=champ):
            ser = cls(data={champ: etranger.pk}, partial=True, context=ctx)
            self.assertFalse(ser.is_valid())
            self.assertEqual(ser.errors[champ][0].code, 'does_not_exist')
            champ_lie = cls(context=ctx).fields[champ]
            self.assertEqual(champ_lie.to_internal_value(propre.pk), propre)

    def test_enf17_ligne_facture_etrangere_comme_absent(self):
        from apps.ventes.models import LigneFacture
        facture_b = self._facture_b()
        corps = {'designation': 'X', 'quantite': '1', 'prix_unitaire': '10',
                 'produit': self.ma['produit'].pk}
        url = '/api/django/ventes/factures-lignes/'
        r = self.api.post(url, {**corps, 'facture': facture_b.id},
                          format='json')
        absent = self.api.post(url, {**corps, 'facture': 999999},
                               format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['facture'][0].code, 'does_not_exist')
        self.assertEqual(
            str(r.data['facture'][0]).replace(str(facture_b.id), '<ID>'),
            str(absent.data['facture'][0]).replace('999999', '<ID>'))
        self.assertFalse(LigneFacture.objects.filter(facture=facture_b).exists())

    def test_enf17_serialiseurs_facturation_bornes(self):
        from apps.ventes import serializers_facturation as sf
        facture_b = self._facture_b()
        paiement_a = self._avance(self.a, self.ma['client'])
        paiement_b = self._avance(self.b, self.mb['client'])
        user_b = User.objects.create_user(
            username='asec27_b', password='x', role_legacy='responsable',
            company=self.b)
        for champ in self.FK_FACTURE:
            self._assert_borne(sf.FactureSerializer, champ,
                               self.ma[champ], self.mb[champ])
        self._assert_borne(sf.FactureSerializer, 'abandon_par',
                           self.user, user_b)
        facture = (self.facture, facture_b)
        client = (self.ma['client'], self.mb['client'])
        produit = (self.ma['produit'], self.mb['produit'])
        paiement = (paiement_a, paiement_b)
        for cls, champ, (propre, etranger) in (
                (sf.AvoirSerializer, 'client', client),
                (sf.AvoirSerializer, 'facture', facture),
                (sf.NoteDebitSerializer, 'client', client),
                (sf.NoteDebitSerializer, 'facture', facture),
                (sf.LigneAvoirSerializer, 'produit', produit),
                (sf.LigneNoteDebitSerializer, 'produit', produit),
                (sf.PromessePaiementSerializer, 'facture', facture),
                (sf.AffectationPaiementSerializer, 'facture', facture),
                (sf.AffectationPaiementSerializer, 'paiement', paiement),
                (sf.LigneRemiseEncaissementSerializer, 'paiement', paiement)):
            self._assert_borne(cls, champ, propre, etranger)

    def test_enf17_fils_facture_lecture_seule_jamais_ecrits(self):
        from apps.ventes import serializers_facturation as sf
        facture_b = self._facture_b()
        ctx = {'request': SimpleNamespace(user=self.user)}
        for cls in (sf.RelanceLogSerializer, sf.FactureActivitySerializer):
            with self.subTest(serializer=cls.__name__):
                ser = cls(data={'facture': facture_b.id}, partial=True,
                          context=ctx)
                self.assertTrue(ser.is_valid(), ser.errors)
                self.assertNotIn('facture', ser.validated_data)
                self.assertIn('facture', cls.same_company_fields)
