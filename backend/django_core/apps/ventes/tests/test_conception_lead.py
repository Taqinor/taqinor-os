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


class EntreesConceptionTests(TestCase):
    """ADEV132 — ``EntreesConception`` : l'adaptateur du marché enveloppé,
    la provenance de chaque valeur, et l'empreinte résidentielle IDENTIQUE à
    celle des blocs d'aujourd'hui (``empreinte_entrees``)."""

    _lead = ChampsEntreesTests._lead
    _colonnes_lues = ChampsEntreesTests._colonnes_lues

    def test_residentiel_empreinte_egale_a_celle_des_blocs(self):
        from apps.ventes.conception.entrees import entrees_pour
        from apps.ventes.domain.entrees import empreinte_entrees, entrees_depuis_lead

        company, lead = self._lead('residentiel')
        lead.occupation_jour = ''
        lead.save(update_fields=['occupation_jour'])
        entrees = entrees_pour(lead, company)
        attendue = entrees_depuis_lead(lead, company)
        self.assertEqual(entrees.marche, 'residentiel')
        self.assertEqual(entrees.moteur, attendue)
        self.assertEqual(entrees.empreinte, empreinte_entrees(attendue))
        utilisees = entrees.entrees_utilisees
        self.assertEqual(utilisees['facture_hiver'], {'valeur': 1200.0, 'source': 'lead'})
        self.assertEqual(utilisees['ville']['source'], 'lead')
        # Présence jamais posée : la valeur retenue est le défaut, et c'est dit.
        self.assertEqual(utilisees['occupation_jour']['source'], 'defaut')
        self._sources_du_contrat(utilisees)

    def test_ci_et_pompage_portent_leur_provenance(self):
        from apps.ventes.conception.entrees import entrees_pour

        for marche in ('commercial', 'industriel', 'agricole'):
            with self.subTest(marche=marche):
                company, lead = self._lead(marche)
                entrees = entrees_pour(lead, company)
                self.assertEqual(entrees.marche, marche)
                self.assertIsNone(entrees.moteur)
                self.assertIsNotNone(entrees.resolution)
                self.assertEqual(len(entrees.empreinte), 64)
                self.assertTrue(entrees.entrees_utilisees)
                self.assertIn('lead', {e['source'] for e in entrees.entrees_utilisees.values()})
                self._sources_du_contrat(entrees.entrees_utilisees)
                # Même lead, mêmes entrées : même empreinte (aucun aléa).
                self.assertEqual(entrees_pour(lead, company).empreinte, entrees.empreinte)

    def test_empreinte_change_avec_une_entree_et_avec_la_pose(self):
        from types import SimpleNamespace

        from apps.ventes.conception.entrees import entrees_pour

        company, lead = self._lead('residentiel')
        avant = entrees_pour(lead, company).empreinte
        self.assertNotEqual(entrees_pour(lead, company, toit=SimpleNamespace(empreinte='c' * 64)).empreinte,
                            avant)
        # Le kWh déclaré prime sur les factures (CAD166) : une facture changée
        # ne bouge rien tant qu'il est posé ; le kWh, lui, bouge l'empreinte.
        lead.facture_hiver = Decimal('1500')
        lead.save(update_fields=['facture_hiver'])
        self.assertEqual(entrees_pour(lead, company).empreinte, avant)
        lead.conso_mensuelle_kwh = Decimal('650')
        lead.save(update_fields=['conso_mensuelle_kwh'])
        self.assertNotEqual(entrees_pour(lead, company).empreinte, avant)

    def test_lecture_complete_ne_lit_que_des_colonnes_d_entree(self):
        """Point 2 de la lane : TOUTE colonne du lead lue par ``entrees_pour``
        est dans ``CHAMPS_ENTREES[marche]`` (ou dans la liste de provenance)."""
        from apps.ventes.conception.champs import CHAMPS_LUS_HORS_ENTREES, champs_pour
        from apps.ventes.conception.entrees import entrees_pour

        for marche in ('residentiel', 'commercial', 'industriel', 'agricole'):
            with self.subTest(marche=marche):
                company, lead = self._lead(marche)
                lues = self._colonnes_lues(lambda: entrees_pour(lead, company))
                hors_liste = lues - set(champs_pour(marche)) - set(CHAMPS_LUS_HORS_ENTREES)
                self.assertEqual(hors_liste, set(), sorted(hors_liste))

    def _sources_du_contrat(self, utilisees):
        for champ, entree in utilisees.items():
            self.assertEqual(set(entree), {'valeur', 'source'}, champ)
            self.assertIn(entree['source'], SOURCES_ENTREE, champ)
        json.dumps(utilisees)


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


