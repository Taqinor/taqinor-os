"""ACAL310 — la consommation PROPOSÉE par le serveur (D-ACAL-20).

Constats C-ACAL-145 / C-ACAL-125 / C-ACAL-004 : le seul écrivain de
``roof_layout.consumption`` était l'atelier TS, sur un barème REGIE figé ; les
fonctions serveur (profil depuis le lead, kWh par le barème SOCIÉTÉ,
appareils + charges, Ramadan, aperçu CSV) n'avaient aucune porte ; la
simulation ignorait ``consumption.saisons`` ; ``profil_depuis_import`` ne
nourrissait aucun profil type.

``POST calepinages/<pk>/consommation/proposer/`` les branche (lecture PURE),
``courbe_charge`` lit les saisons, ``PUT parametres/profils-types/`` accepte
``depuis_import``.

Base de test réelle, barème société RÉEL (``TariffSettings``), lead réel,
client HTTP réel ; la simulation réelle (client rejoué) pour les saisons.
Aucun mock de la source.

Run :
    python manage.py test apps.calepinage.tests.test_acal_consommation_proposee -v2
"""
from __future__ import annotations

import copy
from decimal import Decimal

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.consommation import (
    MOIS_ETE, apercu_courbe_csv, _interpoler_factures,
)
from apps.calepinage.services.courbe_charge import construire_courbe_charge
from apps.parametres.models_tariff import TariffSettings
from apps.parametres.tariff import kwh_depuis_facture

from .test_api_liste import BaseApiCalepinage
from .test_calx5_simulation import LAYOUT

BASE = '/api/django/calepinage/calepinages/'
URL_PROFILS = '/api/django/calepinage/parametres/profils-types/'

APPAREILS = [
    {'kind': 'frigo', 'label': 'Réfrigérateur', 'dailyKwh': 1.2,
     'startHour': 0, 'endHour': 24, 'billing': 'foyer',
     'provenance': 'saisi'},
    {'kind': 'four', 'label': 'Four', 'dailyKwh': 2.0, 'startHour': 18,
     'endHour': 21, 'billing': 'foyer', 'provenance': 'saisi'},
]


