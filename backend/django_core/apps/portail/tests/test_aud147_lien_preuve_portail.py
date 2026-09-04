"""AUD147 — le portail ne rend plus un lien MORT vers la preuve de livraison.

Défaut d'origine : `selectors.livraisons_client_portail` servait
`pod_url = /api/django/installations/preuves-livraison/<id>/`, résolu vers
`PreuveLivraisonViewSet` (`IsAnyRole`), et
`frontend/src/features/portail/client/PortailClientLivraisons.jsx` le rendait
en `<a href … target="_blank">` dès `pod_disponible`. Or
`authentication.permissions.IsAnyRole` exclut explicitement
`portee != 'interne'` : le client cliquait « Voir la preuve de livraison » et
recevait 403 — sur SON PROPRE document.

AUD301 a livré la route PORTAIL (`GET /portail/mes-livraisons/<id>/preuve/`,
`IsPortalClientUser`, triplet société/client/livraison) et y a repointé
`pod_url` ; AUD147 branche la MOITIÉ ÉCRAN dessus : la preuve est LUE par
l'API et RENDUE dans le portail (le chemin renvoie un document JSON, pas un
fichier — un `<a href>` n'aurait affiché que du JSON brut).

Ce module affirme la moitié BACKEND du contrat de l'écran (PACT10) :
l'exemple COMMITTÉ `apps/portail/contract_samples/mes_livraisons.json` est
celui que le serveur renvoie réellement, et c'est ce même fichier que le test
frontend `PortailClientLivraisons.test.jsx` IMPORTE — jamais un mock réécrit à
la main. La forme de la preuve elle-même est couverte par
`test_aud301_preuve_livraison.py` (contrat `mes_livraisons_preuve.json`).

Run :
    python manage.py test apps.portail.tests.test_aud147_lien_preuve_portail -v2
"""
import itertools
import json
import pathlib

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import (
    Installation, Livraison, LivraisonLigne, PreuveLivraison,
)
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS, ROLE_PORTAIL_CLIENT, Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

_SAMPLES = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
CONTRAT = json.loads(
    (_SAMPLES / 'mes_livraisons.json').read_text(encoding='utf-8'))
CONTRAT_PREUVE = json.loads(
    (_SAMPLES / 'mes_livraisons_preuve.json').read_text(encoding='utf-8'))


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD147-{n}',
        email=f'aud147-{company.id}-{n}@example.invalid')


def make_portal_user(company, username, scope_id):
    role, _ = Role.objects.get_or_create(
        company=company, nom=ROLE_PORTAIL_CLIENT,
        defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                  'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
    user.portail_client_id = scope_id
    user.save()
    return user


class LienPreuveLivraisonPortailTests(TestCase):
    def setUp(self):
        self.company = make_company('aud147-co-a', 'AUD147 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.inst_a = Installation.objects.create(
            company=self.company, client=self.client_a,
            reference=f'CH-AUD147-{next(_seq)}')
        self.inst_b = Installation.objects.create(
            company=self.company, client=self.client_b,
            reference=f'CH-AUD147-{next(_seq)}')
        # Une livraison AVEC preuve (le cas qui rendait un lien mort) …
        self.liv_avec = Livraison.objects.create(
            company=self.company, installation=self.inst_a,
            reference='LIV-AUD147-A', numero_suivi='AMANA-778812',
            cout_transport=500)
        LivraisonLigne.objects.create(
            livraison=self.liv_avec, designation='Panneau JA Solar 550 Wc',
            quantite=18)
        PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv_avec,
            signataire_nom='Karim Bennani',
            signature_data='data:image/png;base64,AAAA',
            note='Remis en main propre.', horodatage=timezone.now())
        # … et une livraison SANS preuve (aucun lien ne doit être proposé).
        self.liv_sans = Livraison.objects.create(
            company=self.company, installation=self.inst_a,
            reference='LIV-AUD147-SANS')
        # La livraison d'un AUTRE client de la même société.
        self.liv_autre = Livraison.objects.create(
            company=self.company, installation=self.inst_b,
            reference='LIV-AUD147-B')
        PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv_autre,
            signataire_nom='Autre', horodatage=timezone.now())

        self.user = make_portal_user(
            self.company, 'aud147-portail-a', self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _ligne(self, livraison):
        r = self.api.get('/api/django/portail/mes-livraisons/')
        self.assertEqual(r.status_code, 200, r.data)
        return next(x for x in r.data['results'] if x['id'] == livraison.id)

    # ── PACT10 : la liste servie EST la forme du contrat committé ───────────
    def test_la_liste_a_exactement_les_cles_du_contrat(self):
        attendu = set(CONTRAT['exemple']['results'][0].keys())
        r = self.api.get('/api/django/portail/mes-livraisons/')

        self.assertEqual(set(r.data.keys()), set(CONTRAT['exemple'].keys()))
        self.assertTrue(r.data['results'])
        for ligne in r.data['results']:
            self.assertEqual(set(ligne.keys()), attendu)
        # Les deux variantes du contrat décrivent le même ENSEMBLE de clés
        # (un autre ÉTAT du serveur, jamais une autre FORME).
        self.assertEqual(set(CONTRAT['exemple'].keys()),
                         set(CONTRAT['exemple_vide'].keys()))
        self.assertEqual(
            CONTRAT['endpoint'], 'GET /api/django/portail/mes-livraisons/')

    def test_les_articles_ont_exactement_les_cles_du_contrat(self):
        attendu = set(
            CONTRAT['exemple']['results'][0]['articles'][0].keys())
        ligne = self._ligne(self.liv_avec)

        self.assertTrue(ligne['articles'])
        for article in ligne['articles']:
            self.assertEqual(set(article.keys()), attendu)

    # ── Le lien n'est plus mort ────────────────────────────────────────────
    def test_le_pod_url_ne_pointe_plus_lendpoint_interne(self):
        ligne = self._ligne(self.liv_avec)

        self.assertTrue(ligne['pod_disponible'])
        self.assertNotIn('installations/preuves-livraison', ligne['pod_url'])
        self.assertEqual(
            ligne['pod_url'],
            f'/api/django/portail/mes-livraisons/{self.liv_avec.id}/preuve/')

    def test_sans_preuve_aucun_lien_nest_propose(self):
        ligne = self._ligne(self.liv_sans)

        self.assertFalse(ligne['pod_disponible'])
        self.assertIsNone(ligne['pod_url'])

    def test_le_client_ouvre_sa_preuve_depuis_le_lien_servi(self):
        """Le contrat de bout en bout : ce que la liste donne s'ouvre, et la
        charge renvoyée est celle que l'écran sait rendre."""
        ligne = self._ligne(self.liv_avec)

        r = self.api.get(ligne['pod_url'])

        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(set(r.data.keys()),
                         set(CONTRAT_PREUVE['exemple'].keys()))
        self.assertEqual(r.data['signataire_nom'], 'Karim Bennani')

    def test_la_preuve_dun_autre_client_reste_introuvable(self):
        r = self.api.get(
            f'/api/django/portail/mes-livraisons/{self.liv_autre.id}/preuve/')

        self.assertEqual(r.status_code, 404)

    def test_la_liste_ne_fuit_jamais_le_cout_de_transport(self):
        r = self.api.get('/api/django/portail/mes-livraisons/')

        self.assertNotIn('cout_transport', str(r.data))
        # Le contrat lui-même est client-safe : aucune clé de coût/prix.
        for cle in CONTRAT['exemple']['results'][0]:
            self.assertNotIn('cout', cle)
            self.assertNotIn('prix', cle)
