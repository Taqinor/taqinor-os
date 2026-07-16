"""SCA47 — prix_par_kwc dérivé et gelé sur le Devis (leçon ServiceTitan).

Vérifie :
  * dérivation correcte (Total TTC ÷ kWc) sur un devis résidentiel ET un devis
    industriel, dès qu'un kWc (etude_params) et des lignes existent ;
  * NULL pour le pompage (etude_params sans puissance_kwc) — jamais forcé ;
  * WRITE-ONCE : une fois posé, il n'est PAS recalculé quand les lignes/totaux
    changent ensuite (gelé à la première dérivation) ;
  * lecture seule sur l'API interne (jamais accepté du corps de requête).

(L'absence dans tous les rendus PDF est prouvée dans test_quote_engine.py —
``test_prix_par_kwc_never_in_pdf_html``.)
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


class Sca47PrixParKwcTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='sca47-co', nom='SCA47 Co')
        self.user = User.objects.create_user(
            username='sca47_user', password='x',
            role_legacy='responsable', company=self.co)
        self.cli = Client.objects.create(
            company=self.co, nom='C', prenom='SCA47',
            email='sca47@example.invalid')
        self._sku = 0

    def _produit(self, prix):
        self._sku += 1
        return Produit.objects.create(
            company=self.co, nom=f'P{self._sku}', sku=f'SCA47-{self._sku}',
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=100)

    def _devis(self, ref, etude_params=None, mode='residentiel'):
        return Devis.objects.create(
            company=self.co, reference=ref, client=self.cli,
            statut='brouillon', taux_tva=Decimal('20.00'),
            created_by=self.user, mode_installation=mode,
            etude_params=etude_params)

    def _ligne(self, devis, prix, qte='1'):
        LigneDevis.objects.create(
            devis=devis, produit=self._produit(prix), designation='L',
            quantite=Decimal(qte), prix_unitaire=Decimal(prix),
            remise=Decimal('0'))

    def test_residentiel_derives_prix_par_kwc(self):
        """kWc=10, HT=100000 → TTC=120000 → prix_par_kwc = 12000.00."""
        d = self._devis('DEV-SCA47-RES', {'puissance_kwc': 10})
        self._ligne(d, prix='100000')  # 1 × 100000 HT
        d.save()  # recalcule maintenant que les lignes existent → gèle
        d.refresh_from_db()
        self.assertEqual(d.prix_par_kwc, Decimal('12000.00'))

    def test_industriel_derives_prix_par_kwc(self):
        """Industriel : kWc=50, HT=500000 → TTC=600000 → 12000.00 / kWc."""
        d = self._devis('DEV-SCA47-IND', {'puissance_kwc': 50},
                        mode='industriel')
        self._ligne(d, prix='500000')
        d.save()
        d.refresh_from_db()
        self.assertEqual(d.prix_par_kwc, Decimal('12000.00'))

    def test_pompage_stays_null(self):
        """Pompage : etude_params SANS puissance_kwc → prix_par_kwc reste null,
        jamais forcé."""
        d = self._devis(
            'DEV-SCA47-POMP',
            {'pompe_cv': '10', 'pompe_kw': 7.5, 'hmt_m': '60'},
            mode='agricole')
        self._ligne(d, prix='45000')
        d.save()
        d.refresh_from_db()
        self.assertIsNone(d.prix_par_kwc)

    def test_no_etude_params_stays_null(self):
        """Aucun etude_params → reste null."""
        d = self._devis('DEV-SCA47-NOEP', None)
        self._ligne(d, prix='45000')
        d.save()
        d.refresh_from_db()
        self.assertIsNone(d.prix_par_kwc)

    def test_write_once_not_recomputed_on_update(self):
        """Une fois gelé, prix_par_kwc n'est PAS recalculé quand le total
        change ensuite (write-once)."""
        d = self._devis('DEV-SCA47-WO', {'puissance_kwc': 10})
        self._ligne(d, prix='100000')
        d.save()
        d.refresh_from_db()
        self.assertEqual(d.prix_par_kwc, Decimal('12000.00'))
        # On DOUBLE le total : ajout d'une ligne + save → doit rester figé.
        self._ligne(d, prix='100000')
        d.save()
        d.refresh_from_db()
        self.assertEqual(d.prix_par_kwc, Decimal('12000.00'))

    def test_frozen_before_lines_stays_null_then_freezes(self):
        """À la création pure (aucune ligne), le total est 0 → reste null ;
        il se gèle au premier save où des lignes existent."""
        d = self._devis('DEV-SCA47-EMPTY', {'puissance_kwc': 8})
        # Pas encore de ligne → dérivation impossible → null.
        d.refresh_from_db()
        self.assertIsNone(d.prix_par_kwc)
        # Lignes ajoutées puis save → gèle. HT=80000 → TTC=96000 → 12000.00/kWc.
        self._ligne(d, prix='80000')
        d.save()
        d.refresh_from_db()
        self.assertEqual(d.prix_par_kwc, Decimal('12000.00'))

    def test_prix_par_kwc_read_only_in_serializer(self):
        """Le champ dérivé est read-only : jamais accepté du corps de requête."""
        from apps.ventes.serializers import DevisSerializer, DevisWriteSerializer
        self.assertIn('prix_par_kwc', DevisSerializer.Meta.read_only_fields)
        self.assertIn('prix_par_kwc',
                      DevisWriteSerializer.Meta.read_only_fields)
