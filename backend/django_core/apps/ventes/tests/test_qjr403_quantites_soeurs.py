"""QJR403 / QJR4-1 — quand la quantité de la ligne panneau dominante est
réécrite, ses quantités SŒURS le sont aussi.

TEST ROUGE D'ABORD. ``pipeline._appliquer_preseance_quantite`` écrivait
``lignes_in[dominante.index]['quantite'] = str(quantite)`` depuis
``taille.nb_panneaux`` — et RIEN d'autre. Or les quantités dérivées du MÊME
compte ne sont posées qu'à la COMPOSITION (``domain/composition`` :
``ajouter('panneau', panneau, nb)``, ``ajouter(role_structure, structure, nb)``,
``ajouter('socle', premier('socle'), nb * 2)``).

Sur le chemin ``MODE_ECRIRE`` — celui auquel ``ecrire_lignes`` est liée — le
devis sortait donc avec un nombre de panneaux À JOUR et une structure / des
socles PÉRIMÉS : N panneaux montés sur M structures. Une nomenclature fausse et
un prix faux (confirmé HAUT par la ronde de vérification V3) : ``ecrire`` et
``reconcilier`` ne se composaient pas.

Le rapport sœur reste celui de la composition (structure = nb, socle = nb × 2)
et n'est JAMAIS recalculé selon une seconde formule :
``composition.quantites_derivees_du_compte`` en est la seule définition, et les
deux chemins la consomment.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr403_quantites_soeurs"
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.domain.composition import quantites_derivees_du_compte
from apps.ventes.domain.pipeline import _appliquer_preseance_quantite
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


def _specs(nb_panneaux):
    """Les specs de l'écrivain pour un kit composé à ``nb_panneaux``."""
    derivees = quantites_derivees_du_compte(nb_panneaux)
    return [
        {'designation': 'Onduleur réseau Huawei 10kW Triphasé',
         'quantite': '1', 'prix_unitaire': '16666.67', 'ordre': 0},
        {'designation': 'Panneau Canadian Solar 710W',
         'quantite': str(nb_panneaux), 'prix_unitaire': '1166.67',
         'ordre': 1},
        {'designation': 'Structure acier',
         'quantite': str(derivees['structure']), 'prix_unitaire': '416.67',
         'ordre': 2},
        {'designation': 'Socle béton',
         'quantite': str(derivees['socle']), 'prix_unitaire': '120',
         'ordre': 3},
        {'designation': 'Installation', 'quantite': '1',
         'prix_unitaire': '5000', 'ordre': 4},
    ]


class _Base(TestCase):

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._seq = 0

    def _devis(self, cible=None):
        self._seq += 1
        devis = make_devis(
            self.company, self.user, self.client_obj,
            [('Panneau Canadian Solar 710W', '10', '1166.67')],
            reference='DEV-QJR403-%04d' % self._seq)
        if cible is not None:
            from apps.ventes.domain import overrides as registre
            registre.ecrire_colonne(
                devis,
                registre.fusionner(
                    devis, {'taille.nb_panneaux': {'valeur': cible}},
                    utilisateur=self.user))
        return devis


class LesSoeursSuiventLaDominante(_Base):

    def test_structure_et_socle_suivent_le_nouveau_compte(self):
        """ROUGE AVANT : la structure gardait N et le socle N × 2."""
        specs = _specs(10)
        devis = self._devis(cible=14)
        _appliquer_preseance_quantite(devis, specs)
        par_designation = {s['designation']: s['quantite'] for s in specs}
        self.assertEqual(par_designation['Panneau Canadian Solar 710W'], '14')
        self.assertEqual(par_designation['Structure acier'], '14')
        self.assertEqual(par_designation['Socle béton'], '28')

    def test_les_lignes_etrangeres_au_compte_ne_bougent_pas(self):
        specs = _specs(10)
        devis = self._devis(cible=14)
        _appliquer_preseance_quantite(devis, specs)
        par_designation = {s['designation']: s['quantite'] for s in specs}
        self.assertEqual(
            par_designation['Onduleur réseau Huawei 10kW Triphasé'], '1')
        self.assertEqual(par_designation['Installation'], '1')

    def test_une_soeur_verrouillee_reste_souveraine(self):
        """D12 — ``quantite_manuelle`` est la quantité TAPÉE par le vendeur."""
        specs = _specs(10)
        for spec in specs:
            if spec['designation'] == 'Socle béton':
                spec['quantite_manuelle'] = True
        devis = self._devis(cible=14)
        _appliquer_preseance_quantite(devis, specs)
        par_designation = {s['designation']: s['quantite'] for s in specs}
        self.assertEqual(par_designation['Structure acier'], '14')
        self.assertEqual(par_designation['Socle béton'], '20')