# ── ADEV159 — figer avant de toucher : ce que build_devis_auto écrit AUJOURD'HUI ─
#
# Goldens de CARACTÉRISATION (un JSON par cas sous ``golden/conception/``) pris
# sur le code de création INTACT, avant l'extraction du pipeline pur (ADEV160)
# et le moteur unique (ADEV133) : lignes du devis, TOUTES les clés de
# ``etude_params``, ``electrical_design`` et les champs du devis que la création
# écrit. Leads = les fabriques des trois modules de test du devis automatique
# (``test_devis_auto``, ``test_ciq120_devis_auto_ci``,
# ``test_agr124_devis_auto_agricole``), leurs patrons hors réseau compris.
#
# Capture (une fois, puis à chaque changement VOULU d'un chiffre — jamais pour
# faire passer une extraction) : ``UPDATE_GOLDEN=1`` dans l'environnement du
# conteneur de test. Golden absent ⇒ rouge ; un écart nomme les clés fautives.

DOSSIER_FIGEAGE = Path(__file__).resolve().parent / 'golden' / 'conception'
INSTANT_FIGEAGE = '2026-10-01T10:00:00+01:00'

#: Normalisés (seule instabilité réelle) : identifiants de base et horodatages
#: (les séquences avancent d'une exécution à l'autre sur la base gardée), la
#: référence du devis. Les produits des lignes sont nommés, jamais numérotés.
CLES_IDS_FIGEAGE = frozenset({
    'id', 'pk', 'uuid', 'token', 'jeton', 'produit', 'produit_id', 'client', 'client_id',
    'lead', 'lead_id', 'devis', 'devis_id', 'company', 'company_id', 'user', 'user_id',
    'created_by', 'updated_by', 'created_at', 'updated_at', 'date_creation',
    'date_modification', 'date_validite', 'ligne_id', '_company_id', 'source_lead_id',
})
#: Empreintes calculées SUR des identifiants de base (relevées instables à la
#: double exécution, ``(bloc parent, clé)``) : la valeur est masquée, la
#: PRÉSENCE de la clé reste figée. Les empreintes résidentielles
#: (``_empreinte_entrees``, ``dimensionnement._empreinte``) restent figées.
EMPREINTES_SUR_IDS = frozenset({('etude_ci', 'empreinte'), ('provenance_pompage', '_empreinte')})
#: Lecteurs de la création qui ne CALCULENT rien (identifiés par la pile) : la
#: résolution du client (identité, et les signaux du ``Lead.save`` qu'elle
#: déclenche) et le tampon de provenance recopié sur le devis
#: (``crm.fiche_selectors.lead_provenance_stamp``). Aucun ne relance le moteur.
LECTEURS_HORS_CALCUL = frozenset({'resolve_client_for_lead', 'lead_provenance_stamp'})
#: Colonnes lues par un sélecteur de calcul sans entrer dans aucun chiffre :
#: ``crm.devis_selectors.site_location_for_devis`` rend aussi l'adresse du
#: chantier (``site_adresse``), qu'aucune étude ne lit (ville et GPS seuls).
COLONNES_LUES_SANS_CHIFFRE = frozenset({'adresse'})
#: Clés d'hypothèse suffixées par l'id d'un produit (``section_ac_<id du câble>``).
CLE_SUFFIXEE_PAR_UN_ID = r'\b(section_ac)_\d+\b'

CHAMPS_DEVIS_FIGES = ('mode_installation', 'statut', 'taux_tva', 'remise_globale', 'devise',
                      'regles_calcul', 'option_acceptee', 'prix_par_kwc', 'prix_cible_kwc',
                      'version', 'is_active', 'overrides', 'echeancier', 'roof_layout',
                      'layout_hash', 'offres_tailles_config', 'variante_tier',
                      'electrical_design_hash')
