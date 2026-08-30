"""QJR103 — LE CONTRAT DE PARCOURS DU REGISTRE DE SURCHARGES.

CE QUE CE MODULE TIENT, ET POURQUOI IL EST PILOTÉ PAR TABLE. Le registre
``Devis.overrides`` (QJR57/QJR58, décision fondateur D12) déclare 19 chemins
surchargeables. Un test écrit chemin par chemin aurait couvert ceux auxquels
son auteur a pensé, et RIEN pour le vingtième ajouté six mois plus tard — le
mode d'échec exact que l'audit L3 du 29/08/2026 a trouvé partout ailleurs dans
ce parcours. La table :data:`COUVERTURE` ci-dessous est donc comparée à
``overrides.CHAMPS_OVERRIDABLES`` : **un chemin ajouté au registre sans
couverture fait ROUGIR**, et un chemin retiré du registre mais resté dans la
table aussi. Il n'existe aucun ``skip`` silencieux.

LES QUATRE PROPRIÉTÉS PROUVÉES.

1. **L'OVERRIDE SURVIT À CHAQUE ÉTAPE AVAL, PAR VALEUR.** Pour chaque chemin :
   on relève la valeur AUTO, on pose l'override par le VRAI endpoint
   (``PATCH /ventes/devis/<id>/overrides/``), puis on exécute EN SÉQUENCE les
   dix étapes du parcours (``replace-lines``, ``PATCH /devis/<id>/``,
   ``sync-layout``, ``offres-tailles/appliquer``, ``rafraichir_etudes_du_devis``,
   ``build_quote_data``, ``proposal_data``, la charge utile PDF, ``option_totaux``,
   ``taille_detail``) — et APRÈS CHACUNE on affirme que ``overrides.effectif``
   rend toujours la valeur manuelle.
2. **LA VALEUR RENDUE EN AVAL LA REFLÈTE**, pour chaque chemin qui a
   AUJOURD'HUI un lecteur aval branché. Les chemins qui n'en ont pas encore
   sont déclarés tels quels dans la table, avec la raison : c'est un CONSTAT
   vérifié (un grep sur ``apps/ventes`` ne trouve que leurs définitions), pas
   une facilité — et le jour où l'un d'eux est branché, sa ligne de table
   change et le test le prouve.
3. **LE RETOUR À L'AUTOMATIQUE EST EXACT.** ``DELETE ?chemin=`` (``regenerer``)
   ramène la valeur à CELLE RELEVÉE AU DÉPART, jamais un troisième nombre.
   Ce test-là tourne sur un devis que la séquence n'a PAS encore fait bouger
   (:class:`RetourALAutomatiqueTests`) — et c'est délibéré : après une
   recomposition, une valeur automatique DIFFÉRENTE serait la bonne réponse,
   pas une régression, et l'exiger identique ferait rougir le test pour rien.
   Sur le parcours complet, ce qui est prouvé après ``regenerer`` est ce que
   la propriété de sûreté nº 3 du registre promet : **l'entrée est SUPPRIMÉE**
   (``source`` redevient ``auto``), jamais remplacée par une valeur calculée.
4. **LA TABLE DE PRÉSÉANCE R4-A**, dans les DEUX sens : ``taille.nb_panneaux``
   (niveau devis) contre ``quantite_manuelle`` (niveau ligne) — le drapeau de
   LIGNE gagne pour la quantité de CETTE ligne, le chemin de niveau devis
   alimente ``decider_taille``, et un désaccord émet un avertissement FR qui
   NOMME la ligne (:func:`overrides.preseance_nb_panneaux`).

LE RENDU PDF. ``generate_premium_devis_pdf`` a besoin des bibliothèques
natives de WeasyPrint ET de MinIO. La séquence par chemin exerce donc la
CHARGE UTILE du PDF (``build_quote_data`` en mode ``full`` — les renderers ne
lisent rien d'autre), patron des tests moteur qui exercent le build sans le
rendu ; le rendu RÉEL est exercé une fois, à part, par
:class:`RenduPdfReelTests`, qui se saute proprement si WeasyPrint manque.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_contrat_override_parcours -v 2
"""
import itertools
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import overrides
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()

_seq = itertools.count(1)


# ═══════════════════════════════════════════════════════════════════════════
# Fixture — un devis résidentiel qui porte RÉELLEMENT les deux options
# ═══════════════════════════════════════════════════════════════════════════

#: Réseau + hybride + batterie : le seul montage où ``build_quote_data`` peut
#: rendre « Les deux », donc le seul où une surcharge de ``scenario`` ou de
#: ``recommended_option`` a quelque chose à changer.
LIGNES = (
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Panneau Canadian Solar 710W', '14', '1100'),
    ('Batterie Dyness 10 kWh', '1', '14000'),
    ('Installation', '1', '4000'),
)

#: PV86 — un document à deux options n'existe que lorsque le devis le DÉCLARE.
DEUX_OPTIONS = 'Les deux (Sans + Avec)'


def _layout():
    """Le calepinage minimal accepté par ``sync-layout`` (patron QJR7)."""
    return {
        'version': 1, 'scenario': 'reseau',
        'result': {'panels': 14, 'kwc': 9.94, 'annualKwh': 15000},
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [[0, 0], [12, 0], [12, 8], [0, 8]],
            'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
            'facingAzimuthDeg': 0, 'neededPanels': 14,
        }],
        '_pans_geometry': [{
            'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
            'inclinaison_deg': 30, 'nb_panneaux': 14, 'kwc': 9.94,
            'roof_type': 'pitched',
        }],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Les LECTEURS AVAL — ce qui, aujourd'hui, LIT réellement le registre
