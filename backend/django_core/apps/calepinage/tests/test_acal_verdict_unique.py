# -*- coding: utf-8 -*-
"""ACAL169 — « peut-on publier ? » : UNE réponse, celle de verdict_publiable.

Avant : ``evaluation_electrique['publiable']`` et
``verdict_publiable['publiable']`` étaient deux définitions ; l'affectation
imposée, le polystring et les micro-onduleurs n'entraient que dans la
première — l'écran affichait « Publiable » sur une chaîne trop longue.
Base RÉELLE (Produit / FicheTechnique / réglages), aucun patch.
"""
from __future__ import annotations

import json
import pathlib
from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, CODE_AFFECTATION, CODE_FICHE_INCOMPLETE,
    CODE_MICRO_ONDULEURS, CODE_POLYSTRING, evaluation_electrique,
    verdict_publiable,
)
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage

LAYOUT = {
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [{'id': 'a', 'label': 'PAN-A', 'result': {'count': 24},
               'facingAzimuthDeg': 180.0, 'pitchDeg': 15.0}],
}
REFUSANTS = ('bloquant', 'sans_source')


class VerdictUnique(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(
            company=self.company,
            norme_electrique={'norme': 'nf_c_15_100'})
        self.module = self._produit(
            nom='Module 710', type_fiche='module', vmp_v=41.4, voc_v=49.3,
            isc_a=18.59, imp_a=17.59, pmax_wc=710.0)
        self.onduleur = self._produit(
            nom='Onduleur 10 kW', type_fiche='onduleur', ond_n_mppt=2,
            ond_mppt_v_min=120.0, ond_mppt_v_max=500.0, ond_v_max_abs=600.0,
            ond_i_max_mppt_a=26.0, ond_ac_kw=10.0, ond_phases=3)
        self.base = {
            'module_produit': self.module.pk,
            'onduleur_produit': self.onduleur.pk,
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
            'phases': 3, 'regime': 'TT',
            # La justification de terre RÉELLE (CAL134).
            'terre': {'justification_continuite': True},
        }

    def _produit(self, *, nom, type_fiche, **champs_fiche):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL169-{nom}',
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche=type_fiche,
            **champs_fiche)
        return produit

    def _calepinage(self, **entree):
        donnees = dict(self.base)
        donnees.update(entree)
        donnees = {cle: valeur for cle, valeur in donnees.items()
                   if valeur is not None}
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa',
            roof_layout=LAYOUT, resultat={CLE_ENTREE: donnees})

    def _motifs(self, verdict, code):
        return [motif for motif in verdict['motifs']
                if motif['code'] == code]

    def test_affectation_bloquante_visible_des_deux_cotes(self):
        # ACAL265 — la clé de module est '<zone.id>#<n>' (zone 'a'), le
        # libellé « PAN-A » n'est plus une clé (il reste le nom AFFICHÉ).
        imposee = [{'module': 'a#%d' % rang, 'chaine': 2, 'mppt': 1,
                    'onduleur': 1} for rang in range(1, 21)]
        calepinage = self._calepinage(affectation_manuelle=imposee)
        verdict = verdict_publiable(calepinage)
        motifs = self._motifs(verdict, CODE_AFFECTATION)
        self.assertTrue(motifs, verdict['motifs'])
        self.assertTrue(motifs[0]['libelle'].startswith(
            'Chaîne 2 (pan PAN-A) : 20 modules, maximum'), motifs[0])
        self.assertIn(motifs[0]['statut'], REFUSANTS)
        self.assertFalse(verdict['publiable'])
        self.assertFalse(evaluation_electrique(calepinage)['publiable'])

    def test_polystring_bloquant(self):
        calepinage = self._calepinage(
            polystring=[{'mppt': 99, 'pans': ['PAN-A']}])
        verdict = verdict_publiable(calepinage)
        self.assertTrue(self._motifs(verdict, CODE_POLYSTRING),
                        verdict['motifs'])
        self.assertFalse(verdict['publiable'])
        self.assertFalse(evaluation_electrique(calepinage)['publiable'])

    def test_micro_bloquant(self):
        micro = self._produit(nom='Micro sans borne', type_fiche='optimiseur',
                              opt_ac_kw=0.8, opt_ac_tension_v=230.0)
        calepinage = self._calepinage(onduleur_produit=None,
                                      optimiseur_produit=micro.pk)
        verdict = verdict_publiable(calepinage)
        motifs = self._motifs(verdict, CODE_MICRO_ONDULEURS)
        self.assertTrue([motif for motif in motifs
                         if motif['statut'] in REFUSANTS], verdict['motifs'])
        self.assertFalse(verdict['publiable'])
        self.assertFalse(evaluation_electrique(calepinage)['publiable'])

    def test_indetermine_distinct_du_bloquant(self):
        calepinage = self._calepinage(module_produit=None,
                                      onduleur_produit=None)
        verdict = verdict_publiable(calepinage)
        manques = self._motifs(verdict, CODE_FICHE_INCOMPLETE)
        self.assertTrue(manques, verdict['motifs'])
        for motif in manques:
            self.assertNotIn(motif['statut'], REFUSANTS)
        self.assertEqual(evaluation_electrique(calepinage)['verdict'],
                         'indetermine')

    def test_publiable_derive_de_verdict_publiable(self):
        for entree in ({}, {'affectation_manuelle': [
                {'module': 'PAN-A#%d' % rang, 'chaine': 2, 'mppt': 1,
                 'onduleur': 1} for rang in range(1, 21)]}):
            with self.subTest(entree=bool(entree)):
                calepinage = self._calepinage(**entree)
                self.assertEqual(
                    evaluation_electrique(calepinage)['publiable'],
                    verdict_publiable(calepinage)['publiable'])

    def test_d_hyb_1_hybride_reconnu_par_son_role_sur_le_vrai_chemin(self):
        """D-HYB-1 (fondateur 24/11/2026 : « un produit se reconnaît à son rôle et à sa fiche
        avant son nom ») — vrai chemin ``resoudre_materiel`` → ``conception_du_calepinage`` :
        un onduleur au rôle DÉCLARÉ ``onduleur_hybride``, nommé sans « hybride », publiant sa
        puissance PV maximale, est jugé à elle (24 × 710 Wc = 17,04 kWc sur 10 kW : 1,70)."""
        from apps.calepinage.services.electrique import (
            SOURCE_BORNE_CAPACITE, SOURCE_BORNE_DEVIS, _bloc_ratio_dc_ac, conception_du_calepinage,
        )

        champs = dict(ond_n_mppt=2, ond_mppt_v_min=120.0, ond_mppt_v_max=500.0, ond_v_max_abs=600.0,
                      ond_i_max_mppt_a=26.0, ond_ac_kw=10.0, ond_phases=3, ond_dc_max_kwc=Decimal('20'))
        for role, source, conforme in (('onduleur_hybride', SOURCE_BORNE_CAPACITE, True),
                                       ('', SOURCE_BORNE_DEVIS, False)):
            with self.subTest(role=role):
                # Nom SANS « hybride » (ni le rôle écrit dedans : le nom est le dernier rang).
                onduleur = self._produit(nom='Deye SUN-10K-SG04 %s' % ('A' if role else 'B'),
                                         type_fiche='onduleur', **champs)
                Produit.objects.filter(pk=onduleur.pk).update(role_devis=role)
                # ``conception_du_calepinage`` rend ``(conception, materiel, donnees, document)``.
                conception, materiel, _donnees, _document = conception_du_calepinage(
                    self._calepinage(onduleur_produit=onduleur.pk))
                self.assertEqual(materiel['familles']['onduleur'], (role, ''))  # lu par resoudre_materiel
                self.assertEqual(conception.entree.onduleur.role, role)
                bloc, _avertissements = _bloc_ratio_dc_ac(conception)
                self.assertEqual((bloc['borne_source'], bloc['dans_bornes']), (source, conforme))
                self.assertGreater(bloc['valeur'], 1.35)  # la borne de ratio l'aurait refusé

    # ACAL616 — retenu + voisins de puissance, évalués à chaud, sans écrire.
    def _onduleur(self, nom, ac_kw):
        champs = dict(ond_n_mppt=2, ond_mppt_v_min=120.0, ond_mppt_v_max=500.0,
                      ond_v_max_abs=600.0, ond_i_max_mppt_a=26.0,
                      ond_phases=3)
        if ac_kw is not None:
            champs['ond_ac_kw'] = ac_kw
        return self._produit(nom=nom, type_fiche='onduleur', **champs)

    def _servi(self, calepinage):
        reponse = self.api.get(
            '/api/django/calepinage/calepinages/%s/configurations-onduleur/'
            % calepinage.pk)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return reponse.json()

    def test_voisins_dessus_dessous_et_fiche_incomplete(self):
        import json
        import pathlib

        six = self._onduleur('Onduleur 6 kW', 6.0)
        huit = self._onduleur('Onduleur 8 kW', 8.0)
        cinq = self._onduleur('Onduleur 5 kW', 5.0)
        sans = self._onduleur('Onduleur sans AC', None)
        calepinage = self._calepinage(onduleur_produit=six.pk)
        avant = Calepinage.objects.get(pk=calepinage.pk).resultat
        servi = self._servi(calepinage)
        echantillon = json.loads((pathlib.Path(__file__).resolve().parent.parent
                                  / 'contract_samples'
                                  / 'calepinage_configurations_onduleur.json')
                                 .read_text(encoding='utf-8'))['exemple']
        self.assertEqual(sorted(servi), sorted(echantillon))
        lignes = servi['configurations']
        self.assertEqual([(ligne['role'], ligne['produit_id'])
                          for ligne in lignes],
                         [('retenue', six.pk), ('plus_puissant', huit.pk),
                          ('moins_puissant', cinq.pk)])
        for ligne in lignes:
            self.assertEqual(sorted(ligne),
                             sorted(echantillon['configurations'][0]))
            attendu = evaluation_electrique(
                calepinage, entree={'onduleur_produit': ligne['produit_id']})
            self.assertEqual(ligne['verdict'], attendu['verdict'])
            self.assertEqual(ligne['alertes'], attendu['alertes'])
        self.assertEqual(servi['retenue']['produit_id'], six.pk)
        self.assertIn(sans.pk, [f['produit_id']
                                for f in servi['fiches_incompletes']])
        self.assertIsNone(servi['motif_vide'])
        self.assertNotIn('prix', json.dumps(servi))
        self.assertEqual(Calepinage.objects.get(pk=calepinage.pk).resultat,
                         avant)

    def test_sans_voisin_au_dessus(self):
        cinq = self._onduleur('Onduleur 5 kW', 5.0)
        # Le catalogue porte aussi « Onduleur 10 kW » (setUp) : retenu = 10.
        calepinage = self._calepinage()
        servi = self._servi(calepinage)
        self.assertEqual([ligne['role'] for ligne in servi['configurations']],
                         ['retenue', 'moins_puissant'])
        self.assertEqual(servi['configurations'][1]['produit_id'], cinq.pk)
        self.assertIn('plus puissant', servi['motif_vide'])

    def test_aucun_onduleur_designe(self):
        servi = self._servi(self._calepinage(onduleur_produit=None))
        self.assertIsNone(servi['retenue'])
        self.assertEqual(servi['configurations'], [])
        self.assertIn('Matériel électrique', servi['motif_vide'])

    # ACAL934 — l'état à trois valeurs, le MÊME dans les quatre lectures.
    def _quatre_lectures(self, calepinage):
        from apps.calepinage.services.assistant import _bloc_electrique
        from apps.calepinage.services.electrique import verdict_de_conception

        lectures = (verdict_publiable(calepinage),
                    verdict_de_conception(calepinage),
                    evaluation_electrique(calepinage),
                    _bloc_electrique(calepinage)[0])
        return {(lecture['etat'], lecture['points']) for lecture in lectures}

    def test_sans_module_ni_onduleur_quatre_fois_a_completer(self):
        calepinage = self._calepinage(module_produit=None,
                                      onduleur_produit=None)
        publication = verdict_publiable(calepinage)
        abstentions = sum(motif['statut'] in ('non_verifiable', 'omis',
                                              'sans_source')
                          for motif in publication['motifs'])
        self.assertGreater(abstentions, 0, publication['motifs'])
        self.assertEqual(self._quatre_lectures(calepinage),
                         {('a_completer', abstentions)})
        self.assertTrue(publication['publiable'])
        self.assertEqual(evaluation_electrique(calepinage)['verdict'],
                         'indetermine')
        import json
        import pathlib

        from apps.calepinage.services.electrique import verdict_de_conception

        contrat = json.loads((pathlib.Path(__file__).resolve().parent.parent
                              / 'contract_samples'
                              / 'calepinage_publication_electrique.json')
                             .read_text(encoding='utf-8'))['exemple_evaluation']
        self.assertEqual(sorted(publication), sorted(contrat['publication']))
        self.assertEqual(sorted(verdict_de_conception(calepinage)),
                         sorted(contrat['electrique']))

    def test_bloquant_puis_lectures_identiques(self):
        imposee = [{'module': 'a#%d' % rang, 'chaine': 2, 'mppt': 1,
                    'onduleur': 1} for rang in range(1, 21)]
        calepinage = self._calepinage(affectation_manuelle=imposee)
        motifs = verdict_publiable(calepinage)['motifs']
        bloquants = sum(motif['statut'] == 'bloquant' for motif in motifs)
        self.assertGreater(bloquants, 0, motifs)
        self.assertEqual(self._quatre_lectures(calepinage),
                         {('bloquant', bloquants)})
        self.assertEqual(len(self._quatre_lectures(self._calepinage())), 1)


