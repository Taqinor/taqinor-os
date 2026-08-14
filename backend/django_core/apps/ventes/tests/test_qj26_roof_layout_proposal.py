"""QJ26 — Expose the roof layout in the public proposal payload.

proposal_data exposed only roof_image_url. QJ26 adds a SANITIZED roof_layout
(geometry + per-pan panel count/orientation/tilt/kWc ONLY — NEVER any price,
prix_achat, margin, or internal field), only when present; the PNG stays the
poster/fallback. No-leak, layout-less, and company-scoping covered.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qj26_roof_layout_proposal -v 2
"""
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()


def make_company(slug):
    from authentication.models import Company
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return c


def make_user(company):
    return User.objects.create_user(
        username=f'qj26_{company.slug}', password='x',
        role_legacy='responsable', company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Roof', prenom='Test',
        email=f'r_{company.slug}@ex.com', telephone='+212600000008')


def make_devis(company, user, client, reference, roof_layout=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='envoye', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, roof_layout=roof_layout)
    for desig, qty, pu in [('Onduleur réseau 8kW', '1', '14000'),
                           ('Panneau mono 550W', '10', '1400')]:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:10]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('9999'),
            quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


def sample_layout():
    return {
        'version': 1,
        'scenario': 'reseau',
        'result': {'panels': 16, 'kwc': 8.8, 'annualKwh': 14000,
                   'savings': 11000},
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
            'facingAzimuthDeg': 0, 'neededPanels': 12,
        }],
        '_pans_geometry': [{
            'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
            'inclinaison_deg': 30, 'nb_panneaux': 12, 'kwc': 6.6,
            'roof_type': 'pitched',
            # These MUST be stripped by the sanitizer:
            'prix_achat': 9999, 'marge': 0.3, 'prix_vente': 1400,
        }],
        # top-level internal field that must not leak:
        'prix_achat_total': 123456,
    }


def sample_layout_v2():
    """PV13 — le layout tel que ``serializeLayout`` l'émet en VERSION 2.

    Tout ce que la v1 portait, PLUS : ``result`` complet (dont ``savings``),
    ``scenario``, ``panelWatt``, ``battery``, ``source``, ``devisId``, et une
    ``geometry`` par zone. C'est ce blob-là qui arrive maintenant en production
    (PV13) — donc c'est sur LUI que la whitelist publique doit être épinglée,
    pas sur le blob v1 qui ne portait aucun de ces champs.
    """
    layout = sample_layout()
    layout.update({
        'version': 2,
        'panelWatt': 550,
        'battery': {'kwh': 5, 'count': 1, 'model': 'Deye 5 kWh'},
        'source': 'devis',
        'devisId': 4242,
        'pin': {'lat': 33.57, 'lng': -7.58},
        'outline': [[33.57, -7.58], [33.58, -7.58], [33.58, -7.57]],
        'billKwh': 900,
        'activeAreaId': 'z1',
    })
    # WJ24 — la POSE RÉELLE de la zone : les cellules effectivement occupées
    # (``prefill.ts``), pas les `count` premières du pavage. C'est ce bloc que
    # la proposition publique doit republier, sans quoi le client voit un
    # calepinage recalculé — donc un autre toit que celui qu'on lui a vendu.
    layout['zones'][0]['geometry'] = {
        'azimuthDeg': 0, 'tiltDeg': 30, 'family': 'south', 'flush': True,
        'kwc': 6.6, 'count': 3, 'origin': [-7.58, 33.57],
        'panels': [{'cx': 0.0, 'cy': 0.0},
                   {'cx': 1.15, 'cy': 0.0},
                   {'cx': 2.3, 'cy': 0.0, 'face': 'E'}],
    }
    return layout


