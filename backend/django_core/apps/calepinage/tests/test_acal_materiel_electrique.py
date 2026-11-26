# -*- coding: utf-8 -*-
"""ACAL56 — module, onduleur, optimiseur du calcul électrique (D-ACAL-10).

Désignation EXPLICITE d'abord ; sinon — ACAL2013 (D-ACAL-97) — le matériel de la
CONCEPTION courante du lead (provenance « moteur », relue à chaque lecture, jamais
persistée ; le devis lié n'est plus lu) ; sinon le module posé ; sinon un refus
NOMMÉ qui dit le geste. Et ``GET entree-electrique/`` relit l'entrée stockée.

Produit / FicheTechnique / Devis / LigneDevis RÉELS en base :
``resoudre_materiel`` n'est jamais patché, la conception n'est jamais doublée.
"""
from __future__ import annotations

import json
import pathlib
from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, PROVENANCE_DEVIS, PROVENANCE_EXPLICITE,
    conception_du_calepinage,
)
from apps.calepinage.services.layout import empreinte_document, enregistrer_layout
from apps.calepinage.services.modules_pans import PROVENANCE_POSE, _produit_du_module_pose
from apps.calepinage.services.simulation import construire_contexte
from apps.calepinage.services.suivi_module_pose import (
    PHRASE_SUIVI, _lister_calepinages_au_module_divergent, _module_a_suivre,
)
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis

from .test_acal_cible_lead import ranger_conception
from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = (pathlib.Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'calepinage_entree_electrique.json')

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{
        'id': 'z1', 'label': 'Sud', 'neededPanels': 12,
        'result': {'count': 12},
        'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
    }],
}

#: Températures SAISIES : aucun appel réseau (TMY) pendant les tests.
TEMPERATURES = {'temperature_min_c': -5.0, 'temperature_max_c': 70.0}


def url_entree(pk):
    return f'{url_detail(pk)}entree-electrique/'


class BaseMateriel(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.module_devis = self._produit(
            nom='Module devis 710', type_fiche='module', vmp_v=41.4,
            voc_v=49.3, isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        self.module_explicite = self._produit(
            nom='Module explicite 580', type_fiche='module', vmp_v=44.0,
            voc_v=52.0, isc_a=14.0, imp_a=13.2, pmax_wc=580.0)
        self.onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
            ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=10.0,
            ond_phases=3)

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL56-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _devis(self, *produits):
        devis = Devis.objects.create(company=self.company,
                                     client=self.client_a,
                                     reference='DEV-ACAL56-1')
        for produit in produits:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=Decimal('100'),
                type_ligne='produit', variante='')
        return devis

    def _conception(self, module=None, onduleur=None, nombre=1, longueur=None, **extra):
        """ACAL2013 — la conception COURANTE du lead : module (par sa désignation) et onduleur."""
        module = module or self.module_devis
        onduleur = onduleur or self.onduleur
        return ranger_conception(
            lead=self.lead, nb=12, watt=710, module=module.nom, module_produit=module.pk, longueur=longueur,
            onduleur={'produit': onduleur.pk, 'designation': onduleur.nom, 'quantite': nombre}, **extra)

    def _calepinage(self, *, devis=None, entree=None):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            client=self.client_a, devis=devis, titre='Villa Anfa',
            roof_layout=LAYOUT,
            resultat={CLE_ENTREE: dict(TEMPERATURES, **(entree or {}))})


