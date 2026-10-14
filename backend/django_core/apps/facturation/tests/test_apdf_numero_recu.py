"""APDF30 (C-APDF-011) — le reçu de paiement est numéroté par une séquence
PROPRE à la société (``Paiement.numero_recu``, posé à la première émission
par ``core.numbering``), imprimée à la place de ``paiement.id``.

Rejoue la sonde PFAC-4 (société 2 → n° 8, nouveau paiement société 6 →
n° 192). Vrai ``generate_recu_pdf`` (rendu réel), texte PyMuPDF, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_apdf_numero_recu"
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _texte(pdf_bytes):
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    try:
        return ' '.join(' '.join(page.get_text().split()) for page in doc)
    finally:
        doc.close()


class NumeroRecuTests(TestCase):
    def _societe(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from authentication.models import Company
        n = _nxt()
        company = Company.objects.create(nom=f'APDF30 {n}', slug=f'apdf30-{n}')
        client = Client.objects.create(
            company=company, nom='Client', prenom='APDF30',
            email=f'apdf30-{n}@example.invalid')
        facture = Facture.objects.create(
            company=company, reference=f'FAC-APDF30-{n}', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'),
            montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
            montant_ttc=Decimal('12000'))
        return company, facture

    def _paiement(self, company, facture):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=company, facture=facture, montant=Decimal('100'),
            date_paiement=date(2026, 10, 1), mode=Paiement.Mode.ESPECES)

    def _rendre(self, paiement):
        from apps.ventes.models import Paiement
        from apps.ventes.utils.pdf import generate_recu_pdf
        frais = Paiement.objects.select_related(
            'facture', 'facture__client', 'company').get(pk=paiement.pk)
        return _texte(generate_recu_pdf(frais))

    def test_sequence_par_societe(self):
        co_a, fa = self._societe()
        pa = [self._paiement(co_a, fa) for _ in range(3)]
        co_b, fb = self._societe()
        pb = self._paiement(co_b, fb)
        textes_a = [self._rendre(p) for p in pa]
        texte_b = self._rendre(pb)
        for i, texte in enumerate(textes_a, start=1):
            self.assertIn(f'Reçu de paiement n° REC-{i:04d}', texte)
        self.assertIn('Reçu de paiement n° REC-0001', texte_b)
        self.assertNotIn(f'n° {pb.id} ', texte_b + ' ')

    def test_stable_au_second_rendu(self):
        from apps.ventes.models import Paiement
        co, f = self._societe()
        p = self._paiement(co, f)
        premier = self._rendre(p)
        # CLAUSE PERSISTANCE : numéro stocké, identique au rendu suivant.
        stocke = Paiement.objects.get(pk=p.pk).numero_recu
        self.assertEqual(stocke, 'REC-0001')
        second = self._rendre(p)
        self.assertIn('n° REC-0001', premier)
        self.assertIn('n° REC-0001', second)
        self.assertEqual(Paiement.objects.get(pk=p.pk).numero_recu, stocke)

    def test_independant_des_rollbacks(self):
        """La séquence Postgres globale avance (lignes créées puis annulées) :
        le numéro de reçu, lui, reste contigu dans la société."""
        from django.db import transaction
        co, f = self._societe()
        p1 = self._paiement(co, f)
        self._rendre(p1)
        try:
            with transaction.atomic():
                for _ in range(5):
                    self._paiement(co, f)
                raise RuntimeError('annulation')
        except RuntimeError:
            pass
        p2 = self._paiement(co, f)
        self.assertIn('n° REC-0002', self._rendre(p2))


class RecuPdfVueTests(TestCase):
    """VNT43 — ``GET paiements/<id>/recu-pdf/`` nomme le fichier
    ``Quittance_<numero_recu>.pdf`` (comme l'e-mail), jamais par l'id ; un
    rendu en échec répond un message générique (jamais l'exception brute)."""
    _societe = NumeroRecuTests._societe
    _paiement = NumeroRecuTests._paiement
    _rendre = NumeroRecuTests._rendre

    def _api(self, company):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        user = get_user_model().objects.create_user(
            username=f'vnt43_{_nxt()}', password='x',
            role_legacy='responsable', company=company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_nom_de_fichier_par_numero_de_recu(self):
        from apps.ventes.models import Paiement
        co, f = self._societe()
        for _ in range(2):
            self._rendre(self._paiement(co, f))
        p = self._paiement(co, f)
        r = self._api(co).get(f'/api/django/ventes/paiements/{p.pk}/recu-pdf/')
        self.assertEqual(r.status_code, 200)
        numero = Paiement.objects.get(pk=p.pk).numero_recu
        self.assertEqual(numero, 'REC-0003')
        self.assertIn('Quittance_REC-0003.pdf', r['Content-Disposition'])
        self.assertNotIn(f'Quittance_{p.pk}.pdf', r['Content-Disposition'])

    def test_echec_de_rendu_message_generique(self):
        from unittest.mock import patch
        co, f = self._societe()
        p = self._paiement(co, f)
        with patch('apps.ventes.utils.pdf.generate_recu_pdf',
                   side_effect=RuntimeError('chemin /opt/secret introuvable')):
            r = self._api(co).get(
                f'/api/django/ventes/paiements/{p.pk}/recu-pdf/')
        self.assertEqual(r.status_code, 500)
        self.assertNotIn('/opt/secret', str(r.data))
        self.assertNotIn('RuntimeError', str(r.data))
        self.assertTrue(r.data.get('detail'))


class ResteVenteRecuTests(TestCase):
    """VNT92 — 388, échéancier [acompte 15 000, solde 34 000] : le reçu de
    l'acompte payé imprime « Solde restant dû sur <réf> : 0.00 MAD » ET
    « Reste dû sur la vente : 34000.00 MAD (devis <réf>) », ce reste ==
    ``etat_vente`` ; en arabe via ``TEXTES_AR`` ; un paiement d'une facture
    sans devis garde le reçu d'hier."""

    LIBRE = [{'type': 'acompte', 'libelle': 'Acompte', 'unite': 'montant',
              'pct_or_montant': 15000},
             {'type': 'solde', 'libelle': 'Solde', 'unite': 'montant',
              'pct_or_montant': 34000}]
    _societe = NumeroRecuTests._societe
    _paiement = NumeroRecuTests._paiement
    _rendre = NumeroRecuTests._rendre

    def _acompte_paye(self, langue=None):
        from apps.crm.models import Client
        from apps.ventes.domain.encaissements import (
            recalculer_statut_paiement)
        from apps.ventes.models import Paiement
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        from apps.ventes.utils.echeancier import creer_facture_tranche
        company = make_company()
        user = make_user(company)
        client = make_client(company)
        if langue:
            Client.objects.filter(pk=client.pk).update(langue_document=langue)
            client.refresh_from_db()
        devis = creer_devis_388(company, user, client,
                                f'DEV-VNT92-{_nxt()}', self.LIBRE)
        acompte = creer_facture_tranche(devis, user, company, None)
        paiement = Paiement.objects.create(
            company=company, facture=acompte, montant=Decimal('15000'),
            date_paiement=date(2026, 10, 12), mode=Paiement.Mode.VIREMENT)
        recalculer_statut_paiement(acompte)
        return devis, acompte, paiement

    def _html(self, paiement):
        from unittest.mock import patch

        from apps.ventes.models import Paiement
        from apps.ventes.utils.pdf import generate_recu_pdf
        boite = {}

        def _capturer(html):
            boite['html'] = html
            return b''

        frais = Paiement.objects.select_related(
            'facture', 'facture__client', 'company').get(pk=paiement.pk)
        with patch('apps.ventes.utils.pdf._html_to_pdf',
                   side_effect=_capturer):
            generate_recu_pdf(frais)
        return boite['html']

    def test_acompte_paye_reste_sur_la_vente(self):
        from apps.ventes.vente_facturation import etat_vente
        devis, acompte, paiement = self._acompte_paye()
        texte = self._rendre(paiement)
        self.assertIn(
            f'Solde restant dû sur {acompte.reference} : 0.00 MAD', texte)
        self.assertIn('Reste dû sur la vente : 34000.00 MAD', texte)
        self.assertIn(f'(devis {devis.reference})', texte)
        etat = etat_vente(devis)
        self.assertEqual(Decimal(etat['reste_a_payer_ttc']),
                         Decimal('34000.00'))
        # Payé + reste dû sur la vente = prix convenu (49 000).
        self.assertEqual(paiement.montant + Decimal(etat['reste_a_payer_ttc']),
                         Decimal(etat['prix_convenu_ttc']))

    def test_arabe_via_textes_ar(self):
        from apps.ventes.utils.libelles_ar import TEXTES_AR
        _devis, _acompte, paiement = self._acompte_paye(langue='ar')
        html = self._html(paiement)
        self.assertIn(TEXTES_AR['Reste dû sur la vente'], html)
        self.assertNotIn('Reste dû sur la vente', html)
        self.assertIn('34000.00 MAD', html)

    def test_paiement_sans_devis_recu_inchange(self):
        from apps.ventes.utils.pdf import reste_vente_recu
        co, f = self._societe()
        p = self._paiement(co, f)
        self.assertIsNone(reste_vente_recu(p))
        html = self._html(p)
        self.assertNotIn('Reste dû sur la vente', html)
        self.assertEqual(html.count('class="solde-block"'), 1)