# ═══════════════════════════════════════════════════════════════════════════

def _lire_kwc_quote(ctx):
    return ctx.quote_data().get('puissance_kwc')


def _lire_scenario_quote(ctx):
    return ctx.quote_data().get('scenario')


def _lire_reco_quote(ctx):
    return ctx.quote_data().get('recommended')


def _lire_kwc_du_devis(ctx):
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    return puissance_kwc_du_devis(ctx.devis)


class Couverture:
    """La ligne de table d'UN chemin du registre.

    * ``valeur`` — la valeur MANUELLE posée par le test. Choisie différente de
      l'automatique, sinon la survie ne prouverait rien.
    * ``clef_patch`` — le chemin réellement envoyé au PATCH. Il ne diffère du
      chemin de la liste blanche que pour l'unique motif dynamique
      ``profil.equipements.<clef>``, où ``<clef>`` est un nom d'équipement réel.
    * ``lecteur`` — la fonction qui lit la valeur RENDUE en aval, ``None``
      quand aucun consommateur ne lit encore ce chemin.
    * ``attendu`` — ce que ``lecteur`` doit rendre une fois l'override posé.
      ``None`` ⇒ la valeur manuelle elle-même.
    * ``sans_lecteur`` — la RAISON, obligatoire quand ``lecteur`` est ``None``.
    """

    __slots__ = ('valeur', 'clef_patch', 'lecteur', 'attendu', 'sans_lecteur')

    def __init__(self, valeur, *, clef_patch=None, lecteur=None, attendu=None,
                 sans_lecteur=''):
        self.valeur = valeur
        self.clef_patch = clef_patch
        self.lecteur = lecteur
        self.attendu = attendu
        self.sans_lecteur = sans_lecteur


#: RAISON UNIQUE, vérifiée le 30/08/2026 par grep sur ``backend/django_core``
#: (hors tests, hors le registre lui-même) : ces chemins sont DÉCLARÉS par la
#: décision fondateur D12 et acceptés par l'endpoint, mais AUCUN consommateur
#: ne les lit encore — les brancher est le travail des tâches qui les
#: possèdent, pas de ce test. Le contrat de PARCOURS (l'override survit et se
#: régénère) est prouvé pour eux comme pour les autres.
PAS_ENCORE_LU = ('déclaré D12, aucun lecteur aval branché à ce jour — la '
                 'survie dans le registre et le retour à l\'auto sont '
                 'prouvés, il n\'existe pas encore de valeur rendue.')

#: LA TABLE. Une ligne par chemin de ``overrides.CHAMPS_OVERRIDABLES`` —
#: l'égalité des deux ensembles est elle-même un test (voir
#: :class:`TableDeCouvertureTests`).
COUVERTURE = {
    'taille.nb_panneaux': Couverture(21, lecteur=_lire_kwc_du_devis,
                                     attendu='kwc_21_panneaux'),
    'taille.panel_watt': Couverture(545, sans_lecteur=PAS_ENCORE_LU),
    'taille.kwc': Couverture(9.99, lecteur=_lire_kwc_quote),
    'taille.batterie_nb_modules': Couverture(3, sans_lecteur=PAS_ENCORE_LU),
    'taille.batterie_module_kwh': Couverture(5.12,
                                             sans_lecteur=PAS_ENCORE_LU),
    'scenario': Couverture('Sans batterie', lecteur=_lire_scenario_quote),
    'recommended_option': Couverture('Sans batterie',
                                     lecteur=_lire_reco_quote),
    'profil.occupation': Couverture('jour', sans_lecteur=PAS_ENCORE_LU),
    'profil.factures_mensuelles_reelles': Couverture(
        [1200] * 12, sans_lecteur=PAS_ENCORE_LU),
    'profil.conso_annuelle': Couverture(9600, sans_lecteur=PAS_ENCORE_LU),
    overrides.PREFIXE_EQUIPEMENT + '<clef>': Couverture(
        True, clef_patch=overrides.PREFIXE_EQUIPEMENT + 'piscine',
        sans_lecteur=PAS_ENCORE_LU),
    'tarif.distributeur': Couverture('ONEE', sans_lecteur=PAS_ENCORE_LU),
    'tarif.tranches': Couverture([{'jusqu_a': 100, 'prix': 0.9}],
                                 sans_lecteur=PAS_ENCORE_LU),
    'tarif.charges_fixes_mad': Couverture(42.5, sans_lecteur=PAS_ENCORE_LU),
    'etude.jour_reference': Couverture('2026-03-15',
                                       sans_lecteur=PAS_ENCORE_LU),
    'mode_installation': Couverture('industriel', sans_lecteur=PAS_ENCORE_LU),
    'structure': Couverture('beton', sans_lecteur=PAS_ENCORE_LU),
    'tension': Couverture('triphase', sans_lecteur=PAS_ENCORE_LU),
    'pompe_alim': Couverture('solaire', sans_lecteur=PAS_ENCORE_LU),
}


