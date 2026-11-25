"""CALX244 — l'action ``raccordement`` (contrat CALX205), en HTTP.

Ce qui est prouvé ici :

* ``GET`` répond 200 avec les TROIS blocs du contrat et les CINQ verdicts,
  même sur un calepinage nu — l'état ``exemple_vide`` ;
* ``POST`` enregistre la saisie dans ``Calepinage.resultat`` (JSONField
  existant, aucune migration) et REND le raccordement recalculé : aucun
  second appel à enchaîner ;
* un ``GET`` qui suit un ``POST`` republie la MÊME saisie — c'est ce qui
  distingue une saisie persistée d'un aller-retour sans mémoire ;
* une limite d'élévation SANS sa source est refusée 400 en NOMMANT
  ``source_limite`` — le nom NU que le contrat CALX205 fige dans
  ``refus_limite_sans_source`` ; idem pour le cos φ et pour un régime de
  branchement hors 1/3 (règle fondateur : l'erreur désigne le champ) ;
* la saisie refusée n'entre PAS en base : un refus ne laisse aucune trace ;
* les clés inconnues du corps sont ignorées — le contrat fige sept champs ;
* sans ``calepinage_gerer``, le ``POST`` répond 403 alors que le ``GET``
  passe (garde ``PeutLireOuEcrireCalepinage``, CAL18) ;
* un calepinage d'une AUTRE société est INTROUVABLE (404), jamais
  « interdit » ;
* AUCUNE clé d'argent ne sort de la réponse (D-CALX 5).

Ces tests ont besoin de l'ORM : ils NE PEUVENT PAS être exécutés sur un
poste sans base (aucun docker, aucun PostgreSQL). La CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_api_raccordement -v2
"""
import re

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.permissions import CAL_VOIR
from apps.calepinage.views.raccordement import CLE_SAISIE
from apps.roles.models import Role

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_calx205_contrat_raccordement import RACCORDEMENT

User = get_user_model()

#: Les cinq contrôles, dans l'ordre où le contrat CALX205 les publie.
CODES = ['elevation_tension', 'puissance_souscrite', 'regime_phases',
         'tension_nominale', 'desequilibre_phases',
         'limitation_injection']  # ACAL1187 : le sixième

#: Les mots d'argent qui n'ont rien à faire dans une pièce électrique.
HORS_SUJET = ('prix', 'montant', 'mad', 'tva', 'remise')


def url_raccordement(pk):
    return f'{url_detail(pk)}raccordement/'


class RefusSaisieRaccordementTest(SimpleTestCase):
    """R3-14 — un refus de saisie nomme le champ par son intitulé FRANÇAIS,
    majuscule initiale seule (``capitalize`` écrivait « (kva) », « (kw) »)."""

    def _refus(self, fonction, champ, valeur):
        from apps.calepinage.services import raccordement

        with self.assertRaises(raccordement.RaccordementInvalide) as ctx:
            getattr(raccordement, fonction)(valeur, champ)
        return str(ctx.exception)

    def test_unites_gardent_leur_casse(self):
        for fonction, champ, valeur, attendu in (
                ('_nombre_saisi', 'puissance_souscrite_kva', -3,
                 'La puissance souscrite (kVA)'),
                ('_nombre_saisi', 'tension_nominale_v', 'abc',
                 'La tension nominale (V)'),
                ('_plafond_saisi', 'plafond_injection_kw', -1,
                 "Le plafond d'injection (kW)")):
            self.assertIn(attendu, self._refus(fonction, champ, valeur))

    def test_aucune_cle_technique_dans_les_phrases(self):
        for fonction, champ, valeur in (
                ('_nombre_saisi', 'puissance_souscrite_kva', 0),
                ('_nombre_saisi', 'tension_nominale_v', 1e300),
                ('_plafond_saisi', 'plafond_injection_a', 'x')):
            self.assertIsNone(re.search(
                r'[a-z]+_[a-z_]+', self._refus(fonction, champ, valeur)))


