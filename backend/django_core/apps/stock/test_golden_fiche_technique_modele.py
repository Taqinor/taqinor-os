"""SPL110 — golden du modèle fiche technique (capture seule).

``FicheTechnique`` et les deux validateurs de courbe CALX60 sont capturés tels
qu'ils sont AUJOURD'HUI dans ``stock/models.py`` : aucun code de production
n'est déplacé ni modifié par cette tâche. SPL113 déplacera le bloc vers
``models_fiche_technique.py`` et ce test doit rester VERT sans qu'on
régénère le JSON.

Le test s'importe par la FAÇADE ``apps.stock.models`` (jamais par le futur
module) : l'assertion rouge-d'abord ``FicheTechnique.__module__ ==
'apps.stock.models_fiche_technique'`` arrive dans SPL113.

Sections de ``golden/fiche_technique_modele.json`` :
  * ``ast``          — empreintes AST (outil ``golden/ast_fingerprint.py``) ;
  * ``validateurs``  — valeur de retour / message exact de chaque cas de
                       ``CAS_COURBES`` ;
  * ``meta``         — ``_meta`` du modèle (champs, db_table, ordering…).

Capture (UNE fois, sur le code actuel, jamais après le déplacement) :
    GOLDEN_CAPTURE=1 docker compose exec django_core python manage.py test \
        apps.stock.test_golden_fiche_technique_modele
Hors capture, une section absente du JSON fait ÉCHOUER le test.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.test_golden_fiche_technique_modele -v 2
"""
import hashlib
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import NOT_PROVIDED
from django.test import TestCase

from apps.stock.golden.ast_fingerprint import fingerprint, verifier_section
from apps.stock.models import (
    FicheTechnique, Produit,
    valider_courbe_irradiance, valider_courbe_rendement_onduleur)
# SPL113 — les deux privés ne sont pas ré-exportés par la façade (aucun usage
# hors bloc) : on les lit dans leur module.
from apps.stock.models_fiche_technique import _est_nombre, _valider_courbe
from authentication.models import Company

GOLDEN = 'fiche_technique_modele'

# Cas des deux validateurs de courbe. Chaque entrée : (id, validateur, valeur).
# ``irradiance`` / ``onduleur`` choisissent la fonction ; les valeurs
# n'utilisent que des littéraux (le script de capture hors Django les relit
# tels quels).
CAS_COURBES = [
    ('irr_valide', 'irradiance',
     [{'w_m2': 200, 'rendement_relatif_pct': 95.5},
      {'w_m2': 1000, 'rendement_relatif_pct': 100}]),
    ('irr_valide_decimal', 'irradiance',
     [{'w_m2': Decimal('200'), 'rendement_relatif_pct': Decimal('95.5')},
      {'w_m2': Decimal('1000'), 'rendement_relatif_pct': Decimal('100')}]),
    ('irr_liste_vide', 'irradiance', []),
    ('irr_abscisse_recule', 'irradiance',
     [{'w_m2': 800, 'rendement_relatif_pct': 99},
      {'w_m2': 200, 'rendement_relatif_pct': 95}]),
    ('irr_abscisse_repetee', 'irradiance',
     [{'w_m2': 200, 'rendement_relatif_pct': 95},
      {'w_m2': 600, 'rendement_relatif_pct': 98},
      {'w_m2': 600, 'rendement_relatif_pct': 99}]),
    ('irr_cle_absente', 'irradiance',
     [{'w_m2': 200, 'rendement_relatif_pct': 95}, {'w_m2': 1000}]),
    ('irr_booleen', 'irradiance',
     [{'w_m2': True, 'rendement_relatif_pct': 95}]),
    ('irr_none', 'irradiance', None),
    ('irr_chaine_vide', 'irradiance', ''),
    ('irr_pas_une_liste', 'irradiance', {'w_m2': 200}),
    ('irr_point_non_objet', 'irradiance', [[200, 95]]),
    ('ond_valide', 'onduleur',
     [{'charge_pct': 10, 'rendement_pct': 90},
      {'charge_pct': 50, 'rendement_pct': 97},
      {'charge_pct': 100, 'rendement_pct': 96.5}]),
    ('ond_par_tension_valide', 'onduleur',
     [{'charge_pct': 10, 'rendement_pct': 90, 'tension_v': 230},
      {'charge_pct': 10, 'rendement_pct': 88, 'tension_v': 400},
      {'charge_pct': 50, 'rendement_pct': 97, 'tension_v': 230},
      {'charge_pct': 50, 'rendement_pct': 96, 'tension_v': 400}]),
    ('ond_par_tension_recule', 'onduleur',
     [{'charge_pct': 50, 'rendement_pct': 97, 'tension_v': 230},
      {'charge_pct': 50, 'rendement_pct': 96, 'tension_v': 400},
      {'charge_pct': 20, 'rendement_pct': 93, 'tension_v': 230}]),
    ('ond_tension_non_numerique', 'onduleur',
     [{'charge_pct': 10, 'rendement_pct': 90, 'tension_v': 'haute'}]),
    ('ond_rendement_chaine', 'onduleur',
     [{'charge_pct': 10, 'rendement_pct': '90'}]),
    ('ond_none', 'onduleur', None),
]


