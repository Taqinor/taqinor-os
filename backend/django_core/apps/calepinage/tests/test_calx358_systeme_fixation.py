"""CALX358 — le catalogue de systèmes de fixation DANS le module.

Ce qui est prouvé ici :

* ``SystemeFixation`` et ``ComposantFixation`` sont des ``TenantModel``
  (FK ``company``), nés dans la migration ADDITIVE ``0014`` qui les NOMME
  tous deux et n'écrit AUCUNE donnée — catalogue vide par défaut, donc
  comportement d'aujourd'hui inchangé (D12) ;
* le vocabulaire des rôles est celui du contrat CALX335 ;
* un composant SANS source est refusé en NOMMANT ``source`` ; un système
  sans provenance en nommant ``provenance`` ;
* la règle de quantité SAISIE est validée (base connue ou ``role:<rôle>``,
  facteur/diviseur strictement positifs ou ``null`` = déclaré non saisi),
  chaque refus nommant ce qui ne va pas ;
* aucun import du module d'appels d'offres dans le catalogue, et
  ``services/kits.py`` ne lit pas le nouveau catalogue (D-CALX 2 : on
  PRÉPARE le remplacement de ``KitCalepinage``, on ne retire rien) ;
* en base : société neuve ⇒ aucun système ; un système d'une autre société
  est introuvable ; les composants sortent dans l'ordre du catalogue.

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx358_systeme_fixation -v2
"""
import ast
import json
import pathlib

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.calepinage.models import ComposantFixation, SystemeFixation
from apps.calepinage.services.catalogue_fixation import (
    BASES, erreur_de_regle,
)
from core.models import TenantModel
from django.test import TestCase
from apps.calepinage.services.catalogue_fixation import (
    composants_du_systeme, systeme_de_societe, systemes_actifs,
)
from authentication.models import Company

from .test_api_liste import BaseApiCalepinage

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = RACINE_APP / 'migrations' / '0014_calx358_systeme_fixation.py'
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_fixation_bom.json')
    .read_text(encoding='utf-8'))


def composant(**champs):
    valeurs = {'role': 'rail', 'libelle': 'Rail aluminium', 'unite': 'm',
               'source': 'Notice fabricant (essai), p. 4', 'regle': {}}
    valeurs.update(champs)
    return ComposantFixation(**valeurs)


class ModelesEtMigrationTest(SimpleTestCase):

    def test_deux_modeles_multi_societe(self):
        for modele in (SystemeFixation, ComposantFixation):
            with self.subTest(modele=modele.__name__):
                self.assertTrue(issubclass(modele, TenantModel))
                self.assertEqual(modele._meta.get_field('company')
                                 .related_model._meta.label,
                                 'authentication.Company')

    def test_migration_additive_nomme_les_deux_modeles(self):
        arbre = ast.parse(MIGRATION.read_text(encoding='utf-8'))
        creees, operations = [], []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and isinstance(
                    noeud.func, ast.Attribute):
                operations.append(noeud.func.attr)
                if noeud.func.attr == 'CreateModel':
                    for mot in noeud.keywords:
                        if mot.arg == 'name':
                            creees.append(mot.value.value)
        self.assertEqual(sorted(creees),
                         ['ComposantFixation', 'SystemeFixation'])
        for interdit in ('RunPython', 'RunSQL', 'RemoveField',
                         'DeleteModel', 'AlterField'):
            self.assertNotIn(interdit, operations)

    def test_roles_du_contrat(self):
        roles_contrat = {ligne['role']
                         for ligne in CONTRAT['exemple']['lignes']}
        self.assertTrue(roles_contrat <= set(ComposantFixation.Role.values))
        self.assertEqual(
            set(ComposantFixation.Role.values),
            {'rail', 'pince_milieu', 'pince_fin', 'crochet', 'embout',
             'lest', 'visserie'})

    def test_produit_opaque_jamais_une_fk_dure(self):
        champ = ComposantFixation._meta.get_field('produit_id')
        self.assertFalse(champ.is_relation)
        self.assertTrue(champ.null)


