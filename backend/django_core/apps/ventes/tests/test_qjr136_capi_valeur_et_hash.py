"""QJR136 — la valeur de conversion Meta n'est jamais un montant connu faux.

Trois constats frères du MÊME bloc CAPI (audit du 30/08/2026) :

  · ES8 — quand ``option_totaux`` levait, le repli retombait sur
    ``Devis.total_ttc``, c'est-à-dire le TTC **BRUT** (``models.Devis`` ne
    déduit jamais ``remise_globale``) et la **SOMME des deux options**. Le
    motif brut-vs-net (QJR22/23/24) survivait dans un repli, et corrompait le
    ROAS et l'optimisation d'enchères ;
  · ES9 — le téléphone était haché **sans indicatif pays**
    (``''.join(c for c in phone_raw if c.isdigit())``) alors que la MÊME app
    expose ``utils/phone.normalize_phone_e164`` et que
    ``apps/adsengine/audiences.py`` l'utilise déjà pour Meta : l'appariement
    ``ph`` échouait systématiquement ;
  · ES13 — un devis renouvelé héritait du snapshot d'attribution de sa source
    (``_persist_attribution`` sort si la clé existe) et créditait une SECONDE
    fois le même clic, sans déduplication possible (``event_id`` porte la
    référence, qui a changé).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr136_capi_valeur_et_hash -v 2
"""
import hashlib
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.domain.cycle_vie import _fire_capi_signed_quote
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis
from authentication.models import Company

#: Le numéro tel qu'il est SAISI, et l'E.164 que Meta attend.
TELEPHONE_SAISI = '06 00 00 01 36'
TELEPHONE_E164 = '212600000136'
HASH_ATTENDU = hashlib.sha256(TELEPHONE_E164.encode()).hexdigest()

PIXEL = '1234567890'
TOKEN = 'jeton-de-test-capi'


class _CapiEnvoye:
    """Capture le payload CAPI en interceptant l'appel HTTP sortant."""

    def __init__(self):
        self.appels = []

    def __enter__(self):
        self._patch = patch('urllib.request.urlopen', side_effect=self._faux)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()
        return False

    def _faux(self, req, timeout=None):
        self.appels.append(json.loads(req.data.decode('utf-8')))
        reponse = MagicMock()
        reponse.read.return_value = b'{"events_received":1}'
        reponse.status = 200
        # ``urlopen`` est consommé par un ``with`` : le mock doit se rendre
        # lui-même en entrant dans le bloc.
        reponse.__enter__.return_value = reponse
        reponse.__exit__.return_value = False
        return reponse

    @property
    def evenement(self):
        assert self.appels, 'aucun événement CAPI envoyé'
        return self.appels[-1]['data'][0]


@override_settings(META_CAPI_ACCESS_TOKEN=TOKEN, META_CAPI_PIXEL_ID=PIXEL)
class _BaseCapi(TestCase):
    slug = 'qjr136'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR136',
            email='qjr136-%s@example.com' % self.slug,
            telephone=TELEPHONE_SAISI)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR136-%s' % self.slug[-3:],
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), remise_globale=Decimal('10'))
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 710W',
            sku='QJR136-PAN-%s' % self.company.pk,
            prix_vente=Decimal('1000'), prix_achat=Decimal('1'),
            quantite_stock=50)
        creer_ligne(self.devis, produit=produit, designation='Panneau 710W',
                    quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
                    remise=Decimal('0'))


class LeTelephoneEstHacheEnE164(_BaseCapi):
    """ES9 — l'appariement ``ph`` ne peut réussir qu'avec l'indicatif pays."""

    slug = 'qjr136-hash'

    def test_le_hash_est_celui_du_numero_e164(self):
        with _CapiEnvoye() as capi:
            _fire_capi_signed_quote(devis=self.devis)
        user_data = capi.evenement['user_data']
        self.assertEqual(user_data['ph'], [HASH_ATTENDU])
        # Le TÉMOIN : l'ancien hash (chiffres nus, sans indicatif) est
        # DIFFÉRENT — sans quoi ce test serait vert des deux côtés.
        ancien = hashlib.sha256('0600000136'.encode()).hexdigest()
        self.assertNotEqual(user_data['ph'][0], ancien)

    def test_un_numero_non_normalisable_ne_produit_aucun_hash(self):
        """Mieux vaut aucune clé ``ph`` qu'un hash que Meta n'appariera
        jamais."""
        self.client_obj.telephone = 'à rappeler'
        self.client_obj.save(update_fields=['telephone'])
        self.devis.refresh_from_db()
        with _CapiEnvoye() as capi:
            _fire_capi_signed_quote(devis=self.devis)
        self.assertNotIn('ph', capi.evenement['user_data'])


