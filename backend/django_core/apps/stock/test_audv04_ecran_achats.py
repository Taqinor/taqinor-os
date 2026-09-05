"""AUDV04 — Écran Achats : paliers, échéanciers, alertes fournisseur.

Ferme 5 capacités qui existaient déjà côté sélecteur/service mais restaient
inaccessibles hors tests (aucun ViewSet/URL/cron) :

  * DRAFT165-112 `echeances_facture_fournisseur` — enfin servi par l'action
    `echeancier` GET (au lieu d'une lecture manuelle dupliquée) ;
  * DRAFT165-113 `acomptes_fournisseur_ouverts` — nouvelle action `ouverts` ;
  * DRAFT165-114 `creer_profil_saisonnier` — nouveau ViewSet CRUD ;
  * DRAFT165-115/116 — 2 alertes planifiées (documents de conformité
    fournisseur expirants, BCF en retard côté ACHETEUR) jusqu'ici sans cron ;
  * DRAFT165-117 `prix_effectif_fournisseur` — nouvelle action `effectif`.

Run:
    python manage.py test apps.stock.test_audv04_ecran_achats -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.notifications.models import EventType, Notification
from apps.stock.models import (
    AcompteFournisseur, BonCommandeFournisseur, DocumentConformiteFournisseur,
    EcheanceFactureFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, PalierPrixFournisseur, PrixFournisseur,
    Produit, ProfilSaisonnier,
)
from apps.stock.tasks import (
    notifier_bcf_en_retard_buyer_task,
    notifier_documents_conformite_expirants_task,
)

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


class Audv04Base(TestCase):
    def setUp(self):
        self.company = _company('audv04-co')
        self.user = _user(
            self.company, 'audv04-user',
            permissions=['stock_modifier', 'stock_voir', 'prix_achat_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur AUDV04')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUDV04', sku='OND-AUDV04',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))


class TestEcheancierFactureFournisseur(Audv04Base):
    """DRAFT165-112 — l'action `echeancier` GET route par le sélecteur."""

    def setUp(self):
        super().setUp()
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AUDV04-1',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        EcheanceFactureFournisseur.objects.create(
            company=self.company, facture=self.facture,
            pourcentage=Decimal('30'), montant=Decimal('360'),
            date_echeance=timezone.now().date() + timedelta(days=10))

    def test_echeancier_renvoie_les_lignes_du_selecteur(self):
        url = f'/api/django/stock/factures-fournisseur/{self.facture.pk}/echeancier/'
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data), 1)
        ligne = rep.data[0]
        self.assertEqual(Decimal(str(ligne['montant'])), Decimal('360'))
        self.assertEqual(Decimal(str(ligne['pourcentage'])), Decimal('30'))
        self.assertIn('date_echeance', ligne)
        # Forme du sélecteur (jamais celle du serializer modèle brut) : pas de
        # `facture`/`date_creation` — la même invariance que
        # `echeances_facture_fournisseur` teste déjà côté fonction pure.
        self.assertNotIn('facture', ligne)
        self.assertNotIn('date_creation', ligne)

    def test_echeancier_vide_sans_tranche(self):
        autre = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AUDV04-2',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('500'), montant_tva=Decimal('100'),
            montant_ttc=Decimal('600'))
        url = f'/api/django/stock/factures-fournisseur/{autre.pk}/echeancier/'
        rep = self.api.get(url)
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data, [])


class TestAcomptesOuverts(Audv04Base):
    """DRAFT165-113 — nouvelle action `ouverts`."""

    def test_acompte_partiellement_consomme_apparait(self):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUDV04-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf,
            montant=Decimal('1000'), montant_consomme=Decimal('400'),
            date_versement=timezone.now().date())
        rep = self.api.get('/api/django/stock/acomptes-fournisseur/ouverts/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(len(rep.data), 1)
        self.assertEqual(
            Decimal(str(rep.data[0]['montant_non_consomme'])), Decimal('600'))

    def test_acompte_entierement_consomme_absent(self):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUDV04-2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf,
            montant=Decimal('1000'), montant_consomme=Decimal('1000'),
            date_versement=timezone.now().date())
        rep = self.api.get('/api/django/stock/acomptes-fournisseur/ouverts/')
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(rep.data, [])


