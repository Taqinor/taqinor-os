"""ACAL104 (C-ACAL-101, D-ACAL-6) — le résultat du calepinage et le rapport
d'étude publient l'écart entre la production du DEVIS (moteur devis, imprimée
au client) et le P50 de l'étude technique — jamais l'inverse.

* ``resultat.ecart_devis`` = ``{devis, reference, production_devis_kwh,
  p50_calepinage_kwh, ecart_pct, mention}`` (contrat
  ``calepinage_resultat.json``, ``exemple_ecart_devis``) ; la production du
  devis est LUE par ``apps.ventes.selectors.production_attendue_pour_devis``
  (figure recalée, ACAL101) — jamais un RENDU du devis : le rendu relit ce
  résultat (ombrage servi, D-RES-2710-1) et crée le profil société (ACON87) ;
* ``null`` sans devis lié, sans simulation, ou simulation périmée ;
* la section « Production » du rapport d'étude imprime les deux chiffres et
  l'écart (mêmes valeurs que le JSON).

``resultat_calepinage`` RÉEL (matériel injecté par son seam de test, comme
CALX70) ; sélecteur ventes RÉEL sur un devis en base.

Run :
    python manage.py test apps.calepinage.tests.test_acal_ecart_devis -v2
"""
import copy
import json
import pathlib
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    BLOCS_SIMULATION, CLE_SIMULATION, MENTION_ECART_DEVIS, _ecart_devis,
    resultat_calepinage,
)
from apps.calepinage.services.ecart_devis import ecart_devis_et_motif
from apps.calepinage.services.rapport.production import html_de_section
from apps.ventes.models import Devis

from .test_acal_cible_lead import _valeurs
from .test_acal_materiel_electrique import LAYOUT as LAYOUT_PAN, BaseMateriel
from .test_api_liste import BaseApiCalepinage
from .test_calx70_resultat_sert_la_simulation import (
    LAYOUT, LAYOUT_MODIFIE, MATERIEL, SIMULATION,
)

#: ACAL2017 — la pose du cas 1742 rejoué : 24 panneaux de 710 Wc (17,04 kWc) sur un pan sud.
LAYOUT_1742 = {**LAYOUT_PAN, 'zones': [dict(LAYOUT_PAN['zones'][0], neededPanels=24, result={'count': 24})]}

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads(
    (ECHANTILLONS / 'calepinage_resultat.json').read_text(encoding='utf-8'))

P50 = 15606.0
PRODUCTION_DEVIS = 10340


def _simulation(empreinte):
    depose = {CLE_SIMULATION: {'hash_entree': empreinte,
                               'version_moteur': 'essai',
                               'calcule_le': '2026-10-01T09:00:00Z',
                               'duree_s': 3.0}}
    for cle in BLOCS_SIMULATION:
        depose[cle] = copy.deepcopy(SIMULATION['exemple'][cle])
    depose['production']['total']['p50_kwh'] = P50
    return depose


class EcartDevisTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-202610-0648', statut='brouillon',
            etude_params={'production_annuelle': PRODUCTION_DEVIS,
                          'production_source': 'saisie'})

    def _calepinage(self, *, devis=True, layout=LAYOUT, simule=True):
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            devis=self.devis if devis else None, titre='ACAL104',
            roof_layout=copy.deepcopy(LAYOUT))
        if simule:
            empreinte = resultat_calepinage(
                calepinage, materiel=MATERIEL)['hash_entree']
            calepinage.resultat = _simulation(empreinte)
        calepinage.roof_layout = copy.deepcopy(layout)
        calepinage.save()
        return calepinage

    def test_resultat_publie_ecart_devis(self):
        resultat = resultat_calepinage(self._calepinage(), materiel=MATERIEL)
        self.assertTrue(resultat['simule'])
        self.assertEqual(resultat['ecart_devis'], {
            'devis': self.devis.pk,
            'reference': 'DEV-202610-0648',
            'production_devis_kwh': float(PRODUCTION_DEVIS),
            'p50_calepinage_kwh': P50,
            'ecart_pct': 50.9,
            'mention': MENTION_ECART_DEVIS,
        })
        # Même forme (mêmes clés) que l'échantillon du contrat partagé.
        self.assertEqual(set(resultat['ecart_devis']),
                         set(CONTRAT['exemple_ecart_devis']['ecart_devis']))
        self.assertEqual(MENTION_ECART_DEVIS,
                         CONTRAT['exemple_ecart_devis']['ecart_devis'][
                             'mention'])
        # D-ACAL-6 — le devis ne lit JAMAIS le P50 : sa production est
        # inchangée après la lecture du résultat.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['production_annuelle'],
                         PRODUCTION_DEVIS)

    def test_ecart_null_sans_devis_ou_perime(self):
        sans_devis = self._calepinage(devis=False)
        self.assertIsNone(resultat_calepinage(
            sans_devis, materiel=MATERIEL)['ecart_devis'])
        sans_devis.delete()
        non_simule = self._calepinage(simule=False)
        self.assertIsNone(resultat_calepinage(
            non_simule, materiel=MATERIEL)['ecart_devis'])
        non_simule.delete()
        perime = self._calepinage(layout=LAYOUT_MODIFIE)
        resultat = resultat_calepinage(perime, materiel=MATERIEL)
        self.assertTrue(resultat['simulation_perimee'])
        self.assertIsNone(resultat['ecart_devis'])
        # Devis sans production : rien à comparer.
        Devis.objects.filter(pk=self.devis.pk).update(etude_params={})
        perime.delete()
        frais = self._calepinage()
        self.assertIsNone(resultat_calepinage(
            frais, materiel=MATERIEL)['ecart_devis'])

    def test_figure_non_imprimee_jamais_dite_imprimee(self):
        """ACAL1274 (T2-F2-RESU-024) — la figure POSÉE par le calepinage
        (``production_source='calepinage'``) n'est plus imprimée par le PDF
        aux règles corrigées (AMOT15 : le moteur du devis la recalcule), ni
        une figure C&I (le PDF imprime le moteur C&I) : aucun écart « imprimé
        au client » n'est servi. Règles d'origine : le PDF imprime la figure
        stockée, l'écart est servi."""
        calepinage = self._calepinage()
        cas = (({'production_source': 'calepinage'}, {}, False),
               ({'production_source': 'saisie'}, {'mode_installation': 'commercial'}, False),
               ({'production_source': 'calepinage'}, {'regles_calcul': 1}, True))
        for source, champs, servi in cas:
            Devis.objects.filter(pk=self.devis.pk).update(
                etude_params=dict(source, production_annuelle=PRODUCTION_DEVIS),
                mode_installation=champs.get('mode_installation', 'residentiel'),
                regles_calcul=champs.get('regles_calcul', 14))
            ecart = resultat_calepinage(calepinage, materiel=MATERIEL)['ecart_devis']
            self.assertEqual(ecart is not None, servi, (source, champs))

    def test_devis_d_une_autre_conception_sans_ecart(self):
        """ACON27 (C-ACON-137) — le devis imprime une AUTRE conception (12
        modules, H1) que le calepinage (20 modules, H2) : aucun écart servi ni
        imprimé ; empreintes égales : écart servi ; empreinte inconnue : servi."""
        calepinage = self._calepinage()
        h1, h2 = 'a' * 64, 'b' * 64
        Calepinage.objects.filter(pk=calepinage.pk).update(layout_hash=h2)
        calepinage.refresh_from_db()
        for empreinte_devis, servi in ((h1, False), (h2, True), (None, True)):
            Devis.objects.filter(pk=self.devis.pk).update(layout_hash=empreinte_devis)
            resultat = resultat_calepinage(calepinage, materiel=MATERIEL)
            with self.subTest(empreinte_devis=empreinte_devis):
                self.assertEqual(resultat['ecart_devis'] is not None, servi)
                self.assertEqual('production-ecart-devis' in html_de_section({'resultat': resultat}), servi)
                # ACAL1915 — jamais un silence : la garde en cause est dite.
                self.assertEqual(resultat['ecart_devis_motif'], (
                    '' if servi else CONTRAT['acal1915_motifs']['a_resynchroniser']))

    def test_rapport_etude_imprime_ecart(self):
        exemple = CONTRAT['exemple_ecart_devis']
        html = html_de_section({'resultat': exemple})
        ecart = exemple['ecart_devis']
        self.assertIn('production-ecart-devis', html)
        self.assertIn(ecart['reference'], html)
        self.assertIn('12\u202f600,0', html)   # production du devis, telle quelle
        self.assertIn('13\u202f000,0', html)   # P50 de l'étude
        self.assertIn('+3,2 %', html)
        # ACAL1755 (D-ACAL-86, D-ACAL-96) — deux chiffres différents : chacun
        # NOMMÉ, et le devis envoyé n'est pas modifié (révision proposée).
        self.assertIn('Production retenue par le devis', html)
        self.assertIn('Production simulée de la pose', html)
        self.assertIn("devis envoyé n'est pas modifié : une révision est proposée",
                      html.replace('&#x27;', "'"))
        self.assertNotIn('moteur du devis', html)
        self.assertNotIn('D-ACAL-6', html)
        # Sans écart servi : aucun bloc.
        sans = dict(exemple, ecart_devis=None)
        self.assertNotIn('production-ecart-devis',
                         html_de_section({'resultat': sans}))
        # Les MÊMES valeurs que le JSON servi, sur un vrai calepinage.
        servi = resultat_calepinage(self._calepinage(), materiel=MATERIEL)
        html = html_de_section({'resultat': servi})
        self.assertIn('10\u202f340,0', html)
        self.assertIn('15\u202f606,0', html)
        self.assertIn('+50,9 %', html)
        self.assertEqual(Decimal('50.9'),
                         Decimal(str(servi['ecart_devis']['ecart_pct'])))

    def test_acal1956_production_retenue_par_le_devis_les_trois_etats(self):
        # Sans devis : rien.
        sans = self._calepinage(devis=False, simule=False)
        self.assertIsNone(resultat_calepinage(sans, materiel=MATERIEL)['production_devis'])
        sans.delete()
        # Devis encore brouillon : rien (le client ne l'a pas reçu).
        brouillon = self._calepinage(simule=False)
        self.assertIsNone(resultat_calepinage(brouillon, materiel=MATERIEL)['production_devis'])
        brouillon.delete()
        # Devis envoyé, SANS simulation : la production du devis, telle quelle.
        Devis.objects.filter(pk=self.devis.pk).update(statut='envoye')
        non_simule = self._calepinage(simule=False)
        servi = resultat_calepinage(non_simule, materiel=MATERIEL)
        self.assertFalse(servi['simule'])
        self.assertEqual(servi['production_devis'], {
            'devis': self.devis.pk, 'reference': 'DEV-202610-0648', 'statut': 'envoye',
            'production_annuelle_kwh': float(PRODUCTION_DEVIS), 'production_origine': 'production_annuelle'})
        self.assertEqual(set(servi['production_devis']),
                         set(CONTRAT['exemple_ecart_devis']['production_devis']))
        non_simule.delete()
        # Devis envoyé, AVEC simulation : les deux chiffres côte à côte, devis inchangé.
        servi = resultat_calepinage(self._calepinage(), materiel=MATERIEL)
        self.assertEqual(servi['production_devis']['production_annuelle_kwh'], float(PRODUCTION_DEVIS))
        self.assertEqual(servi['production']['total']['p50_kwh'], P50)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['production_annuelle'], PRODUCTION_DEVIS)


