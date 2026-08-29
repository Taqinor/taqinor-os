"""QJR67 — la surface d'ÉCRITURE d'un devis est déclarée, plus subie.

LE TROU QUE CECI FERME. ``DevisWriteSerializer.Meta`` était
``exclude = ['reference', 'fichier_pdf']`` : CHAQUE autre colonne du modèle
était donc écrivable depuis le corps de la requête, y compris cinq champs
BRUTS sans forme ni provenance — ``etude_params``, ``roof_layout``,
``offres_tailles_config`` (JSONField), ``layout_hash`` (CharField) et
``marge_snapshot`` (DecimalField : la MARGE HT interne, manager-only —
règle #4, elle ne paraît dans aucune sortie client). Le navigateur
pouvait poster n'importe quel chiffre CLIENT-FACING (``puissance_kwc``,
``production_annuelle``, ``economies_annuelles``, ``scenario``,
``etude_horaire``…) directement dans les entrées du PDF et de la page
proposition, en contournant toute la garde « zéro chiffre inventé » que les
sérialiseurs dédiés appliquent.

CE QUE CE MODULE PROUVE.

  1. SURFACE DÉCLARÉE — ``Meta.fields`` est explicite (plus d'``exclude``) et
     couvre EXACTEMENT la surface d'avant, moins ``reference`` et
     ``fichier_pdf``. Un champ de modèle ajouté demain ne s'y invite plus tout
     seul : ce test rougit tant que quelqu'un ne l'a pas écrit sciemment.
  2. LES CINQ BRUTS SONT EN LECTURE SEULE — et un PATCH qui les porte ne
     change RIEN en base (DRF les ignore : c'est le comportement voulu, un 400
     casserait tous les clients qui renvoient l'objet lu tel quel).
  3. L'ÉCHÉANCIER RESTE ÉCRIVABLE, ET VALIDÉ — ce n'est PAS un champ brut :
     c'est le chemin d'écriture prévu du champ, gardé par
     ``EcheancierValidationMixin`` (QJR21). Le passer en lecture seule l'aurait
     rendu silencieusement inécrivable ET aurait supprimé son 400 français.

ATTENTION FIXTURES : montants sous 1000 MAD (R4-B3, ``Facture.pourcentage``
est un ``numeric(5, 2)``).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr_serializer_surface"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.utils import model_meta
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.ventes.serializers import DevisWriteSerializer

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')

#: Les SIX JSONField BRUTS refermés par QJR67. ``echeancier`` n'en fait PAS
#: partie : il est VALIDÉ (voir la classe ``EcheancierResteEcrivable``).
#: ``overrides`` (colonne QJR58 / décision fondateur D12) a été ajouté par
#: arbitrage de l'orchestrateur du 29/08/2026 : même classe, même vague, et
#: laissé ouvert il contournait la garde 400 d'``OverridesSerializer``.
CHAMPS_BRUTS = ('etude_params', 'roof_layout', 'layout_hash',
                'offres_tailles_config', 'marge_snapshot', 'overrides')

#: Jamais exposés à l'écriture (la référence est numérotée côté serveur, le PDF
#: est un artefact de rendu).
JAMAIS_EXPOSES = ('reference', 'fichier_pdf')


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA SURFACE, SANS BASE
# ═══════════════════════════════════════════════════════════════════════════
class SurfaceDeclaree(SimpleTestCase):

    def test_meta_declare_fields_et_plus_exclude(self):
        """Une liste explicite : rien n'entre plus dans l'écriture tout seul."""
        self.assertFalse(hasattr(DevisWriteSerializer.Meta, 'exclude'),
                         "Meta.exclude est revenu : toute nouvelle colonne "
                         "redeviendrait écrivable en silence.")
        self.assertIsInstance(DevisWriteSerializer.Meta.fields, list)

    def test_la_surface_couvre_exactement_le_modele_moins_les_deux_exclus(self):
        """AUCUN champ perdu à la bascule ``exclude`` → ``fields``.

        C'est le risque propre de cette tâche : oublier un nom, c'est rendre
        une colonne silencieusement inécrivable. Le test le NOMME, dans les
        deux sens — et il rougira aussi quand un champ sera ajouté au modèle
        sans être déclaré ici, ce qui est exactement l'intention.
        """
        info = model_meta.get_field_info(Devis)
        attendus = ({info.pk.name}
                    | set(info.fields)
                    | set(info.forward_relations)) - set(JAMAIS_EXPOSES)
        declares = set(DevisWriteSerializer.Meta.fields)
        self.assertEqual(
            declares, attendus,
            'Surface d\'écriture divergente — manquants : %s ; en trop : %s'
            % (sorted(attendus - declares), sorted(declares - attendus)))

    def test_reference_et_fichier_pdf_restent_hors_surface(self):
        for nom in JAMAIS_EXPOSES:
            self.assertNotIn(nom, DevisWriteSerializer().fields, nom)

    def test_les_six_champs_bruts_sont_en_lecture_seule(self):
        champs = DevisWriteSerializer().fields
        for nom in CHAMPS_BRUTS:
            self.assertIn(nom, champs, nom)
            self.assertTrue(
                champs[nom].read_only,
                '%s doit être en lecture seule : il a un endpoint dédié et '
                'gardé, le corps du devis n\'en est pas un.' % nom)

    def test_echeancier_reste_ecrivable_et_valide(self):
        """La contrepartie explicite : validé n'est pas brut (QJR21)."""
        champ = DevisWriteSerializer().fields['echeancier']
        self.assertFalse(champ.read_only)
        self.assertTrue(hasattr(DevisWriteSerializer, 'validate_echeancier'))


