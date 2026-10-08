"""AFAC31 (C-AFAC-031 + C-AFAC-049) — UNE décomposition `decomposition_du`
(TTC + notes de débit − payés − RAS subies − avoirs − abandons) que lisent
`montant_du`, le relevé client (JSON, PDF, portail) et le bloc « Déjà payé /
Reste à payer » du PDF facture : chaque document se rapproche à la main au
centime.

Rejoue FCOR-8 (relevé sans ND/RAS/abandon : écarts 15 000 et 480),
L2-C-AFAC-031 (abandon 500) et FDOC-10 (PDF facture : « débit » absent,
abandon absent). Le PDF est vérifié sur son HTML rendu (WeasyPrint jamais
appelé), comme `apps/ventes/tests/test_facture_pdf_deja_paye.py`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_decomposition_du"
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class DecompositionDuTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC31 Co', slug=f'afac31-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac31_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Releve', prenom='AFAC31',
            email=f'afac31-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    # ── fixtures ────────────────────────────────────────────────────────
    def _facture(self, ttc):
        from apps.ventes.models import Facture
        ttc = Decimal(ttc)
        tva = (ttc / Decimal('6')).quantize(Decimal('0.01'))
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC31-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc - tva, montant_tva=tva, montant_ttc=ttc,
            date_emission=date(2026, 9, 1))

    def _nd(self, facture, ttc):
        from apps.ventes.models import NoteDebit
        ttc = Decimal(ttc)
        tva = (ttc / Decimal('6')).quantize(Decimal('0.01'))
        return NoteDebit.objects.create(
            company=self.company, reference=f'ND-AFAC31-{_nxt()}',
            facture=facture, client=self.client_obj, statut='emise',
            motif='Complément', montant_ht=ttc - tva, montant_tva=tva,
            montant_ttc=ttc)

    def _payer(self, facture, montant):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=date(2026, 9, 15), mode='virement',
            created_by=self.admin)

    def _ras(self, facture, montant):
        from apps.ventes.models import RetenueSubie
        RetenueSubie.objects.create(
            company=self.company, facture=facture, type_retenue='ras_tva',
            taux=Decimal('75'), base=Decimal('20000'),
            montant=Decimal(montant))

    def _abandon(self, facture, montant):
        from apps.ventes.models import Facture
        Facture.objects.filter(pk=facture.pk).update(
            abandon_montant=Decimal(montant),
            abandon_motif='geste_commercial')

    def _releve(self):
        r = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/releve/')
        self.assertEqual(r.status_code, 200, getattr(r, 'data', r))
        return r.data

    def _se_rapproche(self, ligne):
        d = {k: Decimal(ligne[k]) for k in (
            'notes_debit', 'paye', 'retenues', 'avoirs', 'abandons', 'du')}
        total = Decimal(ligne.get('total_ttc', ligne.get('facture')))
        self.assertEqual(
            total + d['notes_debit'] - d['paye'] - d['retenues']
            - d['avoirs'] - d['abandons'], d['du'], ligne)

    def _ligne(self, data, facture):
        return next(x for x in data['lignes']
                    if x['reference'] == facture.reference)

    # ── relevé ──────────────────────────────────────────────────────────
    def test_releve_se_rapproche_nd(self):
        a = self._facture('100000')
        self._nd(a, '10000')
        data = self._releve()
        ligne = self._ligne(data, a)
        self.assertEqual(Decimal(ligne['notes_debit']), Decimal('10000.00'))
        self.assertEqual(Decimal(ligne['du']), Decimal('110000.00'))
        self._se_rapproche(ligne)
        self._se_rapproche(data['totaux'])

    def test_releve_se_rapproche_ras(self):
        b = self._facture('120000')
        self._payer(b, '105000')
        self._ras(b, '15000')
        data = self._releve()
        ligne = self._ligne(data, b)
        self.assertEqual(Decimal(ligne['retenues']), Decimal('15000.00'))
        self._se_rapproche(ligne)

    def test_releve_se_rapproche_abandon(self):
        c = self._facture('1200')
        self._payer(c, '700')
        self._abandon(c, '500')
        data = self._releve()
        ligne = self._ligne(data, c)
        self.assertEqual(Decimal(ligne['abandons']), Decimal('500.00'))
        self._se_rapproche(ligne)
        self._se_rapproche(data['totaux'])
        # Le PDF du relevé imprime les six lignes de la décomposition.
        from apps.ventes.recouvrement import _releve_data
        from apps.ventes.utils.pdf import generate_releve_pdf
        with patch('apps.ventes.utils.pdf._html_to_pdf',
                   return_value=b'%PDF') as rendu:
            generate_releve_pdf(self.client_obj, _releve_data(self.client_obj))
        html = rendu.call_args[0][0]
        for libelle in ('Notes de débit', 'Retenues à la source',
                        'Abandons de créance', 'Solde dû'):
            self.assertIn(libelle, html)

    def test_pdf_facture_bloc_reste_nd_abandon(self):
        from apps.ventes.models import Facture
        from apps.ventes.utils.pdf import (
            _company_context, _render_html, reglements_facture_pdf,
        )
        d = self._facture('1000')
        self._nd(d, '20')
        self._payer(d, '500')
        d = Facture.objects.get(pk=d.pk)
        ctx = _company_context(company=self.company)
        ctx['facture'] = d
        ctx['reglements'] = reglements_facture_pdf(d)
        html = _render_html('facture.html', ctx)
        self.assertIn('Note de débit', html)
        self.assertIn('+20.00 MAD', html)
        self.assertIn('520.00 MAD', html)
        self.assertEqual(d.montant_du, Decimal('520.00'))

        c = self._facture('1200')
        self._payer(c, '700')
        self._abandon(c, '500')
        c = Facture.objects.get(pk=c.pk)
        ctx['facture'] = c
        ctx['reglements'] = reglements_facture_pdf(c)
        html = _render_html('facture.html', ctx)
        self.assertIn('Abandon de créance', html)
        self.assertIn('−500.00 MAD', html)

    def test_portail_meme_decomposition(self):
        from apps.ventes.selectors_facturation import releve_client_portail
        a = self._facture('100000')
        self._nd(a, '10000')
        b = self._facture('120000')
        self._payer(b, '105000')
        self._ras(b, '15000')
        portail = releve_client_portail(self.client_obj)
        interne = self._releve()
        self.assertEqual(
            {k: str(v) for k, v in portail['totaux'].items()},
            {k: str(v) for k, v in interne['totaux'].items()})
        self._se_rapproche(portail['totaux'])