class RaisonCourteDuVerdictTest(SimpleTestCase):
    """T4-X9-002 — liste « Onduleur » : « Courant par entrée MPPT sous le courant admissible (18,6 A
    au-dessus de la borne de fiche 18,0 A) » disait « sous » puis « au-dessus » du même fait. Le
    verdict garde son libellé et son détail (l'installateur) et sert ``raison`` : le fait, son sens,
    sans sigle — la clé que lit la raison courte de la liste."""

    def test_le_courant_qui_depasse_est_dit_dans_son_sens(self):
        from apps.calepinage.services.electrique import VERDICTS_DE_CHAINE, _verdict

        libelle = dict(VERDICTS_DE_CHAINE)['courant_par_entree_mppt']
        echec = _verdict('courant_par_entree_mppt', libelle, 18.6, 18.0, 'sous', bloquant=True, unite='A')
        self.assertEqual(echec['raison'], 'le courant des panneaux (18,6 A) dépasse ce qu’une entrée de cet '
                                          'onduleur accepte (18,0 A)')
        self.assertEqual((echec['libelle'], echec['detail']), (libelle, '18,6 A au-dessus de la borne de fiche 18,0 A'))
        self.assertNotIn('MPPT', echec['raison'])
        passe = _verdict('courant_par_entree_mppt', libelle, 17.0, 18.0, 'sous', bloquant=True, unite='A')
        self.assertIsNone(passe['raison'])
        self.assertEqual(passe['detail'], '17,0 A sous 18,0 A')

    def test_la_tension_trop_basse_par_chaleur_dit_sous(self):
        from apps.calepinage.services.electrique import _verdict

        echec = _verdict('vmp_hot_over_mppt_min', 'x', 141.4, 150.0, 'au-dessus', bloquant=False, unite='V')
        self.assertIn('tombe sous la plage de travail de cet onduleur (150,0 V)', echec['raison'])
        self.assertIsNone(_verdict('vmp_hot_over_mppt_min', 'x', 141.4, None, 'au-dessus', bloquant=False,
                                   unite='V')['raison'])


