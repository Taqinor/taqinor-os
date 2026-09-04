"""QJR421 / QJR4-04 — les écritures « best-effort » de l'acceptation prennent
un POINT DE SAUVEGARDE.

CE QUI ÉTAIT FAUX. ``apps/ventes/domain/cycle_vie.py`` enveloppait
``_persist_attribution`` (et ses semblables : la détection d'options, le
chargement des lignes) dans un ``try / except Exception`` qui se contentait de
journaliser — mais NU, à l'intérieur du ``with transaction.atomic()`` de
l'acceptation et SANS point de sauvegarde. Or en base, une requête en échec
marque la transaction comme non validable : l'``except`` CROYAIT absorber
l'incident, alors que tout ce qui suivait — y compris le passage du devis à
l'état signé — échouait. Un « best-effort » qui fait tomber l'essentiel n'est
pas du best-effort.

LA RÈGLE. Chaque écriture best-effort de cette transaction prend son PROPRE
``atomic()`` imbriqué : l'échec revient au point de sauvegarde, la transaction
principale reste validable, et la journalisation ne change pas. Le coût est
CONSTANT — un point de sauvegarde par bloc best-effort, jamais un par ligne de
devis.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr421_savepoints_acceptation -v 2
"""
import inspect
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.db import transaction as django_transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.lignes import creer_ligne
from apps.ventes.models import Devis
from apps.ventes.services import accept_devis
from authentication.models import Company

LOGGER = 'apps.ventes.services'
RESEAU = 'Onduleur réseau Huawei 10kW Monophasé'
PANNEAU = 'Panneau Canadian Solar 710W'

# Les mots-clés qui identifient une requête de POINT DE SAUVEGARDE. Elles ne
# sont PAS des requêtes métier : le troisième test les compte à part.
_MOTS_SAVEPOINT = ('SAVEPOINT', 'RELEASE SAVEPOINT', 'ROLLBACK TO SAVEPOINT')


def _est_savepoint(sql):
    return sql.strip().upper().startswith(_MOTS_SAVEPOINT)


def _erreur_de_base(**kwargs):
    """Un ``_persist_attribution`` qui échoue par une VRAIE erreur BASE.

    C'est le cœur du constat : une exception Python quelconque serait absorbée
    sans dommage, mais une requête en échec marque la transaction elle-même
    comme non validable — c'est CELA que le point de sauvegarde répare.
    """
    with connection.cursor() as cur:
        cur.execute('SELECT 1 FROM table_qui_nexiste_pas_qjr421')


class _BaseAcceptation(TestCase):
    """Un devis « envoyé » prêt à être accepté."""

    slug = 'qjr421'
    nb_lignes = 2

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR421',
            email='qjr421-%s@example.com' % self.slug)
        self._sku = 0
        self.devis = self._devis('DEV-%s-A' % self.slug.upper(),
                                 nb_lignes=self.nb_lignes)

    def _devis(self, ref, *, nb_lignes=2):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            mode_installation='residentiel', is_active=True, version=1)
        # La première ligne est toujours l'onduleur réseau, les suivantes des
        # panneaux : la composition reste classifiable par le moteur.
        gabarits = [(RESEAU, '1', '15000.00')]
        gabarits += [(PANNEAU, '1', '1166.67')] * max(0, nb_lignes - 1)
        for nom, qte, pu in gabarits[:nb_lignes]:
            self._sku += 1
            produit = Produit.objects.create(
                company=self.company, nom=nom,
                sku='QJR421-%d-%s' % (self._sku, self.company.pk),
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=500)
            creer_ligne(devis, produit=produit, designation=nom,
                        quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                        remise=Decimal('0'))
        return devis


class UneEcritureBestEffortEnEchecNEmpoisonnePlusLaVente(_BaseAcceptation):
    """LE TEST ROUGE — aujourd'hui la transaction entière est perdue."""

    slug = 'qjr421-savepoint'

    def test_une_erreur_base_dans_attribution_laisse_un_devis_signe(self):
        with patch('apps.ventes.domain.cycle_vie._persist_attribution',
                   side_effect=_erreur_de_base):
            accept_devis(devis=self.devis, user=None, nom='M. Client',
                         ip='81.0.0.1')

        self.devis.refresh_from_db()
        self.assertEqual(
            self.devis.statut, Devis.Statut.ACCEPTE,
            "l'écriture best-effort en échec a emporté la transaction : le "
            'devis devait rester signé, le point de sauvegarde est absent.')
        self.assertEqual(self.devis.accepte_par_nom, 'M. Client')
        self.assertIsNotNone(self.devis.date_acceptation)

    def test_l_echeancier_reste_coherent(self):
        """L'aval de la vente (échéancier / chaîne aval) survit lui aussi."""
        with patch('apps.ventes.domain.cycle_vie._persist_attribution',
                   side_effect=_erreur_de_base):
            accept_devis(devis=self.devis, user=None, nom='M. Client')

        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertTrue(
            self.devis.option_acceptee,
            "l'option retenue doit être enregistrée avec l'acceptation : "
            "c'est elle qui détermine le périmètre facturé de l'échéancier.")

    def test_l_echec_best_effort_reste_journalise(self):
        """On ne l'avale JAMAIS en silence — la journalisation ne change pas."""
        with patch('apps.ventes.domain.cycle_vie._persist_attribution',
                   side_effect=_erreur_de_base):
            with self.assertLogs(LOGGER, level='WARNING') as journal:
                accept_devis(devis=self.devis, user=None, nom='M. Client')

        self.assertTrue(
            any('_persist_attribution' in ligne for ligne in journal.output),
            "l'échec best-effort doit rester journalisé mot pour mot : "
            'absorbé ne veut pas dire invisible. Journal : %r' % journal.output)