class SansSurchargeRienNeBouge(_Base):
    """Un devis dont la quantité dominante n'est PAS surchargée est
    inchangé — au centime comme à l'octet."""

    def test_les_specs_sont_identiques(self):
        specs = _specs(10)
        avant = [dict(spec) for spec in specs]
        _appliquer_preseance_quantite(self._devis(), specs)
        self.assertEqual(specs, avant)

    def test_une_cible_egale_au_compte_ne_reecrit_rien(self):
        specs = _specs(10)
        avant = [dict(spec) for spec in specs]
        _appliquer_preseance_quantite(self._devis(cible=10), specs)
        self.assertEqual(specs, avant)


class UneSeuleDefinitionDuRapportSoeur(SimpleTestCase):
    """La composition et le pipeline lisent LA MÊME définition."""

    def test_le_rapport_est_celui_de_la_composition(self):
        for nb in (0, 1, 7, 14, 26):
            self.assertEqual(quantites_derivees_du_compte(nb),
                             {'structure': nb, 'socle': nb * 2})

    def test_une_valeur_illisible_ne_fabrique_aucune_quantite(self):
        self.assertEqual(quantites_derivees_du_compte(None),
                         {'structure': 0, 'socle': 0})
        self.assertEqual(quantites_derivees_du_compte('abc'),
                         {'structure': 0, 'socle': 0})
        self.assertEqual(quantites_derivees_du_compte(Decimal('-3')),
                         {'structure': 0, 'socle': 0})

    def test_acal927_les_affleurants_ne_prennent_ni_structure_ni_socle(self):
        """48 sur 48 ⇒ 0 et 0 ; 40 + 8 ⇒ 8 et 16 ; plus d'affleurants que de
        panneaux ⇒ 0 ; 0 (défaut) ⇒ inchangé. Mutant : ignorer ⇒ 2N."""
        self.assertEqual(quantites_derivees_du_compte(48, 48), {'structure': 0, 'socle': 0})
        self.assertEqual(quantites_derivees_du_compte(48, 40), {'structure': 8, 'socle': 16})
        self.assertEqual(quantites_derivees_du_compte(48, 60), {'structure': 0, 'socle': 0})
        self.assertEqual(quantites_derivees_du_compte(48, 0), quantites_derivees_du_compte(48))


class ACAL927PoseAffleuranteKitDeFixation(_Base):
    """D-ACAL-39 — un toit en pente à panneaux affleurants ne vend que le kit
    de fixation ; jamais de structure de repli ni de prix inventé."""

    LAYOUT = {'zones': [{'id': 'A', 'geometry': {'count': 48, 'flush': True}}]}

    def _catalogue(self, kit=True):
        from apps.stock.models import Produit
        from apps.ventes.tests.test_composition_source_unique import CATALOGUE
        lignes = list(CATALOGUE) + ([('Kit de fixation toit en pente', 'KIT-FIX', '90')] if kit else [])
        return [Produit.objects.create(
            company=self.company, nom=nom, sku='%s-927-%s' % (sku, self.company.pk),
            prix_vente=Decimal(prix), prix_achat=Decimal('1'), quantite_stock=1000)
            for nom, sku, prix in lignes]

    def _lignes(self, affleurants, kit=True, avertissements=None):
        from apps.ventes.domain.composition import composition_residentielle
        lignes = composition_residentielle(
            self._catalogue(kit), kwc=34.08, panel_watt=710, nb_panneaux=48,
            modules_affleurants=affleurants, avertissements=avertissements)
        return {li.designation: li.quantite for li in lignes}

    def test_48_sur_48_ni_structure_ni_socle_et_le_kit(self):
        lignes = self._lignes(48)
        self.assertNotIn('Structures acier', lignes)
        self.assertNotIn('Socles', lignes)
        self.assertEqual(lignes['Kit de fixation toit en pente'], 48)

    def test_40_affleurants_et_8_au_sol(self):
        lignes = self._lignes(40)
        self.assertEqual((lignes['Structures acier'], lignes['Socles']), (8, 16))
        self.assertEqual(lignes['Kit de fixation toit en pente'], 40)

    def test_sans_kit_au_catalogue_l_avertissement_et_aucune_structure(self):
        avertissements = []
        lignes = self._lignes(48, kit=False, avertissements=avertissements)
        self.assertNotIn('Structures acier', lignes)
        self.assertIn('Pose affleurante : aucun kit de fixation tarifé au catalogue — ligne non ajoutée.',
                      avertissements)

    def test_sans_affleurant_identique_au_bit_pres(self):
        lignes = self._lignes(0)
        self.assertEqual((lignes['Structures acier'], lignes['Socles']), (48, 96))
        self.assertNotIn('Kit de fixation toit en pente', lignes)

    def test_le_pipeline_ne_lit_les_affleurants_qu_au_niveau_15(self):
        from apps.ventes.models import Devis
        for niveau, attendu in ((15, ('2', '4')), (14, ('50', '100'))):
            devis = self._devis(cible=50)
            Devis.objects.filter(pk=devis.pk).update(roof_layout=self.LAYOUT, regles_calcul=niveau)
            devis.refresh_from_db()
            specs = _specs(48)
            _appliquer_preseance_quantite(devis, specs)
            par_designation = {s['designation']: s['quantite'] for s in specs}
            self.assertEqual((par_designation['Structure acier'], par_designation['Socle béton']), attendu)


