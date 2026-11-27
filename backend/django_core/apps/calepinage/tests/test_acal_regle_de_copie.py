"""ACAL117 (D-ACAL-15, C-ACAL-011/090) — UNE règle de copie (Dupliquer,
modèle) : pertes copiées, aucun résultat ni saisie de site, variantes NON
retenues et sans résultat, implantation translatée sur le repère du lead
cible, version d'origine déposée.

Services réels ; rien n'est mocké.

Run :
    python manage.py test apps.calepinage.tests.test_acal_regle_de_copie -v2
"""
import copy

from django.test import SimpleTestCase

from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.services.modeles import (
    ModeleInvalide, creer_depuis_modele, marquer_modele,
)
from apps.calepinage.services.variantes import (
    creer_variante, dupliquer, retenir_variante,
)
from apps.crm.models import Lead

from .test_api_liste import BaseApiCalepinage

CASA = {'lat': 33.5731, 'lng': -7.5898}
MARRAKECH = {'lat': 31.6295, 'lng': -7.9811}

POSTES = [{'poste': 'iam', 'libelle': 'IAM', 'pct': 3.0, 'source': None,
           'reference': '', 'mensuel': None},
          {'poste': 'cablage', 'libelle': 'Câblage', 'pct': 1.5,
           'source': None, 'reference': '', 'mensuel': None},
          {'poste': 'mismatch', 'libelle': 'Mismatch', 'pct': 2.0,
           'source': None, 'reference': '', 'mensuel': None}]


def _document():
    return {
        'version': 2,
        'pin': dict(CASA),
        'outline': [[CASA['lat'], CASA['lng']],
                    [CASA['lat'] + 0.0001, CASA['lng']],
                    [CASA['lat'] + 0.0001, CASA['lng'] + 0.0001]],
        'zones': [{'id': 'z1', 'label': 'Pan Sud',
                   'vertices': [[CASA['lng'], CASA['lat']],
                                [CASA['lng'] + 0.0001, CASA['lat']],
                                [CASA['lng'] + 0.0001,
                                 CASA['lat'] + 0.0001]],
                   'geometry': {'count': 12, 'azimuthDeg': 180,
                                'tiltDeg': 15}}],
        'consumption': {'annualKwh': 9000},
    }


class RegleDeCopieTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.source = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL-MODELE',
            roof_layout=_document(), layout_hash='c' * 64,
            version_moteur='2.1.0',
            pertes=copy.deepcopy(POSTES),
            resultat={'simulation': {'hash_entree': 'site-origine'},
                      'raccordement_saisie': {'type': 'mono'}},
            roof_image='roofs/1/calepinage-rendu.png')
        self.variante = creer_variante(self.source, nom='V',
                                       roof_layout=_document(),
                                       resultat={'production': {'p50': 1}})
        retenir_variante(self.variante, appliquer=False)
        # ACON11 — la cible d'une copie a un repère toit (sinon 409).
        Lead.objects.filter(pk=self.lead_2.pk).update(roof_point=dict(CASA))

    def test_dupliquer_copie_pertes_sans_resultat(self):
        copie = dupliquer(self.source, user=self.user, lead_id=self.lead_2.pk)
        copie = Calepinage.objects.get(pk=copie.pk)
        attendu = {cle: valeur for cle, valeur in _document().items()
                   if cle != 'consumption'}
        self.assertEqual(copie.roof_layout, attendu)
        self.assertEqual(copie.pertes, POSTES)
        self.assertIsNone(copie.resultat)
        self.assertEqual(copie.roof_image, '')
        # Lot 2 critique #14 — pas de version de moteur sans résultat.
        self.assertEqual(copie.version_moteur, '')

    def test_dupliquer_ne_copie_pas_la_retenue(self):
        copie = dupliquer(self.source, user=self.user, lead_id=self.lead_2.pk)
        variantes = CalepinageVariante.objects.filter(calepinage=copie)
        self.assertEqual(variantes.count(), 1)
        for variante in variantes:
            self.assertFalse(variante.retenue)
            self.assertIsNone(variante.resultat)

    def test_copie_porte_sa_version_d_origine(self):
        copie = dupliquer(self.source, user=self.user, lead_id=self.lead_2.pk)
        versions = CalepinageVersion.objects.filter(calepinage=copie)
        self.assertEqual(versions.count(), 1)
        version = versions.get()
        self.assertEqual(version.libelle,
                         f"Conception d'origine (copie de #{self.source.pk})")
        self.assertIsNone(version.resultat)
        self.assertEqual(version.roof_layout, copie.roof_layout)

    def test_modele_translate_sur_le_lead_cible(self):
        marquer_modele(self.source, user=self.user)
        cible = Lead.objects.create(company=self.company, nom='Marrakech',
                                    roof_point=dict(MARRAKECH))
        copie = creer_depuis_modele(self.source, user=self.user,
                                    lead_id=cible.pk)
        copie = Calepinage.objects.get(pk=copie.pk)
        document = copie.roof_layout
        self.assertAlmostEqual(document['pin']['lat'], MARRAKECH['lat'], 6)
        self.assertAlmostEqual(document['pin']['lng'], MARRAKECH['lng'], 6)
        premier = document['zones'][0]['vertices'][0]
        self.assertAlmostEqual(premier[0], MARRAKECH['lng'], 4)
        self.assertAlmostEqual(premier[1], MARRAKECH['lat'], 4)
        self.assertAlmostEqual(document['outline'][0][0], MARRAKECH['lat'], 4)
        self.assertNotIn('consumption', document)
        self.assertIsNone(copie.resultat)
        self.assertEqual(copie.roof_image, '')
        self.assertEqual(copie.pertes, POSTES)

    def test_modele_porte_le_materiel_jamais_les_temperatures(self):
        """ACAL959 — module et onduleur suivent ; températures jamais."""
        self.source.resultat = {'entree_electrique': {
            'module_produit': 11, 'onduleur_produit': 22,
            'temperature_min_c': -10, 'temperature_max_c': 70,
            'cle_future': 'x'}}
        self.source.save(update_fields=['resultat'])
        marquer_modele(self.source, user=self.user)
        cible = Lead.objects.create(company=self.company, nom='Agadir',
                                    roof_point=dict(MARRAKECH))
        copie = Calepinage.objects.get(pk=creer_depuis_modele(
            self.source, user=self.user, lead_id=cible.pk).pk)
        self.assertEqual(copie.resultat, {'entree_electrique': {
            'module_produit': 11, 'onduleur_produit': 22}})
        version = CalepinageVersion.objects.get(calepinage=copie)
        self.assertIsNone(version.resultat)

    def test_modele_variantes_translatees_sans_consommation(self):
        """Lot 2 critique #6 — chaque VARIANTE du modèle suit la règle de la
        conception (D-ACAL-15) : translatée sur le lead cible, sans la
        consommation d'un autre client, empreinte recalculée."""
        marquer_modele(self.source, user=self.user)
        cible = Lead.objects.create(company=self.company, nom='Marrakech',
                                    roof_point=dict(MARRAKECH))
        copie = creer_depuis_modele(self.source, user=self.user,
                                    lead_id=cible.pk)
        variantes = list(CalepinageVariante.objects.filter(calepinage=copie))
        self.assertEqual(len(variantes), 1)
        document = variantes[0].roof_layout
        self.assertAlmostEqual(document['pin']['lat'], MARRAKECH['lat'], 6)
        premier = document['zones'][0]['vertices'][0]
        self.assertAlmostEqual(premier[0], MARRAKECH['lng'], 4)
        self.assertAlmostEqual(premier[1], MARRAKECH['lat'], 4)
        self.assertNotIn('consumption', document)
        # La variante SOURCE n'est pas touchée.
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.roof_layout, _document())

    def test_dupliquer_vers_un_autre_lead_retire_et_translate(self):
        """ACON11 (D-ACAL-15) — Dupliquer vers le lead B (Marrakech) : la
        copie perd consommation, factures, production et fond de plan de A,
        son pin est le repère de B ; vers un lead sans repère : 409."""
        from apps.calepinage.services.variantes import (
            CLES_D_UN_AUTRE_SITE, DuplicationEnConflit,
        )
        from apps.records.models import Activity

        document = dict(_document(), billKwh=540, result={'kwc': 5.5},
                        underlay={'attachmentId': 7},
                        imageCapture={'date': '2025-03-21',
                                      'source': 'page du fournisseur'})
        Calepinage.objects.filter(pk=self.source.pk).update(
            roof_layout=document)
        self.source.refresh_from_db()
        b = Lead.objects.create(company=self.company, nom='Marrakech',
                                roof_point=dict(MARRAKECH))
        copie = Calepinage.objects.get(pk=dupliquer(
            self.source, user=self.user, lead_id=b.pk).pk)
        for cle in CLES_D_UN_AUTRE_SITE:
            self.assertNotIn(cle, copie.roof_layout)
        self.assertAlmostEqual(copie.roof_layout['pin']['lat'],
                               MARRAKECH['lat'], 6)
        premier = copie.roof_layout['zones'][0]['vertices'][0]
        self.assertAlmostEqual(premier[1], MARRAKECH['lat'], 4)
        variante = CalepinageVariante.objects.get(calepinage=copie)
        self.assertNotIn('consumption', variante.roof_layout)
        self.assertTrue(Activity.objects.filter(
            object_id=copie.pk, body__contains='non recopiés').exists())

        sans = Lead.objects.create(company=self.company, nom='Sans repère')
        avant = Calepinage.objects.count()
        with self.assertRaises(DuplicationEnConflit) as refus:
            dupliquer(self.source, user=self.user, lead_id=sans.pk)
        self.assertIn("n'a pas de repère toit", refus.exception.corps['lead'])
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_modele_sans_repere_refuse(self):
        marquer_modele(self.source, user=self.user)
        sans = Lead.objects.create(company=self.company, nom='Sans repère')
        avant = Calepinage.objects.count()
        with self.assertRaises(ModeleInvalide) as refus:
            creer_depuis_modele(self.source, user=self.user, lead_id=sans.pk)
        self.assertEqual(refus.exception.champ, 'lead')
        self.assertIn("n'a pas de repère toit", str(refus.exception))
        self.assertEqual(Calepinage.objects.count(), avant)


