"""AUD417 — AUCUN `ModelAdmin` à FK `company` ne liste plus toutes les sociétés.

LE TROU. AUD185 avait posé le mixin `core.admin_scoping.CompanyScopedAdminMixin`
mais ne l'avait appliqué qu'à `ventes` et `compta` ; `stock` (AUD215) était
resté sur `admin.ModelAdmin` nu. Les 18 autres `admin.py` du dépôt n'avaient
AUCUN scope — dont `paie/admin.py` (`BulletinPaieAdmin` expose `brut` /
`net_a_payer`, cherchables par nom d'employé) et `rh/admin.py`
(`DossierEmployeAdmin` / `DocumentEmployeAdmin`, dossiers RH et pièces
personnelles). Un superutilisateur RATTACHÉ À UNE SOCIÉTÉ y voyait, sur une
seule page, les salaires et dossiers RH de TOUTES les sociétés clientes.

CADRAGE HONNÊTE (même adjudication qu'AUD185) : l'acteur est un superuser —
aucune `auth.Permission` n'est attribuée dans ce dépôt, donc un simple
`is_staff` obtient un index d'admin vide. C'est de la défense en profondeur
(RGPD / confidentialité), pas une brèche tenant prouvée.

CE TEST EST LA GARDE TRANSVERSE demandée par la tâche : il itère
`admin.site._registry` — donc TOUT `ModelAdmin` ajouté demain, dans n'importe
quelle app — et échoue pour celui dont le modèle porte un FK `company` sans
base scopée. Aucune liste de modèles n'est écrite à la main ici : elle
dériverait.

Lancer :
    docker compose exec django_core python manage.py test \
        tests.test_aud417_admin_scoping_transverse -v 2
"""
from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from django.test import RequestFactory, SimpleTestCase

from core.admin_scoping import CompanyScopedAdminMixin

#: Bases de scoping ALTERNATIVES tolérées, avec leur justification. Une entrée
#: ici est un choix explicite, revu comme du code — jamais un contournement.
#:
#: * `gestion_projet._AdminScopeSociete` (AUD315) est une base PLUS STRICTE que
#:   le mixin partagé : superutilisateur = tout, compte sans société = RIEN
#:   (fail-closed), plus des permissions objet par ligne. La reformuler sur le
#:   mixin changerait sa sémantique sans rien gagner ; elle scope déjà.
BASES_SCOPEES_ALTERNATIVES = ('_AdminScopeSociete',)


def _porte_fk_company(model):
    try:
        champ = model._meta.get_field('company')
    except (FieldDoesNotExist, AttributeError):
        return False
    return bool(getattr(champ, 'is_relation', False))


def _surcharge_get_queryset(model_admin):
    """Vrai si un ancêtre autre que `ModelAdmin` redéfinit `get_queryset`."""
    return type(model_admin).get_queryset is not admin.ModelAdmin.get_queryset


def _admins_a_scoper():
    return [(modele, adm) for modele, adm in admin.site._registry.items()
            if _porte_fk_company(modele)]


class _Utilisateur:
    """Utilisateur minimal (aucune requête base) pour sonder le filtrage."""

    is_authenticated = True

    def __init__(self, company_id=None, is_superuser=True):
        self.company_id = company_id
        self.is_superuser = is_superuser
        self.is_staff = True
        self.is_active = True


def _requete(company_id):
    requete = RequestFactory().get('/admin/')
    requete.user = _Utilisateur(company_id=company_id)
    return requete


class AucunAdminNonScopeNeSubsiste(SimpleTestCase):
    """La garde transverse — elle couvre les apps existantes ET futures."""

    def test_tout_modeladmin_a_fk_company_est_scope(self):
        non_scopes = sorted(
            f'{modele._meta.app_label}.{modele.__name__}'
            f' ({type(adm).__name__})'
            for modele, adm in _admins_a_scoper()
            if not _surcharge_get_queryset(adm))
        self.assertEqual(
            non_scopes, [],
            "ces ModelAdmin listent les lignes de TOUTES les sociétés : "
            "faites-les hériter de core.admin_scoping.CompanyScopedAdminMixin "
            "(patron : la classe CompanyScopedAdmin en tête de chaque "
            f"admin.py migré par AUD417). Concernés : {non_scopes}")

    def test_le_mixin_partage_est_le_vehicule_par_defaut(self):
        """Un scope maison est toléré s'il est DOCUMENTÉ ci-dessus."""
        exotiques = sorted(
            f'{modele._meta.app_label}.{modele.__name__}'
            for modele, adm in _admins_a_scoper()
            if not isinstance(adm, CompanyScopedAdminMixin)
            and not any(base.__name__ in BASES_SCOPEES_ALTERNATIVES
                        for base in type(adm).__mro__))
        self.assertEqual(
            exotiques, [],
            'scope société maison non documenté : réutilisez le mixin '
            'partagé, ou ajoutez la base à BASES_SCOPEES_ALTERNATIVES avec '
            f'sa justification. Concernés : {exotiques}')

    def test_le_perimetre_nest_pas_vide(self):
        """Non-vacuité : la garde porte bien sur des dizaines de modèles."""
        self.assertGreater(len(_admins_a_scoper()), 100)


class LesDeuxSurfacesLesPlusSensiblesSontFiltrees(SimpleTestCase):
    """Le `Done =` nommé par la tâche : paie et RH, en priorité."""

    CIBLES = (('paie', 'BulletinPaie'), ('rh', 'DossierEmploye'),
              ('rh', 'DocumentEmploye'))

    def _admin_de(self, app_label, nom_modele):
        from django.apps import apps as registre_apps
        try:
            modele = registre_apps.get_model(app_label, nom_modele)
        except LookupError:  # app parquée par l'édition (SOL3)
            return None
        return admin.site._registry.get(modele)

    def test_les_surfaces_paie_et_rh_sont_scopees(self):
        vues = 0
        for app_label, nom_modele in self.CIBLES:
            adm = self._admin_de(app_label, nom_modele)
            if adm is None:
                continue
            vues += 1
            with self.subTest(modele=f'{app_label}.{nom_modele}'):
                self.assertTrue(
                    isinstance(adm, CompanyScopedAdminMixin),
                    f'{app_label}.{nom_modele} : la liste des salaires / '
                    "dossiers RH doit être bornée à la société de l'appelant.")
        self.assertTrue(vues, 'aucune des surfaces ciblées n\'est montée.')

    def test_le_filtre_est_reellement_applique(self):
        """Comportemental, sans base : le WHERE gagne une clause société."""
        adm = self._admin_de('paie', 'BulletinPaie')
        if adm is None:
            self.skipTest('paie parquée par l\'édition courante')
        avec = adm.get_queryset(_requete(company_id=42))
        sans = adm.get_queryset(_requete(company_id=None))
        self.assertGreater(
            len(avec.query.where.children), len(sans.query.where.children),
            'aucune clause de société ajoutée : le mixin ne filtre pas.')

    def test_un_compte_sans_societe_garde_le_comportement_historique(self):
        """Opérateur plateforme (`company` NULL) : aucun filtre, comme avant."""
        adm = self._admin_de('paie', 'BulletinPaie')
        if adm is None:
            self.skipTest('paie parquée par l\'édition courante')
        sans = adm.get_queryset(_requete(company_id=None))
        self.assertEqual(len(sans.query.where.children), 0)
