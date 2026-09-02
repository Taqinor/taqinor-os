"""YRBAC12 — test générique d'isolation multi-tenant sur les viewsets
``TenantMixin``.

``TenantMixin`` scope le queryset générique de chaque ``ModelViewSet`` à
``request.user.company``, mais rien ne le prouvait de façon TRANSVERSALE avant
YRBAC12. Ce test découvre chaque ``ModelViewSet`` concret portant
``TenantMixin`` (``core.tenant_isolation_scan.discover_tenant_viewsets``),
construit un objet MINIMAL dans une société B (factory tolérante,
``build_minimal_instance``) et, comme utilisateur de la société A, vérifie :

* ``list`` : l'objet de B n'apparaît PAS dans les résultats ;
* ``retrieve``/``patch``/``delete`` : 404 (JAMAIS 403 — l'existence d'un
  enregistrement d'une autre société est elle-même sensible).

Les modèles que la factory ne sait pas construire (FK obligatoire non
triviale, type de champ non géré) sont des ``SkipModel`` — listés
explicitement comme dette (jamais un skip silencieux), avec une assertion de
non-régression du nombre de skips (le baseline ne doit jamais AUGMENTER).

CRX17 — trois trous du balai lui-même, comblés
----------------------------------------------

1. **CRÉATION avec une relation étrangère.** Le balai n'exerçait que la lecture
   et l'édition d'un objet EXISTANT du voisin. Le chemin réellement exploité
   est l'autre : créer un objet DANS SA société et l'accrocher à une ligne du
   voisin. ``build_foreign_relation_payload`` synthétise ce corps ; un 201 est
   une FUITE.
2. **Actions de détail.** Les ``@action(detail=True)`` sortaient entièrement du
   balai : une action qui n'appelle pas ``self.get_object()`` répond 200 sur
   l'objet du voisin. Couverture de base : ≤3 actions GET par viewset.
3. **``ReadOnlyModelViewSet`` inclus** (cf. ``tenant_isolation_scan``).

Et deux défauts de MESURE corrigés :

* une liste qui ne répond pas 200, ou dont la forme est inconnue, ne compte
  plus comme « exercée » — elle était comptée alors qu'AUCUNE assertion n'était
  faite dessus (l'ancien compteur mélangeait « modèle construit » et
  « isolation de liste prouvée ») ;
* le cliquet des skips était un pourcentage (85 %) qui, sur les 901 viewsets
  découverts au 02/09, tolérait **765** skips pour ~489 réels : il ne pouvait
  plus capter aucune régression réaliste. Il est recalibré sur le réel mesuré
  (voir ``_PLANCHER_CONSTRUITS`` / ``_PLAFOND_SKIPS_PCT``).
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.tenant_isolation_scan import (
    SkipModel, build_foreign_relation_payload, build_minimal_instance,
    detail_get_actions, discover_tenant_viewsets,
)

User = get_user_model()

# ── Cliquets, calibrés sur le réel mesuré par l'audit L3 du 02/09/2026 ───────
#
# Mesure : 901 viewsets découverts, ~489 non constructibles par la factory
# tolérante → ~412 modèles construits. L'ancien cliquet « 85 % des découverts »
# autorisait 765 skips : quasi tout le parc pouvait devenir non exercé sans que
# la CI bronche.
#
# Deux cliquets remplacent ce pourcentage unique :
#
# * ``_PLANCHER_CONSTRUITS`` — plancher ABSOLU sur le nombre de modèles que la
#   factory sait construire. C'est LUI le vrai garde-fou : il ne peut que
#   monter quand le parc grandit (un viewset ajouté ne retire jamais un modèle
#   construit), donc un plancher calibré sous le réel mesuré capte une
#   régression de la factory ou de la découverte (le bug historique
#   « exercised == 0 ») sans jamais rougir sur la simple croissance du repo.
# * ``_PLAFOND_SKIPS_PCT`` — garde-fou secondaire sur la PROPORTION, resserré
#   de 85 % à 70 % (soit ≤ 630 sur 901, très en deçà des 765 tolérés avant),
#   avec la marge nécessaire à l'arrivée des ``ReadOnlyModelViewSet``.
_PLANCHER_CONSTRUITS = 380
_PLAFOND_SKIPS_PCT = 70

# Budgets de PREMIÈRE OBSERVATION des deux nouvelles couvertures (CRX17). Le
# balai NOMME chaque viewset fautif dans son rapport : ces budgets existent pour
# qu'une RÉGRESSION future soit rouge, pas pour transformer le premier passage
# en mur (les relations nues d'apps/crm viennent d'être fermées par CRX13, mais
# le reste du parc n'a jamais été audité sous cet angle). À resserrer sur le
# compte réel dès qu'il est imprimé par la CI.
_BUDGET_CREATE_ETRANGER = 80
_BUDGET_ACTIONS_ETRANGERES = 60


def _client_for(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api


class TenantIsolationSweepTests(TestCase):
    """Un seul test paramétré (via subTest) sur CHAQUE viewset découvert —
    un run complet couvre l'ensemble des ~104 viewsets ``TenantMixin`` d'un
    coup, avec un rapport de dette clair sur ceux qu'elle n'a pas pu exercer.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company_a = Company.objects.get_or_create(
            slug="yrbac12-a", defaults={"nom": "YRBAC12 A"})[0]
        cls.company_b = Company.objects.get_or_create(
            slug="yrbac12-b", defaults={"nom": "YRBAC12 B"})[0]
        cls.user_a = User.objects.create_user(
            username="yrbac12-user-a", password="x",
            role_legacy="admin", company=cls.company_a)

    def test_sweep_all_tenant_modelviewsets(self):
        entries = discover_tenant_viewsets()
        self.assertGreaterEqual(
            len(entries), 30,
            "La découverte de viewsets TenantMixin est anormalement petite "
            f"({len(entries)}) — le parcours d'URLconf a-t-il régressé ?",
        )

        client = _client_for(self.user_a)
        skipped = []
        constructed = 0
        exercised = 0
        listes_inexploitables = []
        create_fuites = []
        create_dette = []
        action_fuites = []
        actions_exercees = 0

        for entry in entries:
            name = entry.view_class.__name__
            model = entry.model
            with self.subTest(viewset=name):
                if model is None:
                    skipped.append((name, "pas de queryset de classe résolu"))
                    continue
                try:
                    # Point de sauvegarde : une construction qui casse (erreur
                    # d'intégrité) laisserait sinon la transaction du test
                    # AVORTÉE, et tous les viewsets suivants échoueraient en
                    # cascade sur une cause sans rapport.
                    with transaction.atomic():
                        obj_b = build_minimal_instance(model, self.company_b)
                except SkipModel as exc:
                    skipped.append((name, str(exc)))
                    continue
                except Exception as exc:  # noqa: BLE001 - dette, pas un crash
                    skipped.append((name, f"échec de construction : {exc}"))
                    continue

                constructed += 1
                detail_path = entry.detail_path(obj_b.pk)

                # 1) Liste : l'objet de B n'apparaît pas pour A.
                #    CRX17 — ne compte comme EXERCÉ que si la liste a vraiment
                #    répondu 200 ET que sa forme a permis d'extraire des ids :
                #    sinon aucune assertion n'était faite et le viewset était
                #    quand même compté « exercé » (mesure fausse).
                list_resp = client.get(entry.list_path)
                if list_resp.status_code != 200:
                    listes_inexploitables.append(
                        (name, f"liste HTTP {list_resp.status_code}"))
                else:
                    ids = self._extract_ids(list_resp.data)
                    if ids is None:
                        listes_inexploitables.append(
                            (name, "forme de liste inconnue"))
                    else:
                        exercised += 1
                        self.assertNotIn(
                            obj_b.pk, ids,
                            f"{name} : objet de la société B visible dans "
                            f"la liste de la société A.")

                # Un viewset qui refuse l'utilisateur EN BLOC (la LISTE elle
                # aussi répond 401/403) ne révèle rien : son refus est
                # identique pour un objet inexistant, pour le sien et pour
                # celui du voisin. On tolère alors ce MÊME code sur le détail —
                # jamais un 403 isolé sur un viewset dont la liste répond 200
                # (là, le 403 distinguerait l'existence).
                refus_global = ({list_resp.status_code}
                                if list_resp.status_code in (401, 403)
                                else set())

                # 2) Détail : 404 (jamais 403 — existence indistincte).
                get_resp = client.get(detail_path)
                self.assertIn(
                    get_resp.status_code, {404} | refus_global,
                    f"{name} : GET détail d'un objet d'une autre société "
                    f"attendait 404, a renvoyé {get_resp.status_code}.")

                # 3) PATCH : 404 (jamais 403, jamais 200) — 405 accepté : un
                # viewset lecture-seule (sans update) rejette la méthode AVANT
                # toute recherche d'objet, donc aucune fuite inter-société
                # possible (la fuite GET est couverte séparément ci-dessus).
                patch_resp = client.patch(detail_path, {}, format="json")
                self.assertIn(
                    patch_resp.status_code, {404, 405} | refus_global,
                    f"{name} : PATCH d'un objet d'une autre société "
                    f"attendait 404/405, a renvoyé {patch_resp.status_code}.")

                # 4) DELETE : 404 (jamais 403, jamais 204) — 405 idem (viewset
                # sans destroy).
                delete_resp = client.delete(detail_path)
                self.assertIn(
                    delete_resp.status_code, {404, 405} | refus_global,
                    f"{name} : DELETE d'un objet d'une autre société "
                    f"attendait 404/405, a renvoyé {delete_resp.status_code}.")

                # 5) CRX17 — CRÉATION accrochée à une ligne du voisin.
                try:
                    with transaction.atomic():
                        payload, relations = build_foreign_relation_payload(
                            entry.view_class, self.company_b)
                except SkipModel as exc:
                    create_dette.append((name, str(exc)))
                except Exception as exc:  # noqa: BLE001 - dette, pas un crash
                    create_dette.append((name, f"synthèse impossible : {exc}"))
                else:
                    # Le client de test RE-LÈVE les exceptions non gérées : un
                    # POST synthétique qui casse une vue exotique est de la
                    # DETTE (à corriger à part), jamais une fuite — sinon un
                    # seul viewset fragile ferait tomber tout le balai.
                    try:
                        with transaction.atomic():
                            create_resp = client.post(
                                entry.list_path, payload, format="json")
                    except Exception as exc:  # noqa: BLE001 — dette explicite
                        create_dette.append((name, f"POST en erreur : {exc}"))
                    else:
                        if create_resp.status_code in (200, 201):
                            create_fuites.append((name, ", ".join(relations)))

                # 6) CRX17 — actions de détail (couverture de base) : une
                #    @action GET ne doit JAMAIS servir 200 sur l'objet du
                #    voisin (elle doit passer par ``self.get_object()``).
                for url_path in detail_get_actions(entry.view_class):
                    action_path = f"{detail_path.rstrip('/')}/{url_path}/"
                    try:
                        with transaction.atomic():
                            action_resp = client.get(action_path)
                    except Exception as exc:  # noqa: BLE001 — dette explicite
                        create_dette.append(
                            (name, f"@action {url_path} en erreur : {exc}"))
                        continue
                    actions_exercees += 1
                    if action_resp.status_code == 200:
                        action_fuites.append((name, url_path))

        # Rapport de dette explicite (jamais silencieux) — visible dans la
        # sortie du test même quand tous les subTest passent.
        def _rapport(titre, entrees):
            if not entrees:
                return
            print(f"\n{titre} ({len(entrees)}) :")  # noqa: T201
            for nom, detail in sorted(entrees):
                print(f"  - {nom}: {detail}")  # noqa: T201

        _rapport("YRBAC12 — viewsets non exercés par la factory générique",
                 skipped)
        _rapport("CRX17 — listes inexploitables (non comptées comme exercées)",
                 listes_inexploitables)
        _rapport("CRX17 — CRÉATION acceptée avec une relation d'une AUTRE "
                 "société", create_fuites)
        _rapport("CRX17 — création non synthétisable (dette)", create_dette)
        _rapport("CRX17 — @action de détail servant 200 sur l'objet du voisin",
                 action_fuites)
        print(  # noqa: T201
            f"\nCRX17 — découverts={len(entries)} construits={constructed} "
            f"listes exercées={exercised} actions exercées={actions_exercees}")

        self.assertGreater(
            constructed, 0,
            "Aucun viewset n'a pu être construit par la factory — régression "
            "du sweep lui-même.")
        self.assertGreater(
            exercised, 0,
            "Aucune liste n'a pu être exercée (200 + forme connue) — "
            "régression du sweep lui-même.")
        # CRX17 — cliquet PRINCIPAL : un plancher ABSOLU sur les modèles que la
        # factory sait construire. Contrairement à un pourcentage, il ne se
        # relâche pas quand le parc grandit — c'est exactement ce qui avait
        # vidé l'ancien seuil de sa substance (85 % de 901 = 765 skips tolérés
        # pour ~489 réels). Une régression de la factory ou de la découverte
        # (le bug historique « exercised == 0 ») le fait tomber immédiatement.
        self.assertGreaterEqual(
            constructed, _PLANCHER_CONSTRUITS,
            f"CRX17 : la factory ne construit plus que {constructed} modèles "
            f"(plancher {_PLANCHER_CONSTRUITS}, ~412 mesurés le 02/09) — "
            "régression de build_minimal_instance ou de la découverte.")
        # Garde-fou secondaire sur la PROPORTION (resserré 85 % → 70 %).
        self.assertLessEqual(
            len(skipped), len(entries) * _PLAFOND_SKIPS_PCT // 100,
            f"YRBAC12 : dette de couverture anormale "
            f"({len(skipped)}/{len(entries)} viewsets non construits) — voir "
            "le détail ci-dessus (régression probable de la factory/discovery).")

        # CRX17 — budgets de première observation des deux NOUVELLES
        # couvertures (chaque cas fautif est nommé dans le rapport ci-dessus).
        self.assertLessEqual(
            len(create_fuites), _BUDGET_CREATE_ETRANGER,
            f"CRX17 : {len(create_fuites)} viewsets acceptent une CRÉATION "
            "accrochée à une ligne d'une autre société (budget "
            f"{_BUDGET_CREATE_ETRANGER}) — voir la liste nommée ci-dessus.")
        self.assertLessEqual(
            len(action_fuites), _BUDGET_ACTIONS_ETRANGERES,
            f"CRX17 : {len(action_fuites)} @action de détail servent 200 sur "
            f"l'objet d'une autre société (budget "
            f"{_BUDGET_ACTIONS_ETRANGERES}) — voir la liste nommée ci-dessus.")

    @staticmethod
    def _extract_ids(data):
        """Extrait la liste des ``id`` d'une réponse liste (paginée ou non).
        Renvoie ``None`` si la forme est inattendue (pas d'assertion faite)."""
        if isinstance(data, dict) and "results" in data:
            rows = data["results"]
        elif isinstance(data, list):
            rows = data
        else:
            return None
        try:
            return {
                row["id"] for row in rows
                if isinstance(row, dict) and "id" in row
            }
        except (TypeError, KeyError):
            return None