class MaterielDeLaConception(BaseMateriel):
    """ACAL2013 — sans saisie, le matériel de la CONCEPTION (provenance « moteur ») ;
    un devis lié n'est plus lu pour le matériel (mutant : relire la ligne ⇒ rouge)."""

    def test_defaut_conception_provenance_moteur_devis_non_lu(self):
        self._conception()
        autre_onduleur = self._produit(
            nom='Onduleur du devis 5 kW', type_fiche='onduleur', ond_n_mppt=1, ond_mppt_v_min=100.0,
            ond_mppt_v_max=500.0, ond_v_max_abs=600.0, ond_i_max_mppt_a=13.0, ond_ac_kw=5.0, ond_phases=1)
        calepinage = self._calepinage(devis=self._devis(self.module_explicite, autre_onduleur))
        conception, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['provenances'], {'module': 'moteur', 'onduleur': 'moteur', 'optimiseur': None})
        self.assertEqual((materiel['produits']['module'], materiel['produits']['onduleur']),
                         (self.module_devis.pk, self.onduleur.pk))
        self.assertFalse(conception.fiche_incomplete, conception.manquantes)
        self.assertTrue(conception.chaines)
        self.assertEqual(materiel['absents'], ())

    def test_sans_conception_le_devis_lie_n_est_pas_lu(self):
        calepinage = self._calepinage(devis=self._devis(self.module_devis, self.onduleur))
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertIsNone(materiel['produits']['onduleur'])
        self.assertNotIn(PROVENANCE_DEVIS, materiel['provenances'].values())
        self.assertIn("module PV non désigné — désignez-le dans l'onglet Matériel électrique",
                      materiel['absents'])

    def test_module_relu_par_son_identifiant_meme_nom_en_double(self):
        # Relecture E5 m4 — un second produit du même nom ne rend plus le module introuvable.
        double = self._produit(nom='Double', type_fiche='module', vmp_v=40.0, voc_v=48.0,
                               isc_a=13.0, imp_a=12.0, pmax_wc=500.0)
        Produit.objects.filter(pk=double.pk).update(nom=self.module_devis.nom)
        self._conception()
        _c, materiel, _d, _doc = conception_du_calepinage(self._calepinage())
        self.assertEqual((materiel['produits']['module'], materiel['provenances']['module']),
                         (self.module_devis.pk, 'moteur'))

    def test_produits_archives_de_la_conception_dits_jamais_servis(self):
        from apps.stock.models import Produit

        self._conception()
        Produit.objects.filter(pk__in=(self.module_devis.pk, self.onduleur.pk)).update(is_archived=True)
        _c, materiel, _d, _doc = conception_du_calepinage(self._calepinage())
        self.assertIsNone(materiel['produits']['onduleur'])
        self.assertNotEqual(materiel['produits']['module'], self.module_devis.pk)
        textes = ' | '.join(materiel['absents'])
        # Revue E6 m1 — le produit est nommé par la DÉSIGNATION que la conception a gardée,
        # jamais par son identifiant interne.
        self.assertIn('Le module de la conception (Module devis 710) est introuvable ou archivé', textes)
        self.assertIn("L'onduleur de la conception (Onduleur 10 kW) est introuvable ou archivé", textes)
        self.assertNotIn('n°', textes)

    def test_produit_archive_sans_designation_gardee_jamais_d_identifiant(self):
        from apps.stock.models import Produit

        ranger_conception(lead=self.lead, nb=12, watt=710, module=self.module_devis.nom,
                          module_produit=self.module_devis.pk,
                          onduleur={'produit': self.onduleur.pk, 'designation': '', 'quantite': 1})
        Produit.objects.filter(pk=self.onduleur.pk).update(is_archived=True)
        _c, materiel, _d, _doc = conception_du_calepinage(self._calepinage())
        textes = ' | '.join(materiel['absents'])
        self.assertIn("L'onduleur de la conception est introuvable ou archivé", textes)
        self.assertNotIn(str(self.onduleur.pk), textes)

    def test_la_provenance_moteur_n_est_pas_persistee(self):
        self._conception()
        calepinage = self._calepinage()
        avant = dict(calepinage.resultat[CLE_ENTREE])
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['materiel']['module']['provenance'], 'moteur')
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat[CLE_ENTREE], avant)
        self.assertNotIn('module_produit', calepinage.resultat[CLE_ENTREE])


class DesignationEntreeImposee(BaseMateriel):
    """ACAL2013 (clause restée ouverte à l'étape 5) — un onduleur désigné À LA MAIN relance
    le moteur de son porteur (``pose_enregistree`` → file ADEV139), et le moteur le reçoit
    comme entrée IMPOSÉE (``relancer`` → ``imposes``) ; sans désignation, rien n'est imposé."""

    class _Arret(Exception):
        pass

    def test_designation_relance_le_moteur_avec_la_designation_imposee(self):
        from unittest import mock

        from apps.calepinage.services.electrique import enregistrer_entree
        from apps.ventes.conception.service import relancer

        # Relecture E6 B2 : seule une désignation que le catalogue de VENTE du moteur accepte est
        # imposée — l'onduleur porte un nom que le classement reconnaît (réseau, triphasé).
        Produit.objects.filter(pk=self.onduleur.pk).update(nom='Onduleur réseau 10 kW Triphasé')
        self._conception()
        calepinage = self._calepinage()
        with mock.patch('apps.ventes.conception.receivers.mettre_en_file') as en_file, \
                mock.patch('apps.calepinage.services.layout.simuler_apres_enregistrement'):
            with self.captureOnCommitCallbacks(execute=True):
                enregistrer_entree(calepinage, {'onduleur_produit': self.onduleur.pk})
        en_file.assert_called_once()  # mutant « aucune relance sur désignation » : rouge
        self.assertEqual((en_file.call_args.kwargs['calepinage_id'], en_file.call_args.kwargs['origine']),
                         (calepinage.pk, 'pose_enregistree'))
        with mock.patch('apps.ventes.conception.moteur.calculer_conception', side_effect=self._Arret) as calcul:
            with self.assertRaises(self._Arret):
                relancer(self.lead, company=self.company, declencheur={'origine': 'pose_enregistree'},
                         calepinage_id=calepinage.pk, forcer=True)
        self.assertEqual(calcul.call_args.kwargs['imposes'], {'onduleur_produit_id': self.onduleur.pk})

    def test_sans_designation_rien_n_est_impose_ni_relance(self):
        from unittest import mock

        from apps.calepinage.services.electrique import enregistrer_entree
        from apps.ventes.conception.porte_calepinage import designations_du_calepinage

        calepinage = self._calepinage()
        self.assertEqual(designations_du_calepinage(self.company, calepinage.pk), {})
        with mock.patch('apps.ventes.conception.receivers.mettre_en_file') as en_file, \
                mock.patch('apps.calepinage.services.layout.simuler_apres_enregistrement'):
            with self.captureOnCommitCallbacks(execute=True):
                enregistrer_entree(calepinage, {'regime': 'TT'})
        en_file.assert_not_called()