class _Base(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.lead.facture_hiver = Decimal('650')
        self.lead.facture_ete = Decimal('900')
        self.lead.ete_differente = True
        self.lead.type_installation = 'residentiel'
        self.lead.save()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Conso 310', roof_layout=copy.deepcopy(LAYOUT))
        self.url = f'{BASE}{self.calepinage.pk}/consommation/proposer/'

    def _proposer(self, corps):
        return self.api.post(self.url, corps, format='json')


class ProposerTest(_Base):

    def test_lead_factures_bareme_societe(self):
        # Le barème de la SOCIÉTÉ, modifié : un prix unique de 2,00 MAD/kWh
        # (jamais le barème REGIE figé de l'atelier).
        reglages = TariffSettings.get(company=self.company)
        reglages.residential_tiers = [{'max_kwh': None,
                                       'prix_kwh_ttc': '2.00'}]
        # Un barème RÉGLÉ déclare aussi ses charges fixes d'abonnement :
        # sans elles, ``kwh_depuis_facture`` refuse de convertir (kwh None,
        # motif nommé — CALX257) plutôt que de compter le compteur en kWh.
        reglages.redevance_compteur_mad_mois = Decimal('39.94')
        reglages.save()

        reponse = self._proposer({'source': 'lead'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        reglages = TariffSettings.get(company=self.company)
        attendu = 0.0
        for montant in _interpoler_factures(650.0, 900.0):
            kwh = kwh_depuis_facture(reglages, montant,
                                     classe='residentiel')['kwh']
            attendu += float(kwh)
        self.assertAlmostEqual(reponse.data['kwh_annuel'], attendu,
                               delta=0.2)
        consumption = reponse.data['consumption']
        self.assertEqual(consumption['source']['bareme'], 'societe')
        self.assertEqual(consumption['source']['origine'], 'lead')
        self.assertEqual(len(reponse.data['courbe24']), 24)
        self.assertIn('ete', reponse.data['saisons'])
        self.assertGreater(reponse.data['saisons']['ete'],
                           reponse.data['saisons']['hiver'])
        # Lecture PURE : rien n'est écrit.
        self.calepinage.refresh_from_db()
        self.assertNotIn('consumption', self.calepinage.roof_layout)

    def _poser_bareme(self):
        """Le barème RÉEL de la société (prix unique + redevance) : sans lui
        les factures ne se convertissent pas en kWh (CALX257)."""
        reglages = TariffSettings.get(company=self.company)
        reglages.residential_tiers = [{'max_kwh': None,
                                       'prix_kwh_ttc': '2.00'}]
        reglages.redevance_compteur_mad_mois = Decimal('39.94')
        reglages.save()

    def test_lead_residentiel_prend_la_forme_du_devis_presence_supposee(self):
        """ACAL1967 — la forme horaire est celle que le devis prend (présence en
        journée par défaut), dite avec la valeur du champ ``occupation_jour``."""
        from apps.calepinage.services.consommation import AVIS_FORME_UNIFORME
        from apps.ventes.courbes_journalieres import (
            OCCUPATION_PRESENCE, silhouette_occupation)

        self._poser_bareme()
        reponse = self._proposer({'source': 'lead'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        courbe = reponse.data['courbe24']
        silhouette = silhouette_occupation(OCCUPATION_PRESENCE)
        jour_moyen = reponse.data['kwh_annuel'] / 365.0
        for heure in range(24):
            self.assertAlmostEqual(courbe[heure],
                                   jour_moyen * silhouette[heure], places=2)
        self.assertGreater(len(set(courbe)), 1, 'forme uniforme')
        self.assertAlmostEqual(sum(courbe), jour_moyen, delta=0.05)
        avis = ' '.join(reponse.data['avertissements'])
        self.assertIn('présence en journée', avis)
        self.assertIn('« occupation_jour »', avis)
        self.assertIn('présence supposée', avis)
        self.assertNotIn(AVIS_FORME_UNIFORME, reponse.data['avertissements'])
        self.assertEqual(reponse.data['consumption']['courbe24'], courbe)

    def test_lead_absent_en_journee_prend_la_forme_d_absence(self):
        from apps.ventes.courbes_journalieres import (
            OCCUPATION_ABSENCE, OCCUPATION_PRESENCE, silhouette_occupation)

        self.lead.occupation_jour = 'absent'
        self.lead.save()
        self._poser_bareme()

        reponse = self._proposer({'source': 'lead'})

        courbe = reponse.data['courbe24']
        jour_moyen = reponse.data['kwh_annuel'] / 365.0
        absence = silhouette_occupation(OCCUPATION_ABSENCE)
        presence = silhouette_occupation(OCCUPATION_PRESENCE)
        self.assertAlmostEqual(courbe[12], jour_moyen * absence[12], places=2)
        self.assertNotAlmostEqual(courbe[12], jour_moyen * presence[12],
                                  places=2)
        avis = ' '.join(reponse.data['avertissements'])
        self.assertIn('absence en journée', avis)
        self.assertIn('absent', avis)
        self.assertNotIn('supposée', avis)

    def test_lead_commercial_garde_sa_classe_saisie_et_la_forme_uniforme(self):
        from apps.calepinage.services.consommation import AVIS_FORME_UNIFORME

        self._poser_bareme()
        reponse = self._proposer({'source': 'lead', 'classe': 'force_motrice'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        self.assertEqual(len(set(reponse.data['courbe24'])), 1)
        self.assertIn(AVIS_FORME_UNIFORME, reponse.data['avertissements'])

    # ── ACAL2020 (D-ACAL-97) — le chemin lead lit la CONCEPTION, plus les factures ──

    KWH_CONCEPTION = [700.0, 650.0, 600.0, 560.0, 620.0, 800.0, 950.0, 980.0, 760.0, 600.0, 640.0, 720.0]

    def _ranger(self, marche, blocs):
        from apps.ventes.models import ConceptionLead

        return ConceptionLead.ranger(
            lead=self.lead, etat='complet', refus=None, marche=marche, option_retenue='sans',
            valeurs={'sans': {}}, blocs=blocs, entrees_utilisees={}, suppositions=[], empreinte='c' * 64,
            empreinte_pose='', niveau_regles=14, version_moteur='moteur-unique-1',
            declencheur={'raison': 'remplissage', 'champs': [], 'origine': 'remplissage'})

    def test_acal2020_lead_residentiel_kwh_et_forme_de_la_conception(self):
        """Lead résidentiel (présence en journée supposée) : les douze kWh de la conception
        (``blocs.etude_horaire.mois[].consommation_kwh``), jamais le barème appliqué aux
        factures ; la forme = la silhouette d'occupation du moteur, jamais uniforme."""
        from apps.calepinage.services.consommation import AVIS_FORME_UNIFORME
        from apps.ventes.courbes_journalieres import OCCUPATION_PRESENCE, silhouette_occupation

        self._poser_bareme()  # un barème RÉGLÉ : l'ancien chemin aurait converti les factures
        version = self._ranger('residentiel', {'etude_horaire': {
            'occupation': OCCUPATION_PRESENCE,
            'mois': [{'mois': rang + 1, 'consommation_kwh': kwh} for rang, kwh in enumerate(self.KWH_CONCEPTION)]}})

        reponse = self._proposer({'source': 'lead'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        self.assertEqual(reponse.data['kwh_annuel'], round(sum(self.KWH_CONCEPTION), 1))
        jour_moyen = sum(self.KWH_CONCEPTION) / 365.0
        silhouette = silhouette_occupation(OCCUPATION_PRESENCE)
        for heure in range(24):
            self.assertAlmostEqual(reponse.data['courbe24'][heure], jour_moyen * silhouette[heure], places=2)
        self.assertGreater(reponse.data['saisons']['ete'], reponse.data['saisons']['hiver'])
        avis = reponse.data['avertissements']
        self.assertNotIn(AVIS_FORME_UNIFORME, avis)
        self.assertIn('Consommation lue sur la conception du lead (version %s)' % version.version, ' '.join(avis))
        self.lead.refresh_from_db()
        self.assertEqual((self.lead.facture_hiver, self.lead.facture_ete), (Decimal('650'), Decimal('900')))

    def test_acal2020_lead_residentiel_forme_horaire_24_servie_par_le_moteur(self):
        """Reste d'ACAL2020 — la conception SERT la forme 24 h que le moteur résidentiel a
        vraiment utilisée (occupation + équipements, ``valeurs.<option>.forme_horaire_24``) :
        le calepinage la lit telle quelle, ni silhouette recomposée ici ni forme uniforme."""
        from apps.calepinage.services.consommation import AVIS_FORME_UNIFORME

        parts = [0.02] * 8 + [0.06] * 12 + [0.03] * 4  # une journée chargée le jour (somme = 1)
        version = self._ranger('residentiel', {'etude_horaire': {
            'occupation': 'presence_jour',
            'mois': [{'mois': rang + 1, 'consommation_kwh': kwh} for rang, kwh in enumerate(self.KWH_CONCEPTION)]}})
        type(version).objects.filter(pk=version.pk).update(
            niveau_regles=15,  # relecture m2 : la forme du moteur n'est lue qu'au niveau 15
            valeurs={'sans': {'forme_horaire_24': {'valeur': parts, 'unite': 'part', 'source': 'moteur'}}})

        reponse = self._proposer({'source': 'lead'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        jour_moyen = sum(self.KWH_CONCEPTION) / 365.0
        for heure in range(24):  # mutant « silhouette d'occupation » ou « uniforme » : rouge
            self.assertAlmostEqual(reponse.data['courbe24'][heure], jour_moyen * parts[heure], places=3)
        self.assertNotIn(AVIS_FORME_UNIFORME, reponse.data['avertissements'])

    def test_m2_au_niveau_14_la_silhouette_d_occupation_reste(self):
        """Relecture du lot 4, m2 — une conception rangée au niveau 14 (courant) qui porte la
        forme 24 h du moteur : le calepinage garde la silhouette d'occupation qu'il prenait
        avant (aucun chiffre du calepinage ne bouge au niveau 14)."""
        from apps.ventes.courbes_journalieres import OCCUPATION_PRESENCE, silhouette_occupation

        parts = [0.02] * 8 + [0.06] * 12 + [0.03] * 4
        version = self._ranger('residentiel', {'etude_horaire': {
            'occupation': OCCUPATION_PRESENCE,
            'mois': [{'mois': rang + 1, 'consommation_kwh': kwh} for rang, kwh in enumerate(self.KWH_CONCEPTION)]}})
        type(version).objects.filter(pk=version.pk).update(
            valeurs={'sans': {'forme_horaire_24': {'valeur': parts, 'unite': 'part', 'source': 'moteur'}}})

        reponse = self._proposer({'source': 'lead'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        jour_moyen = sum(self.KWH_CONCEPTION) / 365.0
        silhouette = silhouette_occupation(OCCUPATION_PRESENCE)
        for heure in range(24):  # mutant « forme du moteur lue à tout niveau » : rouge
            self.assertAlmostEqual(reponse.data['courbe24'][heure], jour_moyen * silhouette[heure], places=2)

    def test_acal2020_lead_commercial_forme_horaire_de_la_conception(self):
        """Lead commercial : la journée moyenne des jours types de la conception
        (``blocs.etude_ci.profil_charge.jours_types``, pondérée par ``nb_jours``) —
        plus de forme uniforme."""
        from apps.calepinage.services.consommation import AVIS_FORME_UNIFORME

        ouvre = [0.0] * 7 + [10.0] * 11 + [0.0] * 6
        repos = [1.0] * 24
        jours = []
        for mois in range(1, 13):
            jours += [{'mois': mois, 'type_jour': 'ouvre', 'nb_jours': 22, 'charge_kwh': ouvre},
                      {'mois': mois, 'type_jour': 'repos', 'nb_jours': 8, 'charge_kwh': repos}]
        self._ranger('commercial', {'etude_ci': {
            'profil_charge': {'archetype': 'bureau', 'jours_types': jours},
            'bilan': {'par_mois': [{'mois': rang + 1, 'consommation_kwh': kwh}
                                   for rang, kwh in enumerate(self.KWH_CONCEPTION)]}}})

        reponse = self._proposer({'source': 'lead', 'classe': 'force_motrice'})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        self.assertEqual(reponse.data['kwh_annuel'], round(sum(self.KWH_CONCEPTION), 1))
        moyenne = [(22 * o + 8 * r) / 30.0 for o, r in zip(ouvre, repos)]
        jour_moyen = sum(self.KWH_CONCEPTION) / 365.0
        for heure in range(24):
            self.assertAlmostEqual(reponse.data['courbe24'][heure],
                                   jour_moyen * moyenne[heure] / sum(moyenne), places=3)
        self.assertNotIn(AVIS_FORME_UNIFORME, reponse.data['avertissements'])

    def test_acal2020_releve_colle_reste_au_calepinage_jamais_sur_le_lead(self):
        """Un relevé collé reste la saisie du calepinage : la conception du lead ne le
        remplace pas, et rien n'est écrit sur le lead."""
        self._ranger('residentiel', {'etude_horaire': {
            'mois': [{'mois': rang + 1, 'consommation_kwh': kwh} for rang, kwh in enumerate(self.KWH_CONCEPTION)]}})
        contenu = 'kwh\n' + '\n'.join(['0.5'] * 8760)

        reponse = self._proposer({'source': 'csv', 'csv': {'contenu': contenu}})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        self.assertEqual(reponse.data['courbe24'], [0.5] * 24)
        self.assertEqual(reponse.data['consumption']['source']['origine'], 'csv')
        self.lead.refresh_from_db()
        self.assertEqual((self.lead.facture_hiver, self.lead.facture_ete), (Decimal('650'), Decimal('900')))

    def test_appareils_et_climatisation(self):
        reponse = self._proposer({
            'source': 'appareils', 'appareils': APPAREILS,
            'charges': {'climatisation': {
                'btu': 12000, 'eer': 3.2,
                'heures_fonctionnement': [13, 14, 15, 16]}}})

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        courbe = reponse.data['courbe24']
        # 3,2 kWh/j d'appareils + 12000/3.2/1000 × 4 h = 15 kWh de clim.
        self.assertAlmostEqual(sum(courbe), 3.2 + 15.0, delta=0.05)
        self.assertGreater(courbe[14], courbe[3])
        self.assertEqual(reponse.data['consumption']['methode'], 'appareils')

    def test_ramadan_decale_la_courbe(self):
        sans = self._proposer({'source': 'appareils', 'appareils': APPAREILS})
        avec = self._proposer({'source': 'appareils', 'appareils': APPAREILS,
                               'ramadan': {'actif': True,
                                           'jour': '2026-03-01'}})

        self.assertEqual(avec.status_code, 200, avec.content[:300])
        self.assertNotEqual(avec.data['courbe24'], sans.data['courbe24'])
        self.assertAlmostEqual(sum(avec.data['courbe24']),
                               sum(sans.data['courbe24']), delta=0.01)
        self.assertEqual(avec.data['consumption']['methode'], 'courbe')

    def test_csv_illisible_409_nomme(self):
        # ERR-ENF11-FUZZ-CALEPINAGE (w4) : le CONTENU du CSV est un fait que le
        # schéma publié ne peut pas dire -> 409 (la FORME du corps reste 400).
        reponse = self._proposer({'source': 'csv', 'csv': {
            'contenu': 'horodatage;kwh\n2026-01-01T00:00:00+01:00;0.12\n',
            'colonne': 'kwh_x'}})

        self.assertEqual(reponse.status_code, 409, reponse.content[:300])
        self.assertTrue(any(cle.startswith('csv.') for cle in reponse.data),
                        reponse.data)

    def test_forme_du_corps_400_avant_le_contenu(self):
        """La source, la classe, le TYPE des sous-documents et la présence de
        celui de la source choisie : un 400 qui nomme le champ."""
        for corps, champ in (
                ({}, 'source'), ({'source': 'xml'}, 'source'),
                ({'source': 'lead', 'classe': 'luxe'}, 'classe'),
                ({'source': 'factures'}, 'factures'),
                ({'source': 'factures', 'factures': 5}, 'factures'),
                ({'source': 'appareils'}, 'appareils'),
                ({'source': 'appareils', 'appareils': 0}, 'appareils'),
                ({'source': 'appareils', 'appareils': [1]}, 'appareils'),
                ({'source': 'appareils', 'appareils': [], 'charges': []},
                 'charges'),
                ({'source': 'csv'}, 'csv'),
                ({'source': 'lead', 'ramadan': 'oui'}, 'ramadan')):
            reponse = self._proposer(corps)
            self.assertEqual(reponse.status_code, 400, (corps, reponse.data))
            self.assertIn(champ, reponse.data)

    def test_contenu_refuse_409_nomme_et_jamais_500(self):
        for corps, champ in (
                ({'source': 'appareils', 'appareils': APPAREILS,
                  'charges': {'frigo': {}}}, 'charges.frigo'),
                ({'source': 'appareils', 'appareils': APPAREILS,
                  'charges': {'climatisation': 5}}, 'charges.climatisation'),
                ({'source': 'appareils', 'appareils': APPAREILS,
                  'charges': {'climatisation': {'zzz': 1}}},
                 'charges.climatisation.zzz'),
                ({'source': 'appareils', 'appareils': [{}]}, 'appareils'),
                ({'source': 'csv', 'csv': {}}, 'csv')):
            reponse = self._proposer(corps)
            self.assertEqual(reponse.status_code, 409, (corps, reponse.data))
            self.assertTrue(any(cle.startswith(champ) for cle in reponse.data),
                            (corps, reponse.data))

    def test_facture_non_finie_409_et_lead_absent_404(self):
        refus = self._proposer({'source': 'factures',
                                'factures': {'classe': 'residentiel'}})
        self.assertEqual(refus.status_code, 409)
        self.assertIn('factures.hiver_mad', refus.data)

        sans_lead = Calepinage.objects.create(
            company=self.company, client_id=self.client_a.pk,
            titre='Sans lead')
        reponse = self.api.post(
            f'{BASE}{sans_lead.pk}/consommation/proposer/',
            {'source': 'lead'}, format='json')
        self.assertEqual(reponse.status_code, 409)

    def test_profil_depuis_import_cree_un_profil_societe(self):
        lignes = ['horodatage;kwh'] + [
            f'2025-01-01T00:00:00+00:00;{0.5 + (heure % 24) / 48:.3f}'
            for heure in range(8760)]
        apercu = apercu_courbe_csv('\n'.join(lignes), colonne='kwh')

        reponse = self.api.put(URL_PROFILS, {'depuis_import': {
            'apercu': apercu, 'cle': 'releve_maison', 'libelle': 'Relevé',
            'famille': 'residentiel', 'origine': 'Relevé SRM 2025'}},
            format='json')

        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        lecture = self.api.get(URL_PROFILS)
        cles = [profil.get('cle') for profil in lecture.data['profils']]
        self.assertIn('releve_maison', cles)


class ProfilsTypesPutEnBaseTest(BaseApiCalepinage):
    """ERR-ENF11-FUZZ-CALEPINAGE (w4) — ``PUT parametres/profils-types/`` :
    FORME fautive 400 (chemin ``profils[<rang>].<champ>``), état 409 (clé en
    double, journée entièrement nulle), écriture 200 (la CI est la gate)."""

    JOURNEE = [1.0] * 12 + [2.0] * 12

    def _ligne(self, **surcharges):
        ligne = {'cle': 'maison-1', 'courbe': {'annuel': self.JOURNEE},
                 'provenance': 'Relevé de 12 factures, 2025.'}
        ligne.update(surcharges)
        return ligne

    def test_forme_fautive_400_nomme_la_ligne(self):
        reponse = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(), self._ligne(
                cle='autre', provenance='  ')]}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('profils[1].provenance', reponse.data)
        reponse = self.api.put(URL_PROFILS, {'profils': 'x'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('profils', reponse.data)

    def test_etat_409_cle_en_double_et_journee_nulle(self):
        doublon = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(),
                                      self._ligne(cle='MAISON-1')]},
            format='json')
        self.assertEqual(doublon.status_code, 409, doublon.data)
        self.assertIn('maison-1', doublon.data)
        nulle = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(
                courbe={'annuel': [0] * 24})]}, format='json')
        self.assertEqual(nulle.status_code, 409, nulle.data)
        self.assertIn('maison-1.courbe', nulle.data)

    def test_ecriture_200_remplace_les_profils_de_la_societe(self):
        reponse = self.api.put(
            URL_PROFILS, {'profils': [self._ligne(famille='commercial')]},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        cles = [p['cle'] for p in reponse.data['profils']
                if p['source'] == 'societe']
        self.assertEqual(cles, ['maison-1'])


class CorpsProposerPublieTest(SimpleTestCase):
    """ERR-ENF11-FUZZ-CALEPINAGE (w4) — le corps de ``consommation/proposer`` :
    UN prédicat, publié ET appliqué, sans base."""

    @staticmethod
    def _valider(corps):
        from apps.calepinage.serializers_conso import (
            ConsommationProposerCorpsSerializer,
        )

        champs = ConsommationProposerCorpsSerializer(data=corps)
        return champs.is_valid(), dict(champs.errors)

    def test_formes_valides(self):
        for corps in ({'source': 'lead'}, {'source': 'lead', 'classe':
                                           'domestique', 'ramadan': {}},
                      {'source': 'factures', 'factures': {},
                       'classe': 'agricole'},
                      {'source': 'appareils', 'appareils': []},
                      {'source': 'appareils', 'appareils': APPAREILS,
                       'charges': {'pac': {}}},
                      {'source': 'csv', 'csv': {'contenu': ''}}):
            self.assertTrue(self._valider(corps)[0], corps)

    def test_formes_fautives_nomment_le_champ(self):
        for corps, champ in (
                (None, 'non_field_errors'), ([], 'non_field_errors'),
                ({}, 'source'), ({'source': 5}, 'source'),
                ({'source': 'lead', 'classe': ''}, 'classe'),
                ({'source': 'lead', 'factures': []}, 'factures'),
                ({'source': 'lead', 'appareils': {}}, 'appareils'),
                ({'source': 'lead', 'appareils': ['x']}, 'appareils'),
                ({'source': 'lead', 'csv': None}, 'csv'),
                ({'source': 'factures'}, 'factures'),
                ({'source': 'appareils'}, 'appareils'),
                ({'source': 'csv'}, 'csv')):
            valide, erreurs = self._valider(corps)
            self.assertFalse(valide, corps)
            self.assertIn(champ, erreurs)

    def test_le_corps_ne_se_donne_qu_en_json(self):
        # CI #1001 : en multipart / urlencoded un sous-document (objet, liste)
        # ne se transporte pas (liste vide = aucune part) — le schéma publié
        # ne déclare donc QUE ``application/json``.
        from rest_framework.parsers import JSONParser

        from apps.calepinage.views.consommation import proposer_consommation

        self.assertEqual(proposer_consommation.kwargs['parser_classes'],
                         [JSONParser])

    def test_classes_saisissables_et_schema_oneof(self):
        from apps.calepinage.serializers_conso import classes_tarifaires
        from apps.parametres.tariff import CLASSES_INVERSION

        self.assertEqual(set(classes_tarifaires()),
                         {*CLASSES_INVERSION, 'domestique'})
        from apps.calepinage.services.consommation import SOURCES_PROPOSITION
        from apps.calepinage.serializers_conso import SOURCES_CONSOMMATION

        self.assertEqual(SOURCES_CONSOMMATION, SOURCES_PROPOSITION)


class FormeDuMoteurAuNiveau14Test(SimpleTestCase):
    """Relecture du lot 4, m2 — la forme 24 h du moteur résidentiel (``conception/moteur.py::
    forme_horaire_24`` : douze jours types de ``etude_horaire.jours_types_annee`` pondérés par
    leurs jours) n'est PAS la silhouette d'occupation (``courbes_journalieres.
    silhouette_occupation``) que le calepinage prenait avant : la lire déplace la courbe, donc
    l'autoconsommation et la couverture du calepinage. Elle n'est lue qu'au niveau 15."""

    def test_la_forme_du_moteur_differe_de_la_silhouette_pour_un_lead_present_sans_equipement(self):
        from apps.ventes import courbes_journalieres as cj
        from apps.ventes.etude_horaire import jours_types_annee

        jours, _avis, _sources = jours_types_annee(kwc=4.0, conso_kwh_mensuelles=[597.0] * 12,
                                                   ville='Casablanca', occupation=cj.OCCUPATION_PRESENCE)
        self.assertEqual(len(jours or []), 12)
        total = [sum(jour['conso_24h'][heure] * jour['jours'] for jour in jours) for heure in range(24)]
        forme = [valeur / sum(total) for valeur in total]
        silhouette = cj.silhouette_occupation(cj.OCCUPATION_PRESENCE)
        self.assertGreater(max(abs(a - b) for a, b in zip(forme, silhouette)), 1e-3)


class SaisonsLuesParLaSimulationTest(SimpleTestCase):
    """``consumption.saisons`` module la courbe de charge de la simulation."""

    def _serie(self):
        points = [{'annee': 2021, 'mois': mois, 'jour': 15, 'heure': heure,
                   'p_ac_kw': 1.0}
                  for mois in (1, 7) for heure in range(24)]
        return {'points': points, 'pas_minutes': 60,
                'colonne_energie': 'p_ac_kw'}

    def _charge(self, saisons=None):
        consumption = {'courbe24': [0.5] * 24, 'methode': 'courbe',
                       'source': {'origine': 'essai'}}
        if saisons:
            consumption['saisons'] = saisons
        return construire_courbe_charge(
            self._serie(), consommation={'layout': {
                'consumption': consumption}})

    def test_saisons_lues_par_la_simulation(self):
        sans = self._charge()
        avec = self._charge({'ete': 1.5, 'hiver': 0.8})

        self.assertEqual(sans['courbe'][:24], sans['courbe'][24:])
        janvier, juillet = avec['courbe'][:24], avec['courbe'][24:]
        self.assertIn(7, MOIS_ETE)
        self.assertAlmostEqual(janvier[0], 0.5 * 0.8)
        self.assertAlmostEqual(juillet[0], 0.5 * 1.5)
        self.assertTrue(any('saisonnalité SAISIE' in texte
                            for texte in avec['avertissements']))


class FacturesMoisTest(SimpleTestCase):
    """ACAL836 — de 1 à 12 factures (MAD ou kWh), les mois vides estimés."""

    @staticmethod
    def proposer(mois, **corps):
        from types import SimpleNamespace

        from apps.calepinage.services.consommation import (
            proposer_consommation,
        )

        return proposer_consommation(
            SimpleNamespace(lead_id=None, roof_layout={}),
            dict({'source': 'factures', 'factures': {'mois': mois}}, **corps),
            company=None)

    def test_trois_factures_kwh_douze_mois_dont_neuf_estimes(self):
        rendu = self.proposer([{'mois': 1, 'kwh': 300},
                               {'mois': 7, 'kwh': 500},
                               {'mois': 10, 'kwh': 400}])
        mois = rendu['mois']
        self.assertEqual(len(mois), 12)
        self.assertEqual([m['source'] for m in mois].count('estime'), 9)
        self.assertEqual({m['mois'] for m in mois if m['source'] == 'facture'},
                         {1, 7, 10})
        attendu = {2: 333.3, 3: 366.7, 4: 400.0, 5: 433.3, 6: 466.7,
                   8: 466.7, 9: 433.3, 11: 366.7, 12: 333.3}
        for rang, kwh in attendu.items():
            self.assertEqual(mois[rang - 1]['kwh'], kwh, rang)
        self.assertIn('9 mois estimés', ' '.join(rendu['avertissements']))
        # des kWh seuls ne demandent pas de classe tarifaire.
        self.assertIsNotNone(rendu['consumption'])

    def test_un_seul_mois_est_recopie(self):
        rendu = self.proposer([{'mois': 4, 'kwh': 250}])
        self.assertEqual({m['kwh'] for m in rendu['mois']}, {250.0})
        self.assertEqual(rendu['kwh_annuel'], 3000.0)

    def test_un_mois_en_mad_non_convertible_laisse_consumption_nul(self):
        rendu = self.proposer([{'mois': 1, 'mad': 800}], classe='residentiel')
        self.assertIsNone(rendu['consumption'])
        self.assertTrue(rendu['avertissements'])

    def test_des_mad_sans_classe_sont_refuses_en_nommant_classe(self):
        from apps.calepinage.services.consommation import ProfilInvalide

        with self.assertRaises(ProfilInvalide) as capture:
            self.proposer([{'mois': 1, 'mad': 800}])
        self.assertEqual(capture.exception.champ, 'classe')

    def test_refus_nommes(self):
        from apps.calepinage.services.consommation import ProfilInvalide

        cas = (
            ([{'mois': 1, 'kwh': 300}, {'mois': 2, 'kwh': -5}],
             'factures.mois[1].kwh'),
            ([{'mois': 13, 'kwh': 300}], 'factures.mois[0].mois'),
            ([{'mois': 3, 'kwh': 1}, {'mois': 3, 'kwh': 2}],
             'factures.mois[1].mois'),
            ([{'mois': 3}], 'factures.mois[0].mad'),
            ([{'mois': 3, 'mad': 5, 'kwh': 5}], 'factures.mois[0].kwh'),
        )
        for mois, champ in cas:
            with self.subTest(champ=champ):
                with self.assertRaises(ProfilInvalide) as capture:
                    self.proposer(mois, classe='residentiel')
                self.assertEqual(capture.exception.champ, champ)

    def test_hiver_mad_reste_exige_sans_mois(self):
        from apps.calepinage.services.consommation import (
            ProfilInvalide, proposer_consommation,
        )
        from types import SimpleNamespace

        with self.assertRaises(ProfilInvalide) as capture:
            proposer_consommation(
                SimpleNamespace(lead_id=None, roof_layout={}),
                {'source': 'factures', 'factures': {}}, company=None)
        self.assertEqual(capture.exception.champ, 'factures.hiver_mad')

    def test_l_exemple_du_contrat_est_ce_que_le_service_rend(self):
        import json
        import pathlib

        contrat = json.loads(
            (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
             / 'calepinage_consommation_proposee.json')
            .read_text(encoding='utf-8'))
        rendu = self.proposer(contrat['corps_factures_mois']['factures']
                              ['mois'])
        attendu = contrat['exemple_factures_mois']
        self.assertEqual(rendu['mois'], attendu['mois'])
        self.assertEqual(rendu['kwh_annuel'], attendu['kwh_annuel'])


class LireFactureTest(BaseApiCalepinage):
    """ACAL839 — ``consommation/lire-facture/`` : la lecture d'une photo de
    facture, en proposition ; l'OCR (serveur IA) est simulé, jamais appelé."""

    def setUp(self):
        super().setUp()
        import json
        import pathlib

        self.contrat = json.loads(
            (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
             / 'calepinage_consommation_photo_facture.json')
            .read_text(encoding='utf-8'))
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Facture 839',
            roof_layout=copy.deepcopy(LAYOUT))
        self.url = f'{BASE}{self.calepinage.pk}/consommation/lire-facture/'

    def _photo(self, octets=b'photo', nom='facture.jpg'):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return {'fichier': SimpleUploadedFile(nom, octets,
                                              content_type='image/jpeg')}

    def _poster(self, corps, api=None):
        return (api or self.api).post(self.url, corps, format='multipart')

    def test_ocr_coupe_get_faux_et_post_200_lignes_vides_sans_reseau(self):
        from unittest import mock

        with mock.patch('requests.post', side_effect=AssertionError('réseau')):
            lu = self.api.get(self.url)
            reponse = self._poster(self._photo())
        self.assertEqual(lu.status_code, 200)
        self.assertEqual(dict(lu.data), self.contrat['exemple_indisponible'])
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(dict(reponse.data),
                         self.contrat['exemple_indisponible'])

    def test_ocr_actif_simule_rend_une_ligne_sans_mois_et_n_ecrit_rien(self):
        from unittest import mock

        from django.test import override_settings

        reponse_ocr = mock.Mock(status_code=200)
        reponse_ocr.json.return_value = {
            'donnees_structurees': {'conso_kwh': 412}}
        with override_settings(CRM_CAPTURE_OCR_ENABLED=True), \
                mock.patch('apps.crm.intake_photo._service_token_for',
                           return_value='jeton'), \
                mock.patch('requests.post', return_value=reponse_ocr):
            lu = self.api.get(self.url)
            reponse = self._poster(self._photo())
        self.assertEqual(dict(lu.data), self.contrat['exemple_disponibilite'])
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(dict(reponse.data), self.contrat['exemple'])
        self.assertIsNone(reponse.data['lignes'][0]['mois'])
        self.calepinage.refresh_from_db()
        self.assertNotIn('consumption', self.calepinage.roof_layout)

    def test_fichier_absent_ou_trop_gros_400_nomme(self):
        absent = self._poster({})
        self.assertEqual(absent.status_code, 400)
        self.assertEqual(dict(absent.data), self.contrat['refus_400_fichier'])
        gros = self._poster(self._photo(b'x' * (11 * 1024 * 1024)))
        self.assertEqual(gros.status_code, 400)
        self.assertIn('fichier', gros.data)

    def test_sans_droit_403_et_autre_societe_404(self):
        self.assertEqual(
            self._poster(self._photo(), api=self.api_sans).status_code, 403)
        self.assertEqual(
            self._poster(self._photo(), api=self.api_autre).status_code, 404)
        self.assertEqual(self.api_autre.get(self.url).status_code, 404)

    def test_le_contrat_porte_les_motifs_du_service(self):
        from apps.crm.intake_photo import MOTIF_OCR_DESACTIVE
        from apps.calepinage.views.consommation import REFUS_FICHIER

        self.assertEqual(self.contrat['exemple_indisponible']['motif'],
                         MOTIF_OCR_DESACTIVE)
        self.assertEqual(self.contrat['refus_400_fichier']['fichier'],
                         REFUS_FICHIER)