class RefusNommantLeChampTest(SimpleTestCase):

    def _refus(self, instance):
        with self.assertRaises(ValidationError) as refus:
            instance.clean()
        return refus.exception.message_dict

    def test_composant_sans_source(self):
        erreurs = self._refus(composant(source='  '))
        self.assertIn('source', erreurs)

    def test_composant_sans_libelle_ni_unite(self):
        erreurs = self._refus(composant(libelle='', unite=''))
        self.assertIn('libelle', erreurs)
        self.assertIn('unite', erreurs)

    def test_composant_complet_accepte(self):
        composant(regle={'base': 'longueur_rangees_m', 'facteur': 2,
                         'libelle_facteur': 'rails par rangée'}).clean()

    def test_systeme_sans_provenance(self):
        systeme = SystemeFixation(code='essai', libelle='Système d’essai',
                                  provenance='')
        self.assertIn('provenance', self._refus(systeme))

    def test_regle_invalide_nommee_regle(self):
        erreurs = self._refus(composant(regle={'base': 'surface'}))
        self.assertIn('regle', erreurs)


class RegleDeQuantiteTest(SimpleTestCase):
    """La règle SAISIE : un vocabulaire, aucun nombre inventé."""

    def test_regle_vide_recevable(self):
        self.assertEqual(erreur_de_regle({}), '')
        self.assertEqual(erreur_de_regle(None), '')

    def test_bases_du_document_et_reference_de_role(self):
        for base in list(BASES) + ['role:rail', 'role:crochet']:
            with self.subTest(base=base):
                self.assertEqual(erreur_de_regle({'base': base}), '')

    def test_bases_d_orientation_admises(self):
        # ACAL569 — portrait et paysage, par module et par rangée.
        for base in ('modules_portrait', 'modules_paysage',
                     'rangees_portrait', 'rangees_paysage'):
            with self.subTest(base=base):
                self.assertIn(base, BASES)
                self.assertEqual(erreur_de_regle({'base': base,
                                                  'facteur': 4}), '')

    def test_refus(self):
        cas = (
            ([], 'objet'),
            ({'base': 'modules', 'coef': 2}, 'coef'),
            ({'facteur': 2}, 'base'),
            ({'base': 'surface_toit'}, 'surface_toit'),
            ({'base': 'role:tuile'}, 'role:tuile'),
            ({'base': 'modules', 'facteur': -1}, 'facteur'),
            ({'base': 'modules', 'diviseur': 0}, 'diviseur'),
            ({'base': 'modules', 'facteur': True}, 'facteur'),
            ({'base': 'modules', 'facteur': '2'}, 'facteur'),
            ({'base': 'modules', 'libelle_facteur': 2}, 'libelle_facteur'),
        )
        for regle, nomme in cas:
            with self.subTest(regle=regle):
                message = erreur_de_regle(regle)
                self.assertTrue(message)
                self.assertIn(nomme, message)

    def test_parametre_declare_non_saisi_recevable(self):
        """``null`` = déclaré mais non saisi : la ligne sortira non calculée."""
        self.assertEqual(
            erreur_de_regle({'base': 'role:rail', 'diviseur': None,
                             'libelle_diviseur': 'entraxe (m)'}), '')


class CouverturesTest(SimpleTestCase):
    """ACAL566 — le vocabulaire des couvertures EST celui du lead."""

    def test_parite_avec_le_type_de_toiture_du_lead(self):
        from apps.calepinage.services.catalogue_fixation import COUVERTURES
        from apps.crm.models import Lead

        self.assertEqual(COUVERTURES, tuple(Lead.TypeToiture.values))

    def test_refus_nommes(self):
        from apps.calepinage.services.catalogue_fixation import (
            erreur_de_couvertures,
        )

        self.assertEqual(erreur_de_couvertures([]), '')
        self.assertEqual(erreur_de_couvertures(['tuiles', 'bac_acier']), '')
        self.assertIn('inconnue', erreur_de_couvertures(['ardoise']))
        self.assertIn('deux fois', erreur_de_couvertures(['tuiles', 'tuiles']))
        self.assertIn('liste', erreur_de_couvertures('tuiles'))