CHAMPS_LIGNE_FIGES = ('ordre', 'designation', 'quantite', 'prix_unitaire', 'remise', 'taux_tva',
                      'tva_base_legale', 'type_ligne', 'variante', 'optionnelle',
                      'quantite_manuelle', 'prix_manuel', 'ligne_composee', 'role_devis',
                      'groupe_index', 'groupe_label')


def _normaliser_figeage(noeud, parent=None):
    import re
    from datetime import date, datetime

    if isinstance(noeud, dict):
        sortie = {}
        for cle, valeur in noeud.items():
            cle = str(cle)
            if valeur is not None and (cle in CLES_IDS_FIGEAGE or (parent, cle) in EMPREINTES_SUR_IDS):
                sortie[cle] = '<masque>'
            else:
                sortie[cle] = _normaliser_figeage(valeur, cle)
        return sortie
    if isinstance(noeud, (list, tuple)):
        return [_normaliser_figeage(v, parent) for v in noeud]
    if isinstance(noeud, Decimal):
        return str(noeud)
    if isinstance(noeud, (date, datetime)):
        return '<date>'
    if isinstance(noeud, str):
        noeud = re.sub(CLE_SUFFIXEE_PAR_UN_ID, r'\1_<id>', noeud)
        return re.sub(r'\b(DEV|BROUILLON)-[0-9-]+\b', r'\1-<ref>', noeud)
    return noeud


def _ecarts_figeage(attendu, reel, chemin='$'):
    """Chemins où ``reel`` diffère d'``attendu``, clé par clé."""
    if isinstance(attendu, dict) and isinstance(reel, dict):
        ecarts = []
        for cle in sorted(set(attendu) | set(reel)):
            if cle not in attendu or cle not in reel:
                ecarts.append(f'{chemin}.{cle} ({"ajoutée" if cle in reel else "absente"})')
            else:
                ecarts += _ecarts_figeage(attendu[cle], reel[cle], f'{chemin}.{cle}')
        return ecarts
    if isinstance(attendu, list) and isinstance(reel, list) and len(attendu) == len(reel):
        ecarts = []
        for i, (a, r) in enumerate(zip(attendu, reel)):
            ecarts += _ecarts_figeage(a, r, f'{chemin}[{i}]')
        return ecarts
    return [] if attendu == reel else [f'{chemin} : {attendu!r} -> {reel!r}'[:300]]


def _photo_du_devis(devis):
    """Ce que la création a écrit : champs, lignes (produit NOMMÉ), étude,
    conception électrique, totaux. Jamais ``marge_snapshot`` (prix d'achat)."""
    devis.refresh_from_db()
    lignes = []
    for ligne in devis.lignes.select_related('produit').order_by('ordre', 'pk'):
        photo = {nom: getattr(ligne, nom) for nom in CHAMPS_LIGNE_FIGES}
        photo['produit_nom'] = getattr(ligne.produit, 'nom', None)
        lignes.append(photo)
    champs = {nom: getattr(devis, nom) for nom in CHAMPS_DEVIS_FIGES}
    champs.update(total_ht=devis.total_ht, total_tva=devis.total_tva, total_ttc=devis.total_ttc)
    return _normaliser_figeage({
        'champs_devis': champs, 'lignes': lignes, 'etude_params': devis.etude_params or {},
        'electrical_design': devis.electrical_design})


def _emprunt(classe, *noms):
    """Une classe porteuse des fabriques ``noms`` d'une classe de test voisine
    (jamais importée dans ce module : le chargeur la rejouerait)."""
    return type('Fabriques' + classe.__name__, (), {nom: classe.__dict__[nom] for nom in noms})


