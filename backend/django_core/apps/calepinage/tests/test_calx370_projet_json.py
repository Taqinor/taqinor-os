"""CALX370 — exporter puis RÉIMPORTER un projet de calepinage complet.

Ce qui est prouvé ici :

* le contrat partagé ``contract_samples/calepinage_projet_json.json`` est
  AFFIRMÉ : l'aperçu que le service rend pour l'exemple committé de
  ``export_projet.json`` est, à l'octet près, ``exemple_apercu`` ; les refus
  committés sont ceux que le service lève ;
* l'export passe au format 2 : ``postes_pertes`` (les postes SAISIS) et
  ``variantes`` rejoignent le fichier, en fin ;
* la réimportation VALIDE TOUT avant d'écrire, et chaque refus NOMME le
  chemin du champ fautif — version inconnue (``format_version``), document
  de pose invalide (``roof_layout.zones.0.vertices``), variante, poste, clé
  de coût (D5 : aucune clé de prix ni de coût dans l'enveloppe) ;
* identifiants de société et d'utilisateur REPOSÉS par le serveur ;
* en base (CI) : un export puis un import dans une société VIDE restitue le
  même nombre de modules, les mêmes postes de pertes et les mêmes variantes ;
  la porte ``POST calepinages/import-projet/`` crée (201), prévisualise sans
  écrire (200), refuse en 400 nommé, et exige la permission de gestion.

Run :
    python manage.py test apps.calepinage.tests.test_calx370_projet_json -v2
"""
import copy
import json
import pathlib
import unittest
from types import SimpleNamespace
from unittest import mock

from apps.calepinage.services import export_projet as ep
from apps.calepinage.services.export_projet import (
    BLOCS_IGNORES, BLOCS_REPRIS, CLES_DOCUMENT, CLES_VARIANTE,
    FORMAT_VERSION, FORMATS_IMPORTABLES, MOTIF_FORMAT_1, ImportProjetRefuse,
    _analyser_projet, importer_projet,
)

from .test_api_liste import URL, BaseApiCalepinage

ECHANTILLONS = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CONTRAT = charger('calepinage_projet_json.json')
EXPORT = charger('export_projet.json')
RESULTAT = charger('calepinage_resultat.json')


def fichier(**remplacements):
    """Le fichier d'export committé (format 2), modifiable sans effet de bord."""
    document = copy.deepcopy(EXPORT['exemple'])
    document.update(remplacements)
    return document


def refus(document):
    with unittest.TestCase().assertRaises(ImportProjetRefuse) as capture:
        _analyser_projet(document)
    return capture.exception


# ═══════════════════════════════════════════════════════════════════════════
# 1. LE CONTRAT PARTAGÉ — affirmé, pas recopié
# ═══════════════════════════════════════════════════════════════════════════

class ContratPartageTest(unittest.TestCase):
    def test_la_route_est_celle_du_contrat(self):
        self.assertEqual(
            CONTRAT['endpoint'],
            'POST /api/django/calepinage/calepinages/import-projet/')
        source = (pathlib.Path(__file__).resolve().parents[1] / 'views'
                  / 'projet_json.py').read_text(encoding='utf-8')
        self.assertIn("url_path='import-projet'", source)

    def test_l_apercu_de_l_exemple_committe_est_l_exemple_apercu(self):
        apercu = importer_projet(fichier(), None, lead_id=12, apercu=True)
        self.assertEqual(apercu, CONTRAT['exemple_apercu'])

    def test_l_exemple_ecrit_a_la_meme_forme_que_l_apercu(self):
        exemple, apercu = CONTRAT['exemple'], CONTRAT['exemple_apercu']
        self.assertEqual(list(exemple), list(apercu))
        self.assertTrue(exemple['ecrit'])
        self.assertIsInstance(exemple['calepinage'], int)
        self.assertFalse(apercu['ecrit'])
        self.assertIsNone(apercu['calepinage'])
        self.assertEqual(exemple['repris'], list(BLOCS_REPRIS))
        self.assertEqual([i['bloc'] for i in exemple['ignores']],
                         [bloc for bloc, _ in BLOCS_IGNORES])

    def test_les_refus_committes_sont_ceux_du_service(self):
        erreur = refus(fichier(format_version=7))
        self.assertEqual({erreur.champ: str(erreur)},
                         CONTRAT['exemple_refus_version'])
        casse = fichier()
        casse['roof_layout']['zones'][0]['vertices'] = 'x'
        erreur = refus(casse)
        # La fin du message est celle de ``jsonschema`` (sa formulation peut
        # bouger d'une version à l'autre) : la clé et le préfixe NOMMÉ, eux,
        # sont le contrat.
        self.assertEqual([erreur.champ], list(CONTRAT['exemple_refus_champ']))
        prefixe = ('Fichier de projet refusé au champ '
                   '« roof_layout.zones.0.vertices » : ')
        self.assertTrue(str(erreur).startswith(prefixe))
        self.assertTrue(CONTRAT['exemple_refus_champ'][erreur.champ]
                        .startswith(prefixe))

    def test_aucune_cle_de_montant_dans_le_contrat(self):
        for cle in ('exemple', 'exemple_apercu', 'requete'):
            self.assertEqual(
                ep._chemins(CONTRAT[cle], '',
                            lambda c, _v: ep.cle_de_montant(c)), [], cle)