class TestSafeRoofLayoutV2Whitelist(TestCase):
    """PV24 — la whitelist publique tient face au layout v2.

    Le sérialiseur v2 (PV13) ajoute une demi-douzaine de clés au blob stocké.
    ``_safe_roof_layout`` est une whitelist, donc elle DEVRAIT toutes les
    ignorer — mais « devrait » n'est pas une garantie : ce test épingle
    l'ENSEMBLE EXACT des clés publiées, de sorte qu'un futur ajout côté outil
    3D (ou un « on recopie le layout, c'est plus simple ») fasse rougir le
    gate au lieu de publier en silence un champ à sémantique de prix.
    """

    #: Les SEULES clés que la proposition publique a le droit de porter.
    CLES_PUBLIABLES = {'pans', 'zones', 'result', 'scenario'}
    #: Le résultat public est GÉOMÉTRIQUE : ni économies, ni rien de monétaire.
    CLES_RESULT_PUBLIABLES = {'panels', 'kwc', 'annualKwh'}

    def setUp(self):
        self.company = make_company('pv24-pub')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._suite = 0

    def _safe(self, layout):
        from apps.ventes.public_views import _safe_roof_layout
        self._suite += 1
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-PV24-%03d' % self._suite, roof_layout=layout)
        return _safe_roof_layout(devis)

    def test_le_jeu_de_cles_publiees_est_exactement_celui_attendu(self):
        safe = self._safe(sample_layout_v2())
        self.assertIsNotNone(safe)
        self.assertEqual(set(safe), self.CLES_PUBLIABLES)
        self.assertEqual(set(safe['result']), self.CLES_RESULT_PUBLIABLES)

    #: Les SEULES sous-clés qu'une pose publiée a le droit de porter (WJ24).
    CLES_GEOMETRY_PUBLIABLES = {'azimuthDeg', 'tiltDeg', 'kwc', 'count',
                                'family', 'flush', 'origin', 'panels'}

    def test_aucun_ajout_v2_ne_traverse_la_whitelist(self):
        safe = self._safe(sample_layout_v2())
        for ajout in ('panelWatt', 'battery', 'source', 'devisId', 'version',
                      'pin', 'outline', 'billKwh', 'activeAreaId', 'savings'):
            self.assertNotIn(ajout, json.dumps(safe),
                             'la clé v2 « %s » fuit dans la proposition '
                             'publique' % ajout)
        # WJ24 — `geometry` est désormais PUBLIÉE (le client doit voir la pose
        # réelle), mais toujours par recopie champ par champ : le jeu de
        # sous-clés est épinglé ici exactement comme le jeu de clés racines.
        pose = safe['zones'][0]['geometry']
        self.assertEqual(set(pose), self.CLES_GEOMETRY_PUBLIABLES)
        for panneau in pose['panels']:
            self.assertLessEqual(set(panneau), {'cx', 'cy', 'face'})

    def test_une_geometrie_piegee_ne_laisse_rien_passer(self):
        """La recopie est CHAMP PAR CHAMP, et c'est tout l'enjeu.

        ``roof_layout`` est le blob POST stocké TEL QUEL : republier
        ``zone.geometry`` en bloc reviendrait à republier ce qu'on y aurait
        glissé. On y niche donc ici tout ce qui ne doit jamais sortir.
        """
        layout = sample_layout_v2()
        layout['zones'][0]['geometry'].update({
            'prix_achat': 9999, 'marge': 0.42, 'prix_vente': 1400,
            'note_interne': 'remise max 12 %', 'cout_pose': 3200,
        })
        layout['zones'][0]['geometry']['panels'][0].update({
            'prix_achat': 777, 'marge': 0.9})

        safe = self._safe(layout)
        pose = safe['zones'][0]['geometry']
        self.assertEqual(set(pose), self.CLES_GEOMETRY_PUBLIABLES)
        self.assertEqual(set(pose['panels'][0]), {'cx', 'cy'})
        blob = json.dumps(safe)
        for fuite in ('prix_achat', 'marge', 'prix_vente', 'note_interne',
                      'cout_pose', '9999', '777', '3200', '0.42'):
            self.assertNotIn(fuite, blob,
                             '« %s » fuit par zone.geometry' % fuite)

    def test_les_valeurs_exotiques_sont_jetees(self):
        """Typage STRICT : une coordonnée n'est jamais une chaîne ni un bool."""
        layout = sample_layout_v2()
        layout['zones'][0]['geometry'] = {
            'azimuthDeg': 'plein sud', 'tiltDeg': None, 'kwc': True,
            'family': 'portrait', 'flush': 'oui', 'count': 12,
            'origin': [0, 0, 0],
            'panels': [{'cx': 1.0, 'cy': 'gauche'}, 'pas un dict',
                       {'cx': 2.0, 'cy': 3.0, 'face': 'Z'}],
        }
        pose = self._safe(layout)['zones'][0]['geometry']
        self.assertEqual(set(pose), {'count', 'panels'})
        self.assertEqual(pose['panels'], [{'cx': 2.0, 'cy': 3.0}])

    def test_la_liste_de_panneaux_est_bornee(self):
        from apps.ventes.public_views import _MAX_PANNEAUX_PUBLIES
        layout = sample_layout_v2()
        layout['zones'][0]['geometry']['panels'] = [
            {'cx': float(i), 'cy': 0.0}
            for i in range(_MAX_PANNEAUX_PUBLIES + 250)]
        pose = self._safe(layout)['zones'][0]['geometry']
        self.assertEqual(len(pose['panels']), _MAX_PANNEAUX_PUBLIES)

    def test_une_geometrie_absente_ne_publie_aucune_cle(self):
        """Layout v1 (aucune pose) : la clé n'apparaît simplement pas."""
        safe = self._safe(sample_layout())
        self.assertNotIn('geometry', safe['zones'][0])

    def test_les_economies_restent_hors_de_la_proposition(self):
        """``result.savings`` porte une sémantique de PRIX : jamais publié."""
        layout = sample_layout_v2()
        self.assertIn('savings', layout['result'])   # présent à la source…
        safe = self._safe(layout)
        self.assertNotIn('savings', safe['result'])  # …absent à la sortie.
        self.assertNotIn('11000', json.dumps(safe))

    def test_la_v2_n_ajoute_que_la_pose_reelle(self):
        """WJ24 — le SEUL ajout publiable de la v2 est ``zones[].geometry``.

        (Avant WJ24 les deux sorties étaient identiques, et c'était le bug : la
        pose réelle restait à quai, donc le lien client re-calculait un
        calepinage au lieu de montrer celui qui a été vendu.)
        """
        v1 = self._safe(sample_layout())
        v2 = self._safe(sample_layout_v2())

        self.assertEqual(set(v1), set(v2))
        self.assertEqual(v1['pans'], v2['pans'])
        self.assertEqual(v1['result'], v2['result'])
        self.assertEqual(v1['scenario'], v2['scenario'])

        pose = v2['zones'][0].pop('geometry')
        self.assertEqual(json.dumps(v1['zones'], sort_keys=True),
                         json.dumps(v2['zones'], sort_keys=True))
        self.assertEqual(pose['count'], 3)
        self.assertEqual(len(pose['panels']), 3)
        self.assertEqual(pose['origin'], [-7.58, 33.57])