class ConceptionSurUnePoseDAutreTaille(BaseMateriel):
    """Relecture E5 M4 — les chaînes de la conception (12 modules, 1 onduleur) ne sont
    IMPOSÉES qu'à une pose du MÊME nombre de panneaux ; 16 panneaux posés : chaînes
    calculées pour la pose réelle, aucun module « en réserve », aucune partition
    forcée ; la longueur de la conception reste la RÉFÉRENCE de l'écart."""

    def _pose(self, nb):
        calepinage = self._calepinage()
        zone = dict(LAYOUT['zones'][0], neededPanels=nb, result={'count': nb})
        calepinage.roof_layout = {**LAYOUT, 'zones': [zone]}
        calepinage.save(update_fields=['roof_layout'])
        return calepinage

    @staticmethod
    def _textes(conception):
        return ' | '.join([*conception.alertes, *conception.bloquants,
                           *(str(getattr(v, 'message', v)) for v in getattr(conception, 'verdicts', ()))])

    def test_seize_panneaux_poses_conception_de_douze(self):
        from apps.calepinage.services.suppositions import reference_de_longueur

        self._conception(longueur=12)
        calepinage = self._pose(16)
        conception, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['provenances']['onduleur'], 'moteur')
        self.assertEqual(sum(chaine.nb_modules for chaine in conception.chaines), 16)  # mutant forçage : 12
        self.assertNotIn('en réserve', self._textes(conception))
        self.assertNotIn('aucune découpe en chaînes ÉGALES', self._textes(conception))
        self.assertEqual(reference_de_longueur(calepinage), 12)

    def test_meme_taille_la_conception_est_imposee(self):
        self._conception(longueur=6)
        conception, _m, _d, _doc = conception_du_calepinage(self._pose(12))
        self.assertEqual({chaine.nb_modules for chaine in conception.chaines}, {6})


class MaterielExplicite(BaseMateriel):

    def test_designation_gagne_sur_la_conception(self):
        self._conception()
        calepinage = self._calepinage(
            entree={'module_produit': self.module_explicite.pk})
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['produits']['module'],
                         self.module_explicite.pk)
        self.assertEqual(materiel['provenances']['module'],
                         PROVENANCE_EXPLICITE)
        # ACAL2013 — l'onduleur, non désigné, reste celui de la conception.
        self.assertEqual(materiel['provenances']['onduleur'], 'moteur')


class SansDevis(BaseMateriel):

    def test_absent_nomme_le_geste(self):
        calepinage = self._calepinage()
        conception, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertIn("module PV non désigné — désignez-le dans l'onglet "
                      'Matériel électrique', materiel['absents'])
        self.assertTrue(conception.fiche_incomplete)
        self.assertFalse(conception.chaines)
        self.assertFalse(conception.bloquants)


class ModulePose(BaseMateriel):
    """T4-B4-007 / T4-U1-006 — le module CHOISI à l'étape Panneaux (posé sur
    les pans, ``geometry.moduleId`` → ``modules[].produitId``) EST le module du
    calcul électrique quand rien d'autre n'est désigné : jamais redemandé dans
    « Matériel électrique », jamais « Aucun module n'est désigné »."""

    def _layout_pose(self, produit):
        module = {'id': 'produit-%s' % produit.pk, 'produitId': produit.pk,
                  'libelle': produit.nom, 'source': 'fiche produit',
                  'longueurMm': 2384.0, 'largeurMm': 1303.0, 'pmaxWc': 710.0}
        zone = dict(LAYOUT['zones'][0])
        zone['geometry'] = {'moduleId': module['id'],
                            'panels': [{'n': i + 1} for i in range(12)]}
        return {**LAYOUT, 'modules': [module], 'zones': [zone]}

    def test_le_module_pose_est_le_module_du_calcul(self):
        calepinage = self._calepinage()
        calepinage.roof_layout = self._layout_pose(self.module_devis)
        calepinage.save(update_fields=['roof_layout'])
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['produits']['module'], self.module_devis.pk)
        self.assertEqual(materiel['provenances']['module'], PROVENANCE_POSE)
        self.assertFalse([a for a in materiel['absents']
                          if a.startswith('module PV')], materiel['absents'])
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['materiel']['module']['provenance'],
                         PROVENANCE_POSE)
        # Lu, jamais écrit : l'entrée stockée ne gagne aucun `module_produit`.
        calepinage.refresh_from_db()
        self.assertNotIn('module_produit', calepinage.resultat[CLE_ENTREE])

    def test_une_designation_explicite_gagne_sur_le_module_pose(self):
        calepinage = self._calepinage(
            entree={'module_produit': self.module_explicite.pk})
        calepinage.roof_layout = self._layout_pose(self.module_devis)
        calepinage.save(update_fields=['roof_layout'])
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['produits']['module'],
                         self.module_explicite.pk)
        self.assertEqual(materiel['provenances']['module'],
                         PROVENANCE_EXPLICITE)


