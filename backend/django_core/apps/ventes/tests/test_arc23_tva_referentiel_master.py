"""ARC23 — Référentiel de taux de TVA (master parametres.TauxTVA).

Vérifie :
  - le master seedé porte les taux marocains usuels (20/14/10/7/0) + un défaut ;
  - le défaut du référentiel est BRANCHÉ sur la création de ligne de devis
    (ligne standard sans taux ni produit taxé → taux STANDARD du référentiel) ;
  - sans référentiel actif, le comportement historique est PRÉSERVÉ (repli
    CompanyProfile.tva_standard / 20) ;
  - Produit.tva reste AUTORITAIRE (DC7) ;
  - IMMUTABILITÉ LÉGALE (règle #4) : un taux déjà figé sur un document existant
    n'est JAMAIS réécrit quand le référentiel change.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_arc23_tva_referentiel_master -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.parametres.models import TauxTVA
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.serializers import LigneDevisSerializer
from apps.ventes.tests.test_quote_engine import make_company, make_user


class TestArc23TauxTVAMaster(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='D', email='c@d.ma')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ARC23-1',
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20.00'), created_by=self.user)

    def _produit(self, nom, tva=None):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=f'sku-{nom[:8]}',
            prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
            quantite_stock=10, tva=tva)

    def _create_line(self, designation, produit):
        s = LigneDevisSerializer()
        return s.create({
            'devis': self.devis, 'produit': produit,
            'designation': designation, 'quantite': Decimal('1'),
            'prix_unitaire': Decimal('1000'), 'remise': Decimal('0'),
        })

    # ── Master + seed ────────────────────────────────────────────────────────
    def test_seed_creates_moroccan_rates(self):
        crees = TauxTVA.seed_defaults(self.company)
        self.assertEqual(crees, 5)
        taux = set(
            TauxTVA.objects.filter(company=self.company)
            .values_list('taux', flat=True))
        self.assertEqual(
            taux,
            {Decimal('20'), Decimal('14'), Decimal('10'), Decimal('7'),
             Decimal('0')})

    def test_seed_is_idempotent(self):
        self.assertEqual(TauxTVA.seed_defaults(self.company), 5)
        # Rejoué : aucun doublon, aucune nouvelle ligne.
        self.assertEqual(TauxTVA.seed_defaults(self.company), 0)
        self.assertEqual(
            TauxTVA.objects.filter(company=self.company).count(), 5)

    def test_default_taux_is_standard_20(self):
        TauxTVA.seed_defaults(self.company)
        self.assertEqual(TauxTVA.default_taux(self.company), Decimal('20'))
        # Un seul défaut par société.
        self.assertEqual(
            TauxTVA.objects.filter(company=self.company, defaut=True).count(),
            1)

    # ── Défauts branchés sur la création ─────────────────────────────────────
    def _set_profile_tva_standard(self, value):
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=self.company)
        prof.tva_standard = Decimal(value)
        prof.save(update_fields=['tva_standard'])

    def test_visible_knob_dominates_seeded_referentiel(self):
        # ARC23 (corrigé) — le knob VISIBLE en Paramètres
        # (CompanyProfile.tva_standard) prime sur le référentiel seedé (sans UI).
        # Le tenant met « TVA standard » à 14 % ; le référentiel reste à 20 %
        # (valeur seedée par défaut à l'inscription). Une ligne de repli DOIT
        # prendre 14 % — le référentiel ne réprime plus l'édition de l'utilisateur.
        TauxTVA.seed_defaults(self.company)  # référentiel standard = 20 %
        self._set_profile_tva_standard('14')
        produit = self._produit('Onduleur réseau', tva=None)
        ligne = self._create_line('Onduleur réseau', produit)
        self.assertEqual(ligne.taux_tva, Decimal('14'))

    def test_untouched_knob_keeps_default_20(self):
        # Tenant qui n'a jamais touché le knob (défaut 20) + référentiel seedé à
        # 20 → la ligne de repli garde 20 % (valeur d'aujourd'hui inchangée).
        TauxTVA.seed_defaults(self.company)
        produit = self._produit('Onduleur réseau', tva=None)
        ligne = self._create_line('Onduleur réseau', produit)
        self.assertEqual(ligne.taux_tva, Decimal('20'))

    def test_no_referentiel_preserves_historical_behavior(self):
        # Aucun référentiel actif (setUp ne seede pas) → repli 20 % historique.
        self.assertIsNone(TauxTVA.default_taux(self.company))
        produit = self._produit('Onduleur réseau', tva=None)
        ligne = self._create_line('Onduleur réseau', produit)
        self.assertEqual(ligne.taux_tva, Decimal('20'))

    def test_produit_tva_stays_authoritative(self):
        # DC7 — même avec un référentiel actif, Produit.tva prime sur le défaut.
        TauxTVA.seed_defaults(self.company)
        TauxTVA.objects.filter(
            company=self.company, code='standard').update(taux=Decimal('18'))
        produit = self._produit('Onduleur réseau', tva=Decimal('14'))
        ligne = self._create_line('Onduleur réseau', produit)
        self.assertEqual(ligne.taux_tva, Decimal('14'))

    def test_inactive_default_falls_back_to_historical(self):
        # Défaut désactivé → default_taux None → repli historique 20 %.
        TauxTVA.seed_defaults(self.company)
        TauxTVA.objects.filter(
            company=self.company, code='standard').update(actif=False)
        self.assertIsNone(TauxTVA.default_taux(self.company))
        produit = self._produit('Onduleur réseau', tva=None)
        ligne = self._create_line('Onduleur réseau', produit)
        self.assertEqual(ligne.taux_tva, Decimal('20'))

    # ── Immutabilité légale (règle #4) ───────────────────────────────────────
    def test_existing_document_line_never_rewritten(self):
        # Une ligne déjà FIGÉE à 20 % ne change JAMAIS quand le référentiel passe
        # son défaut à 18 % : le référentiel n'alimente QUE les défauts à la
        # création, il ne réécrit jamais une valeur émise.
        produit = self._produit('Onduleur figé', tva=None)
        ligne = self._create_line('Onduleur figé', produit)
        self.assertEqual(ligne.taux_tva, Decimal('20'))

        TauxTVA.seed_defaults(self.company)
        TauxTVA.objects.filter(
            company=self.company, code='standard').update(taux=Decimal('18'))

        ligne.refresh_from_db()
        self.assertEqual(ligne.taux_tva, Decimal('20'))
        # Le document lui-même conserve son taux figé.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.taux_tva, Decimal('20.00'))

    def test_referential_is_company_scoped(self):
        from authentication.models import Company
        other = Company.objects.create(slug='arc23-other', nom='Autre')
        TauxTVA.seed_defaults(self.company)
        # L'autre société n'a AUCUN taux tant qu'elle n'est pas seedée.
        self.assertIsNone(TauxTVA.default_taux(other))
        self.assertEqual(
            TauxTVA.objects.filter(company=other).count(), 0)