# ═══════════════════════════════════════════════════════════════════════════
# 2. LA GARDE À L'ÉCRITURE — par l'API
# ═══════════════════════════════════════════════════════════════════════════
def _company():
    company, _ = Company.objects.get_or_create(
        slug='qjr67-co', defaults={'nom': 'QJR67 Co'})
    return company


def _user(company):
    return User.objects.create_user(
        username='qjr67_resp', password='x', role_legacy='responsable',
        company=company)


def _client_obj(company):
    return Client.objects.create(
        company=company, nom='QJR67', prenom='Client',
        email='qjr67@example.invalid', telephone='+212600000067')


class PatchBrutIgnore(TestCase):
    """Un corps qui porte un champ brut ne déplace RIEN en base."""

    #: Ce que le serveur a calculé — et que le navigateur ne doit pas pouvoir
    #: remplacer par ses propres chiffres.
    ETUDE_SERVEUR = {
        'puissance_kwc': 6.6,
        'production_annuelle': 10500,
        'factures_mensuelles_reelles': [820] * 12,
    }

    def setUp(self):
        self.company = _company()
        self.user = _user(self.company)
        self.client_obj = _client_obj(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-Q67A',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), mode_installation='residentiel',
            etude_params=dict(self.ETUDE_SERVEUR),
            roof_layout={'pans': ['serveur']},
            layout_hash='hash-serveur',
            offres_tailles_config={'eco': {'nb_panneaux': 10}},
            # ``marge_snapshot`` est un DecimalField (marge HT figée en MAD,
            # manager-only — QX23be), PAS un JSONField : un dict y lève
            # « conversion from dict to Decimal is not supported » dès la
            # création. Montant volontairement sous 1000 MAD (R4-B3).
            marge_snapshot=Decimal('12.50'))

    def _patch(self, corps):
        return self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/', corps, format='json')

    def _assert_etude_serveur_intacte(self):
        """Les clés du SERVEUR sont inchangées, celles du navigateur absentes.

        Assertion par CLÉ et non par dict entier : ``perform_update`` relance
        les rafraîchisseurs (bloc horaire, dimensionnement), qui ont le droit
        d'AJOUTER leurs propres clés — ce n'est pas ce que ce test surveille.
        """
        etude = self.devis.etude_params or {}
        for cle, valeur in self.ETUDE_SERVEUR.items():
            self.assertEqual(etude.get(cle), valeur, cle)
        self.assertNotIn('economies_annuelles', etude,
                         'un chiffre client-facing posté par le navigateur a '
                         'atterri dans les entrées du PDF')

    def test_etude_params_poste_en_corps_est_ignore(self):
        """Le cas qui motive la tâche : des chiffres client-facing inventés."""
        reponse = self._patch({'etude_params': {
            'puissance_kwc': 99, 'production_annuelle': 999999,
            'economies_annuelles': 999999}})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self._assert_etude_serveur_intacte()

    def test_les_quatre_autres_champs_bruts_sont_ignores(self):
        reponse = self._patch({
            'roof_layout': {'pans': ['navigateur']},
            'layout_hash': 'hash-navigateur',
            'offres_tailles_config': {'eco': {'nb_panneaux': 999}},
            'marge_snapshot': '999.90',
        })
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.roof_layout, {'pans': ['serveur']})
        self.assertEqual(self.devis.layout_hash, 'hash-serveur')
        self.assertEqual(self.devis.offres_tailles_config,
                         {'eco': {'nb_panneaux': 10}})
        self.assertEqual(self.devis.marge_snapshot, Decimal('12.50'))

    def test_le_reste_du_corps_passe_toujours(self):
        """La fermeture ne doit RIEN casser du chemin d'écriture normal."""
        reponse = self._patch({'note': 'Note du vendeur',
                               'etude_params': {'puissance_kwc': 99}})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.note, 'Note du vendeur')
        self._assert_etude_serveur_intacte()

    def test_overrides_poste_en_corps_est_ignore(self):
        """Le 6e brut (QJR58/D12) : le corps du devis n'est pas sa porte.

        Ouvert, il contournait la garde qui fait toute la valeur du registre :
        ``OverridesSerializer`` refuse en 400 un champ DÉRIVÉ et un chemin
        inconnu, et un PATCH y FUSIONNE au lieu de remplacer.
        """
        reponse = self._patch({'overrides': {
            'prix_ttc': {'valeur': 1},
            'taille.nb_panneaux': {'valeur': 999}}})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertIn(self.devis.overrides, (None, {}))

    def test_le_chemin_dedie_ecrit_toujours_les_overrides(self):
        """La porte n'est pas murée : elle est NOMMÉE, et elle garde."""
        url = f'/api/django/ventes/devis/{self.devis.id}/overrides/'
        pose = self.api.patch(url, {'taille.nb_panneaux': 14}, format='json')
        self.assertEqual(pose.status_code, 200, pose.data)
        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.overrides['taille.nb_panneaux']['valeur'], 14)
        # Et la garde du sérialiseur dédié est toujours là.
        refus = self.api.patch(url, {'prix_ttc': 120000}, format='json')
        self.assertEqual(refus.status_code, 400, refus.data)

    def test_le_chemin_dedie_ecrit_toujours_l_etude(self):
        """La porte n'est pas murée : elle est NOMMÉE (QJR62, fusion)."""
        reponse = self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/etude-params/',
            {'conso_annuelle': 9000}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['conso_annuelle'], 9000)
        # FUSION, jamais remplacement : les clés du serveur survivent.
        self.assertEqual(self.devis.etude_params['puissance_kwc'], 6.6)
        self.assertEqual(
            self.devis.etude_params['factures_mensuelles_reelles'], [820] * 12)


class EcheancierResteEcrivable(TestCase):
    """QJR21 doit survivre à QJR67 : l'échéancier s'écrit, et se valide."""

    def setUp(self):
        self.company = _company()
        self.user = _user(self.company)
        self.client_obj = _client_obj(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-Q67B',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')

    def _patch(self, echeancier):
        return self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'echeancier': echeancier}, format='json')

    def test_un_echeancier_valide_est_bien_persiste(self):
        reponse = self._patch([
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 30},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 70},
        ])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(len(self.devis.echeancier), 2)

    def test_un_echeancier_ambigu_est_toujours_refuse_en_400(self):
        reponse = self._patch([
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 750},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 100},
        ])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('echeancier', reponse.data)
        self.devis.refresh_from_db()
        self.assertIsNone(self.devis.echeancier)
