# -*- coding: utf-8 -*-
"""QJR606 — ``recommander_taille`` reçoit partout les mêmes entrées du devis.

Constat : quatre jeux d'entrées — le tableau stocké (``etudes``) sans phase
ni gamme, le devis automatique (``taille``) avec la phase, et
``profils_comparatifs`` qui relisait la fiche à la main. ``EntreesMoteur``
porte désormais ``phase`` et ``gamme_nom_devis``, lues une fois par
``entrees_depuis_devis`` / ``entrees_depuis_lead``.

Run :
    python manage.py test apps.ventes.tests.test_entrees_moteur_gamme_phase -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.ventes import dimensionnement
from apps.ventes.models import Devis, ParametresGammes

CLES_DEVIS = ('company', 'conso_kwh_mensuelles', 'ville', 'lat', 'lon',
              'equipements', 'source_conso', 'jour_reference', 'tranches',
              'charges_fixes_mad', 'phase', 'gamme_nom_devis')


class EntreesIdentiques(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(slug='qjr606', nom='qjr606')
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={
                'deux_gammes': True,
                'nom_essentielle': ParametresGammes.SLOT_ESSENTIELLE,
                'nom_premium': ParametresGammes.SLOT_PREMIUM,
                'marques': {ParametresGammes.SLOT_PREMIUM: {
                    'onduleur_reseau': 'Deye'}},
            })
        client = Client.objects.create(company=self.company, nom='QJR606')
        self.lead = Lead.objects.create(
            company=self.company, nom='QJR606', ville='Casablanca',
            raccordement='monophase', facture_hiver=Decimal('900'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR606', statut='brouillon',
            client=client, lead=self.lead, taux_tva=Decimal('20'),
            mode_installation='residentiel',
            etude_params={'gamme': {'nom': ParametresGammes.SLOT_PREMIUM}})
        self.appels = []
        vrai = dimensionnement.recommander_taille

        def _espion(**kwargs):
            self.appels.append(kwargs)
            return {'tableau': [], 'recommandation': None, 'motivation': ''}

        dimensionnement.recommander_taille = _espion
        self.addCleanup(setattr, dimensionnement, 'recommander_taille', vrai)

    def test_trois_appelants_memes_entrees(self):
        from apps.ventes.domain.etudes import rafraichir_dimensionnement_devis
        from apps.ventes.domain.taille import (
            _panneaux_dimensionnement_horaire,
            phase_client_pour_dimensionnement)
        from apps.ventes.profils_comparatifs import _dimensionnement_variante

        rafraichir_dimensionnement_devis(self.devis, force=True)
        _dimensionnement_variante(self.devis, 'presence')
        _panneaux_dimensionnement_horaire(
            lead=self.lead, company=self.company,
            phase=phase_client_pour_dimensionnement(self.lead))
        self.assertEqual(len(self.appels), 3, self.appels)
        etude, profil, lead = self.appels

        for cle in CLES_DEVIS:
            self.assertIn(cle, etude, cle)
            self.assertEqual(etude[cle], profil.get(cle), cle)
        self.assertEqual(etude['phase'], 'monophase')
        self.assertEqual(etude['gamme_nom_devis'],
                         ParametresGammes.SLOT_PREMIUM)
        self.assertEqual(lead['phase'], 'monophase')
        self.assertIn('gamme_nom_devis', lead)
