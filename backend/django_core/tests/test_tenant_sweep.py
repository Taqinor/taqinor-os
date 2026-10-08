"""QAH4 — balayage d'isolation multi-tenant (IDOR/BOLA) sur TOUTES les routes.

LE TROU. Le balai YRBAC12 (``core/tests/test_tenant_isolation_sweep.py``) ne
voit que les viewsets qui héritent de ``TenantMixin`` — et sa factory abandonne
dès qu'un FK obligatoire vise autre chose que ``Company``/``CustomUser``, soit
la moitié du parc. Or ~90 % des viewsets de ce dépôt scopent À LA MAIN
(``get_queryset`` maison, helpers ``_scope``/``_scoped``…) : c'est précisément
là qu'un oubli ne se voit sur aucun gate.

CE TEST est la garde transverse demandée par QAH4 (même esprit que
``tests/test_aud417_admin_scoping_transverse.py`` : il itère le REGISTRE, donc
tout viewset ajouté demain est couvert sans branchement manuel). Pour CHAQUE
viewset monté sous ``api/django/`` (``testkit.tenant_sweep.decouvrir_viewsets``) :

1. un objet RÉEL est construit dans la société A (constructeur générique : FK
   obligatoires construits dans la même société, champs texte MARQUÉS
   ``qah4a…``) ;
2. **contrôle positif** : l'administrateur de A doit le voir (détail 200 ou
   présent dans sa liste) — sinon le viewset est « non exercé » et le dit, au
   lieu de passer pour isolé parce que PERSONNE ne voit l'objet ;
3. l'administrateur de B rejoue sur l'objet de A : lecture détail, PATCH, chaque
   ``@action`` de détail (toutes méthodes — exports et PDF compris), puis
   DELETE. Chaque réponse est comparée à la même requête sur un identifiant
   INEXISTANT (``testkit.tenant_sweep.verdict``) : 2xx = fuite de lecture ou
   d'écriture ; un statut différent de l'inexistant (403 contre 404) = oracle
   d'existence (la règle « 404, jamais 403 ») ;
4. B lit sa liste (et chaque ``@action`` GET de liste) : aucune ligne de A, et
   AUCUN marqueur ``qah4a`` dans le corps — ce second oracle attrape aussi les
   exports CSV, statistiques et agrégats qui servent des données du voisin ;
5. si le sérialiseur de création laisse ``company`` INSCRIPTIBLE, B crée avec
   ``company`` = A puis déplace son propre objet vers A : la société du corps
   doit être ignorée (forcée par ``perform_create``/``perform_update``).

Chaque requête de B est jouée dans un point de sauvegarde ANNULÉ : un effet de
bord d'une sonde (une suppression qui fuit…) ne contamine jamais la suivante.

LES CLIQUETS (ils ne peuvent que se resserrer)
---------------------------------------------
* ``EXCLUSIONS`` — viewsets volontairement hors balayage, CHACUN justifié ;
  ``EXCLUSIONS_PLAFOND`` fige la taille : ajouter une entrée impose de monter le
  plafond dans la même revue. Une entrée « référentiel » est VÉRIFIÉE : son
  modèle ne doit avoir aucun chemin vers une société.
* ``FUITES_CONNUES`` — fuite observée → tâche ERR, jamais une exclusion. Le test
  rougit sur toute fuite ABSENTE de la liste ET sur toute entrée qui ne fuit
  plus (elle doit alors être retirée) : la liste ne fait que rétrécir.
* ``PLANCHER_EXERCES_PCT`` — part minimale de viewsets réellement exercés
  (contrôle positif réussi) par partition : un balai qui ne prouve plus rien
  (régression du constructeur, de l'authentification…) rougit au lieu de
  rester vert à vide.

Découpé en ``NB_PARTITIONS`` classes : ``manage.py test --parallel`` affecte une
CLASSE entière à un worker, huit tranches courtes tiennent donc dans le temps
d'un shard au lieu d'en devenir la borne indivisible.

Lancer (CI : shards ``backend-tests``, ``scripts/ci_shard.py`` y inclut
``tests/``) :
    docker compose exec django_core python manage.py test \
        tests.test_tenant_sweep -v 2
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field

from django.core.cache import cache
from django.db import transaction
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from testkit import tenant_sweep as ts
from testkit.factories import CompanyFactory, UserFactory

# ── Exclusions (justifiées, ne peuvent que rétrécir) ─────────────────────────
#
# Clé = ``app.NomDuViewSet`` (``ts.libelle_viewset``). Valeur = (nature, raison).
# Natures admises : ``referentiel`` (modèle SANS aucun chemin vers une société —
# vérifié par ``GardesStatiques``), ``public`` (route sans authentification
# société), ``plateforme`` (surface éditeur). Une fuite n'est JAMAIS une raison
# d'exclure : elle va dans ``FUITES_CONNUES`` avec sa tâche ERR.
EXCLUSIONS = {
    'core.ChangelogViewSet': (
        'referentiel',
        "FG399/AUD813 — journal des nouveautés GLOBAL au produit : "
        "``core.ChangelogEntry`` n'a aucune FK société, toute société lit les "
        "mêmes notes publiées (et l'écriture est réservée au superutilisateur "
        "Django). Qu'un tenant voie une note créée « chez » un autre est le "
        "comportement voulu, pas une fuite."),
}
EXCLUSIONS_PLAFOND = 1

# ── Fuites connues (cliquet) ─────────────────────────────────────────────────
#
# Clé = ``Constat.cle`` (``'<libellé> :: <MÉTHODE> <action>'``, imprimée par le
# rapport), valeur = identifiant de la tâche ERR ouverte dans
# ``docs/ERROR_PLAN.md``. Vide = aucune fuite tolérée.
FUITES_CONNUES = {}
FUITES_CONNUES_PLAFOND = 0

NB_PARTITIONS = 8

# Plancher de PREMIÈRE OBSERVATION (aucune mesure CI n'existait à l'écriture) :
# il capte l'effondrement du balai (« exercés == 0 », le bug historique de
# YRBAC12) sans rougir sur la dette réelle de construction. À resserrer sur le
# réel que le rapport imprime en CI.
PLANCHER_EXERCES_PCT = 30

# ── ASEC18 — étape « écriture » (FK inscriptible vers une ligne du voisin) ───
#
# Pour chaque viewset EXERCÉ, l'administrateur de A PATCHe SON objet (et, si
# la route existe, rejoue sa création) en posant dans chaque FK inscriptible
# vers un modèle tenant l'identifiant d'une ligne de B. Attendu : 400/404 (ou
# champ ignoré) et la relation relue EN BASE ne pointe jamais la ligne de B.
#
# Exemptions = liste NOMMÉE (site → (raison, tâche qui la retire)) qui ne peut
# que décroître, plus les sites encore constatés d'ERR-SPL72 lus dans
# ``scripts/fk_scoping_allow.txt`` (même format ``chemin::Serializer.champ``,
# même propriétaire ; chaque ligne retirée là-bas l'est ici). Vide pour les
# sites corrigés par ASEC6, 7, 22, 26, 27, 28, 30, 32, 33, 34, 35.
EXEMPTIONS_ECRITURE = {}
EXEMPTIONS_ECRITURE_PLAFOND = 0
TACHE_SPL72 = 'ERR-SPL72-FK-SCOPING-95'

#: Part minimale, par tranche, des sites d'écriture (viewsets à modèle servant
#: PATCH ou création) dont l'étape a réellement inspecté le sérialiseur.
PLANCHER_ECRITURE_PCT = 30


@functools.lru_cache(maxsize=None)
def sites_spl72():
    """Sites ERR-SPL72 encore ouverts (``scripts/fk_scoping_allow.txt``)."""
    from pathlib import Path

    from django.conf import settings

    chemin = (Path(settings.BASE_DIR).resolve().parent.parent / 'scripts'
              / 'fk_scoping_allow.txt')
    if not chemin.is_file():
        return frozenset()
    return frozenset(
        ligne.strip() for ligne in chemin.read_text(encoding='utf-8')
        .splitlines() if ligne.strip() and not ligne.startswith('#'))


def exemption_ecriture(site):
    """Tâche qui retire l'exemption de ``site``, ou ``None``."""
    if site in EXEMPTIONS_ECRITURE:
        return EXEMPTIONS_ECRITURE[site][1]
    if site in sites_spl72():
        return TACHE_SPL72
    return None


