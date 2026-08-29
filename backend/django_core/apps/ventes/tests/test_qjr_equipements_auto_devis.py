# -*- coding: utf-8 -*-
"""QJR9 (29/08/2026) — le devis automatique / tunnel dimensionne sur les MÊMES
quinze champs d'équipement que l'aperçu écran.

LE DÉFAUT CORRIGÉ. ``services._panneaux_dimensionnement_horaire`` composait sa
couche équipement à la main sur SIX clés (piscine, piscine_pompe_kw,
voiture_electrique, ve_km_semaine, clim, clim_pieces) alors que
``crm.selectors.equipements_pour_devis`` en lit QUINZE : les huit grandeurs
L-BACK/L-BACK2 (``chauffe_eau_kw``/``creneau``, ``ve_chargeur_kw``/``creneau``,
``clim_kw``, ``clim_creneau``, ``piscine_heures_jour``, ``piscine_creneau``)
plus ``chauffe_eau_electrique`` n'atteignaient JAMAIS le moteur sur le chemin
auto-devis/tunnel. Deux clients différents étaient donc dimensionnés selon
qu'on passait par l'écran d'aperçu ou par le devis automatique.

CE QUE CE MODULE ÉPINGLE. Le moteur (``dimensionnement.recommander_taille``)
est remplacé par un ESPION : on compare, pour le MÊME lead, le dict
``equipements`` que chacun des deux chemins lui remet, et le nombre de panneaux
rendu de part et d'autre. Aucun catalogue ni appel PVGIS n'est nécessaire — le
sujet est la couche d'entrée, pas le contenu du catalogue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr_equipements_auto_devis"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from authentication.models import Company

User = get_user_model()

#: Réponse canonique de l'espion : le moteur n'est pas le sujet, sa RÉPONSE
#: est donc figée pour que toute différence observée vienne des ENTRÉES.
RECOMMANDATION_ESPION = {
    'recommandation': {'panneaux': 12, 'panel_watt': 550, 'kwc': 6.6},
    'recommandation_avec': None,
}


class _EspionMoteur:
    """Remplaçant de ``recommander_taille`` qui MÉMORISE ses kwargs."""

    def __init__(self):
        self.appels = []

    def __call__(self, **kwargs):
        self.appels.append(kwargs)
        return dict(RECOMMANDATION_ESPION)

    @property
    def equipements_du_dernier_appel(self):
        return self.appels[-1].get('equipements')


class _QJR9Base(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr9-co', defaults={'nom': 'QJR9 Co'})
        self.user = User.objects.create_user(
            username='qjr9_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _lead_l_back(self, **surcharges):
        """Lead portant les grandeurs L-BACK que l'ancien chemin PERDAIT :
        chauffe-eau (kW + créneau) et chargeur VE (kW + créneau)."""
        champs = dict(
            company=self.company, nom='Lead', prenom='QJR9',
            telephone='+212600000091', ville='Casablanca',
            facture_hiver=Decimal('1800'), ete_differente=False,
            occupation_jour='present',
            equip_voiture_electrique=True, equip_ve_km_semaine=150,
            equip_ve_chargeur_kw=7.4, equip_ve_creneau='nuit',
            equip_chauffe_eau_electrique=True, equip_chauffe_eau_kw=2.4,
            equip_chauffe_eau_creneau='soir',
        )
        champs.update(surcharges)
        return Lead.objects.create(**champs)

    def _lead_six_anciens_champs(self, **surcharges):
        """Lead ne portant QUE les six champs de l'ancienne composition —
        preuve de non-régression."""
        champs = dict(
            company=self.company, nom='Lead', prenom='QJR9 Ancien',
            telephone='+212600000092', ville='Casablanca',
            facture_hiver=Decimal('1800'), ete_differente=False,
            occupation_jour='present',
            equip_piscine=True, equip_piscine_pompe_kw=1.1,
            equip_voiture_electrique=True, equip_ve_km_semaine=150,
            equip_clim=True, equip_clim_pieces=3,
        )
        champs.update(surcharges)
        return Lead.objects.create(**champs)

    def _panneaux_chemin_auto(self, lead, espion):
        """(nb_panneaux, equipements remis au moteur) du chemin AUTO-DEVIS."""
        from apps.ventes.services import _panneaux_dimensionnement_horaire

        with mock.patch('apps.ventes.dimensionnement.recommander_taille',
                        espion):
            nb, _watt, source, _avec = _panneaux_dimensionnement_horaire(
                lead=lead, company=self.company, phase=None)
        self.assertEqual(source, 'moteur_horaire')
        return nb, espion.equipements_du_dernier_appel

    def _panneaux_chemin_apercu(self, lead, espion):
        """(nb_panneaux, equipements remis au moteur) du chemin APERÇU."""
        with mock.patch('apps.ventes.dimensionnement.recommander_taille',
                        espion):
            resp = self.api.post(
                '/api/django/ventes/etude-horaire/preview/',
                {'mode_installation': 'residentiel', 'lead': lead.id,
                 'dimensionner': True},
                format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        dimensionnement = resp.data.get('dimensionnement')
        self.assertIsNotNone(dimensionnement, resp.data.get('avertissements'))
        return (dimensionnement['recommandation']['panneaux'],
                espion.equipements_du_dernier_appel)


class MemeDimensionnementQueLApercuTests(_QJR9Base):
    def test_grandeurs_l_back_atteignent_le_moteur_sur_le_chemin_auto(self):
        """LE BUG : la couche ``chauffe_eau`` (kW + créneau réels) n'existait
        pas du tout sur le chemin auto-devis, et la fenêtre de recharge VE
        n'était jamais resserrée par le chargeur réel."""
        lead = self._lead_l_back()
        _nb, equipements = self._panneaux_chemin_auto(lead, _EspionMoteur())

        self.assertIn('chauffe_eau', equipements)
        self.assertEqual(equipements['chauffe_eau']['kw'], 2.4)
        self.assertEqual(
            equipements['chauffe_eau']['source'],
            'lead:equip_chauffe_eau_kw+creneau')
        self.assertIn('ve', equipements)
        self.assertIn('equip_ve_chargeur_kw', equipements['ve']['source'])

    def test_auto_et_apercu_remettent_le_meme_dict_au_moteur(self):
        lead = self._lead_l_back()
        _nb_auto, equip_auto = self._panneaux_chemin_auto(
            lead, _EspionMoteur())
        _nb_apercu, equip_apercu = self._panneaux_chemin_apercu(
            lead, _EspionMoteur())
        self.assertEqual(equip_auto, equip_apercu)

    def test_auto_et_apercu_rendent_le_meme_nombre_de_panneaux(self):
        lead = self._lead_l_back()
        nb_auto, _ = self._panneaux_chemin_auto(lead, _EspionMoteur())
        nb_apercu, _ = self._panneaux_chemin_apercu(lead, _EspionMoteur())
        self.assertEqual(nb_auto, nb_apercu)
        self.assertEqual(nb_auto, RECOMMANDATION_ESPION['recommandation']['panneaux'])