class ImageCaptureTest(SimpleTestCase):
    """ACAL1041 — la date de l'image est propre au site, jamais recopiée."""

    def test_image_capture_absent_de_la_copie_vers_un_autre_lead(self):
        from apps.calepinage.services.variantes import preparer_pour_cible
        source = dict(_document(), imageCapture={
            'date': '2025-03-21', 'source': 'page du fournisseur'})
        for pin in (None, dict(MARRAKECH)):
            with self.subTest(pin=pin):
                self.assertNotIn('imageCapture',
                                 preparer_pour_cible(source, pin))
        self.assertIn('imageCapture', source)

    def test_echantillon_valide_et_refus_nommes(self):
        import json
        import pathlib

        from jsonschema import Draft202012Validator
        schema = json.loads((pathlib.Path(__file__).resolve().parents[1]
                             / 'contract_samples/roof_layout_v2.schema.json')
                            .read_text(encoding='utf-8'))
        valideur = Draft202012Validator(schema['properties']['imageCapture'])
        echantillon = schema['exemple_image_capture']
        self.assertTrue(valideur.is_valid(echantillon))
        for faux in (dict(echantillon, date='21/03/2025'),
                     dict(echantillon, source=''), {'date': '2025-03-21'}):
            with self.subTest(faux=faux):
                self.assertFalse(valideur.is_valid(faux))
        self.assertNotIn('imageCapture', schema['exemple'])