class SurfacesDePoseSeules(BaseMateriel):
    """T4-U4-018 — un champ au sol (28) et une ombrière (16), aucun pan de
    toit : « Raccorder automatiquement » (POST entree-electrique) câble les
    44 modules, chaque ligne nommée par sa surface."""

    def test_post_entree_cable_le_sol_et_l_ombriere(self):
        calepinage = self._calepinage()
        calepinage.roof_layout = {'pin': LAYOUT['pin'], 'zones': [], 'poseSurfaces': [
            {'kind': 'sol', 'id': 'sol-1', 'label': 'Champ au sol', 'moduleWc': 710,
             'engine': {'modules': 28}},
            {'kind': 'ombriere', 'id': 'omb-1', 'label': 'Ombrière parking',
             'moduleWc': 710, 'engine': {'modules': 16}}]}
        calepinage.save(update_fields=['roof_layout'])
        onduleur = self._produit(
            nom='Deye 30kW Triphasé', type_fiche='onduleur', ond_n_mppt=3,
            ond_mppt_v_min=200.0, ond_mppt_v_max=850.0, ond_v_max_abs=1000.0,
            ond_i_max_mppt_a=32.0, ond_ac_kw=30.0, ond_phases=3)
        reponse = self.api.post(url_entree(calepinage.pk), {
            'module_produit': self.module_devis.pk, 'onduleur_produit': onduleur.pk},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = reponse.data['electrique']['affectation']
        self.assertEqual(len(lignes), 44)
        self.assertEqual({ligne['pan'] for ligne in lignes if ligne['chaine'] is not None},
                         {'Champ au sol', 'Ombrière parking'})


class GetEntree(BaseMateriel):

    def test_forme_du_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self._conception()  # ACAL2013 — le matériel vient de la conception
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur))
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        donnees = reponse.data
        self.assertEqual(sorted(donnees), sorted(contrat['exemple']))
        self.assertEqual(sorted(donnees['entree']),
                         sorted(contrat['exemple']['entree']))
        self.assertEqual(sorted(donnees['materiel']),
                         sorted(contrat['exemple']['materiel']))
        self.assertEqual(sorted(donnees['materiel']['module']),
                         sorted(contrat['exemple']['materiel']['module']))
        self.assertEqual(sorted(donnees['candidats']),
                         sorted(contrat['exemple']['candidats']))
        attendu = sorted(contrat['exemple']['candidats']['modules'][0])
        self.assertTrue(donnees['candidats']['modules'])
        for ligne in donnees['candidats']['modules']:
            self.assertEqual(sorted(ligne), attendu)
        self.assertEqual(donnees['absents'], ['optimiseur'])
        self.assertNotIn('prix', json.dumps(donnees, default=str))

    def test_post_puis_get_relit_l_entree_ecrite(self):
        calepinage = self._calepinage()
        corps = {'module_produit': self.module_explicite.pk,
                 'onduleur_produit': self.onduleur.pk, 'dc_m': 25.0,
                 'phases': 3}
        poste = self.api.post(url_entree(calepinage.pk), corps,
                              format='json')
        self.assertEqual(poste.status_code, 200, poste.data)
        calepinage.refresh_from_db()
        stockee = dict(calepinage.resultat[CLE_ENTREE])
        lu = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(lu.status_code, 200, lu.data)
        for cle, valeur in corps.items():
            self.assertEqual(lu.data['entree'][cle], valeur, cle)
        # Ré-enregistrer sans rien toucher : entrée octet-identique.
        self.api.post(url_entree(calepinage.pk), corps, format='json')
        calepinage.refresh_from_db()
        self.assertEqual(
            json.dumps(calepinage.resultat[CLE_ENTREE], sort_keys=True),
            json.dumps(stockee, sort_keys=True))

    def test_une_autre_societe_ne_voit_rien(self):
        calepinage = self._calepinage()
        reponse = self.api_autre.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 404)


class Simulation(BaseMateriel):

    def test_construire_contexte_fiche_module_non_vide(self):
        self._conception()  # ACAL2013
        calepinage = self._calepinage()
        contexte, meta = construire_contexte(calepinage)
        self.assertEqual(contexte['fiche_module'].get('pmax_wc'), 710.0)
        self.assertIsNotNone(meta['kwc'])