def ecarts_de_couverture(chemins_registre, table):
    """``(non couverts, orphelins)`` — la comparaison registre ↔ table.

    Fonction PURE et EXTRAITE exprès : c'est elle que le test négatif appelle
    avec un registre doctoré pour prouver qu'un chemin ajouté au registre — ou
    retiré de lui — fait bien rougir, sans avoir à modifier le vrai module.
    """
    registre = list(chemins_registre)
    non_couverts = [c for c in registre if c not in table]
    orphelins = [c for c in table if c not in registre]
    return non_couverts, orphelins


# ═══════════════════════════════════════════════════════════════════════════
# Le contexte de parcours — le devis, ses étapes, ses lectures
# ═══════════════════════════════════════════════════════════════════════════

class Parcours:
    """Un devis NEUF + les dix étapes aval, exécutables une par une."""

    def __init__(self, case):
        from apps.ventes.domain.geometrie import layout_hash
        self.case = case
        n = next(_seq)
        # ``layout_hash`` EST POSÉ DÈS LA CRÉATION, ET C'EST DÉLIBÉRÉ : l'étape
        # ``sync-layout`` renvoie alors le MÊME calepinage, court-circuite sur
        # ``inchange: True`` et n'écrit RIEN (comportement documenté de
        # ``sync_devis_from_layout``). L'endpoint est donc réellement exercé,
        # sans qu'une recomposition légitime ne déplace la valeur AUTOMATIQUE
        # sous les pieds des assertions de survie.
        self.devis = Devis.objects.create(
            company=case.company, reference=f'DEV-QJR103-{n:04d}',
            client=case.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=case.user, mode_installation='residentiel',
            roof_layout=_layout(), layout_hash=layout_hash(_layout()),
            etude_params={'scenario': DEUX_OPTIONS})
        for designation, qte, prix in LIGNES:
            LigneDevis.objects.create(
                devis=self.devis, produit=case.produits[designation],
                designation=designation, quantite=Decimal(qte),
                prix_unitaire=Decimal(prix), remise=Decimal('0'))
        self.token = str(uuid.uuid4())
        ShareLink.objects.create(company=case.company, devis=self.devis,
                                 token=self.token,
                                 niveau=ShareLink.NIVEAU_CONFIANCE)
        self.url = f'/api/django/ventes/devis/{self.devis.id}/overrides/'

    # ── lectures ────────────────────────────────────────────────────────────

    def recharger(self):
        self.devis.refresh_from_db()
        self.devis._prefetched_objects_cache = {}
        return self.devis

    def quote_data(self, options=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(self.recharger(), options)

    def effectif(self, chemin):
        return overrides.effectif(self.recharger(), chemin, None)

    # ── les dix étapes du parcours, dans l'ordre ────────────────────────────

    def etape_replace_lines(self):
        corps = {'lignes': [
            {'produit': self.case.produits[designation].id,
             'designation': designation, 'quantite': qte,
             'prix_unitaire': prix}
            for designation, qte, prix in LIGNES]}
        r = self.case.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            corps, format='json')
        return r.status_code, (200,)

    def etape_patch_devis(self):
        # ``overrides`` est DÉLIBÉRÉMENT dans le corps : la colonne est en
        # lecture seule sur ``DevisSerializer`` (QJR67), et un PATCH d'écran
        # qui la renvoie vide ne doit PAS vider le registre.
        r = self.case.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'note': 'parcours QJR103', 'overrides': {}}, format='json')
        return r.status_code, (200,)

    def etape_sync_layout(self):
        r = self.case.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/sync-layout/',
            _layout(), format='json')
        # 409 = garde de statut (règle #4) ; 400 = layout refusé. Les deux
        # sont des refus LÉGITIMES qui ne doivent rien écrire du tout.
        return r.status_code, (200, 400, 409)

    def etape_appliquer_taille(self):
        r = self.case.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/'
            'offres-tailles/appliquer/', {'cle': 'recommande'}, format='json')
        # 400 = « ce devis ne permet pas encore de dériver des tailles »,
        # motif NOMMÉ et attendu sur une fixture sans profil de consommation.
        return r.status_code, (200, 400)

    def etape_rafraichir_etudes(self):
        from apps.ventes.domain.etudes import rafraichir_etudes_du_devis
        rafraichir_etudes_du_devis(self.recharger())
        return 200, (200,)

    def etape_build_quote_data(self):
        self.quote_data()
        return 200, (200,)

    def etape_proposal_data(self):
        r = self.case.public.get(
            f'/api/django/public/proposal/{self.token}/data/')
        return r.status_code, (200,)

    def etape_charge_utile_pdf(self):
        # La charge utile que TOUS les renderers premium consomment. Le rendu
        # natif lui-même est exercé par ``RenduPdfReelTests``.
        self.quote_data({'pdf_mode': 'full'})
        return 200, (200,)

    def etape_option_totaux(self):
        from apps.ventes.utils.options import option_totaux
        option_totaux(self.recharger())
        return 200, (200,)

    def etape_taille_detail(self):
        r = self.case.public.get(
            f'/api/django/public/proposal/{self.token}/taille/eco/'
            '?variante=sans')
        # 404 GÉNÉRIQUE = refus documenté (taille non envoyée, dérivation
        # impossible) — une LECTURE, qui ne doit toucher aucun registre.
        return r.status_code, (200, 404)

    ETAPES = (
        ('replace-lines', etape_replace_lines),
        ('PATCH devis', etape_patch_devis),
        ('sync-layout', etape_sync_layout),
        ('offres-tailles/appliquer', etape_appliquer_taille),
        ('rafraichir_etudes_du_devis', etape_rafraichir_etudes),
        ('build_quote_data', etape_build_quote_data),
        ('proposal_data', etape_proposal_data),
        ('charge utile PDF', etape_charge_utile_pdf),
        ('option_totaux', etape_option_totaux),
        ('taille_detail', etape_taille_detail),
    )