#: Quelle forme de clé d'identifiant chercher dans une ligne de liste.
_CLES_ID = ('id', 'pk')


@functools.lru_cache(maxsize=None)
def _entrees():
    return tuple(ts.decouvrir_viewsets())


@functools.lru_cache(maxsize=None)
def _apiviews_ecriture():
    return tuple(ts.decouvrir_apiviews_ecriture())


def _a_balayer(index):
    return [e for e in ts.partition(list(_entrees()), index, NB_PARTITIONS)
            if e.libelle not in EXCLUSIONS]


def _client(user):
    api = APIClient(raise_request_exception=False)
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Annuler(Exception):
    """Force l'annulation du point de sauvegarde d'une sonde."""


@dataclass
class _Reponse:
    statut: int
    marque_a: bool
    donnees: object
    apres: object = None


@dataclass
class _Resultat:
    libelle: str
    statut: str = 'exerce'  # exerce | non_exerce | sans_modele
    raison: str = ''
    modele: str = ''
    constats: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    sondes: int = 0
    non_sondees: int = 0
    a_liste_voit: bool = False
    # ASEC18 — étape « écriture » : sans_ecriture | exerce | non_exerce
    ecriture: str = 'sans_ecriture'
    constats_fk: list = field(default_factory=list)
    sites_sondes: set = field(default_factory=set)
    fk_sondees: int = 0