class EcartDevisSansRenduTest(SimpleTestCase):
    """L'écart de l'atelier lit la figure du devis par le sélecteur YSERV8,
    jamais par un rendu ``build_quote_data`` : le rendu d'un devis brouillon
    relit ``resultat_calepinage`` (ombrage servi, D-RES-2710-1 — boucle) et
    crée le profil société absent, qui périme la simulation (ACON87). Sans
    base : devis et sélecteurs sont des doublures."""

    def _ecart(self, production):
        devis = SimpleNamespace(pk=71, company_id=3, reference='DEV-202611-0071', roof_layout={})
        calepinage = SimpleNamespace(devis_id=71, company_id=3)
        with mock.patch('apps.ventes.selectors.get_devis_by_pk', return_value=devis), \
                mock.patch('apps.ventes.selectors_calepinage._conception_a_jour', return_value=True), \
                mock.patch('apps.ventes.selectors.production_attendue_pour_devis',
                           return_value=production) as lue, \
                mock.patch('apps.ventes.quote_engine.builder.build_quote_data') as rendu:
            ecart = _ecart_devis(calepinage, 4808.0)
        rendu.assert_not_called()
        lue.assert_called_once_with(71)
        return ecart

    def test_la_phrase_porte_la_figure_du_devis_sans_rendu(self):
        ecart = self._ecart(Decimal('3628'))
        self.assertEqual(ecart['production_devis_kwh'], 3628.0)
        self.assertEqual(ecart['ecart_pct'], round((4808 - 3628) / 3628 * 100, 1))
        self.assertIn('3\u202f628,0', html_de_section({'resultat': {'ecart_devis': ecart}}))

    def test_acal1755_un_seul_chiffre_quand_devis_et_simulation_sont_egaux(self):
        """ACAL1755 (D-ACAL-86) — même chiffre au kWh près : le rapport n'en
        imprime qu'UN, sans écart ni proposition de révision."""
        ecart = self._ecart(Decimal('4808.3'))
        html = html_de_section({'resultat': {'ecart_devis': ecart}})
        self.assertIn('production-ecart-devis', html)
        self.assertEqual(html.count('4 808'), 1)
        self.assertIn('Production — devis DEV-202611-0071 et simulation de la pose', html)
        self.assertNotIn('Écart', html)
        self.assertNotIn('révision', html)

    def test_sans_production_aucune_phrase(self):
        """Pompage : aucune production au devis ⇒ aucun écart, jamais un 0."""
        self.assertIsNone(self._ecart(None))
        self.assertEqual(html_de_section({'resultat': {'ecart_devis': None}}).count('production-ecart-devis'), 0)


