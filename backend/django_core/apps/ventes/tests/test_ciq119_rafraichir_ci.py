# -*- coding: utf-8 -*-
"""CIQ119 — rafraîchisseur d'étude C&I : l'étude suit les LIGNES facturées.

``rafraichir_etude_ci_devis`` (appelé par ``rafraichir_etudes_du_devis``)
relit les panneaux et onduleurs réellement au devis, appelle ``etudier_ci``
en « taille donnée » et n'écrit que ``etude_ci`` / ``production_figee``.
PVGIS est simulé (table vendorisée de Casablanca) : aucun accès réseau.

Chemins de copie (grep ``etude_params_pour_copie``) — ils purgent déjà
``etude_ci``/``production_figee`` (CIQ117) puis appellent
``rafraichir_etudes_du_devis(force=True)``, qui recalcule donc l'étude C&I :
``domain/creation.py`` (dupliquer), ``domain/cycle_vie.py`` (renouveler),
``domain/gammes.py`` (gamme sœur), ``views/devis.dupliquer_variante``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq119_rafraichir_ci"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.domain import etude_ci
from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tests.test_ciq118_etude_ci_preview import _production_casablanca
from authentication.models import Company

User = get_user_model()

ENTREES = {
    'mode': 'industriel', 'tension': 'bt', 'phases': 'tri',
    'site': {'ville': 'Casablanca', 'lat': None, 'lon': None},
    'consommation': {'kwh_mensuels': [20000] * 12},
    'rythme': {'jours_ouverts': [True] * 6 + [False],
               'plages': {'ouvre': [[7, 19]], 'samedi': [[7, 13]]},
               'talon': {'kw': 5}},
    'tarif_declare': {'contrat': 'bt_patente'},
}


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='ciq119-co', defaults={'nom': 'CIQ119 Co'})[0]
        cls.client_obj = Client.objects.create(company=cls.co, nom='Usine CIQ119')
        cls.panneau = Produit.objects.create(
            company=cls.co, nom='Panneau 710W', prix_vente=Decimal('1272.73'),
            prix_achat=Decimal('800'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.ond50 = cls._onduleur('Onduleur réseau Huawei 50kW Triphasé', 50)
        cls.ond30 = cls._onduleur('Onduleur réseau Huawei 30kW Triphasé', 30)

    @classmethod
    def _onduleur(cls, nom, kw):
        produit = Produit.objects.create(
            company=cls.co, nom=nom, prix_vente=Decimal('40000'),
            prix_achat=Decimal('30000'), role_devis='onduleur_reseau', garantie='10 ans constructeur')
        FicheTechnique.objects.create(
            company=cls.co, produit=produit, type_fiche='onduleur',
            ond_ac_kw=Decimal(kw), ond_phases=3, ond_n_mppt=4,
            ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
            ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
            ond_rendement_euro_pct=Decimal('98.4'))
        return produit

    def setUp(self):
        patcher = mock.patch.object(etude_ci, 'lire_production',
                                    side_effect=_production_casablanca)
        self.production = patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(
            username='ciq119_user', password='x', role_legacy='responsable',
            company=self.co)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, mode='industriel', ref='DEV-CIQ119-01'):
        devis = Devis.objects.create(
            company=self.co, reference=ref, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20'), mode_installation=mode,
            etude_params=dict(ENTREES, mode=mode) if mode in ('commercial', 'industriel')
            else {})
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau 710W',
            quantite=Decimal('70'), prix_unitaire=Decimal('1272.73'), remise=Decimal('0'))
        LigneDevis.objects.create(
            devis=devis, produit=self.ond50, designation='Onduleur 50 kW',
            quantite=Decimal('1'), prix_unitaire=Decimal('40000'), remise=Decimal('0'))
        return devis


class RafraichisseurTests(_Base):
    def test_ligne_onduleur_remplacee_recalcule_etude(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        avant = devis.etude_params['etude_ci']
        self.assertIsNotNone(avant['bilan'])
        self.assertIn('production_figee', devis.etude_params)
        self.assertEqual(avant['taille']['retenue_kwc'], 49.7)

        ligne = devis.lignes.get(produit=self.ond50)
        rep = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                             {'produit': self.ond30.id}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        devis.refresh_from_db()
        apres = devis.etude_params['etude_ci']
        self.assertNotEqual(avant['empreinte'], apres['empreinte'])
        self.assertIsNotNone(apres['bilan'])
        ids = [o['produit'] for o in apres['composition']['onduleurs']['combinaison']]
        self.assertEqual(ids, [self.ond30.id])

    def test_panneaux_modifies_bilan_recalcule(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        avant = devis.etude_params['etude_ci']['bilan']['production_kwh']
        ligne = devis.lignes.get(produit=self.panneau)
        rep = self.api.patch(f'/api/django/ventes/devis-lignes/{ligne.id}/',
                             {'quantite': '100'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        devis.refresh_from_db()
        self.assertGreater(devis.etude_params['etude_ci']['bilan']['production_kwh'], avant)

    def test_second_appel_sans_changement_zero_ecriture(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        with CaptureQueriesContext(connection) as requetes:
            etude_ci.rafraichir_etude_ci_devis(devis)
        ecritures = [q['sql'] for q in requetes.captured_queries
                     if q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))]
        self.assertEqual(ecritures, [])

    def test_cad177_production_figee_garde_ses_hypotheses_et_alertes(self):
        # CAD177 (CIQ334/CIQ346, nocturne 37803204581) — un recalcul qui
        # REPREND `production_figee` (empreinte changée, ex. provenance
        # ré-horodatée) rendait l'étude SANS les hypothèses PVGIS ni les
        # alertes du toit : ré-enregistrer un devis inchangé changeait son
        # etude_ci. Toit déclaré hors orientation PVGIS + pose à confirmer.
        devis = self._devis()
        devis.etude_params = dict(
            devis.etude_params, toit={'type_pose': 'bac_acier', 'pente_deg': 10,
                                      'azimut_deg': 20})
        devis.save(update_fields=['etude_params'])
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        avant = devis.etude_params['etude_ci']
        self.assertIn('source_production', {h['cle'] for h in avant['hypotheses']})
        self.assertIn('orientation_non_prise_en_compte', {a['code'] for a in avant['alertes']})
        appels_pvgis = self.production.call_count
        etude_ci.rafraichir_etude_ci_devis(devis, force=True)
        devis.refresh_from_db()
        apres = devis.etude_params['etude_ci']
        self.assertEqual(self.production.call_count, appels_pvgis,
                         'la production figée est reprise, PVGIS non rappelé')
        self.assertEqual(apres['hypotheses'], avant['hypotheses'])
        self.assertEqual(apres['alertes'], avant['alertes'])

    def test_r1_p5_devis_aux_regles_anterieures_jamais_de_bascule_rasante(self):
        # R1 (P5, coordinatrice 28/10/2026) — un devis à ``regles_calcul`` ≤ 2
        # garde la borne 30° seule et son alerte « taille au-delà du toit » ;
        # sans devis (aperçu) ou au niveau courant, la règle rasante s'applique.
        FicheTechnique.objects.filter(pmax_wc=Decimal('710')).update(
            longueur_mm=2384, largeur_mm=1303)
        entrees = dict(ENTREES, toit={'type_pose': 'toit_plat_leste', 'surface_utile_m2': 200},
                       taille_explicite_kwc=30)
        courant = etude_ci.etudier_ci(self.co, entrees)
        self.assertEqual(courant['taille']['bornes']['toit']['kwc_10'], 35.5)
        self.assertEqual(courant['taille']['inclinaison_retenue_deg'], 10)
        self.assertNotIn('taille_au_dela_du_toit', {a['code'] for a in courant['alertes']})
        devis = self._devis()
        devis.regles_calcul = 2
        ancien = etude_ci.etudier_ci(self.co, entrees, devis=devis)
        toit = ancien['taille']['bornes']['toit']
        self.assertNotIn('kwc_10', toit)
        self.assertAlmostEqual(toit['kwc'], 21.3, places=2)
        self.assertEqual((ancien['taille']['inclinaison_retenue_deg'],
                          ancien['taille']['taille_limitee_toit']), (None, None))
        self.assertIn('taille_au_dela_du_toit', {a['code'] for a in ancien['alertes']})
        devis.regles_calcul = 3          # création = toujours le niveau courant
        self.assertEqual(etude_ci.etudier_ci(self.co, entrees, devis=devis)
                         ['taille']['bornes']['toit']['kwc_10'], 35.5)

    def test_cad177_apercu_taille_saisie_meme_bilan_que_l_etude_du_devis(self):
        # CAD177 (CIQ334, nocturne 37871928670) — 49 kWc saisis se posent en
        # 70 panneaux de 710 Wc (49,7 kWc) : l'aperçu calculait son bilan à
        # 49 kWc, l'étude du devis (PDF) à 49,7 kWc — deux taux imprimés.
        apercu = etude_ci.etudier_ci(self.co, dict(ENTREES, taille_explicite_kwc=49))
        self.assertEqual(apercu['taille']['retenue_kwc'], 49.7)
        panneaux = [lg for lg in apercu['composition']['lignes'] if lg['role'] == 'panneau']
        self.assertEqual(panneaux[0]['quantite'], 70)
        self.assertIn('taille_panneaux_entiers', {h['cle'] for h in apercu['hypotheses']})
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        etude = devis.etude_params['etude_ci']
        for cle in ('production_kwh', 'autoconso_kwh', 'taux_autoconso', 'taux_couverture'):
            self.assertAlmostEqual(apercu['bilan'][cle], etude['bilan'][cle], places=6, msg=cle)

    def test_plus_aucun_panneau_derivees_retirees(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.lignes.filter(produit=self.panneau).delete()
        devis.refresh_from_db()
        etude_ci.rafraichir_etude_ci_devis(devis)
        devis.refresh_from_db()
        self.assertNotIn('etude_ci', devis.etude_params)
        self.assertNotIn('production_figee', devis.etude_params)

    def test_residentiel_et_agricole_inchanges(self):
        for mode, ref in (('residentiel', 'DEV-CIQ119-R'), ('agricole', 'DEV-CIQ119-A')):
            devis = self._devis(mode=mode, ref=ref)
            avant = dict(devis.etude_params or {})
            self.assertIsNone(etude_ci.rafraichir_etude_ci_devis(devis))
            devis.refresh_from_db()
            self.assertEqual(dict(devis.etude_params or {}), avant)
            self.production.assert_not_called()

    def test_statut_jamais_touche(self):
        devis = self._devis()
        rafraichir_etudes_du_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'brouillon')


class CreationAtomiqueCompleteTests(_Base):
    """ERR-AGNR-CI-ETUDE-AJOUTEE-AU-REENREGISTREMENT — le geste de l'écran
    générateur : ``POST /devis/atomic/`` (choix + entrées C&I dans le corps,
    ``etudeDeCreation``) puis le PATCH de fusion des mêmes entrées. Le devis
    créé porte DÉJÀ ``etude_ci`` / ``production_figee`` (le PDF les lit
    stockées) ; un « Enregistrer » sans rien toucher (``replace-lines`` aux
    choix seuls, puis le même PATCH) laisse ``etude_params`` identique."""

    CHOIX = {'scenario': 'Sans batterie', 'recommended_option': 'Sans batterie',
             'nombre_proprietes': None}

    def _lignes(self):
        return [
            {'produit': self.panneau.id, 'designation': 'Panneau 710W', 'quantite': '70',
             'prix_unitaire': '1272.73', 'remise': '0', 'taux_tva': '20.00',
             'type_ligne': 'produit', 'ordre': 0},
            {'produit': self.ond50.id, 'designation': 'Onduleur 50 kW', 'quantite': '1',
             'prix_unitaire': '40000', 'remise': '0', 'taux_tva': '20.00',
             'type_ligne': 'produit', 'ordre': 1},
        ]

    def _patch_etude(self, devis):
        rep = self.api.patch(f'/api/django/ventes/devis/{devis.id}/etude-params/',
                             dict(self.CHOIX, **ENTREES), format='json')
        self.assertEqual(rep.status_code, 200, rep.content)

    def test_creation_porte_l_etude_et_reenregistrement_a_vide_identique(self):
        rep = self.api.post('/api/django/ventes/devis/atomic/', {
            'client': self.client_obj.id, 'statut': 'brouillon', 'taux_tva': '20.00',
            'mode_installation': 'industriel', 'lignes': self._lignes(),
            'etude_params': dict(self.CHOIX, **ENTREES)}, format='json')
        self.assertEqual(rep.status_code, 201, rep.content)
        devis = Devis.objects.get(pk=rep.data['id'])
        self.assertIsNotNone(devis.etude_params.get('etude_ci', {}).get('bilan'))
        self.assertIn('production_figee', devis.etude_params)
        self._patch_etude(devis)
        devis.refresh_from_db()
        apres_creation = devis.etude_params
        self.assertIn('etude_ci', apres_creation)
        self.assertIn('production_figee', apres_creation)

        rep = self.api.post(f'/api/django/ventes/devis/{devis.id}/replace-lines/', {
            'lignes': self._lignes(), 'etude_params': self.CHOIX}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self._patch_etude(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params, apres_creation)


class PreseanceVisiteSurDevisTests(TestCase):
    """CORC4 (27/10/2026, constat CSV) — une mesure de visite VALIDÉE passe
    devant la valeur STOCKÉE d'un devis brouillon (copie d'une déclaration
    faite avant la visite) ; un devis envoyé garde ce que le client a reçu ;
    une saisie du corps reste souveraine."""

    RELEVE = {'visite_id': 7, 'validee_le': '2026-10-27',
              'trajets': [{'longueur_dc_m': 50, 'longueur_ac_m': 12},
                          {'longueur_dc_m': 35, 'longueur_ac_m': 40}]}

    def _resoudre(self, statut, origine='devis'):
        from types import SimpleNamespace
        res = etude_ci._Resolution()
        res.poser('longueur_dc_m', 20, etude_ci._provenance(origine))
        with mock.patch('apps.visites.selectors.releve_ci_pour_lead',
                        return_value=self.RELEVE):
            etude_ci._couche_visite(res, object(), [],
                                    devis=SimpleNamespace(statut=statut))
        return res

    def test_brouillon_suit_la_visite_trajet_le_plus_long(self):
        res = self._resoudre('brouillon')
        self.assertEqual(res.valeur('longueur_dc_m'), 50)
        self.assertEqual(res.valeur('longueur_ac_m'), 40)
        self.assertEqual(res.provenance('longueur_dc_m')['origine'], 'mesure_visite')

    def test_devis_envoye_garde_sa_valeur(self):
        self.assertEqual(self._resoudre('envoye').valeur('longueur_dc_m'), 20)

    def test_saisie_du_corps_reste_souveraine(self):
        self.assertEqual(self._resoudre('brouillon', origine='saisie').valeur('longueur_dc_m'), 20)