class _BalayageTenant:
    """Une tranche du balayage. Les classes concrètes (en bas du fichier) ne
    fixent que ``INDEX`` ; ce mixin n'hérite pas de ``TestCase`` pour ne pas
    être collecté lui-même."""

    INDEX = None

    @classmethod
    def setUpTestData(cls):
        cls.company_a = CompanyFactory(nom=f'{ts.MARQUE_A} société')
        cls.company_b = CompanyFactory(nom=f'{ts.MARQUE_B} société')
        cls.user_a = UserFactory(company=cls.company_a, role_legacy='admin')
        cls.user_b = UserFactory(company=cls.company_b, role_legacy='admin')

    # -- orchestration --------------------------------------------------------

    def _resultats_tranche(self):
        """Le balayage de la tranche, joué UNE fois par classe : les deux
        tests (isolation, écriture) jugent les mêmes résultats — la tranche
        ne coûte pas deux constructions du parc."""
        cls = type(self)
        cache_classe = cls.__dict__.get('_resultats_caches')
        if cache_classe is not None:
            return cache_classe
        entrees = _a_balayer(self.INDEX)
        self.assertTrue(entrees, f'tranche {self.INDEX} vide')
        self.client_a = _client(self.user_a)
        self.client_b = _client(self.user_b)
        self.cons_a = ts.Constructeur(self.company_a, self.user_a, ts.MARQUE_A)
        self.cons_b = ts.Constructeur(self.company_b, self.user_b, ts.MARQUE_B)
        resultats = [self._balayer_protege(entree) for entree in entrees]
        self._rapport(resultats)
        cls._resultats_caches = resultats
        return resultats

    def test_isolation_de_chaque_viewset_de_la_tranche(self):
        resultats = self._resultats_tranche()
        for res in resultats:
            with self.subTest(viewset=res.libelle):
                self._verifier_cliquet(res)
        self._verifier_couverture(resultats)

    def test_ecriture_fk_voisine_refusee(self):
        """ASEC18 — A ne peut lier À SON objet aucune ligne de B par une FK
        inscriptible (PATCH, création) ; exemptions nommées seulement."""
        resultats = self._resultats_tranche()
        for res in resultats:
            with self.subTest(viewset=res.libelle):
                self._verifier_cliquet_ecriture(res)
        self._verifier_couverture_ecriture(resultats)

    def _balayer_protege(self, entree):
        """Un défaut du BALAI (pas du code testé) ne doit ni tout faire tomber
        ni passer sous silence : il est reporté comme « non exercé »."""
        etat = [(cons, dict(cons._cache),
                 {k: set(v) for k, v in cons.construits.items()})
                for cons in (self.cons_a, self.cons_b)]
        try:
            with transaction.atomic():
                return self._balayer(entree)
        except Exception as exc:  # noqa: BLE001 — dette du balai, nommée
            # Tout ce que ce viewset a construit vient d'être annulé : le
            # cache des constructeurs ne doit plus pointer ces lignes.
            for cons, cache_avant, construits_avant in etat:
                cons._cache = cache_avant
                cons.construits.clear()
                cons.construits.update(construits_avant)
            return _Resultat(
                entree.libelle, statut='non_exerce',
                raison=f'erreur du balai : {type(exc).__name__}: '
                       f'{(str(exc).splitlines() or [""])[0][:160]}')

    def _balayer(self, entree):
        res = _Resultat(entree.libelle)
        cache.clear()  # throttles par vue (LocMem) : jamais un 429 hérité
        model = (ts.modele_statique(entree.view_class)
                 or ts.modele_dynamique(entree, self.user_a))
        if model is None:
            res.statut = 'sans_modele'
            res.raison = 'vue calculée : seul le balayage par marqueurs joue'
            self._sonder_listes(entree, res, None, {})
            return res
        res.modele = model._meta.label
        if ts.portee_tenant(model) is None:
            # Modèle résolu À L'EXÉCUTION (pas de ``queryset`` de classe, donc
            # invisible de ``GardesStatiques``) et sans aucun chemin vers une
            # société : tout le monde le voit par conception, le rejouer
            # produirait une fausse alerte. Seul le balayage par marqueurs joue.
            res.statut = 'non_exerce'
            res.raison = ('modèle sans société (référentiel partagé) — '
                          'seul le balayage par marqueurs joue')
            self._sonder_listes(entree, res, None, {})
            return res
        try:
            obj = self.cons_a.objet(model)
        except ts.ConstructionImpossible as exc:
            res.statut = 'non_exerce'
            res.raison = f'construction impossible — {exc}'
            self._sonder_listes(entree, res, model, {})
            return res
        valeurs = self._valeurs_url(entree, obj)
        absentes = dict(valeurs)
        absentes[entree.lookup_kwarg] = ts.valeur_absente(
            model, entree.lookup_field)

        self._controle_positif(entree, res, obj, valeurs)

        route = entree.route_detail()
        methodes_detail = {m for m, _a in route.methodes} if route else set()
        if route is not None:
            self._sonder(entree, res, 'get', 'retrieve', route, valeurs,
                         absentes)
            if 'patch' in methodes_detail:
                self._sonder(entree, res, 'patch', 'partial_update', route,
                             valeurs, absentes)
        for methode, action, route_action in entree.actions_supplementaires(
                detail=True):
            self._sonder(entree, res, methode, action, route_action, valeurs,
                         absentes)
        self._sonder_listes(entree, res, model, valeurs, obj=obj)
        self._sonder_company_etrangere(entree, res, model, valeurs)
        self._sonder_fk_voisines(entree, res, model, valeurs, obj)
        if route is not None and 'delete' in methodes_detail:
            self._sonder(entree, res, 'delete', 'destroy', route, valeurs,
                         absentes)
        return res

    # -- requêtes -------------------------------------------------------------

    def _requete(self, client, methode, chemin, corps=None, apres=None):
        """Joue une requête dans un point de sauvegarde TOUJOURS annulé et
        rend statut / marqueur / données lus AVANT l'annulation."""
        boite = {}
        try:
            with transaction.atomic():
                if methode == 'get':
                    reponse = client.get(chemin)
                else:
                    reponse = getattr(client, methode)(
                        chemin, corps if corps is not None else {},
                        format='json')
                valeur_apres = None
                if apres is not None:
                    try:
                        with transaction.atomic():
                            valeur_apres = apres(reponse)
                    except Exception:  # noqa: BLE001 — base avortée par la vue
                        valeur_apres = None
                boite['rep'] = _Reponse(
                    statut=reponse.status_code,
                    marque_a=ts.contient_marque(reponse, ts.MARQUE_A),
                    donnees=ts.donnees(reponse), apres=valeur_apres)
                raise _Annuler
        except _Annuler:
            pass
        return boite['rep']

    def _valeurs_url(self, entree, obj):
        if entree.lookup_field == 'pk':
            lookup = obj.pk
        else:
            lookup = getattr(obj, entree.lookup_field, None)
        valeurs = {entree.lookup_kwarg: lookup}
        for route in entree.routes:
            for groupe in route.groupes:
                if groupe not in valeurs:
                    valeur = ts.valeur_groupe(obj, groupe)
                    if valeur is not None:
                        valeurs[groupe] = valeur
        return valeurs

    def _ids_a(self, model):
        if ts._est_company(model):
            return {str(self.company_a.pk)}
        champs = ts._champs_fk_company(model)
        if champs:
            with transaction.atomic():
                return {str(pk) for pk in model._base_manager.filter(
                    **{champs[0].name: self.company_a}).values_list(
                        'pk', flat=True)}
        return {str(pk) for pk in self.cons_a.construits.get(model, ())}

    # -- contrôle positif ---------------------------------------------------

    def _controle_positif(self, entree, res, obj, valeurs):
        cles = _CLES_ID + (entree.lookup_field,)
        cibles = {str(obj.pk), str(valeurs.get(entree.lookup_kwarg))}
        statut_detail = None
        route = entree.route_detail()
        if route is not None:
            chemin = route.remplir(valeurs)
            if chemin is not None:
                statut_detail = self._requete(
                    self.client_a, 'get', chemin).statut
        statut_liste = None
        route_liste = entree.route_liste()
        if route_liste is not None:
            chemin = route_liste.remplir(valeurs)
            if chemin is not None:
                rep = self._requete(self.client_a, 'get',
                                    chemin + '?page_size=200')
                statut_liste = rep.statut
                ids = ts.identifiants_lignes(rep.donnees, cles) or set()
                res.a_liste_voit = rep.statut == 200 and bool(ids & cibles)
        if statut_detail == 200 or res.a_liste_voit:
            return
        res.statut = 'non_exerce'
        res.raison = (
            f'contrôle positif KO — A ne voit pas son propre objet '
            f'(détail {statut_detail}, liste {statut_liste}'
            f'{", objet absent" if statut_liste == 200 else ""})')

    # -- sondes de B --------------------------------------------------------

    def _sonder(self, entree, res, methode, action, route, valeurs, absentes):
        chemin = route.remplir(valeurs)
        if chemin is None:
            res.non_sondees += 1  # segment imbriqué sans valeur sûre
            return
        rep = self._requete(self.client_b, methode, chemin)
        res.sondes += 1
        statut_absent = None
        if ts.a_besoin_de_la_sonde_absente(rep.statut):
            chemin_absent = route.remplir(absentes)
            if chemin_absent is not None:
                statut_absent = self._requete(
                    self.client_b, methode, chemin_absent).statut
        genre = ts.verdict(methode, rep.statut, statut_absent, rep.marque_a)
        if genre:
            res.constats.append(ts.Constat(
                entree.libelle, genre, f'{methode.upper()} {action}',
                f'objet de A → HTTP {rep.statut}, identifiant inexistant → '
                f'HTTP {statut_absent}'
                f'{" (données de A dans le corps)" if rep.marque_a else ""}'))

    def _sonder_listes(self, entree, res, model, valeurs, obj=None):
        route = entree.route_liste()
        chemin = route.remplir(valeurs) if route is not None else None
        if chemin is not None:
            rep = self._requete(self.client_b, 'get',
                                chemin + '?page_size=200')
            res.sondes += 1
            if 200 <= rep.statut < 300:
                if rep.marque_a:
                    res.constats.append(ts.Constat(
                        entree.libelle, 'lecture', 'GET list (marqueur)',
                        'la liste de B contient des données marquées de A'))
                # Les identifiants ne font foi que si A a vu SON objet dans SA
                # liste : la liste sert bien ce modèle, clé = pk.
                if model is not None and obj is not None and res.a_liste_voit:
                    cles = _CLES_ID + (entree.lookup_field,)
                    ids_b = ts.identifiants_lignes(rep.donnees, cles) or set()
                    fuite = ids_b & self._ids_a(model)
                    if fuite:
                        res.constats.append(ts.Constat(
                            entree.libelle, 'lecture', 'GET list',
                            f'{len(fuite)} ligne(s) de A dans la liste de B '
                            f'(ids {sorted(fuite)[:5]})'))
        for methode, action, route_action in entree.actions_supplementaires(
                detail=False):
            if methode != 'get' or ts.action_binaire(action):
                continue
            chemin = route_action.remplir(valeurs)
            if chemin is None:
                res.non_sondees += 1
                continue
            rep = self._requete(self.client_b, 'get', chemin)
            res.sondes += 1
            if 200 <= rep.statut < 300 and rep.marque_a:
                res.constats.append(ts.Constat(
                    entree.libelle, 'lecture', f'GET {action} (marqueur)',
                    "l'action de liste sert à B des données marquées de A"))

    def _sonder_company_etrangere(self, entree, res, model, valeurs):
        creations = entree.routes_action('create')
        noms_fk = {f.name for f in ts._champs_fk_company(model)}
        if not creations or not noms_fk:
            return
        segments = {k: v for k, v in valeurs.items()
                    if k != entree.lookup_kwarg}
        try:
            with transaction.atomic():
                vue = ts.instancier_vue(
                    entree, ts.requete_drf(self.user_b, 'post'), 'create',
                    kwargs=segments)
                serializer = vue.get_serializer()
                ecrits = [nom for nom, champ in serializer.fields.items()
                          if not champ.read_only and champ.source in noms_fk]
        except Exception as exc:  # noqa: BLE001 — noté, jamais une fuite
            res.notes.append(f'sérialiseur de création non instanciable : '
                             f'{type(exc).__name__}')
            return
        if not ecrits:
            return  # ``company`` non inscriptible : ignorée par construction
        try:
            obj_b = self.cons_b.objet(model)
        except ts.ConstructionImpossible as exc:
            res.notes.append(f'création non sondée (objet B) : {exc}')
            return
        source = serializer.fields[ecrits[0]].source
        filtre_a = {source: self.company_a}
        valeurs_b = self._valeurs_url(entree, obj_b)
        chemin = creations[0][1].remplir(valeurs_b)
        if chemin is None:
            res.non_sondees += 1
            return
        corps = ts.charge_utile(serializer, obj_b)
        for nom in ecrits:
            corps[nom] = self.company_a.pk
        with transaction.atomic():
            avant = model._base_manager.filter(**filtre_a).count()
        rep = self._requete(
            self.client_b, 'post', chemin, corps,
            apres=lambda _r: model._base_manager.filter(**filtre_a).count())
        res.sondes += 1
        if 200 <= rep.statut < 300 and (rep.apres or 0) > avant:
            res.constats.append(ts.Constat(
                entree.libelle, 'creation', 'POST create (company étrangère)',
                f'HTTP {rep.statut} : la ligne est née dans la société A '
                f'(« {source} » lu du corps, jamais forcé côté serveur)'))
        elif not 200 <= rep.statut < 300:
            res.notes.append(f'création avec company étrangère : HTTP '
                             f'{rep.statut} (refus ou corps non valide)')
        route = entree.route_detail()
        if route is None or 'patch' not in {m for m, _a in route.methodes}:
            return
        chemin = route.remplir(valeurs_b)
        if chemin is None:
            return
        rep = self._requete(
            self.client_b, 'patch', chemin,
            {nom: self.company_a.pk for nom in ecrits},
            apres=lambda _r: model._base_manager.filter(
                pk=obj_b.pk).values_list(source, flat=True).first())
        res.sondes += 1
        if 200 <= rep.statut < 300 and rep.apres == self.company_a.pk:
            res.constats.append(ts.Constat(
                entree.libelle, 'ecriture',
                'PATCH partial_update (company étrangère)',
                f'HTTP {rep.statut} : B a DÉPLACÉ son objet dans la société A'))

    # -- ASEC18 : étape « écriture » ----------------------------------------

    def _sonder_fk_voisines(self, entree, res, model, valeurs, obj):
        """A pose, sur SON objet, l'identifiant d'une ligne de B dans chaque
        FK inscriptible vers un modèle tenant (PATCH détail, puis création).
        La relation relue en base ne doit jamais pointer la ligne de B."""
        route = entree.route_detail()
        patch = route is not None and 'patch' in {
            m for m, _a in route.methodes}
        creations = entree.routes_action('create')
        if not patch and not creations:
            return  # aucun site d'écriture générique sur ce viewset
        if res.statut != 'exerce':
            res.ecriture = 'non_exerce'
            return
        segments = {k: v for k, v in valeurs.items()
                    if k != entree.lookup_kwarg}
        try:
            with transaction.atomic():
                action = 'partial_update' if patch else 'create'
                vue = ts.instancier_vue(
                    entree, ts.requete_drf(self.user_a, 'patch' if patch
                                           else 'post'), action,
                    kwargs=segments)
                serializer = (vue.get_serializer(obj, data={}, partial=True)
                              if patch else vue.get_serializer())
                champs = ts.champs_fk_inscriptibles(serializer)
        except Exception as exc:  # noqa: BLE001 — dette du balai, nommée
            res.ecriture = 'non_exerce'
            res.notes.append(f'écriture : sérialiseur non instanciable '
                             f'({type(exc).__name__})')
            return
        res.ecriture = 'exerce'
        chemin_patch = route.remplir(valeurs) if patch else None
        for nom, source, cible, multiple in champs:
            site = ts.site_serialiseur(serializer, nom)
            try:
                avant = ts.valeur_relation(obj, source)
            except Exception:  # noqa: BLE001 — source hors modèle
                res.notes.append(f'écriture : {nom} non relisible en base')
                continue
            cache_b = dict(self.cons_b._cache)
            construits_b = {k: set(v)
                            for k, v in self.cons_b.construits.items()}
            try:
                with transaction.atomic():
                    voisin = self.cons_b.parent(cible)
            except Exception as exc:  # noqa: BLE001 — construction de B
                # Les parents construits puis annulés ne doivent plus être
                # servis par le cache (même règle que ``_balayer_protege``).
                self.cons_b._cache = cache_b
                self.cons_b.construits.clear()
                self.cons_b.construits.update(construits_b)
                res.notes.append(f'écriture : {nom} non sondé (ligne de B '
                                 f'{cible._meta.label} : {type(exc).__name__})')
                continue
            valeur = [voisin.pk] if multiple else voisin.pk
            res.sites_sondes.add(site)
            if chemin_patch is not None:
                rep = self._requete(
                    self.client_a, 'patch', chemin_patch, {nom: valeur},
                    apres=lambda _r, s=source: ts.valeur_relation(obj, s))
                res.sondes += 1
                res.fk_sondees += 1
                if (ts.fk_voisine_ecrite(rep.apres, voisin.pk)
                        and not ts.fk_voisine_ecrite(avant, voisin.pk)):
                    res.constats_fk.append((site, f'PATCH fk:{nom}', (
                        f'HTTP {rep.statut} : la ligne {voisin.pk} de B '
                        f'({cible._meta.label}) est liée à l\'objet de A')))
            if creations:
                self._sonder_creation_fk(entree, res, model, valeurs, obj,
                                         creations, (nom, source, site),
                                         voisin, valeur)

    def _sonder_creation_fk(self, entree, res, model, valeurs, obj,
                            creations, champ, voisin, valeur):
        nom, source, site = champ
        chemin = creations[0][1].remplir(valeurs)
        if chemin is None:
            return
        segments = {k: v for k, v in valeurs.items()
                    if k != entree.lookup_kwarg}
        try:
            with transaction.atomic():
                vue = ts.instancier_vue(
                    entree, ts.requete_drf(self.user_a, 'post'), 'create',
                    kwargs=segments)
                corps = ts.charge_utile(vue.get_serializer(), obj)
        except Exception:  # noqa: BLE001 — création non rejouable
            return
        corps[nom] = valeur
        filtre = {source: voisin}
        try:
            with transaction.atomic():
                avant = model._base_manager.filter(**filtre).count()
        except Exception:  # noqa: BLE001 — relation non filtrable
            return
        rep = self._requete(
            self.client_a, 'post', chemin, corps,
            apres=lambda _r: model._base_manager.filter(**filtre).count())
        res.sondes += 1
        res.fk_sondees += 1
        if 200 <= rep.statut < 300 and (rep.apres or 0) > avant:
            res.constats_fk.append((site, f'POST fk:{nom}', (
                f'HTTP {rep.statut} : un objet de A est né lié à la ligne '
                f'{voisin.pk} de B')))

    def _verifier_cliquet_ecriture(self, res):
        non_exemptes = [(site, sonde, detail)
                        for site, sonde, detail in res.constats_fk
                        if exemption_ecriture(site) is None]
        self.assertEqual(
            non_exemptes, [],
            f'FK VOISINE écrite ({res.libelle}) : ' + ' | '.join(
                f'{site} [{sonde}] {detail}'
                for site, sonde, detail in non_exemptes)
            + ' — bornez le champ (`same_company_fields` / '
              '`CompanyScopedRelationsMixin` / `validate_<champ>`), sinon '
              'ouvrez une tâche ERR et nommez le site dans EXEMPTIONS_ECRITURE.')
        fuyants = {site for site, _s, _d in res.constats_fk}
        perimees = sorted(site for site in res.sites_sondes
                          if site in EXEMPTIONS_ECRITURE
                          and site not in fuyants)
        self.assertEqual(
            perimees, [],
            f'exemption(s) d\'écriture plus observée(s) sur {res.libelle} : '
            f'{perimees} — retirez-les de EXEMPTIONS_ECRITURE et baissez '
            'EXEMPTIONS_ECRITURE_PLAFOND.')

    def _verifier_couverture_ecriture(self, resultats):
        sites = [r for r in resultats if r.ecriture != 'sans_ecriture']
        exerces = [r for r in sites if r.ecriture == 'exerce']
        self.assertGreaterEqual(
            len(exerces) * 100, PLANCHER_ECRITURE_PCT * len(sites),
            f'ASEC18 tranche {self.INDEX} : seulement {len(exerces)}/'
            f'{len(sites)} sites d\'écriture exercés (plancher '
            f'{PLANCHER_ECRITURE_PCT} %).')

    # -- cliquets et rapport ------------------------------------------------

    def _verifier_cliquet(self, res):
        observees = {c.cle: c for c in res.constats}
        connues = {cle for cle in FUITES_CONNUES
                   if cle.startswith(f'{res.libelle} :: ')}
        nouvelles = sorted(set(observees) - set(FUITES_CONNUES))
        disparues = sorted(connues - set(observees))
        self.assertEqual(
            nouvelles, [],
            'FUITE multi-tenant : ' + ' | '.join(
                f'{cle} [{observees[cle].genre}] {observees[cle].detail}'
                for cle in nouvelles)
            + " — corrigez le scoping (get_queryset filtré par "
              "request.user.company, company forcée dans perform_create), "
              "sinon ouvrez une tâche ERR et ajoutez la clé à FUITES_CONNUES. "
              "JAMAIS une exclusion.")
        self.assertEqual(
            disparues, [],
            f'fuite(s) connue(s) plus observée(s) sur {res.libelle} '
            f'({res.statut}{": " + res.raison if res.raison else ""}) : '
            f'{disparues} — si elle est corrigée, retirez-la de FUITES_CONNUES '
            'et baissez FUITES_CONNUES_PLAFOND.')

    def _rapport(self, resultats):
        par_statut = {}
        for res in resultats:
            par_statut.setdefault(res.statut, []).append(res)
        print(f'\nQAH4 — tranche {self.INDEX}/{NB_PARTITIONS} : '  # noqa: T201
              f'{len(resultats)} viewsets, '
              + ', '.join(f'{k}={len(v)}' for k, v in sorted(
                  par_statut.items()))
              + f', sondes={sum(r.sondes for r in resultats)}, '
              f'non sondées={sum(r.non_sondees for r in resultats)}')
        for statut in ('non_exerce', 'sans_modele'):
            for res in par_statut.get(statut, []):
                print(f'  [{statut}] {res.libelle} '  # noqa: T201
                      f'({res.modele or "?"}) : {res.raison}')
        ecriture = {}
        for res in resultats:
            ecriture.setdefault(res.ecriture, []).append(res)
        apiviews = ts.partition(list(_apiviews_ecriture()), self.INDEX,
                                NB_PARTITIONS)
        print(f'ASEC18 — écriture tranche {self.INDEX} : '  # noqa: T201
              + ', '.join(f'{k}={len(v)}' for k, v in sorted(
                  ecriture.items()))
              + f', FK sondées={sum(r.fk_sondees for r in resultats)}, '
              f'APIView/@api_view à écriture découvertes (non exercées '
              f'génériquement)={len(apiviews)}')
        for res in resultats:
            for site, sonde, detail in res.constats_fk:
                tache = exemption_ecriture(site)
                etiquette = f'exemptée {tache}' if tache else 'NON EXEMPTÉE'
                print(f'  [FK VOISINE {etiquette}] {res.libelle} :: '  # noqa: T201
                      f'{sonde} — {site} : {detail}')
        for res in resultats:
            for constat in res.constats:
                print(f'  [FUITE {constat.genre}] {constat.cle} : '  # noqa: T201
                      f'{constat.detail}')
            for note in res.notes:
                print(f'  [note] {res.libelle} : {note}')  # noqa: T201

    def _verifier_couverture(self, resultats):
        avec_modele = [r for r in resultats if r.statut != 'sans_modele']
        exerces = [r for r in avec_modele if r.statut == 'exerce']
        self.assertGreaterEqual(
            len(exerces) * 100, PLANCHER_EXERCES_PCT * len(avec_modele),
            f'QAH4 tranche {self.INDEX} : seulement {len(exerces)}/'
            f'{len(avec_modele)} viewsets exercés (plancher '
            f'{PLANCHER_EXERCES_PCT} %) — le balai ne prouve plus rien : '
            'régression du constructeur, de la découverte ou de '
            "l'authentification (voir le rapport ci-dessus).")


