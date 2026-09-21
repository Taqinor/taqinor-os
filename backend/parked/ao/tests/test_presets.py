"""AOF27 — ``PresetCalepinage`` : jeux de paramètres nommés et réappliquables.

Le jeu de référence s'appelle **« FRDISI 2026-07 »**. Le test le plus important
de ce module est un GREP : le mot interdit (celui qui présenterait ces valeurs
comme réglementaires) ne doit apparaître NULLE PART dans ``apps/ao``. Aucun
texte réglementaire marocain — dégagement pompier, distance acrotère, exutoire
— n'existe dans ce dépôt : les présenter ainsi produirait un jour un plan non
conforme, opposable à l'entreprise.

Run :
    python manage.py test apps.ao.tests.test_presets -v2
"""
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.models import (
    PRESET_CONSERVATEUR_NOM, PRESET_REFERENCE_NOM, PRESET_REFERENCE_PARAMETRES,
    AppelOffre, BatimentAO, PresetCalepinage, ToitureAO,
)
from authentication.models import Company

AO_DIR = Path(__file__).resolve().parent.parent
#: Le mot INTERDIT, construit sans jamais l'écrire en clair — sinon ce
#: fichier de test se ferait détecter par son propre grep.
MOT_INTERDIT = re.compile(r'\bnorm' + 'es?\\b', re.IGNORECASE)

#: Modules qui parlent des RÉFÉRENCES EXTERNES RÉELLES (NF C 15-100, IEC
#: 61215, loi 13-09, décret 2-12-349…) et non des paramètres maison. La
#: liste est FERMÉE et nominative : tout autre fichier d'``apps/ao`` reste
#: refusé, si bien qu'un module qui recommencerait à présenter les
#: dégagements TAQINOR comme réglementaires échoue toujours ici.
#:
#: L'exemption est nécessaire, pas de confort : ``literaux.py`` doit
#: reconnaître le mot LITTÉRAL dans le texte d'un CPS pour disculper le
#: numéro qui le suit — le renommer casserait le détecteur.
FICHIERS_A_REFERENCES_EXTERNES = {
    'contexte.py',        # tolérances de littéraux : références externes
    'gabarits.py',        # EXCEPTIONS_NORMATIVES (liste fermée, motivée)
    'literaux.py',        # motifs disculpants du détecteur de chiffres
    'test_aof_gabarits.py',
    'test_aof_literaux.py',
}


class TestNommageHonnete(SimpleTestCase):
    def test_le_jeu_de_reference_porte_son_vrai_nom(self):
        self.assertEqual(PRESET_REFERENCE_NOM, 'FRDISI 2026-07')

    def test_le_mot_interdit_n_apparait_nulle_part_dans_apps_ao(self):
        fautifs = []
        for chemin in sorted(AO_DIR.rglob('*.py')):
            if chemin.name == Path(__file__).name:
                continue  # ce fichier CITE le motif, par construction
            if chemin.name in FICHIERS_A_REFERENCES_EXTERNES:
                continue  # références EXTERNES réelles — voir ci-dessus
            texte = chemin.read_text(encoding='utf-8')
            if MOT_INTERDIT.search(texte):
                fautifs.append(chemin.name)
        self.assertEqual(
            fautifs, [],
            'Aucun texte réglementaire marocain sur les dégagements '
            "n'existe dans ce dépôt : ces valeurs sont des paramètres MAISON, "
            f'et le vocabulaire doit le dire. Fichiers fautifs : {fautifs}')

    def test_aucune_exemption_perimee(self):
        """Une exemption qui ne sert plus doit DISPARAÎTRE, pas dormir.

        Sans ce contrôle, la liste ci-dessus grossirait en silence et
        finirait par exempter des fichiers qui n'ont plus rien à voir avec
        une référence externe — c'est-à-dire par désarmer le grep.
        """
        presents = {c.name for c in AO_DIR.rglob('*.py')
                    if MOT_INTERDIT.search(c.read_text(encoding='utf-8'))}
        inutiles = sorted(FICHIERS_A_REFERENCES_EXTERNES - presents)
        self.assertEqual(
            inutiles, [],
            f'Exemptions devenues inutiles, à retirer : {inutiles}')

    def test_le_mot_interdit_ne_touche_jamais_les_parametres_maison(self):
        """Le cœur de la règle : les dégagements MAISON ne sont pas des textes.

        Même dans les fichiers exemptés, le mot ne doit jamais se retrouver
        sur la même ligne qu'un paramètre de calepinage — c'est exactement
        l'amalgame que AOF27 interdit.
        """
        maison = re.compile(
            r'degagement|dégagement|rive_|allee_|allée|preset|acrotere|'
            r'acrotère|exutoire', re.IGNORECASE)
        fautifs = []
        for chemin in sorted(AO_DIR.rglob('*.py')):
            if chemin.name == Path(__file__).name:
                continue
            for numero, ligne in enumerate(
                    chemin.read_text(encoding='utf-8').splitlines(), 1):
                if MOT_INTERDIT.search(ligne) and maison.search(ligne):
                    fautifs.append(f'{chemin.name}:{numero}')
        self.assertEqual(
            fautifs, [],
            'Le mot interdit est employé au contact d’un paramètre MAISON : '
            f'{fautifs}')

    def test_les_valeurs_de_reference(self):
        self.assertEqual(PRESET_REFERENCE_PARAMETRES['rive_laterale_m'], 0.35)
        self.assertEqual(PRESET_REFERENCE_PARAMETRES['rive_extremite_m'], 0.35)
        self.assertEqual(PRESET_REFERENCE_PARAMETRES['allee_min_m'], 0.60)
        degagements = PRESET_REFERENCE_PARAMETRES[
            'degagements_par_provenance_m']
        self.assertEqual(degagements['MESURE'], 0.30)
        self.assertEqual(degagements['DEVINE'], 0.50)

    def test_la_variante_conservatrice_existe_a_titre_d_information(self):
        self.assertEqual(PRESET_CONSERVATEUR_NOM, 'Variante conservatrice')