class TestSafeRoofLayoutSanitizer(TestCase):
    def setUp(self):
        self.company = make_company('qj26-san')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_sanitized_layout_geometry_only(self):
        from apps.ventes.public_views import _safe_roof_layout
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-1', roof_layout=sample_layout())
        safe = _safe_roof_layout(devis)
        self.assertIsNotNone(safe)
        pan = safe['pans'][0]
        self.assertEqual(pan['orientation'], 'Sud')
        self.assertEqual(pan['azimut_deg'], 0)
        self.assertEqual(pan['inclinaison_deg'], 30)
        self.assertEqual(pan['nb_panneaux'], 12)
        self.assertEqual(pan['kwc'], 6.6)
        # geometry totals present, but savings/price absent
        self.assertIn('kwc', safe['result'])
        self.assertNotIn('savings', safe['result'])
        # NO price / margin / internal key anywhere in the JSON
        blob = json.dumps(safe)
        for leak in ('prix_achat', 'marge', 'prix_vente', '9999', '123456',
                     'savings'):
            self.assertNotIn(leak, blob)

    def test_no_layout_returns_none(self):
        from apps.ventes.public_views import _safe_roof_layout
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-NONE', roof_layout=None)
        self.assertIsNone(_safe_roof_layout(devis))


class TestProposalRoofLayoutPayload(TestCase):
    def setUp(self):
        self.company = make_company('qj26-ep')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _get_payload(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token)
        c = DjangoClient()
        return c.get(f'/api/django/public/proposal/{token}/data/')

    def test_payload_has_sanitized_roof_layout(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-EP', roof_layout=sample_layout())
        resp = self._get_payload(devis)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn('roof_layout', payload)
        self.assertIsNotNone(payload['roof_layout'])
        blob = json.dumps(payload['roof_layout'])
        for leak in ('prix_achat', 'marge', '9999', '123456'):
            self.assertNotIn(leak, blob)

    def test_layoutless_proposal_omits_roof_layout(self):
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-EP2', roof_layout=None)
        resp = self._get_payload(devis)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIsNone(payload['roof_layout'])

    def test_full_payload_never_leaks_buy_price(self):
        """The whole proposal payload must never contain the reseller buy price
        (9999) that is set on the products' prix_achat."""
        devis = make_devis(self.company, self.user, self.client_obj,
                           'DEV-QJ26-LEAK', roof_layout=sample_layout())
        resp = self._get_payload(devis)
        raw = json.dumps(resp.json())
        # Le prix d'achat (9999) ne doit jamais apparaître comme VALEUR AUTONOME.
        # On borne le motif (aucun chiffre/point adjacent) : « 9999 » en
        # sous-chaîne d'un montant client LÉGITIME — ex. un cashflow 25 ans
        # « 399991 » (QX39) — n'est PAS une fuite du prix d'achat.
        self.assertNotRegex(
            raw, r'(?<![\d.])9999(?![\d.])',
            "prix d'achat 9999 fuité comme valeur autonome dans la charge utile")
        self.assertNotIn('prix_achat', raw)


class TestRoofLayoutCompanyScoping(TestCase):
    def test_token_only_reads_its_own_company_layout(self):
        """A token bound to company A's devis returns A's layout; company B's
        devis+layout are unreachable through it (token is single-devis-scoped)."""
        co_a = make_company('qj26-a')
        co_b = make_company('qj26-b')
        ua, ub = make_user(co_a), make_user(co_b)
        ca, cb = make_client(co_a), make_client(co_b)
        da = make_devis(co_a, ua, ca, 'DEV-QJ26-A', roof_layout=sample_layout())
        make_devis(co_b, ub, cb, 'DEV-QJ26-B', roof_layout=sample_layout())
        token = str(uuid.uuid4())
        ShareLink.objects.create(company=co_a, devis=da, token=token)
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['reference'], 'DEV-QJ26-A')