class DecouplageTest(SimpleTestCase):
    """D-CALX 2 — on PRÉPARE le remplacement de KitCalepinage, rien de plus."""

    def test_catalogue_sans_import_du_module_d_appels_d_offres(self):
        texte = (RACINE_APP / 'services' / 'catalogue_fixation.py').read_text(
            encoding='utf-8')
        arbre = ast.parse(texte)
        modules = [noeud.module or '' for noeud in ast.walk(arbre)
                   if isinstance(noeud, ast.ImportFrom)]
        modules += [alias.name for noeud in ast.walk(arbre)
                    if isinstance(noeud, ast.Import) for alias in noeud.names]
        self.assertFalse([m for m in modules
                          if m.startswith(('apps.ao', 'apps.ged'))])

    def test_kits_ne_lit_pas_le_nouveau_catalogue(self):
        texte = (RACINE_APP / 'services' / 'kits.py').read_text(
            encoding='utf-8')
        self.assertNotIn('SystemeFixation', texte)
        self.assertNotIn('catalogue_fixation', texte)


# ── ORM — la CI est la gate de ces classes ─────────────────────────────────


class CatalogueEnBase(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='Fixation Co',
                                              slug='fixation-co-358')
        self.autre = Company.objects.create(nom='Voisine Fixation',
                                            slug='voisine-fixation-358')

    def _systeme(self, company, code='incline', actif=True):
        return SystemeFixation.objects.create(
            company=company, code=code, libelle=f'Système {code}',
            provenance='Notice fabricant (essai)', actif=actif)

    def test_societe_neuve_sans_catalogue(self):
        self.assertEqual(systemes_actifs(self.company), [])

    def test_systemes_actifs_seulement(self):
        actif = self._systeme(self.company, 'a')
        self._systeme(self.company, 'b', actif=False)
        self._systeme(self.autre, 'c')
        self.assertEqual(systemes_actifs(self.company), [actif])

    def test_systeme_d_une_autre_societe_introuvable(self):
        etranger = self._systeme(self.autre)
        self.assertIsNone(systeme_de_societe(self.company, etranger.pk))
        self.assertIsNone(systeme_de_societe(self.company, 'abc'))

    def test_meme_code_dans_deux_societes(self):
        self._systeme(self.company, 'incline')
        self._systeme(self.autre, 'incline')

    def test_composants_dans_l_ordre_du_catalogue(self):
        systeme = self._systeme(self.company)
        second = ComposantFixation.objects.create(
            company=self.company, systeme=systeme, role='crochet',
            libelle='Crochet', unite='u', source='Notice', ordre=2)
        premier = ComposantFixation.objects.create(
            company=self.company, systeme=systeme, role='rail',
            libelle='Rail', unite='m', source='Notice', ordre=1)
        self.assertEqual(composants_du_systeme(systeme), [premier, second])

    def test_full_clean_refuse_un_composant_sans_source(self):
        systeme = self._systeme(self.company)
        instance = ComposantFixation(company=self.company, systeme=systeme,
                                     role='rail', libelle='Rail', unite='m',
                                     source='')
        with self.assertRaises(ValidationError) as refus:
            instance.full_clean()
        self.assertIn('source', refus.exception.message_dict)

    def test_systeme_d_une_autre_societe_refuse_au_composant(self):
        etranger = self._systeme(self.autre)
        instance = ComposantFixation(company=self.company, systeme=etranger,
                                     role='rail', libelle='Rail', unite='m',
                                     source='Notice')
        with self.assertRaises(ValidationError) as refus:
            instance.clean()
        self.assertIn('systeme', refus.exception.message_dict)


# ── ACAL558 — le catalogue servi en HTTP ────────────────────────────────────

URL_SYSTEMES = '/api/django/calepinage/calepinages/systemes-fixation/'
CONTRAT_SYSTEMES = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_systemes_fixation.json')
    .read_text(encoding='utf-8'))


def _corps(**champs):
    corps = json.loads(json.dumps(
        CONTRAT_SYSTEMES['exemple_creation']['corps']))
    corps.update(champs)
    return corps