class EcartDevisMotifTest(SimpleTestCase):
    """ACAL1915 — un devis LIÉ sans écart servi : ``ecart_devis_motif`` dit la
    garde en cause, phrase du contrat (``acal1915_motifs``) mot pour mot ;
    jamais un silence. ``''`` sans devis lié ou quand l'écart est servi."""

    MOTIFS = CONTRAT['acal1915_motifs']

    def _lu(self, *, p50=4808.0, devis_id=71, devis=True, societe=3, a_jour=True,
            imprimee=True, production=Decimal('3628')):
        trouve = (SimpleNamespace(pk=71, company_id=societe, reference='DEV-202611-0071')
                  if devis else None)
        calepinage = SimpleNamespace(devis_id=devis_id, company_id=3)
        with mock.patch('apps.ventes.selectors.get_devis_by_pk', return_value=trouve), \
                mock.patch('apps.ventes.selectors_calepinage._conception_a_jour', return_value=a_jour), \
                mock.patch('apps.ventes.selectors_calepinage.figure_stockee_imprimee', return_value=imprimee), \
                mock.patch('apps.ventes.selectors.production_attendue_pour_devis', return_value=production), \
                mock.patch('apps.ventes.quote_engine.builder.build_quote_data') as rendu:
            lu = ecart_devis_et_motif(calepinage, p50)
        rendu.assert_not_called()
        return lu

    def test_devis_lie_sans_ecart_toujours_un_motif_du_contrat(self):
        cas = {'simulation': {'p50': None},
               'devis_introuvable': {'devis': False},
               'autre_societe': {'societe': 9},
               'a_resynchroniser': {'a_jour': False},
               'production_recalculee_au_rendu': {'imprimee': False},
               'sans_production': {'production': None},
               'production_nulle': {'production': Decimal('0')}}
        attendu = {'autre_societe': 'devis_introuvable', 'production_nulle': 'sans_production'}
        for nom, champs in cas.items():
            with self.subTest(cas=nom):
                ecart, motif = self._lu(**champs)
                self.assertIsNone(ecart)
                self.assertEqual(motif, self.MOTIFS[attendu.get(nom, nom)])

    def test_sans_devis_ou_ecart_servi_aucun_motif(self):
        self.assertEqual(self._lu(devis_id=None), (None, ''))
        ecart, motif = self._lu()
        self.assertEqual(ecart['production_devis_kwh'], 3628.0)
        self.assertEqual(motif, '')
        # Le seul cas qui compte au rendu reste celui de ``_ecart_devis``.
        self.assertEqual(set(ecart), set(CONTRAT['exemple_ecart_devis']['ecart_devis']))

    def test_le_contrat_porte_la_cle_dans_chaque_exemple(self):
        for etat in ('exemple', 'exemple_perime', 'exemple_vide', 'exemple_ecart_devis'):
            self.assertEqual(CONTRAT[etat]['ecart_devis_motif'], '', etat)
        fragment = CONTRAT['acal1915_ecart_devis_motif']
        self.assertIsNone(fragment['ecart_devis'])
        self.assertIn(fragment['ecart_devis_motif'], self.MOTIFS.values())