class _AtomicEspion:
    """Compte les ``atomic()`` ouverts DEPUIS ``cycle_vie``, et eux seuls.

    POURQUOI PAS UN PROXY POSÉ SUR ``cycle_vie.transaction``. La première
    écriture de cet espion remplaçait l'attribut ``transaction`` du module —
    mais ``cycle_vie`` importe ``transaction`` FONCTION-LOCALEMENT
    (``from django.db import transaction`` à l'intérieur d'``accept_devis``).
    Le module ne porte donc AUCUN attribut ``transaction`` à remplacer
    (``AttributeError`` au montage), et l'import local ré-écraserait de toute
    façon le nom à chaque appel.

    On remplace donc ``atomic`` sur le VRAI module — celui que l'import local
    retrouve — et on n'incrémente que lorsque le cadre appelant EST
    ``cycle_vie``. Tout le reste de la chaîne d'acceptation (stock,
    installations, numérotation) traverse le compteur sans l'incrémenter :
    exactement la mesure que le proxy visait, et le comportement du vrai
    ``atomic`` reste intact (on ne fait que le déléguer).
    """

    MODULE = 'apps.ventes.domain.cycle_vie'

    def __init__(self):
        self.entrees = 0
        self._vrai = django_transaction.atomic

    def __call__(self, *args, **kwargs):
        cadre = inspect.currentframe()
        appelant = cadre.f_back if cadre is not None else None
        if (appelant is not None
                and appelant.f_globals.get('__name__') == self.MODULE):
            self.entrees += 1
        return self._vrai(*args, **kwargs)


class LeCoutDuPointDeSauvegardeEstConstant(_BaseAcceptation):
    """Troisième test — le point de sauvegarde ne coûte pas une requête par
    ligne de devis, et une acceptation nominale reste inchangée au centime."""

    slug = 'qjr421-cout'
    nb_lignes = 2

    def _savepoints_pour(self, devis):
        with CaptureQueriesContext(connection) as requetes:
            accept_devis(devis=devis, user=None, nom='M. Client')
        return len([q for q in requetes.captured_queries
                    if _est_savepoint(q['sql'])])

    def _atomics_de_l_acceptation(self, devis):
        """Le nombre d'``atomic()`` ouverts PAR ``cycle_vie`` pendant
        l'acceptation — les trois blocs best-effort de QJR421 compris."""
        espion = _AtomicEspion()
        with patch('django.db.transaction.atomic', espion):
            accept_devis(devis=devis, user=None, nom='M. Client')
        return espion.entrees

    def test_le_nombre_de_savepoints_ne_suit_pas_le_nombre_de_lignes(self):
        """CE QUE QJR421 PROMET, ET RIEN D'AUTRE.

        La première écriture de ce test comptait TOUS les points de sauvegarde
        émis par la chaîne d'acceptation complète — donc aussi ceux, PRÉEXISTANTS
        et étrangers à cette tâche, que posent l'aval (stock, installations,
        numérotation) une fois par ligne de devis. Elle mesurait ainsi 22
        savepoints à 2 lignes et 52 à 20 lignes, et faisait porter à QJR421 un
        coût qu'il n'a pas créé : le diff de la tâche n'ajoute QUE trois
        ``atomic()`` imbriqués, tous hors de la moindre boucle.

        La mesure porte donc désormais sur ce que ``cycle_vie`` ouvre lui-même :
        ce nombre doit être RIGOUREUSEMENT le même à 2 lignes et à 20 —
        l'égalité, pas une tolérance. Un savepoint par bloc best-effort ; jamais
        un par ligne.
        """
        petit = self.devis                       # 2 lignes
        gros = self._devis('DEV-QJR421-GROS', nb_lignes=20)

        atomics_petit = self._atomics_de_l_acceptation(petit)
        atomics_gros = self._atomics_de_l_acceptation(gros)

        self.assertGreaterEqual(
            atomics_petit, 3,
            'les trois blocs best-effort de QJR421 doivent bien ouvrir leur '
            'point de sauvegarde (mesuré : %d)' % atomics_petit)
        self.assertEqual(
            atomics_gros, atomics_petit,
            'le coût en points de sauvegarde de l\'acceptation suit le nombre '
            'de lignes (2 lignes → %d atomic(), 20 lignes → %d) : un savepoint '
            'par bloc best-effort était attendu, pas un par ligne.'
            % (atomics_petit, atomics_gros))

    def test_l_acceptation_emet_bien_des_points_de_sauvegarde(self):
        """Le compteur de requêtes reste utile comme TÉMOIN : les ``atomic()``
        imbriqués se traduisent réellement en SQL ``SAVEPOINT`` (sans quoi le
        test ci-dessus mesurerait une intention, pas un effet)."""
        self.assertGreater(self._savepoints_pour(self.devis), 0)

    def test_une_acceptation_nominale_est_inchangee_au_centime(self):
        avant_ht = self.devis.total_ht
        avant_ttc = self.devis.total_ttc

        accept_devis(devis=self.devis, user=None, nom='M. Client')

        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(self.devis.total_ht, avant_ht)
        self.assertEqual(self.devis.total_ttc, avant_ttc)
