"""CAL197 — presets société de calepinage : réutilisés, jamais réinventés.

Ce qui est prouvé ici :

* un jeu MAISON s'enregistre, se remplace (par ``id``) et se retire ;
* un preset SANS ``id``/``nom`` est refusé en nommant le champ ;
* les presets d'une société n'apparaissent JAMAIS dans une autre (multi-
  société) ;
* ``selectors.presets_de_societe`` joint les jeux MAISON et les presets AO de
  portée société SANS en copier un dans l'autre.

Run :
    python manage.py test apps.calepinage.tests.test_cal197_presets -v2
"""
from django.test import TestCase

from apps.ao.models import PresetCalepinage
from apps.calepinage import selectors
from apps.calepinage.services.presets import (
    PresetInvalide, enregistrer_jeu, jeux_de_societe, retirer_jeu,
)
from authentication.models import Company


class JeuxMaisonTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Presets Co',
                                              slug='presets-co-197')
        self.autre = Company.objects.create(nom='Autre Co',
                                            slug='autre-co-197')

    def test_societe_sans_reglage_recoit_liste_vide(self):
        self.assertEqual(jeux_de_societe(self.company), [])

    def test_enregistrer_puis_lire(self):
        enregistrer_jeu(self.company, {
            'id': 'standard', 'nom': 'Standard',
            'marge_toiture_m': 0.3, 'espacement_rangee_m': 0.02,
        })
        jeux = jeux_de_societe(self.company)
        self.assertEqual(len(jeux), 1)
        self.assertEqual(jeux[0]['nom'], 'Standard')
        self.assertEqual(jeux[0]['marge_toiture_m'], 0.3)

    def test_remplacer_par_id(self):
        enregistrer_jeu(self.company, {'id': 'std', 'nom': 'Standard',
                                       'marge_toiture_m': 0.3})
        enregistrer_jeu(self.company, {'id': 'std', 'nom': 'Standard v2',
                                       'marge_toiture_m': 0.5})
        jeux = jeux_de_societe(self.company)
        self.assertEqual(len(jeux), 1)
        self.assertEqual(jeux[0]['nom'], 'Standard v2')
        self.assertEqual(jeux[0]['marge_toiture_m'], 0.5)

    def test_id_manquant_refuse_en_nommant_le_champ(self):
        with self.assertRaises(PresetInvalide) as ctx:
            enregistrer_jeu(self.company, {'nom': 'Sans id'})
        self.assertEqual(ctx.exception.champ, 'id')

    def test_nom_manquant_refuse_en_nommant_le_champ(self):
        with self.assertRaises(PresetInvalide) as ctx:
            enregistrer_jeu(self.company, {'id': 'x'})
        self.assertEqual(ctx.exception.champ, 'nom')

    def test_retirer_jeu_introuvable_refuse(self):
        with self.assertRaises(PresetInvalide):
            retirer_jeu(self.company, 'fantome')

    def test_retirer_jeu_existant(self):
        enregistrer_jeu(self.company, {'id': 'std', 'nom': 'Standard'})
        retirer_jeu(self.company, 'std')
        self.assertEqual(jeux_de_societe(self.company), [])

    def test_isolation_multi_societe(self):
        enregistrer_jeu(self.company, {'id': 'std', 'nom': 'Standard'})
        self.assertEqual(jeux_de_societe(self.autre), [])


class PresetsDeSocieteSelectorTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Presets Sel Co',
                                              slug='presets-sel-co-197')

    def test_joint_module_et_societe_ao_sans_copie(self):
        enregistrer_jeu(self.company, {'id': 'std', 'nom': 'Standard'})
        preset_ao = PresetCalepinage.objects.create(
            company=self.company, nom='FRDISI 2026-07',
            portee=PresetCalepinage.Portee.SOCIETE,
            parametres={'retrait_rive_m': 0.4})

        resultat = selectors.presets_de_societe(self.company)

        self.assertEqual(len(resultat['module']), 1)
        self.assertEqual(resultat['module'][0]['id'], 'std')
        self.assertEqual(len(resultat['societe_ao']), 1)
        self.assertEqual(resultat['societe_ao'][0]['id'], preset_ao.pk)
        self.assertEqual(resultat['societe_ao'][0]['nom'], 'FRDISI 2026-07')
        # Un preset de portée AO (pas SOCIETE) n'apparaît pas ici.
        PresetCalepinage.objects.create(
            company=self.company, nom='Affaire seule',
            portee=PresetCalepinage.Portee.AO, parametres={})
        resultat_2 = selectors.presets_de_societe(self.company)
        self.assertEqual(len(resultat_2['societe_ao']), 1)

    def test_societe_none_rend_listes_vides(self):
        resultat = selectors.presets_de_societe(None)
        self.assertEqual(resultat['module'], [])
        self.assertEqual(resultat['societe_ao'], [])