class EtatDePublicationPur(SimpleTestCase):
    """ACAL934 — la règle de rangement, sans base (mutant : un
    ``non_verifiable`` rangé en « pret » échoue ici)."""

    def test_rangement(self):
        from apps.calepinage.services.etat_dossier_electrique import (
            etat_a_chaud, etat_de_publication,
        )

        def motifs(*statuts):
            return [{'statut': statut} for statut in statuts]

        cas = (((), ('pret', 0)), (('ok', 'alerte'), ('pret', 0)),
               (('non_verifiable',), ('a_completer', 1)),
               (('omis', 'sans_source', 'ok'), ('a_completer', 2)),
               (('bloquant', 'omis', 'bloquant'), ('bloquant', 2)))
        for statuts, attendu in cas:
            with self.subTest(statuts=statuts):
                etat = etat_de_publication(motifs(*statuts))
                self.assertEqual((etat['etat'], etat['points']), attendu)
        self.assertEqual(etat_a_chaud(['x'], ['y']),
                         {'etat': 'bloquant', 'points': 1})
        self.assertEqual(etat_a_chaud([], ['y', 'z']),
                         {'etat': 'a_completer', 'points': 2})
        self.assertEqual(etat_a_chaud([], []), {'etat': 'pret', 'points': 0})


