"""ACAL117 (D-ACAL-15, C-ACAL-011/090) — UNE règle de copie (Dupliquer,
modèle) : pertes copiées, aucun résultat ni saisie de site, variantes NON
retenues et sans résultat, implantation translatée sur le repère du lead
cible, version d'origine déposée.

Services réels ; rien n'est mocké.

Run :
    python manage.py test apps.calepinage.tests.test_acal_regle_de_copie -v2
"""
import copy

from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion,
)
from apps.calepinage.services.modeles import (
    ModeleInvalide, creer_depuis_modele, marquer_modele,
)
from apps.calepinage.services.variantes import (
    creer_variante, dupliquer, retenir_variante,
)
from apps.crm.models import Lead

from .test_api_liste import BaseApiCalepinage

CASA = {'lat': 33.5731, 'lng': -7.5898}
MARRAKECH = {'lat': 31.6295, 'lng': -7.9811}

POSTES = [{'poste': 'iam', 'libelle': 'IAM', 'pct': 3.0, 'source': None,
           'reference': '', 'mensuel': None},
          {'poste': 'cablage', 'libelle': 'Câblage', 'pct': 1.5,
           'source': None, 'reference': '', 'mensuel': None},
          {'poste': 'mismatch', 'libelle': 'Mismatch', 'pct': 2.0,
           'source': None, 'reference': '', 'mensuel': None}]


def _document():
    return {
        'version': 2,
        'pin': dict(CASA),
        'outline': [[CASA['lat'], CASA['lng']],
                    [CASA['lat'] + 0.0001, CASA['lng']],
                    [CASA['lat'] + 0.0001, CASA['lng'] + 0.0001]],
        'zones': [{'id': 'z1', 'label': 'Pan Sud',
                   'vertices': [[CASA['lng'], CASA['lat']],
                                [CASA['lng'] + 0.0001, CASA['lat']],
                                [CASA['lng'] + 0.0001,
                                 CASA['lat'] + 0.0001]],
                   'geometry': {'count': 12, 'azimuthDeg': 180,
                                'tiltDeg': 15}}],
        'consumption': {'annualKwh': 9000},
    }


class RegleDeCopieTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.source = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL-MODELE',
            roof_layout=_document(), layout_hash='c' * 64,
            pertes=copy.deepcopy(POSTES),
            resultat={'simulation': {'hash_entree': 'site-origine'},
                      'raccordement_saisie': {'type': 'mono'}},
            roof_image='roofs/1/calepinage-rendu.png')
        self.variante = creer_variante(self.source, nom='V',
                                       roof_layout=_document(),
                                       resultat={'production': {'p50': 1}})
        retenir_variante(self.variante, appliquer=False)

    def test_dupliquer_copie_pertes_sans_resultat(self):
        copie = dupliquer(self.source, user=self.user, lead_id=self.lead_2.pk)
        copie = Calepinage.objects.get(pk=copie.pk)
        self.assertEqual(copie.roof_layout, self.source.roof_layout)
        self.assertEqual(copie.pertes, POSTES)
        self.assertIsNone(copie.resultat)
        self.assertEqual(copie.roof_image, '')

    def test_dupliquer_ne_copie_pas_la_retenue(self):
        copie = dupliquer(self.source, user=self.user, lead_id=self.lead_2.pk)
        variantes = CalepinageVariante.objects.filter(calepinage=copie)
        self.assertEqual(variantes.count(), 1)
        for variante in variantes:
            self.assertFalse(variante.retenue)
            self.assertIsNone(variante.resultat)

    def test_copie_porte_sa_version_d_origine(self):
        copie = dupliquer(self.source, user=self.user, lead_id=self.lead_2.pk)
        versions = CalepinageVersion.objects.filter(calepinage=copie)
        self.assertEqual(versions.count(), 1)
        version = versions.get()
        self.assertEqual(version.libelle,
                         f"Conception d'origine (copie de #{self.source.pk})")
        self.assertIsNone(version.resultat)
        self.assertEqual(version.roof_layout, copie.roof_layout)

    def test_modele_translate_sur_le_lead_cible(self):
        marquer_modele(self.source, user=self.user)
        cible = Lead.objects.create(company=self.company, nom='Marrakech',
                                    roof_point=dict(MARRAKECH))
        copie = creer_depuis_modele(self.source, user=self.user,
                                    lead_id=cible.pk)
        copie = Calepinage.objects.get(pk=copie.pk)
        document = copie.roof_layout
        self.assertAlmostEqual(document['pin']['lat'], MARRAKECH['lat'], 6)
        self.assertAlmostEqual(document['pin']['lng'], MARRAKECH['lng'], 6)
        premier = document['zones'][0]['vertices'][0]
        self.assertAlmostEqual(premier[0], MARRAKECH['lng'], 4)
        self.assertAlmostEqual(premier[1], MARRAKECH['lat'], 4)
        self.assertAlmostEqual(document['outline'][0][0], MARRAKECH['lat'], 4)
        self.assertNotIn('consumption', document)
        self.assertIsNone(copie.resultat)
        self.assertEqual(copie.roof_image, '')
        self.assertEqual(copie.pertes, POSTES)

    def test_modele_variantes_translatees_sans_consommation(self):
        """Lot 2 critique #6 — chaque VARIANTE du modèle suit la règle de la
        conception (D-ACAL-15) : translatée sur le lead cible, sans la
        consommation d'un autre client, empreinte recalculée."""
        marquer_modele(self.source, user=self.user)
        cible = Lead.objects.create(company=self.company, nom='Marrakech',
                                    roof_point=dict(MARRAKECH))
        copie = creer_depuis_modele(self.source, user=self.user,
                                    lead_id=cible.pk)
        variantes = list(CalepinageVariante.objects.filter(calepinage=copie))
        self.assertEqual(len(variantes), 1)
        document = variantes[0].roof_layout
        self.assertAlmostEqual(document['pin']['lat'], MARRAKECH['lat'], 6)
        premier = document['zones'][0]['vertices'][0]
        self.assertAlmostEqual(premier[0], MARRAKECH['lng'], 4)
        self.assertAlmostEqual(premier[1], MARRAKECH['lat'], 4)
        self.assertNotIn('consumption', document)
        # La variante SOURCE n'est pas touchée.
        self.variante.refresh_from_db()
        self.assertEqual(self.variante.roof_layout, _document())

    def test_modele_sans_repere_refuse(self):
        marquer_modele(self.source, user=self.user)
        sans = Lead.objects.create(company=self.company, nom='Sans repère')
        avant = Calepinage.objects.count()
        with self.assertRaises(ModeleInvalide) as refus:
            creer_depuis_modele(self.source, user=self.user, lead_id=sans.pk)
        self.assertEqual(refus.exception.champ, 'lead')
        self.assertIn("n'a pas de repère toit", str(refus.exception))
        self.assertEqual(Calepinage.objects.count(), avant)
