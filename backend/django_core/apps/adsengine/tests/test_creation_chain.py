"""PUB131 — Harnais d'intégration « PREMIÈRE CHAÎNE DE CRÉATION ».

Toute la classe de défauts du groupe PUB-P8 tient en une phrase : la chaîne
n'avait JAMAIS été exercée bout-en-bout. Chaque maillon avait son test unitaire,
et pourtant le payload ROTATE_CREATIVE partait creux, le FlightRunner créait des
coquilles sans ad, et ``dco.py`` n'avait aucun appelant. Ce module déroule les
TROIS chemins RÉELS de bout en bout, transport Meta MOCKÉ (``httpx.MockTransport``
sur le VRAI ``MetaClient`` — jamais un faux client qui accepterait n'importe
quoi), et ASSERTE les payloads Graph FINAUX :

  (a) DUPLICATE du gagnant — PUB116 (``winner_duplicate``) → ``propose_duplicate``
      → approbation → ``duplicate_adset_with_ad`` : 2 appels Graph (adset puis ad
      qui réutilise le créatif LIVE) ;
  (b) ROTATION depuis le BACKLOG — table de faits PUBLIÉE → variante ancrée
      (backend LLM mocké, PUB124/125) → approbation humaine (lot + check-list
      policy) → média uploadé au COMPTE (PUB122) → ``run_weekly`` matérialise
      (PUB120) un ROTATE_CREATIVE au payload COMPLET (PUB119) dont le créatif
      vient du PONT (PUB123) → approbation → dispatch ;
  (c) DCO recombiné — PUB118 : moisson des miroirs gagnants → spec plafonnée →
      approbation → ad à ``asset_feed_spec`` INLINE (PUB117).

Et deux GARDES STATIQUES, sur la seule surface qui parle à Graph
(``meta_client.py``) :

  * « aucun chemin d'unpause » — aucun statut littéral autre que ``PAUSED``,
    aucune méthode de réactivation, aucune méthode qui ACCEPTE un ``status`` ;
  * « le maillon PAUSED est présent » — chaque créateur d'objet de DIFFUSION
    passe par ``_forced_status_payload`` (ou délègue à un créateur qui le fait).

Les deux gardes sont des FONCTIONS pures appliquées à du TEXTE : leur pouvoir de
détection est prouvé sur des injections temporaires (une garde qui ne détecte
rien passerait au vert sur un dépôt cassé), et l'état du dépôt est asserté
séparément — zéro occurrence aujourd'hui, et ce compteur ne peut que rester à
zéro.
"""
import datetime
import json
import re
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs

import httpx
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import creative_factory, dco, policy as policy_mod
from apps.adsengine import meta_client as mc
from apps.adsengine import recombine, rules_engine, services, tasks
from apps.adsengine.flightrunner import FlightRunner
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, ArmDailyStat,
    CreativeBacklogItem, CreativeGenerationBatch, DecisionLog, EngineAction,
    Experiment, ExperimentArm, FactEntry, FactTable, FlightPlan,
    GuardrailConfig, InsightSnapshot, MetaConnection, RulePolicy,
)

User = get_user_model()

# Lundi (jour d'évaluation de la rotation — ``rotation.is_rotation_day``), le
# même repère que les tests PUB120 : la chaîne (b) passe par ``run_weekly``.
MONDAY = datetime.date(2026, 7, 13)

META_CLIENT_PATH = (
    Path(__file__).resolve().parent.parent / 'meta_client.py')


# ═════════════════════════════════════════════════════════════════════════════
# GARDES STATIQUES — fonctions PURES sur du texte (testables par injection)
# ═════════════════════════════════════════════════════════════════════════════
# Un statut littéral autre que PAUSED posé dans un payload : ``{'status': 'ACTIVE'}``,
# ``payload['status'] = 'ACTIVE'``, ``status='ACTIVE'``. L'écriture LÉGITIME
# (``payload['status'] = FORCED_STATUS``) vise un NOM, jamais un littéral.
_RX_STATUT_LITTERAL = re.compile(
    r"""(?:(['"])status\1\s*\]?\s*[:=]|\bstatus\s*=)\s*(['"])(?!PAUSED\2)""")