def _executer(fonction, valeur):
    """Appelle un VRAI validateur : retour ou message exact de refus."""
    try:
        retour = fonction(valeur)
    except ValidationError as exc:
        return {'refus': True, 'messages': list(exc.messages)}
    return {'refus': False, 'retour': retour}


def _decrire_champ(champ):
    rel = getattr(champ, 'remote_field', None)
    defaut = champ.default
    if defaut is NOT_PROVIDED:
        defaut = None
    elif callable(defaut):
        defaut = 'callable:%s' % getattr(defaut, '__name__', repr(defaut))
    else:
        defaut = repr(defaut)
    validateurs = [
        getattr(v, '__name__', None) or type(v).__name__
        for v in champ.validators]
    return {
        'nom': champ.name,
        'classe': type(champ).__name__,
        'null': champ.null,
        'blank': champ.blank,
        'defaut': defaut,
        'max_length': getattr(champ, 'max_length', None),
        'max_digits': getattr(champ, 'max_digits', None),
        'decimal_places': getattr(champ, 'decimal_places', None),
        'validateurs': validateurs,
        'help_text_sha1': hashlib.sha1(
            str(champ.help_text).encode('utf-8')).hexdigest(),
        'related_name': getattr(rel, 'related_name', None) if rel else None,
        'on_delete': (rel.on_delete.__name__
                      if rel is not None and rel.on_delete else None),
    }


def _decrire_modele():
    meta = FicheTechnique._meta
    return {
        'db_table': meta.db_table,
        'ordering': list(meta.ordering),
        'verbose_name': str(meta.verbose_name),
        'verbose_name_plural': str(meta.verbose_name_plural),
        'constraints': [repr(c) for c in meta.constraints],
        'indexes': [repr(i) for i in meta.indexes],
        # Champs « avant » seulement : les relations inverses ajoutées par
        # d'autres apps ne sont pas la fiche.
        'champs': [_decrire_champ(f) for f in meta.get_fields()
                   if f.concrete],
    }


