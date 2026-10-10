"""ACHT52 (C-ACHT-052) — FK inscriptibles bornées à la société :
`GpsConsentRecordSerializer.technicien`, `LotPrelevementSerializer.operateur`,
`PickListLigneSerializer.bin`, `OrdreAssemblageSerializer.chantier` /
`.ordre_sous_traitance`, `ProjetSerializer.responsable` — un id d'une autre
société donne 400 sans écriture ni nom renvoyé.

Rejoue CTEN-4 : GPS technicien=B 201, LOT operateur=B 200, PICKLIGNE bin=B
200, ORDRE chantier=B 201, PROGRAMME responsable=B 201.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht52_fk_corps_tenant"

ENF17 — étendu à TOUTES les FK cross-app inscriptibles des sérialiseurs
installations (64 sites : produit, emplacement, fournisseur, BCF / facture /
réception fournisseur, pièce jointe, client, lead, devis, ticket SAV, kit
d'outillage) : l'id d'ailleurs = l'id absent (400), l'id de la société reste
accepté (``FkInstallationsBorneesSocieteTests``).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.achats.models import (
    BonCommandeFournisseur, FactureFournisseur, ReceptionFournisseur,
)
from apps.crm.models import Client, Lead
from apps.installations import serializers as S
from apps.installations.models import (
    BinLocation, Installation, Kit, KitComposant, LotPrelevement,
    OrdreSousTraitance, PickList, PickListLigne,
)
from apps.outillage.models import KitOutillage
from apps.records.models import Attachment
from apps.sav.models import Ticket
from apps.stock.models import EmplacementStock, Fournisseur, Produit
from apps.ventes.models import Devis

User = get_user_model()
BASE = '/api/django/installations'


class FkCorpsTenantTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='ACHT52 A', slug='acht52-a')
        self.co_b = Company.objects.create(nom='ACHT52 B', slug='acht52-b')
        self.admin = User.objects.create_user(
            username='admin-a-acht52', password='x', company=self.co_a,
            role_legacy='admin')
        self.user_a = User.objects.create_user(
            username='user-a-acht52', password='x', company=self.co_a,
            role_legacy='technicien')
        self.user_b = User.objects.create_user(
            username='user-b-SECRET', password='x', company=self.co_b,
            role_legacy='technicien')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        # Données de B.
        emp_b = EmplacementStock.objects.create(company=self.co_b, nom='Dépôt B')
        self.bin_b = BinLocation.objects.create(
            company=self.co_b, emplacement=emp_b, code='B-01')
        self.chantier_b = Installation.objects.create(
            company=self.co_b, reference='CH-B-ACHT52')
        four_b = Fournisseur.objects.create(company=self.co_b, nom='Four B')
        self.ordre_b = OrdreSousTraitance.objects.create(
            company=self.co_b, reference='OST-B', sous_traitant=four_b,
            prestation='x', montant=Decimal('1'))
        # Données de A.
        emp_a = EmplacementStock.objects.create(company=self.co_a, nom='Dépôt A')
        self.bin_a = BinLocation.objects.create(
            company=self.co_a, emplacement=emp_a, code='A-01')
        self.chantier_a = Installation.objects.create(
            company=self.co_a, reference='CH-A-ACHT52')
        self.lot_a = LotPrelevement.objects.create(
            company=self.co_a, reference='LOT-A')
        pick = PickList.objects.create(
            company=self.co_a, reference='PL-A', installation=self.chantier_a)
        self.ligne_a = PickListLigne.objects.create(
            pick_list=pick, designation='x', quantite_demandee=1)
        self.kit_a = Kit.objects.create(company=self.co_a, nom='Kit A')
        # ACHT25 : un ordre d'assemblage exige une nomenclature exploitable
        # (composant catalogue à quantité > 0).
        produit_a = Produit.objects.create(
            company=self.co_a, nom='Composant A', prix_vente=Decimal('1'))
        KitComposant.objects.create(
            kit=self.kit_a, produit=produit_a, quantite=1)

    def _refus(self, r, champ):
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(champ, r.data)
        self.assertNotIn('SECRET', str(r.data))

    def test_gps_technicien(self):
        r = self.api.post(f'{BASE}/gps-consentements/', {
            'technicien': self.user_b.id, 'consent_ref': 'CONS-1'},
            format='json')
        self._refus(r, 'technicien')
        r = self.api.post(f'{BASE}/gps-consentements/', {
            'technicien': self.user_a.id, 'consent_ref': 'CONS-2'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_lot_operateur(self):
        r = self.api.patch(f'{BASE}/lots-prelevement/{self.lot_a.id}/',
                           {'operateur': self.user_b.id}, format='json')
        self._refus(r, 'operateur')
        self.lot_a.refresh_from_db()
        self.assertIsNone(self.lot_a.operateur_id)
        r = self.api.patch(f'{BASE}/lots-prelevement/{self.lot_a.id}/',
                           {'operateur': self.user_a.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_pick_ligne_bin(self):
        r = self.api.patch(f'{BASE}/pick-list-lignes/{self.ligne_a.id}/',
                           {'bin': self.bin_b.id}, format='json')
        self._refus(r, 'bin')
        self.ligne_a.refresh_from_db()
        self.assertIsNone(self.ligne_a.bin_id)
        r = self.api.patch(f'{BASE}/pick-list-lignes/{self.ligne_a.id}/',
                           {'bin': self.bin_a.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_ordre_assemblage_chantier_et_ordre_st(self):
        base = {'kit': self.kit_a.id, 'quantite': 1}
        r = self.api.post(f'{BASE}/ordres-assemblage/', {
            **base, 'chantier': self.chantier_b.id}, format='json')
        self._refus(r, 'chantier')
        r = self.api.post(f'{BASE}/ordres-assemblage/', {
            **base, 'ordre_sous_traitance': self.ordre_b.id}, format='json')
        self._refus(r, 'ordre_sous_traitance')
        r = self.api.post(f'{BASE}/ordres-assemblage/', {
            **base, 'chantier': self.chantier_a.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_programme_responsable(self):
        r = self.api.post(f'{BASE}/programmes/', {
            'nom': 'Programme', 'responsable': self.user_b.id},
            format='json')
        self._refus(r, 'responsable')
        r = self.api.post(f'{BASE}/programmes/', {
            'nom': 'Programme', 'responsable': self.user_a.id},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)


ID_ABSENT = 99999999

#: (sérialiseur, champ, cible) — ``cible`` nomme la ligne de ``_Societe``.
SITES = (
    (S.ApprobationBCFSerializer, 'bcf', 'bcf'),
    (S.BinAffectationSerializer, 'produit', 'produit'),
    (S.BinLocationSerializer, 'emplacement', 'emplacement'),
    (S.BudgetEngagementSerializer, 'bon_commande', 'bcf'),
    (S.BudgetEngagementSerializer, 'facture', 'facture'),
    (S.ColisLigneSerializer, 'produit', 'produit'),
    (S.CommandeCadreLigneSerializer, 'produit', 'produit'),
    (S.CommandeCadreSerializer, 'fournisseur', 'fournisseur'),
    (S.ComponentSerialSerializer, 'plaque_attachment', 'attachment'),
    (S.ComponentSerialSerializer, 'produit', 'produit'),
    (S.ComptageLigneSerializer, 'produit', 'produit'),
    (S.ConsommationLigneSerializer, 'produit', 'produit'),
    (S.ContratPrixFournisseurSerializer, 'fournisseur', 'fournisseur'),
    (S.ContratPrixLigneSerializer, 'produit', 'produit'),
    (S.ControleQualiteOrdreSerializer, 'photo', 'attachment'),
    (S.DemandeAchatLigneSerializer, 'produit', 'produit'),
    (S.DemandeAchatSerializer, 'fournisseur_suggere', 'fournisseur'),
    (S.DemandeTransfertSerializer, 'destination', 'emplacement'),
    (S.DemandeTransfertSerializer, 'produit', 'produit'),
    (S.DemandeTransfertSerializer, 'source', 'emplacement'),
    (S.DossierImportSerializer, 'bon_commande', 'bcf'),
    (S.DossierImportSerializer, 'fournisseur', 'fournisseur'),
    (S.EtapeAssemblageSerializer, 'piece_jointe', 'attachment'),
    (S.InstallationSerializer, 'client', 'client'),
    (S.InstallationSerializer, 'lead', 'lead'),
    (S.InterventionPreparationSerializer, 'kit', 'kit_outillage'),
    (S.InterventionSerializer, 'camionnette', 'emplacement'),
    (S.InterventionSerializer, 'ticket', 'ticket'),
    (S.KitComposantSerializer, 'produit', 'produit'),
    (S.KitSerializer, 'produit_compose', 'produit'),
    (S.LandedCostLigneSerializer, 'produit', 'produit'),
    (S.LivraisonLigneSerializer, 'produit', 'produit'),
    (S.LivraisonSerializer, 'depot', 'emplacement'),
    (S.MaterielConsigneSerializer, 'fournisseur', 'fournisseur'),
    (S.OrdreAssemblageLigneSerializer, 'produit', 'produit'),
    (S.OrdreAssemblageSerializer, 'devis', 'devis'),
    (S.OrdreAssemblageSerializer, 'emplacement_destination', 'emplacement'),
    (S.OrdreAssemblageSerializer, 'emplacement_source', 'emplacement'),
    (S.OrdreAssemblageSerializer, 'sous_traitant', 'fournisseur'),
    (S.OrdreDemontageLigneSerializer, 'produit', 'produit'),
    (S.OrdreDemontageSerializer, 'emplacement_destination', 'emplacement'),
    (S.OrdreDemontageSerializer, 'emplacement_source', 'emplacement'),
    (S.PhotoChecklistMetaSerializer, 'attachment', 'attachment'),
    (S.PickListLigneSerializer, 'produit', 'produit'),
    (S.PreuveLivraisonSerializer, 'photo', 'attachment'),
    (S.ProjetDevisSerializer, 'devis', 'devis'),
    (S.ProjetSerializer, 'client', 'client'),
    (S.ProjetTicketSerializer, 'ticket', 'ticket'),
    (S.PutAwaySerializer, 'emplacement', 'emplacement'),
    (S.PutAwaySerializer, 'produit', 'produit'),
    (S.ReceptionNonFactureeSerializer, 'bon_commande', 'bcf'),
    (S.ReceptionNonFactureeSerializer, 'reception', 'reception'),
    (S.RegleRangementSerializer, 'produit', 'produit'),
    (S.RegleReapproSerializer, 'emplacement_cible', 'emplacement'),
    (S.RegleReapproSerializer, 'emplacement_source', 'emplacement'),
    (S.RegleReapproSerializer, 'produit', 'produit'),
    (S.ReserveSerializer, 'photo', 'attachment'),
    (S.RetourLivraisonLigneSerializer, 'produit', 'produit'),
    (S.RetourMaterielLigneSerializer, 'produit', 'produit'),
    (S.SerieAssemblageSerializer, 'produit', 'produit'),
    (S.SerieEntrepotSerializer, 'emplacement', 'emplacement'),
    (S.SerieEntrepotSerializer, 'produit', 'produit'),
    (S.SessionComptageSerializer, 'emplacement', 'emplacement'),
    (S.ToolReturnSerializer, 'emplacement_retour', 'emplacement'),
)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Societe:
    """Une ligne de chaque modèle cible pour UNE société."""

    def __init__(self, company, suffixe):
        self.user = User.objects.create_user(
            username=f'enf17-inst-{suffixe}', password='x',
            role_legacy='admin', company=company)
        self.client = Client.objects.create(
            company=company, nom=f'Client {suffixe}')
        self.lead = Lead.objects.create(company=company, nom=f'Lead {suffixe}')
        self.chantier = Installation.objects.create(
            company=company, reference=f'ENF17-CH-{suffixe}',
            client=self.client)
        self.produit = Produit.objects.create(
            company=company, nom=f'PRODUIT-{suffixe}-SECRET',
            prix_vente=Decimal('10'), prix_achat=Decimal('5'))
        self.emplacement = EmplacementStock.objects.create(
            company=company, nom=f'Dépôt {suffixe}')
        self.fournisseur = Fournisseur.objects.create(
            company=company, nom=f'Fournisseur {suffixe}')
        self.bcf = BonCommandeFournisseur.objects.create(
            company=company, reference=f'ENF17-BCF-{suffixe}',
            fournisseur=self.fournisseur)
        self.facture = FactureFournisseur.objects.create(
            company=company, reference=f'ENF17-FF-{suffixe}',
            fournisseur=self.fournisseur, montant_ht=Decimal('100'),
            montant_tva=Decimal('20'), montant_ttc=Decimal('120'))
        self.reception = ReceptionFournisseur.objects.create(
            company=company, reference=f'ENF17-REC-{suffixe}',
            bon_commande=self.bcf)
        self.attachment = Attachment.objects.create(
            company=company,
            content_type=ContentType.objects.get_for_model(Installation),
            object_id=self.chantier.id, file_key=f'enf17/{suffixe}',
            filename='photo.png', mime='image/png')
        self.devis = Devis.objects.create(
            company=company, reference=f'ENF17-DEV-{suffixe}',
            client=self.client, lead=self.lead, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        self.ticket = Ticket.objects.create(
            company=company, reference=f'ENF17-SAV-{suffixe}',
            client=self.client)
        self.kit_outillage = KitOutillage.objects.create(
            company=company, nom=f'Kit outils {suffixe}',
            type_intervention='pose')


class FkInstallationsBorneesSocieteTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='enf17-inst-a', slug='enf17-inst-a')
        self.co_b = Company.objects.create(nom='enf17-inst-b', slug='enf17-inst-b')
        self.a = _Societe(self.co_a, 'A')
        self.b = _Societe(self.co_b, 'B')
        self.ctx = {'request': SimpleNamespace(user=self.a.user)}

    def test_chaque_fk_bornee_comme_un_id_absent(self):
        for cls, champ, cible in SITES:
            propre = getattr(self.a, cible)
            etranger = getattr(self.b, cible)
            with self.subTest(serializer=cls.__name__, champ=champ):
                ser = cls(data={champ: etranger.pk}, partial=True,
                          context=self.ctx)
                self.assertFalse(ser.is_valid())
                self.assertIn(champ, ser.errors)
                self.assertEqual(ser.errors[champ][0].code, 'does_not_exist')
                absent = cls(data={champ: ID_ABSENT}, partial=True,
                             context=self.ctx)
                self.assertFalse(absent.is_valid())
                self.assertEqual(
                    str(ser.errors[champ][0]).replace(
                        str(etranger.pk), '<ID>'),
                    str(absent.errors[champ][0]).replace(
                        str(ID_ABSENT), '<ID>'))
                champ_lie = cls(context=self.ctx).fields[champ]
                self.assertEqual(champ_lie.to_internal_value(propre.pk),
                                 propre)

    # ── bout en bout ─────────────────────────────────────────────────────

    def _refus(self, r, champ):
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(champ, r.data)
        self.assertNotIn('SECRET', str(r.data))

    def test_programme_client_etranger_400(self):
        api = _api(self.a.user)
        r = api.post(f'{BASE}/programmes/', {
            'nom': 'Programme', 'client': self.b.client.pk}, format='json')
        self._refus(r, 'client')
        r = api.post(f'{BASE}/programmes/', {
            'nom': 'Programme', 'client': self.a.client.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_ligne_pick_list_produit_etranger_400(self):
        pick = PickList.objects.create(
            company=self.co_a, reference='ENF17-PL-A',
            installation=self.a.chantier)
        ligne = PickListLigne.objects.create(
            pick_list=pick, designation='x', quantite_demandee=1)
        api = _api(self.a.user)
        url = f'{BASE}/pick-list-lignes/{ligne.id}/'
        r = api.patch(url, {'produit': self.b.produit.pk}, format='json')
        self._refus(r, 'produit')
        ligne.refresh_from_db()
        self.assertIsNone(ligne.produit_id)
        r = api.patch(url, {'produit': self.a.produit.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        ligne.refresh_from_db()
        self.assertEqual(ligne.produit_id, self.a.produit.pk)

    def test_chantier_client_etranger_400(self):
        api = _api(self.a.user)
        url = f'{BASE}/chantiers/{self.a.chantier.id}/'
        r = api.patch(url, {'client': self.b.client.pk}, format='json')
        self._refus(r, 'client')
        self.a.chantier.refresh_from_db()
        self.assertEqual(self.a.chantier.client_id, self.a.client.pk)
        r = api.patch(url, {'lead': self.a.lead.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