class PariteLead1742Test(BaseMateriel):
    """ACAL2017 (C4-E5, PARITÉ) — le lead 1742 rejoué en fabrique, dans SA vérité : résidentiel,
    deux options, conception rangée à 35 panneaux de 710 Wc (option « sans », onduleur HYBRIDE de
    12 kW à capacité publiée de 18 kWc, chaînes de 12), pose réelle de 24 panneaux (17,04 kWc :
    dans les 18 kWc publiés). Le calepinage lit la cible, le matériel et la chaîne de la
    conception : 35, l'hybride de l'option « sans », 12, aucun « contre 16 » — sur un BROUILLON,
    SANS devis et avec le devis ENVOYÉ, à l'identique.

    Revue E6 m4 — le test d'avant (capacité relevée à 30, cas du devis envoyé retiré, état jugé
    par ``assertNotEqual``) est rétabli. Les verdicts rangés sont ceux que le moteur juge pour SA
    conception (``porte_calepinage.verdicts_electriques`` sur 35 panneaux, 24,85 kWc), rangés
    par l'écrivain du modèle. Le contrôle de ratio de « Prêt à envoyer ? » doit juger la POSE
    réelle : « ok » (aucune alerte 1,50 nulle part, vérifié dès aujourd'hui) — c'est l'item M4
    de la lane du moteur (``pret_a_envoyer.py``), d'où le seul test marqué « échec attendu »."""

    def setUp(self):
        super().setUp()
        from apps.ventes.conception.porte_calepinage import verdicts_electriques
        from apps.ventes.models import ConceptionLead

        self.hybride = self._produit(
            nom='Onduleur hybride Deye 12 kW', type_fiche='onduleur', ond_n_mppt=2, ond_mppt_v_min=160.0,
            ond_mppt_v_max=950.0, ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0, ond_ac_kw=12.0, ond_phases=3,
            ond_dc_max_kwc=Decimal('18'))
        hybride = {'produit': self.hybride.pk, 'designation': self.hybride.nom, 'quantite': 1}
        chaines = [{'nb_modules': 12, 'conforme': True}] * 2 + [{'nb_modules': 11, 'conforme': True}]
        design = {'ratio_dc_ac': 2.07, 'chaines': chaines,
                  'materiel': {'onduleur': {'designation': self.hybride.nom, 'ac_kw': 12.0}}}
        verdicts = {'valeur': verdicts_electriques(self.company, design, [hybride], 24.85),
                    'unite': None, 'source': 'moteur'}
        option = dict(_valeurs(35, watt=710, module=self.module_devis.nom, module_produit=self.module_devis.pk,
                               onduleur=hybride, longueur=12), verdicts=verdicts)
        ConceptionLead.ranger(
            lead=self.lead, etat='complet', refus=None, marche='residentiel', option_retenue='sans',
            valeurs={'sans': option, 'avec': option}, blocs={}, entrees_utilisees={}, suppositions=[],
            empreinte='c' * 64, empreinte_pose='', niveau_regles=14, version_moteur='moteur-unique-1',
            declencheur={'raison': 'remplissage', 'champs': [], 'origine': 'remplissage'})

    def _cas(self):
        """Les trois cas du lead 1742 : ``{nom: devis}`` — brouillon, aucun devis, devis ENVOYÉ."""
        envoye = self._devis(self.module_devis, self.hybride)
        Devis.objects.filter(pk=envoye.pk).update(statut=Devis.Statut.ENVOYE, reference='DEV-ACAL56-2')
        return {'brouillon': self._devis(self.module_devis, self.hybride), 'sans_devis': None,
                'envoye': Devis.objects.get(pk=envoye.pk)}

    def _lu(self, devis):
        """``(cible, onduleur, provenance, longueur de référence)``, le contrôle de ratio, le texte servi."""
        from apps.calepinage.services.devis import _cible_du_calepinage
        from apps.calepinage.services.electrique import resoudre_materiel
        from apps.calepinage.services.pret_a_envoyer import controles_electriques

        calepinage = self._calepinage(devis=devis)
        calepinage.roof_layout = copy.deepcopy(LAYOUT_1742)
        calepinage.save(update_fields=['roof_layout'])
        cible = _cible_du_calepinage(calepinage)
        materiel = resoudre_materiel(self.company, {}, calepinage=calepinage)
        servi = resultat_calepinage(calepinage)
        ratio = next(c for c in controles_electriques(calepinage) if c['code'] == 'ratio_dc_ac')
        return ((cible['panneaux'], materiel['produits']['onduleur'], materiel['provenances']['onduleur'],
                 servi['longueur_chaine']['longueur_dossier']), ratio,
                json.dumps([servi, ratio], ensure_ascii=False, default=str))

    def test_lead_1742_trente_cinq_hybride_chaines_de_douze_sans_seize_ni_1_50(self):
        for cas, devis in self._cas().items():
            with self.subTest(cas=cas):
                lu, _ratio, texte = self._lu(devis)
                self.assertEqual(lu, (35, self.hybride.pk, 'moteur', 12))
                self.assertNotIn('contre 16', texte)
                self.assertNotIn('1,50', texte)

    def test_lead_1742_ratio_juge_pour_la_pose_reelle_ok(self):
        for cas, devis in self._cas().items():
            with self.subTest(cas=cas):
                _lu, ratio, _texte = self._lu(devis)
                self.assertEqual(ratio['etat'], 'ok', ratio)