class GoldenFicheTechniqueModeleTests(TestCase):

    def test_spl113_bloc_vit_dans_models_fiche_technique(self):
        """SPL113 — le bloc a déménagé dans ``models_fiche_technique.py`` et
        la façade ``apps.stock.models`` ré-exporte LE MÊME objet (pas un
        jumeau)."""
        import importlib

        import apps.stock.models as facade
        module = importlib.import_module('apps.stock.models_fiche_technique')
        self.assertEqual(FicheTechnique.__module__,
                         'apps.stock.models_fiche_technique')
        self.assertIs(module.FicheTechnique, facade.FicheTechnique)
        for nom in ('valider_courbe_irradiance',
                    'valider_courbe_rendement_onduleur'):
            self.assertIs(getattr(module, nom), getattr(facade, nom))
        # Les deux privés ne sont PAS ré-exportés par la façade.
        self.assertFalse(hasattr(facade, '_est_nombre'))
        self.assertFalse(hasattr(facade, '_valider_courbe'))

    def test_empreintes_ast(self):
        """Empreintes AST des cinq symboles — indépendantes du fichier."""
        courant = {
            '_est_nombre': fingerprint(_est_nombre),
            '_valider_courbe': fingerprint(_valider_courbe),
            'valider_courbe_irradiance': fingerprint(
                valider_courbe_irradiance),
            'valider_courbe_rendement_onduleur': fingerprint(
                valider_courbe_rendement_onduleur),
            'FicheTechnique': fingerprint(FicheTechnique),
        }
        verifier_section(self, GOLDEN, 'ast', courant)

    def test_comportement_des_validateurs(self):
        """Les VRAIS validateurs (aucun mock) sur ~18 cas : retour ou message
        exact incluant l'index du point fautif."""
        fonctions = {
            'irradiance': valider_courbe_irradiance,
            'onduleur': valider_courbe_rendement_onduleur,
        }
        courant = {
            cid: _executer(fonctions[quel], valeur)
            for cid, quel, valeur in CAS_COURBES}
        # Garde de sens indépendante du JSON : un refus nomme son index.
        self.assertIn('index 1', ' '.join(
            courant['irr_abscisse_recule']['messages']))
        self.assertFalse(courant['irr_valide']['refus'])
        verifier_section(self, GOLDEN, 'validateurs', courant)

    def test_meta_du_modele(self):
        """db_table, ordering, constraints, indexes, verbose_name et, pour
        chaque champ, nom/classe/null/blank/défaut/longueurs/validateurs/
        help_text/related_name/on_delete."""
        verifier_section(self, GOLDEN, 'meta', _decrire_modele())

    def test_aucune_migration_a_creer(self):
        """``makemigrations --check --dry-run`` : code 0 (SystemExit absent),
        aucune migration créée — le modèle est déjà en phase avec l'état."""
        try:
            call_command('makemigrations', '--check', '--dry-run',
                         verbosity=0)
        except SystemExit as exc:  # pragma: no cover - échec attendu = rouge
            self.fail('makemigrations --check a rendu le code %r : le modèle '
                      'a dérivé de ses migrations.' % (exc.code,))

    def test_full_clean_et_str_par_type_de_fiche(self):
        """``full_clean()`` passe et ``str()`` rend « Fiche technique — <id> »
        pour une fiche de chaque ``TypeFiche`` (+ sans type) et pour une
        fiche à ``pdf`` legacy."""
        co = Company.objects.get_or_create(
            slug='spl110-golden-co', defaults={'nom': 'SPL110 Golden'})[0]
        types = [''] + [valeur for valeur, _ in
                        FicheTechnique.TypeFiche.choices]
        self.assertEqual(
            types, ['', 'module', 'onduleur', 'batterie', 'optimiseur',
                    'pompe', 'variateur_pompage',
                    # CIQ101 — choix C&I additifs.
                    'limiteur', 'logger', 'protection', 'cable', 'structure',
                    'autre'])
        for i, type_fiche in enumerate(types):
            produit = Produit.objects.create(
                company=co, nom='Produit SPL110 %d' % i,
                sku='SPL110-%d' % i, prix_achat=Decimal('100'),
                prix_vente=Decimal('150'), quantite_stock=1)
            fiche = FicheTechnique(
                company=co, produit=produit, type_fiche=type_fiche)
            fiche.full_clean()
            fiche.save()
            self.assertEqual(
                str(fiche), 'Fiche technique — %s' % produit.pk)
        legacy = Produit.objects.create(
            company=co, nom='Produit SPL110 legacy', sku='SPL110-LEG',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=1)
        fiche = FicheTechnique(
            company=co, produit=legacy, type_fiche='module',
            pdf='stock/fiches_techniques/2026/01/legacy.pdf')
        fiche.full_clean()
        fiche.save()
        fiche.refresh_from_db()
        self.assertEqual(fiche.pdf.name,
                         'stock/fiches_techniques/2026/01/legacy.pdf')
        self.assertEqual(fiche.pdf_key, '')
        self.assertEqual(str(fiche), 'Fiche technique — %s' % legacy.pk)