class NonRegressionSixAnciensChampsTests(_QJR9Base):
    """Un lead ne portant que les six champs d'avant compose EXACTEMENT les
    mêmes couches qu'avant — piscine sur son bloc du mémo, clim estimée par
    pièce, VE sur sa fenêtre heures-creuses par défaut."""

    def test_couches_identiques_a_la_composition_historique(self):
        lead = self._lead_six_anciens_champs()
        _nb, equipements = self._panneaux_chemin_auto(lead, _EspionMoteur())

        self.assertEqual(set(equipements), {'piscine', 'clim', 've'})
        self.assertEqual(
            equipements['piscine']['source'],
            'memo_2026-08-21_etage2:piscine_bloc_10_18h')
        self.assertEqual(
            equipements['clim']['source'],
            'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h')
        self.assertEqual(
            equipements['ve']['source'],
            'memo_2026-08-21_etage2:ve_ademe_19_8kwh_100km')
        self.assertNotIn('chauffe_eau', equipements)

    def test_auto_et_apercu_restent_alignes_sans_les_grandeurs_l_back(self):
        lead = self._lead_six_anciens_champs()
        _nb_auto, equip_auto = self._panneaux_chemin_auto(
            lead, _EspionMoteur())
        _nb_apercu, equip_apercu = self._panneaux_chemin_apercu(
            lead, _EspionMoteur())
        self.assertEqual(equip_auto, equip_apercu)


class SelecteurCrmPartageTests(_QJR9Base):
    """``equipements_pour_devis`` reste la MÊME sortie, désormais dérivée de
    ``equipements_pour_lead`` : un seul endroit lit les quinze champs."""

    def test_pour_devis_egale_pour_lead_du_meme_lead(self):
        from apps.crm.selectors import (
            equipements_pour_devis, equipements_pour_lead,
        )

        lead = self._lead_l_back()

        class _DevisDuck:
            pass

        duck = _DevisDuck()
        duck.lead = lead
        self.assertEqual(
            equipements_pour_devis(duck), equipements_pour_lead(lead))

    def test_pour_lead_sans_lead_rend_un_dict_vide(self):
        from apps.crm.selectors import equipements_pour_lead

        self.assertEqual(equipements_pour_lead(None), {})

    def test_les_quinze_champs_sont_lus(self):
        from apps.crm.selectors import equipements_pour_lead

        lead = self._lead_l_back()
        self.assertEqual(set(equipements_pour_lead(lead)), {
            'piscine', 'piscine_pompe_kw', 'voiture_electrique',
            've_km_semaine', 'clim', 'clim_pieces', 'chauffe_eau_electrique',
            'chauffe_eau_kw', 'chauffe_eau_creneau', 've_chargeur_kw',
            've_creneau', 'clim_kw', 'piscine_heures_jour', 'clim_creneau',
            'piscine_creneau',
        })
