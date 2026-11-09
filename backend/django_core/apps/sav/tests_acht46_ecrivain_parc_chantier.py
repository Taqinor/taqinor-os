"""ACHT46 — écrivain unique du parc d'un chantier : le résultat ne dépend plus
de l'ordre réception / relevé de série ; doublon sans exception ; recalage des
garanties quand la date de réception est corrigée.

Run :
    python manage.py test apps.sav.tests_acht46_ecrivain_parc_chantier -v2
"""
from datetime import date

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Equipement
from apps.sav.services import (
    assurer_equipement_chantier, recaler_garanties_chantier,
    sweep_bom_to_parc,
)
from apps.stock.models import Produit

RECEPTION = date(2026, 9, 1)
POSE_REELLE = date(2026, 8, 25)  # ACHT125 — pose réelle ≠ réception


class EcrivainParcChantierTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='acht46-co', defaults={'nom': 'ACHT46 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ACHT46')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-46', prix_achat=0,
            prix_vente=10, garantie_mois=120)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-46', prix_achat=0,
            prix_vente=10, garantie_mois=60)

    def _chantier(self, ref, date_pose_reelle=None):
        return Installation.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            date_pose_reelle=date_pose_reelle,
            bom=[{'produit_id': self.panneau.id, 'designation': 'Panneau',
                  'quantite': 12},
                 {'produit_id': self.onduleur.id, 'designation': 'Onduleur',
                  'quantite': 1}])

    def _balayage(self, chantier):
        par_id = {self.panneau.id: self.panneau,
                  self.onduleur.id: self.onduleur}
        return sweep_bom_to_parc(
            installation=chantier, company=self.company,
            date_pose=RECEPTION, created_by=None,
            resolve_produit=par_id.get)

    def _assurer(self, chantier, produit, serie, qte, date_pose=RECEPTION):
        return assurer_equipement_chantier(
            company=self.company, installation=chantier, produit=produit,
            numero_serie=serie, quantite_ligne=qte, date_pose=date_pose,
            created_by=None)

    def _parc(self, chantier, produit, sauf=()):
        return sorted(
            (e.numero_serie or '', e.date_pose, e.date_fin_garantie) for e in
            Equipement.objects.filter(installation=chantier, produit=produit)
            .exclude(numero_serie__in=sauf))

    def test_ordre_indifferent(self):
        # ACHT125 — chantiers à pose réelle ≠ réception ; l'ordre B relève la
        # série AVANT la réception, datée de la pose réelle (comme le terrain).
        a = self._chantier('CHT-46-A', POSE_REELLE)
        self._balayage(a)
        self._assurer(a, self.panneau, 'SN-A1', 12)
        b = self._chantier('CHT-46-B', POSE_REELLE)
        self._assurer(b, self.panneau, 'SN-B1', 12, date_pose=POSE_REELLE)
        main = Equipement.objects.create(
            company=self.company, produit=self.panneau, installation=b,
            numero_serie='SN-B-MAIN', date_pose=date(2026, 8, 1))
        main.recompute_garanties()
        main.save(update_fields=['date_fin_garantie'])
        self._balayage(b)
        parc_a = self._parc(a, self.panneau)
        parc_b = self._parc(b, self.panneau, sauf=('SN-B-MAIN',))
        attendu = [(False, RECEPTION, date(2036, 9, 1)),
                   (True, RECEPTION, date(2036, 9, 1))]
        self.assertEqual([(s != '', d, f) for s, d, f in parc_a], attendu)
        self.assertEqual([(s != '', d, f) for s, d, f in parc_b], attendu)
        main.refresh_from_db()
        self.assertEqual((main.date_pose, main.date_fin_garantie),
                         (date(2026, 8, 1), date(2036, 8, 1)))
        # Second balayage : idempotent.
        avant = self._parc(b, self.panneau)
        self._balayage(b)
        self.assertEqual(self._parc(b, self.panneau), avant)

    def test_placeholder_rempli_quantite_1(self):
        c = self._chantier('CHT-46-O')
        self._balayage(c)
        statut, eq = self._assurer(c, self.onduleur, 'SN-O1', 1)
        self.assertEqual(statut, 'rempli')
        self.assertEqual(
            list(Equipement.objects.filter(
                installation=c, produit=self.onduleur
            ).values_list('numero_serie', flat=True)), ['SN-O1'])

    def test_doublon_sans_exception(self):
        c = self._chantier('CHT-46-D')
        self._balayage(c)
        self._assurer(c, self.panneau, 'SN-A1', 12)
        statut, _ = self._assurer(c, self.panneau, 'SN-A1', 12)
        self.assertEqual(statut, 'doublon')
        self.assertEqual(Equipement.objects.filter(
            company=self.company, numero_serie='SN-A1').count(), 1)

    def test_recalage_garanties(self):
        c = self._chantier('CHT-46-R')
        self._balayage(c)
        main = Equipement.objects.create(
            company=self.company, produit=self.onduleur, installation=c,
            numero_serie='SN-MAIN', date_pose=date(2026, 5, 5))
        nouvelle = date(2026, 8, 15)
        n = recaler_garanties_chantier(
            company=self.company, installation=c, ancienne_date=RECEPTION,
            nouvelle_date=nouvelle)
        self.assertEqual(n, 2)
        self.assertTrue(all(
            e.date_pose == nouvelle for e in Equipement.objects.filter(
                installation=c).exclude(pk=main.pk)))
        main.refresh_from_db()
        self.assertEqual(main.date_pose, date(2026, 5, 5))
        eq = Equipement.objects.filter(
            installation=c, produit=self.panneau).first()
        self.assertEqual(eq.date_fin_garantie.year, 2036)

    def test_ajout_manuel_remplit_le_placeholder(self):
        """ACSV59 (C-ACSV-069) — l'ajout manuel (POST sav/equipements/) d'une
        série au chantier réceptionné passe par l'écrivain unique : le
        placeholder sans série est rempli, daté de la réception ; doublon 400 ;
        sans chantier (comptoir) : créé tel quel. ROUGE AVANT : 2 onduleurs."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        admin = get_user_model().objects.create_user(
            username='acsv59_admin', password='x', role_legacy='admin', company=self.company)
        api = APIClient()
        api.force_authenticate(admin)
        c = self._chantier('CHT-ACSV59')
        Installation.objects.filter(pk=c.pk).update(date_reception=RECEPTION)
        c.refresh_from_db()
        self._balayage(c)
        corps = {'installation': c.pk, 'produit': self.onduleur.pk,
                 'numero_serie': 'SN-9', 'date_pose': '2026-08-25'}
        r = api.post('/api/django/sav/equipements/', corps, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        parc = list(Equipement.objects.filter(installation=c, produit=self.onduleur)
                    .values_list('numero_serie', 'date_pose'))
        self.assertEqual(parc, [('SN-9', RECEPTION)])
        self.assertEqual(r.data['id'], Equipement.objects.get(numero_serie='SN-9').pk)
        r = api.post('/api/django/sav/equipements/', corps, format='json')
        self.assertEqual(r.status_code, 409, r.content)  # garde du sérialiseur (ENF11)
        self.assertIn('numero_serie', r.data)
        r = api.post('/api/django/sav/equipements/', {
            'produit': self.onduleur.pk, 'numero_serie': 'SN-COMPTOIR',
            'date_pose': '2026-08-25'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Equipement.objects.get(numero_serie='SN-COMPTOIR').date_pose, date(2026, 8, 25))