class MaterielDuModeleTest(SimpleTestCase):
    """ACAL959 — la liste blanche, sans base."""

    def test_seules_les_cles_blanches_sont_copiees(self):
        from apps.calepinage.services.variantes import (
            CHAMPS_ENTREE_DU_MODELE, _resultat_du_modele,
        )
        entree = {cle: i for i, cle in enumerate(CHAMPS_ENTREE_DU_MODELE)}
        entree.update(temperature_min_c=-10, temperature_max_c=70,
                      longueurs={'dc': 30}, cle_future='x')
        self.assertEqual(_resultat_du_modele({'entree_electrique': entree,
                                              'production': {'p50': 1}}),
                         {'entree_electrique': {
                             cle: i for i, cle in
                             enumerate(CHAMPS_ENTREE_DU_MODELE)}})

    def test_sans_cle_blanche_aucun_resultat(self):
        from apps.calepinage.services.variantes import _resultat_du_modele
        for resultat in (None, {}, {'simulation': {'hash_entree': 'x'}},
                         {'entree_electrique': {'temperature_min_c': -5}}):
            with self.subTest(resultat=resultat):
                self.assertIsNone(_resultat_du_modele(resultat))


class OnduleurDeLOriginalTest(SimpleTestCase):
    """ACAL1253 (D-ACAL-65) — la copie résout le MÊME onduleur, le même nombre et la même longueur
    que son original. Les vraies fonctions tournent (``materiel_de_la_conception``,
    ``options_de_la_conception``) ; seules les lectures en base sont remplacées : la conception du
    lead (``devis_retenu.conception_du_calepinage``, servie à l'ORIGINAL seul), le produit actif du
    catalogue et le nombre de panneaux posés."""

    CONCEPTION = {'etat': 'complet', 'option_retenue': 'A', 'valeurs': {'A': {
        'onduleur_produit': {'valeur': 42}, 'nombre_onduleurs': {'valeur': 2},
        'nb_panneaux': {'valeur': 24}, 'chaines': {'valeur': {'longueur': 12}}}}}

    def _original(self, resultat=None, lead_id=3):
        return Calepinage(pk=11, lead_id=lead_id, resultat=copy.deepcopy(resultat))

    def _copier(self, original, lead_cible, poses=24):
        from unittest import mock

        from apps.calepinage.services.variantes import _resultat_de_la_copie

        avant = copy.deepcopy(original.resultat)
        with mock.patch('apps.calepinage.services.devis_retenu.conception_du_calepinage',
                        side_effect=lambda c: self.CONCEPTION if c is original else None), \
                mock.patch('apps.calepinage.services.equipements._produit_actif',
                           side_effect=lambda company, identifiant, type_fiche: identifiant), \
                mock.patch('apps.calepinage.services.equipements._panneaux_poses', return_value=poses):
            produit = _resultat_de_la_copie(original, lead_cible)
        self.assertEqual(original.resultat, avant)  # l'original n'est jamais modifié
        return produit

    def test_meme_lead_rien_n_est_ecrit(self):
        # La copie relit la même conception : aucune désignation figée.
        self.assertIsNone(self._copier(self._original(), lead_cible=3))

    def test_sans_lead_la_copie_reprend_ce_que_options_de_la_conception_donne_a_l_original(self):
        from apps.calepinage.services.variantes import CLE_ONDULEUR_REPRIS
        resultat = self._copier(self._original(lead_id=None), lead_cible=None)
        self.assertEqual(resultat['entree_electrique'],
                         {'onduleur_produit': 42, 'nombre_onduleurs': 2, 'longueur_chaine_forcee': 12})
        self.assertEqual(resultat[CLE_ONDULEUR_REPRIS], {'calepinage': 11, 'onduleur_produit': 42})

    def test_la_copie_resout_les_memes_options_que_l_original(self):
        from unittest import mock

        from apps.calepinage.services.electrique import _options_entree
        from apps.calepinage.services.equipements import options_de_la_conception
        original = self._original(lead_id=None)
        entree = self._copier(original, lead_cible=None)['entree_electrique']
        copie = Calepinage(pk=12, lead_id=None, resultat={'entree_electrique': entree})
        with mock.patch('apps.calepinage.services.devis_retenu.conception_du_calepinage',
                        side_effect=lambda c: self.CONCEPTION if c is original else None), \
                mock.patch('apps.calepinage.services.equipements._produit_actif',
                           side_effect=lambda company, identifiant, type_fiche: identifiant), \
                mock.patch('apps.calepinage.services.equipements._panneaux_poses', return_value=24):
            attendu = options_de_la_conception({}, original, {})
            lu = options_de_la_conception(_options_entree(entree), copie, entree)
        self.assertEqual(attendu, {'nombre_onduleurs': 2, 'longueur_forcee': 12})
        self.assertEqual(lu, attendu)

    def test_autre_lead_reprend_aussi_et_pose_d_une_autre_taille_ne_force_ni_nombre_ni_longueur(self):
        self.assertEqual(self._copier(self._original(), lead_cible=9)['entree_electrique'],
                         {'onduleur_produit': 42, 'nombre_onduleurs': 2, 'longueur_chaine_forcee': 12})
        # 20 panneaux posés ≠ 24 de la conception : l'original n'imposait rien, la copie non plus.
        self.assertEqual(self._copier(self._original(), lead_cible=9, poses=20)['entree_electrique'],
                         {'onduleur_produit': 42})

    def test_onduleur_deja_designe_la_copie_est_inchangee(self):
        resultat = {'entree_electrique': {'onduleur_produit': 5}}
        self.assertEqual(self._copier(self._original(resultat), lead_cible=9), resultat)

    def test_onduleur_non_resolu_rien_n_est_invente(self):
        from unittest import mock

        from apps.calepinage.services.variantes import _resultat_de_la_copie
        original = self._original()
        with mock.patch('apps.calepinage.services.devis_retenu.conception_du_calepinage', return_value=None):
            self.assertIsNone(_resultat_de_la_copie(original, None))