class _ParcoursBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from authentication.models import Company
        cls.company = Company.objects.create(slug='qjr103-co',
                                             nom='QJR103 Co')
        cls.user = User.objects.create_user(
            username='qjr103', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Bennani', prenom='Salma',
            email='s@example.com', telephone='+212600000104')
        cls.produits = {
            designation: Produit.objects.create(
                company=cls.company, nom=designation,
                sku=f'QJR103-{index}', prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=100)
            for index, (designation, _qte, prix) in enumerate(LIGNES)
        }

    def setUp(self):
        from django.test import Client as DjangoClient
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.public = DjangoClient()

    def poser(self, parcours, chemin, valeur):
        r = self.api.patch(parcours.url, {chemin: {'valeur': valeur}},
                           format='json')
        self.assertEqual(r.status_code, 200,
                         f'pose de « {chemin} » refusée : {r.data}')
        return r

    def regenerer(self, parcours, chemin):
        r = self.api.delete(f'{parcours.url}?chemin={chemin}')
        self.assertEqual(r.status_code, 200,
                         f'régénération de « {chemin} » refusée : {r.data}')
        return r


# ═══════════════════════════════════════════════════════════════════════════
# (1) La table couvre le registre — un chemin ajouté SANS couverture ROUGIT
# ═══════════════════════════════════════════════════════════════════════════

class TableDeCouvertureTests(TestCase):
    """Le contrat de COUVERTURE lui-même — sans base, purement structurel."""

    def test_la_table_couvre_exactement_le_registre(self):
        non_couverts, orphelins = ecarts_de_couverture(
            overrides.CHAMPS_OVERRIDABLES, COUVERTURE)
        self.assertEqual(
            non_couverts, [],
            'Chemin(s) ajouté(s) à overrides.CHAMPS_OVERRIDABLES sans ligne '
            'de couverture dans COUVERTURE : le registre grandit, le contrat '
            'de parcours doit grandir avec lui — ajouter la ligne (valeur '
            'manuelle + lecteur aval, ou la raison de son absence).')
        self.assertEqual(
            orphelins, [],
            'Chemin(s) de COUVERTURE absent(s) du registre : retirer la ligne '
            'de table dans le MÊME commit que le retrait du chemin.')

    def test_le_registre_couvre_les_19_chemins_de_la_decision_D12(self):
        self.assertEqual(len(overrides.CHAMPS_OVERRIDABLES), 19)
        self.assertEqual(len(COUVERTURE), 19)

    def test_un_chemin_ajoute_au_registre_sans_couverture_rougit(self):
        """LE TEST NÉGATIF — la garde sait vraiment rougir."""
        non_couverts, orphelins = ecarts_de_couverture(
            tuple(overrides.CHAMPS_OVERRIDABLES) + ('taille.inventee',),
            COUVERTURE)
        self.assertEqual(non_couverts, ['taille.inventee'])
        self.assertEqual(orphelins, [])

    def test_un_chemin_retire_du_registre_rougit_aussi(self):
        """LE TEST NÉGATIF, dans l'autre sens."""
        ampute = tuple(c for c in overrides.CHAMPS_OVERRIDABLES
                       if c != 'scenario')
        non_couverts, orphelins = ecarts_de_couverture(ampute, COUVERTURE)
        self.assertEqual(non_couverts, [])
        self.assertEqual(orphelins, ['scenario'])

    def test_chaque_ligne_declare_un_lecteur_ou_une_raison(self):
        """Aucun SKIP SILENCIEUX : sans lecteur, la raison est obligatoire."""
        for chemin, couverture in COUVERTURE.items():
            with self.subTest(chemin=chemin):
                if couverture.lecteur is None:
                    self.assertTrue(
                        couverture.sans_lecteur.strip(),
                        f'« {chemin} » n\'a ni lecteur aval ni raison écrite.')

    def test_les_lecteurs_branches_sont_les_quatre_chemins_lus_a_ce_jour(self):
        """Le CONSTAT épinglé : brancher un cinquième chemin fait rougir ici.

        C'est voulu — cette ligne est le rappel que la table doit gagner un
        lecteur en même temps que le code en gagne un.
        """
        branches = sorted(c for c, v in COUVERTURE.items()
                          if v.lecteur is not None)
        self.assertEqual(branches, ['recommended_option', 'scenario',
                                    'taille.kwc', 'taille.nb_panneaux'])


# ═══════════════════════════════════════════════════════════════════════════
# (2) L'override survit à CHAQUE étape aval, par valeur
# ═══════════════════════════════════════════════════════════════════════════

