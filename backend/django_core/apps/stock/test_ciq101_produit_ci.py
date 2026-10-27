"""CIQ101 — champs C&I sur ``Produit`` (``role_ci``, ``type_pose``,
``delai_appro_jours``) et fiches limiteur / logger / protection / câble /
structure + champs onduleur ajoutés.

Contrat partagé : ``contract_samples/produit_ci.json``. Vide = « non publié »,
jamais une valeur par défaut.
"""
import json
from importlib import import_module
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations import AddField, AlterField
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import Categorie, FicheTechnique, Produit
from authentication.models import Company
from core import product_roles

User = get_user_model()

URL_PRODUITS = '/api/django/stock/produits/'
URL_FICHES = '/api/django/stock/fiches-techniques/'
CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_ci.json')
    .read_text(encoding='utf-8'))
MIGRATION = '0163_ciq101_produit_ci'


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


def _champs_fiches_ci():
    champs = []
    for nom, bloc in CONTRAT['fiches'].items():
        champs.extend(bloc['champs'])
    return champs


class CIQ101Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='ciq101-co', defaults={'nom': 'CIQ101 Co'})[0]
        roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='ciq101_dir', password='x', company=cls.company,
            role=roles['Directeur'])


class TestVocabulaire(SimpleTestCase):
    def test_roles_ci_egaux_au_contrat(self):
        self.assertEqual(
            list(product_roles.ROLES_CI), list(CONTRAT['roles_ci']))
        self.assertEqual(product_roles.LIBELLES_ROLES_CI, CONTRAT['roles_ci'])
        # CCAT4 — libellés des types de pose : le contrat les porte, l'écran les lit.
        self.assertEqual(product_roles.LIBELLES_TYPES_POSE, CONTRAT['libelles_types_pose'])

    def test_types_pose_egaux_au_contrat(self):
        self.assertEqual(
            list(product_roles.TYPES_POSE),
            CONTRAT['champs_produit']['type_pose']['choix'])

    def test_roles_ci_distincts_et_roles_devis_inchanges(self):
        # aucun rôle résidentiel ajouté : vocabulaire séparé
        self.assertNotIn('onduleur_string_tri', product_roles.ROLES_DEVIS)
        self.assertEqual(product_roles.ROLES_DEVIS[0], 'onduleur_reseau')

    def test_famille_vers_role_exhaustif_sans_modification(self):
        self.assertEqual(
            set(product_roles.FAMILLE_VERS_ROLE),
            {v for v, _ in Categorie.TypeEquipement.choices})
        self.assertIsNone(product_roles.FAMILLE_VERS_ROLE['compteur'])
        self.assertIsNone(product_roles.FAMILLE_VERS_ROLE['protection'])

    def test_types_fiche_ajoutes_et_anciens_conserves(self):
        valeurs = [c[0] for c in FicheTechnique.TypeFiche.choices]
        for v in ('module', 'onduleur', 'batterie', 'optimiseur', 'pompe',
                  'variateur_pompage', 'autre', 'limiteur', 'logger',
                  'protection', 'cable', 'structure'):
            self.assertIn(v, valeurs)

    def test_cles_des_fiches_du_contrat_sur_le_serializeur(self):
        from apps.stock.serializers_fiche_technique import FicheTechniqueSerializer
        champs = set(FicheTechniqueSerializer().fields)
        for cle in _champs_fiches_ci():
            self.assertIn(cle, champs)
        for cle in CONTRAT['fiches']['onduleur'][
                'champs_onduleur_existants']:
            self.assertIn(cle, champs)

    def test_pvond_non_etendu(self):
        """Les cinq champs onduleur ajoutés n'entrent PAS dans le verrou."""
        from apps.stock.selectors import CLES_CONTRAT_ONDULEUR
        for cle in CONTRAT['fiches']['onduleur']['champs']:
            self.assertNotIn(cle.removeprefix('ond_'), CLES_CONTRAT_ONDULEUR)
        self.assertEqual(len(CLES_CONTRAT_ONDULEUR), 10)