# ═══════════════════════════════════════════════════════════════════════════
# 2. L'EXPORT AU FORMAT 2 — les deux blocs de la réimportation
# ═══════════════════════════════════════════════════════════════════════════

POSTES = copy.deepcopy(EXPORT['exemple']['postes_pertes'])


def pivot(**champs):
    """Un calepinage NON ENREGISTRÉ, sans société : aucune lecture en base."""
    valeurs = dict(pk=1, company=None, client_id=None, lead_id=None,
                   devis_id=None, titre='Toiture atelier',
                   roof_layout=copy.deepcopy(EXPORT['exemple']['roof_layout']),
                   layout_hash='ab' * 32, version_moteur='calepinage-1.0.0',
                   resultat=None, pertes=copy.deepcopy(POSTES))
    valeurs.update(champs)
    return SimpleNamespace(**valeurs)


def exporte(objet=None):
    return ep.document_de_projet(
        objet or pivot(), resultat=copy.deepcopy(RESULTAT['exemple_vide']),
        site={'adresse': None, 'ville': None, 'pin': None, 'outline': None,
              'source': None},
        equipements={})


class ExportFormat2Test(unittest.TestCase):
    def test_le_format_2_ajoute_les_deux_blocs_en_fin(self):
        self.assertEqual(FORMAT_VERSION, 2)
        self.assertIn(FORMAT_VERSION, FORMATS_IMPORTABLES)
        self.assertEqual(CLES_DOCUMENT[-2:], ('postes_pertes', 'variantes'))
        document = exporte()
        self.assertEqual(tuple(document), CLES_DOCUMENT)
        self.assertEqual(document['format_version'], 2)

    def test_les_postes_saisis_sont_exportes_tels_quels(self):
        document = exporte()
        self.assertEqual(document['postes_pertes'], POSTES)
        # `pertes` reste la liste SERVIE : vide tant que rien n'est simulé.
        self.assertEqual(document['pertes'], [])

    def test_sans_societe_aucune_variante_n_est_lue(self):
        self.assertEqual(exporte()['variantes'], [])

    def test_les_variantes_lues_ont_la_forme_du_contrat(self):
        variantes = [
            SimpleNamespace(nom=' Variante A ', retenue=True,
                            roof_layout={'version': 2}, layout_hash='c' * 64,
                            resultat={'kwc': 8.64}),
            SimpleNamespace(nom='Variante B', retenue=False,
                            roof_layout=None, layout_hash='', resultat=None),
        ]
        with mock.patch('apps.calepinage.selectors.variantes',
                        return_value=variantes):
            lignes = ep._bloc_variantes(pivot(company=object()))
        self.assertEqual([tuple(ligne) for ligne in lignes],
                         [CLES_VARIANTE, CLES_VARIANTE])
        self.assertEqual(lignes[0]['nom'], 'Variante A')
        self.assertTrue(lignes[0]['retenue'])
        self.assertIsNone(lignes[1]['layout_hash'])
        for ligne in EXPORT['exemple']['variantes']:
            self.assertEqual(tuple(ligne), CLES_VARIANTE)

    def test_l_export_se_relit_par_la_reimportation(self):
        plan = _analyser_projet(json.loads(ep.octets_de_projet(exporte())))
        self.assertEqual(len(plan['postes']), len(POSTES))
        self.assertEqual(plan['roof_layout'],
                         EXPORT['exemple']['roof_layout'])


