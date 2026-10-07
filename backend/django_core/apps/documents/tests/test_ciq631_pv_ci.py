"""CIQ631 — PV de réception C&I : signataire nommé (fonction, société),
co-signature facultative, recette et réserves imprimées, empreinte qui couvre
leur contenu. Tests sur le HTML RENDU.
"""
import datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation, Reserve
from apps.installations.services import (
    ESSAIS_RECETTE, ensure_commissioning_record,
)
from authentication.models import Company

User = get_user_model()
TRAIT = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQ'
    'GAhKmMIQAAAABJRU5ErkJggg==')


@patch('apps.ventes.utils.pdf._download', return_value=None)
@patch('apps.documents.builders._html_to_pdf')
class PvReceptionCITests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ631', slug='ciq631-co')
        self.client_ent = Client.objects.create(
            company=self.company, nom='Hôtel Atlas SARL',
            type_client='entreprise', email='h@example.com')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-CIQ631-10',
            client=self.client_ent, type_installation='industriel',
            puissance_installee_kwc=Decimal('100'))
        record = ensure_commissioning_record(self.inst)
        for champ in ESSAIS_RECETTE:
            setattr(record, champ, True)
        record.resultat = 'reserves'
        record.date_essai = datetime.date(2026, 10, 12)
        record.save()
        self.reserve = Reserve.objects.create(
            company=self.company, installation=self.inst, origine='recette',
            description='Étiquette coffret AC', responsable='Équipe pose',
            date_echeance=datetime.date(2026, 10, 26))
        self.inst.signature_client = TRAIT
        self.inst.signataire_nom = 'Karim Alaoui'
        self.inst.signataire_fonction = 'Directeur technique'
        self.inst.signataire_societe = 'Hôtel Atlas SARL'
        self.inst.cosignataire_nom = 'Nadia Bennani'
        self.inst.cosignataire_organisme = 'Bureau de contrôle'
        self.inst.signe_le = timezone.now()
        self.inst.save()

    def _html(self, mock_pdf, chantier, **kwargs):
        from apps.documents import builders
        mock_pdf.return_value = b'%PDF-fake'
        builders.generate_pv_reception(chantier, **kwargs)
        return mock_pdf.call_args[0][0]

    def test_pv_ci_porte_fonction_societe_reserves_resultat(
            self, mock_pdf, _dl):
        html = self._html(mock_pdf, self.inst)
        self.assertIn('Directeur technique', html)
        self.assertIn('Hôtel Atlas SARL', html)
        self.assertIn('Co-signataire : Nadia Bennani', html)
        self.assertIn('Étiquette coffret AC', html)
        self.assertIn('26/10/2026', html)
        self.assertIn('Équipe pose', html)
        self.assertIn('Conforme avec réserves', html)
        self.assertIn('PR mesuré (à titre d&#x27;information)', html)
        self.assertNotIn('prix_achat', html)

    def test_modifier_une_reserve_change_l_empreinte(self, mock_pdf, _dl):
        from apps.documents.builders import empreinte_signature
        avant = empreinte_signature(self.inst)
        self.reserve.date_echeance = datetime.date(2026, 11, 2)
        self.reserve.save()
        self.assertNotEqual(avant, empreinte_signature(self.inst))

    def test_pv_definitive_meme_gabarit_titre_et_date(self, mock_pdf, _dl):
        self.inst.date_reception_definitive = datetime.date(2027, 10, 13)
        self.inst.save()
        html = self._html(mock_pdf, self.inst, definitive=True)
        self.assertIn('PROCÈS-VERBAL DE RÉCEPTION DÉFINITIVE', html)
        self.assertIn('13/10/2027', html)

    def test_residentiel_empreinte_inchangee_champs_vides(
            self, mock_pdf, _dl):
        import hashlib
        from apps.documents.builders import empreinte_signature
        inst = Installation.objects.create(
            company=self.company, reference='CHT-CIQ631-20',
            type_installation='residentiel', signature_client=TRAIT,
            signataire_nom='Salma', signe_le=timezone.now())
        graine = '|'.join([inst.reference, 'Salma',
                           inst.signe_le.isoformat(), TRAIT])
        self.assertEqual(empreinte_signature(inst),
                         hashlib.sha256(graine.encode()).hexdigest()[:16])
        html = self._html(mock_pdf, inst)
        self.assertNotIn('Recette de mise en service', html)
        self.assertNotIn('Signataire :', html)


class SignerClientCITests(TestCase):
    def test_signer_client_saisit_fonction_et_preremplit_societe(self):
        company = Company.objects.create(nom='CIQ631b', slug='ciq631-b')
        user = User.objects.create_user(
            username='ciq631', password='x', role_legacy='responsable',
            company=company)
        client = Client.objects.create(
            company=company, nom='Clinique Anfa SA',
            type_client='entreprise', email='c@example.com')
        inst = Installation.objects.create(
            company=company, reference='CHT-CIQ631-30', client=client,
            type_installation='industriel')
        api = APIClient()
        api.force_authenticate(user)
        r = api.post(
            f'/api/django/installations/chantiers/{inst.id}/signer-client/',
            {'signature_client': TRAIT, 'signataire_nom': 'Dr Idrissi',
             'signataire_fonction': 'Directeur', 'cosignataire_nom': 'BET'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        inst.refresh_from_db()
        self.assertEqual(inst.signataire_fonction, 'Directeur')
        self.assertEqual(inst.signataire_societe, 'Clinique Anfa SA')
        self.assertEqual(inst.cosignataire_nom, 'BET')
