"""ACAL36 (C-ACAL-115/114) — le contexte de conception du calepinage sert
``revision_possible`` et le devis lié (référence, statut, client) selon le
contrat ``calepinage_design_context.json``.

``revision_possible`` est LU sur ventes (``devis_modifiabilite`` →
``domain.modifiabilite.verdict``, réel) ; ``calepinage.devis_lie`` reprend le
bloc ``devis`` du contexte ventes. Aucun mock : APIClient réel, base réelle.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_design_context.json').read_text(encoding='utf-8'))

LAYOUT = {'schema_version': 2, 'result': {'panels': 12, 'kwc': 8.64}}


def url_contexte(pk):
    return f'{url_detail(pk)}design-context/'


class ContexteDevisLieTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.client_lie = Client.objects.create(company=self.company,
                                                nom='Client ACAL36')
        self.lead_lie = Lead.objects.create(company=self.company,
                                            nom='Lead ACAL36')

    def _calepinage_lie(self, statut):
        devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference=f'DEV-ACAL36-{statut}', statut=statut)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=devis,
            titre=f'QA-ACAL36-{statut}', roof_layout=LAYOUT)
        return calepinage, devis

    def _contexte(self, calepinage):
        reponse = self.api.get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_accepte_revision_possible_et_devis_lie(self):
        attendu = CONTRAT['exemple_accepte']
        calepinage, devis = self._calepinage_lie(Devis.Statut.ACCEPTE)
        contexte = self._contexte(calepinage)
        self.assertIs(contexte['revision_possible'], True)
        self.assertEqual(attendu['revision_possible'], True)
        devis_lie = contexte['calepinage']['devis_lie']
        self.assertEqual(sorted(devis_lie),
                         sorted(attendu['calepinage']['devis_lie']))
        self.assertEqual(devis_lie['id'], devis.pk)
        self.assertEqual(devis_lie['reference'], devis.reference)
        self.assertEqual(devis_lie['statut'], 'accepte')
        self.assertTrue(devis_lie['client_nom'])

    def test_brouillon_revision_impossible(self):
        calepinage, _devis = self._calepinage_lie(Devis.Statut.BROUILLON)
        contexte = self._contexte(calepinage)
        self.assertIs(contexte['revision_possible'],
                      CONTRAT['exemple']['revision_possible'])
        self.assertEqual(contexte['calepinage']['devis_lie']['statut'],
                         'brouillon')

    def test_sans_devis_cles_presentes_a_null(self):
        attendu = CONTRAT['exemple_sans_devis']
        nu = Calepinage.objects.create(company=self.company,
                                       client=self.client_lie,
                                       titre='QA-ACAL36-nu')
        contexte = self._contexte(nu)
        self.assertIn('revision_possible', contexte)
        self.assertIs(contexte['revision_possible'],
                      attendu['revision_possible'])
        self.assertIn('devis_lie', contexte['calepinage'])
        self.assertIsNone(contexte['calepinage']['devis_lie'])
        # Les sept clés historiques restent toutes présentes.
        for cle in ('calepinage', 'geometrie', 'cible', 'carte', 'modifiable',
                    'raison_lecture_seule', 'avertissements'):
            self.assertIn(cle, contexte)


def _contrat_retenue():
    return json.loads((Path(__file__).resolve().parent.parent / 'contract_samples'
                       / 'calepinage_conception_retenue.json').read_text(encoding='utf-8'))


class _DevisDeuxOptions(BaseApiCalepinage):
    """ACAL1950 — un devis « Les deux » à deux comptes de panneaux : onduleur
    réseau dans l'option sans, hybride + batterie dans l'option avec (même
    fabrique que ``apps/ventes/tests/test_ctx3d_cible_avec.py``)."""

    PRODUITS = (('PAN', 'Panneau Jinko 715W'),
                ('ONDR', 'Onduleur réseau Huawei 20kW Triphasé'),
                ('ONDH', 'Onduleur hybride Deye 20kW Triphasé'),
                ('BAT', 'Batterie Dyness 10 kWh'))

    def setUp(self):
        from decimal import Decimal

        from apps.stock.models import Produit

        super().setUp()
        self.client_lie = Client.objects.create(company=self.company, nom='Client ACAL1950')
        self.lead_lie = Lead.objects.create(company=self.company, nom='Lead ACAL1950')
        self.produits = {cle: Produit.objects.create(
            company=self.company, nom=nom, sku=f'ACAL1950-{cle}',
            prix_vente=Decimal('1100'), quantite_stock=50)
            for cle, nom in self.PRODUITS}
        self.compteur = 0

    def _devis(self, lignes, statut='envoye', mode='residentiel', **extra):
        from decimal import Decimal

        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, client=self.client_lie, lead=self.lead_lie,
            reference=f'DEV-ACAL1950-{self.compteur * 10}', statut=statut,
            mode_installation=mode, **extra)
        for cle, quantite, variante in lignes:
            produit = self.produits[cle]
            devis.lignes.create(produit=produit, designation=produit.nom,
                                quantite=Decimal(str(quantite)),
                                prix_unitaire=Decimal('1100'), variante=variante)
        return devis

    def _les_deux(self, recommandee=None, etude=None, **extra):
        params = {'scenario': 'Les deux (Sans + Avec)', **(etude or {})}
        if recommandee:
            params['recommended_option'] = recommandee
        return self._devis(
            [('PAN', 35, 'sans'), ('PAN', 48, 'avec'), ('ONDR', 1, 'sans'),
             ('ONDH', 1, 'avec'), ('BAT', 1, 'avec')],
            etude_params=params, **extra)


class ConceptionRetenueTest(_DevisDeuxOptions):
    """ACAL1950 — le devis dit sa conception retenue (sélecteur ventes réel)."""

    @staticmethod
    def _lire(devis):
        from apps.ventes.selectors_calepinage import conception_retenue_du_devis

        return conception_retenue_du_devis(devis)

    def test_recommandee_sans_rend_l_option_sans_et_ses_quantites(self):
        devis = self._les_deux('Sans batterie', etude={
            'etude_horaire': {'annuel': {'production_kwh': 60000}},
            'etude_horaire_sans': {'annuel': {'production_kwh': 41250}}})
        lu = self._lire(devis)
        self.assertEqual(sorted(lu), sorted(_contrat_retenue()['exemple']))
        self.assertEqual((lu['option'], lu['deux_options'], lu['recu']), ('sans', True, True))
        self.assertEqual(lu['module']['quantite'], 35)
        self.assertEqual(lu['module']['produit'], self.produits['PAN'].pk)
        self.assertEqual(lu['module']['watt'], 715.0)
        self.assertEqual([(o['produit'], o['quantite']) for o in lu['onduleurs']],
                         [(self.produits['ONDR'].pk, 1)])
        # La conception électrique rangée décrit l'option « avec » : jamais servie pour « sans ».
        self.assertIsNone(lu['chaines'])
        self.assertEqual((lu['production_annuelle_kwh'], lu['production_origine']),
                         (41250.0, 'etude_horaire_sans'))

    def test_recommandee_avec_rend_l_option_avec(self):
        devis = self._les_deux('Avec batterie', electrical_design={'chaines': [
            {'nb_modules': 12}, {'nb_modules': 12}, {'nb_modules': 12}, {'nb_modules': 12}]})
        lu = self._lire(devis)
        self.assertEqual((lu['option'], lu['module']['quantite']), ('avec', 48))
        self.assertEqual([o['produit'] for o in lu['onduleurs']], [self.produits['ONDH'].pk])
        self.assertEqual(lu['chaines'], {'nombre': 4, 'longueurs': [12, 12, 12, 12], 'longueur': 12})

    def test_option_unique_et_cle_absente_rend_null(self):
        devis = self._devis([('PAN', 10, ''), ('ONDR', 1, '')], statut='brouillon')
        lu = self._lire(devis)
        self.assertEqual((lu['option'], lu['deux_options'], lu['recu']), ('sans', False, False))
        self.assertEqual(lu['module']['quantite'], 10)
        self.assertIsNone(lu['chaines'])
        self.assertIsNone(lu['production_annuelle_kwh'])
        self.assertIsNone(lu['production_origine'])
        self.assertIsNone(self._lire(None))
        self.assertIsNone(_contrat_retenue()['exemple_vide'])

    def test_c_i_lit_le_bilan_du_moteur(self):
        devis = self._devis([('PAN', 35, ''), ('ONDR', 1, '')], mode='commercial',
                            etude_params={'etude_ci': {'bilan': {'production_kwh': 95425}}})
        lu = self._lire(devis)
        self.assertEqual((lu['production_annuelle_kwh'], lu['production_origine']),
                         (95425.0, 'etude_ci'))


class CibleOptionRetenueTest(_DevisDeuxOptions):
    """ACAL1951 généralisé par ACAL2012 — la cible de l'atelier suit l'option que la
    CONCEPTION retient (plus le devis lié), et l'enregistrement du dessin range l'option
    que le devis lié visait."""

    def _calepinage(self, devis):
        return Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=devis,
            titre='QA-ACAL1951')

    def _cible(self, calepinage):
        reponse = self.api.get(url_contexte(calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data['cible']

    # ACAL2012 (D-ACAL-97) — réalignés : l'option et la taille sont celles de la CONCEPTION
    # courante du lead, plus celles que le devis lié recommande.
    def test_devis_recommande_avec_la_cible_suit_la_conception(self):
        from .test_acal_cible_lead import ranger_conception

        ranger_conception(lead=self.lead_lie, nb=35, avec=48, option='sans')
        cible = self._cible(self._calepinage(self._les_deux('Avec batterie')))
        self.assertEqual((cible['panneaux'], cible['option'], cible['source']), (35, 'sans', 'factures'))
        self.assertFalse(cible['batterie'])

    def test_devis_recommande_sans_la_cible_suit_la_conception(self):
        from .test_acal_cible_lead import ranger_conception

        ranger_conception(lead=self.lead_lie, nb=35, avec=48, option='avec')
        cible = self._cible(self._calepinage(self._les_deux('Sans batterie')))
        self.assertEqual((cible['panneaux'], cible['option']), (48, 'avec'))
        self.assertTrue(cible['batterie'])
        self.assertIn('option', CONTRAT['exemple']['cible'])

    def test_sans_devis_aucune_option(self):
        cible = self._cible(Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, titre='QA-ACAL1951-lead'))
        self.assertIsNotNone(cible)
        self.assertNotEqual(cible['source'], 'devis')
        self.assertIsNone(cible['option'])

    def test_l_enregistrement_range_l_option_visee(self):
        """ACAL2025 — l'option rangée est celle de la CONCEPTION (« avec »), plus celle que
        les lignes du devis recommandent (« sans »)."""
        from apps.calepinage.services.devis_retenu import CLE_OPTION_DESSINEE

        from .test_acal_cible_lead import ranger_conception

        ranger_conception(lead=self.lead_lie, nb=35, avec=48, option='avec')
        calepinage = self._calepinage(self._les_deux('Sans batterie', statut='brouillon'))
        url = f'{url_detail(calepinage.pk)}layout/'
        reponse = self.api.post(url, {'schema_version': 2, 'zones': []}, format='json',
                                HTTP_IF_MATCH='""')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        calepinage.refresh_from_db()
        self.assertEqual(calepinage.resultat[CLE_OPTION_DESSINEE],
                         {'devis': calepinage.devis_id, 'option': 'avec'})


class LignesDuDevisPlusSourceTest(_DevisDeuxOptions):
    """ACAL2025 (C4-E8) — la cible et le matériel du calepinage viennent de la conception : la
    conception retenue du DEVIS (ses lignes) n'est plus lue pour l'une ni pour l'autre, et les
    deux lecteurs morts (``_produits_du_devis``, ``produits_retenus``) n'existent plus."""

    def test_cible_et_materiel_sans_lire_les_lignes_du_devis(self):
        from unittest import mock

        from apps.calepinage.services import devis_retenu, electrique
        from apps.calepinage.services.devis import _cible_du_calepinage
        from apps.calepinage.services.modules_stock import modules_disponibles_du_calepinage

        from .test_acal_cible_lead import ranger_conception

        ranger_conception(lead=self.lead_lie, nb=35, option='sans')
        calepinage = Calepinage.objects.create(company=self.company, lead_id=self.lead_lie.pk,
                                               devis=self._les_deux('Avec batterie'), titre='QA-ACAL2025')
        with mock.patch('apps.ventes.selectors_calepinage.conception_retenue_du_devis',
                        side_effect=AssertionError('lignes du devis lues')) as lu, \
                mock.patch('apps.ventes.selectors_calepinage.conception_retenue_du_devis_id',
                           side_effect=AssertionError('lignes du devis lues')) as lu_id:
            self.assertEqual(_cible_du_calepinage(calepinage)['panneaux'], 35)
            electrique.resoudre_materiel(self.company, {}, calepinage=calepinage)
            modules_disponibles_du_calepinage(calepinage, [])  # ACAL2025 — l'ordre des modules
        self.assertEqual((lu.call_count, lu_id.call_count), (0, 0))
        self.assertFalse(hasattr(devis_retenu, 'module_retenu_du_devis'))
        self.assertFalse(hasattr(electrique, '_produits_du_devis'))  # mutant « rétabli » : rouge
        self.assertFalse(hasattr(devis_retenu, 'produits_retenus'))
        self.assertFalse(hasattr(devis_retenu, 'cible_de_l_option_retenue'))