class ActionRaccordementTest(BaseApiCalepinage):
    """La porte HTTP du point de raccordement réseau."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')

    def _utilisateur_lecteur(self):
        """Un compte qui VOIT les calepinages, et rien de plus."""
        role = Role.objects.create(company=self.company, nom='Lecteur CALX244',
                                   permissions=[CAL_VOIR])
        return User.objects.create_user(
            username='calx244_lecteur', password='x', company=self.company,
            role=role)

    # ── Lecture ──────────────────────────────────────────────────────────
    def test_get_rend_les_trois_blocs(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 200, reponse.data)
        # Les blocs du contrat (ACAL782/783 : + regime, injection,
        # injection_motif).
        self.assertEqual(sorted(reponse.data),
                         sorted(RACCORDEMENT['exemple']))

    def test_get_rend_toujours_les_six_verdicts(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        self.assertEqual([v['code'] for v in reponse.data['verdicts']],
                         CODES)

    def test_sans_saisie_chaque_verdict_est_omis_et_dit_pourquoi(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        for verdict in reponse.data['verdicts']:
            with self.subTest(code=verdict['code']):
                self.assertEqual(verdict['statut'], 'omis')
                self.assertTrue(verdict['detail'].strip())

    def test_aucune_grandeur_n_est_publiee_a_zero(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        for champ, valeur in reponse.data['calcul'].items():
            with self.subTest(champ=champ):
                self.assertIsNone(valeur)

    # ── Écriture ─────────────────────────────────────────────────────────
    def test_post_enregistre_et_republie(self):
        reponse = self.api.post(
            url_raccordement(self.calepinage.pk),
            {'puissance_souscrite_kva': 12, 'phases': 3,
             'tension_nominale_v': 400},
            format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['saisie']['puissance_souscrite_kva'],
                         12.0)
        self.calepinage.refresh_from_db()
        self.assertEqual(
            self.calepinage.resultat[CLE_SAISIE]['tension_nominale_v'],
            400.0)

    def test_bornes_publiees_ENF11(self):
        """Strictement positif (0 et négatif refusés) ; plafond >= 0."""
        for champ in ('puissance_souscrite_kva', 'tension_nominale_v',
                      'limite_elevation_pct', 'cos_phi_impose'):
            for valeur in (0, -1):
                with self.subTest(champ=champ, valeur=valeur):
                    reponse = self.api.post(
                        url_raccordement(self.calepinage.pk),
                        {champ: valeur}, format='json')
                    self.assertEqual(reponse.status_code, 400)
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'plafond_injection_kw': -1}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_la_saisie_survit_au_get_suivant(self):
        self.api.post(url_raccordement(self.calepinage.pk),
                      {'phases': 1, 'tension_nominale_v': 230},
                      format='json')

        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.data['saisie']['phases'], 1)
        self.assertEqual(reponse.data['saisie']['tension_nominale_v'], 230.0)

    def test_une_cle_inconnue_n_entre_pas_en_base(self):
        self.api.post(url_raccordement(self.calepinage.pk),
                      {'phases': 3, 'numero_compteur': 'X1'}, format='json')

        self.calepinage.refresh_from_db()
        self.assertNotIn('numero_compteur',
                         self.calepinage.resultat[CLE_SAISIE])

    def test_le_post_n_ecrase_pas_le_reste_du_resultat(self):
        self.calepinage.resultat = {'sld_edition': {'libelles': {}}}
        self.calepinage.save(update_fields=['resultat'])

        self.api.post(url_raccordement(self.calepinage.pk), {'phases': 3},
                      format='json')

        self.calepinage.refresh_from_db()
        self.assertIn('sld_edition', self.calepinage.resultat)

    # ── Refus : le champ fautif est NOMMÉ ────────────────────────────────
    def test_limite_sans_source_est_refusee_en_nommant_le_champ(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'limite_elevation_pct': 3}, format='json')

        # ENF11 : règle liant deux champs (valeur sans source) = 409.
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('source_limite', reponse.data)

    def test_cos_phi_sans_source_est_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'cos_phi_impose': 0.9}, format='json')

        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('source_cos_phi', reponse.data)

    def test_plafond_sans_justification_409_et_nul_400(self):
        """ENF11 (fuzz 01/11) : plafond sans justification = 409 ; un NUL dans
        une provenance = 400 nommé (était un 500 au rangement JSONB)."""
        url = url_raccordement(self.calepinage.pk)
        reponse = self.api.post(url, {'plafond_injection_kw': 3},
                                format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('plafond_injection_justification', reponse.data)
        reponse = self.api.post(
            url, {'plafond_injection_kw': 3,
                  'plafond_injection_justification': 'a\x00b'},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('plafond_injection_justification', reponse.data)

    def test_un_regime_hors_1_et_3_est_refuse(self):
        reponse = self.api.post(url_raccordement(self.calepinage.pk),
                                {'phases': 2}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('phases', reponse.data)

    def test_phases_publie_1_ou_3_au_schema(self):
        # ENF11 — la règle de ``_phases_saisies`` est publiée (enum 1|3, vide
        # permis) : le fuzz n'envoie plus un régime que le serveur refuse.
        from django.urls import include, path
        from drf_spectacular.generators import SchemaGenerator

        from apps.calepinage import urls as calepinage_urls

        schema = SchemaGenerator(patterns=[
            path('api/django/calepinage/', include(calepinage_urls)),
        ]).get_schema(request=None, public=True)
        corps = schema['paths'][
            '/api/django/calepinage/calepinages/{id}/raccordement/']['post'][
            'requestBody']['content']['application/json']['schema']
        nom = corps['$ref'].rsplit('/', 1)[-1]
        phases = schema['components']['schemas'][nom]['properties']['phases']
        composants = schema['components']['schemas']

        def valeurs_enum(noeud):
            # La forme dépend du post-traitement des enums (``$ref`` direct,
            # ``allOf``/``oneOf`` + NullEnum, ``enum`` en ligne) : on la
            # parcourt jusqu'à trouver les valeurs.
            if '$ref' in noeud:
                return valeurs_enum(composants[noeud['$ref'].rsplit('/', 1)[-1]])
            trouvees = list(noeud.get('enum') or [])
            for cle in ('allOf', 'oneOf', 'anyOf'):
                for sous in noeud.get(cle, []):
                    trouvees += valeurs_enum(sous)
            return trouvees

        enum = valeurs_enum(phases)
        self.assertEqual(sorted(v for v in enum if v is not None
                                and v != ''), [1, 3])

    def test_un_refus_ne_laisse_aucune_trace_en_base(self):
        self.api.post(url_raccordement(self.calepinage.pk),
                      {'limite_elevation_pct': 3}, format='json')

        self.calepinage.refresh_from_db()
        self.assertNotIn(CLE_SAISIE, self.calepinage.resultat or {})

    # ── Droits et société ────────────────────────────────────────────────
    def test_le_lecteur_lit_mais_n_ecrit_pas(self):
        """CAL18 — la garde choisit son code par la MÉTHODE, pas par la
        classe."""
        api_lecteur = self._client(self._utilisateur_lecteur())

        lecture = api_lecteur.get(url_raccordement(self.calepinage.pk))
        ecriture = api_lecteur.post(url_raccordement(self.calepinage.pk),
                                    {'phases': 3}, format='json')

        self.assertEqual(lecture.status_code, 200, lecture.data)
        self.assertEqual(ecriture.status_code, 403, ecriture.data)

    def test_sans_aucun_droit_calepinage_la_lecture_est_refusee(self):
        reponse = self.api_sans.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 403, reponse.data)

    def test_un_calepinage_d_une_autre_societe_est_introuvable(self):
        reponse = self.api_autre.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 404, reponse.data)

    def test_le_post_d_une_autre_societe_est_introuvable(self):
        reponse = self.api_autre.post(url_raccordement(self.calepinage.pk),
                                      {'phases': 3}, format='json')

        self.assertEqual(reponse.status_code, 404, reponse.data)

    # ── Hors sujet ───────────────────────────────────────────────────────
    def test_aucun_mot_d_argent_dans_la_reponse(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))
        texte = str(reponse.data).lower()

        for mot in HORS_SUJET:
            with self.subTest(mot=mot):
                self.assertIsNone(
                    re.search(r'\b%s\b' % mot, texte),
                    "Le calepinage ne calcule aucun argent (D-CALX 5).")


class PhasesDeSaisiesElectriquesLuesTest(BaseApiCalepinage):
    """ACAL1512 — l'onglet Raccordement lit les phases de « Saisies
    électriques » comme ``evaluer-electrique`` (``_phases_du_raccordement``),
    sans les recopier dans sa propre saisie."""

    def setUp(self):
        super().setUp()
        from decimal import Decimal

        from apps.calepinage.services.electrique import CLE_ENTREE
        from apps.stock.models import FicheTechnique, Produit

        produits = {}
        for nom, type_fiche, fiche in (
                ('Module 710', 'module', dict(
                    vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59,
                    pmax_wc=710.0)),
                ('Onduleur 10 kW tri', 'onduleur', dict(
                    ond_n_mppt=2, ond_mppt_v_min=160.0, ond_mppt_v_max=950.0,
                    ond_v_max_abs=1100.0, ond_i_max_mppt_a=26.0,
                    ond_ac_kw=10.0, ond_phases=3))):
            produit = Produit.objects.create(
                company=self.company, nom=nom, sku=f'ACAL1512-{nom}',
                prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
                quantite_stock=1)
            FicheTechnique.objects.create(company=self.company,
                                          produit=produit,
                                          type_fiche=type_fiche, **fiche)
            produits[type_fiche] = produit.pk
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa 1992',
            roof_layout={'pin': {'lat': 33.57, 'lng': -7.59},
                         'zones': [{'id': 'z1', 'label': 'Sud',
                                    'result': {'count': 12},
                                    'facingAzimuthDeg': 180.0,
                                    'pitchDeg': 15.0}]},
            resultat={CLE_ENTREE: {
                'module_produit': produits['module'],
                'onduleur_produit': produits['onduleur'],
                'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
                'phases': 1}})

    def test_phases_de_saisies_electriques_lues_par_le_raccordement(self):
        reponse = self.api.get(url_raccordement(self.calepinage.pk))

        self.assertEqual(reponse.status_code, 200, reponse.data)
        regime, = [v for v in reponse.data['verdicts']
                   if v['code'] == 'regime_phases']
        self.assertEqual(regime['statut'], 'bloquant', regime)
        self.assertEqual(regime['source'],
                         'saisie — phases (Saisies électriques)')
        # Lue, jamais recopiée : la saisie de l'écran reste vide.
        self.assertIsNone(reponse.data['saisie']['phases'])
        self.calepinage.refresh_from_db()
        self.assertNotIn(CLE_SAISIE, self.calepinage.resultat)
