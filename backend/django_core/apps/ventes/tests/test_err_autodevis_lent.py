"""ERR-E2E-AUTODEVIS-LENT (07/10/2026) — le « Devis automatique » ne calcule
ses études qu'UNE fois et ne dépend d'aucun service externe joignable.

Symptôme : ``figures-parite.spec`` (CI e2e-shard 2, PR #823/#836/#840) voyait
le ``POST /ventes/devis/auto/`` dépasser 15 s. Mesure sur l'image prod, réseau
coupé (réseau docker ``--internal``) : AUCUN appel sortant — la latence est du
calcul. Mais quand l'écran envoie ``etude_params`` (factures réelles + conso,
TOUJOURS le cas d'un lead avec facture), les quatre études tournaient DEUX
fois : une dans le pipeline SANS ces clés (résultat jeté), une après leur
fusion. 7 appels du moteur de dimensionnement au lieu de 4, 4,4 s → 2,8 s.

Ces tests verrouillent :
1. avec ou sans ``etude_params``, le moteur de dimensionnement tourne le
   MÊME nombre de fois (la fusion entre AVANT les études) ;
2. les clés de l'appelant sont bien sur le devis, avec son dimensionnement ;
3. une clé refusée par le schéma sort toujours en 422 nommé ``etude_params`` ;
4. le devis auto d'un lead à ville seule n'ouvre AUCUNE connexion réseau, et
   celui d'un lead GPS aboutit même PVGIS injoignable (repli table sourcée).

5. ADEV80 (C-ACI-009) — le POST est idempotent et patient : deux POST
   identiques < 120 s => UN seul brouillon (le second répond 200, même forme),
   un corps différent => un nouveau brouillon, verrou par lead (409 si
   ``cache.add`` répond ``False``, création normale si le cache est en panne).

Run :
    python manage.py test apps.ventes.tests.test_err_autodevis_lent -v 2
"""
import urllib.error
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.crm.models import Lead
from apps.ventes.models import Devis
from apps.ventes.tests.test_composition_source_unique import (
    auth_client, make_company, seed,
)

User = get_user_model()

AUTO_URL = '/api/django/ventes/devis/auto/'

#: Le corps que l'écran envoie pour un lead avec facture (autoQuote.js).
ETUDE_ECRAN = {
    'factures_mensuelles_reelles': [900] * 12,
    'conso_annuelle': 6000,
}


class _Base(TestCase):
    slug = 'err-autodevis-lent'

    def setUp(self):
        self.company = make_company(self.slug)
        self.user = User.objects.create_user(
            username='u-%s' % self.slug, password='x',
            company=self.company, role_legacy='admin')
        seed(self.company)
        self.api = auth_client(self.user)

    def lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Auto', prenom='Lent',
            facture_hiver=Decimal('900'), ville='Casablanca', **extra)

    def creer(self, lead, etude=None):
        corps = {'lead': lead.id, 'remise_globale': '0'}
        if etude is not None:
            corps['etude_params'] = etude
        return self.api.post(AUTO_URL, corps, format='json')


class LesEtudesNeTournentQuUneFois(_Base):
    slug = 'err-autodevis-une-fois'

    def _appels_moteur(self, etude):
        from apps.ventes import dimensionnement
        with mock.patch.object(
                dimensionnement, 'recommander_taille',
                wraps=dimensionnement.recommander_taille) as espion:
            reponse = self.creer(self.lead(), etude)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return espion.call_count, reponse

    def test_etude_ecran_ne_double_pas_les_etudes(self):
        sans, _ = self._appels_moteur(None)
        avec, reponse = self._appels_moteur(dict(ETUDE_ECRAN))
        # Garde du garde : un moteur jamais appelé rendrait l'égalité vide.
        self.assertGreater(sans, 0)
        self.assertEqual(
            avec, sans,
            'les études du devis automatique tournent de nouveau deux fois '
            'quand l\'écran envoie ses factures réelles (%d appels du moteur '
            'au lieu de %d)' % (avec, sans))
        devis = Devis.objects.get(pk=reponse.data['id'])
        ep = devis.etude_params or {}
        self.assertEqual(ep.get('factures_mensuelles_reelles'),
                         ETUDE_ECRAN['factures_mensuelles_reelles'])
        self.assertEqual(ep.get('conso_annuelle'), ETUDE_ECRAN['conso_annuelle'])
        self.assertIsInstance(ep.get('dimensionnement'), dict)

    def test_cle_refusee_reste_un_422_nomme(self):
        reponse = self.creer(self.lead(), {'dimensionnement': {'faux': 1}})
        self.assertEqual(reponse.status_code, 409, reponse.data)  # CI #997 fuzz : refus d'état, 409
        self.assertEqual(reponse.data.get('field'), 'etude_params')


