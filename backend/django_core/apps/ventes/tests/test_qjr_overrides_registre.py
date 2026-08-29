"""QJR57 — le REGISTRE de surcharges : liste blanche, résolveur, sérialiseur.

CE QUE CES TESTS TIENNENT (les trois propriétés de sûreté du contrat PACT10
``contract_samples/devis_overrides.json``) :

1. **ENTRÉES SEULES** — un champ DÉRIVÉ est refusé en 400, jamais ignoré ; un
   chemin hors liste blanche D12 aussi ; une clé indexée par POSITION aussi.
2. **DÉRIVATION À CHAQUE LECTURE** — ``effectif`` n'est jamais stocké.
3. **``regenerer`` SUPPRIME** — il ne remplace jamais par une valeur calculée.

Et la FUSION : poser un chemin ne touche AUCUN autre, bit à bit.

La liste blanche est ÉPINGLÉE contre le contrat committé : elle ne peut pas
diverger en silence de ce que l'écran (QJR88) lira.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_overrides_registre -v 2
"""
import json
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.ventes.domain import overrides as R
from apps.ventes.serializers import OverridesSerializer

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'devis_overrides.json')

HORODATAGE = datetime(2026, 8, 29, 9, 0, tzinfo=dt_timezone.utc)


class _Devis:
    """Porteur minimal : le registre vit sur ``overrides`` (colonne QJR58)."""

    def __init__(self, overrides=None):
        self.overrides = overrides


class _Utilisateur:
    def __init__(self, email='sami@taqinor.ma'):
        self.email = email


class ListeBlancheTests(SimpleTestCase):
    """La liste D12 est celle du CONTRAT, jamais une recopie qui dérive."""

    def test_les_chemins_sont_ceux_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        attendus = contrat['notes']['chemins_autorises']
        self.assertEqual(sorted(R.CHAMPS_OVERRIDABLES), sorted(attendus))

    def test_un_chemin_de_la_liste_est_autorise(self):
        for chemin in R.CHAMPS_OVERRIDABLES:
            if chemin.endswith('<clef>'):
                continue
            with self.subTest(chemin=chemin):
                self.assertTrue(R.chemin_autorise(chemin))

    def test_le_motif_equipement_accepte_une_clef_reelle(self):
        self.assertTrue(R.chemin_autorise('profil.equipements.piscine'))
        self.assertTrue(
            R.chemin_autorise('profil.equipements.vehicule_electrique'))

    def test_le_motif_equipement_refuse_un_index_de_position(self):
        self.assertFalse(R.chemin_autorise('profil.equipements.3'))
        self.assertFalse(R.chemin_autorise('profil.equipements.'))
        self.assertFalse(R.chemin_autorise('profil.equipements.a.b'))

    def test_un_chemin_inconnu_est_refuse(self):
        self.assertFalse(R.chemin_autorise('taille.inventee'))
        self.assertFalse(R.chemin_autorise(''))
        self.assertFalse(R.chemin_autorise(None))


class EffectifTests(SimpleTestCase):
    """Dérivation à CHAQUE lecture — rien n'est stocké."""

    def test_sans_override_l_effectif_est_l_auto(self):
        valeur, source = R.effectif(_Devis(), 'taille.nb_panneaux', 12)
        self.assertEqual((valeur, source), (12, 'auto'))

    def test_avec_override_le_manuel_prime_et_la_source_le_dit(self):
        devis = _Devis({'taille.nb_panneaux': {
            'valeur': 14, 'origine': 'manuel'}})
        self.assertEqual(R.effectif(devis, 'taille.nb_panneaux', 12),
                         (14, 'manuel'))

    def test_l_auto_bouge_sans_toucher_au_manuel(self):
        devis = _Devis({'taille.nb_panneaux': {
            'valeur': 14, 'origine': 'manuel'}})
        for auto in (12, 18, None):
            with self.subTest(auto=auto):
                self.assertEqual(
                    R.effectif(devis, 'taille.nb_panneaux', auto)[0], 14)

    def test_la_vue_effective_a_la_forme_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        attendues = set(contrat['exemple']['effectif']['taille.nb_panneaux'])
        devis = _Devis({'taille.nb_panneaux': {
            'valeur': 14, 'origine': 'manuel'}})
        bloc = R.vue_effective(devis, {'taille.nb_panneaux': 12,
                                       'taille.kwc': 8.52})
        self.assertEqual(set(bloc['taille.nb_panneaux']), attendues)
        self.assertEqual(bloc['taille.nb_panneaux'],
                         {'auto': 12, 'manuel': 14, 'effectif': 14,
                          'source': 'manuel'})
        self.assertEqual(bloc['taille.kwc'],
                         {'auto': 8.52, 'manuel': None, 'effectif': 8.52,
                          'source': 'auto'})

    def test_un_override_pose_ne_disparait_jamais_d_une_lecture(self):
        devis = _Devis({'tarif.distributeur': {
            'valeur': 'ONEE', 'origine': 'import'}})
        bloc = R.vue_effective(devis, {})
        self.assertEqual(bloc['tarif.distributeur']['source'], 'import')
        self.assertIsNone(bloc['tarif.distributeur']['auto'])