class ACAL1238LeKitSuitLesAffleurants(SimpleTestCase):
    """ACAL1238 — tout affleurant, 8 → 10 panneaux au niveau 15 : la ligne « kit de fixation »
    suit les modules affleurants (10), jamais 0 ni l'ancien 8 ; niveau 14 inchangé ; idempotent."""

    LAYOUT = {'zones': [{'id': 'A', 'geometry': {'count': 10, 'flush': True}}]}
    KIT = 'Kit de fixation toit en pente'

    def _appliquer(self, specs, niveau, cible=10):
        from types import SimpleNamespace
        from unittest import mock

        with mock.patch('apps.ventes.domain.overrides.cible_dimensionnement_du_devis', return_value=cible), \
                mock.patch('apps.ventes.domain.overrides.preseance_nb_panneaux',
                           return_value=SimpleNamespace(quantite_ligne=cible)):
            _appliquer_preseance_quantite(
                SimpleNamespace(regles_calcul=niveau, roof_layout=self.LAYOUT), specs)
        return {s['designation']: s['quantite'] for s in specs}

    def _specs(self, nb=8):
        return [{'designation': 'Panneau Canadian Solar 710W', 'quantite': str(nb)},
                {'designation': self.KIT, 'quantite': str(nb)}]

    def test_tout_affleurant_8_vers_10_le_kit_a_10(self):
        self.assertEqual(self._appliquer(self._specs(), 15)[self.KIT], '10')

    def test_reecrire_deux_fois_donne_les_memes_quantites(self):
        specs = self._specs()
        premiere = dict(self._appliquer(specs, 15))
        specs[0]['quantite'] = '8'
        self.assertEqual(self._appliquer(specs, 15), premiere)

    def test_niveau_14_le_kit_inchange(self):
        self.assertEqual(self._appliquer(self._specs(), 14)[self.KIT], '8')


class T4X4001PanneauxRetouchesALEcran(_Base):
    """T4-X4-001 — le vendeur passe 5 → 7 panneaux à l'écran : structure et
    socles de la MÊME option suivent par LA règle de la composition ; une
    sœur saisie à la main est gardée et dite."""

    def _devis_et_specs(self):
        """Un devis à 5 panneaux en base et les specs d'écran de ses lignes."""
        self._seq += 1
        devis = make_devis(
            self.company, self.user, self.client_obj,
            [('Panneau Canadian Solar 710W', '5', '1166.67'),
             ('Structure acier', '5', '416.67'), ('Socle béton', '10', '120')],
            reference='DEV-T4X4001-%04d' % self._seq)
        specs = [{'produit': li.produit_id, 'designation': li.designation,
                  'quantite': str(li.quantite), 'prix_unitaire': str(li.prix_unitaire),
                  'ordre': k} for k, li in enumerate(devis.lignes.order_by('id'))]
        return devis, {s['designation']: s for s in specs}, specs

    def _quantites(self, devis):
        return {li.designation: li.quantite for li in devis.lignes.all()}

    def test_structure_et_socles_suivent_les_panneaux_retouches(self):
        from apps.ventes.domain.pipeline import ecrire_lignes
        devis, par, specs = self._devis_et_specs()
        par['Panneau Canadian Solar 710W'].update(quantite='7', quantite_manuelle=True)
        ecrire_lignes(devis, specs, company=self.company)
        q = self._quantites(devis)
        self.assertEqual(q['Panneau Canadian Solar 710W'], Decimal('7'))
        self.assertEqual(q['Structure acier'], Decimal('7'))
        self.assertEqual(q['Socle béton'], Decimal('14'))

    def test_un_devis_commercial_garde_les_quantites_de_son_moteur(self):
        """CI rouge du 25/11 (``BrouillonsSuiventLaConceptionTests``, cas C&I : structure
        « 1 lot » réécrite à 162) — la règle des sœurs est celle de la composition
        résidentielle : sur un devis commercial, industriel ou agricole rien n'est réécrit."""
        from apps.ventes.domain.pipeline import ecrire_lignes
        from apps.ventes.models import Devis

        for mode in ('commercial', 'industriel', 'agricole'):
            with self.subTest(mode=mode):
                devis, par, specs = self._devis_et_specs()
                Devis.objects.filter(pk=devis.pk).update(mode_installation=mode)
                devis.refresh_from_db()
                par['Panneau Canadian Solar 710W'].update(quantite='7', quantite_manuelle=True)
                ecrire_lignes(devis, specs, company=self.company)
                q = self._quantites(devis)
                self.assertEqual((q['Structure acier'], q['Socle béton']), (Decimal('5'), Decimal('10')))

    def test_une_soeur_tapee_a_la_main_est_gardee_et_dite(self):
        from apps.ventes.domain.pipeline import ecrire_lignes
        devis, par, specs = self._devis_et_specs()
        par['Panneau Canadian Solar 710W'].update(quantite='7', quantite_manuelle=True)
        par['Socle béton'].update(quantite='12', quantite_manuelle=True)
        avertissements = []
        ecrire_lignes(devis, specs, company=self.company, avertissements=avertissements)
        q = self._quantites(devis)
        self.assertEqual(q['Structure acier'], Decimal('7'))
        self.assertEqual(q['Socle béton'], Decimal('12'))
        self.assertIn('« Socle béton » : quantité saisie à la main (12) gardée pour 7 panneaux.',
                      avertissements)

    def test_reenregistrer_a_l_identique_ne_reecrit_rien(self):
        from apps.ventes.domain.pipeline import ecrire_lignes
        devis, par, specs = self._devis_et_specs()
        par['Structure acier']['quantite'] = '6'
        ecrire_lignes(devis, specs, company=self.company)
        self.assertEqual(self._quantites(devis)['Structure acier'], Decimal('6'))


