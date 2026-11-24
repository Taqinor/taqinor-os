# -*- coding: utf-8 -*-
"""Le moteur unique (D-ACAL-97) — le résultat d'une conception rangé sur le lead.

Module neuf du paquet ``apps/ventes/conception/`` (conception :
``docs/audits/l5-calepinage/controles/C4-un-seul-moteur.md``, §4).

* ADEV129 — le CONTRAT ``contract_samples/conception_lead.json``, posé SEUL sur
  ``main`` avant le modèle, le moteur et la route (PACT10) : chaque clé du §4,
  la forme ACTUELLE des blocs d'étude du devis (jamais redéfinie ici : relue
  dans les contrats et le schéma existants), aucune clé d'achat ni de marge.
* ADEV130 — ``apps/ventes/conception/champs.py::CHAMPS_ENTREES`` : les
  colonnes du lead que lisent les trois adaptateurs (résidentiel, C&I,
  pompage), déduites en ESPIONNANT leurs lectures sur un lead renseigné ; un
  adaptateur qui lit une colonne hors liste est rouge.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_conception_lead"
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase

DOSSIER = Path(__file__).resolve().parents[1] / 'contract_samples'
CONTRAT = DOSSIER / 'conception_lead.json'

#: La sortie du moteur (§3) — aussi la réponse de l'aperçu, sans écriture.
CLES_RESULTAT = {
    'etat', 'refus', 'marche', 'option_retenue', 'valeurs', 'blocs',
    'suppositions', 'entrees_utilisees', 'empreinte', 'niveau_regles',
    'version_moteur',
}
#: Ce que la version RANGÉE ajoute (§4, §5) ; ``lead`` / ``calepinage`` /
#: ``empreinte_pose`` : le porteur et la pose utilisée (ADEV131).
CLES_RANGEES = {
    'declencheur', 'version', 'calcule_le', 'perimee', 'ecart_devis',
    'brouillons_a_mettre_a_jour', 'lead', 'calepinage', 'empreinte_pose',
}
CLES_VALEUR = {'valeur', 'unite', 'source'}
SOURCES_VALEUR = {'moteur', 'pose', 'impose', 'devis', 'defaut'}
SOURCES_ENTREE = {'lead', 'calepinage', 'reglage_societe', 'defaut'}
CLES_SUPPOSITION = {'code', 'champ', 'valeur', 'source', 'message'}
CLES_DECLENCHEUR = {'raison', 'champs', 'origine'}
CLES_CHAMP_MODIFIE = {'champ', 'avant', 'apres'}
ORIGINES = {'lead_entrees_modifiees', 'pose_enregistree', 'regles',
            'remplissage', 'manuel', 'filet'}
CLES_ECART = {'valeur', 'devis', 'conception', 'devis_ref',
              'reviser_possible', 'mise_a_jour_proposee'}
CLES_REFUS = {'code', 'champ', 'message'}
#: La table §2, par option (résidentiel, commercial, industriel).
VALEURS_SOLAIRES = {
    'nb_panneaux', 'puissance_kwc', 'module', 'onduleurs', 'nombre_onduleurs',
    'chaines', 'temperature_froid', 'tension_froid', 'ratio_dc_ac',
    'production_annuelle', 'production_mensuelle', 'autoconsommation',
    'couverture', 'economies_annuelles', 'payback', 'consommation_annuelle',
    'forme_horaire',
}
#: La table §2 en agricole (la pompe remplace taille / matériel / bilan).
VALEURS_POMPAGE = {'nb_panneaux', 'puissance_kwc', 'pompe', 'variateur', 'm3_jour'}
CLES_CORPS_APERCU = {'lead', 'calepinage', 'entrees', 'imposes'}
CLES_IMPOSES = {'nb_panneaux', 'module_id', 'onduleur_id', 'nombre_onduleurs',
                'batterie'}


def _lire(nom):
    return json.loads((DOSSIER / nom).read_text(encoding='utf-8'))


def _cles_interdites(noeud, chemin='$'):
    """Chemins de toute clé d'achat ou de marge, à toute profondeur."""
    trouves = []
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if 'prix_achat' in cle or cle.startswith('marge'):
                trouves.append(f'{chemin}.{cle}')
            trouves += _cles_interdites(valeur, f'{chemin}.{cle}')
    elif isinstance(noeud, list):
        for i, valeur in enumerate(noeud):
            trouves += _cles_interdites(valeur, f'{chemin}[{i}]')
    return trouves