class MaterielRetenuParLeDevis(BaseMateriel):
    """ACAL1952 — sans saisie, l'onduleur, leur nombre et la longueur de chaîne
    sont ceux du DEVIS (option retenue), servis avec la provenance « devis » ;
    une saisie contraire reste permise et est dite comme écart."""

    def setUp(self):
        super().setUp()
        self.hybride = self._produit(
            nom='Onduleur hybride 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=160.0, ond_mppt_v_max=950.0, ond_v_max_abs=1100.0,
            ond_i_max_mppt_a=26.0, ond_ac_kw=10.0, ond_phases=3)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie Dyness 10 kWh', sku='ACAL1952-BAT',
            prix_vente=Decimal('1500'), quantite_stock=1)

    def _devis_deux_options(self, recommandee):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, reference='DEV-ACAL1952-10',
            statut='envoye', etude_params={'scenario': 'Les deux (Sans + Avec)',
                                           'recommended_option': recommandee})
        for produit, variante in ((self.module_devis, ''), (self.onduleur, 'sans'),
                                  (self.hybride, 'avec'), (self.batterie, 'avec')):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom, quantite=Decimal('1'),
                prix_unitaire=Decimal('100'), type_ligne='produit', variante=variante)
        return devis

    def test_devis_a_un_onduleur_sert_l_onduleur_le_nombre_et_la_provenance(self):
        self._conception()  # relecture E5 — le calcul lit la CONCEPTION, jamais la ligne du devis
        calepinage = self._calepinage(devis=self._devis(self.module_devis, self.onduleur))
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        bloc = reponse.data['devis_retenu']
        self.assertEqual((bloc['onduleur']['produit_id'], bloc['nombre_onduleurs'], bloc['provenance']),
                         (self.onduleur.pk, 1, 'devis'))
        self.assertEqual(bloc['ecarts'], [])
        # ACAL2013 — le bloc du devis informe ; le CALCUL ne lit plus la ligne du devis.
        self.assertEqual(reponse.data['materiel']['onduleur']['provenance'], 'moteur')  # mutant « ligne » : devis
        self.assertEqual(sorted(bloc), sorted(json.loads(CONTRAT.read_text(encoding='utf-8'))
                                              ['exemple']['devis_retenu']))

    def test_option_avec_du_moteur_sert_l_onduleur_hybride(self):
        # ACAL2013 — l'option que la CONCEPTION retient, plus celle que le devis recommande.
        self._conception(avec=12, option='avec', par_avec={'onduleur': {
            'produit': self.hybride.pk, 'designation': self.hybride.nom, 'quantite': 1}})
        calepinage = self._calepinage(devis=self._devis_deux_options('Sans batterie'))
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual((materiel['produits']['onduleur'], materiel['provenances']['onduleur']),
                         (self.hybride.pk, 'moteur'))

    def test_saisie_contraire_servie_et_ecart_nomme(self):
        calepinage = self._calepinage(
            devis=self._devis(self.module_devis, self.onduleur),
            entree={'onduleur_produit': self.hybride.pk, 'nombre_onduleurs': 2})
        reponse = self.api.get(url_entree(calepinage.pk))
        self.assertEqual(reponse.data['materiel']['onduleur']['produit_id'], self.hybride.pk)
        self.assertEqual(reponse.data['materiel']['onduleur']['provenance'], PROVENANCE_EXPLICITE)
        ecarts = reponse.data['devis_retenu']['ecarts']
        self.assertEqual(len(ecarts), 2, ecarts)
        self.assertIn('au devis DEV-ACAL56-1', ecarts[0])
        self.assertIn('Onduleur hybride 10 kW', ecarts[0])

    def test_sans_devis_inchange(self):
        reponse = self.api.get(url_entree(self._calepinage().pk))
        self.assertIsNone(reponse.data['devis_retenu'])

    def test_le_module_de_l_atelier_est_celui_de_la_conception_retenue(self):
        """Rejeu T3-VAGUEC2 — un module d'ESSAI de même puissance, premier du
        catalogue par son nom, était posé d'office au lieu du module du devis.
        Le module de la conception retenue (option « avec » recommandée) est
        celui de l'entrée électrique ET le premier du catalogue de l'atelier."""
        cotes = {'longueur_mm': 2384, 'largeur_mm': 1303, 'pmax_wc': 710.0,
                 'vmp_v': 41.4, 'voc_v': 49.3, 'isc_a': 18.59, 'imp_a': 17.59}
        essai = self._produit(nom='A panneau essai 710W', type_fiche='module', **cotes)
        retenu = self._produit(nom='Panneau retenu 710W', type_fiche='module', **cotes)
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, reference='DEV-ACAL1952-20',
            statut='envoye', etude_params={'scenario': 'Les deux (Sans + Avec)',
                                           'recommended_option': 'Avec batterie'})
        for produit, variante in ((essai, 'sans'), (self.onduleur, 'sans'), (retenu, 'avec'),
                                  (self.hybride, 'avec'), (self.batterie, 'avec')):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom, quantite=Decimal('1'),
                prix_unitaire=Decimal('100'), type_ligne='produit', variante=variante)
        self._conception(module=retenu)  # ACAL2013 — le module de la CONCEPTION
        calepinage = self._calepinage(devis=devis)
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual((materiel['produits']['module'], materiel['provenances']['module']),
                         (retenu.pk, 'moteur'))
        catalogue = self.api.get(f'{url_detail(calepinage.pk)}modules-disponibles/')
        self.assertEqual(catalogue.status_code, 200, catalogue.data)
        self.assertEqual(catalogue.data['modules'][0]['module']['produitId'], retenu.pk)
        # Une désignation manuelle reste permise et garde la main.
        calepinage.resultat = {CLE_ENTREE: dict(TEMPERATURES, module_produit=essai.pk)}
        calepinage.save()
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual((materiel['produits']['module'], materiel['provenances']['module']),
                         (essai.pk, PROVENANCE_EXPLICITE))

    def test_acal1953_l_ecart_de_longueur_se_mesure_a_la_conception(self):
        # ACAL2014 — la référence de l'écart est la longueur de la CONCEPTION (plus celle du devis : 9).
        from apps.calepinage.services.electrique import resultat_calepinage

        self._conception(longueur=14)
        devis = self._devis(self.module_devis, self.onduleur)
        devis.electrical_design = {'chaines': [{'nb_modules': 9}]}
        devis.save(update_fields=['electrical_design'])
        # Onduleur DÉSIGNÉ : la longueur de la conception n'est pas imposée au calcul, elle sert de référence.
        calepinage = self._calepinage(devis=devis, entree={'onduleur_produit': self.onduleur.pk})
        servi = resultat_calepinage(calepinage)
        longueur = servi['longueur_chaine']
        self.assertEqual(longueur['longueur_dossier'], 14)
        calcul = longueur['longueur'] or max(longueur['par_pan'].values())
        self.assertEqual(longueur['ecart'], calcul - 14)
        texte = json.dumps(servi, ensure_ascii=False)
        self.assertNotIn('au dossier (écart', texte)
        if calcul != 14:
            self.assertIn('calculée %s contre 14 à la conception' % calcul, texte)


