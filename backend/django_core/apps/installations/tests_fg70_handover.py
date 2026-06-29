"""
FG70 — Remise de garantie automatique à la réception.

Au passage à « Réceptionné » (ou « Mise en service », qui se rabat dessus), le
chantier balaie sa nomenclature gelée (`Installation.bom`) vers le parc SAV : un
`sav.Equipement` (sans n° de série) par ligne de BoM ayant un produit catalogue.
IDEMPOTENT : un re-passage ne duplique rien. L'écriture passe par
`apps.sav.services.sweep_bom_to_parc` (jamais d'import direct des modèles SAV).

Run :
    python manage.py test apps.installations.tests_fg70_handover -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.installations.services import create_installation_from_devis
from apps.sav.models import Equipement

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg70-co-{n}', defaults={'nom': nom or f'FG70 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, garantie_mois=None, garantie_production_mois=None):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-{company.id}-{n}',
        prix_vente=Decimal('100'), quantite_stock=50,
        garantie_mois=garantie_mois,
        garantie_production_mois=garantie_production_mois)


def make_chantier_with_bom(company, user, lines):
    """lines = [(produit, quantite), ...] → devis accepté + chantier (BoM gelé)."""
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'fg70-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-FG70-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestFG70WarrantyHandover(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='fg70_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(
            self.company, 'Panneau 550W', garantie_mois=120,
            garantie_production_mois=300)
        self.onduleur = make_produit(
            self.company, 'Onduleur 5kW', garantie_mois=60)

    def _receptionner(self, inst):
        return self.api.patch(
            f'/api/django/installations/chantiers/{inst.id}/',
            {'statut': Installation.Statut.RECEPTIONNE}, format='json')

    def test_reception_sweeps_bom_into_parc(self):
        """Au passage à « Réceptionné », un équipement par ligne de BoM est créé."""
        inst = make_chantier_with_bom(
            self.company, self.user,
            [(self.panneau, 8), (self.onduleur, 1)])
        self.assertEqual(inst.equipements.count(), 0)
        r = self._receptionner(inst)
        self.assertEqual(r.status_code, 200)
        equips = list(inst.equipements.all())
        # Un équipement par produit (pas un par unité), sans n° de série.
        self.assertEqual(len(equips), 2)
        self.assertTrue(all(e.numero_serie in (None, '') for e in equips))
        produit_ids = {e.produit_id for e in equips}
        self.assertEqual(produit_ids, {self.panneau.id, self.onduleur.id})

    def test_warranty_dates_computed_from_product(self):
        """date_pose = date_reception ; les fins de garantie sont calculées."""
        inst = make_chantier_with_bom(
            self.company, self.user, [(self.panneau, 4)])
        self._receptionner(inst)
        inst.refresh_from_db()
        eq = inst.equipements.get(produit=self.panneau)
        self.assertIsNotNone(inst.date_reception)
        self.assertEqual(eq.date_pose, inst.date_reception)
        # 120 mois (10 ans) matériel + 300 mois production → dates posées.
        self.assertIsNotNone(eq.date_fin_garantie)
        self.assertIsNotNone(eq.date_fin_garantie_production)
        self.assertEqual(eq.date_fin_garantie.year, inst.date_reception.year + 10)

    def test_sweep_is_idempotent(self):
        """Re-passer à « Réceptionné » ne duplique aucun équipement."""
        inst = make_chantier_with_bom(
            self.company, self.user, [(self.panneau, 8), (self.onduleur, 1)])
        self._receptionner(inst)
        self.assertEqual(inst.equipements.count(), 2)
        # Repasser à « Installé » puis re-réceptionner.
        self.api.patch(
            f'/api/django/installations/chantiers/{inst.id}/',
            {'statut': Installation.Statut.INSTALLE}, format='json')
        self._receptionner(inst)
        self.assertEqual(inst.equipements.count(), 2)

    def test_existing_serial_equipement_not_duplicated(self):
        """Un équipement déjà saisi (avec série) pour ce produit n'est pas doublé."""
        inst = make_chantier_with_bom(
            self.company, self.user, [(self.panneau, 8)])
        # Saisie manuelle préalable d'un équipement avec n° de série.
        Equipement.objects.create(
            company=self.company, produit=self.panneau, installation=inst,
            numero_serie='SN-EXISTANT', date_pose=None)
        self._receptionner(inst)
        equips = list(inst.equipements.filter(produit=self.panneau))
        self.assertEqual(len(equips), 1)
        self.assertEqual(equips[0].numero_serie, 'SN-EXISTANT')

    def test_empty_bom_is_robust(self):
        """BoM vide → aucun équipement, aucun plantage."""
        inst = make_chantier_with_bom(self.company, self.user, [])
        r = self._receptionner(inst)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(inst.equipements.count(), 0)

    def test_mise_en_service_also_sweeps(self):
        """« Mise en service » (rabat sur « Réceptionné ») balaie aussi le BoM."""
        inst = make_chantier_with_bom(
            self.company, self.user, [(self.panneau, 4)])
        r = self.api.post(
            f'/api/django/installations/chantiers/{inst.id}/mise-en-service/',
            {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(inst.equipements.count(), 1)

    def test_handover_chatter_note_written(self):
        """Une note de remise de garantie est ajoutée au chatter."""
        inst = make_chantier_with_bom(
            self.company, self.user, [(self.panneau, 4)])
        self._receptionner(inst)
        notes = [a.body for a in inst.activites.all() if a.body]
        self.assertTrue(any('Remise de garantie' in n for n in notes))

    def test_remise_garantie_endpoint(self):
        """L'endpoint remise-garantie renvoie la liste des équipements couverts."""
        inst = make_chantier_with_bom(
            self.company, self.user,
            [(self.panneau, 8), (self.onduleur, 1)])
        self._receptionner(inst)
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/remise-garantie/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nb_equipements'], 2)
        noms = {it['produit_nom'] for it in r.data['equipements']}
        self.assertEqual(noms, {'Panneau 550W', 'Onduleur 5kW'})
        # Aucun prix d'achat exposé.
        for it in r.data['equipements']:
            self.assertNotIn('prix_achat', it)

    def test_company_scoped(self):
        """Le balayage n'affecte que la société du chantier."""
        other = make_company()
        inst = make_chantier_with_bom(
            self.company, self.user, [(self.panneau, 4)])
        self._receptionner(inst)
        self.assertFalse(
            Equipement.objects.filter(company=other).exists())