# Le mot ACTIVE entre guillemets n'a rien à faire dans le transport Graph.
_RX_ACTIVE_LITTERAL = re.compile(r"""(['"])ACTIVE\1""")
# Une méthode dont le NOM promet une réactivation.
_RX_METHODE_REACTIVATION = re.compile(
    r"^\s*def\s+\w*(?:unpause|un_pause|depause|resume|reactivate|set_active"
    r"|activate)\w*\s*\(", re.IGNORECASE)
# Une signature de méthode qui ACCEPTE un ``status`` (le rendrait paramétrable).
_RX_SIGNATURE_STATUS = re.compile(
    r"^[ \t]*def\s+\w+\s*\((?:[^()]|\([^()]*\))*\)", re.MULTILINE)

UNPAUSE_GUARD_RULES = (
    ('statut_litteral_non_paused', _RX_STATUT_LITTERAL),
    ('active_litteral', _RX_ACTIVE_LITTERAL),
    ('methode_de_reactivation', _RX_METHODE_REACTIVATION),
)


def scan_unpause_paths(text):
    """PUB131 — Cherche tout chemin d'UNPAUSE dans du code de transport Graph.

    Renvoie une liste de ``(règle, numéro de ligne, ligne)``. Fonction PURE :
    elle s'applique au fichier RÉEL comme à une injection de test — c'est la
    seule façon de prouver qu'elle détecte quelque chose."""
    findings = []
    for num, line in enumerate(text.splitlines(), 1):
        for name, rx in UNPAUSE_GUARD_RULES:
            if rx.search(line):
                findings.append((name, num, line.strip()))
    for match in _RX_SIGNATURE_STATUS.finditer(text):
        if re.search(r'\bstatus\b', match.group(0)):
            num = text[:match.start()].count('\n') + 1
            findings.append(('signature_avec_status', num,
                             ' '.join(match.group(0).split())[:120]))
    return findings


# Créateurs d'objets de DIFFUSION (campagne / ad set / ad) : chacun DOIT forcer
# PAUSED. Les autres ``create_*`` du client (post de Page, conteneur IG,
# audience, étude A/B, adcreative, médias de compte) ne créent PAS d'objet de
# diffusion — ils n'ont pas de champ ``status`` et retirent tout statut glissé.
DELIVERY_CREATORS = (
    'create_campaign',
    'create_adset',
    'create_ad',
    'create_ad_with_object_story_spec',
    'create_ad_with_asset_feed_spec',
    'update_status_paused',
)
# Un créateur COMPOSITE n'appelle pas ``_forced_status_payload`` lui-même : il
# délègue aux créateurs élémentaires (qui, eux, le font).
COMPOSITE_CREATORS = {
    'duplicate_adset_with_ad': ('self.create_adset(', 'self.create_ad('),
}


def method_bodies(text):
    """``{nom de méthode: corps}`` pour toutes les ``def`` d'un module.

    Découpage par la prochaine ``def``/``class`` de même indentation ou moins —
    suffisant et déterministe pour un garde de présence de maillon."""
    bodies = {}
    starts = [(m.start(), m.group(1), m.group(2))
              for m in re.finditer(r"^([ \t]*)def\s+(\w+)\s*\(", text,
                                   re.MULTILINE)]
    for index, (pos, indent, name) in enumerate(starts):
        end = len(text)
        for next_pos, next_indent, _ in starts[index + 1:]:
            if len(next_indent) <= len(indent):
                end = next_pos
                break
        bodies[name] = text[pos:end]
    return bodies


def missing_paused_links(text):
    """PUB131 — Créateurs de diffusion qui NE passent plus par le maillon PAUSED.

    Renvoie la liste des noms fautifs (vide = chaîne intacte). Retirer la ligne
    ``_forced_status_payload`` d'un créateur — ou sa délégation dans le chemin
    duplicate — fait apparaître son nom ici : c'est la preuve que le garde
    détecte la SUPPRESSION d'un maillon, pas seulement un ajout suspect."""
    bodies = method_bodies(text)
    missing = []
    for name in DELIVERY_CREATORS:
        body = bodies.get(name)
        if body is None:
            missing.append(name)
        elif '_forced_status_payload(' not in body:
            missing.append(name)
    for name, required in COMPOSITE_CREATORS.items():
        body = bodies.get(name)
        if body is None or not all(token in body for token in required):
            missing.append(name)
    return missing


