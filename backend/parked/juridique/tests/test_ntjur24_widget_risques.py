"""NTJUR24 — données du widget « Risques juridiques » du tableau de bord.

Critère d'acceptation : « un utilisateur sans permission confidentiel voit un
total qui EXCLUT les dossiers confidentiels (pas de fuite par agrégat) ».
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.juridique.models import DelaiPrescription, DossierJuridique

from ._base import auth, make_admin, make_company, make_responsable

URL = '/api/django/juridique/dossiers/tableau-bord/'


class WidgetRisquesJuridiquesTests(TestCase):
    def setUp(self):
        self.company = make_company('jur-w24-co', 'Juridique W24')
        self.admin = make_admin(self.company, 'jur-w24-admin')
        self.responsable = make_responsable(self.company, 'jur-w24-resp')
        self.api = auth(self.admin)

    def _dossier(self, reference, **kwargs):
        defauts = {
            'titre': f'D {reference}', 'date_ouverture': date(2026, 3, 1),
            'montant_en_jeu': Decimal('0'),
        }
        defauts.update(kwargs)
        return DossierJuridique.objects.create(
            company=self.company, reference=reference, **defauts)

    def test_le_widget_a_les_quatre_indicateurs(self):
        self._dossier('JUR-2026-0001', montant_en_jeu=Decimal('120000'),
                      montant_risque_estime=Decimal('40000'))
        provisionne = self._dossier(
            'JUR-2026-0002', montant_en_jeu=Decimal('80000'))
        provisionne.provision_comptable_id = 77
        provisionne.save(update_fields=['provision_comptable_id'])
        DelaiPrescription.objects.create(
            company=self.company, dossier=provisionne,
            date_declenchement=timezone.localdate(), duree_jours=10,
            date_limite=timezone.localdate() + timedelta(days=10))

        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nombre_dossiers'], 2)
        self.assertEqual(resp.data['montant_en_jeu_total'], '200000.00')
        self.assertEqual(resp.data['provisions_comptabilisees'], 1)
        self.assertEqual(resp.data['provisions_proposees'], 1)
        self.assertEqual(resp.data['echeances_prescription_30j'], 1)

    def test_le_montant_en_jeu_ignore_les_dossiers_clos(self):
        self._dossier('JUR-2026-0003', montant_en_jeu=Decimal('50000'))
        self._dossier('JUR-2026-0004', montant_en_jeu=Decimal('900000'),
                      statut=DossierJuridique.Statut.CLOS_PERDU)
        resp = self.api.get(URL)
        self.assertEqual(resp.data['montant_en_jeu_total'], '50000.00')

    def test_aucune_fuite_par_agregat_pour_un_role_non_autorise(self):
        self._dossier('JUR-2026-0005', montant_en_jeu=Decimal('10000'))
        secret = self._dossier(
            'JUR-2026-0006', montant_en_jeu=Decimal('750000'),
            confidentialite=(
                DossierJuridique.NiveauConfidentialite.CONFIDENTIEL))
        secret.provision_comptable_id = 99
        secret.save(update_fields=['provision_comptable_id'])
        DelaiPrescription.objects.create(
            company=self.company, dossier=secret,
            date_declenchement=timezone.localdate(), duree_jours=5,
            date_limite=timezone.localdate() + timedelta(days=5))

        vu = auth(self.responsable).get(URL)
        self.assertEqual(vu.data['nombre_dossiers'], 1)
        self.assertEqual(vu.data['montant_en_jeu_total'], '10000.00')
        self.assertEqual(vu.data['provisions_comptabilisees'], 0)
        # Le délai du dossier confidentiel ne fuite pas non plus par ce
        # compteur.
        self.assertEqual(vu.data['echeances_prescription_30j'], 0)

        complet = self.api.get(URL)
        self.assertEqual(complet.data['nombre_dossiers'], 2)
        self.assertEqual(complet.data['montant_en_jeu_total'], '760000.00')
        self.assertEqual(complet.data['provisions_comptabilisees'], 1)
        self.assertEqual(complet.data['echeances_prescription_30j'], 1)

    def test_une_prescription_lointaine_n_est_pas_comptee(self):
        dossier = self._dossier('JUR-2026-0007')
        DelaiPrescription.objects.create(
            company=self.company, dossier=dossier,
            date_declenchement=timezone.localdate(), duree_jours=200,
            date_limite=timezone.localdate() + timedelta(days=200))
        resp = self.api.get(URL)
        self.assertEqual(resp.data['echeances_prescription_30j'], 0)