class TestApplicationDuPreset(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF27 Co', slug='aof27-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-27-1', objet='Presets')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05H')
        services.seeder_presets(self.company)
        self.preset = PresetCalepinage.objects.get(
            company=self.company, nom=PRESET_REFERENCE_NOM)

    def test_seed_additif_et_rejouable(self):
        avant = PresetCalepinage.objects.filter(company=self.company).count()
        self.assertEqual(services.seeder_presets(self.company), 0)
        self.assertEqual(
            PresetCalepinage.objects.filter(company=self.company).count(),
            avant)

    def test_le_preset_de_reference_est_par_defaut(self):
        self.assertTrue(self.preset.par_defaut)
        self.assertEqual(
            services.preset_par_defaut(
                self.company, PresetCalepinage.Portee.AO),
            self.preset)

    def test_application_en_un_appel(self):
        services.appliquer_preset(self.preset, self.toiture)
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.preset_applique_id, self.preset.id)
        self.assertEqual(self.toiture.parametres_calepinage['allee_min_m'],
                         0.60)

    def test_l_application_est_tracee(self):
        from apps.records.services import chatter_qs

        services.appliquer_preset(self.preset, self.toiture)
        entrees = [
            e for e in chatter_qs(self.ao, company=self.company)
            if e.field == 'preset_applique'
        ]
        self.assertEqual(len(entrees), 1)
        self.assertEqual(entrees[0].new_value, PRESET_REFERENCE_NOM)

    def test_l_instantane_survit_a_une_edition_du_preset(self):
        """Éditer un preset ne réécrit JAMAIS un calepinage déjà appliqué."""
        services.appliquer_preset(self.preset, self.toiture)
        self.preset.parametres['allee_min_m'] = 1.20
        self.preset.save(update_fields=['parametres'])
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.parametres_calepinage['allee_min_m'],
                         0.60)

    def test_reapplication_ecrase_l_instantane(self):
        services.appliquer_preset(self.preset, self.toiture)
        conservateur = PresetCalepinage.objects.get(
            company=self.company, nom=PRESET_CONSERVATEUR_NOM)
        services.appliquer_preset(conservateur, self.toiture)
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.preset_applique_id, conservateur.id)
        self.assertEqual(self.toiture.parametres_calepinage['allee_min_m'],
                         0.50)

    def test_seed_scope_societe(self):
        autre = Company.objects.create(nom='AOF27 X', slug='aof27-x')
        self.assertEqual(
            PresetCalepinage.objects.filter(company=autre).count(), 0)