class LaValeurDeConversionNEstJamaisDevinee(_BaseCapi):
    """ES8 — plus de repli sur le TTC brut."""

    slug = 'qjr136-valeur'

    def test_la_valeur_envoyee_est_le_ttc_NET_canonique(self):
        from apps.ventes.domain.argent import Vue, totaux
        from apps.ventes.utils.options import option_totaux

        with _CapiEnvoye() as capi:
            _fire_capi_signed_quote(devis=self.devis)
        attendu = float(option_totaux(self.devis)['ttc'])
        self.assertAlmostEqual(
            capi.evenement['custom_data']['value'], attendu, places=2)
        # Le TÉMOIN : le TTC **BRUT** — remise globale JAMAIS déduite — est un
        # AUTRE nombre, et c'est lui que l'ancien repli envoyait.
        #
        # Il se NOMME désormais ``argent.Vue.BRUT`` et non plus
        # ``Devis.total_ttc`` : QJR51 / décision fondateur D2 a rebranché
        # ``Devis.total_*`` sur la vue **NET** (cf. ``models.Devis
        # ._totaux_argent``), donc ``devis.total_ttc`` EST maintenant, au bit,
        # la chaîne canonique que ce test compare — un témoin qui ne peut plus
        # que coïncider, quelle que soit la fixture. La vue BRUT, elle, reste
        # « le comportement d'hier de ``Devis.total_*``, au bit »
        # (``domain/argent._brut``).
        #
        # Dérivation sur CETTE fixture (1 ligne 10 × 1 000, TVA 20 %,
        # ``remise_globale`` = 10 %) :
        #   · BRUT : HT 10 000 + TVA 2 000            = 12 000,00
        #   · NET  : HT 10 000 − 1 000 = 9 000, TVA 1 800 = 10 800,00
        # Les deux chaînes DIVERGENT donc bien de la remise et de sa TVA.
        brut = float(totaux(self.devis, vue=Vue.BRUT).ttc)
        self.assertNotAlmostEqual(brut, attendu, places=2)

    def test_rien_n_est_envoye_quand_la_chaine_canonique_echoue(self):
        with patch('apps.ventes.utils.options.option_totaux',
                   side_effect=RuntimeError('chaîne canonique indisponible')):
            with _CapiEnvoye() as capi:
                _fire_capi_signed_quote(devis=self.devis)
        self.assertEqual(
            capi.appels, [],
            'un montant deviné est parti chez Meta : il entraîne durablement '
            "l'algorithme d'enchères.")


class LeRenouvellementNHeritePasDeLAttribution(TestCase):
    """ES13 — le patron « double application » sur le clic publicitaire."""

    slug = 'qjr136-attribution'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR136',
            email='qjr136-attr@example.com')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='QJR136',
            telephone='+212600000136')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR136-ATTR',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            etude_params={
                'scenario': 'Sans batterie',
                'attribution': {'fbclid': 'CLIC-DU-SOURCE',
                                'utm_source': 'facebook'},
            })

    def test_le_snapshot_du_source_ne_part_pas_dans_le_renouvellement(self):
        from apps.ventes.domain.cycle_vie import renouveler_devis

        nouveau = renouveler_devis(self.devis, user=None)
        self.assertNotIn('attribution', nouveau.etude_params or {})
        # La CONFIGURATION, elle, suit : seule l'attribution est retirée.
        self.assertEqual(
            (nouveau.etude_params or {}).get('scenario'), 'Sans batterie')

    def test_le_devis_source_garde_son_attribution(self):
        from apps.ventes.domain.cycle_vie import renouveler_devis

        renouveler_devis(self.devis, user=None)
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.etude_params['attribution']['fbclid'], 'CLIC-DU-SOURCE')

    def test_le_duplicata_non_plus(self):
        """Même clé, même raison : un duplicata ne recrédite pas le clic de
        son original."""
        from apps.ventes.domain.creation import dupliquer_devis

        copie = dupliquer_devis(self.devis, user=None)
        self.assertNotIn('attribution', copie.etude_params or {})