class PoserEtFusionTests(SimpleTestCase):
    """Poser UN chemin laisse les autres intouchés, bit à bit."""

    def test_poser_ecrit_la_provenance(self):
        registre = R.poser(_Devis(), 'taille.nb_panneaux', 14,
                           utilisateur=_Utilisateur(), horodatage=HORODATAGE)
        self.assertEqual(registre['taille.nb_panneaux'], {
            'valeur': 14,
            'pose_le': HORODATAGE.isoformat(),
            'pose_par': 'sami@taqinor.ma',
            'origine': 'manuel'})

    def test_poser_ne_touche_aucun_autre_chemin(self):
        depart = {'tarif.distributeur': {
            'valeur': 'ONEE', 'pose_le': 'x', 'pose_par': 'y',
            'origine': 'import'}}
        registre = R.poser(_Devis(dict(depart)), 'taille.nb_panneaux', 14,
                           horodatage=HORODATAGE)
        self.assertEqual(registre['tarif.distributeur'],
                         depart['tarif.distributeur'])

    def test_poser_refuse_un_champ_derive(self):
        with self.assertRaises(ValueError):
            R.poser(_Devis(), 'production_annuelle', 12000,
                    horodatage=HORODATAGE)

    def test_poser_refuse_un_chemin_inconnu(self):
        with self.assertRaises(ValueError):
            R.poser(_Devis(), 'taille.inventee', 1, horodatage=HORODATAGE)

    def test_poser_refuse_une_origine_inventee(self):
        with self.assertRaises(ValueError):
            R.poser(_Devis(), 'scenario', 'Les deux', origine='magie',
                    horodatage=HORODATAGE)

    def test_la_fusion_conserve_les_chemins_precedents(self):
        depart = {'scenario': {'valeur': 'Les deux (Sans + Avec)',
                               'pose_le': 'x', 'pose_par': 'y',
                               'origine': 'manuel'}}
        registre = R.fusionner(
            _Devis(dict(depart)),
            {'taille.nb_panneaux': {'valeur': 14},
             'tarif.distributeur': {'valeur': 'ONEE', 'origine': 'import'}},
            horodatage=HORODATAGE)
        self.assertEqual(set(registre),
                         {'scenario', 'taille.nb_panneaux',
                          'tarif.distributeur'})
        self.assertEqual(registre['scenario'], depart['scenario'])
        self.assertEqual(registre['tarif.distributeur']['origine'], 'import')

    def test_poser_ne_persiste_rien(self):
        """QJR57 est PUR : la colonne n'existe qu'à partir de QJR58."""
        devis = _Devis()
        R.poser(devis, 'taille.nb_panneaux', 14, horodatage=HORODATAGE)
        self.assertIsNone(devis.overrides)


class RegenererTests(SimpleTestCase):
    """``regenerer`` SUPPRIME — il ne remplace jamais."""

    def test_regenerer_supprime_l_override(self):
        devis = _Devis({'taille.nb_panneaux': {'valeur': 14,
                                               'origine': 'manuel'}})
        registre = R.regenerer(devis, 'taille.nb_panneaux')
        self.assertNotIn('taille.nb_panneaux', registre)

    def test_apres_regenerer_l_effectif_redevient_l_auto(self):
        devis = _Devis(R.regenerer(
            _Devis({'taille.nb_panneaux': {'valeur': 14,
                                           'origine': 'manuel'}}),
            'taille.nb_panneaux'))
        self.assertEqual(R.effectif(devis, 'taille.nb_panneaux', 12),
                         (12, 'auto'))

    def test_regenerer_un_chemin_non_pose_est_un_no_op(self):
        devis = _Devis({'scenario': {'valeur': 'x', 'origine': 'manuel'}})
        registre = R.regenerer(devis, 'taille.nb_panneaux')
        self.assertEqual(set(registre), {'scenario'})


class SerialiseurTests(SimpleTestCase):
    """Les TROIS refus, en 400 et en français — jamais un silence."""

    def _valider(self, corps):
        s = OverridesSerializer(data=corps)
        s.is_valid(raise_exception=True)
        return s.validated_data

    def test_un_champ_derive_est_refuse_en_400(self):
        with self.assertRaises(ValidationError) as ctx:
            self._valider({'prix_ttc': 120000})
        self.assertIn('prix_ttc', ctx.exception.detail)

    def test_un_chemin_inconnu_est_refuse_en_400(self):
        with self.assertRaises(ValidationError) as ctx:
            self._valider({'taille.inventee': 1})
        self.assertIn('taille.inventee', ctx.exception.detail)

    def test_une_cle_indexee_par_position_est_refusee_en_400(self):
        with self.assertRaises(ValidationError) as ctx:
            self._valider({'lignes[3].prix_manuel': True})
        self.assertIn('lignes[3].prix_manuel', ctx.exception.detail)

    def test_un_corps_vide_est_refuse(self):
        with self.assertRaises(ValidationError):
            self._valider({})

    def test_un_corps_valide_est_normalise(self):
        propre = self._valider({
            'taille.nb_panneaux': 14,
            'tarif.distributeur': {'valeur': 'ONEE', 'origine': 'import'}})
        self.assertEqual(propre, {
            'taille.nb_panneaux': {'valeur': 14, 'origine': 'manuel'},
            'tarif.distributeur': {'valeur': 'ONEE', 'origine': 'import'}})

    def test_le_refus_nomme_TOUS_les_chemins_fautifs(self):
        with self.assertRaises(ValidationError) as ctx:
            self._valider({'prix_ttc': 1, 'payback_annees': 2,
                           'taille.nb_panneaux': 14})
        self.assertEqual(set(ctx.exception.detail),
                         {'prix_ttc', 'payback_annees'})

    def test_une_origine_inventee_est_refusee(self):
        with self.assertRaises(ValidationError):
            self._valider({'scenario': {'valeur': 'x', 'origine': 'magie'}})
