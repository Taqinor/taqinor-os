"""ENF17 — installations : toute FK cross-app inscriptible est bornée société.

Avant ENF17, 64 FK des sérialiseurs installations (produit, emplacement,
fournisseur, BCF / facture / réception fournisseur, pièce jointe, client,
lead, devis, ticket SAV, kit d'outillage — ``scripts/fk_scoping_allow.txt``)
résolvaient l'id d'une ligne d'une AUTRE société. Attendu désormais, pour
chacune : l'id d'ailleurs reçoit EXACTEMENT la réponse d'un id absent (400
« objet inexistant », aucun oracle d'existence) et l'id de sa propre société
reste accepté.

Les sérialiseurs sont éprouvés directement (requête en contexte, ``partial``
pour ne fournir que le champ visé) ; trois chemins HTTP réels (programme,
ligne de pick-list, chantier) confirment le 400 de bout en bout.

Run:
    python manage.py test apps.installations.tests_enf17_fk_societe -v 2
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.achats.models import (
    BonCommandeFournisseur, FactureFournisseur, ReceptionFournisseur,
)
from apps.crm.models import Client, Lead
from apps.installations import serializers as S
from apps.installations.models import Installation, PickList, PickListLigne
from apps.outillage.models import KitOutillage
from apps.records.models import Attachment
from apps.sav.models import Ticket
from apps.stock.models import EmplacementStock, Fournisseur, Produit
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

ID_ABSENT = 99999999
BASE = '/api/django/installations'

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