DOCUMENT_982 = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'userJourneyPro11.document.json'


def _pan_982(count, azimut, inclinaison, famille, watt):
    return {'count': count, 'azimuthDeg': azimut, 'tiltDeg': inclinaison, 'family': famille,
            'kwc': round(count * watt / 1000, 3), 'moduleId': 'module-%d' % watt}


CHAMP_982 = {'id': 'champ-1', 'kind': 'sol', 'label': 'CHAMP-SOL', 'moduleWc': 710, 'tiltDeg': 20.0,
             'rowAzimuthDeg': 90.0, 'engine': {'modules': 24}}
#: ACAL982 — un cas = une ligne (nom, pan, fiche W, surface de pose). L'est-ouest est à 10° : la seule
#: série PVGIS enregistrée (aucune à 15°).
CAS_982 = (
    ('pan Sud', _pan_982(12, 180.0, 15.0, 'surimposition', 720), 720, None),
    ('pan est-ouest', _pan_982(20, 90.0, 10.0, 'eastwest', 720), 720, None),
    ('module catalogue 710 W', _pan_982(12, 180.0, 15.0, 'surimposition', 710), 710, None),
    ('toit + champ', _pan_982(12, 180.0, 15.0, 'surimposition', 710), 710, CHAMP_982),
)
#: L'écart DÉCIDÉ, publié (jamais une exemption de code) : atelier et PDF du devis peuvent différer, nommé à l'écran.
ECARTS_DECIDES_982 = ({'grandeur': 'production annuelle', 'surfaces': ('atelier', 'PDF'), 'statut': 'écart décidé',
                       'decision': 'ACAL1001', 'nomme_par': 'BandeauProvenanceProduction.jsx::EcartDevis'},)


