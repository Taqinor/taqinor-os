"""CIQ102 — ``stock.selectors.produits_ci`` : UNE lecture serveur du
catalogue C&I (contrat ``contract_samples/produit_ci.json`` →
``element_produits_ci``).
"""
import json
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import produits_ci
from authentication.models import Company

CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_ci.json')
    .read_text(encoding='utf-8'))
CLES = set(CONTRAT['element_produits_ci']['cles'])
INTERDITS = set(CONTRAT['element_produits_ci']['interdit'])


def _cles_recursives(objet):
    if isinstance(objet, dict):
        for k, v in objet.items():
            yield k
            yield from _cles_recursives(v)
    elif isinstance(objet, list):
        for v in objet:
            yield from _cles_recursives(v)


def _fiche_onduleur(company, produit, **surcharges):
    champs = dict(
        type_fiche='onduleur', ond_ac_kw=Decimal('150'), ond_phases=3,
        ond_n_mppt=7, ond_mppt_v_min=Decimal('200'),
        ond_mppt_v_max=Decimal('1000'), ond_v_max_abs=Decimal('1100'),
        ond_i_max_mppt_a=Decimal('48'),
        ond_rendement_euro_pct=Decimal('98.4'))
    champs.update(surcharges)
    return FicheTechnique.objects.create(
        company=company, produit=produit, **champs)


class ProduitsCiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='ciq102-co', defaults={'nom': 'CIQ102 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='ciq102-autre', defaults={'nom': 'CIQ102 Autre'})[0]
        cls.ond_ok = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau Huawei 150kW Triphasé',
            marque='Huawei', role_devis='onduleur_reseau',
            prix_vente=Decimal('80000'), prix_achat=Decimal('60000'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_ok)
        cls.ond_incomplet = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau 100kW Triphasé',
            role_devis='onduleur_reseau', prix_vente=Decimal('60000'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_incomplet,
                        ond_i_max_mppt_a=None)
        cls.ond_sans_prix = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau 50kW Triphasé',
            role_ci='onduleur_string_tri', prix_vente=Decimal('0'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_sans_prix,
                        ond_ac_kw=Decimal('50'))
        cls.structure = Produit.objects.create(
            company=cls.company, nom='Structure bac acier C&I',
            role_devis='structure', role_ci='structure_ci',
            type_pose='bac_acier', prix_vente=Decimal('0'))
        cls.meter = Produit.objects.create(
            company=cls.company, nom='Smart Meter', marque='Huawei',
            role_devis='smart_meter', prix_vente=Decimal('1500'))
        cls.archive = Produit.objects.create(
            company=cls.company, nom='Compteur archivé', role_ci=(
                'compteur_injection'), prix_vente=1, is_archived=True)
        cls.etranger = Produit.objects.create(
            company=cls.autre, nom='Compteur autre société',
            role_ci='compteur_injection', prix_vente=1)
        cls.panneau = Produit.objects.create(
            company=cls.company, nom='Panneau 710W', role_devis='panneau',
            prix_vente=1400)
        # ADEV86 (D-ACI-3=b) — onduleur réseau MONOPHASÉ à fiche complète.
        cls.ond_mono = Produit.objects.create(
            company=cls.company, nom='Onduleur réseau Huawei 10kW Monophasé',
            role_devis='onduleur_reseau', prix_vente=Decimal('12000'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_mono, ond_ac_kw=Decimal('10'),
                        ond_phases=1, ond_n_mppt=2,
                        ond_mppt_v_max=Decimal('550'),
                        ond_v_max_abs=Decimal('600'),
                        ond_i_max_mppt_a=Decimal('20'))
        cls.ond_tri_declare_mono = Produit.objects.create(
            company=cls.company, nom='Onduleur 20kW déclaré mono',
            role_ci='onduleur_string_mono', prix_vente=Decimal('15000'),
            garantie='10 ans')
        _fiche_onduleur(cls.company, cls.ond_tri_declare_mono,
                        ond_ac_kw=Decimal('20'), ond_bat_aucune=True)
        # ADEV87 — câbles solaires DC : fiche côté DC, rôle de devis déclaré,
        # et le câble seedé H1Z2Z2-K sans fiche ni rôle (repli par le nom).
        cls.cable_dc_fiche = Produit.objects.create(
            company=cls.company, nom='Câble DC 6 mm²', prix_vente=Decimal('12'))
        FicheTechnique.objects.create(
            company=cls.company, produit=cls.cable_dc_fiche, type_fiche='cable',
            cable_cote='dc', cable_section_mm2=6)
        cls.cable_dc_role = Produit.objects.create(
            company=cls.company, nom='Câble solaire 4 mm² (au mètre)',
            role_devis='cable_dc', prix_vente=Decimal('10'))
        cls.cable_dc_seed = Produit.objects.create(
            company=cls.company, sku='CAB-H1Z2Z2-6-M',
            nom='Câble solaire Nexans H1Z2Z2-K 6 mm² (au mètre)',
            prix_vente=Decimal('14'))

    def _par_id(self, **kw):
        return {e['id']: e for e in produits_ci(self.company, **kw)}

    def test_forme_du_contrat(self):
        for element in produits_ci(self.company):
            self.assertEqual(set(element), CLES)

    def test_onduleur_complet_eligible_declare_par_fiche(self):
        e = self._par_id()[self.ond_ok.id]
        self.assertEqual(e['role_ci'], 'onduleur_string_tri')
        self.assertEqual(e['classement'], 'fiche')
        self.assertTrue(e['eligible_ci'])
        self.assertIsNone(e['motif_exclusion'])
        self.assertEqual(e['fiche']['type_fiche'], 'onduleur')
        self.assertEqual(e['fiche']['ond_phases'], 3)
        self.assertEqual(e['fiche']['ond_compteurs_compatibles'], [])
        self.assertEqual(e['fiche']['ond_limitation_export'], '')
        self.assertEqual(set(e['fiche']) - {'type_fiche'}, set(
            CONTRAT['fiches']['onduleur']['champs_onduleur_existants'])
            | set(CONTRAT['fiches']['onduleur']['champs']))

    def test_onduleur_monophase_role_mono_eligible(self):
        # ADEV86 — ``ond_phases == 1`` ⇒ rôle ``onduleur_string_mono``, éligible.
        e = self._par_id()[self.ond_mono.id]
        self.assertEqual(e['role_ci'], 'onduleur_string_mono')
        self.assertEqual(e['classement'], 'fiche')
        self.assertTrue(e['eligible_ci'])
        self.assertIsNone(e['motif_exclusion'])
        self.assertEqual(e['fiche']['ond_phases'], 1)

    def test_role_mono_sur_fiche_triphasee_exclu(self):
        e = self._par_id()[self.ond_tri_declare_mono.id]
        self.assertEqual(e['role_ci'], 'onduleur_string_mono')
        self.assertEqual(e['classement'], 'declare')
        self.assertFalse(e['eligible_ci'])
        self.assertIn('fiche à 1 phase', e['motif_exclusion'])

    def test_cable_dc_servi(self):
        # ADEV87 — fiche ``cable_cote='dc'``, ``role_devis='cable_dc'`` ou nom
        # H1Z2Z2-K (seed) ⇒ rôle C&I ``cable_dc``, éligible.
        par_id = self._par_id()
        for produit, classement in ((self.cable_dc_fiche, 'fiche'),
                                    (self.cable_dc_role, 'fiche'),
                                    (self.cable_dc_seed, 'nom')):
            e = par_id[produit.id]
            self.assertEqual(e['role_ci'], 'cable_dc', produit.nom)
            self.assertEqual(e['classement'], classement, produit.nom)
            self.assertTrue(e['eligible_ci'])
        self.assertEqual(par_id[self.cable_dc_fiche.id]['fiche']['cable_cote'], 'dc')

    def test_onduleur_fiche_incomplete_exclu_motif_pvond(self):
        e = self._par_id()[self.ond_incomplet.id]
        self.assertFalse(e['eligible_ci'])
        self.assertIn('courant maxi par MPPT (A)', e['motif_exclusion'])
        self.assertIn('fiche incomplète', e['motif_exclusion'])

    def test_onduleur_sans_prix_exclu(self):
        e = self._par_id()[self.ond_sans_prix.id]
        self.assertEqual(e['classement'], 'declare')
        self.assertFalse(e['eligible_ci'])
        self.assertEqual(e['motif_exclusion'], 'prix de vente non saisi')
        self.assertNotIn(self.ond_sans_prix.id, self._par_id(avec_prix=True))

    def test_structure_sans_prix_reste_eligible(self):
        e = self._par_id()[self.structure.id]
        self.assertFalse(e['prix_connu'])
        self.assertTrue(e['eligible_ci'])
        self.assertEqual(e['type_pose'], 'bac_acier')
        self.assertIsNone(e['fiche'])

    def test_repli_par_le_nom(self):
        e = self._par_id()[self.meter.id]
        self.assertEqual(e['role_ci'], 'compteur_injection')
        self.assertEqual(e['classement'], 'nom')

    def test_bornage_societe_et_archives(self):
        ids = self._par_id()
        self.assertNotIn(self.etranger.id, ids)
        self.assertNotIn(self.archive.id, ids)
        self.assertNotIn(self.panneau.id, ids)  # aucun rôle C&I

    def test_aucun_prix_achat_ni_marge(self):
        cles = set(_cles_recursives(produits_ci(self.company)))
        self.assertFalse(cles & INTERDITS)
        self.assertNotIn('prix_achat', json.dumps(
            produits_ci(self.company), default=str))

    def test_requetes_bornees(self):
        with self.assertNumQueries(1):
            produits_ci(self.company)


# ═══════════════════════════════════════════════════════════════════════════
# CCAT8 — « Prêt pour le devis C&I » (stock.pret_devis_ci + route)
# ═══════════════════════════════════════════════════════════════════════════

CONTRAT_PRET = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'pret_devis_ci.json')
    .read_text(encoding='utf-8'))