class T4X6008DeuxOptionsLaLigneAvecNEstPasReecrite(SimpleTestCase):
    """T4-X6-008 — épicerie à deux options (22 panneaux « sans », 23 « avec »)
    portant ``taille.nb_panneaux = 22`` : l'enregistrement ramenait en silence
    la ligne « avec » (la plus grande, donc « dominante ») à 22. Le compte de
    niveau devis décrit l'option SANS batterie (T4-X4-019) : seule elle peut
    être réécrite, avec ses sœurs ; l'option « avec » garde les siennes."""

    def _specs(self):
        return [
            {'designation': 'Panneau Canadian Solar 715W', 'quantite': '22', 'variante': 'sans'},
            {'designation': 'Structure acier', 'quantite': '22', 'variante': 'sans'},
            {'designation': 'Panneau Canadian Solar 715W', 'quantite': '23', 'variante': 'avec'},
            {'designation': 'Structure acier', 'quantite': '23', 'variante': 'avec'},
        ]

    def _appliquer(self, specs, cible, avertissements=None):
        from types import SimpleNamespace
        from unittest import mock

        def preseance(_devis, dominante, **_k):
            return SimpleNamespace(quantite_ligne=cible)
        with mock.patch('apps.ventes.domain.overrides.cible_dimensionnement_du_devis',
                        return_value=cible), \
                mock.patch('apps.ventes.domain.overrides.preseance_nb_panneaux', side_effect=preseance):
            _appliquer_preseance_quantite(SimpleNamespace(regles_calcul=14, roof_layout=None), specs,
                                          avertissements=avertissements)
        return [(s['variante'], s['designation'], s['quantite']) for s in specs]

    def test_classe_toute_quantite_reecrite_est_dite(self):
        # T4-X6-008 (classe) — une taille de devis différente de l'option sans
        # batterie réécrit ses lignes : chaque réécriture est DITE (servie par
        # replace-lines dans ``alertes``) ; rien à dire quand rien ne bouge.
        avertissements = []
        self._appliquer(self._specs(), 20, avertissements)
        self.assertEqual(avertissements, [
            '« Panneau Canadian Solar 715W » : 22 → 20 (taille déclarée au niveau du devis : 20 panneaux).',
            '« Structure acier » : 22 → 20 (suit 20 panneaux).'])
        rien = []
        self._appliquer(self._specs(), 22, rien)
        self.assertEqual(rien, [])

    def test_compte_egal_a_l_option_sans_rien_ne_bouge(self):
        specs = self._specs()
        avant = [dict(s) for s in specs]
        self._appliquer(specs, 22)
        self.assertEqual(specs, avant)

    def test_compte_different_ne_reecrit_que_l_option_sans(self):
        lu = self._appliquer(self._specs(), 20)
        self.assertEqual(lu, [('sans', 'Panneau Canadian Solar 715W', '20'),
                              ('sans', 'Structure acier', '20'),
                              ('avec', 'Panneau Canadian Solar 715W', '23'),
                              ('avec', 'Structure acier', '23')])
