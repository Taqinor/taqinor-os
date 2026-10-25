"""ADEP29 - scripts/check_get_or_create.py : lecture seule, cles de contenu."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_get_or_create as guard  # noqa: E402 — après sys.path/setup() (D-ENF22)

APPEL = "def creer(a):\n    return Foo.objects.get_or_create(nom=a)\n"


class Depot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = self.tmp / "backend" / "django_core" / "apps" / "x"
        self.app.mkdir(parents=True)
        (self.tmp / "docs").mkdir()
        self.sauve = (guard.ROOT, guard.DJANGO_CORE, guard.APPS_DIR, guard.AUDIT_DOC)
        guard.ROOT = self.tmp
        guard.DJANGO_CORE = self.tmp / "backend" / "django_core"
        guard.APPS_DIR = guard.DJANGO_CORE / "apps"
        guard.AUDIT_DOC = self.tmp / "docs" / "get-or-create-audit.md"
        self.addCleanup(self.restaurer)

    def restaurer(self):
        guard.ROOT, guard.DJANGO_CORE, guard.APPS_DIR, guard.AUDIT_DOC = self.sauve

    def source(self, contenu):
        (self.app / "svc.py").write_text(contenu, encoding="utf-8")

    def lancer(self, *args):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = guard.main(list(args))
        return code


class GetOrCreateTests(Depot):
    def test_second_passage_reste_rouge(self):
        self.source(APPEL)
        self.assertEqual(self.lancer(), 1)
        self.assertEqual(self.lancer(), 1)  # le premier passage n'a rien ecrit
        self.assertFalse(guard.AUDIT_DOC.exists())

    def test_write_regenere(self):
        self.source(APPEL)
        self.assertEqual(self.lancer("--write"), 0)
        self.assertTrue(guard.AUDIT_DOC.exists())
        self.assertIn("svc.py::creer::Foo", guard.AUDIT_DOC.read_text(encoding="utf-8"))
        self.assertEqual(self.lancer(), 0)

    def test_insertion_amont_sans_faux_nouveau(self):
        self.source(APPEL)
        self.lancer("--write")
        self.source("import os\n\n\n# commentaire\n" + APPEL)  # decale l'appel
        self.assertEqual(self.lancer(), 0)

    def test_decalage_de_ligne_ne_rougit_plus(self):
        """AMET100 : la fonction descend de 20 lignes -> la garde reste verte SANS regeneration (cle par symbole)."""
        self.source(APPEL)
        self.assertEqual(self.lancer("--write"), 0)
        avant = guard.AUDIT_DOC.read_text(encoding="utf-8")
        self.source("# ligne de remplissage\n" * 20 + APPEL)
        self.assertEqual(self.lancer(), 0)
        self.assertEqual(guard.AUDIT_DOC.read_text(encoding="utf-8"), avant)  # le registre n'a pas bouge
        self.assertEqual(guard.TYPE_DE_CLE, "par_symbole")

    def test_depot_reel_vert(self):
        self.restaurer()
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(guard.main([]), 0, sortie.getvalue()[-500:])


ENTETE = "from django.db import models\nfrom django.db.models import Q\n\n\n"


class UniciteTests(Depot):
    """ENF18 (tranche get_or_create) : un lookup adosse a une garantie d'unicite du modele cible
    sort du registre ; tout le reste (pas de garantie, condition illisible, NULL possible,
    modele introuvable) y reste."""

    def liste(self, modeles, appel, fichier_modeles="models.py"):
        """Ecrit modeles + appel, regenere le registre ; True si l'appel y est LISTE (non couvert)."""
        (self.app / fichier_modeles).write_text(ENTETE + modeles, encoding="utf-8")
        self.source(appel)
        self.assertEqual(self.lancer("--write"), 0)
        return "svc.py::" in guard.AUDIT_DOC.read_text(encoding="utf-8")

    def assertCouvert(self, modeles, appel, **kw):
        self.assertFalse(self.liste(modeles, appel, **kw), "attendu COUVERT (absent du registre)")

    def assertListe(self, modeles, appel, **kw):
        self.assertTrue(self.liste(modeles, appel, **kw), "attendu LISTE (non couvert)")

    # -- formes de garantie reconnues -------------------------------------------------------
    def test_champ_unique_true(self):
        self.assertCouvert("class Foo(models.Model):\n    code = models.CharField(unique=True)\n",
                           "def creer(a):\n    return Foo.objects.get_or_create(code=a)\n")

    def test_cle_primaire_et_one_to_one(self):
        self.assertCouvert("class Foo(models.Model):\n    ref = models.CharField(primary_key=True)\n",
                           "def creer(a):\n    return Foo.objects.get_or_create(ref=a)\n")
        self.assertCouvert("class Foo(models.Model):\n    user = models.OneToOneField('x.U', models.CASCADE)\n",
                           "def creer(u):\n    return Foo.objects.update_or_create(user=u, defaults={'n': 1})\n")

    def test_unique_together_toutes_formes(self):
        for forme in ("[('company', 'nom')]", "(('company', 'nom'),)", "('company', 'nom')",
                      "[['company', 'nom']]"):
            with self.subTest(forme=forme):
                self.assertCouvert(
                    "class Foo(models.Model):\n    class Meta:\n        unique_together = " + forme + "\n",
                    "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a)\n")

    def test_unique_constraint_multiligne(self):
        modeles = ("class Foo(models.Model):\n    class Meta:\n        constraints = [\n"
                   "            models.UniqueConstraint(\n                fields=['company', 'nom'],\n"
                   "                name='uniq_foo'),\n        ]\n")
        self.assertCouvert(modeles, "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a)\n")

    def test_suffixe_id_equivaut_au_champ(self):
        modeles = ("class Foo(models.Model):\n    class Meta:\n        unique_together = [('company', 'nom')]\n")
        self.assertCouvert(modeles, "def creer(c, a):\n    return Foo.objects.get_or_create(company_id=c, nom=a)\n")
        modeles = ("class Foo(models.Model):\n    class Meta:\n        unique_together = [('company_id', 'nom')]\n")
        self.assertCouvert(modeles, "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a)\n")

    def test_lookup_plus_large_que_la_contrainte_reste_couvert(self):
        modeles = "class Foo(models.Model):\n    class Meta:\n        unique_together = [('company', 'nom')]\n"
        self.assertCouvert(
            modeles, "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a, actif=True)\n")

    def test_pk_toujours_unique_meme_modele_inconnu(self):
        self.assertCouvert("", "def creer(a):\n    return Inconnu.objects.get_or_create(pk=a)\n")

    # -- ce qui reste signale ---------------------------------------------------------------
    def test_lookup_non_couvert_reste_signale(self):
        modeles = "class Foo(models.Model):\n    class Meta:\n        unique_together = [('company', 'nom')]\n"
        # il manque `company` ; autre champ ; contrainte absente ; lookup `__iexact` (pas un champ exact)
        self.assertListe(modeles, "def creer(a):\n    return Foo.objects.get_or_create(nom=a)\n")
        self.assertListe(modeles, "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, code=a)\n")
        self.assertListe(modeles, "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom__iexact=a)\n")
        self.assertListe("class Foo(models.Model):\n    nom = models.CharField()\n",
                         "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a)\n")

    def test_modele_introuvable_ou_non_resolu_reste_signale(self):
        modeles = "class Foo(models.Model):\n    code = models.CharField(unique=True)\n"
        self.assertListe(modeles, "def creer(a):\n    return Absent.objects.get_or_create(code=a)\n")
        self.assertListe(modeles, "def creer(modele, a):\n    return modele.objects.get_or_create(code=a)\n")
        self.assertListe(modeles, "def creer(obj, a):\n    return obj.relation.get_or_create(code=a)\n")
        self.assertListe(modeles, "def creer(a):\n    return Foo.objects.filter(x=1).get_or_create(code=a)\n")

    def test_classe_qui_n_est_pas_un_modele_n_est_pas_indexee(self):
        self.assertListe("class Foo:\n    code = models.CharField(unique=True)\n",
                         "def creer(a):\n    return Foo.objects.get_or_create(code=a)\n")

    # -- contraintes partielles -------------------------------------------------------------
    def partielle(self, condition):
        return ("class Foo(models.Model):\n    class Meta:\n        constraints = [\n"
                "            models.UniqueConstraint(fields=['company', 'nom'], name='u', condition="
                + condition + "),\n        ]\n")

    def test_contrainte_partielle_couvre_si_la_condition_est_reprise_dans_le_lookup(self):
        appel = "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a, actif=True)\n"
        self.assertCouvert(self.partielle("Q(actif=True)"), appel)
        self.assertCouvert(self.partielle("Q(actif=True) & Q(deleted_at__isnull=True)"),
                           "def creer(c, a):\n    return Foo.objects.get_or_create("
                           "company=c, nom=a, actif=True, deleted_at__isnull=True)\n")

    def test_contrainte_partielle_ne_couvre_pas_un_lookup_qui_peut_sortir_de_la_condition(self):
        sans = "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a)\n"
        autre = "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a, actif=False)\n"
        variable = "def creer(c, a, v):\n    return Foo.objects.get_or_create(company=c, nom=a, actif=v)\n"
        self.assertListe(self.partielle("Q(actif=True)"), sans)
        self.assertListe(self.partielle("Q(actif=True)"), autre)
        self.assertListe(self.partielle("Q(actif=True)"), variable)

    def test_condition_illisible_n_est_jamais_comptee(self):
        appel = "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a, actif=True)\n"
        for condition in ("~Q(nom='', actif=False)", "Q(actif=True) | Q(nom='x')", "Q(actif=True, _connector='OR')"):
            with self.subTest(condition=condition):
                self.assertListe(self.partielle(condition), appel)

    # -- valeurs NULL -----------------------------------------------------------------------
    def test_litteral_none_n_epingle_pas_le_champ(self):
        modeles = "class Foo(models.Model):\n    class Meta:\n        unique_together = [('company', 'nom')]\n"
        self.assertListe(modeles, "def creer(a):\n    return Foo.objects.get_or_create(company=None, nom=a)\n")

    def test_champ_nullable_de_contrainte_exige_une_constante(self):
        modeles = ("class Foo(models.Model):\n    owner = models.ForeignKey('x.U', models.CASCADE, null=True)\n"
                   "    class Meta:\n        unique_together = [('company', 'owner')]\n")
        self.assertListe(modeles, "def creer(c, o):\n    return Foo.objects.get_or_create(company=c, owner_id=o)\n")
        self.assertCouvert(modeles, "def creer(c):\n    return Foo.objects.get_or_create(company=c, owner_id=7)\n")

    def test_company_nullable_historique_reste_couvert_avec_une_variable(self):
        modeles = ("class Foo(models.Model):\n    company = models.ForeignKey('x.C', models.CASCADE, null=True)\n"
                   "    class Meta:\n        unique_together = [('company', 'nom')]\n")
        self.assertCouvert(modeles, "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a)\n")

    # -- valeur PROUVEE non nulle par un garde-fou (ENF18) -----------------------------------
    MODELE_OWNER = ("class Foo(models.Model):\n"
                    "    owner = models.ForeignKey('x.U', models.CASCADE, null=True)\n"
                    "    class Meta:\n        unique_together = [('company', 'owner')]\n")
    CREER = "def creer(c, o, autre, journal):\n"
    APPEL_OWNER = "Foo.objects.get_or_create(company=c, owner_id=o)\n"

    def test_garde_fou_prouve_la_valeur_nullable(self):
        a = self.APPEL_OWNER
        formes = (
            "    if o is None:\n        return None\n    return " + a,
            "    if not o:\n        raise ValueError('o')\n    return " + a,
            "    if autre is None or o is None:\n        return None\n    return " + a,
            "    if not autre or not o:\n        return None\n    return " + a,
            "    if o is not None:\n        return " + a,
            "    if o:\n        return " + a,
            "    if o is not None and autre:\n        return " + a,
            "    assert o is not None\n    return " + a,
            "    if o is None:\n        journal()\n    else:\n        return " + a,
            "    for x in autre:\n        if o is None:\n            continue\n        " + a,
            "    if o is None:\n        return None\n    with journal:\n        return " + a,
            "    if o is None:\n        return None\n    try:\n        return " + a
            + "    except KeyError:\n        return None\n",
        )
        for corps in formes:
            with self.subTest(corps=corps):
                self.assertCouvert(self.MODELE_OWNER, self.CREER + corps)

    def test_sans_preuve_la_valeur_nullable_reste_signalee(self):
        a = self.APPEL_OWNER
        formes = (
            "    return " + a,
            "    if o is None:\n        journal()\n    return " + a,              # le garde-fou ne sort pas
            "    if o is None:\n        return None\n    o = autre\n    return " + a,   # reaffecte
            "    if o is None:\n        return None\n    for o in autre:\n        " + a,  # boucle reaffecte
            "    if autre is None:\n        return None\n    return " + a,           # autre variable
            "    if o is not None:\n        journal()\n    return " + a,             # appel hors du bloc
            "    if o is None and autre:\n        return None\n    return " + a,     # `and` ne prouve rien au faux
            "    if o is None:\n        return None\n    return Foo.objects.get_or_create(company=c, owner_id=o.pk)\n",
            "    if o is None:\n        return None\n    return lambda: " + a,         # s'execute plus tard
            "    def interne():\n        return " + a
            + "    if o is None:\n        return None\n    return interne()\n",
        )
        for corps in formes:
            with self.subTest(corps=corps):
                self.assertListe(self.MODELE_OWNER, self.CREER + corps)

    def test_condition_negee_satisfaite_par_une_valeur_prouvee(self):
        non_vide = ("class Foo(models.Model):\n    phase = models.CharField(max_length=9, blank=True, default='')\n"
                    "    class Meta:\n        constraints = [\n            models.UniqueConstraint(\n"
                    "                fields=['company', 'phase'], name='u', condition=~Q(phase='')),\n        ]\n")
        appel = "    return Foo.objects.get_or_create(company=c, phase=p)\n"
        self.assertCouvert(non_vide, "def creer(c, p):\n    if not p:\n        return None\n" + appel)
        self.assertListe(non_vide, "def creer(c, p):\n" + appel)
        # non nul n'est pas non vide : `if p is None` ne prouve pas `~Q(phase='')`
        self.assertListe(non_vide, "def creer(c, p):\n    if p is None:\n        return None\n" + appel)
        self.assertCouvert(non_vide, "def creer(c):\n    return Foo.objects.get_or_create(company=c, phase='pose')\n")
        self.assertListe(non_vide, "def creer(c):\n    return Foo.objects.get_or_create(company=c, phase='')\n")

    def test_conjonction_isnull_et_vide_exige_une_valeur_non_nulle_et_non_vide(self):
        modeles = ("class Foo(models.Model):\n    cle = models.CharField(max_length=9, null=True, blank=True)\n"
                   "    class Meta:\n        constraints = [\n            models.UniqueConstraint(\n"
                   "                fields=['company', 'cle'], name='u',\n"
                   "                condition=~Q(cle__isnull=True) & ~Q(cle='')),\n        ]\n")
        appel = "    return Foo.objects.get_or_create(company=c, cle=k)\n"
        self.assertCouvert(modeles, "def creer(c, k):\n    if not k:\n        return None\n" + appel)
        self.assertListe(modeles, "def creer(c, k):\n    if k is None:\n        return None\n" + appel)  # peut etre ''
        self.assertListe(modeles, "def creer(c, k):\n" + appel)

    def test_condition_isnull_faux_positive_satisfaite_par_une_valeur_non_nulle(self):
        modeles = ("class Foo(models.Model):\n    cle = models.CharField(max_length=9, null=True, blank=True)\n"
                   "    class Meta:\n        constraints = [\n            models.UniqueConstraint(\n"
                   "                fields=['company', 'cle'], name='u', condition=Q(cle__isnull=False)),\n        ]\n")
        appel = "    return Foo.objects.get_or_create(company=c, cle=k)\n"
        self.assertCouvert(modeles, "def creer(c, k):\n    if k is None:\n        return None\n" + appel)
        self.assertListe(modeles, "def creer(c, k):\n" + appel)
        # `Q(cle__isnull=True)` n'est pas satisfait par une valeur non nulle
        nulle = modeles.replace("isnull=False", "isnull=True")
        self.assertListe(nulle, "def creer(c, k):\n    if k is None:\n        return None\n" + appel)

    # -- heritage ---------------------------------------------------------------------------
    def test_champ_unique_herite_d_une_base_abstraite(self):
        modeles = ("class Base(models.Model):\n    code = models.CharField(unique=True)\n"
                   "    class Meta:\n        abstract = True\n\n\n"
                   "class Foo(Base):\n    pass\n")
        self.assertCouvert(modeles, "def creer(a):\n    return Foo.objects.get_or_create(code=a)\n")

    def test_meta_herite_sans_meta_propre_ou_via_base_meta(self):
        base = ("class Base(models.Model):\n    class Meta:\n        abstract = True\n"
                "        unique_together = [('company', 'nom')]\n\n\n")
        appel = "def creer(c, a):\n    return Foo.objects.get_or_create(company=c, nom=a)\n"
        self.assertCouvert(base + "class Foo(Base):\n    pass\n", appel)
        self.assertCouvert(base + "class Foo(Base):\n    class Meta(Base.Meta):\n        ordering = ['nom']\n", appel)
        # un Meta propre qui N'etend PAS Base.Meta remplace celui de la base (regle Django)
        self.assertListe(base + "class Foo(Base):\n    class Meta:\n        ordering = ['nom']\n", appel)

    # -- recepteurs -------------------------------------------------------------------------
    def test_recepteurs_resolus(self):
        modeles = "class Foo(models.Model):\n    code = models.CharField(unique=True)\n"
        (self.app / "models.py").write_text(ENTETE + modeles, encoding="utf-8")
        for appel in (
            "def a(v):\n    return Foo.objects.select_for_update().get_or_create(code=v)\n",
            "def a(v):\n    return Foo.objects.using('x').all().get_or_create(code=v)\n",
            "def a(v):\n    return models.Foo.objects.get_or_create(code=v)\n",
            "from x.models import Foo as F\n\n\ndef a(v):\n    return F.objects.get_or_create(code=v)\n",
            "def a(v):\n    from .models import Foo as F\n    return F.objects.get_or_create(code=v)\n",
        ):
            with self.subTest(appel=appel):
                self.assertCouvert(modeles, appel)

    def test_cls_et_self_class_dans_un_modele(self):
        classe = ("class Foo(models.Model):\n    code = models.CharField(unique=True)\n\n"
                  "    @classmethod\n    def un(cls, v):\n        return cls.objects.get_or_create(code=v)\n\n"
                  "    def deux(self, v):\n        return self.__class__.objects.get_or_create(code=v)\n\n"
                  "    def trois(self, v):\n        return type(self).objects.get_or_create(code=v)\n")
        (self.app / "svc.py").write_text(ENTETE + classe, encoding="utf-8")
        self.assertEqual(self.lancer("--write"), 0)
        self.assertNotIn("svc.py::", guard.AUDIT_DOC.read_text(encoding="utf-8"))
        # la meme forme dans une classe NON modele n'est pas couverte
        (self.app / "svc.py").write_text("class Service:\n    @classmethod\n    def un(cls, v):\n"
                                         "        return cls.objects.get_or_create(code=v)\n", encoding="utf-8")
        self.assertEqual(self.lancer("--write"), 0)
        self.assertIn("svc.py::Service.un::cls", guard.AUDIT_DOC.read_text(encoding="utf-8"))

    # -- homonymes entre apps ---------------------------------------------------------------
    def autre_app(self):
        autre = guard.APPS_DIR / "y"
        autre.mkdir()
        return autre

    def test_homonyme_l_app_d_import_absolu_departage(self):
        (self.autre_app() / "models.py").write_text(
            ENTETE + "class Role(models.Model):\n    class Meta:\n        unique_together = [('company', 'nom')]\n",
            encoding="utf-8")
        self.app.joinpath("models.py").write_text(
            ENTETE + "class Role(models.Model):\n    nom = models.CharField()\n", encoding="utf-8")
        appel = "def creer(c, a):\n    return Role.objects.get_or_create(company=c, nom=a)\n"
        # sans indice : la classe de l'app appelante (x) fait foi -> non couvert
        self.source(appel)
        self.assertEqual(self.lancer("--write"), 0)
        self.assertIn("svc.py::", guard.AUDIT_DOC.read_text(encoding="utf-8"))
        # import absolu depuis apps.y -> la classe de y fait foi -> couvert
        self.source("from apps.y.models import Role\n\n\n" + appel)
        self.assertEqual(self.lancer("--write"), 0)
        self.assertNotIn("svc.py::", guard.AUDIT_DOC.read_text(encoding="utf-8"))

    def test_homonyme_sans_indice_exige_que_toutes_les_classes_couvrent(self):
        for app in ("y", "z"):
            (guard.APPS_DIR / app).mkdir()
        (guard.APPS_DIR / "y" / "models.py").write_text(
            ENTETE + "class Role(models.Model):\n    class Meta:\n        unique_together = [('company', 'nom')]\n",
            encoding="utf-8")
        (guard.APPS_DIR / "z" / "models.py").write_text(
            ENTETE + "class Role(models.Model):\n    nom = models.CharField()\n", encoding="utf-8")
        self.source("def creer(c, a):\n    return Role.objects.get_or_create(company=c, nom=a)\n")
        self.assertEqual(self.lancer("--write"), 0)
        self.assertIn("svc.py::", guard.AUDIT_DOC.read_text(encoding="utf-8"))

    def test_modele_hors_models_py_dans_core(self):
        core = guard.DJANGO_CORE / "core"
        core.mkdir()
        (core / "idempotency.py").write_text(
            ENTETE + "class Trace(models.Model):\n    cle = models.CharField(unique=True)\n", encoding="utf-8")
        self.source("from core.idempotency import Trace\n\n\n"
                    "def creer(a):\n    return Trace.objects.get_or_create(cle=a)\n")
        self.assertEqual(self.lancer("--write"), 0)
        self.assertNotIn("svc.py::", guard.AUDIT_DOC.read_text(encoding="utf-8"))

    # -- le registre ne liste que le non couvert --------------------------------------------
    def test_appel_couvert_nouveau_ne_rougit_pas_et_n_entre_pas_au_registre(self):
        (self.app / "models.py").write_text(
            ENTETE + "class Foo(models.Model):\n    code = models.CharField(unique=True)\n", encoding="utf-8")
        self.source("def creer(a):\n    return Foo.objects.get_or_create(code=a)\n")
        self.assertEqual(self.lancer(), 0)  # aucun registre, appel couvert : vert
        self.assertFalse(guard.AUDIT_DOC.exists())

    def test_contrainte_retiree_fait_rougir_l_appel(self):
        (self.app / "models.py").write_text(
            ENTETE + "class Foo(models.Model):\n    code = models.CharField(unique=True)\n", encoding="utf-8")
        self.source("def creer(a):\n    return Foo.objects.get_or_create(code=a)\n")
        self.assertEqual(self.lancer(), 0)
        (self.app / "models.py").write_text(
            ENTETE + "class Foo(models.Model):\n    code = models.CharField()\n", encoding="utf-8")
        self.assertEqual(self.lancer(), 1)


if __name__ == "__main__":
    unittest.main()