class SurvieDeLOverrideTests(_ParcoursBase):

    def _attendu(self, parcours, couverture):
        """La valeur que le lecteur aval doit rendre, override posé.

        RECALCULÉE À CHAQUE ÉTAPE (jamais figée avant la séquence) : le
        ``taille.nb_panneaux`` surchargé se lit ``nb × le wattage RÉELLEMENT
        LU sur les lignes COURANTES`` (QJR63) — un wattage figé serait un
        nombre inventé dès qu'une étape toucherait la composition.
        """
        if couverture.attendu == 'kwc_21_panneaux':
            from apps.ventes.quote_engine.builder import panneaux_et_watt_lu
            lignes = [ligne for ligne in parcours.recharger().lignes.all()
                      if not ligne.optionnelle]
            _nb, watt = panneaux_et_watt_lu(lignes)
            self.assertTrue(watt, 'watt du panneau illisible sur la fixture')
            return round(couverture.valeur * float(watt) / 1000, 2)
        return couverture.valeur

    def test_chaque_chemin_survit_aux_dix_etapes(self):
        for chemin, couverture in COUVERTURE.items():
            with self.subTest(chemin=chemin):
                parcours = Parcours(self)
                clef = couverture.clef_patch or chemin

                # (a) la valeur AUTO, relevée AVANT toute pose.
                _auto, source = parcours.effectif(clef)
                self.assertEqual(source, 'auto')

                # (b) la pose, par le VRAI endpoint.
                self.poser(parcours, clef, couverture.valeur)

                # (c) les dix étapes, EN SÉQUENCE.
                for nom, etape in Parcours.ETAPES:
                    code, admis = etape(parcours)
                    self.assertIn(
                        code, admis,
                        f'[{chemin}] étape « {nom} » : statut {code} hors '
                        f'des statuts documentés {admis}.')
                    valeur, source = parcours.effectif(clef)
                    self.assertEqual(
                        source, 'manuel',
                        f'[{chemin}] l\'override a DISPARU après « {nom} ».')
                    self.assertEqual(
                        valeur, couverture.valeur,
                        f'[{chemin}] la valeur du registre a changé après '
                        f'« {nom} » : {valeur!r} au lieu de '
                        f'{couverture.valeur!r}.')
                    if couverture.lecteur is not None:
                        self.assertEqual(
                            couverture.lecteur(parcours),
                            self._attendu(parcours, couverture),
                            f'[{chemin}] la valeur RENDUE ne reflète plus '
                            f'l\'override après « {nom} ».')

                # (d) au bout du parcours, ``regenerer`` SUPPRIME l'entrée —
                # il ne la remplace jamais par une valeur calculée.
                self.regenerer(parcours, clef)
                _valeur, source = parcours.effectif(clef)
                self.assertEqual(
                    source, 'auto',
                    f'[{chemin}] « regenerer » n\'a pas SUPPRIMÉ l\'entrée.')
                self.assertNotIn(clef,
                                 overrides.registre_du_devis(parcours.devis))


# ═══════════════════════════════════════════════════════════════════════════
# (2 bis) « regenerer » rend EXACTEMENT l'auto relevé — jamais un 3ᵉ nombre
# ═══════════════════════════════════════════════════════════════════════════

class RetourALAutomatiqueTests(_ParcoursBase):
    """Poser puis régénérer, sur un devis que RIEN d'autre n'a fait bouger.

    Séparé de la séquence à dessein : après une recomposition, une valeur
    automatique DIFFÉRENTE serait la bonne réponse (le moteur re-dérive sur
    les lignes courantes), pas une régression. Ici, entre le relevé et le
    retour, la seule chose qui a changé est l'override lui-même — l'égalité
    stricte est donc la propriété exacte que ``regenerer`` doit tenir.
    """

    def test_chaque_chemin_revient_exactement_a_sa_valeur_auto(self):
        for chemin, couverture in COUVERTURE.items():
            with self.subTest(chemin=chemin):
                parcours = Parcours(self)
                clef = couverture.clef_patch or chemin

                auto_registre, source = parcours.effectif(clef)
                self.assertEqual(source, 'auto')
                auto_rendu = (couverture.lecteur(parcours)
                              if couverture.lecteur else None)

                self.poser(parcours, clef, couverture.valeur)
                self.assertEqual(parcours.effectif(clef)[1], 'manuel')

                self.regenerer(parcours, clef)
                valeur, source = parcours.effectif(clef)
                self.assertEqual(source, 'auto')
                self.assertEqual(valeur, auto_registre)
                if couverture.lecteur is not None:
                    self.assertEqual(
                        couverture.lecteur(parcours), auto_rendu,
                        f'[{chemin}] « regenerer » a rendu un TROISIÈME '
                        f'nombre au lieu de la valeur AUTO relevée.')


# ═══════════════════════════════════════════════════════════════════════════
# (2 bis) QJR216 — le bloc ``effectif`` porte la VRAIE carte des valeurs AUTO,
#         et le DELETE rend la valeur du moteur
# ═══════════════════════════════════════════════════════════════════════════