def document_982(pan, watt, champ):
    doc = json.loads(DOCUMENT_982.read_text(encoding='utf-8'))
    doc['zones'][0].update(id='z1', geometry=dict(pan), pitchDeg=pan['tiltDeg'], facingAzimuthDeg=pan['azimuthDeg'],
                           roofType='flat' if pan['family'] == 'eastwest' else 'pitched')
    doc['modules'] = [{'id': pan['moduleId'], 'pmaxWc': watt}]
    if champ:
        doc['poseSurfaces'] = [dict(champ)]
    return doc


def surfaces_982(doc, watt):
    """{grandeur: {surface: valeur}} — chaque lecture du serveur."""
    from apps.calepinage.services.mesures import mesures_du_document
    from apps.calepinage.tests.test_golden_trois_projets import simuler_projet
    from apps.ventes.domain.etude_schema import cles_etude_du_layout
    from apps.ventes.domain.geometrie import lire_layout

    simule, mesures = simuler_projet(None, layout=doc, watt=watt), mesures_du_document(doc)
    p50 = simule['total']['p50_kwh']
    stockee = cles_etude_du_layout('residentiel', {'annualKwh': p50}, doc).get('production_annuelle')
    production = {'simulation Total': round(p50),
                  'somme des pans simulés': round(sum(pan['p50_kwh'] for pan in simule['par_pan']))}
    if stockee is not None:
        production['devis production_annuelle'] = stockee
    return {
        'kWc du pan toit': {
            'document geometry.kwc': doc['zones'][0]['geometry']['kwc'],
            'liste (mesures du pan)': mesures['pans'][0]['kwc'],
            'simulation (pan)': simule['par_pan'][0]['kwc']},
        'kWc total': {
            'liste (kwc_pose)': mesures['kwc'],
            'étude (puissance_kwc)': lire_layout(doc, toit_plat_corrige=True).kwc,
            'simulation Total': simule['total']['kwc'],
            'somme des pans simulés': sum(pan['kwc'] for pan in simule['par_pan'])},
        'production annuelle': production,
    }