class ContratConceptionLeadTests(SimpleTestCase):
    """ADEV129 — l'échantillon porte chaque clé du §4 et aucune clé interdite."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.doc = json.loads(CONTRAT.read_text(encoding='utf-8'))
        cls.exemples = {k: v for k, v in cls.doc.items()
                        if k.startswith('exemple')}

    def test_route_et_exemples(self):
        self.assertEqual(self.doc['endpoint'],
                         'GET /api/django/ventes/conception/<int:lead_id>/')
        self.assertIn('exemple', self.exemples)
        self.assertGreaterEqual(len(self.exemples), 3)

    def test_chaque_cle_du_resultat_range(self):
        for nom, ex in self.exemples.items():
            with self.subTest(exemple=nom):
                self.assertEqual(set(ex), CLES_RESULTAT | CLES_RANGEES)
                self.assertIn(ex['etat'], {'complet', 'refus'})
                self.assertEqual(len(ex['empreinte']), 64)
                int(ex['empreinte'], 16)
                self.assertIsInstance(ex['niveau_regles'], int)
                self.assertIsInstance(ex['version'], int)
                self.assertIsInstance(ex['perimee'], bool)
                self.assertTrue(ex['lead'] or ex['calepinage'])
                self.assertIn(len(ex['empreinte_pose']), (0, 64))
                if ex['etat'] == 'refus':
                    self.assertEqual(set(ex['refus']), CLES_REFUS)
                    self.assertEqual(ex['valeurs'], {})
                else:
                    self.assertIsNone(ex['refus'])
                    self.assertIn(ex['option_retenue'], ex['valeurs'])

    def test_valeurs_par_option(self):
        for nom, ex in self.exemples.items():
            attendues = (VALEURS_POMPAGE if ex['marche'] == 'agricole'
                         else VALEURS_SOLAIRES)
            for option, valeurs in ex['valeurs'].items():
                with self.subTest(exemple=nom, option=option):
                    self.assertIn(option, {'sans', 'avec'})
                    self.assertEqual(set(valeurs), attendues)
                    for cle, valeur in valeurs.items():
                        self.assertEqual(set(valeur), CLES_VALEUR, cle)
                        self.assertIn(valeur['source'], SOURCES_VALEUR, cle)

    def test_suppositions_entrees_et_declencheur(self):
        for nom, ex in self.exemples.items():
            with self.subTest(exemple=nom):
                for sup in ex['suppositions']:
                    self.assertEqual(set(sup), CLES_SUPPOSITION)
                for champ, entree in ex['entrees_utilisees'].items():
                    self.assertEqual(set(entree), {'valeur', 'source'}, champ)
                    self.assertIn(entree['source'], SOURCES_ENTREE, champ)
                dec = ex['declencheur']
                self.assertEqual(set(dec), CLES_DECLENCHEUR)
                self.assertIn(dec['origine'], ORIGINES)
                for modif in dec['champs']:
                    self.assertEqual(set(modif), CLES_CHAMP_MODIFIE)
                for ecart in ex['ecart_devis']:
                    self.assertEqual(set(ecart), CLES_ECART)
                    self.assertIn(ecart['valeur'], VALEURS_SOLAIRES | VALEURS_POMPAGE)
                for brouillon in ex['brouillons_a_mettre_a_jour']:
                    self.assertEqual(set(brouillon), {'devis', 'reference', 'motif'})
        self.assertTrue(self.doc['exemple']['ecart_devis'])
        self.assertTrue(self.doc['exemple']['declencheur']['champs'])

    def test_apercu_sans_ecriture(self):
        apercu = self.doc['apercu']
        self.assertEqual(apercu['endpoint'],
                         'POST /api/django/ventes/conception/apercu/')
        self.assertEqual(set(apercu['corps']), CLES_CORPS_APERCU)
        self.assertEqual(set(apercu['corps']['imposes']), CLES_IMPOSES)
        self.assertEqual(set(apercu['reponse']), CLES_RESULTAT)
        # Une valeur tapée et non enregistrée n'est jamais dite « du lead ».
        for champ, entree in apercu['reponse']['entrees_utilisees'].items():
            self.assertIn(entree['source'], SOURCES_ENTREE | {'saisie'}, champ)

    def test_blocs_forme_actuelle_du_devis(self):
        """Les blocs sont ceux que le devis porte AUJOURD'HUI dans
        ``etude_params`` : clés dérivées du schéma, sous-clés relues dans les
        contrats existants (jamais une seconde définition)."""
        from apps.ventes.domain import etude_schema as es

        moteurs = {es.MOTEUR_HORAIRE, es.MOTEUR_DIMENSIONNEMENT, es.MOTEUR_CI,
                   es.MOTEUR_POMPAGE}
        horaire = _lire('etude_horaire.json')['exemple']
        ci = _lire('etude_ci_preview.json')['cles_etude_params_ci_v2']
        pompage = _lire('etude_pompage_preview.json')['cles_etude_params_v2']
        sous_cles = {
            'etude_horaire': set(horaire['etude']) | {'_empreinte_entrees'},
            'etude_horaire_sans': set(horaire['etude']) | {'_empreinte_entrees'},
            'dimensionnement': (set(horaire['dimensionnement'])
                                | {'_empreinte_entrees'}),
            'etude_ci': set(next(d['contient'] for d in ci['derivees']
                                 if d['cle'] == 'etude_ci')),
        }
        derivees_pompage = {d['cle'] for d in pompage['derivees']}
        vus = set()
        for nom, ex in [*self.exemples.items(),
                        ('apercu', self.doc['apercu']['reponse'])]:
            for cle, bloc in ex['blocs'].items():
                with self.subTest(exemple=nom, bloc=cle):
                    regle = es.SCHEMA.get(cle)
                    self.assertIsNotNone(regle, cle)
                    self.assertEqual(regle['nature'], es.DERIVEE)
                    self.assertIn(regle['proprietaire'], moteurs)
                    if regle['proprietaire'] == es.MOTEUR_POMPAGE:
                        self.assertTrue(cle in derivees_pompage
                                        or not isinstance(bloc, dict), cle)
                    if cle in sous_cles:
                        self.assertLessEqual(set(bloc), sous_cles[cle])
                    vus.add(cle)
        self.assertLessEqual({'etude_horaire', 'dimensionnement', 'etude_ci'}, vus)

    def test_aucune_cle_d_achat_ni_de_marge(self):
        self.assertEqual(_cles_interdites(self.doc), [])
        # Le parcours détecte bien une clé interdite enfouie.
        self.assertEqual(_cles_interdites({'a': [{'b': {'prix_achat_ht': 1}}]}),
                         ['$.a[0].b.prix_achat_ht'])


# ── ADEV130 — les colonnes du lead qui sont des entrées du moteur ────────────

#: Un lead renseigné sur toutes les entrées connues des trois adaptateurs, pour
#: que chaque branche de lecture s'exécute (valeurs illustratives).
_LEAD_RENSEIGNE = {
    'ville': 'Casablanca', 'ville_reference': 'Casablanca',
    'gps_lat': Decimal('33.5731'), 'gps_lng': Decimal('-7.5898'),
    'facture_hiver': Decimal('1200'), 'facture_ete': Decimal('900'),
    'ete_differente': True, 'conso_mensuelle_kwh': Decimal('500'),
    'bill_kwh': Decimal('500'), 'raccordement': 'triphase',
    'occupation_jour': 'present', 'equip_clim': True, 'equip_piscine': True,
    'equip_voiture_electrique': True, 'equip_chauffe_eau_electrique': True,
    'tension_raccordement': 'bt', 'contrat_electricite': 'bt_patente',
    'compteur_puissance_kva': Decimal('36'), 'regime_equipes': '2x8',
    'jours_ouverture': [1, 2, 3, 4, 5], 'heure_debut': 8, 'heure_fin': 18,
    'fermeture_mois': [8], 'type_surface': 'toiture',
    'type_toiture': 'terrasse_beton', 'surface_toiture_m2': Decimal('200'),
    'tva_recuperable': 'oui', 'pompe_hmt_m': Decimal('40'),
    'pompe_debit_m3h': Decimal('5'), 'besoin_eau_m3j': Decimal('30'),
}


class ChampsEntreesTests(TestCase):
    """ADEV130 — un adaptateur qui lit une colonne absente de
    ``CHAMPS_ENTREES`` est rouge. L'espion compte TOUTE lecture d'une colonne
    sur une instance ``Lead`` pendant l'appel de l'adaptateur (y compris dans
    les sélecteurs du CRM qu'il appelle)."""

    def _lead(self, marche):
        from apps.crm.models import Lead
        from authentication.models import Company

        company = Company.objects.create(nom=f'Moteur {marche}',
                                         slug=f'moteur-unique-{marche}')
        lead = Lead.objects.create(company=company, nom='Lead', prenom=marche,
                                   telephone='+212600000000',
                                   type_installation=marche, **_LEAD_RENSEIGNE)
        return company, lead

    def _colonnes_lues(self, appel):
        from apps.crm.models import Lead

        colonnes = {}
        for champ in Lead._meta.concrete_fields:
            colonnes[champ.name] = champ.name
            colonnes[champ.attname] = champ.name
        lues = set()
        lecture = object.__getattribute__

        def espion(instance, nom):
            if nom in colonnes:
                lues.add(colonnes[nom])
            return lecture(instance, nom)

        with mock.patch.object(Lead, '__getattribute__', espion):
            appel()
        return lues

    def _adaptateur(self, marche, company, lead):
        from apps.ventes.domain import entrees, etude_ci, pompage

        if marche == 'residentiel':
            return lambda: entrees.entrees_depuis_lead(lead, company)
        if marche == 'agricole':
            return lambda: pompage.resoudre_entrees(company, {}, lead=lead)
        return lambda: etude_ci.resoudre_entrees({}, lead=lead)

    def test_chaque_colonne_lue_par_l_adaptateur_est_dans_la_liste(self):
        from apps.ventes.conception.champs import (
            CHAMPS_ENTREES, CHAMPS_LUS_HORS_ENTREES, champs_pour)

        self.assertEqual(set(CHAMPS_ENTREES),
                         {'residentiel', 'commercial', 'industriel', 'agricole'})
        for marche in CHAMPS_ENTREES:
            with self.subTest(marche=marche):
                company, lead = self._lead(marche)
                lues = self._colonnes_lues(self._adaptateur(marche, company, lead))
                # L'espion voit bien les lectures (preuve qu'il n'est pas muet).
                self.assertIn('gps_lat', lues)
                hors_liste = lues - set(champs_pour(marche)) - set(CHAMPS_LUS_HORS_ENTREES)
                self.assertEqual(
                    hors_liste, set(),
                    f"{marche} : colonnes lues par l'adaptateur et absentes de "
                    f"CHAMPS_ENTREES['{marche}'] : {sorted(hors_liste)}")

    def test_listes_sur_de_vraies_colonnes_sans_identite(self):
        from apps.crm.models import Lead
        from apps.ventes.conception.champs import (
            CHAMPS_ENTREES, CHAMPS_LUS_HORS_ENTREES, champs_pour)

        colonnes = {f.name for f in Lead._meta.concrete_fields}
        for marche, champs in CHAMPS_ENTREES.items():
            with self.subTest(marche=marche):
                self.assertIsInstance(champs, tuple)
                self.assertEqual(champs_pour(marche), champs)
                self.assertLessEqual(set(champs), colonnes)
                self.assertEqual(set(champs) & set(CHAMPS_LUS_HORS_ENTREES), set())
                self.assertIn('type_installation', champs)
                for identite in ('nom', 'prenom', 'telephone', 'email', 'notes'):
                    self.assertNotIn(identite, champs)
        self.assertIn('facture_hiver', champs_pour('residentiel'))
        self.assertLessEqual(set(CHAMPS_LUS_HORS_ENTREES), colonnes)
        with self.assertRaises(KeyError):
            champs_pour('inconnu')


# ── ADEV131 — le résultat rangé : une seule version courante par porteur ─────

def _champs_version(**extra):
    """Une version de conception complète (valeurs illustratives)."""
    champs = {
        'etat': 'complet', 'refus': None, 'marche': 'residentiel',
        'option_retenue': 'sans',
        'valeurs': {'sans': {'nb_panneaux': {'valeur': 10, 'unite': 'panneaux',
                                             'source': 'moteur'}}},
        'blocs': {'etude_horaire': {'version': 1, 'kwc': 7.1}},
        'entrees_utilisees': {'facture_hiver': {'valeur': 1200, 'source': 'lead'}},
        'suppositions': [{'code': 'occupation_supposee', 'champ': 'occupation_jour',
                          'valeur': 'presence_jour', 'source': 'defaut',
                          'message': 'Présence en journée supposée.'}],
        'empreinte': 'a' * 64, 'empreinte_pose': '', 'niveau_regles': 14,
        'version_moteur': 'qjr43-2',
        'declencheur': {'raison': 'remplissage initial', 'champs': [],
                        'origine': 'remplissage'},
    }
    champs.update(extra)
    return champs


class ConceptionLeadModeleTests(TestCase):
    """ADEV131 — ``ConceptionLead`` : une seule ``courante`` par porteur
    (lead, ou calepinage sans lead), version = plus haut utilisé + 1, société
    venue du porteur, rien n'est jamais supprimé."""

    def setUp(self):
        from apps.crm.models import Lead
        from authentication.models import Company

        self.company = Company.objects.create(nom='Conception A', slug='conception-a')
        self.autre = Company.objects.create(nom='Conception B', slug='conception-b')
        self.lead = Lead.objects.create(company=self.company, nom='Lead', prenom='A',
                                        telephone='+212600000001')

    def test_deux_versions_la_seconde_devient_seule_courante(self):
        from apps.ventes.models import ConceptionLead

        v1 = ConceptionLead.ranger(lead=self.lead, **_champs_version())
        v2 = ConceptionLead.ranger(lead=self.lead, **_champs_version(empreinte='b' * 64))
        v1.refresh_from_db()
        self.assertEqual((v1.version, v1.courante), (1, False))
        self.assertEqual((v2.version, v2.courante), (2, True))
        self.assertEqual(ConceptionLead.objects.filter(lead=self.lead).count(), 2)
        self.assertEqual(ConceptionLead.objects.get(lead=self.lead, courante=True).pk, v2.pk)

    def test_contrainte_refuse_deux_courantes_pour_un_lead(self):
        from django.db import IntegrityError, transaction

        from apps.ventes.models import ConceptionLead

        ConceptionLead.ranger(lead=self.lead, **_champs_version())
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ConceptionLead.objects.create(company=self.company, lead=self.lead,
                                              version=9, courante=True, **_champs_version())

    def test_contrainte_refuse_deux_courantes_pour_un_calepinage_sans_lead(self):
        from django.db import IntegrityError, transaction

        from apps.ventes.models import ConceptionLead

        ConceptionLead.objects.create(company=self.company, calepinage_id=77, version=1,
                                      courante=True, **_champs_version())
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ConceptionLead.objects.create(company=self.company, calepinage_id=77,
                                              version=2, courante=True, **_champs_version())

    def test_version_plus_haut_utilise_plus_un_jamais_le_compte(self):
        from apps.ventes.models import ConceptionLead

        # Une seule ligne, mais de version 5 : un count()+1 rendrait 2.
        ConceptionLead.objects.create(company=self.company, lead=self.lead, version=5,
                                      courante=False, **_champs_version())
        nouvelle = ConceptionLead.ranger(lead=self.lead, **_champs_version())
        self.assertEqual(nouvelle.version, 6)

    def test_societe_venue_du_lead_jamais_d_ailleurs(self):
        from apps.ventes.models import ConceptionLead

        version = ConceptionLead.ranger(lead=self.lead, **_champs_version())
        self.assertEqual(version.company_id, self.company.pk)
        with self.assertRaises(ValueError):
            ConceptionLead.ranger(lead=self.lead, company=self.autre, **_champs_version())

    def test_porteur_obligatoire_et_lead_en_chaine_cascade(self):
        from django.db import models

        from apps.ventes.models import ConceptionLead

        with self.assertRaises(ValueError):
            ConceptionLead.ranger(company=self.company, **_champs_version())
        champ = ConceptionLead._meta.get_field('lead')
        self.assertEqual(champ.related_model._meta.label, 'crm.Lead')
        self.assertTrue(champ.null)
        self.assertIs(champ.remote_field.on_delete, models.CASCADE)

    def test_version_relue_champ_pour_champ(self):
        from apps.ventes.models import ConceptionLead

        champs = _champs_version()
        rangee = ConceptionLead.ranger(lead=self.lead, **champs)
        relue = ConceptionLead.objects.get(pk=rangee.pk)
        for nom in ('valeurs', 'blocs', 'suppositions', 'entrees_utilisees', 'declencheur',
                    'etat', 'marche', 'option_retenue', 'empreinte', 'niveau_regles',
                    'version_moteur'):
            self.assertEqual(getattr(relue, nom), champs[nom], nom)
        self.assertIsNotNone(relue.calcule_le)
        self.assertIsNone(relue.calcule_par)
