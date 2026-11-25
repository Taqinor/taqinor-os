"""ACAL325 (C-ACAL-145) — l'enregistrement d'un plan n'écrit plus
``resultat['verdict_electrique']`` (instantané lu par personne, recopié
périmé dans chaque version) ; le verdict reste CALCULÉ (rendu par
``rejouer_apres_layout``) et SERVI À LA DEMANDE par ``evaluation_electrique``
; la réconciliation de longueur (CAL170) est toujours journalisée.

Calepinage simulé par les VRAIS écrivains, enregistré en base ; le matériel
est le seam documenté (``patch_materiel``). La réconciliation hors tolérance
est provoquée par son ENTRÉE (``longueur_chaine_retenue``), jamais par un
double de ``journaliser_ecart_longueur`` (la fonction prouvée).

Run :
    python manage.py test apps.calepinage.tests.test_acal_verdict_non_persiste -v2
"""
import copy
import json
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_FIL_ECARTS, evaluation_electrique, rejouer_apres_layout,
)
from apps.calepinage.services.layout import enregistrer_layout

from .acal_livrables_helpers import calepinage_simule_reel, patch_materiel
from .test_api_liste import BaseApiCalepinage, url_detail

HORS_TOLERANCE = {'longueur': 12, 'origine': 'calcul', 'detail': 'essai',
                  'longueur_dossier': 16, 'ecart': -4,
                  'hors_tolerance': True, 'par_pan': {}}


class VerdictNonPersisteTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL325',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '')

    def _document_modifie(self):
        document = copy.deepcopy(self.calepinage.roof_layout)
        document['zones'][0]['geometry']['count'] += 1
        return document

    def test_sorties_ne_declarent_plus_verdict_electrique(self):
        # Lot 2 critique #21 — aucun écrivain ne pose plus la clé.
        from apps.calepinage.services.resultat import CLES_SORTIES

        self.assertNotIn('verdict_electrique', CLES_SORTIES)

    def test_sans_en_tete_de_simulation_rien_n_est_perime(self):
        """Lot 2 critique #21 — un résultat SANS ``simulation.hash_entree``
        (jamais simulé) n'est pas « périmé »."""
        from apps.calepinage.services.electrique import resultat_calepinage

        resultat = copy.deepcopy(self.calepinage.resultat)
        resultat.pop('simulation', None)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            resultat=resultat)
        cal = Calepinage.objects.get(pk=self.calepinage.pk)
        with patch_materiel():
            servi = resultat_calepinage(cal)
        self.assertFalse(servi['simulation_perimee'])
        self.assertFalse(servi.get('motif'))

    def test_enregistrer_layout_n_ecrit_pas_verdict_electrique(self):
        with patch_materiel():
            enregistrer_layout(self.calepinage, self._document_modifie(),
                               user=self.user)
        relu = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertNotIn('verdict_electrique', relu.resultat)
        # La version déposée ne porte aucun verdict périmé non plus.
        version = relu.versions.order_by('-id').first()
        self.assertTrue(version.resultat is None
                        or 'verdict_electrique' not in version.resultat)

    def test_la_reconciliation_de_longueur_est_toujours_journalisee(self):
        with patch_materiel(), mock.patch(
                'apps.calepinage.services.electrique._longueur_chaine_retenue',
                return_value=dict(HORS_TOLERANCE)):
            enregistrer_layout(self.calepinage, self._document_modifie(),
                               user=self.user)
        relu = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertIn(CLE_FIL_ECARTS, relu.resultat)
        self.assertTrue(relu.resultat[CLE_FIL_ECARTS])
        self.assertNotIn('verdict_electrique', relu.resultat)

    def test_verdict_servi_a_la_demande_inchange(self):
        with patch_materiel():
            enregistrer_layout(self.calepinage, self._document_modifie(),
                               user=self.user)
            relu = Calepinage.objects.get(pk=self.calepinage.pk)
            rendu = rejouer_apres_layout(relu, user=self.user)
            a_la_demande = evaluation_electrique(
                Calepinage.objects.get(pk=self.calepinage.pk))
            servi = self.api.get(f'{url_detail(self.calepinage.pk)}resultat/')
        self.assertIsNotNone(rendu)
        self.assertEqual(rendu, a_la_demande)
        self.assertEqual(servi.status_code, 200, servi.data)
        # Rejouer n'a toujours rien écrit.
        self.assertNotIn('verdict_electrique', Calepinage.objects.get(
            pk=self.calepinage.pk).resultat)


