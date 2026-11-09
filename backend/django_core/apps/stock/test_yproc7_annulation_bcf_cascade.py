"""YPROC7 — Annulation d'un BCF : cascade sur les réceptions ouvertes + garde
à la confirmation.

Couvre :
  * confirmer une réception dont le BCF est ANNULE est refusé (ValueError) ;
  * annuler un BCF annule en cascade ses réceptions BROUILLON (idempotent,
    jamais une réception déjà CONFIRME/ANNULE) et notifie le créateur ;
  * un BCF entièrement reçu reste inannulable (comportement inchangé) ;
  * un BCF partiellement reçu reste annulable, avec le détail des quantités
    déjà entrées en stock dans la réponse.

Run:
    python manage.py test apps.stock.test_yproc7_annulation_bcf_cascade -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Yproc7Base(TestCase):
    def setUp(self):
        self.company = _company('yproc7-co')
        self.user = _user(
            self.company, 'yproc7-user',
            permissions=['stock_modifier', 'stock_voir', 'prix_achat_voir',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YPROC7')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur YPROC7', sku='OND-YPROC7',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf(self, statut=BonCommandeFournisseur.Statut.ENVOYE, quantite=10):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC7-1',
            fournisseur=self.fournisseur, statut=statut,
            created_by=self.user)
        bc.ligne = bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('100'))
        return bc

    def _reception_brouillon(self, bc, quantite=5):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-YPROC7-1',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(
            ligne_commande=bc.ligne, produit=self.produit, quantite=quantite)
        return rec


class TestGardeConfirmationBcfAnnule(Yproc7Base):
    def test_confirmer_reception_bcf_annule_refuse(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ANNULE)
        rec = self._reception_brouillon(bc)
        with self.assertRaises(ValueError):
            confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.BROUILLON)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)

    def test_confirmer_reception_bcf_actif_toujours_permis(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        rec = self._reception_brouillon(bc)
        confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.CONFIRME)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)


class TestCascadeAnnulationBcf(Yproc7Base):
    def test_annuler_bcf_annule_receptions_brouillon(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        rec = self._reception_brouillon(bc)
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/',
            {'motif_annulation': 'Fournisseur en rupture'}, format='json')
        self.assertEqual(resp.status_code, 200)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ANNULE)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.ANNULE)
        self.assertIn('cascade', resp.data)
        self.assertEqual(resp.data['cascade']['receptions_annulees'], 1)

    def test_bcf_facture_ou_acompte_inannulable(self):
        """AAPV62 — BCF facturé (FF) et acompté : 409 nommant la facture et
        l'acompte, BCF resté « envoyé »."""
        from apps.stock.models import AcompteFournisseur, FactureFournisseur
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-AAPV62', fournisseur=self.fournisseur,
            bon_commande=bc, montant_ht=Decimal('20000'), montant_tva=Decimal('4000'),
            montant_ttc=Decimal('24000'))
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bc, montant=Decimal('7200'))
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/',
            {'motif_annulation': 'x'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertIn('FF-AAPV62', resp.data['detail'])
        self.assertIn("l'acompte de 7 200,00", resp.data['detail'])
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_annuler_bcf_ne_touche_pas_reception_deja_confirmee(self):
        bc = self._bcf(
            statut=BonCommandeFournisseur.Statut.ENVOYE, quantite=10)
        rec_confirmee = self._reception_brouillon(bc, quantite=3)
        confirm_reception_fournisseur(rec_confirmee, self.user)
        rec_brouillon = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-YPROC7-2',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec_brouillon.lignes.create(
            ligne_commande=bc.ligne, produit=self.produit, quantite=2)

        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/',
            {'motif_annulation': 'Fournisseur en rupture'}, format='json')
        self.assertEqual(resp.status_code, 200)
        rec_confirmee.refresh_from_db()
        rec_brouillon.refresh_from_db()
        self.assertEqual(
            rec_confirmee.statut, ReceptionFournisseur.Statut.CONFIRME)
        self.assertEqual(
            rec_brouillon.statut, ReceptionFournisseur.Statut.ANNULE)
        # Le détail des quantités déjà en stock est renvoyé (décision retour).
        self.assertEqual(
            resp.data['cascade']['quantites_deja_recues'][0]['quantite_recue'],
            3)

    def test_bcf_entierement_recu_reste_inannulable(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.RECU)
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/')
        self.assertEqual(resp.status_code, 409)

    def test_motif_nul_ou_non_texte_400_jamais_500(self):
        # ENF11 (nocturne 15/10) — un caractère nul faisait un ValueError SQL.
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        for motif in ('rupture\x00', 5, ['x']):
            resp = self.api.post(
                f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/',
                {'motif_annulation': motif}, format='json')
            self.assertEqual(resp.status_code, 400, (motif, resp.content))
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_annuler_deux_fois_idempotent_sur_receptions(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        self._reception_brouillon(bc)
        resp1 = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/',
            {'motif_annulation': 'Fournisseur en rupture'}, format='json')
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.data['cascade']['receptions_annulees'], 1)
        # Ré-annuler un BCF déjà annulé : aucune réception brouillon restante
        # à annuler (idempotence sur la cascade — le service ne recompte pas
        # une réception déjà ANNULE).
        resp2 = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/',
            {'motif_annulation': 'Confirmation ré-annulation'}, format='json')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data['cascade']['receptions_annulees'], 0)

    def _da_commandee_puis_annulee(self):
        """AAPV85 — budget 50 000 allumé, DA 20 000 approuvée → generer-bcf
        (BCF-A) → annuler (DA rouverte, réalisé 0)."""
        import datetime
        from apps.installations import services as inst_services
        from apps.installations.models import DemandeAchat, DemandeAchatLigne
        from apps.stock.models import AchatsParametres, BudgetDepartement
        from apps.stock.selectors import consommation_budget
        params = AchatsParametres.for_company(self.company)
        params.budget_departement_actif = True
        params.save(update_fields=['budget_departement_actif'])
        budget = BudgetDepartement.objects.create(
            company=self.company, periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=datetime.date.today().year, montant_alloue=Decimal('50000'))
        admin = User.objects.create_user(username='aapv85-admin', password='x', company=self.company,
                                         role_legacy='admin')
        api = APIClient()
        api.force_authenticate(admin)
        da = DemandeAchat.objects.create(company=self.company, reference='DA-AAPV85-1', objet='Câbles',
                                         created_by=admin, fournisseur_suggere=self.fournisseur)
        DemandeAchatLigne.objects.create(demande=da, designation='Lot câbles', quantite=1,
                                         prix_estime=Decimal('20000'))
        base = '/api/django/installations/demandes-achat/'
        self.assertEqual(api.post(f'{base}{da.pk}/soumettre/').status_code, 200)
        inst_services.decider_demande_achat(da, approuver=True, user=admin)
        self.assertEqual(api.post(f'{base}{da.pk}/generer-bcf/', {}, format='json').status_code, 200)
        da.refresh_from_db()
        bcf_a = da.bon_commande_id
        r = api.post(f'/api/django/stock/bons-commande-fournisseur/{bcf_a}/annuler/',
                     {'motif_annulation': 'erreur'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(consommation_budget(budget)['realise'], Decimal('0'))
        return api, da, bcf_a, (lambda: consommation_budget(budget)['realise'])

    def test_rouvrir_bcf_ne_d_une_da_recommande(self):
        """AAPV85 (D-AAPV-5 = recommander) — « Réouvrir » le BCF annulé né d'une
        DA re-commande la DA et re-consomme l'engagement ; generer-bcf alors 409,
        un seul BCF vivant pour la DA (C-AAPV-VER-007)."""
        from apps.installations.models import DemandeAchat
        api, da, bcf_a, realise = self._da_commandee_puis_annulee()
        r = api.post(f'/api/django/stock/bons-commande-fournisseur/{bcf_a}/rouvrir/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        da.refresh_from_db()
        self.assertEqual((da.statut, da.bon_commande_id, da.bcf_annule_id),
                         (DemandeAchat.Statut.COMMANDEE, bcf_a, None))
        self.assertEqual(realise(), Decimal('20000'))
        rb = api.post(f'/api/django/installations/demandes-achat/{da.pk}/generer-bcf/', {}, format='json')
        self.assertGreaterEqual(rb.status_code, 400)
        vivants = BonCommandeFournisseur.objects.filter(company=self.company).exclude(
            statut=BonCommandeFournisseur.Statut.ANNULE)
        self.assertEqual(list(vivants.values_list('id', flat=True)), [bcf_a])

    def test_rouvrir_bcf_dont_la_da_a_un_autre_bcf_refuse(self):
        """AAPV85 — la DA rouverte a déjà généré BCF-B : « Réouvrir » A rend 409
        nommant la DA et BCF-B ; A reste annulé."""
        api, da, bcf_a, _ = self._da_commandee_puis_annulee()
        self.assertEqual(api.post(f'/api/django/installations/demandes-achat/{da.pk}/generer-bcf/', {},
                                  format='json').status_code, 200)
        da.refresh_from_db()
        ref_b = BonCommandeFournisseur.objects.get(pk=da.bon_commande_id).reference
        r = api.post(f'/api/django/stock/bons-commande-fournisseur/{bcf_a}/rouvrir/', {}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('DA-AAPV85-1', str(r.data))
        self.assertIn(ref_b, str(r.data))
        self.assertEqual(BonCommandeFournisseur.objects.get(pk=bcf_a).statut,
                         BonCommandeFournisseur.Statut.ANNULE)

    def test_rouvrir_bcf_annule_sans_da_inchange(self):
        """AAPV85 — témoin : un BCF annulé sans DA se réouvre (200, brouillon)."""
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ANNULE)
        r = self.api.post(f'/api/django/stock/bons-commande-fournisseur/{bc.id}/rouvrir/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.BROUILLON)