# ── Les tranches (une classe = une unité d'affectation --parallel) ───────────


class BalayageTenantTranche0(_BalayageTenant, TestCase):
    INDEX = 0


class BalayageTenantTranche1(_BalayageTenant, TestCase):
    INDEX = 1


class BalayageTenantTranche2(_BalayageTenant, TestCase):
    INDEX = 2


class BalayageTenantTranche3(_BalayageTenant, TestCase):
    INDEX = 3


class BalayageTenantTranche4(_BalayageTenant, TestCase):
    INDEX = 4


class BalayageTenantTranche5(_BalayageTenant, TestCase):
    INDEX = 5


class BalayageTenantTranche6(_BalayageTenant, TestCase):
    INDEX = 6


class BalayageTenantTranche7(_BalayageTenant, TestCase):
    INDEX = 7


# ── Gardes statiques (aucune base) ───────────────────────────────────────────


class GardesStatiques(SimpleTestCase):
    """Ce qui se vérifie sur le registre seul : périmètre, cliquets, tranches."""

    def test_la_decouverte_couvre_le_parc(self):
        """Non-vacuité : 392 viewsets montés au 28/09/2026 (MVP solaire)."""
        self.assertGreaterEqual(len(_entrees()), 300)

    def test_les_libelles_sont_uniques(self):
        libelles = [e.libelle for e in _entrees()]
        doublons = sorted({x for x in libelles if libelles.count(x) > 1})
        self.assertEqual(doublons, [], 'libellés ambigus pour les cliquets')

    def test_chaque_viewset_est_dans_exactement_une_tranche(self):
        vus = []
        for index in range(NB_PARTITIONS):
            vus += [e.libelle for e in _a_balayer(index)]
        attendus = sorted(e.libelle for e in _entrees()
                          if e.libelle not in EXCLUSIONS)
        self.assertEqual(sorted(vus), attendus)
        self.assertEqual(len(vus), len(set(vus)))

    def test_les_exclusions_existent_et_sont_justifiees(self):
        connus = {e.libelle for e in _entrees()}
        for libelle, (nature, raison) in EXCLUSIONS.items():
            with self.subTest(exclusion=libelle):
                self.assertIn(libelle, connus,
                              'exclusion périmée : le viewset a disparu — '
                              "retirez l'entrée et baissez le plafond.")
                self.assertIn(nature, ('referentiel', 'public', 'plateforme'))
                self.assertGreaterEqual(len(raison), 40,
                                        'une exclusion se JUSTIFIE.')

    def test_les_exclusions_ne_peuvent_que_retrecir(self):
        self.assertLessEqual(
            len(EXCLUSIONS), EXCLUSIONS_PLAFOND,
            "nouvelle exclusion : c'est une décision de revue (plafond à "
            'monter explicitement), jamais un moyen de passer au vert.')

    def test_un_referentiel_exclu_na_vraiment_aucune_societe(self):
        par_libelle = {e.libelle: e for e in _entrees()}
        for libelle, (nature, _raison) in EXCLUSIONS.items():
            if nature != 'referentiel' or libelle not in par_libelle:
                continue
            with self.subTest(exclusion=libelle):
                model = ts.modele_statique(par_libelle[libelle].view_class)
                self.assertIsNotNone(model)
                self.assertIsNone(
                    ts.portee_tenant(model),
                    f'{libelle} sert {model._meta.label}, qui APPARTIENT à '
                    "une société : ce n'est pas un référentiel partagé.")

    def test_tout_referentiel_partage_est_declare(self):
        """Un viewset dont le modèle n'a aucun chemin vers une société ne peut
        pas être balayé (tout le monde voit tout, par conception) : il doit
        être déclaré ici, avec sa raison, plutôt que produire une fausse
        alerte — ou, s'il n'est PAS censé être partagé, recevoir sa FK."""
        oublies = []
        for entree in _entrees():
            model = ts.modele_statique(entree.view_class)
            if model is None or entree.libelle in EXCLUSIONS:
                continue
            if ts.portee_tenant(model) is None:
                oublies.append(f'{entree.libelle} ({model._meta.label})')
        self.assertEqual(oublies, [])

    def test_les_fuites_connues_visent_des_viewsets_existants(self):
        connus = {e.libelle for e in _entrees()}
        for cle, err in FUITES_CONNUES.items():
            with self.subTest(fuite=cle):
                self.assertIn(cle.split(' :: ')[0], connus)
                self.assertTrue(err.startswith('ERR'), err)
        self.assertLessEqual(len(FUITES_CONNUES), FUITES_CONNUES_PLAFOND)