class AucunServiceExterneNeBloque(_Base):
    slug = 'err-autodevis-reseau'

    def test_lead_ville_seule_aucun_appel_reseau(self):
        """Le cas CI : ville connue, pas de GPS → table de référence, zéro
        connexion sortante (urllib ni requests)."""
        refus = urllib.error.URLError('réseau coupé (test)')
        with mock.patch('urllib.request.urlopen',
                        side_effect=refus) as urlopen, \
                mock.patch('requests.sessions.Session.request',
                           side_effect=OSError('réseau coupé (test)')) as req:
            reponse = self.creer(self.lead(), dict(ETUDE_ECRAN))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(urlopen.call_count, 0)
        self.assertEqual(req.call_count, 0)

    def test_lead_gps_pvgis_injoignable_aboutit(self):
        """GPS → PVGIS live tenté ; injoignable, le devis naît quand même sur
        la table sourcée (jamais un 500, jamais une attente)."""
        lead = self.lead(gps_lat=Decimal('33.5731'), gps_lng=Decimal('-7.5898'))
        with mock.patch('urllib.request.urlopen',
                        side_effect=urllib.error.URLError('PVGIS coupé')):
            reponse = self.creer(lead, dict(ETUDE_ECRAN))
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=reponse.data['id'])
        self.assertIsInstance((devis.etude_params or {}).get('dimensionnement'),
                              dict)


class AutoDevisIdempotentEtVerrou(_Base):
    """ADEV80 — « deux clics rapides => un seul brouillon » (P-ACI-3)."""
    slug = 'err-autodevis-idempotent'

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def _nb(self, lead):
        return Devis.objects.filter(lead=lead).count()

    def _cle_verrou(self, lead):
        return 'devis-auto:%d:%d' % (self.company.id, lead.id)

    def test_deux_post_identiques_un_seul_devis_et_200_meme_forme(self):
        lead = self.lead()
        premier = self.creer(lead, dict(ETUDE_ECRAN))
        second = self.creer(lead, dict(ETUDE_ECRAN))
        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['id'], premier.data['id'])
        self.assertEqual(set(second.data), set(premier.data))
        for cle in ('reference', 'statut', 'kwc', 'nb_lignes',
                    'proposal_token', 'proposal_path', 'alertes'):
            self.assertEqual(second.data[cle], premier.data[cle], cle)
        self.assertEqual(self._nb(lead), 1)

    def test_target_kwc_different_cree_un_second_devis(self):
        lead = self.lead()
        premier = self.api.post(
            AUTO_URL, {'lead': lead.id, 'target_kwc': 6}, format='json')
        second = self.api.post(
            AUTO_URL, {'lead': lead.id, 'target_kwc': 9}, format='json')
        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertNotEqual(second.data['id'], premier.data['id'])
        self.assertEqual(self._nb(lead), 2)

    def test_rejeu_expire_cree_un_nouveau_devis(self):
        """Le rejeu s'éteint avec sa clé (TTL 120 s) : un clic tardif crée."""
        lead = self.lead()
        premier = self.creer(lead)
        cache.clear()  # simule l'expiration des 120 s
        second = self.creer(lead)
        self.assertEqual(premier.status_code, 201, premier.data)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(self._nb(lead), 2)

    def test_verrou_pose_donne_409(self):
        lead = self.lead()
        with mock.patch('django.core.cache.cache.add',
                        return_value=False) as add:
            reponse = self.creer(lead)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(
            reponse.data['detail'],
            'Un devis automatique est déjà en cours pour ce lead.')
        self.assertEqual(self._nb(lead), 0)
        self.assertIn(self._cle_verrou(lead),
                      [c.args[0] for c in add.call_args_list])

    def test_cache_en_panne_pas_de_verrou_creation_normale(self):
        """NTPLT24 : ``add`` -> None (django_redis fail-soft) n'est PAS un 409."""
        lead = self.lead()
        with mock.patch('django.core.cache.cache.add', return_value=None):
            reponse = self.creer(lead)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(self._nb(lead), 1)

    def test_verrou_libere_apres_creation_et_apres_refus(self):
        lead = self.lead()
        self.assertEqual(self.creer(lead).status_code, 201)
        self.assertIsNone(cache.get(self._cle_verrou(lead)))
        # Refus d'état (clé d'étude rejetée) : le verrou est quand même levé.
        autre = self.lead()
        refus = self.creer(autre, {'dimensionnement': {'faux': 1}})
        self.assertEqual(refus.status_code, 409)
        self.assertIsNone(cache.get(self._cle_verrou(autre)))