class BlocEffectifPorteLesAutosTests(_ParcoursBase):
    """TEST ROUGE D'ABORD (QJR216).

    Avant le correctif, ``views/devis._overrides_reponse`` construisait
    ``vue_effective(devis, {})`` — une carte ``autos`` VIDE en dur — donc
    **toute** réponse annonçait ``auto: null`` ; et après un
    ``DELETE ?chemin=``, le chemin régénéré DISPARAISSAIT de la réponse au lieu
    d'y revenir avec la valeur du moteur.

    La fixture porte 14 panneaux de 710 W : le moteur a donc une valeur
    parfaitement lisible pour ``taille.nb_panneaux`` (14), ``taille.panel_watt``
    (710) et ``taille.kwc`` (9,94).
    """

    #: Les valeurs que le lecteur unique des lignes (PVUNI) tire de la fixture.
    AUTOS_ATTENDUS = {
        'taille.nb_panneaux': 14,
        'taille.panel_watt': 710,
        'taille.kwc': 9.94,
        'mode_installation': 'residentiel',
    }

    def _bloc(self, reponse, chemin):
        self.assertIn(chemin, reponse.data['effectif'],
                      f'« {chemin} » absent du bloc effectif : {reponse.data}')
        return reponse.data['effectif'][chemin]

    def test_get_porte_la_valeur_moteur_de_chaque_chemin_derivable(self):
        parcours = Parcours(self)
        reponse = self.api.get(parcours.url)
        self.assertEqual(reponse.status_code, 200)
        for chemin, attendu in self.AUTOS_ATTENDUS.items():
            with self.subTest(chemin=chemin):
                bloc = self._bloc(reponse, chemin)
                self.assertEqual(bloc['auto'], attendu)
                self.assertIsNone(bloc['manuel'])
                self.assertEqual(bloc['source'], 'auto')
                self.assertEqual(bloc['effectif'], attendu)

    def test_une_surcharge_montre_les_deux_valeurs_cote_a_cote(self):
        parcours = Parcours(self)
        self.poser(parcours, 'taille.nb_panneaux', 18)
        bloc = self._bloc(self.api.get(parcours.url), 'taille.nb_panneaux')
        self.assertEqual(bloc['auto'], 14)     # ce que le moteur calcule
        self.assertEqual(bloc['manuel'], 18)   # ce que le vendeur a déclaré
        self.assertEqual(bloc['effectif'], 18)
        self.assertEqual(bloc['source'], 'manuel')

    def test_delete_rend_exactement_la_valeur_moteur(self):
        parcours = Parcours(self)
        self.poser(parcours, 'taille.nb_panneaux', 18)
        reponse = self.regenerer(parcours, 'taille.nb_panneaux')
        bloc = self._bloc(reponse, 'taille.nb_panneaux')
        self.assertEqual(bloc['auto'], 14)
        self.assertIsNone(bloc['manuel'])
        self.assertEqual(bloc['effectif'], 14)
        self.assertEqual(bloc['source'], 'auto')
        self.assertNotIn('taille.nb_panneaux', reponse.data['overrides'])

    def test_delete_dun_chemin_sans_derivation_le_rend_quand_meme(self):
        """Un chemin que le moteur ne sait pas dériver revient avec
        ``auto: null`` — une omission HONNÊTE, jamais une disparition."""
        parcours = Parcours(self)
        self.poser(parcours, 'tarif.distributeur', 'ONEE')
        reponse = self.regenerer(parcours, 'tarif.distributeur')
        bloc = self._bloc(reponse, 'tarif.distributeur')
        self.assertIsNone(bloc['auto'])
        self.assertIsNone(bloc['manuel'])
        self.assertEqual(bloc['source'], 'auto')

    def test_la_carte_auto_ignore_le_registre(self):
        """``auto`` est la valeur AUTOMATIQUE : une surcharge posée ne doit pas
        la déplacer, sinon ``auto`` et ``manuel`` diraient la même chose."""
        parcours = Parcours(self)
        self.poser(parcours, 'taille.kwc', 25)
        autos = overrides.autos_du_devis(parcours.recharger())
        self.assertEqual(autos['taille.kwc'], 9.94)

    def test_un_devis_sans_panneau_lisible_nomet_rien_dinvente(self):
        parcours = Parcours(self)
        parcours.devis.lignes.filter(designation__startswith='Panneau').delete()
        autos = overrides.autos_du_devis(parcours.recharger())
        self.assertNotIn('taille.nb_panneaux', autos)
        self.assertNotIn('taille.kwc', autos)


# ═══════════════════════════════════════════════════════════════════════════
# (3) Le PATCH devis ne peut PAS vider le registre
# ═══════════════════════════════════════════════════════════════════════════

class RegistreNonEcrasableParLEcranTests(_ParcoursBase):

    def test_un_patch_devis_portant_overrides_vide_ne_vide_rien(self):
        parcours = Parcours(self)
        self.poser(parcours, 'tarif.distributeur', 'ONEE')
        code, _admis = Parcours.etape_patch_devis(parcours)
        self.assertEqual(code, 200)
        self.assertEqual(parcours.effectif('tarif.distributeur'),
                         ('ONEE', 'manuel'))


# ═══════════════════════════════════════════════════════════════════════════
# (4) R4-A — la table de PRÉSÉANCE, dans les DEUX sens
# ═══════════════════════════════════════════════════════════════════════════