class GardesEcriture(SimpleTestCase):
    """ASEC18 — cliquets de l'étape « écriture » et découverte des APIView."""

    def test_les_exemptions_sont_nommees_et_ne_peuvent_que_retrecir(self):
        for site, (raison, tache) in EXEMPTIONS_ECRITURE.items():
            with self.subTest(site=site):
                self.assertIn('::', site, 'site = chemin::Serializer.champ')
                self.assertGreaterEqual(len(raison), 20)
                self.assertRegex(tache, r'^(ERR|ASEC)')
        self.assertLessEqual(len(EXEMPTIONS_ECRITURE),
                             EXEMPTIONS_ECRITURE_PLAFOND)
        self.assertGreaterEqual(PLANCHER_ECRITURE_PCT, 30)

    def test_les_sites_spl72_sont_lus(self):
        """Les exemptions ERR-SPL72 viennent du fichier statique (même
        format) : un fichier introuvable viderait la liste en silence."""
        sites = sites_spl72()
        self.assertTrue(sites, 'scripts/fk_scoping_allow.txt introuvable')
        self.assertTrue(all('::' in s for s in sites))

    def test_les_apiview_a_ecriture_sont_decouvertes(self):
        apiviews = _apiviews_ecriture()
        self.assertGreaterEqual(len(apiviews), 50)
        viewsets = {e.libelle for e in _entrees()}
        for libelle, _gabarit, methodes in apiviews:
            self.assertNotIn(libelle, viewsets)
            self.assertTrue(set(methodes) <= set(ts.METHODES_ECRITURE))