class ResultatsDeLaConceptionTest(_DevisDeuxOptions):
    """ACAL2015 (C4-E5, D-ACAL-96) — ``conception`` de ``GET resultat/`` : UN chiffre de
    production (celui de la conception courante) ; un devis lié REÇU par le client
    (envoyé) est nommé avec l'écart que ventes sert (``ecart_devis``), jamais modifié ;
    un brouillon ou l'absence de devis ne nomment rien d'autre."""

    def setUp(self):
        super().setUp()
        from .test_acal_cible_lead import ranger_conception

        self.version = ranger_conception(lead=self.lead_lie, nb=48, watt=715, option='sans')
        self.attendu = self.version.valeurs['sans']['production_annuelle']['valeur']

    def _bloc(self, devis=None):
        from apps.calepinage.services.devis_retenu import bloc_conception

        return bloc_conception(Calepinage.objects.create(
            company=self.company, lead_id=self.lead_lie.pk, devis=devis, titre='QA-ACAL2015'))

    def test_t4_x5_004_le_devis_envoye_du_lead_non_lie_est_nomme(self):
        """T4-X5-004 — le devis automatique du lead a été ENVOYÉ sans lien au calepinage : le
        calepinage du lead le nomme quand même, avec l'écart que ventes sert (« Réviser le
        devis » possible) ; la production comparée est celle du devis ; le devis n'est pas touché."""
        from django.utils import timezone

        from apps.calepinage.services.devis_retenu import bloc_conception, bloc_production_devis

        devis = self._les_deux('Sans batterie', etude={'etude_horaire_sans': {
            'annuel': {'production_kwh': 6047.0}}}, date_envoi=timezone.now())
        avant = Devis.objects.filter(pk=devis.pk).values().get()
        calepinage = Calepinage.objects.create(company=self.company, lead_id=self.lead_lie.pk,
                                               titre='QA-T4-X5-004')  # aucun devis lié
        envoye = bloc_conception(calepinage)['devis_envoye']
        self.assertEqual((envoye['devis'], envoye['reference']), (devis.pk, devis.reference))
        ecarts = {e['valeur']: e for e in envoye['ecart_devis']}
        self.assertEqual((ecarts['nb_panneaux']['devis'], ecarts['nb_panneaux']['conception']), (35, 48))
        self.assertTrue(ecarts['nb_panneaux']['reviser_possible'])
        self.assertEqual(bloc_production_devis(calepinage)['devis'], devis.pk)
        self.assertEqual(Devis.objects.filter(pk=devis.pk).values().get(), avant)

    def test_d_acal_109_les_phrases_du_materiel_designe_servies_telles_quelles(self):
        """D-ACAL-109 / D-ACAL-110 — ``designations`` : les phrases servies par ventes dont le
        champ est le matériel désigné (onduleur, module), dans leur ordre ; ``[]`` sinon."""
        self.assertEqual(self._bloc()['designations'], [])
        phrases = [{'code': 'option_materiel_du_moteur', 'champ': 'onduleur_produit', 'message': 'A'},
                   {'code': 'froid_suppose', 'champ': 'gps_lat', 'message': 'B'},
                   {'code': 'panneaux_au_module_designe', 'champ': 'module_produit', 'message': 'C'}]
        type(self.version).objects.filter(pk=self.version.pk).update(suppositions=phrases)
        self.assertEqual(self._bloc()['designations'], ['A', 'C'])

    def test_sans_devis_un_seul_chiffre(self):
        bloc = self._bloc()
        self.assertEqual((bloc['production_annuelle_kwh'], bloc['option'], bloc['devis_envoye']),
                         (self.attendu, 'sans', None))
        self.assertEqual(bloc['version'], self.version.version)

    def test_t4_x7_013_la_production_porte_sa_taille(self):
        """T4-X7-013 — la production servie va avec la taille de la MÊME option (48 × 715 W) :
        jamais une production lue ici et une taille lue sur une autre lecture."""
        bloc = self._bloc()
        table = self.version.valeurs['sans']
        self.assertEqual((bloc['puissance_kwc'], bloc['nb_panneaux']),
                         (table['puissance_kwc']['valeur'], 48))
        self.assertEqual(bloc['puissance_kwc'], round(48 * 715 / 1000, 2))

    def test_brouillon_un_seul_chiffre(self):
        bloc = self._bloc(self._les_deux('Sans batterie', statut='brouillon'))
        self.assertEqual((bloc['production_annuelle_kwh'], bloc['devis_envoye']), (self.attendu, None))

    def test_t4_x7_006_le_devis_lie_dit_s_il_porte_la_pose(self):
        """T4-X7-006 — après « Réviser le devis », la V2 (brouillon) liée ne porte pas la pose : le
        bloc la nomme (``devis_lie``) avec ``a_jour`` faux (empreintes différentes), vrai quand elles
        sont égales, ``None`` sans empreinte ; ``None`` sans devis lié. Rien n'est écrit."""
        self.assertIsNone(self._bloc()['devis_lie'])
        devis = self._les_deux('Sans batterie', statut='brouillon')
        Devis.objects.filter(pk=devis.pk).update(layout_hash='a' * 64)
        devis.refresh_from_db()
        avant = Devis.objects.filter(pk=devis.pk).values().get()
        from apps.calepinage.services.devis_retenu import bloc_conception

        # UN calepinage par devis (contrainte ``calepinage_un_par_devis``) : le même, dont l'empreinte change.
        calepinage = Calepinage.objects.create(company=self.company, lead_id=self.lead_lie.pk, devis=devis,
                                               titre='QA-T4-X7-006')
        lie = bloc_conception(calepinage)['devis_lie']
        self.assertEqual((lie['devis'], lie['reference'], lie['statut']), (devis.pk, devis.reference, 'brouillon'))
        self.assertIsNone(lie['a_jour'])  # le calepinage neuf n'a pas d'empreinte : inconnu, jamais « périmé »
        Calepinage.objects.filter(pk=calepinage.pk).update(layout_hash='b' * 64)
        calepinage.refresh_from_db()
        self.assertIs(bloc_conception(calepinage)['devis_lie']['a_jour'], False)
        Calepinage.objects.filter(pk=calepinage.pk).update(layout_hash='a' * 64)
        calepinage.refresh_from_db()
        self.assertIs(bloc_conception(calepinage)['devis_lie']['a_jour'], True)
        self.assertEqual(Devis.objects.filter(pk=devis.pk).values().get(), avant)

    def test_envoye_nomme_le_devis_et_l_ecart_sans_le_toucher(self):
        from django.utils import timezone

        devis = self._les_deux('Sans batterie', etude={'etude_horaire_sans': {
            'annuel': {'production_kwh': 6047.0}}}, date_envoi=timezone.now())
        avant = Devis.objects.filter(pk=devis.pk).values().get()
        bloc = self._bloc(devis)
        envoye = bloc['devis_envoye']
        self.assertEqual((envoye['devis'], envoye['reference'], envoye['statut']),
                         (devis.pk, devis.reference, 'envoye'))
        self.assertEqual(envoye['envoye_le'], devis.date_envoi.isoformat())
        ecarts = {e['valeur']: e for e in envoye['ecart_devis']}
        self.assertEqual((ecarts['nb_panneaux']['devis'], ecarts['nb_panneaux']['conception']), (35, 48))
        self.assertTrue(ecarts['nb_panneaux']['reviser_possible'])
        self.assertEqual(ecarts['production_annuelle']['devis'], 6047)
        self.assertEqual(bloc['production_annuelle_kwh'], self.attendu)
        self.assertEqual(Devis.objects.filter(pk=devis.pk).values().get(), avant)

    def test_m2_le_devis_envoye_sert_sa_propre_production_et_son_option(self):
        """Relecture E5 M2 — ``devis_envoye`` porte la production et l'option que le
        DEVIS a rangées (jamais celles de la conception) : devis « avec » (60 000 kWh),
        conception « sans » ; un devis sans production rangée sert ``None``. Rien
        n'est écrit sur le devis. Mutant « option de la conception » : 'sans'."""
        from django.utils import timezone

        devis = self._les_deux('Avec batterie', etude={'etude_horaire': {'annuel': {'production_kwh': 60000}}},
                               date_envoi=timezone.now())
        avant = Devis.objects.filter(pk=devis.pk).values().get()
        envoye = self._bloc(devis)['devis_envoye']
        contrat = json.loads((Path(__file__).resolve().parent.parent / 'contract_samples'
                              / 'calepinage_resultat.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(envoye), sorted(contrat['acal2015_conception']['devis_envoye']))
        self.assertEqual((envoye['option'], envoye['production_annuelle_kwh']), ('avec', 60000.0))
        self.assertEqual(Devis.objects.filter(pk=devis.pk).values().get(), avant)
        sans_production = self._bloc(self._les_deux('Sans batterie', date_envoi=timezone.now()))['devis_envoye']
        self.assertEqual((sans_production['option'], sans_production['production_annuelle_kwh']), ('sans', None))

    def test_servi_par_get_resultat_et_contrat(self):
        calepinage = Calepinage.objects.create(company=self.company, lead_id=self.lead_lie.pk,
                                               titre='QA-ACAL2015-get')
        reponse = self.api.get(f'{url_detail(calepinage.pk)}resultat/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        contrat = json.loads((Path(__file__).resolve().parent.parent / 'contract_samples'
                              / 'calepinage_resultat.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(reponse.data['conception']), sorted(contrat['acal2015_conception']))
        self.assertIn('conception', contrat['exemple'])