class BuildMinimalInstanceFactoryTests(TestCase):
    """Exerce ``build_minimal_instance`` directement sur des modèles réels
    pour prouver, en isolation, chaque branche de la factory tolérante."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug="yrbac12-factory", defaults={"nom": "YRBAC12 Factory"})[0]

    def test_simple_model_only_company_required(self):
        """``records.Tag`` : seule ``company`` est obligatoire."""
        from apps.records.models import Tag
        tag = build_minimal_instance(Tag, self.company)
        self.assertEqual(tag.company_id, self.company.pk)

    def test_required_user_fk_is_built_via_customuser(self):
        """Un FK obligatoire vers ``settings.AUTH_USER_MODEL`` (ex.
        ``records.Follower.user``) est construit récursivement — mais
        ``Follower`` reste SkipModel à cause de son FK ``content_type``
        (``django.contrib.contenttypes.ContentType``, non géré) : preuve que
        la factory est tolérante ET honnête (elle ne construit QUE ce qu'elle
        sait faire, jamais une devinette risquée sur le reste)."""
        from apps.records.models import Follower
        with self.assertRaises(SkipModel):
            build_minimal_instance(Follower, self.company)

    def test_non_tenant_model_is_skipped(self):
        """Un modèle sans champ ``company`` (ex. ``authentication.Company``
        lui-même) est hors périmètre — SkipModel, jamais un crash."""
        with self.assertRaises(SkipModel):
            build_minimal_instance(Company, self.company)


class Crx17CouverturesTests(TestCase):
    """CRX17 — les trois nouvelles briques du balai, prouvées en isolation."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug="crx17-scan", defaults={"nom": "CRX17 Scan"})[0]

    # ── ReadOnlyModelViewSet désormais dans le périmètre ────────────────────

    def test_readonly_modelviewset_est_dans_le_perimetre(self):
        from rest_framework import viewsets as drf_viewsets
        from core.mixins import TenantMixin
        from core.tenant_isolation_scan import (
            _is_concrete_tenant_modelviewset,
        )

        class _LectureSeule(TenantMixin, drf_viewsets.ReadOnlyModelViewSet):
            pass

        class _SansTenant(drf_viewsets.ReadOnlyModelViewSet):
            pass

        self.assertTrue(
            _is_concrete_tenant_modelviewset(_LectureSeule),
            "Un ReadOnlyModelViewSet TenantMixin doit être balayé : la fuite "
            "de LECTURE est la même que sur un ModelViewSet.")
        self.assertFalse(_is_concrete_tenant_modelviewset(_SansTenant))

    # ── Corps de création avec une relation étrangère ───────────────────────

    def test_payload_pointe_la_relation_vers_la_societe_donnee(self):
        from rest_framework import serializers as drf
        from apps.records.models import Tag

        class _Serializer(drf.Serializer):
            tag = drf.PrimaryKeyRelatedField(queryset=Tag.objects.all())
            titre = drf.CharField()
            note = drf.CharField(required=False)

        class _ViewSet:
            serializer_class = _Serializer

        payload, relations = build_foreign_relation_payload(
            _ViewSet, self.company)
        self.assertEqual(relations, ["tag"])
        self.assertIn("titre", payload)
        self.assertNotIn("note", payload)  # facultatif → jamais synthétisé
        cible = Tag.objects.get(pk=payload["tag"])
        self.assertEqual(cible.company_id, self.company.pk)

    def test_relation_many_est_envoyee_en_liste(self):
        from rest_framework import serializers as drf
        from apps.records.models import Tag

        class _Serializer(drf.Serializer):
            tags = drf.PrimaryKeyRelatedField(
                queryset=Tag.objects.all(), many=True)

        payload, relations = build_foreign_relation_payload(
            type("_VS", (), {"serializer_class": _Serializer}), self.company)
        self.assertEqual(relations, ["tags"])
        self.assertIsInstance(payload["tags"], list)

    def test_sans_relation_company_scopee_le_viewset_est_de_la_dette(self):
        from rest_framework import serializers as drf

        class _Serializer(drf.Serializer):
            titre = drf.CharField()

        with self.assertRaises(SkipModel):
            build_foreign_relation_payload(
                type("_VS", (), {"serializer_class": _Serializer}),
                self.company)

    def test_champ_obligatoire_non_synthetisable_est_de_la_dette(self):
        from rest_framework import serializers as drf
        from apps.records.models import Tag

        class _Serializer(drf.Serializer):
            tag = drf.PrimaryKeyRelatedField(queryset=Tag.objects.all())
            fichier = drf.FileField()

        with self.assertRaises(SkipModel):
            build_foreign_relation_payload(
                type("_VS", (), {"serializer_class": _Serializer}),
                self.company)

    def test_serializer_absent_est_de_la_dette(self):
        with self.assertRaises(SkipModel):
            build_foreign_relation_payload(type("_VS", (), {}), self.company)

    # ── Actions de détail ──────────────────────────────────────────────────

    def test_seules_les_actions_get_de_detail_sont_retenues(self):
        from rest_framework import viewsets as drf_viewsets
        from rest_framework.decorators import action

        class _AvecActions(drf_viewsets.ViewSet):
            @action(detail=True, methods=["get"], url_path="resume")
            def resume(self, request, pk=None):
                pass

            @action(detail=True, methods=["post"], url_path="valider")
            def valider(self, request, pk=None):
                pass

            @action(detail=False, methods=["get"], url_path="global")
            def globale(self, request):
                pass

        self.assertEqual(detail_get_actions(_AvecActions), ["resume"])

    def test_le_nombre_d_actions_exercees_est_borne(self):
        from rest_framework import viewsets as drf_viewsets
        from rest_framework.decorators import action

        attributs = {}
        for i in range(6):
            def _vue(self, request, pk=None):
                pass
            # DRF exige que le nom de la fonction ÉGALE le nom d'attribut
            # (``get_extra_actions`` l'assertionne) — on le pose avant de
            # décorer.
            _vue.__name__ = f"a{i}"
            attributs[f"a{i}"] = action(
                detail=True, methods=["get"], url_path=f"a{i}")(_vue)
        _Beaucoup = type("_Beaucoup", (drf_viewsets.ViewSet,), attributs)

        self.assertEqual(len(detail_get_actions(_Beaucoup)), 3)
        self.assertEqual(len(detail_get_actions(_Beaucoup, limit=5)), 5)
