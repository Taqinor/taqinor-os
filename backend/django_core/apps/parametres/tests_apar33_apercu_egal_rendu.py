"""APAR33 — l'APERÇU d'un gabarit de document a la même enveloppe que le rendu
réel (``{cible: {…}}`` + clés plates) et signale toute variable que le rendu
ne servira jamais, au lieu d'inventer « Exemple <racine> » (C-APAR-046)."""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres import gabarits_contexte as gc
from apps.parametres.models import GabaritDocumentCustom
from authentication.models import Company
from core.templating import rendre, variables_utilisees

User = get_user_model()

CORPS = ('Chantier {{ chantier.reference }} / {{ reference }} / '
         '{{ clien_nom }}')


def _faux(champs, **extra):
    return SimpleNamespace(**{c: f'v-{c}' for c in champs}, **extra)


class ApercuEgalRenduTests(SimpleTestCase):
    def test_cles_exemples_egales_cles_resolveurs(self):
        champs = {
            'chantier': gc._champs_chantier(_faux(
                ['reference', 'statut', 'date_debut', 'date_fin',
                 'site_ville', 'site_adresse', 'puissance_kwc'],
                client='Client X')),
            'client': gc._champs_client(_faux(
                ['nom', 'prenom', 'email', 'telephone', 'ville', 'adresse',
                 'ice'])),
            'ticket': gc._champs_ticket(_faux(
                ['reference', 'statut', 'priorite', 'type', 'description'],
                client='Client X')),
        }
        for cible, contexte in champs.items():
            with self.subTest(cible=cible):
                self.assertEqual(set(gc.EXEMPLES[cible]), set(contexte))

    def test_cas_pointe_rempli_et_faute_de_frappe_signalee(self):
        contexte, avertissements = gc.apercu_contexte(
            'chantier', variables_utilisees(CORPS))
        self.assertEqual(
            rendre(CORPS, contexte, strict=False),
            'Chantier CH-2026-0042 / CH-2026-0042 / ')
        self.assertEqual(avertissements, ['variable inconnue : clien_nom'])

    def test_rendu_reel_meme_enveloppe(self):
        chantier = _faux(
            ['statut', 'date_debut', 'date_fin', 'site_ville', 'site_adresse',
             'puissance_kwc'], reference='CHT-202610-0002', client=None)
        with patch.dict(gc.RESOLVEURS, {
                'chantier': lambda company, cid: gc._champs_chantier(chantier)}):
            reel = gc.construire_contexte('chantier', None, 1)
        self.assertEqual(
            rendre(CORPS, reel, strict=False),
            'Chantier CHT-202610-0002 / CHT-202610-0002 / ')
        apercu, _ = gc.apercu_contexte('chantier', variables_utilisees(CORPS))
        self.assertEqual(set(apercu), set(reel))
        self.assertEqual(set(apercu['chantier']), set(reel['chantier']))

    def test_objet_custom_garde_un_exemple_generique(self):
        contexte, avertissements = gc.apercu_contexte(
            'objet_custom', ['numero_compteur'])
        self.assertEqual(contexte['numero_compteur'], 'Exemple numero compteur')
        self.assertEqual(avertissements, [])


class ApercuAvertissementsApiTests(TestCase):
    def test_entete_avertissements(self):
        company = Company.objects.create(nom='APAR33 Co', slug='apar33-co')
        user = User.objects.create_user(
            username='apar33_u', password='x', role_legacy='responsable',
            company=company)
        GabaritDocumentCustom.objects.create(
            company=company, code='apar33', nom='APAR33',
            cible=GabaritDocumentCustom.Cible.CHANTIER, corps=CORPS)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        with patch('core.pdf.render_pdf', return_value=b'%PDF') as m:
            res = api.get('/api/django/parametres/gabarits-document/apar33/apercu/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Chantier CH-2026-0042 / CH-2026-0042 /',
                      m.call_args.kwargs['html'])
        self.assertEqual(json.loads(res['X-Apercu-Avertissements']),
                         ['variable inconnue : clien_nom'])