def ecarts_982(cas, surfaces):
    ecarts = []
    for grandeur, lues in surfaces.items():
        (premiere, attendu), *autres = lues.items()
        for surface, valeur in autres:
            if attendu is None or valeur is None or round(float(valeur), 3) != round(float(attendu), 3):
                ecarts.append('%s — %s : %s = %s, %s = %s' % (cas, grandeur, premiere, attendu, surface, valeur))
    return ecarts


class GrandeurUnique(SimpleTestCase):
    """ACAL982 — une grandeur, une valeur, sur le document golden (jumeau web : userJourneyPro11.test.ts). Les
    quatre lectures « à compléter » sans matériel : ``VerdictUnique.test_sans_module_ni_onduleur_quatre_fois_a_
    completer`` (base réelle, jouée en CI)."""

    def test_chaque_cas_une_valeur(self):
        for cas, pan, watt, champ in CAS_982:
            with self.subTest(cas=cas):
                self.assertEqual(ecarts_982(cas, surfaces_982(document_982(pan, watt, champ), watt)), [])

    def test_la_garde_nomme_un_document_faux(self):
        cas, pan, watt, champ = CAS_982[2]
        faux = document_982(dict(pan, kwc=8.64), watt, champ)
        self.assertIn('module catalogue 710 W — kWc du pan toit : document geometry.kwc = 8.64, '
                      'liste (mesures du pan) = 8.52', ecarts_982(cas, surfaces_982(faux, watt)))

    def test_le_seul_ecart_admis_est_publie(self):
        self.assertEqual([(e['statut'], e['decision'], e['nomme_par']) for e in ECARTS_DECIDES_982],
                         [('écart décidé', 'ACAL1001', 'BandeauProvenanceProduction.jsx::EcartDevis')])
