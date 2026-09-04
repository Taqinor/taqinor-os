"""AUD153 — ``EncoursCache`` : le job quotidien avait UN écrivain et ZÉRO
lecteur ; il en a désormais UN, exactement le sien.

Grep exhaustif (préservé) : avant ce correctif, ``EncoursCache`` n'était
touché en écriture que par ``credit/tasks.py`` (``recalculer_encours_pour_
societe``) ; aucune lecture nulle part ailleurs — ``credit/selectors.py``,
``credit/views.py``, ``credit/serializers.py``, ``frontend/src``.

DEUX moteurs de hold/encours coexistent dans le dépôt (décision WIR93,
``apps/credit/services.py`` en-tête) — CE lane a vérifié le code avant de
coder et a trouvé que le fix littéralement décrit par AUD153 (« brancher
``ventes/domain/recouvrement.verifier_credit_hold`` sur ``EncoursCache`` »)
citait en réalité le moteur B (FG41/XFAC28, actuellement seul branché en
production), qui calcule son encours via ``apps.crm.selectors.
credit_hold_check`` — une assiette et un chemin ENTIÈREMENT DISTINCTS
d'``apps.credit``/``EncoursCache``. Y brancher le cache aurait fusionné les
deux moteurs que WIR93 maintient DÉLIBÉRÉMENT séparés (« la bascule vers une
source unique reste ouverte au fondateur ») et cassé
``test_wir93_encours_non_divergence.py``. PIRE : ``apps.credit.services.
verifier_hold_credit`` (NTCRD6, le moteur A — celui qui utilise réellement
``apps.credit.selectors.encours_client``) porte déjà un test EXPLICITE et
NOMMÉ pour l'inverse — ``test_ntcrd32_encours_cache.
test_hold_uses_live_not_cache`` — qui verrouille qu'un hook bloquant ne lit
JAMAIS ce cache, précisément parce qu'une autorisation sur une donnée
périmée est le défaut le plus grave de la hiérarchie AUD1.

Le fix retenu ici respecte donc les DEUX invariants existants (moteur B
inchangé, moteur A jamais lu par un hold) et donne au cache exactement le
rôle que son propre docstring annonçait depuis NTCRD32 : « éviter de
recalculer... à chaque AFFICHAGE de liste » — ``selectors.disponible_credit``
(fiche/score/badges NTCRD23, jamais une décision de blocage) en devient
l'UNIQUE lecteur, via un « read-through » avec repli de fraîcheur.

Run :
    python manage.py test apps.credit.tests.test_aud153_encours_cache_brancher -v2
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.credit.models import EncoursCache, LimiteCredit
from apps.credit.models import ENCOURS_CACHE_FRAICHEUR_MAX
from apps.credit.selectors import badge_credit, disponible_credit
from apps.crm.models import Client
from apps.ventes.models import Facture
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='aud153-co', nom='AUD153 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud153DisponibleCreditLitLeCacheFraisTests(TestCase):
    """ROUGE avant correctif : chaque appel recalculait en LIVE (une requête
    de plus sur ``encours_ouvert_par_tiers``) malgré un cache frais déjà posé
    — ``EncoursCache`` n'avait aucun lecteur."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='aud153_user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='aud153@example.com')
        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'))

    def test_cache_frais_evite_le_recalcul_live(self):
        EncoursCache.objects.create(
            company=self.company, client=self.client_obj,
            encours=Decimal('5000'))

        with patch('apps.ventes.selectors.encours_ouvert_par_tiers') as m:
            resultat = disponible_credit(self.client_obj)

        m.assert_not_called()
        self.assertEqual(resultat['encours'], Decimal('5000'))

    def test_cache_absent_recalcule_live_et_peuple_le_cache(self):
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-A153001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('7000'), created_by=self.user)
        self.assertFalse(
            EncoursCache.objects.filter(client=self.client_obj).exists())

        resultat = disponible_credit(self.client_obj)

        self.assertEqual(resultat['encours'], Decimal('7000'))
        cache = EncoursCache.objects.get(client=self.client_obj)
        self.assertEqual(cache.encours, Decimal('7000'))

    def test_cache_perime_est_ignore_et_rafraichi(self):
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-A153002',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('9000'), created_by=self.user)
        cache = EncoursCache.objects.create(
            company=self.company, client=self.client_obj,
            encours=Decimal('1'))
        # `calcule_le` est `auto_now=True` : on le fait vieillir SANS passer
        # par .save() (qui l'écraserait), via .update() sur le queryset.
        perime = (timezone.now()
                  - ENCOURS_CACHE_FRAICHEUR_MAX
                  - timedelta(minutes=1))
        EncoursCache.objects.filter(id=cache.id).update(calcule_le=perime)

        resultat = disponible_credit(self.client_obj)

        self.assertEqual(resultat['encours'], Decimal('9000'))
        cache.refresh_from_db()
        self.assertEqual(cache.encours, Decimal('9000'))

    def test_badge_credit_herite_du_cache_sans_modification(self):
        """NTCRD23 — ``badge_credit`` appelle ``disponible_credit`` : il
        hérite du read-through SANS aucun changement de son propre code."""
        EncoursCache.objects.create(
            company=self.company, client=self.client_obj,
            encours=Decimal('99000'))  # proche de la limite 100000 -> orange
        with patch('apps.ventes.selectors.encours_ouvert_par_tiers') as m:
            couleur = badge_credit(self.client_obj)
        m.assert_not_called()
        self.assertEqual(couleur, 'orange')


class Aud153NonRegressionMoteursBloquantsTests(TestCase):
    """Les DEUX invariants pré-existants restent intacts : le hold NTCRD6 et
    le diagnostic WIR93 ne lisent jamais ce cache — inchangé par ce lane."""

    def setUp(self):
        self.company = make_company('aud153-hold-co', 'AUD153 Hold Co')
        self.user = User.objects.create_user(
            username='aud153_hold_user', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', email='aud153-hold@example.com')

    def test_verifier_hold_credit_ignore_un_cache_perime_a_zero(self):
        """Même scénario que l'existant ``test_ntcrd32_encours_cache.
        test_hold_uses_live_not_cache`` : préservé tel quel par ce lane —
        conservé ici comme garde de non-régression locale au fix AUD153."""
        from apps.credit.services import verifier_hold_credit

        LimiteCredit.objects.create(
            company=self.company, client=self.client_obj,
            montant_limite=Decimal('100000'),
            mode_hold=LimiteCredit.ModeHold.BLOCAGE)
        EncoursCache.objects.update_or_create(
            client=self.client_obj,
            defaults={'company': self.company, 'encours': Decimal('0')})
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-A153HOLD',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('200000'), created_by=self.user)

        result = verifier_hold_credit(self.client_obj, Decimal('0'))
        self.assertFalse(result['autorise'])

    def test_ecart_encours_moteurs_ignore_un_cache_perime_a_zero(self):
        from apps.credit.services import ecart_encours_moteurs

        EncoursCache.objects.update_or_create(
            client=self.client_obj,
            defaults={'company': self.company, 'encours': Decimal('0')})
        Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-A153ECART',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ttc=Decimal('4000'), created_by=self.user)

        res = ecart_encours_moteurs(self.client_obj)
        # Les deux moteurs restent LIVE : 4000 des deux côtés, pas 0.
        self.assertEqual(res['encours_credit'], Decimal('4000'))
        self.assertEqual(res['encours_ventes'], Decimal('4000'))