class TestSchemaFicheBornes(SimpleTestCase):
    """api-fuzz #997 : le schéma de requête de la fiche dit les bornes que les
    validateurs appliquent (oracle : DRF `run_validation` sur les mêmes
    valeurs, jamais un motif plus large que le serveur)."""

    @staticmethod
    def _schema():
        from apps.stock.schema_contraintes import declarer_contraintes_achats
        base = {'type': 'string', 'format': 'decimal', 'nullable': True}
        champs = {
            'ond_rendement_max_pct': r'^-?(?:\d{1,3}(?:\.\d{0,1})?|\.\d{1,1})$',
            'ond_rendement_cec_pct': r'^-?(?:\d{1,3}(?:\.\d{0,1})?|\.\d{1,1})$',
            'bat_c_rate_charge': r'^-?(?:\d{1,2}(?:\.\d{0,2})?|\.\d{1,2})$',
            'bat_c_rate_decharge': r'^-?(?:\d{1,2}(?:\.\d{0,2})?|\.\d{1,2})$',
            'ond_conso_nuit_w': r'^-?(?:\d{1,5}(?:\.\d{0,2})?|\.\d{1,2})$',
            'lim_phases': None,
        }
        props = {n: ({**base, 'pattern': m} if m else {'type': 'integer'})
                 for n, m in champs.items()}
        schema = {'components': {'schemas': {
            'FicheTechniqueRequest': {'properties': props}}}}
        declarer_contraintes_achats(schema)
        return props

    def test_motifs_jamais_plus_larges_que_drf(self):
        import re
        from rest_framework.exceptions import ValidationError
        from apps.stock.serializers_fiche_technique import (
            FicheTechniqueSerializer,
        )
        props = self._schema()
        champs = FicheTechniqueSerializer().fields
        valeurs = ['', '-', '.', '0', '0.0', '0.00', '0.001', '0.009', '0.01',
                   '0.5', '.5', '.01', '1', '1.0', '5.', '99.9', '100',
                   '100.0', '100.1', '101', '-1', '12.345', '99.99']
        for nom in ('ond_rendement_max_pct', 'ond_rendement_cec_pct',
                    'bat_c_rate_charge', 'bat_c_rate_decharge', 'ond_conso_nuit_w'):
            motif = re.compile(props[nom]['pattern'])
            for v in valeurs:
                if not motif.search(v):
                    continue
                try:
                    champs[nom].run_validation(v)
                except ValidationError as exc:
                    self.fail(f'{nom}={v!r} publié mais refusé : {exc.detail}')

    def test_conso_nuit_sans_signe_zero_publie(self):
        # api-fuzz : ``ond_conso_nuit_w`` >= 0 (MinValueValidator) — « -.17 » était publié.
        import re
        motif = self._schema()['ond_conso_nuit_w']['pattern']
        for refuse in ('-.17', '-1', '-0'):
            self.assertIsNone(re.search(motif, refuse), refuse)
        for accepte in ('0', '.17', '5', '12345.67'):
            self.assertIsNotNone(re.search(motif, accepte), accepte)

    def test_zero_n_est_plus_publie_et_phases_limitees(self):
        import re
        props = self._schema()
        for nom in ('ond_rendement_max_pct', 'bat_c_rate_charge'):
            self.assertIsNone(re.search(props[nom]['pattern'], '0'))
        self.assertEqual(props['lim_phases']['enum'], [1, 3, None])
        self.assertTrue(props['lim_phases']['nullable'])


class TestMigration(SimpleTestCase):
    def test_operations_additives_et_reversibles(self):
        module = import_module(f'apps.stock.migrations.{MIGRATION}')
        ops = module.Migration.operations
        for op in ops:
            self.assertIsInstance(op, (AddField, AlterField))
            self.assertTrue(op.reversible)
        ajoutes = {op.name for op in ops if isinstance(op, AddField)}
        for cle in ('role_ci', 'type_pose', 'delai_appro_jours'):
            self.assertIn(cle, ajoutes)
        for cle in _champs_fiches_ci():
            self.assertIn(cle, ajoutes)

    def test_aller_retour_des_etats(self):
        loader = MigrationLoader(None, ignore_no_migrations=True)
        apres = loader.project_state(('stock', MIGRATION)).apps
        avant = loader.project_state(
            ('stock', '0162_agr104_roles_pompage')).apps
        noms_apres = {f.name for f in apres.get_model(
            'stock', 'Produit')._meta.get_fields()}
        noms_avant = {f.name for f in avant.get_model(
            'stock', 'Produit')._meta.get_fields()}
        self.assertIn('role_ci', noms_apres)
        self.assertNotIn('role_ci', noms_avant)
        fiche_avant = {f.name for f in avant.get_model(
            'stock', 'FicheTechnique')._meta.get_fields()}
        for cle in _champs_fiches_ci():
            self.assertNotIn(cle, fiche_avant)


