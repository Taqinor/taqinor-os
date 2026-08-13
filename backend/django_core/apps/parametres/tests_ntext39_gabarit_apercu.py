"""NTEXT39 — aperçu d'un gabarit de document avec des données FACTICES.

``GET parametres/gabarits-document/<code>/apercu/`` rend le gabarit avec un jeu
de valeurs de DÉMONSTRATION : la mise en page est vérifiable avant usage, sans
lire ni modifier une seule fiche réelle.
"""
import itertools
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.models import CustomObjectDef, CustomRecord
from apps.parametres.gabarits_contexte import contexte_demonstration
from apps.parametres.models import GabaritDocumentCustom

User = get_user_model()

URL = '/api/django/parametres/gabarits-document/'

_seq = itertools.count(1)

CORPS = (
    '<h1>Fiche {{ reference }}</h1>'
    '<p>Client : {{ client_nom }}</p>'
    '<p>Ville : {{ site_ville }}</p>'
    '<p>Champ maison : {{ numero_compteur }}</p>'
)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ContexteDemonstrationTests(TestCase):
    def test_valeurs_dexemple_par_cible(self):
        contexte = contexte_demonstration('chantier', ['reference',
                                                       'client_nom'])
        self.assertEqual(contexte['reference'], 'CH-2026-0042')
        self.assertEqual(contexte['client_nom'], 'Société Exemple SARL')

    def test_placeholder_inconnu_recoit_une_valeur_generique(self):
        contexte = contexte_demonstration('chantier', ['numero_compteur'])
        self.assertEqual(contexte['numero_compteur'], 'Exemple numero compteur')

    def test_aucune_cle_de_prix_dachat_meme_en_exemple(self):
        contexte = contexte_demonstration(
            'chantier', ['prix_achat', 'marge', 'reference'])
        self.assertNotIn('prix_achat', contexte)
        self.assertNotIn('marge', contexte)
        self.assertIn('reference', contexte)


class ApercuGabaritTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom=f'NTEXT39 Co {next(_seq)}')
        self.user = User.objects.create_user(
            username=f'ntext39-u{next(_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = _auth(self.user)
        self.gabarit = GabaritDocumentCustom.objects.create(
            company=self.company, code='fiche_visite', nom='Fiche de visite',
            cible=GabaritDocumentCustom.Cible.CHANTIER, corps=CORPS)

    def test_apercu_streame_un_pdf_sans_cible_id(self):
        with patch('core.pdf.render_pdf', return_value=b'%PDF-1.7 fake') as m:
            res = self.api.get(f'{URL}fiche_visite/apercu/')
        self.assertEqual(res.status_code, 200, getattr(res, 'data', res))
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertIn('fiche_visite-apercu.pdf', res['Content-Disposition'])

        html = m.call_args.kwargs['html']
        self.assertIn('CH-2026-0042', html)
        self.assertIn('Société Exemple SARL', html)
        self.assertIn('Casablanca', html)
        # Le placeholder « maison » est REMPLI (jamais laissé littéral).
        self.assertIn('Exemple numero compteur', html)
        self.assertNotIn('{{', html)

    def test_apercu_ne_touche_aucune_donnee_reelle(self):
        objet = CustomObjectDef.objects.create(
            company=self.company, code='visites', libelle='Visites')
        CustomRecord.objects.create(
            company=self.company, objet=objet, data={'reference': 'VRAI-001'})
        with patch('core.pdf.render_pdf', return_value=b'%PDF') as m:
            res = self.api.get(f'{URL}fiche_visite/apercu/')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('VRAI-001', m.call_args.kwargs['html'])
        self.assertEqual(CustomRecord.objects.count(), 1)

    def test_gabarit_dune_autre_societe_reste_invisible(self):
        autre = Company.objects.create(nom=f'NTEXT39 Autre {next(_seq)}')
        GabaritDocumentCustom.objects.create(
            company=autre, code='hors_societe', nom='Hors société',
            cible=GabaritDocumentCustom.Cible.CLIENT, corps='<p>x</p>')
        res = self.api.get(f'{URL}hors_societe/apercu/')
        self.assertEqual(res.status_code, 404)

    def test_moteur_pdf_absent_degrade_en_503(self):
        with patch('apps.parametres.views_gabarits.rendre_pdf',
                   side_effect=OSError('boom')):
            res = self.api.get(f'{URL}fiche_visite/apercu/')
        self.assertEqual(res.status_code, 503)
