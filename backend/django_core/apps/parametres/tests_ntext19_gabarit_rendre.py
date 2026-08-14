"""NTEXT19 — endpoint de rendu d'un gabarit de document custom.

``GET parametres/gabarits-document/<code>/rendre/?cible_id=<id>`` résout l'objet
cible via les selectors de l'app propriétaire, construit un contexte de
placeholders WHITELISTÉS (jamais de prix d'achat / marge) et streame le PDF.
Objet inexistant ou d'une autre société → 404 en français. Un placeholder
inconnu reste littéral et ne fait jamais planter le rendu.
"""
import itertools
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.models import CustomObjectDef, CustomRecord
from apps.parametres import gabarits
from apps.parametres.gabarits_contexte import (
    CLES_INTERDITES, construire_contexte,
)
from apps.parametres.models import GabaritDocumentCustom

User = get_user_model()

URL = '/api/django/parametres/gabarits-document/'

_seq = itertools.count(1)

CORPS = (
    '<h1>{{ objet_libelle }}</h1>'
    '<p>Réf : {{ id }}</p>'
    '<p>Inconnu : {{ champ_absent }}</p>'
)


def make_company(nom=None):
    return Company.objects.create(nom=nom or f'NTEXT19 Co {next(_seq)}')


def make_user(company):
    return User.objects.create_user(
        username=f'ntext19-u{next(_seq)}', password='x',
        role_legacy='responsable', company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RendreGabaritTests(TestCase):
    def setUp(self):
        self.company = make_company('NTEXT19 Rendu')
        self.autre = make_company('NTEXT19 Autre')
        self.user = make_user(self.company)
        self.api = _auth(self.user)
        self.gabarit = GabaritDocumentCustom.objects.create(
            company=self.company, code='fiche-suivi', nom='Fiche de suivi',
            cible=GabaritDocumentCustom.Cible.OBJET_CUSTOM, corps=CORPS)
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='visiteurs',
            libelle='Registre de visiteurs')
        self.record = CustomRecord.objects.create(
            company=self.company, objet=self.objet,
            data={'nom': 'Amine', 'motif': 'Livraison'})

    def test_rendre_streams_a_pdf(self):
        # ``gabarits.rendre_pdf`` importe ``core.pdf.render_pdf`` À L'APPEL :
        # c'est donc CE symbole qu'on remplace (aucun WeasyPrint en test).
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.7 fake'):
            res = self.api.get(
                f'{URL}{self.gabarit.code}/rendre/'
                f'?cible_id={self.record.pk}')
        self.assertEqual(res.status_code, 200, getattr(res, 'data', None))
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))

    def test_missing_cible_id_is_400(self):
        res = self.api.get(f'{URL}{self.gabarit.code}/rendre/')
        self.assertEqual(res.status_code, 400)

    def test_unknown_target_is_404_in_french(self):
        res = self.api.get(
            f'{URL}{self.gabarit.code}/rendre/?cible_id=999999')
        self.assertEqual(res.status_code, 404)
        self.assertIn('société', res.data['detail'])

    def test_target_of_other_company_is_404(self):
        objet_autre = CustomObjectDef.objects.create(
            company=self.autre, code='visiteurs', libelle='Registre')
        record_autre = CustomRecord.objects.create(
            company=self.autre, objet=objet_autre, data={'nom': 'X'})
        res = self.api.get(
            f'{URL}{self.gabarit.code}/rendre/?cible_id={record_autre.pk}')
        self.assertEqual(res.status_code, 404)

    def test_gabarit_of_other_company_is_404(self):
        etranger = GabaritDocumentCustom.objects.create(
            company=self.autre, code='fiche-etrangere', nom='Étrangère',
            cible=GabaritDocumentCustom.Cible.OBJET_CUSTOM, corps=CORPS)
        res = self.api.get(
            f'{URL}{etranger.code}/rendre/?cible_id={self.record.pk}')
        self.assertEqual(res.status_code, 404)

    def test_unknown_placeholder_stays_literal(self):
        contexte = construire_contexte(
            'objet_custom', self.company, self.record.pk)
        html = gabarits.rendre_html(self.gabarit, contexte)
        self.assertIn('Registre de visiteurs', html)
        self.assertIn('{{ champ_absent }}', html)

    def test_context_is_flat_and_prefixed(self):
        contexte = construire_contexte(
            'objet_custom', self.company, self.record.pk)
        self.assertEqual(contexte['nom'], 'Amine')
        self.assertEqual(contexte['objet_custom']['motif'], 'Livraison')

    def test_context_never_exposes_purchase_price(self):
        self.record.data = {'nom': 'Amine', 'prix_achat': '1200',
                            'marge_nette': '15'}
        self.record.save(update_fields=['data'])
        contexte = construire_contexte(
            'objet_custom', self.company, self.record.pk)
        for cle in contexte:
            self.assertFalse(
                any(mot in cle.lower() for mot in CLES_INTERDITES), cle)

    def test_list_only_returns_active_templates_of_the_company(self):
        GabaritDocumentCustom.objects.create(
            company=self.company, code='inactive', nom='Inactive',
            cible=GabaritDocumentCustom.Cible.CLIENT, corps='', actif=False)
        GabaritDocumentCustom.objects.create(
            company=self.autre, code='autre-societe', nom='Autre',
            cible=GabaritDocumentCustom.Cible.CLIENT, corps='')
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200)
        donnees = res.data
        resultats = donnees['results'] if 'results' in donnees else donnees
        self.assertEqual([r['code'] for r in resultats], ['fiche-suivi'])