# ═══════════════════════════════════════════════════════════════════════════
# 3. LA VALIDATION — tout avant d'écrire, chaque refus NOMME son chemin
# ═══════════════════════════════════════════════════════════════════════════

class ValidationTest(unittest.TestCase):
    def test_une_version_inconnue_est_refusee_en_la_nommant(self):
        for version in (7, 0, '2', None, True, 2.5):
            with self.subTest(version=version):
                erreur = refus(fichier(format_version=version))
                self.assertEqual(erreur.champ, 'format_version')
                self.assertIn(json.dumps(version), str(erreur))

    def test_un_fichier_qui_n_est_pas_un_objet(self):
        for brut in (None, [], 'texte'):
            with self.subTest(brut=brut):
                self.assertEqual(refus(brut).champ, 'projet')

    def test_une_cle_de_cout_est_refusee_en_la_nommant(self):
        document = fichier()
        document['variantes'][0]['resultat']['prix_achat_total'] = 1
        erreur = refus(document)
        self.assertEqual(erreur.champ,
                         'variantes[0].resultat.prix_achat_total')
        document = fichier()
        document['equipements']['panneau']['specs']['cout_unitaire'] = 1
        self.assertIn('cout_unitaire', refus(document).champ)

    def test_le_document_de_pose_invalide_nomme_son_chemin(self):
        casse = fichier()
        casse['roof_layout']['zones'][0]['vertices'] = 'x'
        erreur = refus(casse)
        self.assertEqual(erreur.champ, 'roof_layout.zones.0.vertices')
        variante = fichier()
        variante['variantes'][0]['roof_layout']['zones'][0]['geometry'][
            'count'] = 'douze'
        erreur = refus(variante)
        self.assertEqual(erreur.champ,
                         'variantes[0].roof_layout.zones.0.geometry.count')
        self.assertEqual(refus(fichier(roof_layout=[1, 2])).champ,
                         'roof_layout')

    def test_les_variantes_sont_validees_une_par_une(self):
        sans_nom = fichier()
        sans_nom['variantes'][1]['nom'] = '  '
        self.assertEqual(refus(sans_nom).champ, 'variantes[1].nom')
        deux = fichier()
        deux['variantes'][1]['retenue'] = True
        self.assertEqual(refus(deux).champ, 'variantes[1].retenue')
        texte = fichier()
        texte['variantes'][0]['retenue'] = 'oui'
        self.assertEqual(refus(texte).champ, 'variantes[0].retenue')
        self.assertEqual(refus(fichier(variantes={'a': 1})).champ,
                         'variantes')
        self.assertEqual(refus(fichier(variantes=['x'])).champ,
                         'variantes[0]')

    def test_les_postes_sont_valides_par_le_service_des_pertes(self):
        double = fichier()
        double['postes_pertes'].append(copy.deepcopy(POSTES[0]))
        self.assertEqual(refus(double).champ,
                         'postes_pertes[%d]' % len(POSTES))
        source = fichier()
        source['postes_pertes'][1]['source'] = 'devinette'
        self.assertEqual(refus(source).champ, 'postes_pertes[1]')
        self.assertEqual(refus(fichier(postes_pertes='x')).champ,
                         'postes_pertes')
        sans_nom = fichier()
        sans_nom['postes_pertes'][0]['poste'] = ''
        self.assertEqual(refus(sans_nom).champ, 'postes_pertes[0].poste')

    def test_le_format_1_est_relu_sans_variante(self):
        ancien = fichier(format_version=1)
        ancien.pop('postes_pertes')
        ancien.pop('variantes')
        plan = _analyser_projet(ancien)
        self.assertEqual([p['poste'] for p in plan['postes']],
                         [p['poste'] for p in EXPORT['exemple']['pertes']])
        self.assertEqual(plan['variantes'], [])
        self.assertIn(MOTIF_FORMAT_1, plan['avertissements'])

    def test_aucun_identifiant_du_fichier_n_entre_dans_le_plan(self):
        plan = _analyser_projet(fichier())
        self.assertEqual(set(plan), {'format_version', 'titre',
                                     'roof_layout', 'postes', 'variantes',
                                     'avertissements'})
        self.assertNotIn('company', json.dumps(plan))
        self.assertNotIn('cree_par', json.dumps(plan))

    def test_le_rattachement_est_un_lead_ou_un_client(self):
        for cibles in ({}, {'lead_id': 1, 'client_id': 2}):
            with self.subTest(cibles=cibles):
                with self.assertRaises(ImportProjetRefuse) as capture:
                    importer_projet(fichier(), None, apercu=True, **cibles)
                self.assertEqual(capture.exception.champ, 'lead')

    def test_l_apercu_n_ecrit_rien(self):
        with mock.patch('apps.calepinage.services.creation.creer_pour_lead'
                        ) as creation, \
                mock.patch('apps.calepinage.services.layout.'
                           'enregistrer_layout') as layout:
            resume = importer_projet(fichier(), None, lead_id=3, apercu=True)
        creation.assert_not_called()
        layout.assert_not_called()
        self.assertFalse(resume['ecrit'])
        self.assertEqual(resume['modules'], 12)
        self.assertEqual(resume['variante_retenue'],
                         EXPORT['exemple']['variantes'][0]['nom'])