class FigeageDevisAutoTests(TestCase):
    """ADEV159 — figer avant de toucher : un golden par cas de ``build_devis_auto``."""

    def setUp(self):
        from freezegun import freeze_time

        figeur = freeze_time(INSTANT_FIGEAGE)
        figeur.start()
        self.addCleanup(figeur.stop)
        # Hors réseau (patron SPL160) : chaque lecture PVGIS prend son repli.
        coupure = mock.patch('urllib.request.urlopen', side_effect=OSError('ADEV159 hors réseau'))
        coupure.start()
        self.addCleanup(coupure.stop)

    def _patcher(self, cible, nom, **kw):
        patcher = mock.patch.object(cible, nom, **kw)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _utilisateur(self, company):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            username=f'figeage-{company.pk}', password='x', role_legacy='responsable',
            company=company)

    # ── fabriques des trois modules voisins ─────────────────────────────────
    def _residentiel(self, **extra):
        from apps.crm.models import Lead
        from apps.ventes.tests import test_devis_auto as res

        company = res.make_company('auto-co')
        res.seed_catalogue(company)
        extra.setdefault('ville', res.VILLE_ANCRE)
        extra.setdefault('email', 'auto@ex.com')
        return company, Lead.objects.create(company=company, nom='Auto', prenom='Lead', **extra)

    def _ci(self, *, batteries=False, boulangerie=False, **kw):
        from apps.ventes import tarif_ci
        from apps.ventes.domain import etude_ci
        from apps.ventes.tests import test_ciq120_devis_auto_ci as ci

        fab = _emprunt(ci._Base, 'setUpTestData', '_lead')
        fab._boulangerie = ci.OptionBatterieCITests.__dict__['_boulangerie']
        fab.setUpTestData()
        fab = fab()
        if batteries:
            ci._semer_batterie(fab)
        self._patcher(etude_ci, 'lire_production', side_effect=ci._production_casablanca)
        self._patcher(tarif_ci, 'tarif_applicable', side_effect=ci._tarif_grille)
        return fab.co, (fab._boulangerie(**kw) if boulangerie else fab._lead(**kw))

    def _agricole(self, *, existante=False, **kw):
        from apps.ventes.domain import pompage
        from apps.ventes.tests import test_agr124_devis_auto_agricole as agr

        fab = _emprunt(agr.DevisAutoAgricoleTests, 'setUpTestData', '_produit', '_pompe', '_lead',
                       '_lead_existante')
        fab.setUpTestData()
        fab = fab()
        fab._pompe('15000')
        self._patcher(pompage, 'profils_horaires_site', return_value=agr.PROFILS)
        self._patcher(pompage, 'temperatures_du_site', return_value=None)
        return fab.co, (fab._lead_existante(**kw) if existante else fab._lead(**kw))

    # ── capture / comparaison ───────────────────────────────────────────────
    def _figer(self, nom, company, lead):
        import os

        from apps.ventes.services import build_devis_auto

        devis = build_devis_auto(lead=lead, user=self._utilisateur(company), company=company)
        photo = json.loads(json.dumps(_photo_du_devis(devis), default=str))
        self.assertEqual(_cles_interdites(photo), [], "prix d'achat ou marge dans le golden")
        fichier = DOSSIER_FIGEAGE / f'{nom}.json'
        if os.environ.get('UPDATE_GOLDEN') == '1':
            DOSSIER_FIGEAGE.mkdir(parents=True, exist_ok=True)
            fichier.write_text(json.dumps(photo, indent=1, sort_keys=True, ensure_ascii=False) + '\n',
                               encoding='utf-8')
        self.assertTrue(fichier.is_file(), f'golden {nom} absent : capturer avec UPDATE_GOLDEN=1')
        ecarts = _ecarts_figeage(json.loads(fichier.read_text(encoding='utf-8')), photo)
        self.assertEqual(ecarts, [], f'{nom} : ce que build_devis_auto écrit a changé :\n'
                                     + '\n'.join(ecarts[:40]))
        return photo

    def test_residentiel_facture_en_dirhams_seule(self):
        photo = self._figer('res_facture_dirhams', *self._residentiel(facture_hiver=Decimal('1800')))
        self.assertIn('etude_horaire', photo['etude_params'])
        self.assertIn('dimensionnement', photo['etude_params'])
        # Le golden n'est pas vide : lignes et totaux réellement figés.
        self.assertTrue(photo['lignes'])
        self.assertGreater(float(photo['champs_devis']['total_ttc']), 0)

    def test_residentiel_kwh_declare_ete_different(self):
        self._figer('res_kwh_declare_ete_different', *self._residentiel(
            facture_hiver=Decimal('1800'), facture_ete=Decimal('2600'), ete_differente=True,
            conso_mensuelle_kwh=Decimal('700'), occupation_jour='present'))

    def test_residentiel_batterie_souhaitee_avec(self):
        self._figer('res_batterie_avec', *self._residentiel(
            facture_hiver=Decimal('2500'), batterie_souhaitee='avec'))

    def test_residentiel_batterie_souhaitee_sans(self):
        self._figer('res_batterie_sans', *self._residentiel(
            facture_hiver=Decimal('2500'), batterie_souhaitee='sans'))

    def test_commercial(self):
        photo = self._figer('ci_commercial', *self._ci(conso_mensuelle_kwh=Decimal('6000')))
        self.assertIn('etude_ci', photo['etude_params'])

    def test_commercial_deux_options_batterie(self):
        self._figer('ci_commercial_deux_options', *self._ci(batteries=True, boulangerie=True))

    def test_industriel(self):
        self._figer('ci_industriel', *self._ci(
            conso_mensuelle_kwh=Decimal('20000'), type_installation='industriel',
            categorie_commerciale=None, jours_ouverture=[1, 2, 3, 4, 5, 6], heure_debut=7,
            heure_fin=19))

    def test_agricole_pompe_a_courbe(self):
        photo = self._figer('agr_pompe_courbe', *self._agricole())
        self.assertTrue(any((li['produit_nom'] or '').startswith('Pompe') for li in photo['lignes']))

    def test_creation_complete_ne_lit_que_des_colonnes_connues(self):
        """Point 2 (ADEV133) : toute colonne du lead lue pendant UN
        ``build_devis_auto`` complet est une entrée du moteur
        (``CHAMPS_ENTREES[marche]``), une provenance, ou sert la seule
        RÉSOLUTION DU CLIENT / l'auteur (``LUES_POUR_LE_CLIENT``, jamais un
        chiffre), ou le TAMPON de provenance du devis
        (``crm.fiche_selectors.LEAD_PROVENANCE_FIELDS``, recopié sans calcul) —
        sinon la relance du moteur manquerait ce champ."""
        from apps.ventes.conception.champs import CHAMPS_LUS_HORS_ENTREES, champs_pour

        cas = (('residentiel', self._residentiel(facture_hiver=Decimal('1800'))),
               ('commercial', self._ci(conso_mensuelle_kwh=Decimal('6000'))),
               ('agricole', self._agricole()))
        for marche, (company, lead) in cas:
            with self.subTest(marche=marche):
                lues, hors_calcul = self._lectures_de_la_creation(company, lead)
                self.assertIn('type_installation', lues)
                # Les lecteurs hors calcul lisent bien (l'exclusion n'est pas muette).
                self.assertIn('nom', hors_calcul)
                hors = (lues - set(champs_pour(marche)) - set(CHAMPS_LUS_HORS_ENTREES)
                        - COLONNES_LUES_SANS_CHIFFRE)
                self.assertEqual(hors, set(), f'{marche} : {sorted(hors)}')

    def _lectures_de_la_creation(self, company, lead):
        """``(colonnes lues par le calcul, colonnes lues par un lecteur hors
        calcul)`` pendant un ``build_devis_auto`` complet. Le lecteur est
        identifié par la PILE (jamais par le nom de la colonne) : une colonne
        lue À LA FOIS par le tampon et par le calcul compte pour le calcul."""
        import sys

        from apps.crm.models import Lead
        from apps.ventes.services import build_devis_auto

        user = self._utilisateur(company)
        colonnes = {f.attname: f.name for f in Lead._meta.concrete_fields}
        colonnes.update({f.name: f.name for f in Lead._meta.concrete_fields})
        lues, hors_calcul = set(), set()
        lecture = object.__getattribute__

        def espion(instance, nom):
            if nom in colonnes:
                cadre, profondeur = sys._getframe(1), 0
                while cadre is not None and profondeur < 60:
                    if cadre.f_code.co_name in LECTEURS_HORS_CALCUL:
                        hors_calcul.add(colonnes[nom])
                        break
                    cadre, profondeur = cadre.f_back, profondeur + 1
                else:
                    lues.add(colonnes[nom])
            return lecture(instance, nom)

        with mock.patch.object(Lead, '__getattribute__', espion):
            build_devis_auto(lead=lead, user=user, company=company)
        return lues, hors_calcul

    def test_agricole_pompe_existante(self):
        photo = self._figer('agr_pompe_existante', *self._agricole(existante=True))
        self.assertFalse(any((li['produit_nom'] or '').startswith('Pompe') for li in photo['lignes']))