class OnduleurReprisLuParSesLecteursTest(SimpleTestCase):
    """Lot 8 (tâche 2) — un onduleur « repris de l'original » n'est PAS une désignation du vendeur : ni
    imposé au moteur du lead (``ventes.conception.porte_calepinage.designations_du_calepinage``), ni
    chiffré comme désigné (``services.devis._onduleur_designe``), ni jugé comme tel par l'aperçu ; le
    marqueur ne vaut que tant que l'entrée porte cet onduleur, et il voyage dans l'export de projet."""

    @staticmethod
    def _calepinage(entree, repris=None):
        from types import SimpleNamespace

        from apps.calepinage.services.variantes import CLE_ONDULEUR_REPRIS
        resultat = {'entree_electrique': dict(entree)}
        if repris is not None:
            resultat[CLE_ONDULEUR_REPRIS] = repris
        return SimpleNamespace(pk=7, company=None, resultat=resultat)

    def test_valide_seulement_tant_que_l_entree_porte_l_onduleur_marque(self):
        from apps.calepinage.services.variantes import onduleur_designe_a_la_main, onduleur_repris_valide

        marque = {'calepinage': 11, 'onduleur_produit': 42}
        repris = self._calepinage({'onduleur_produit': 42, 'nombre_onduleurs': 1}, marque)
        change = self._calepinage({'onduleur_produit': 43, 'nombre_onduleurs': 1}, marque)  # choisi à la main ensuite
        main = self._calepinage({'onduleur_produit': 42, 'nombre_onduleurs': 1})
        self.assertEqual(onduleur_repris_valide(repris.resultat), marque)
        self.assertIsNone(onduleur_repris_valide(change.resultat))
        self.assertEqual([onduleur_designe_a_la_main(c) for c in (repris, change, main)], [False, True, True])
        self.assertFalse(onduleur_designe_a_la_main(self._calepinage({}, marque)))  # aucun onduleur
        self.assertIsNone(onduleur_repris_valide({'onduleur_repris': ['x'],
                                                  'entree_electrique': {'onduleur_produit': 1}}))

    def test_le_devis_ne_chiffre_pas_un_onduleur_repris_comme_designe(self):
        from apps.calepinage.services.devis import _onduleur_designe

        marque = {'calepinage': 11, 'onduleur_produit': 42}
        self.assertIsNone(_onduleur_designe(self._calepinage({'onduleur_produit': 42, 'nombre_onduleurs': 1}, marque)))
        self.assertEqual(_onduleur_designe(self._calepinage({'onduleur_produit': 43, 'nombre_onduleurs': 1}, marque)),
                         {'produit_id': 43, 'nombre': 1, 'nombre_illisible': False})

    def test_la_conception_du_lead_n_impose_pas_un_onduleur_repris(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.ventes.conception.porte_calepinage import designations_du_calepinage
        from apps.ventes.domain import resolution_catalogue as rc

        marque = {'calepinage': 11, 'onduleur_produit': 42}
        repris = self._calepinage({'onduleur_produit': 42}, marque)
        self.assertEqual(designations_du_calepinage(None, 7, repris), {})  # rien d'imposé, aucun vivier lu
        unique = SimpleNamespace(statut=rc.STATUT_UNIQUE)
        with mock.patch.object(rc, 'vivier', return_value=[]), \
                mock.patch.object(rc, 'resoudre_par_id', return_value=unique):
            self.assertEqual(designations_du_calepinage(None, 7, self._calepinage({'onduleur_produit': 43}, marque)),
                             {'onduleur_produit_id': 43})

    def test_l_export_de_projet_porte_le_marqueur_valide_et_l_import_le_relit(self):
        from apps.calepinage.services import export_projet as ep

        marque = {'calepinage': 11, 'onduleur_produit': 42}
        bloc = ep._bloc_saisies(self._calepinage({'onduleur_produit': 42}, marque))
        self.assertEqual(bloc['onduleur_repris'], marque)
        self.assertIsNone(ep._bloc_saisies(self._calepinage({'onduleur_produit': 43}, marque))['onduleur_repris'])
        self.assertIsNone(ep._bloc_saisies(self._calepinage({'onduleur_produit': 42}))['onduleur_repris'])
        self.assertEqual(ep._valider_saisies({'onduleur_repris': marque})['onduleur_repris'], marque)
        self.assertIsNone(ep._valider_saisies(None)['onduleur_repris'])
        for brut, chemin in (({'onduleur_produit': 'x'}, 'saisies.onduleur_repris.onduleur_produit'),
                             ({'onduleur_produit': 4, 'autre': 1}, 'saisies.onduleur_repris.autre'),
                             ([1], 'saisies.onduleur_repris')):
            with self.subTest(chemin=chemin), self.assertRaises(ep.ImportProjetRefuse) as capture:
                ep._valider_saisies({'onduleur_repris': brut})
            self.assertEqual(capture.exception.champ, chemin)

    def test_l_import_ne_repose_le_marqueur_que_sur_le_meme_onduleur(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.calepinage.services import export_projet as ep

        marque = {'calepinage': 11, 'onduleur_produit': 42}
        for produits, attendu in (({'onduleur_produit': 42}, marque), ({}, None)):
            cible = SimpleNamespace(pk=None, resultat={})
            saisies = {'entree_electrique': {'dc_m': 3.0}, 'produits': produits, 'raccordement_saisie': None,
                       'sld_edition': None, 'onduleur_repris': marque}
            with self.subTest(produits=produits), \
                    mock.patch('apps.calepinage.services.electrique.enregistrer_entree'):
                ep._ecrire_saisies(cible, saisies)
            self.assertEqual(cible.resultat.get('onduleur_repris'), attendu)