class OracleEtOutillage(SimpleTestCase):
    """Les briques pures du balai, prouvées en isolation."""

    def test_fk_voisine_ecrite(self):
        self.assertTrue(ts.fk_voisine_ecrite(7, 7))
        self.assertTrue(ts.fk_voisine_ecrite('7', 7))
        self.assertTrue(ts.fk_voisine_ecrite(frozenset({3, 7}), 7))
        self.assertFalse(ts.fk_voisine_ecrite(None, 7))
        self.assertFalse(ts.fk_voisine_ecrite(frozenset({3}), 7))
        self.assertFalse(ts.fk_voisine_ecrite(8, 7))

    def test_champs_fk_inscriptibles_et_site(self):
        from django.apps import apps
        from rest_framework import serializers as drf

        class _LigneSerializer(drf.ModelSerializer):
            class Meta:
                model = apps.get_model('ventes', 'LigneDevis')
                fields = ['id', 'devis', 'produit', 'designation']
                read_only_fields = ['devis']

        serializer = _LigneSerializer()
        champs = {nom: (source, cible._meta.label, multiple)
                  for nom, source, cible, multiple
                  in ts.champs_fk_inscriptibles(serializer)}
        self.assertEqual(champs, {'produit': ('produit', 'stock.Produit',
                                              False)})
        self.assertEqual(
            ts.site_serialiseur(serializer, 'produit'),
            'backend/django_core/tests/test_tenant_sweep.py'
            '::_LigneSerializer.produit')

    def test_verdict_404_nest_jamais_une_fuite(self):
        self.assertIsNone(ts.verdict('get', 404, None, False))
        self.assertIsNone(ts.verdict('delete', 404, None, True))

    def test_verdict_succes_sur_lobjet_du_voisin(self):
        self.assertEqual(ts.verdict('get', 200, 404, False), 'lecture')
        self.assertEqual(ts.verdict('patch', 200, 404, False), 'ecriture')
        self.assertEqual(ts.verdict('delete', 204, 404, False), 'ecriture')
        self.assertEqual(ts.verdict('post', 201, 404, False), 'ecriture')

    def test_verdict_oracle_dexistence(self):
        """403 sur l'objet de A, 404 sur l'inexistant : B apprend qu'il existe."""
        self.assertEqual(ts.verdict('get', 403, 404, False), 'existence')
        self.assertEqual(ts.verdict('post', 400, 404, False), 'existence')
        self.assertEqual(ts.verdict('get', 500, 404, False), 'existence')

    def test_verdict_refus_indistinct_nest_pas_une_fuite(self):
        """Même refus pour l'objet de A et pour le néant : rien n'a fui."""
        self.assertIsNone(ts.verdict('get', 403, 403, False))
        self.assertIsNone(ts.verdict('patch', 405, 405, False))
        self.assertIsNone(ts.verdict('get', 429, 404, False))

    def test_verdict_vue_qui_ignore_lidentifiant(self):
        """Singleton/agrégat : 200 partout ; fuite seulement si A est servi."""
        self.assertIsNone(ts.verdict('get', 200, 200, False))
        self.assertEqual(ts.verdict('get', 200, 200, True), 'lecture')

    def test_gabarit_de_route(self):
        chemin, groupes = ts._gabarit(
            'api/django/stock/^produits/(?P<pk>[^/.]+)/historique/$')
        self.assertEqual(chemin, '/api/django/stock/produits/{pk}/historique/')
        self.assertEqual(groupes, ('pk',))
        chemin, groupes = ts._gabarit(
            'api/django/custom-fields/custom-objects/<slug:object_code>/'
            'records/')
        self.assertEqual(groupes, ('object_code',))
        route = ts.Route(chemin, groupes, (('get', 'list'),), False)
        self.assertIsNone(route.remplir({}))
        self.assertEqual(route.remplir({'object_code': 'x1'}),
                         '/api/django/custom-fields/custom-objects/x1/records/')

    def test_lignes_et_identifiants(self):
        self.assertEqual(ts.identifiants_lignes({'results': [{'id': 3}]}),
                         {'3'})
        self.assertEqual(ts.identifiants_lignes([{'pk': 'a'}, 'x']), {'a'})
        self.assertIsNone(ts.identifiants_lignes({'count': 0}))

    def test_corps_texte_ignore_les_binaires(self):
        from django.http import HttpResponse
        json_rep = HttpResponse(b'{"nom": "QAH4A00001"}',
                                content_type='application/json')
        pdf_rep = HttpResponse(b'%PDF qah4a00001',
                               content_type='application/pdf')
        self.assertTrue(ts.contient_marque(json_rep, ts.MARQUE_A))
        self.assertFalse(ts.contient_marque(pdf_rep, ts.MARQUE_A))

    def test_actions_binaires(self):
        self.assertTrue(ts.action_binaire('valorisation_xlsx'))
        self.assertTrue(ts.action_binaire('analyse_achats_pdf'))
        self.assertFalse(ts.action_binaire('export_csv'))

    def test_portee_tenant_du_parc(self):
        from django.apps import apps
        self.assertEqual(ts.portee_tenant(apps.get_model('authentication',
                                                         'Company')),
                         'societe')
        self.assertEqual(ts.portee_tenant(apps.get_model('ventes', 'Devis')),
                         'directe')
        self.assertEqual(ts.portee_tenant(apps.get_model('ventes',
                                                         'LigneDevis')),
                         'via:devis')


