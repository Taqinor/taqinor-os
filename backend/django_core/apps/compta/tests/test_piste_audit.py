"""Tests COMPTA39 — piste d'audit comptable inaltérable (hash-chaînée).

Chaque écriture validée est scellée dans un maillon append-only enchaîné au
précédent (hash = SHA256(hash_precedent + empreinte_contenu)). On vérifie :
le chaînage, l'idempotence du scellement, la détection d'une altération
d'écriture (rupture de chaîne) et l'append-only du maillon.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    EcritureComptable, Journal, LigneEcriture, PisteAuditComptable,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PisteAuditTests(TestCase):
    def setUp(self):
        self.co = make_company('compta-audit', 'Compta Audit')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.filter(
            company=self.co, type_journal=Journal.Type.VENTE).first()

    def _ecriture(self, montant=Decimal('100')):
        ecr = EcritureComptable.objects.create(
            company=self.co, journal=self.journal,
            date_ecriture=date(2026, 4, 1), libelle='Écriture audit',
            reference='EC-1', statut=EcritureComptable.Statut.VALIDEE)
        c5141 = services._assurer_compte(self.co, '5141')
        c7121 = services._assurer_compte(self.co, '7121')
        LigneEcriture.objects.create(
            company=self.co, ecriture=ecr, compte=c5141,
            debit=montant, credit=Decimal('0'), libelle='d')
        LigneEcriture.objects.create(
            company=self.co, ecriture=ecr, compte=c7121,
            debit=Decimal('0'), credit=montant, libelle='c')
        return ecr

    def test_scellement_chaine_les_maillons(self):
        e1 = self._ecriture()
        e2 = self._ecriture(Decimal('200'))
        m1 = services.enregistrer_piste_audit(e1)
        m2 = services.enregistrer_piste_audit(e2)
        self.assertEqual(m1.sequence, 1)
        self.assertEqual(m1.hash_precedent, '')  # genesis
        self.assertEqual(m2.sequence, 2)
        # Le hash du 2e maillon reprend le hash du 1er.
        self.assertEqual(m2.hash_precedent, m1.hash)
        self.assertNotEqual(m1.hash, m2.hash)

    def test_idempotent(self):
        e1 = self._ecriture()
        a = services.enregistrer_piste_audit(e1)
        b = services.enregistrer_piste_audit(e1)
        self.assertEqual(a.id, b.id)
        self.assertEqual(
            PisteAuditComptable.objects.filter(company=self.co).count(), 1)

    def test_integrite_valide(self):
        services.enregistrer_piste_audit(self._ecriture())
        services.enregistrer_piste_audit(self._ecriture(Decimal('300')))
        res = services.verifier_integrite_piste(self.co)
        self.assertTrue(res['valide'])
        self.assertEqual(res['nb_maillons'], 2)
        self.assertIsNone(res['rupture'])

    def test_alteration_ecriture_casse_la_chaine(self):
        e1 = self._ecriture()
        services.enregistrer_piste_audit(e1)
        services.enregistrer_piste_audit(self._ecriture(Decimal('300')))
        # On altère l'écriture scellée après coup → l'empreinte ne colle plus.
        e1.libelle = 'LIBELLÉ FALSIFIÉ'
        # Contourne le save() protégé de l'écriture pour simuler une fraude SQL.
        EcritureComptable.objects.filter(pk=e1.pk).update(
            libelle='LIBELLÉ FALSIFIÉ')
        res = services.verifier_integrite_piste(self.co)
        self.assertFalse(res['valide'])
        self.assertEqual(res['rupture'], 1)

    def test_maillon_append_only(self):
        m = services.enregistrer_piste_audit(self._ecriture())
        m.hash = 'x' * 64
        with self.assertRaises(ValidationError):
            m.save()

    def test_aud170_maillon_protege_la_suppression_de_l_ecriture(self):
        """AUD170 — une écriture scellée ne peut plus disparaître en cascade."""
        from django.db.models import ProtectedError

        ecr = self._ecriture()
        services.enregistrer_piste_audit(ecr)
        with self.assertRaises(ProtectedError):
            ecr.delete()
        self.assertTrue(
            EcritureComptable.objects.filter(pk=ecr.pk).exists())
        self.assertTrue(
            PisteAuditComptable.objects.filter(ecriture=ecr).exists())

    def test_scope_societe(self):
        autre = make_company('compta-audit-autre', 'Autre')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        services.enregistrer_piste_audit(self._ecriture())
        # La chaîne de l'autre société est vide et intègre.
        res = services.verifier_integrite_piste(autre)
        self.assertTrue(res['valide'])
        self.assertEqual(res['nb_maillons'], 0)


class Aud170SuppressionEcritureApiTests(TestCase):
    """AUD170 — ``DELETE /compta/ecritures/<id>/`` refuse le validé/scellé."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        self.co = make_company('aud170-co', 'AUD170 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.journal = Journal.objects.filter(
            company=self.co, type_journal=Journal.Type.VENTE).first()
        self.user = User.objects.create_user(
            username='aud170-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _ecriture(self, statut, montant=Decimal('250000')):
        ecr = EcritureComptable.objects.create(
            company=self.co, journal=self.journal,
            date_ecriture=date(2026, 4, 1), libelle='Vente AUD170',
            reference=f'EC-{statut}', statut=statut)
        c5141 = services._assurer_compte(self.co, '5141')
        c7121 = services._assurer_compte(self.co, '7121')
        LigneEcriture.objects.create(
            company=self.co, ecriture=ecr, compte=c5141,
            debit=montant, credit=Decimal('0'))
        LigneEcriture.objects.create(
            company=self.co, ecriture=ecr, compte=c7121,
            debit=Decimal('0'), credit=montant)
        return ecr

    def test_delete_ecriture_validee_refuse(self):
        ecr = self._ecriture(EcritureComptable.Statut.VALIDEE)
        resp = self.api.delete(f'/api/django/compta/ecritures/{ecr.id}/')
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertLess(resp.status_code, 500)
        self.assertTrue(
            EcritureComptable.objects.filter(pk=ecr.pk).exists())

    def test_delete_ecriture_scellee_refuse(self):
        ecr = self._ecriture(EcritureComptable.Statut.BROUILLON)
        services.enregistrer_piste_audit(ecr)
        resp = self.api.delete(f'/api/django/compta/ecritures/{ecr.id}/')
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertLess(resp.status_code, 500)
        self.assertTrue(
            EcritureComptable.objects.filter(pk=ecr.pk).exists())

    def test_delete_brouillon_periode_ouverte_reste_204(self):
        ecr = self._ecriture(EcritureComptable.Statut.BROUILLON)
        resp = self.api.delete(f'/api/django/compta/ecritures/{ecr.id}/')
        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', None))
        self.assertFalse(
            EcritureComptable.objects.filter(pk=ecr.pk).exists())
