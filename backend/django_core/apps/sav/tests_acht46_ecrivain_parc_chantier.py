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

    def _chantier(self, ref):
        return Installation.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
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

    def _assurer(self, chantier, produit, serie, qte):
        return assurer_equipement_chantier(
            company=self.company, installation=chantier, produit=produit,
            numero_serie=serie, quantite_ligne=qte, date_pose=RECEPTION,
            created_by=None)

    def _parc(self, chantier, produit):
        return sorted(
            (e.numero_serie or '', e.date_pose) for e in
            Equipement.objects.filter(installation=chantier, produit=produit))

    def test_ordre_indifferent(self):
        a = self._chantier('CHT-46-A')
        self._balayage(a)
        self._assurer(a, self.panneau, 'SN-A1', 12)
        b = self._chantier('CHT-46-B')
        self._assurer(b, self.panneau, 'SN-B1', 12)
        self._balayage(b)
        parc_a = self._parc(a, self.panneau)
        parc_b = self._parc(b, self.panneau)
        self.assertEqual(
            [(s != '', d) for s, d in parc_a],
            [(s != '', d) for s, d in parc_b])
        self.assertEqual(len(parc_a), 2)
        self.assertEqual({d for _, d in parc_a}, {RECEPTION})
        self.assertEqual({d for _, d in parc_b}, {RECEPTION})

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