class TestSaisieEtLecture(CIQ101Base):
    def test_compteur_tc_declare_servi_tel_quel(self):
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, {
            'nom': 'Compteur triphasé à TC 250 A', 'prix_vente': '3000',
            'role_ci': 'compteur_injection'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        pid = r.data['id']
        r = client.post(URL_FICHES, {
            'produit': pid, 'type_fiche': 'limiteur',
            'lim_mode': 'compteur_tc', 'lim_phases': 3}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        fiche = client.get(f'{URL_FICHES}{r.data["id"]}/').data
        self.assertEqual(fiche['lim_mode'], 'compteur_tc')
        self.assertIsNone(fiche['lim_onduleurs_max'])  # non publié
        self.assertEqual(fiche['lim_marques'], [])
        self.assertIsNone(fiche['lim_i_max_a'])
        produit = client.get(f'{URL_PRODUITS}{pid}/').data
        self.assertEqual(produit['role_ci'], 'compteur_injection')
        self.assertIsNone(produit['role_devis'])  # role_devis non touché

    def test_role_ci_hors_vocabulaire_400_nomme_le_champ(self):
        r = api_for(self.user).post(URL_PRODUITS, {
            'nom': 'Produit invalide', 'prix_vente': '1',
            'role_ci': 'turbine'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('role_ci', r.data)

    def test_type_pose_bac_acier_accepte_et_inconnu_refuse(self):
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, {
            'nom': 'Structure bac acier', 'prix_vente': '1',
            'role_ci': 'structure_ci', 'type_pose': 'bac_acier'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['type_pose'], 'bac_acier')
        r = client.post(URL_PRODUITS, {
            'nom': 'Structure x', 'prix_vente': '1', 'type_pose': 'vitre'},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('type_pose', r.data)

    def test_produit_sans_saisie_vide_non_publie(self):
        p = Produit.objects.create(
            company=self.company, nom='Produit vide', prix_vente=1)
        r = api_for(self.user).get(f'{URL_PRODUITS}{p.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['role_ci'], '')
        self.assertEqual(r.data['type_pose'], '')
        self.assertIsNone(r.data['delai_appro_jours'])

    def test_masse_sans_notice_refusee(self):
        p = Produit.objects.create(
            company=self.company, nom='Structure lestée', prix_vente=1)
        client = api_for(self.user)
        r = client.post(URL_FICHES, {
            'produit': p.pk, 'type_fiche': 'structure',
            'struct_type_pose': 'toit_plat_leste',
            'struct_masse_kg_m2': 12}, format='json')
        self.assertEqual(r.status_code, 409)  # ENF11 : règle croisée masse/notice
        self.assertIn('struct_notice', r.data)
        r = client.post(URL_FICHES, {
            'produit': p.pk, 'type_fiche': 'structure',
            'struct_type_pose': 'toit_plat_leste', 'struct_masse_kg_m2': 12,
            'struct_notice': {'document': 'Notice X', 'date': '2026-01-02',
                              'page': 3}}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['struct_notice'], {
            'document': 'Notice X', 'date': '2026-01-02', 'page': 3})

    def test_fiche_vide_null_et_pdf_vide_acceptes(self):
        """api-fuzz #997 : les validateurs lisent déjà `None` comme « vide » ;
        le schéma publié (nullable) et le serveur disent la même chose."""
        p = Produit.objects.create(
            company=self.company, nom='Limiteur nul', prix_vente=1)
        r = api_for(self.user).post(URL_FICHES, {
            'produit': p.pk, 'type_fiche': 'limiteur', 'lim_phases': None,
            'ond_compteurs_compatibles': None, 'lim_marques': None,
            'log_marques': None, 'struct_notice': None, 'pdf': ''},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['lim_marques'], [])
        self.assertEqual(r.data['ond_compteurs_compatibles'], [])
        self.assertEqual(r.data['log_marques'], [])
        self.assertEqual(r.data['struct_notice'],
                         {'document': '', 'date': None, 'page': None})
        self.assertIsNone(r.data['lim_phases'])

    def test_options_servent_les_libelles_fr_des_roles(self):
        """CIQ104 — l'écran lit les libellés par OPTIONS (aucun miroir JS)."""
        r = api_for(self.user).options(URL_PRODUITS)
        self.assertEqual(r.status_code, 200)
        choix = {c['value']: c['display_name']
                 for c in r.data['actions']['POST']['role_ci']['choices']}
        self.assertEqual(choix, CONTRAT['roles_ci'])

    def test_etat_ci_servi_et_sans_prix_achat(self):
        """CIQ104 — ``etat_ci`` (filtre « C&I à compléter »)."""
        p = Produit.objects.create(
            company=self.company, nom='Structure bac acier', prix_vente=0,
            role_ci='structure_ci', type_pose='bac_acier')
        r = api_for(self.user).get(f'{URL_PRODUITS}{p.pk}/')
        self.assertEqual(r.data['etat_ci']['role_ci'], 'structure_ci')
        self.assertFalse(r.data['etat_ci']['prix_connu'])
        self.assertTrue(r.data['etat_ci']['eligible_ci'])
        self.assertNotIn('prix_achat', r.data['etat_ci'])
        autre = Produit.objects.create(
            company=self.company, nom='Article quelconque', prix_vente=1)
        r = api_for(self.user).get(f'{URL_PRODUITS}{autre.pk}/')
        self.assertIsNone(r.data['etat_ci'])

    def test_enregistrer_rouvrir_enregistrer_identique(self):
        client = api_for(self.user)
        r = client.post(URL_PRODUITS, {
            'nom': 'Disjoncteur AC 125 A', 'prix_vente': '900',
            'role_ci': 'protection_ac', 'delai_appro_jours': 21},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        url_p = f'{URL_PRODUITS}{r.data["id"]}/'
        r = client.post(URL_FICHES, {
            'produit': r.data['id'], 'type_fiche': 'protection',
            'prot_type': 'disjoncteur', 'prot_cote': 'ac',
            'prot_calibre_a': 125, 'prot_poles': 4}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        url_f = f'{URL_FICHES}{r.data["id"]}/'
        avant_p = client.get(url_p).data
        avant_f = client.get(url_f).data
        champs_p = ('role_ci', 'type_pose', 'delai_appro_jours')
        r = client.patch(url_p, {c: avant_p[c] for c in champs_p},
                         format='json')
        self.assertEqual(r.status_code, 200, r.data)
        champs_f = _champs_fiches_ci()
        r = client.patch(url_f, {c: avant_f[c] for c in champs_f},
                         format='json')
        self.assertEqual(r.status_code, 200, r.data)
        apres_p = client.get(url_p).data
        apres_f = client.get(url_f).data
        for c in champs_p:
            self.assertEqual(avant_p[c], apres_p[c], c)
        for c in champs_f:
            self.assertEqual(avant_f[c], apres_f[c], c)


class TestCCAT1PrixConnuCi(CIQ101Base):
    """CCAT1 — UNE règle « prix connu C&I » pour la fiche produit
    (``etat_ci_produit``) et le catalogue de l'étude (``produits_ci``)."""

    def _etats(self, produit):
        from apps.stock.selectors import etat_ci_produit, produits_ci
        catalogue = {e['id']: e for e in produits_ci(self.company)}
        return etat_ci_produit(produit), catalogue[produit.pk]

    def test_coffret_au_bareme_sans_prix_de_vente_est_connu(self):
        from decimal import Decimal
        p = Produit.objects.create(
            company=self.company, nom='Coffret AC bareme', prix_vente=0,
            role_ci='coffret_ac', prix_fixe_ht=Decimal('1200'))
        etat, entree = self._etats(p)
        self.assertTrue(etat['prix_connu'])
        self.assertTrue(entree['prix_connu'])
        self.assertEqual(etat['eligible_ci'], entree['eligible_ci'])

    def test_coffret_sans_bareme_ni_prix_est_inconnu(self):
        p = Produit.objects.create(
            company=self.company, nom='Coffret AC nu', prix_vente=0,
            role_ci='coffret_ac')
        etat, entree = self._etats(p)
        self.assertFalse(etat['prix_connu'])
        self.assertFalse(entree['prix_connu'])

    def test_bareme_ne_vaut_que_pour_les_coffrets(self):
        from decimal import Decimal
        from apps.stock.etat_ci import prix_connu_ci
        p = Produit(nom='Structure', prix_vente=0,
                    prix_fixe_ht=Decimal('500'))
        self.assertFalse(prix_connu_ci(p, 'structure_ci'))
        self.assertTrue(prix_connu_ci(p, 'coffret_dc'))
        p.prix_fixe_ht, p.prix_vente = None, Decimal('10')
        self.assertTrue(prix_connu_ci(p, 'structure_ci'))


class TestCCAT2OptionBatterie(CIQ101Base):
    """CCAT2 — hybrides basse tension et batteries de l'option « avec
    batterie » visibles dans ``etat_ci`` (mêmes règles que le moteur)."""

    def _produit(self, nom, role_devis, prix=0, **fiche):
        p = Produit.objects.create(
            company=self.company, nom=nom, prix_vente=prix,
            role_devis=role_devis)
        if fiche:
            FicheTechnique.objects.create(produit=p, **fiche)
        return Produit.objects.select_related(
            'categorie', 'fiche_technique').get(pk=p.pk)

    def _hybride(self, prix=0, **plage):
        return self._produit(
            'Deye SUN-12K-SG05LP3 hybride', 'onduleur_hybride', prix,
            type_fiche='onduleur', **plage)

    def _etat(self, produit):
        from apps.stock.etat_ci import etat_ci_complet
        return etat_ci_complet(produit)

    def test_hybride_bt_sans_prix(self):
        etat = self._etat(self._hybride(ond_bat_v_min=40, ond_bat_v_max=60,
                                        ond_ac_kw=12, ond_phases=3))
        self.assertEqual(etat['role_ci'], 'onduleur_hybride')
        self.assertEqual(etat['classement'], 'declare')
        self.assertFalse(etat['prix_connu'])
        self.assertFalse(etat['eligible_ci'])
        self.assertEqual(etat['motif_exclusion'], 'prix de vente non saisi')

    def test_hybride_sans_plage_batterie(self):
        etat = self._etat(self._hybride(prix=9000))
        self.assertFalse(etat['eligible_ci'])
        self.assertEqual(
            etat['motif_exclusion'], 'plage de tension batterie non publiée')

    def test_hybride_haute_tension_hors_option(self):
        self.assertIsNone(self._etat(
            self._hybride(prix=9000, ond_bat_v_min=150, ond_bat_v_max=600)))

    def test_hybride_bt_complet_eligible(self):
        etat = self._etat(self._hybride(
            prix=9000, ond_bat_v_min=40, ond_bat_v_max=60, ond_ac_kw=12,
            ond_phases=3))
        self.assertTrue(etat['eligible_ci'])
        self.assertTrue(etat['prix_connu'])
        self.assertIsNone(etat['motif_exclusion'])
        self.assertEqual(
            set(etat), {'role_ci', 'libelle', 'classement', 'prix_connu',
                        'eligible_ci', 'motif_exclusion'})

    def test_hybride_sans_puissance_ac_ni_phase(self):
        # Revue CCAT2 — le moteur écarte ces hybrides (onduleurs.py) : Stock aussi.
        sans_ac = self._etat(self._hybride(
            prix=9000, ond_bat_v_min=40, ond_bat_v_max=60, ond_phases=3))
        self.assertEqual(sans_ac['motif_exclusion'],
                         'fiche incomplète : puissance AC')
        sans_phase = self._etat(self._hybride(
            prix=9000, ond_bat_v_min=40, ond_bat_v_max=60, ond_ac_kw=12))
        self.assertEqual(sans_phase['motif_exclusion'], 'phase non publiée')

    def test_hybride_sans_fiche_onduleur(self):
        etat = self._etat(self._produit(
            'Onduleur hybride sans fiche', 'onduleur_hybride', 9000))
        self.assertEqual(etat['motif_exclusion'], 'fiche onduleur absente')

    def test_batterie_haute_tension_hors_option_bt(self):
        # R4 Fable — le pack HV garde sa tension OMISE exprès (seed BAT-DYN-HV-16) :
        # jamais « à compléter », hors option basse tension comme le moteur.
        self.assertIsNone(self._etat(self._produit(
            'Batterie Deye BOS-B Pro haute tension — 16 kWh', 'batterie', 48000,
            type_fiche='batterie', bat_kwh_nominal=16)))
        self.assertIsNone(self._etat(self._produit(
            'Batterie HV', 'batterie', 48000, type_fiche='batterie',
            bat_kwh_usable=14, bat_v_nominal=409.6)))

    def test_batterie_sans_capacite_utile(self):
        etat = self._etat(self._produit(
            'Batterie Dyness', 'batterie', 12000, type_fiche='batterie',
            bat_v_nominal=51.2))
        self.assertEqual(etat['role_ci'], 'batterie')
        self.assertFalse(etat['eligible_ci'])
        self.assertEqual(etat['motif_exclusion'],
                         'fiche incomplète : capacité utile')

    def test_batterie_capacite_nominale_x_dod_et_tension(self):
        etat = self._etat(self._produit(
            'Batterie Dyness', 'batterie', 12000, type_fiche='batterie',
            bat_kwh_nominal=10, bat_dod_pct=90, bat_v_nominal=51.2))
        self.assertTrue(etat['eligible_ci'])
        self.assertIsNone(etat['motif_exclusion'])

    def test_batterie_sans_fiche_ni_prix(self):
        etat = self._etat(self._produit('Batterie sans fiche', 'batterie'))
        self.assertEqual(
            etat['motif_exclusion'],
            'fiche incomplète : capacité utile, tension nominale')

    def test_batterie_ci_declaree_controle_aussi_la_fiche(self):
        p = Produit.objects.create(
            company=self.company, nom='Batterie C&I', prix_vente=5000,
            role_ci='batterie_ci')
        etat = self._etat(p)
        self.assertEqual(etat['role_ci'], 'batterie_ci')
        self.assertFalse(etat['eligible_ci'])
        self.assertEqual(
            etat['motif_exclusion'],
            'fiche incomplète : capacité utile, tension nominale')

    def test_produit_quelconque_reste_sans_etat(self):
        self.assertIsNone(self._etat(self._produit('Article', '', 10)))

    def test_etat_ci_servi_par_l_api_pour_un_hybride(self):
        p = self._hybride(
            prix=9000, ond_bat_v_min=40, ond_bat_v_max=60,
            ond_ac_kw=12, ond_phases=3)
        r = api_for(self.user).get(f'{URL_PRODUITS}{p.pk}/')
        self.assertEqual(r.data['etat_ci']['role_ci'], 'onduleur_hybride')
        self.assertTrue(r.data['etat_ci']['eligible_ci'])
        self.assertNotIn('prix_achat', r.data['etat_ci'])

    def test_tension_port_bt_alignee_sur_le_moteur(self):
        from apps.ventes.moteur_ci import batterie
        self.assertEqual(product_roles.TENSION_PORT_BT_MAX_V,
                         batterie.TENSION_PORT_BT_MAX_V)


class TestCCAT11Panneau(CIQ101Base):
    """CCAT11 — un panneau sans Pmax ou sans prix bloque tout devis C&I : il
    apparaît dans ``etat_ci`` (le moteur l'ignore sinon, sans le dire)."""

    def _panneau(self, prix=0, **fiche):
        p = Produit.objects.create(
            company=self.company, nom='Panneau 550 W', prix_vente=prix,
            role_devis='panneau')
        if fiche:
            FicheTechnique.objects.create(produit=p, type_fiche='module', **fiche)
        return Produit.objects.select_related(
            'categorie', 'fiche_technique').get(pk=p.pk)

    def _etat(self, produit):
        from apps.stock.etat_ci import etat_ci_complet
        return etat_ci_complet(produit)

    def test_sans_pmax(self):
        etat = self._etat(self._panneau(prix=900))
        self.assertEqual(etat['role_ci'], 'panneau')
        self.assertEqual(etat['libelle'], 'Panneau (devis C&I)')
        self.assertFalse(etat['eligible_ci'])
        self.assertEqual(etat['motif_exclusion'],
                         'fiche incomplète : puissance (Pmax)')

    def test_sans_prix(self):
        etat = self._etat(self._panneau(prix=0, pmax_wc=550))
        self.assertFalse(etat['eligible_ci'])
        self.assertFalse(etat['prix_connu'])
        self.assertEqual(etat['motif_exclusion'], 'prix de vente non saisi')

    def test_complet(self):
        etat = self._etat(self._panneau(prix=900, pmax_wc=550))
        self.assertTrue(etat['eligible_ci'])
        self.assertTrue(etat['prix_connu'])
        self.assertIsNone(etat['motif_exclusion'])

    def test_servi_par_l_api_sans_prix_d_achat(self):
        p = self._panneau(prix=0)
        r = api_for(self.user).get(f'{URL_PRODUITS}{p.pk}/')
        self.assertEqual(r.data['etat_ci']['role_ci'], 'panneau')
        self.assertNotIn('prix_achat', r.data['etat_ci'])

    def test_autre_produit_reste_sans_etat(self):
        p = Produit.objects.create(company=self.company, nom='Article',
                                   prix_vente=10)
        self.assertIsNone(self._etat(p))