def _document_pose(*pans):
    """D-ACAL-169 — un toit posé : ``pans`` = ``(produit_id, modules)`` ;
    ``produit_id`` ``None`` ⇒ pan posé sans modèle du catalogue ; un 3e
    élément vrai ⇒ pan « existant » (ACAL573)."""
    modules, zones = [], []
    for index, (produit_id, nombre, *existant) in enumerate(pans):
        geometrie = {'panels': [{'n': i + 1} for i in range(nombre)]}
        if produit_id is not None:
            ident = 'produit-%s' % produit_id
            if ident not in [module['id'] for module in modules]:
                modules.append({'id': ident, 'produitId': produit_id,
                                'libelle': 'Module %s' % produit_id,
                                'source': 'fiche produit',
                                'longueurMm': 2384.0, 'largeurMm': 1303.0,
                                'pmaxWc': 715.0})
            geometrie['moduleId'] = ident
        zones.append({'id': 'z%d' % index, 'label': 'Pan %d' % index,
                      'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0,
                      'geometry': geometrie,
                      **({'existant': True} if any(existant) else {})})
    return {'pin': LAYOUT['pin'], 'modules': modules, 'zones': zones}


class ModuleASuivre(SimpleTestCase):
    """D-ACAL-169 (point 3) — la règle PURE : quelle désignation stockée ne
    suit plus le toit, et par quel module la remplacer."""

    def test_module_change_sur_le_toit_le_module_pose_dominant(self):
        document = _document_pose((715, 12), (716, 2))
        self.assertEqual(_module_a_suivre(document, {'module_produit': 710}), 715)

    def test_toit_mixte_le_module_encore_pose_reste(self):
        document = _document_pose((710, 4), (715, 8))
        self.assertIsNone(_module_a_suivre(document, {'module_produit': 710}))
        self.assertIsNone(_module_a_suivre(document, {'module_produit': '710'}))

    def test_toit_sans_module_pose_rien(self):
        self.assertIsNone(_module_a_suivre(_document_pose((715, 0)),
                                           {'module_produit': 710}))
        self.assertIsNone(_module_a_suivre(dict(LAYOUT, zones=[]),
                                           {'module_produit': 710}))

    def test_pan_pose_sans_produit_la_designation_est_son_defaut(self):
        document = _document_pose((None, 12), (715, 4))
        self.assertIsNone(_module_a_suivre(document, {'module_produit': 710}))

    def test_pan_existant_sans_produit_n_empeche_pas_de_suivre(self):
        # Revue lot 8 — l'atelier ne pose aucun module sur un pan « existant » :
        # 6 modules existants sans produit + 12 neufs en 715, entrée 710 ⇒ 715.
        document = _document_pose((None, 6, True), (715, 12))
        self.assertEqual(_module_a_suivre(document, {'module_produit': 710}), 715)
        self.assertEqual(_lister_calepinages_au_module_divergent(
            [(7, document, {CLE_ENTREE: {'module_produit': 710}})]), [7])

    def test_pan_existant_jamais_module_dominant(self):
        # Un pan existant de 20 modules d'un produit 999 ne gagne jamais.
        document = _document_pose((999, 20, True), (715, 12))
        self.assertEqual(_module_a_suivre(document, {'module_produit': 710}), 715)
        self.assertEqual(_module_a_suivre(document, {'module_produit': 999}), 715)
        # Les autres appelants lisent ce qu'ils lisaient (défaut inchangé).
        self.assertEqual(_produit_du_module_pose(document), 999)

    def test_sans_designation_rien(self):
        document = _document_pose((715, 12))
        for entree in (None, {}, {'module_produit': None}, {'module_produit': ''}):
            self.assertIsNone(_module_a_suivre(document, entree))

    def test_r7n2_sans_designation_le_module_de_la_conception_est_juge(self):
        # Rien de stocké : la lecture prend le 710 de la conception ⇒ il est jugé
        # comme une désignation stockée.
        document = _document_pose((715, 35))
        for entree in (None, {}, {'module_produit': None}, {'module_produit': ''}):
            self.assertEqual(_module_a_suivre(document, entree, 710), 715)
        # Module de la conception encore posé (toit mixte) : rien.
        self.assertIsNone(_module_a_suivre(_document_pose((710, 4), (715, 8)), {}, 710))
        # Rien de posé, ou pan posé sans produit : rien.
        self.assertIsNone(_module_a_suivre(_document_pose((715, 0)), {}, 710))
        self.assertIsNone(_module_a_suivre(_document_pose((None, 12), (715, 4)), {}, 710))
        # Pans existants écartés, comme pour une désignation stockée.
        self.assertEqual(_module_a_suivre(_document_pose((999, 20, True), (715, 12)), {}, 710), 715)
        # Une désignation stockée garde la main sur la conception.
        self.assertIsNone(_module_a_suivre(document, {'module_produit': 715}, 710))

    def test_liste_en_lecture_seule_les_seuls_identifiants_concernes(self):
        lignes = [
            (1, _document_pose((715, 12)), {CLE_ENTREE: {'module_produit': 710}}),
            (2, _document_pose((710, 4), (715, 8)), {CLE_ENTREE: {'module_produit': 710}}),
            (3, _document_pose((715, 12)), {CLE_ENTREE: {}}),
            (4, _document_pose((715, 12)), None),
        ]
        self.assertEqual(_lister_calepinages_au_module_divergent(lignes), [1])


