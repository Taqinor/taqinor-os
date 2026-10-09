"""AFAC52 (C-AFAC-045) — le journal des ventes et l'export comptable
ventilent une facture de tranche SANS lignes par ses taux RÉELS
(``facture_par_taux`` / ``ventilation_tva``) au lieu d'un panier au « taux
mélangé » : une tranche 10 %/20 % donne deux lignes et deux paniers de TVA.

Rejoue la sonde FDOC-6 (journal et `_compta_rows` : une ligne « 16.62 % »
par tranche ; Résumé TVA : seul panier « 16.62 % »). Tranches réelles
(``generer-facture``), aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_export_taux_mixtes"
"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()
TAUX_REELS = {Decimal('10'), Decimal('20')}


class ExportTauxMixtesTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis, Facture, LigneDevis
        from authentication.models import Company
        self.company = Company.objects.create(nom='AFAC52', slug='afac52-co')
        self.user = User.objects.create_user(
            username='afac52_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='AFAC52',
            email='afac52@example.invalid')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AFAC52-1', client=client,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
            mode_installation='residentiel')
        for designation, pu, taux in (('Panneaux', '40000', '10.00'),
                                      ('Reste', '60000', '20.00')):
            LigneDevis.objects.create(
                devis=devis, designation=designation, quantite=Decimal('1'),
                prix_unitaire=Decimal(pu), remise=Decimal('0'),
                taux_tva=Decimal(taux))
        self.tranches = []
        for _ in range(2):  # acompte puis tranche intermédiaire
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/', {},
                format='json')
            self.assertEqual(r.status_code, 201, r.data)
            self.tranches.append(Facture.objects.get(pk=r.data['id']))
        self.debut = date.today().replace(day=1)
        self.fin = date.today() + timedelta(days=1)

    def _journal(self):
        from openpyxl import load_workbook
        from apps.ventes.exports import export_journal_ventes
        resp = export_journal_ventes(self.company, self.debut, self.fin)
        body = (b''.join(resp.streaming_content) if resp.streaming
                else resp.content)
        return load_workbook(BytesIO(body))

    def test_journal_tranche_deux_taux(self):
        wb = self._journal()
        lignes = [r for r in wb.worksheets[0].iter_rows(values_only=True)]
        for tranche in self.tranches:
            mes = [r for r in lignes if r and r[0] == tranche.reference]
            self.assertEqual({Decimal(str(r[9])) for r in mes}, TAUX_REELS)
            ttc = sum((Decimal(str(r[11])) for r in mes), Decimal('0'))
            self.assertEqual(ttc.quantize(Decimal('0.01')),
                             Decimal(str(tranche.total_ttc)))

    def test_resume_tva_sans_taux_melange(self):
        wb = self._journal()
        taux = set()
        for r in wb.worksheets[1].iter_rows(min_row=2, values_only=True):
            libelle = (r or (None,))[0]
            if isinstance(libelle, str) and libelle.endswith('%'):
                taux.add(Decimal(libelle.rstrip('% ').strip()))
        # Seuls les paniers 10 % et 20 % — jamais le taux mélangé (16,62 %).
        self.assertEqual(taux, TAUX_REELS)

    def test_compta_rows_deux_taux(self):
        from apps.ventes.exports import _compta_rows
        rows, _tot = _compta_rows(self.company, self.debut, self.fin)
        for tranche in self.tranches:
            mes = [r for r in rows if r[0] == tranche.reference]
            self.assertEqual({Decimal(str(r[9])) for r in mes}, TAUX_REELS)

    def test_parite_journal_grand_livre_hors_acompte(self):
        """Tranche intermédiaire : HT/TVA par taux du journal = la ventilation
        lue par le grand-livre (``facture_par_taux``)."""
        from apps.ventes.exports import facture_par_taux
        intermediaire = self.tranches[1]
        par_taux, _ttc = facture_par_taux(intermediaire)
        wb = self._journal()
        mes = [r for r in wb.worksheets[0].iter_rows(values_only=True)
               if r and r[0] == intermediaire.reference]
        journal = {Decimal(str(r[9])): (Decimal(str(r[8])).quantize(
            Decimal('0.01')), Decimal(str(r[10])).quantize(Decimal('0.01')))
            for r in mes}
        attendu = {t: (v['ht'], v['tva']) for t, v in par_taux.items()}
        self.assertEqual(journal, attendu)