class UnpauseGuardTests(SimpleTestCase):
    """Le garde « aucun chemin d'unpause » — pouvoir de détection PROUVÉ."""

    INJECTIONS = (
        "        payload['status'] = 'ACTIVE'",
        "        body = {'status': 'ACTIVE'}",
        "        return self._request('POST', obj, data={'status': 'ACTIVE'})",
        "        payload.update(status='ACTIVE')",
        "    def unpause_campaign(self, *, campaign_id):",
        "    def resume_delivery(self, *, ad_id):",
        "    def update_status(self, *, object_id, status):",
    )

    def test_the_guard_flags_every_injected_unpause_path(self):
        for injection in self.INJECTIONS:
            with self.subTest(injection=injection.strip()):
                self.assertTrue(
                    scan_unpause_paths(injection),
                    f"garde aveugle sur : {injection.strip()}")

    def test_the_guard_accepts_the_legitimate_forced_paused_writing(self):
        legit = (
            "        payload['status'] = FORCED_STATUS  # mot final\n"
            "        extras.pop('status', None)\n"
            "        if key == 'status':\n"
            "    def update_status_paused(self, *, object_id, level=None):\n"
            "        base = {'status': 'PAUSED'}\n")
        self.assertEqual(scan_unpause_paths(legit), [])

    def test_the_real_graph_transport_has_no_unpause_path(self):
        text = META_CLIENT_PATH.read_text(encoding='utf-8')
        findings = scan_unpause_paths(text)
        # Zéro aujourd'hui — et ce compteur ne peut que RESTER à zéro : toute
        # nouvelle occurrence rougit ce test avec sa ligne exacte.
        self.assertEqual(findings, [], f'chemins suspects : {findings}')

    def test_forced_status_is_hardcoded_to_paused(self):
        self.assertEqual(mc.FORCED_STATUS, 'PAUSED')

    def test_no_client_method_accepts_a_status_argument(self):
        # La garantie du LANGAGE (kwargs-only) : passer ``status`` lève TypeError.
        client = mc.MetaClient(access_token='tok', ad_account_id='act_1')
        for method, kwargs in (
                (client.create_campaign, {'name': 'x', 'objective': 'LEADS'}),
                (client.create_adset, {'name': 'x', 'campaign_id': 'c'}),
                (client.create_ad, {'name': 'x', 'adset_id': 'a'}),
                (client.update_status_paused, {'object_id': 'o'}),
        ):
            with self.subTest(method=method.__name__):
                with self.assertRaises(TypeError):
                    method(status='ACTIVE', **kwargs)


class PausedLinkPresenceGuardTests(SimpleTestCase):
    """Le garde « le maillon PAUSED est présent » — suppression ⇒ ROUGE."""

    def test_the_guard_flags_a_deleted_forced_status_link(self):
        text = META_CLIENT_PATH.read_text(encoding='utf-8')
        # Suppression VOLONTAIRE du maillon dans ``create_ad`` (en mémoire, le
        # fichier n'est pas touché) : le garde doit nommer la méthode.
        broken = text.replace(
            "    def create_ad(self, *, name, adset_id, extra_fields=None):\n"
            '        """Crée une ad — TOUJOURS PAUSED (aucun ``status`` '
            'acceptable)."""\n'
            "        base = {'name': name, 'adset_id': adset_id}\n"
            "        payload = self._forced_status_payload(base, extra_fields)",
            "    def create_ad(self, *, name, adset_id, extra_fields=None):\n"
            '        """Crée une ad."""\n'
            "        base = {'name': name, 'adset_id': adset_id}\n"
            "        payload = dict(base)")
        self.assertNotEqual(broken, text,
                            'le motif de suppression ne correspond plus au '
                            'code : mettre le garde à jour, pas le contourner')
        self.assertIn('create_ad', missing_paused_links(broken))

    def test_the_guard_flags_a_broken_duplicate_delegation(self):
        text = META_CLIENT_PATH.read_text(encoding='utf-8')
        broken = text.replace('        ad = self.create_ad(\n',
                              '        ad = self._request(\n')
        self.assertNotEqual(broken, text)
        self.assertIn('duplicate_adset_with_ad', missing_paused_links(broken))

    def test_every_delivery_creator_still_carries_the_paused_link(self):
        text = META_CLIENT_PATH.read_text(encoding='utf-8')
        self.assertEqual(missing_paused_links(text), [])