class CatalogueEnHttp(BaseApiCalepinage):
    """ACAL558 — liste, création, modification, suppression ; société et
    droits lus côté serveur."""

    def setUp(self):
        from apps.roles.models import Role
        from django.contrib.auth import get_user_model

        super().setUp()
        self.role_lecteur = Role.objects.create(
            company=self.company, nom='Lecteur calepinage',
            permissions=['calepinage_voir'])
        lecteur = get_user_model().objects.create_user(
            username='cal_lecteur_558', password='x', company=self.company,
            role=self.role_lecteur)
        self.api_lecteur = self._client(lecteur)

    def _creer(self, **champs):
        reponse = self.api.post(URL_SYSTEMES, _corps(**champs), format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return reponse.data['systeme']

    def test_creation_a_la_forme_du_contrat(self):
        systeme = self._creer()
        attendu = CONTRAT_SYSTEMES['exemple_creation']['reponse']['systeme']
        self.assertEqual(set(systeme), set(attendu))
        self.assertEqual([c['role'] for c in systeme['composants']],
                         ['rail', 'lest'])
        self.assertEqual([c['ordre'] for c in systeme['composants']], [0, 1])
        liste = self.api.get(URL_SYSTEMES)
        self.assertEqual(liste.status_code, 200, liste.data)
        self.assertEqual([s['id'] for s in liste.data['systemes']],
                         [systeme['id']])

    def test_post_sans_provenance_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(URL_SYSTEMES, _corps(provenance=''),
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('provenance', reponse.data)
        self.assertIn('provenance du système est obligatoire',
                      reponse.data['provenance'][0])
        self.assertFalse(SystemeFixation.objects.exists())

    def test_composant_sans_source_n_ecrit_aucun_systeme(self):
        corps = _corps()
        corps['composants'][1]['source'] = ''
        reponse = self.api.post(URL_SYSTEMES, corps, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('composants[1].source', reponse.data)
        self.assertFalse(SystemeFixation.objects.exists())
        self.assertFalse(ComposantFixation.objects.exists())

    def test_regle_invalide_et_code_en_double(self):
        self._creer()
        corps = _corps()
        corps['composants'][0]['regle'] = {'base': 'surface'}
        reponse = self.api.post(URL_SYSTEMES, corps, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(reponse.data['composants[0].regle'],
                         [erreur_de_regle({'base': 'surface'})])
        self.assertIn('code', reponse.data)

    def test_couvertures_acceptees_et_refusees_en_nommant_le_champ(self):
        # ACAL566 — clé additive du contrat.
        systeme = self._creer(couvertures=['tuiles'])
        self.assertEqual(systeme['couvertures'], ['tuiles'])
        reponse = self.api.post(URL_SYSTEMES,
                                _corps(code='autre', couvertures=['ardoise']),
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('couvertures', reponse.data)

    def test_company_du_corps_ignoree(self):
        systeme = self._creer(company=self.autre.pk)
        self.assertEqual(
            SystemeFixation.objects.get(pk=systeme['id']).company_id,
            self.company.pk)

    def test_autre_societe_liste_vide_et_detail_404(self):
        systeme = self._creer()
        self.assertEqual(self.api_autre.get(URL_SYSTEMES).data,
                         {'systemes': []})
        detail = f"{URL_SYSTEMES}{systeme['id']}/"
        self.assertEqual(self.api_autre.get(detail).status_code, 404)
        self.assertEqual(self.api_autre.delete(detail).status_code, 404)
        self.assertTrue(SystemeFixation.objects.filter(
            pk=systeme['id']).exists())

    def test_lecteur_lit_mais_n_ecrit_pas(self):
        systeme = self._creer()
        detail = f"{URL_SYSTEMES}{systeme['id']}/"
        self.assertEqual(self.api_lecteur.get(URL_SYSTEMES).status_code, 200)
        self.assertEqual(self.api_lecteur.get(detail).status_code, 200)
        self.assertEqual(self.api_lecteur.post(
            URL_SYSTEMES, _corps(code='autre'), format='json').status_code,
            403)
        self.assertEqual(self.api_lecteur.patch(
            detail, {'actif': False}, format='json').status_code, 403)
        self.assertEqual(self.api_lecteur.delete(detail).status_code, 403)

    def test_patch_remplace_les_composants_et_delete_libere_le_calepinage(
            self):
        from apps.calepinage.models import Calepinage

        systeme = self._creer()
        detail = f"{URL_SYSTEMES}{systeme['id']}/"
        corps = _corps()
        corps['composants'] = list(reversed(corps['composants']))
        reponse = self.api.patch(
            detail, {'actif': False, 'composants': corps['composants']},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['systeme']['actif'])
        self.assertEqual([c['role'] for c in
                          reponse.data['systeme']['composants']],
                         ['lest', 'rail'])
        self.assertEqual(ComposantFixation.objects.count(), 2)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa',
            systeme_fixation_id=systeme['id'])
        self.assertEqual(self.api.delete(detail).status_code, 204)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.systeme_fixation_id)