# ═══════════════════════════════════════════════════════════════════════════
# 4. EN BASE (CI) — l'aller-retour et la porte HTTP
# ═══════════════════════════════════════════════════════════════════════════

URL_IMPORT = '%simport-projet/' % URL


class AllerRetourEnBaseTest(BaseApiCalepinage):
    """Export → JSON strict → import dans une société VIDE."""

    def setUp(self):
        super().setUp()
        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.layout import enregistrer_layout
        from apps.calepinage.services.pertes import enregistrer_pertes
        from apps.calepinage.services.variantes import creer_variante

        self.source = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        enregistrer_layout(self.source,
                           copy.deepcopy(EXPORT['exemple']['roof_layout']))
        enregistrer_pertes(self.source, copy.deepcopy(POSTES))
        for ligne in EXPORT['exemple']['variantes']:
            creer_variante(self.source, nom=ligne['nom'],
                           roof_layout=copy.deepcopy(ligne['roof_layout']),
                           resultat=copy.deepcopy(ligne['resultat']),
                           retenir=ligne['retenue'])
        self.source.refresh_from_db()

    def _exporter(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=copy.deepcopy(RESULTAT['exemple_vide'])):
            document = ep.document_de_projet(self.source)
        return json.loads(ep.octets_de_projet(document))

    def _variantes(self, calepinage):
        from apps.calepinage.selectors import variantes

        return sorted((v.nom, v.retenue, json.dumps(v.roof_layout,
                                                    sort_keys=True))
                      for v in variantes(calepinage))

    def test_un_aller_retour_restitue_le_projet(self):
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from authentication.models import Company

        document = self._exporter()
        self.assertEqual(document['format_version'], FORMAT_VERSION)
        self.assertEqual(ep._chemins(document, '',
                                     lambda c, _v: ep.cle_de_montant(c)), [])

        vide = Company.objects.create(nom='Société vide', slug='vide-calx370')
        client = Client.objects.create(company=vide, nom='Client arrivée')
        resume = importer_projet(document, vide, client_id=client.pk)

        copie = Calepinage.objects.get(pk=resume['calepinage'])
        self.assertEqual(copie.company_id, vide.pk)
        self.assertEqual(copie.client_id, client.pk)
        self.assertEqual(Calepinage.objects.filter(company=vide).count(), 1)
        # Même nombre de modules, même document, même empreinte.
        self.assertEqual(ep._modules_du_document(copie.roof_layout),
                         ep._modules_du_document(self.source.roof_layout))
        self.assertEqual(resume['modules'],
                         ep._modules_du_document(self.source.roof_layout))
        self.assertEqual(copie.roof_layout, self.source.roof_layout)
        self.assertEqual(copie.layout_hash, self.source.layout_hash)
        # Mêmes postes de pertes.
        self.assertEqual(copie.pertes, self.source.pertes)
        # Mêmes variantes, même retenue.
        self.assertEqual(self._variantes(copie), self._variantes(self.source))
        self.assertTrue(resume['ecrit'])
        self.assertEqual(resume['variantes'], 2)
        # La source n'a pas bougé.
        self.assertEqual(Calepinage.objects.filter(
            company=self.company).count(), 1)

    def test_le_resultat_du_fichier_n_est_pas_reimporte(self):
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from authentication.models import Company

        document = self._exporter()
        document['resultat'] = copy.deepcopy(RESULTAT['exemple'])
        vide = Company.objects.create(nom='Société vide 2',
                                      slug='vide-calx370-2')
        client = Client.objects.create(company=vide, nom='Client arrivée')
        resume = importer_projet(document, vide, client_id=client.pk)
        copie = Calepinage.objects.get(pk=resume['calepinage'])
        self.assertIsNone(copie.resultat)
        self.assertIn('resultat', [i['bloc'] for i in resume['ignores']])

    def test_un_client_d_une_autre_societe_est_introuvable(self):
        from apps.crm.models import Client

        etranger = Client.objects.create(company=self.autre, nom='Voisin')
        with self.assertRaises(ImportProjetRefuse) as capture:
            importer_projet(self._exporter(), self.company,
                            client_id=etranger.pk)
        self.assertEqual(capture.exception.champ, 'client')