class EntreeSuitLeModulePose(BaseMateriel):
    """D-ACAL-169 (point 3) — base de données (CI) : ``enregistrer_layout``
    réel ; l'entrée suit le module posé dans la MÊME transaction et le chatter
    le dit ; ni ``layout_hash`` ni l'empreinte document ne bougent."""

    def setUp(self):
        super().setUp()
        self.module_715 = self._produit(
            nom='Module 715', type_fiche='module', vmp_v=41.6,
            voc_v=49.5, isc_a=18.65, imp_a=17.19, pmax_wc=715.0)

    def _notes(self, calepinage):
        """Les entrées du journal qui disent le suivi du module (tous genres)."""
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        return list(Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk, field='module_produit')
            .values_list('kind', 'old_value', 'new_value', 'body'))

    def test_module_change_l_entree_suit_et_le_dit(self):
        from apps.ventes.services import layout_hash

        devis = self._devis(self.module_devis)
        devis.electrical_design_hash = 'empreinte-figee'
        devis.save(update_fields=['electrical_design_hash'])
        calepinage = self._calepinage(
            devis=devis, entree={'module_produit': self.module_devis.pk})
        document = _document_pose((self.module_715.pk, 12))
        rendu = enregistrer_layout(calepinage, document, user=self.user)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat[CLE_ENTREE]['module_produit'],
                         self.module_715.pk)
        self.assertEqual(calepinage.resultat[CLE_ENTREE]['temperature_min_c'],
                         TEMPERATURES['temperature_min_c'])
        # Entrée AUTOMATIQUE (modification ancien → nouveau), jamais une note du vendeur.
        from apps.records.models import Activity

        self.assertEqual(self._notes(calepinage), [(
            Activity.Kind.MODIFICATION, 'Module devis 710', 'Module 715',
            PHRASE_SUIVI % ('Module devis 710', 'Module 715'))])
        # Les empreintes stockées ne lisent que le document : elles ne bougent pas.
        self.assertEqual(calepinage.layout_hash, layout_hash(document))
        self.assertEqual(rendu['empreinte_document'], empreinte_document(document))
        devis.refresh_from_db()
        self.assertEqual(devis.electrical_design_hash, 'empreinte-figee')
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual(materiel['produits']['module'], self.module_715.pk)

    def test_r7n2_sans_designation_la_conception_suivie_devient_le_module_pose(self):
        # Calepinage 24 du 26/11 : rien de désigné, conception à 710, 715 posés.
        self._conception()
        calepinage = self._calepinage()
        avant = conception_du_calepinage(calepinage)[1]
        self.assertEqual(avant['provenances']['module'], 'moteur')  # la LECTURE ne change pas
        document = _document_pose((self.module_715.pk, 12))
        rendu = enregistrer_layout(calepinage, document, user=self.user)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat[CLE_ENTREE]['module_produit'], self.module_715.pk)
        from apps.records.models import Activity

        self.assertEqual(self._notes(calepinage), [(
            Activity.Kind.MODIFICATION, 'Module devis 710', 'Module 715',
            PHRASE_SUIVI % ('Module devis 710', 'Module 715'))])
        self.assertEqual(rendu['empreinte_document'], empreinte_document(document))
        _c, materiel, _d, _doc = conception_du_calepinage(calepinage)
        self.assertEqual((materiel['produits']['module'], materiel['provenances']['module']),
                         (self.module_715.pk, PROVENANCE_EXPLICITE))

    def test_r7n2_sans_designation_conception_encore_posee_ou_absente_rien(self):
        self._conception()
        calepinage = self._calepinage()
        enregistrer_layout(calepinage, _document_pose(
            (self.module_devis.pk, 4), (self.module_715.pk, 8)), user=self.user)
        calepinage.refresh_from_db()
        self.assertNotIn('module_produit', calepinage.resultat[CLE_ENTREE])
        self.assertEqual(self._notes(calepinage), [])

    def test_r7n2_sans_conception_rien_n_est_ecrit(self):
        calepinage = self._calepinage()
        enregistrer_layout(calepinage, _document_pose((self.module_715.pk, 12)), user=self.user)
        calepinage.refresh_from_db()
        self.assertNotIn('module_produit', calepinage.resultat[CLE_ENTREE])

    def test_r7n2_module_pose_archive_ou_d_une_autre_famille_refuse(self):
        self._conception()
        Produit.objects.filter(pk=self.module_715.pk).update(is_archived=True)
        onduleur_pose = self._produit(nom='Pas un module', type_fiche='onduleur', ond_n_mppt=1,
                                      ond_mppt_v_min=100.0, ond_mppt_v_max=500.0, ond_v_max_abs=600.0,
                                      ond_i_max_mppt_a=13.0, ond_ac_kw=5.0, ond_phases=1)
        for produit in (self.module_715, onduleur_pose):
            calepinage = self._calepinage()
            enregistrer_layout(calepinage, _document_pose((produit.pk, 12)), user=self.user)
            calepinage.refresh_from_db()
            self.assertNotIn('module_produit', calepinage.resultat[CLE_ENTREE], produit.nom)
            self.assertEqual(self._notes(calepinage), [], produit.nom)

    def test_toit_mixte_entree_intacte(self):
        calepinage = self._calepinage(
            entree={'module_produit': self.module_devis.pk})
        enregistrer_layout(calepinage, _document_pose(
            (self.module_devis.pk, 4), (self.module_715.pk, 8)), user=self.user)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat[CLE_ENTREE]['module_produit'],
                         self.module_devis.pk)
        self.assertEqual(self._notes(calepinage), [])

    def test_toit_sans_module_pose_entree_intacte(self):
        calepinage = self._calepinage(
            entree={'module_produit': self.module_devis.pk})
        enregistrer_layout(calepinage, _document_pose((self.module_715.pk, 0)),
                           user=self.user)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat[CLE_ENTREE]['module_produit'],
                         self.module_devis.pk)

    def test_renvoi_a_l_identique_octet_pour_octet(self):
        calepinage = self._calepinage(
            entree={'module_produit': self.module_715.pk})
        document = _document_pose((self.module_715.pk, 12))
        enregistrer_layout(calepinage, document, user=self.user)
        calepinage.refresh_from_db()
        avant = (json.dumps(calepinage.resultat, sort_keys=True),
                 calepinage.layout_hash, empreinte_document(calepinage.roof_layout))
        notes = self._notes(calepinage)
        rendu = enregistrer_layout(calepinage, json.loads(json.dumps(document)),
                                   user=self.user)
        self.assertTrue(rendu['inchange'])
        calepinage.refresh_from_db()
        self.assertEqual((json.dumps(calepinage.resultat, sort_keys=True),
                          calepinage.layout_hash,
                          empreinte_document(calepinage.roof_layout)), avant)
        self.assertEqual(self._notes(calepinage), notes)

    def test_entree_perimee_non_touchee_garde_son_panneau(self):
        # D-ACAL-169 (4) — un calepinage enregistré dont l'entrée est déjà
        # périmée, renvoyé à l'identique : rien n'est réécrit (lecture seule).
        calepinage = self._calepinage()
        document = _document_pose((self.module_715.pk, 12))
        enregistrer_layout(calepinage, document, user=self.user)
        Calepinage.objects.filter(pk=calepinage.pk).update(resultat={
            CLE_ENTREE: dict(TEMPERATURES, module_produit=self.module_devis.pk)})
        calepinage.refresh_from_db()
        avant = json.dumps(calepinage.resultat, sort_keys=True)
        rendu = enregistrer_layout(calepinage, json.loads(json.dumps(document)),
                                   user=self.user)
        self.assertTrue(rendu['inchange'])
        calepinage.refresh_from_db()
        self.assertEqual(json.dumps(calepinage.resultat, sort_keys=True), avant)
        self.assertEqual(_lister_calepinages_au_module_divergent(
            Calepinage.objects.filter(pk=calepinage.pk).values_list(
                'pk', 'roof_layout', 'resultat')), [calepinage.pk])