class TestPrixEffectifAction(Audv04Base):
    """DRAFT165-117 — nouvelle action `effectif`."""

    def setUp(self):
        super().setUp()
        self.pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'))
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=self.pf, qte_min=10, prix=Decimal('900'))

    def test_prix_effectif_applique_le_palier(self):
        rep = self.api.get(
            '/api/django/stock/prix-fournisseurs/effectif/',
            {'produit': self.produit.pk, 'fournisseur': self.fournisseur.pk,
             'quantite': 20})
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(Decimal(str(rep.data['prix_effectif'])), Decimal('900'))

    def test_prix_effectif_sans_palier_prend_le_prix_de_base(self):
        rep = self.api.get(
            '/api/django/stock/prix-fournisseurs/effectif/',
            {'produit': self.produit.pk, 'fournisseur': self.fournisseur.pk,
             'quantite': 1})
        self.assertEqual(rep.status_code, 200)
        self.assertEqual(Decimal(str(rep.data['prix_effectif'])), Decimal('1000'))

    def test_prix_effectif_refuse_sans_prix_achat_voir(self):
        sans_droit = _user(
            self.company, 'audv04-sans-droit', permissions=['stock_voir'])
        rep = _api(sans_droit).get(
            '/api/django/stock/prix-fournisseurs/effectif/',
            {'produit': self.produit.pk, 'fournisseur': self.fournisseur.pk})
        self.assertEqual(rep.status_code, 403)

    def test_prix_effectif_parametres_manquants(self):
        rep = self.api.get('/api/django/stock/prix-fournisseurs/effectif/')
        self.assertEqual(rep.status_code, 400)


class TestProfilSaisonnierViewSet(Audv04Base):
    """DRAFT165-114 — nouveau ViewSet CRUD, création via le service (garde
    anti-chevauchement héritée, jamais dupliquée)."""

    def test_creation_produit(self):
        rep = self.api.post('/api/django/stock/profils-saisonniers/', {
            'produit': self.produit.pk, 'mois_debut': 5, 'mois_fin': 8,
            'seuil_min': 10, 'quantite_cible': 40, 'nom': 'Saison pompage',
        })
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertEqual(ProfilSaisonnier.objects.count(), 1)
        profil = ProfilSaisonnier.objects.get()
        self.assertEqual(profil.company_id, self.company.id)

    def test_produit_et_categorie_a_la_fois_refuse(self):
        from apps.stock.models import Categorie
        cat = Categorie.objects.create(company=self.company, nom='Onduleurs')
        rep = self.api.post('/api/django/stock/profils-saisonniers/', {
            'produit': self.produit.pk, 'categorie': cat.pk,
            'mois_debut': 5, 'mois_fin': 8,
        })
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(ProfilSaisonnier.objects.count(), 0)

    def test_chevauchement_refuse(self):
        ProfilSaisonnier.objects.create(
            company=self.company, produit=self.produit,
            mois_debut=5, mois_fin=8, actif=True)
        rep = self.api.post('/api/django/stock/profils-saisonniers/', {
            'produit': self.produit.pk, 'mois_debut': 6, 'mois_fin': 9,
        })
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(ProfilSaisonnier.objects.count(), 1)

    def test_lecture_liste(self):
        ProfilSaisonnier.objects.create(
            company=self.company, produit=self.produit,
            mois_debut=5, mois_fin=8, actif=True)
        rep = self.api.get('/api/django/stock/profils-saisonniers/')
        self.assertEqual(rep.status_code, 200)
        lignes = rep.data['results'] if isinstance(rep.data, dict) else rep.data
        self.assertEqual(len(lignes), 1)


class TestAlerteDocumentsConformiteExpirants(Audv04Base):
    """DRAFT165-115 — la tâche battait dans le vide (aucun cron)."""

    def test_notifie_et_idempotent_meme_jour(self):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            obligatoire=True,
            date_expiration=timezone.now().date() + timedelta(days=5))
        result = notifier_documents_conformite_expirants_task()
        self.assertEqual(result[self.company.id], 1)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.SUPPLIER_DOC_EXPIRING).count(),
            1)
        # Idempotent : un second passage le même jour ne renotifie pas.
        result2 = notifier_documents_conformite_expirants_task()
        self.assertEqual(result2[self.company.id], 0)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company,
                event_type=EventType.SUPPLIER_DOC_EXPIRING).count(),
            1)

    def test_aucun_document_expirant_aucune_notification(self):
        result = notifier_documents_conformite_expirants_task()
        self.assertEqual(result[self.company.id], 0)
        self.assertFalse(Notification.objects.filter(
            company=self.company,
            event_type=EventType.SUPPLIER_DOC_EXPIRING).exists())


class TestAlerteBcfEnRetardBuyer(Audv04Base):
    """DRAFT165-116 — l'alerte ACHETEUR (BCF_LATE) n'avait aucun appelant."""

    def _bcf_en_retard(self):
        hier = timezone.now().date() - timedelta(days=5)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUDV04-LATE',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=hier)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=0)
        return bcf

    def test_notifie_et_idempotent_meme_jour(self):
        self._bcf_en_retard()
        result = notifier_bcf_en_retard_buyer_task()
        self.assertEqual(result[self.company.id], 1)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, event_type=EventType.BCF_LATE).count(),
            1)
        result2 = notifier_bcf_en_retard_buyer_task()
        self.assertEqual(result2[self.company.id], 0)
        self.assertEqual(
            Notification.objects.filter(
                company=self.company, event_type=EventType.BCF_LATE).count(),
            1)

    def test_bcf_dans_les_temps_non_notifie(self):
        demain = timezone.now().date() + timedelta(days=5)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUDV04-OK',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=demain)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'), quantite_recue=0)
        result = notifier_bcf_en_retard_buyer_task()
        self.assertEqual(result[self.company.id], 0)