# ═════════════════════════════════════════════════════════════════════════════
# CHAÎNES RÉELLES — transport Meta mocké sur le VRAI client
# ═════════════════════════════════════════════════════════════════════════════
class ChainBase(TestCase):
    """Fixtures communes + assertions sur les payloads Graph FINAUX."""

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(
            nom='Chaîne Co', slug=self.slug)
        self.user = User.objects.create_user(
            username=f'{self.slug}-op', password='x', company=self.company,
            role_legacy='normal')
        self.connection = MetaConnection.objects.create(
            company=self.company, ad_account_id='act_1', page_id='page-42',
            enabled=True, credentials={'access_token': 'tok'})
        self.requests = []

    def tearDown(self):
        cache.clear()

    # ── Transport Graph mocké (le VRAI MetaClient au-dessus) ────────────────
    def _graph_client(self):
        def handler(request):
            self.requests.append(request)
            path = request.url.path
            if path.endswith('/adsets'):
                return httpx.Response(200, json={'id': 'as-new-1'})
            if path.endswith('/ads'):
                return httpx.Response(200, json={'id': 'ad-new-1'})
            if path.endswith('/adimages'):
                return httpx.Response(200, json={
                    'images': {'bytes': {'hash': 'hash-genere-1'}}})
            return httpx.Response(200, json={'id': 'obj-1'})

        return mc.MetaClient(
            access_token='tok', ad_account_id='act_1',
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=0, backoff_base=0)

    def _posts(self, edge):
        """Corps décodés des POST envoyés sur une edge Graph donnée."""
        return [parse_qs(r.content.decode('utf-8'))
                for r in self.requests
                if r.method == 'POST' and r.url.path.endswith(f'/{edge}')]

    def _approve(self, action):
        """Approbation HUMAINE de l'action (le geste de l'écran Approbations)."""
        EngineAction.objects.filter(pk=action.pk).update(
            status=EngineAction.Statut.APPROUVEE, approved_by=self.user)
        action.refresh_from_db()
        return action

    def _assert_born_paused(self, body):
        """Tout objet de diffusion naît PAUSED — invariant permanent règle #3."""
        self.assertEqual(body.get('status'), ['PAUSED'])

    def _assert_no_request_ever_activates(self):
        """AUCUN corps envoyé à Graph ne porte un statut d'activation."""
        for request in self.requests:
            raw = request.content.decode('utf-8')
            self.assertNotIn('ACTIVE', raw.upper().replace('%22', ''))

    def _snap(self, obj, *, day, spend, results, impressions=None):
        ct = ContentType.objects.get_for_model(type(obj))
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=obj.pk,
            date=MONDAY - datetime.timedelta(days=day),
            spend=str(spend), results=results, impressions=impressions)


class ChaineDuplicateGagnantTests(ChainBase):
    """(a) PUB116 → ``propose_duplicate`` → ``duplicate_adset_with_ad``."""

    slug = 'chaine-a'

    def setUp(self):
        super().setUp()
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='CAMP', status='ACTIVE')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='WINNER',
            status='ACTIVE', campaign=self.campaign, budget='10000')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad1', name='AD-A', status='ACTIVE',
            adset=self.adset)
        AdCreativeMirror.objects.create(
            company=self.company, ad=self.ad, creative_meta_id='cr1')
        # Gagnant NET : CPL court (3 j) 1,0 < CPL long (7 j) 2,0, volume 50.
        for day in (0, 1, 2):
            self._snap(self.adset, day=day, spend=10, results=10)
        for day in (3, 4, 5, 6):
            self._snap(self.adset, day=day, spend=17.5, results=5)
        RulePolicy.objects.create(
            company=self.company, template_key='winner_duplicate',
            enabled=True, dry_run=False, mode=RulePolicy.Mode.PROPOSE)

    def test_winner_to_graph_end_to_end(self):
        # 1) Le moteur PROPOSE (jamais n'applique).
        rules_engine.evaluate_company(self.company, now=MONDAY)
        action = EngineAction.objects.get(
            company=self.company, kind=services.KIND_DUPLICATE)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.payload['creative_id'], 'cr1')
        self.assertEqual(self.requests, [])  # zéro réseau avant approbation

        # 2) Approbation humaine, puis application sur le transport mocké.
        services.apply_action(self._approve(action),
                              client=self._graph_client())
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

        # 3) Payloads Graph FINAUX : l'ad set PUIS l'ad qui le rejoint.
        adsets = self._posts('adsets')
        ads = self._posts('ads')
        self.assertEqual(len(adsets), 1)
        self.assertEqual(len(ads), 1)
        self.assertEqual(adsets[0]['name'], ['WINNER (copie)'])
        self.assertEqual(adsets[0]['campaign_id'], ['c1'])
        self.assertEqual(adsets[0]['daily_budget'], ['10000'])
        self._assert_born_paused(adsets[0])
        self.assertEqual(ads[0]['name'], ['AD-A (copie)'])
        # L'ad rejoint l'ad set RÉELLEMENT créé (l'id vient de la réponse Graph).
        self.assertEqual(ads[0]['adset_id'], ['as-new-1'])
        self.assertEqual(json.loads(ads[0]['creative'][0]),
                         {'creative_id': 'cr1'})
        self._assert_born_paused(ads[0])
        self._assert_no_request_ever_activates()