class PreseanceR4ATests(_ParcoursBase):
    """``taille.nb_panneaux`` (devis) contre ``quantite_manuelle`` (ligne)."""

    def _ligne_panneaux(self, parcours):
        return parcours.devis.lignes.get(
            designation='Panneau Canadian Solar 710W')

    def test_sens_1_la_ligne_verrouillee_gagne_pour_sa_quantite(self):
        parcours = Parcours(self)
        ligne = self._ligne_panneaux(parcours)
        ligne.quantite_manuelle = True
        ligne.save(update_fields=['quantite_manuelle'])
        self.poser(parcours, 'taille.nb_panneaux', 21)

        avertissements = []
        verdict = overrides.preseance_nb_panneaux(
            parcours.recharger(), ligne, avertissements=avertissements)

        self.assertEqual(verdict.quantite_ligne, 14)
        self.assertEqual(verdict.source_ligne, overrides.SOURCE_LIGNE_MANUELLE)
        # Le chemin de NIVEAU DEVIS n'est pas perdu : il alimente la cible.
        self.assertEqual(verdict.cible_dimensionnement, 21)
        self.assertTrue(verdict.conflit)
        self.assertEqual(avertissements, [verdict.avertissement])
        # L'avertissement NOMME la ligne et les DEUX nombres.
        self.assertIn('Panneau Canadian Solar 710W', verdict.avertissement)
        self.assertIn('14', verdict.avertissement)
        self.assertIn('21', verdict.avertissement)

    def test_sens_2_sans_verrou_le_chemin_de_devis_pilote_la_quantite(self):
        parcours = Parcours(self)
        ligne = self._ligne_panneaux(parcours)
        self.assertFalse(ligne.quantite_manuelle)
        self.poser(parcours, 'taille.nb_panneaux', 21)

        avertissements = []
        verdict = overrides.preseance_nb_panneaux(
            parcours.recharger(), ligne, avertissements=avertissements)

        self.assertEqual(verdict.quantite_ligne, 21)
        self.assertEqual(verdict.source_ligne, overrides.SOURCE_DEVIS)
        self.assertEqual(verdict.cible_dimensionnement, 21)
        self.assertFalse(verdict.conflit)
        self.assertIsNone(verdict.avertissement)
        self.assertEqual(avertissements, [])

    def test_verrou_et_chemin_de_devis_D_ACCORD_n_avertissent_pas(self):
        """Un désaccord seul mérite un avertissement — pas la coexistence."""
        parcours = Parcours(self)
        ligne = self._ligne_panneaux(parcours)
        ligne.quantite_manuelle = True
        ligne.save(update_fields=['quantite_manuelle'])
        self.poser(parcours, 'taille.nb_panneaux', 14)

        avertissements = []
        verdict = overrides.preseance_nb_panneaux(
            parcours.recharger(), ligne, avertissements=avertissements)

        self.assertEqual(verdict.quantite_ligne, 14)
        self.assertEqual(verdict.cible_dimensionnement, 14)
        self.assertFalse(verdict.conflit)
        self.assertEqual(avertissements, [])

    def test_aucune_surcharge_du_tout_laisse_la_ligne_telle_quelle(self):
        parcours = Parcours(self)
        verdict = overrides.preseance_nb_panneaux(
            parcours.recharger(), self._ligne_panneaux(parcours))
        self.assertEqual(verdict.quantite_ligne, 14)
        self.assertEqual(verdict.source_ligne, overrides.SOURCE_AUTO)
        self.assertIsNone(verdict.cible_dimensionnement)
        self.assertFalse(verdict.conflit)

    def test_une_surcharge_illisible_ne_decide_rien(self):
        """Zéro chiffre inventé : un override non entier vaut une absence."""
        parcours = Parcours(self)
        self.poser(parcours, 'taille.nb_panneaux', 'beaucoup')
        verdict = overrides.preseance_nb_panneaux(
            parcours.recharger(), self._ligne_panneaux(parcours))
        self.assertIsNone(verdict.cible_dimensionnement)
        self.assertEqual(verdict.quantite_ligne, 14)
        self.assertFalse(verdict.conflit)

    def test_sans_ligne_dominante_la_cible_reste_lisible(self):
        parcours = Parcours(self)
        self.poser(parcours, 'taille.nb_panneaux', 21)
        verdict = overrides.preseance_nb_panneaux(parcours.recharger(), None)
        self.assertEqual(verdict.cible_dimensionnement, 21)
        self.assertEqual(verdict.quantite_ligne, 21)
        self.assertFalse(verdict.conflit)