class ConstructeurGenerique(TestCase):
    """Le constructeur sur des modèles réels : chaque branche qui compte."""

    @classmethod
    def setUpTestData(cls):
        cls.company = CompanyFactory(nom='QAH4 constructeur')
        cls.user = UserFactory(company=cls.company, role_legacy='admin')

    def _constructeur(self):
        return ts.Constructeur(self.company, self.user, ts.MARQUE_A)

    def test_modele_a_fk_company_seule(self):
        from apps.records.models import Tag
        tag = self._constructeur().objet(Tag)
        self.assertEqual(tag.company_id, self.company.pk)

    def test_chaine_de_fk_obligatoires_dans_la_meme_societe(self):
        """LigneDevis → Devis → Client : tout naît dans la société."""
        from django.apps import apps
        LigneDevis = apps.get_model('ventes', 'LigneDevis')
        ligne = self._constructeur().objet(LigneDevis)
        self.assertEqual(ligne.devis.company_id, self.company.pk)

    def test_les_champs_texte_portent_le_marqueur_de_la_societe(self):
        from django.apps import apps
        Client = apps.get_model('crm', 'Client')
        client = self._constructeur().objet(Client)
        self.assertTrue(client.nom.lower().startswith(ts.MARQUE_A))

    def test_company_et_utilisateur(self):
        from django.apps import apps
        from django.contrib.auth import get_user_model
        cons = self._constructeur()
        self.assertEqual(
            cons.objet(apps.get_model('authentication', 'Company')),
            self.company)
        user = cons.objet(get_user_model())
        self.assertEqual(user.company_id, self.company.pk)

    def test_les_parents_sont_reutilises(self):
        from django.apps import apps
        Devis = apps.get_model('ventes', 'Devis')
        cons = self._constructeur()
        premier = cons.objet(Devis)
        second = cons.objet(Devis)
        self.assertNotEqual(premier.pk, second.pk)
        self.assertEqual(premier.client_id, second.client_id)