class ChaineRotationBacklogTests(ChainBase):
    """(b) fait publié → variante ancrée (LLM mocké) → approbation → média
    uploadé → ``run_weekly`` (PUB120) → payload complet (PUB119 + pont PUB123)
    → dispatch."""

    slug = 'chaine-b'

    def setUp(self):
        super().setUp()
        GuardrailConfig.objects.create(company=self.company)
        self.plan = FlightPlan.objects.create(
            company=self.company, name='Plan chaîne',
            status=FlightPlan.Statut.ACTIF)
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-1', name='Solaire',
            status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-1', name='Toit Casa',
            status='PAUSED', campaign=self.campaign)
        self.experiment = Experiment.objects.create(
            company=self.company, name='Accroche facture',
            status=Experiment.Statut.EN_COURS, campaign=self.campaign)
        self.weak_ad = self._ad_with_creative('ad-weak', 'cr-weak')
        self.strong_ad = self._ad_with_creative('ad-strong', 'cr-strong')
        self.weak_arm = self._arm('faible', self.weak_ad.meta_id)
        self.strong_arm = self._arm('fort', self.strong_ad.meta_id)

    # ── Fixtures de rotation (mêmes conditions structurelles que PUB120) ────
    def _ad_with_creative(self, meta_id, creative_id):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=meta_id, adset=self.adset,
            name=meta_id)
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id=creative_id,
            link_url='https://taqinor.ma/devis')
        return ad

    def _arm(self, label, ad_id, *, days=14, impressions=400):
        arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.experiment, label=label,
            ad_id=ad_id)
        for offset in range(days):
            ArmDailyStat.objects.create(
                company=self.company, arm=arm,
                date=MONDAY - datetime.timedelta(days=offset),
                impressions=impressions, conversations=1, spend='10.00')
        return arm

    def _log_prob_best(self, mapping):
        return DecisionLog.objects.create(
            company=self.company, experiment=self.experiment,
            inputs={}, posteriors={},
            allocations={'prob_best': mapping},
            summary_fr='Repondération de la chaîne.')

    def _runner(self, *, today=MONDAY):
        return FlightRunner(self.plan, clock=lambda: today)

    def _make_weak_two_weeks(self):
        """Amène le bras faible à 2 semaines FAIBLES consécutives (la série
        avance d'un cran par semaine ÉVALUÉE).

        On évalue la semaine précédente par ``_rotation_snapshots`` — le seul
        geste dont la série a besoin — et NON par un ``run_weekly`` complet : une
        boucle entière matérialiserait déjà une ENTRÉE cette semaine-là (2 bras
        vivants sur ``ADS_PER_ADSET``=3 laissent un slot libre), consommant l'item
        de backlog une semaine AVANT la rotation que ce test observe."""
        self._log_prob_best({'faible': 0.05, 'fort': 0.95})
        previous = MONDAY - datetime.timedelta(days=7)
        self._runner(today=previous)._rotation_snapshots(
            self.experiment, today=previous)

    # ── Maillon 1 : un FAIT publié ──────────────────────────────────────────
    def _publish_facts(self):
        table = FactTable.create_draft(self.company)
        FactEntry.objects.create(
            table=table, company=self.company, cle='autoconsommation',
            valeur='82', unite='%', source='RedaSolar',
            verifie_le=datetime.date(2026, 1, 1))
        table.publish()
        return table

    # ── Maillon 2 : une variante ANCRÉE produite par le backend LLM mocké ───
    def _generate_grounded_asset(self):
        content = json.dumps({'variants': [{
            'hook_text': "Jusqu'à 82 % d'autoconsommation",
            'primary_text': 'Vos factures baissent, chiffres vérifiés.',
            'cta': 'LEARN_MORE', 'hook_tag': 'FACTURE',
            'claims': [{'fact_key': 'autoconsommation'}],
        }]})
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            'choices': [{'message': {'content': content}}]}
        env = {'ADSENGINE_GEN_API_KEY': 'k', 'GROQ_API_KEY': ''}
        with mock.patch.dict('os.environ', env):
            with mock.patch('requests.post', return_value=response):
                report = tasks._run_grounded_generation(
                    self.company, 'panneaux solaires économies maison sud')
        self.assertTrue(report['enabled'])
        self.assertEqual(report['assets'], 1)
        self.assertEqual(report['rejected'], 0)
        from apps.adsengine.models import CreativeAsset
        asset = CreativeAsset.objects.get(company=self.company)
        # L'IA produit un ASSET, jamais une décision : zéro EngineAction ici.
        self.assertFalse(EngineAction.objects.filter(
            company=self.company).exists())
        self.assertTrue(asset.ai_generated)      # étiquette IA (PUB126)
        self.assertFalse(asset.is_policy_passed)  # PENDING : rien n'est validé
        return asset

    # ── Maillon 3 : l'approbation HUMAINE (lot + check-list policy) ─────────
    def _approve_asset(self, asset):
        batch = CreativeGenerationBatch.objects.get(company=self.company)
        recombine.approve_lot(batch, user=self.user)
        confirmed = [rule['key'] for rule
                     in policy_mod.build_checklist(self.company)['forbidden']]
        policy_mod.record_policy_check(
            asset, confirmed_keys=confirmed, checked_by=self.user)
        asset.refresh_from_db()
        self.assertTrue(asset.is_policy_passed)
        item = CreativeBacklogItem.objects.get(
            company=self.company, asset=asset)
        self.assertEqual(item.status, CreativeBacklogItem.Statut.EN_FILE)
        return item

    def test_published_fact_to_dispatched_rotation_end_to_end(self):
        self._publish_facts()
        asset = self._generate_grounded_asset()
        item = self._approve_asset(asset)

        # ── Maillon 4 : le média part au COMPTE publicitaire (PUB122) ───────
        client = self._graph_client()
        upload = creative_factory.upload_asset_to_account(
            self.company, asset, client=client,
            media_url='https://minio.local/presigne.jpg')
        self.assertTrue(upload['uploaded'], upload['message'])
        asset.refresh_from_db()
        self.assertEqual(asset.meta_image_hash, 'hash-genere-1')
        # Un média de compte ne porte JAMAIS de statut (il ne diffuse rien).
        self.assertNotIn('status', self._posts('adimages')[0])

        # ── Maillon 5 : ``run_weekly`` MATÉRIALISE la rotation (PUB120) ─────
        self._make_weak_two_weeks()
        report = self._runner().run_weekly()
        self.assertEqual(report['rotation_proposals']['rotations'], 1)

        rotate = EngineAction.objects.get(
            company=self.company, kind=EngineAction.Kind.ROTATE_CREATIVE)
        self.assertEqual(rotate.status, EngineAction.Statut.PROPOSEE)
        # PUB119 — les TROIS pièces sont résolues à la proposition.
        self.assertEqual(rotate.payload['adset_id'], 'as-1')
        self.assertTrue(rotate.payload['name'])
        # PUB123 — le créatif vient du PONT (l'asset du backlog gagne sur le
        # créatif LIVE de repli), avec la Page de la connexion et le hash de
        # COMPTE — jamais une clé de stockage interne.
        story = rotate.payload['creative']['object_story_spec']
        self.assertEqual(story['page_id'], 'page-42')
        self.assertEqual(story['link_data']['image_hash'], 'hash-genere-1')
        self.assertEqual(story['link_data']['link'],
                         'https://taqinor.ma/devis')
        self.assertEqual(rotate.payload['creative_asset_id'], asset.pk)
        self.assertEqual(rotate.payload['backlog_item_id'], item.pk)
        self.assertTrue(rotate.payload['ai_generated'])
        # L'item consommé quitte la file libre.
        item.refresh_from_db()
        self.assertEqual(item.status, CreativeBacklogItem.Statut.PROGRAMME)

        # ── Maillon 6 : approbation puis dispatch → payload Graph FINAL ─────
        before = len(self._posts('ads'))
        services.apply_action(self._approve(rotate), client=client)
        rotate.refresh_from_db()
        self.assertEqual(rotate.status, EngineAction.Statut.APPLIQUEE)

        ads = self._posts('ads')
        self.assertEqual(len(ads), before + 1)
        body = ads[-1]
        self.assertEqual(body['adset_id'], ['as-1'])
        self.assertTrue(body['name'][0])
        creative = json.loads(body['creative'][0])
        self.assertEqual(creative['object_story_spec']['page_id'], 'page-42')
        self.assertEqual(
            creative['object_story_spec']['link_data']['image_hash'],
            'hash-genere-1')
        self._assert_born_paused(body)
        self._assert_no_request_ever_activates()