class LongueurDeLaConceptionTest(BaseApiCalepinage):
    """ACAL2014 (C4-E5) — la longueur de chaîne d'un calepinage de LEAD se compare à
    celle de sa CONCEPTION (aucun « contre 16 ») ; la constante d'appel d'offres
    (``MODULES_PAR_CHAINE``) ne se lit que pour un dossier d'appel d'offres. Lecture
    seule : rien n'est écrit."""

    def test_lead_reference_conception_aucun_contre_16(self):
        from apps.calepinage.services.electrique import resultat_calepinage
        from apps.calepinage.services.suppositions import reference_de_longueur

        from .test_acal_cible_lead import ranger_conception

        pivot = calepinage_simule_reel()
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL2014',
            roof_layout=copy.deepcopy(pivot.roof_layout), resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '')
        ranger_conception(lead=self.lead, nb=14, longueur=14)
        self.assertEqual(reference_de_longueur(calepinage), 14)
        with patch_materiel():
            servi = resultat_calepinage(calepinage)
        self.assertEqual(servi['longueur_chaine']['longueur_dossier'], 14)
        texte = json.dumps(servi, ensure_ascii=False, default=str)
        self.assertNotIn('contre 16', texte)
        self.assertNotIn('au devis (écart', texte)

    def test_fiche_muette_d_un_lead_sans_seize(self):
        from apps.calepinage.services.electrique import ORIGINE_LONGUEUR_DOSSIER, _longueur_chaine_retenue
        from apps.calepinage.services.suppositions import liste_des_suppositions

        from .test_elec_reconciliation_noyaux import MODULE, _conception

        muette = _conception(24, module_specs={c: v for c, v in MODULE.items() if c != 'voc_v'})
        lead = _longueur_chaine_retenue(muette, None)
        self.assertEqual((lead['origine'], lead['longueur'], lead['longueur_dossier']),
                         (ORIGINE_LONGUEUR_DOSSIER, None, None))
        self.assertNotIn('16', lead['detail'])
        suppose = liste_des_suppositions(lead, {'degagements': {'allee_technique_m': 0.8}},
                                         ORIGINE_LONGUEUR_DOSSIER)
        self.assertEqual([(s['code'], s['valeur']) for s in suppose], [('longueur_chaine_dossier', None)])
        conception = _longueur_chaine_retenue(muette, 14)
        self.assertEqual((conception['longueur'], conception['longueur_dossier']), (14, 14))

    def test_appel_d_offres_garde_seize(self):
        from types import SimpleNamespace

        from apps.calepinage.services.electrique import _longueur_chaine_retenue
        from apps.calepinage.services.suppositions import reference_de_longueur
        from core.calepinage.electrique import MODULES_PAR_CHAINE

        from .test_elec_reconciliation_noyaux import MODULE, _conception

        dossier = SimpleNamespace(appel_offre_id=7, lead_id=None, company=None)
        self.assertEqual(reference_de_longueur(dossier), MODULES_PAR_CHAINE)
        muette = _conception(24, module_specs={c: v for c, v in MODULE.items() if c != 'voc_v'})
        self.assertEqual(_longueur_chaine_retenue(muette, reference_de_longueur(dossier))['longueur'],
                         MODULES_PAR_CHAINE)