class EndpointImportProjetEnBaseTest(BaseApiCalepinage):
    """``POST …/import-projet/`` — câblage, société, permission (CI)."""

    def _post(self, corps, *, api=None):
        return (api or self.api).post(URL_IMPORT, corps, format='json')

    def test_import_cree_dans_la_societe_de_l_appelant(self):
        from apps.calepinage.models import Calepinage

        reponse = self._post({'projet': fichier(), 'lead': self.lead.pk,
                              'company': self.autre.pk})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(list(reponse.data), list(CONTRAT['exemple']))
        copie = Calepinage.objects.get(pk=reponse.data['calepinage'])
        self.assertEqual(copie.company_id, self.company.pk)
        self.assertEqual(copie.lead_id, self.lead.pk)
        self.assertEqual(copie.cree_par_id, self.user.pk)
        self.assertEqual(reponse.data['variantes'], 2)

    def test_l_apercu_rend_la_forme_sans_rien_ecrire(self):
        from apps.calepinage.models import Calepinage

        avant = Calepinage.objects.count()
        reponse = self._post({'projet': fichier(), 'lead': self.lead.pk,
                              'apercu': True})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(reponse.data['ecrit'])
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_une_version_inconnue_400_en_la_nommant(self):
        reponse = self._post({'projet': fichier(format_version=9),
                              'lead': self.lead.pk})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('format_version', reponse.data)
        self.assertIn('9', str(reponse.data['format_version']))

    def test_un_document_de_pose_invalide_400_chemin_nomme(self):
        casse = fichier()
        casse['roof_layout']['zones'][0]['vertices'] = 'x'
        reponse = self._post({'projet': casse, 'lead': self.lead.pk})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('roof_layout.zones.0.vertices', reponse.data)

    def test_une_cle_de_cout_400_en_la_nommant(self):
        document = fichier()
        document['variantes'][0]['resultat']['prix_achat'] = 1
        reponse = self._post({'projet': document, 'lead': self.lead.pk})
        self.assertEqual(reponse.status_code, 400)
        self.assertTrue(any('prix_achat' in cle for cle in reponse.data))

    def test_un_lead_d_une_autre_societe_est_refuse(self):
        from apps.crm.models import Lead

        etranger = Lead.objects.create(company=self.autre, nom='Voisin')
        reponse = self._post({'projet': fichier(), 'lead': etranger.pk})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('lead', reponse.data)

    def test_sans_permission_de_gestion_c_est_403(self):
        reponse = self._post({'projet': fichier(), 'lead': self.lead.pk},
                             api=self.api_sans)
        self.assertEqual(reponse.status_code, 403)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