POSTE_EXEMPLE = CONTRAT_PRET['exemple']['postes'][0]
PRESTATIONS_CI = (
    'etudes_ingenierie', 'pose_structure', 'pose_modules', 'raccordement_ac',
    'mise_en_service', 'dossier_raccordement', 'levage_acces', 'transport_ci')
FORFAIT = {'fixe_ht': '1000', 'source': 'devis fournisseur 10/2026'}
URL_PRET = '/api/django/stock/produits/pret-devis-ci/'


class PretDevisCiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        from apps.parametres.models import CompanyProfile
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        cls.company = Company.objects.get_or_create(
            slug='ccat8-co', defaults={'nom': 'CCAT8 Co'})[0]
        cls.autre = Company.objects.get_or_create(
            slug='ccat8-autre', defaults={'nom': 'CCAT8 Autre'})[0]
        roles = {nom: Role.objects.create(
            company=cls.company, nom=nom, permissions=list(perms),
            est_systeme=True) for nom, perms in CANONICAL_SYSTEM_ROLES}
        cls.user = get_user_model().objects.create_user(
            username='ccat8_dir', password='x', company=cls.company,
            role=roles['Directeur'])
        CompanyProfile.objects.update_or_create(
            company=cls.company,
            defaults={'forfaits_ci': {c: dict(FORFAIT) for c in PRESTATIONS_CI}})
        # Un catalogue VOLONTAIREMENT incomplet (cas du plan).
        cls.coffret_ac = Produit.objects.create(
            company=cls.company, nom='Coffret AC C&I', role_ci='coffret_ac',
            prix_vente=0)
        cls.structure_bac = Produit.objects.create(
            company=cls.company, nom='Structure bac acier', role_ci='structure_ci',
            type_pose='bac_acier', prix_vente=Decimal('100'))
        cls.pose_archivee = Produit.objects.create(
            company=cls.company, nom='Pose des modules', sku='CI-POSE-MOD',
            role_ci='pose_modules', prix_vente=Decimal('100'),
            is_archived=True)
        for cle in PRESTATIONS_CI:
            if cle != 'pose_modules':
                Produit.objects.create(
                    company=cls.company, nom='Article ' + cle, role_ci=cle,
                    prix_vente=Decimal('100'))
        cls.dyness = Produit.objects.create(
            company=cls.company, nom='Batterie Dyness 10 kWh',
            role_devis='batterie', prix_vente=Decimal('5000'))
        # Une autre société : ses articles ne doivent jamais apparaître.
        cls.etranger = Produit.objects.create(
            company=cls.autre, nom='Coffret AC autre société',
            role_ci='coffret_ac', prix_vente=Decimal('10'))

    def _postes(self, company=None):
        from apps.stock.pret_devis_ci import pret_devis_ci
        res = pret_devis_ci(company or self.company)
        return res, {p['cle']: p for p in res['postes']}

    def test_cas_du_plan(self):
        res, postes = self._postes()
        self.assertFalse(res['pret'])
        self.assertEqual(postes['structure_ci:toit_plat_leste']['statut'],
                         'absent')
        coffret = postes['coffret_ac']
        self.assertEqual(coffret['statut'], 'a_completer')
        self.assertEqual(coffret['articles'], [{
            'id': self.coffret_ac.id, 'nom': 'Coffret AC C&I',
            'motif': 'prix de vente non saisi'}])
        self.assertEqual(coffret['action']['lien'], '/stock?ci=a_completer')
        forfait = postes['forfait:pose_modules']
        self.assertEqual(forfait['statut'], 'a_completer')
        self.assertEqual(forfait['articles'], [])
        self.assertIn("Créer l'article « Pose des modules »",
                      forfait['action']['texte'])
        self.assertEqual(postes['forfait:transport_ci']['statut'], 'ok')
        batterie = postes['option_batterie:batterie']
        self.assertEqual(batterie['statut'], 'a_completer')
        self.assertEqual(batterie['articles'][0]['id'], self.dyness.id)
        self.assertIn('fiche incomplète', batterie['articles'][0]['motif'])
        # la structure d'un autre type de pose existe mais ne remplace pas le
        # défaut obligatoire (toit plat lesté)
        self.assertEqual(postes['structure_ci:bac_acier']['statut'], 'ok')
        self.assertFalse(postes['structure_ci:bac_acier']['obligatoire'])

    def test_forfait_non_regle_est_absent(self):
        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.filter(company=self.company).update(
            forfaits_ci={'pose_structure': dict(FORFAIT)})
        _res, postes = self._postes()
        self.assertEqual(postes['forfait:transport_ci']['statut'], 'absent')
        self.assertEqual(postes['forfait:transport_ci']['action']['lien'],
                         '/parametres?onglet=devis#prestations-ci')
        self.assertEqual(postes['forfait:pose_structure']['statut'], 'ok')

    def test_decompte_des_obligatoires_manquants(self):
        res, postes = self._postes()
        manquants = [c for c, p in postes.items()
                     if p['obligatoire'] and p['statut'] != 'ok']
        self.assertEqual(res['nb_obligatoires_manquants'], len(manquants))
        self.assertIn('panneau', manquants)
        self.assertIn('forfait:pose_modules', manquants)

    def test_isolation_societe(self):
        res, postes = self._postes()
        ids = {a['id'] for p in res['postes'] for a in p['articles']}
        self.assertNotIn(self.etranger.id, ids)
        _res, autre = self._postes(self.autre)
        self.assertEqual(autre['coffret_ac']['statut'], 'ok')
        self.assertNotIn(self.coffret_ac.id, {
            a['id'] for p in autre.values() for a in p['articles']})
        self.assertEqual(autre['forfait:pose_modules']['statut'], 'absent')

    def test_forme_du_contrat_et_aucune_cle_de_prix(self):
        res, _postes = self._postes()
        self.assertEqual(set(res), set(CONTRAT_PRET['exemple']))
        for poste in res['postes']:
            self.assertEqual(set(poste), set(POSTE_EXEMPLE))
            self.assertEqual(set(poste['action']), {'texte', 'lien'})
            self.assertIn(poste['statut'], ('ok', 'a_completer', 'absent'))
            self.assertIn(poste['groupe'], (
                'materiel', 'prestation', 'option', 'option_batterie'))
            for article in poste['articles']:
                self.assertEqual(set(article), {'id', 'nom', 'motif'})
        cles = {c.lower() for c in _cles_recursives(res)}
        self.assertFalse([c for c in cles if 'prix' in c or 'marge' in c])
        self.assertNotIn('prix_achat', json.dumps(res, default=str))

    def test_catalogue_complet_est_pret(self):
        from apps.parametres.models import CompanyProfile
        co = self.autre
        CompanyProfile.objects.update_or_create(
            company=co,
            defaults={'forfaits_ci': {c: dict(FORFAIT) for c in PRESTATIONS_CI}})
        for cle in PRESTATIONS_CI:
            Produit.objects.create(company=co, nom='Art ' + cle, role_ci=cle,
                                   prix_vente=Decimal('100'))
        panneau = Produit.objects.create(
            company=co, nom='Panneau 550W', role_devis='panneau',
            prix_vente=Decimal('900'))
        FicheTechnique.objects.create(
            company=co, produit=panneau, type_fiche='module', pmax_wc=550)
        ond = Produit.objects.create(
            company=co, nom='Onduleur réseau Huawei 150kW Triphasé',
            role_devis='onduleur_reseau', prix_vente=Decimal('80000'),
            garantie='10 ans')
        _fiche_onduleur(co, ond)
        disjoncteur = Produit.objects.create(
            company=co, nom='Disjoncteur 250A', role_ci='protection_ac',
            prix_vente=Decimal('300'))
        FicheTechnique.objects.create(
            company=co, produit=disjoncteur, type_fiche='protection',
            prot_type='disjoncteur', prot_cote='ac', prot_calibre_a=250)
        cable_ac = Produit.objects.create(
            company=co, nom='Câble AC 95 mm²', role_ci='cable_ac',
            prix_vente=Decimal('50'))
        FicheTechnique.objects.create(
            company=co, produit=cable_ac, type_fiche='cable', cable_cote='ac',
            cable_section_mm2=95)
        for role, nom in (('coffret_dc', 'Coffret DC'), ('coffret_ac', 'Coffret AC'),
                          ('cable_dc', 'Câble DC'),
                          ('compteur_injection', 'Compteur')):
            Produit.objects.create(company=co, nom=nom, role_ci=role,
                                   prix_vente=Decimal('50'))
        Produit.objects.create(
            company=co, nom='Structure toit plat lesté', role_ci='structure_ci',
            type_pose='toit_plat_leste', prix_vente=Decimal('50'))
        res, postes = self._postes(co)
        obligatoires = {c: p['statut'] for c, p in postes.items()
                        if p['obligatoire']}
        self.assertEqual(
            {c: s for c, s in obligatoires.items() if s != 'ok'}, {})
        self.assertTrue(res['pret'])
        self.assertEqual(res['nb_obligatoires_manquants'], 0)

    def test_disjoncteur_sans_calibre_et_cable_sans_section_a_completer(self):
        # Revue R3 — le moteur n'apparie que par calibre / section : sans
        # cette grandeur l'article n'est jamais composé, le poste reste ouvert.
        co = self.company
        Produit.objects.create(company=co, nom='Câble AC sans fiche',
                               role_ci='cable_ac', prix_vente=Decimal('50'))
        d = Produit.objects.create(company=co, nom='Disjoncteur sans calibre',
                                   role_ci='protection_ac', prix_vente=Decimal('300'))
        FicheTechnique.objects.create(company=co, produit=d, type_fiche='protection',
                                      prot_type='disjoncteur', prot_cote='ac')
        _res, postes = self._postes(co)
        self.assertEqual(postes['protection_ac']['statut'], 'a_completer')
        self.assertEqual(postes['protection_ac']['articles'][0]['motif'],
                         'fiche incomplète : calibre (A)')
        self.assertEqual(postes['cable_ac']['statut'], 'a_completer')
        self.assertEqual(postes['cable_ac']['articles'][0]['motif'],
                         'fiche incomplète : section (mm²)')

    def test_route_api(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        r = client.get(URL_PRET)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), set(CONTRAT_PRET['exemple']))
        self.assertFalse(r.json()['pret'])
        self.assertNotIn('prix_achat', json.dumps(r.json()))
        self.assertEqual(APIClient().get(URL_PRET).status_code, 401)