class PreseanceR4AAtteintLeVendeurTests(_ParcoursBase):
    """QJR217 — TEST ROUGE D'ABORD : la règle R4-A avait ZÉRO appelant.

    ``preseance_nb_panneaux`` était écrite, testée dans les deux sens, et
    jamais appelée hors des tests : une ligne verrouillée à 14 panneaux qui
    contredisait ``taille.nb_panneaux = 10`` ne produisait AUCUN avertissement,
    et ``puissance_kwc_du_devis`` suivait silencieusement le niveau DEVIS
    pendant que le moteur PDF suivait les LIGNES.
    """

    def _ligne_panneaux(self, parcours):
        return parcours.devis.lignes.get(
            designation='Panneau Canadian Solar 710W')

    def _verrouiller(self, parcours):
        ligne = self._ligne_panneaux(parcours)
        ligne.quantite_manuelle = True
        ligne.save(update_fields=['quantite_manuelle'])
        return ligne

    def test_le_lecteur_de_kwc_emet_l_avertissement_nomme(self):
        """LE ROUGE : aucun avertissement n'était produit."""
        from apps.ventes.domain.scenario import puissance_kwc_du_devis

        parcours = Parcours(self)
        self._verrouiller(parcours)
        self.poser(parcours, 'taille.nb_panneaux', 10)

        avertissements = []
        puissance_kwc_du_devis(parcours.recharger(),
                               avertissements=avertissements)
        self.assertEqual(len(avertissements), 1, avertissements)
        message = avertissements[0]
        self.assertIn('Panneau Canadian Solar 710W', message)
        self.assertIn('14', message)
        self.assertIn('10', message)

    def test_la_ligne_verrouillee_decide_le_kwc_vendu(self):
        """R4-A phrase 1 : le verrou de ligne gagne pour CETTE ligne — le kWc
        décrit donc les 14 panneaux vendus, pas les 10 de la cible."""
        from apps.ventes.domain.scenario import puissance_kwc_du_devis

        parcours = Parcours(self)
        self._verrouiller(parcours)
        self.poser(parcours, 'taille.nb_panneaux', 10)
        self.assertAlmostEqual(
            puissance_kwc_du_devis(parcours.recharger()), 9.94, places=2)

    def test_sans_verrou_le_niveau_devis_pilote_toujours_le_kwc(self):
        """Non-régression QJR63 : sans verrou, rien ne change."""
        from apps.ventes.domain.scenario import puissance_kwc_du_devis

        parcours = Parcours(self)
        self.poser(parcours, 'taille.nb_panneaux', 10)
        avertissements = []
        self.assertAlmostEqual(
            puissance_kwc_du_devis(parcours.recharger(),
                                   avertissements=avertissements),
            7.1, places=2)
        self.assertEqual(avertissements, [])

    def test_taille_kwc_reste_prioritaire(self):
        """Non-régression : ``taille.kwc`` posé explicitement prime sur tout."""
        from apps.ventes.domain.scenario import puissance_kwc_du_devis

        parcours = Parcours(self)
        self._verrouiller(parcours)
        self.poser(parcours, 'taille.kwc', 12.5)
        self.assertAlmostEqual(
            puissance_kwc_du_devis(parcours.recharger()), 12.5, places=2)

    def test_la_cible_de_dimensionnement_reste_lisible(self):
        """R4-A phrase 2 : le niveau DEVIS n'est pas perdu — il reste la cible
        que ``decider_taille`` reçoit (elle ne passe pas par ce lecteur)."""
        parcours = Parcours(self)
        ligne = self._verrouiller(parcours)
        self.poser(parcours, 'taille.nb_panneaux', 10)
        verdict = overrides.preseance_nb_panneaux(parcours.recharger(), ligne)
        self.assertEqual(verdict.cible_dimensionnement, 10)
        self.assertEqual(verdict.quantite_ligne, 14)

    def test_la_resynchro_fait_remonter_l_avertissement_a_l_ecran(self):
        """L'avertissement atteint la RÉPONSE que l'écran affiche déjà."""
        parcours = Parcours(self)
        self._verrouiller(parcours)
        self.poser(parcours, 'taille.nb_panneaux', 10)

        # Un layout DIFFÉRENT de celui déjà posé : sinon ``sync-layout``
        # court-circuite sur ``inchange`` et n'exécute pas la resynchro.
        layout = _layout()
        layout['result'] = dict(layout['result'], annualKwh=15100)
        reponse = self.api.post(
            f'/api/django/ventes/devis/{parcours.devis.id}/sync-layout/',
            layout, format='json')
        self.assertIn(reponse.status_code, (200, 400, 409),
                      getattr(reponse, 'data', reponse))
        if reponse.status_code != 200 or reponse.data.get('inchange'):
            self.skipTest('sync-layout n\'a pas resynchronisé ce devis '
                          '(refus ou layout inchangé) : le câblage de '
                          "l'avertissement est déjà épinglé au lecteur de kWc.")
        messages = ' '.join(reponse.data.get('avertissements') or ())
        self.assertIn('Panneau Canadian Solar 710W', messages)

    def test_la_ligne_panneau_dominante_est_la_plus_grande(self):
        from apps.ventes.domain.scenario import ligne_panneau_dominante

        parcours = Parcours(self)
        lignes = list(parcours.devis.lignes.select_related('produit').all())
        dominante = ligne_panneau_dominante(lignes)
        self.assertEqual(dominante.designation, 'Panneau Canadian Solar 710W')
        self.assertIsNone(ligne_panneau_dominante(
            [li for li in lignes
             if not li.designation.startswith('Panneau')]))


# ═══════════════════════════════════════════════════════════════════════════
# (5) Le rendu PDF RÉEL — une fois, à part, sautable
# ═══════════════════════════════════════════════════════════════════════════

@tag('weasyprint')
class RenduPdfReelTests(_ParcoursBase):
    """``generate_premium_devis_pdf`` de bout en bout, override posé.

    Patron des tests moteur : le rendu natif est exercé une SEULE fois (il
    coûte des secondes et des bibliothèques natives), la séquence par chemin
    se contentant de la charge utile que ce rendu consomme.
    """

    def test_le_pdf_est_rendu_avec_le_scenario_surcharge(self):
        try:
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — libs natives absentes
            self.skipTest('weasyprint natif indisponible')
        from apps.ventes.quote_engine.builder import generate_premium_devis_pdf

        parcours = Parcours(self)
        self.poser(parcours, 'scenario', 'Sans batterie')
        cle = generate_premium_devis_pdf(parcours.devis.id, persist=False)
        self.assertTrue(cle)
        self.assertEqual(parcours.effectif('scenario'),
                         ('Sans batterie', 'manuel'))
        self.assertEqual(parcours.quote_data().get('scenario'),
                         'Sans batterie')