class ChaineDcoRecombineeTests(ChainBase):
    """(c) PUB118 — moisson des miroirs gagnants → spec plafonnée → ad à
    ``asset_feed_spec`` INLINE (PUB117)."""

    slug = 'chaine-c'

    def setUp(self):
        super().setUp()
        self.source_campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-src', name='Solaire',
            status='PAUSED')
        self.source_adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as-src', name='Gagnants',
            status='PAUSED', campaign=self.source_campaign)
        self.target = AdSetMirror.objects.create(
            company=self.company, meta_id='as-new', name='Nouveau',
            status='PAUSED', campaign=self.source_campaign)
        self._winner(1)

    def _winner(self, idx, *, results=5, impressions=1000):
        ad = AdMirror.objects.create(
            company=self.company, meta_id=f'ad-{idx}', name=f'Ad {idx}',
            adset=self.source_adset)
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id=f'cr-{idx}',
            image_hash=f'hash-{idx}', title=f'Titre {idx}',
            body=f'Corps {idx}', description=f'Desc {idx}',
            cta_type='LEARN_MORE', link_url='https://taqinor.ma')
        self._snap(ad, day=0, spend=30, results=results,
                   impressions=impressions)
        return ad

    def test_dco_recombination_end_to_end(self):
        action = services.propose_dco_recombination(
            self.company, adset=self.target, now=MONDAY)
        self.assertEqual(action.kind, EngineAction.Kind.CREATE_AD)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        spec = action.payload['asset_feed_spec']
        # La spec est bâtie UNIQUEMENT d'assets déjà mirorés (zéro clé externe).
        self.assertEqual([img['hash'] for img in spec['images']], ['hash-1'])
        # Plafonds DCO respectés (la source de vérité des plafonds, pas un
        # nombre recopié ici).
        self.assertLessEqual(len(spec['images']), dco.DCO_MAX_IMAGES)
        self.assertLessEqual(len(spec['bodies']), dco.DCO_MAX_BODIES)
        self.assertEqual(spec['ad_formats'], [dco.AD_FORMAT_IMAGE])
        # PUB-P8/C2 — la chaîne (c) déclare la Page qui publie, exactement comme
        # (a) et (b) : un créatif DCO sans acteur n'existe pas côté Graph.
        self.assertEqual(action.payload['object_story_spec'],
                         {'page_id': 'page-42'})
        self.assertEqual(self.requests, [])  # zéro réseau avant approbation

        services.apply_action(self._approve(action),
                              client=self._graph_client())
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)

        ads = self._posts('ads')
        self.assertEqual(len(ads), 1)
        self.assertEqual(ads[0]['adset_id'], ['as-new'])
        self.assertTrue(ads[0]['name'][0])
        creative = json.loads(ads[0]['creative'][0])
        self.assertEqual(creative['asset_feed_spec'], spec)
        # Payload Graph FINAL : l'acteur est présent sur la chaîne (c) comme il
        # l'est sur (a) et (b) — plus aucune ad sans Page.
        self.assertEqual(creative['object_story_spec']['page_id'], 'page-42')
        self._assert_born_paused(ads[0])
        self._assert_no_request_ever_activates()

    def test_dco_without_a_connected_page_is_refused_in_french(self):
        # PUB-P8/C2 — la Page manquante est un refus À LA PROPOSITION (aucune
        # EngineAction écrite), jamais un échec découvert à l'application.
        from apps.adsengine import creative_bridge

        MetaConnection.objects.filter(pk=self.connection.pk).update(page_id='')
        with self.assertRaises(creative_bridge.CreativeAssetNotReady) as ctx:
            services.propose_dco_recombination(
                self.company, adset=self.target, now=MONDAY)
        self.assertEqual(ctx.exception.key, creative_bridge.REFUS_PAGE)
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
        self.assertEqual(self.requests, [])
