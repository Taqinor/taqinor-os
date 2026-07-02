"""
CH4 — Pack de remise client (handover).

Couvre :
  * atteindre la remise (Réceptionné) ASSEMBLE le pack (idempotent) et fait
    tirer la remise de garantie FG70 (parc SAV) inchangée ;
  * le pack RÉFÉRENCE les pièces réelles (as-built, garanties, certificat de
    recette CH3, dossier 82-21, monitoring) ;
  * DÉGRADE proprement : une pièce manquante apparaît `present=False` et un
    pack incomplet est produit quand même (jamais de plantage) ;
  * le gate exige les pièces OBLIGATOIRES : incomplet bloque, complet passe.

Run :
    python manage.py test apps.installations.tests_ch4_handover -v2
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    CommissioningRecord, HandoverPack, Installation,
)
from apps.installations.services import (
    assemble_handover_pieces, ensure_commissioning_record,
    generer_handover_pack, seed_stages, verifier_transition_statut,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ch4-co-{n}', defaults={'nom': f'CH4 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ch4-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, statut=Installation.Statut.INSTALLE):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='CH4',
        email=f'ch4-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-CH4-{n}', client=client,
        statut=statut)


def _pieces_by_type(pieces):
    return {p['type']: p for p in pieces}


class HandoverAssemblyTests(TestCase):
    def setUp(self):
        self.company = make_company()

    def test_degrade_proprement_pieces_manquantes(self):
        inst = make_installation(self.company)
        resume = assemble_handover_pieces(inst)
        by_type = _pieces_by_type(resume['pieces'])
        # Un chantier nu : pièces obligatoires absentes → present=False.
        self.assertFalse(by_type['as_built']['present'])
        self.assertFalse(by_type['commissioning']['present'])
        self.assertFalse(resume['complet'])
        # Dossier 82-21 non concerné → présent (non obligatoire).
        self.assertTrue(by_type['dossier_8221']['present'])
        self.assertFalse(by_type['dossier_8221']['obligatoire'])

    def test_pack_complet_quand_pieces_reunies(self):
        from apps.stock.models import Produit
        from apps.sav.models import Equipement
        from apps.installations.models import DocumentProjet
        inst = make_installation(self.company)
        # As-built.
        DocumentProjet.objects.create(
            company=self.company, installation=inst,
            type_doc='schema_unifilaire', titre='Schéma unifilaire v1')
        # Garantie (parc SAV).
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur CH4',
            prix_vente=Decimal('100'), description='Fiche technique onduleur')
        Equipement.objects.create(
            company=self.company, installation=inst, produit=produit,
            date_fin_garantie=date.today() + timedelta(days=400))
        # Certificat de recette PASSÉ.
        rec = ensure_commissioning_record(inst)
        rec.resultat = CommissioningRecord.Resultat.CONFORME
        rec.save(update_fields=['resultat'])
        inst.refresh_from_db()
        resume = assemble_handover_pieces(inst)
        self.assertTrue(resume['complet'], resume['pieces'])

    def test_generer_pack_idempotent(self):
        inst = make_installation(self.company)
        p1 = generer_handover_pack(inst)
        p2 = generer_handover_pack(inst)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(
            HandoverPack.objects.filter(installation=inst).count(), 1)
        self.assertIsNotNone(p1.date_generation)


class HandoverGateTests(TestCase):
    def setUp(self):
        self.company = make_company()
        seed_stages(self.company)

    def _chantier_pret_pour_remise(self):
        """Chantier avec checklist faite + séries + recette OK, mais SANS pack
        assemblé (as-built manquant)."""
        from apps.stock.models import Produit
        from apps.sav.models import Equipement
        inst = make_installation(
            self.company, statut=Installation.Statut.INSTALLE)
        # Recette OK (débloque exige_tests si présent ailleurs).
        rec = ensure_commissioning_record(inst)
        rec.resultat = CommissioningRecord.Resultat.CONFORME
        rec.save(update_fields=['resultat'])
        # Checklist complète.
        from apps.installations.services import ensure_checklist_items
        for item in ensure_checklist_items(inst):
            item.fait = True
            item.save(update_fields=['fait'])
        # Un équipement/série + garantie.
        produit = Produit.objects.create(
            company=self.company, nom='Panneau CH4', prix_vente=Decimal('50'))
        Equipement.objects.create(
            company=self.company, installation=inst, produit=produit,
            numero_serie='SN-CH4', date_fin_garantie=date.today())
        inst.refresh_from_db()
        return inst

    def test_gate_remise_bloque_sans_as_built(self):
        inst = self._chantier_pret_pour_remise()
        raisons = verifier_transition_statut(
            inst, Installation.Statut.RECEPTIONNE)
        self.assertTrue(any('Pack de remise incomplet' in r for r in raisons),
                        raisons)

    def test_gate_remise_passe_avec_pack_complet(self):
        from apps.installations.models import DocumentProjet
        inst = self._chantier_pret_pour_remise()
        DocumentProjet.objects.create(
            company=self.company, installation=inst,
            type_doc='schema_unifilaire', titre='Schéma')
        inst.refresh_from_db()
        raisons = verifier_transition_statut(
            inst, Installation.Statut.RECEPTIONNE)
        self.assertEqual(raisons, [])


class HandoverApiTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_apercu_get_puis_generation_post(self):
        inst = make_installation(self.company)
        r = self.api.get(f'{BASE}/chantiers/{inst.id}/pack-remise/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['complet'])
        self.assertIn('pieces', r.data)
        r2 = self.api.post(f'{BASE}/chantiers/{inst.id}/pack-remise/')
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertTrue(HandoverPack.objects.filter(
            installation=inst).exists())

    def test_reception_assemble_le_pack_et_remet_la_garantie(self):
        from apps.stock.models import Produit
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur R', prix_vente=Decimal('100'))
        inst = make_installation(
            self.company, statut=Installation.Statut.INSTALLE)
        inst.bom = [{'produit_id': produit.id, 'designation': 'Onduleur R',
                     'quantite': 1}]
        inst.save(update_fields=['bom'])
        r = self.api.patch(
            f'{BASE}/chantiers/{inst.id}/',
            {'statut': Installation.Statut.RECEPTIONNE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # FG70 — garantie remise (équipement au parc).
        self.assertTrue(inst.equipements.exists())
        # CH4 — pack assemblé.
        self.assertTrue(HandoverPack.objects.filter(
            installation=inst).exists())
