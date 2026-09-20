"""CAL29 — l'isolation multi-société, VERROUILLÉE DE BOUT EN BOUT.

Cette suite ne contient AUCUNE liste de routes écrite à la main : elle PARCOURT
LE ROUTEUR (``django.urls.get_resolver()``) et applique les mêmes trois
questions à CHAQUE route du module. C'est la seule forme qui tienne : trente
routes arriveront après cette tâche, et une liste écrite à la main les
oublierait en silence — c'est-à-dire exactement le jour où une route neuve
fuirait entre deux sociétés sans que personne ne le voie.

LES TROIS QUESTIONS, POUR CHAQUE ROUTE
--------------------------------------
1. un objet d'une AUTRE société est-il INTROUVABLE (404) — jamais « interdit »
   (403), qui confirmerait son existence ?
2. la route est-elle REFUSÉE (403) à un compte sans la permission du domaine ?
3. un ``company`` envoyé dans le CORPS est-il IGNORÉ (la société reste celle de
   l'appelant) ?

Retirer volontairement un filtre société (par exemple en remplaçant
``get_queryset`` par ``Calepinage.objects.all()``) fait rougir la première.

Run :
    python manage.py test apps.calepinage.tests.test_isolation_societe -v2
"""
from django.urls import URLPattern, URLResolver, get_resolver

from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import (
    Calepinage, CalepinageVariante, CalepinageVersion, PhotoSite,
)
from apps.records.models import Attachment
from core.models import BackgroundJob

from .test_api_liste import BaseApiCalepinage

PREFIXE = 'api/django/calepinage/'


def _routes(resolver=None, prefixe=''):
    """Toutes les routes servies, à plat — LUES DANS LE ROUTEUR."""
    resolver = resolver or get_resolver()
    trouvees = []
    for motif in resolver.url_patterns:
        chemin = prefixe + str(motif.pattern)
        if isinstance(motif, URLResolver):
            trouvees.extend(_routes(motif, chemin))
        elif isinstance(motif, URLPattern):
            trouvees.append((chemin, motif.callback))
    return trouvees


def routes_du_module():
    """Les routes de ``/api/django/calepinage/`` — jamais une liste écrite."""
    vues = []
    for chemin, callback in _routes():
        if not chemin.startswith(PREFIXE):
            continue
        reste = chemin[len(PREFIXE):]
        if '(?P<format>' in reste or reste.startswith('<drf_format_suffix'):
            continue
        if not reste:
            continue
        vues.append((reste, callback))
    return vues


def methodes_servies(callback):
    """Les méthodes HTTP réellement servies par cette route."""
    actions = getattr(callback, 'actions', None)
    if actions:
        return [m.upper() for m in actions]
    classe = getattr(callback, 'cls', None) or getattr(callback, 'view_class',
                                                       None)
    if classe is None:
        return ['GET']
    return [m.upper() for m in ('get', 'post', 'put', 'patch', 'delete')
            if hasattr(classe, m)]


class BalayageIsolationTest(BaseApiCalepinage):
    """Le MÊME contrôle sur chaque route, quelle qu'elle soit."""

    def setUp(self):
        super().setUp()
        # Les objets ÉTRANGERS : tout ce qu'un chemin peut nommer.
        self.cal_etranger = Calepinage.objects.create(
            company=self.autre, lead_id=77, titre='Chez la voisine',
            roof_layout={'result': {'panels': 9}}, layout_hash='9' * 64)
        self.variante_etrangere = CalepinageVariante.objects.create(
            company=self.autre, calepinage=self.cal_etranger, nom='Voisine')
        self.version_etrangere = CalepinageVersion.objects.create(
            company=self.autre, calepinage=self.cal_etranger,
            layout_hash='9' * 64)
        self.job_etranger = BackgroundJob.objects.create(
            company=self.autre, user=self.user_autre, kind='calepinage')
        # CAL52 — une photo de site ÉTRANGÈRE : la pièce jointe est
        # créée en base directement (aucun envoi MinIO n'est nécessaire
        # pour qu'un chemin nomme un identifiant).
        piece = Attachment.objects.create(
            company=self.autre,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.cal_etranger.pk,
            file_key='voisine/vol.png', filename='vol.png',
            size=1, mime='image/png')
        self.photo_etrangere = PhotoSite.objects.create(
            company=self.autre, calepinage=self.cal_etranger,
            attachment=piece, prise_le='2026-03-12')
        # Un objet À NOUS, pour les questions 2 et 3.
        self.mien = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Le mien')

    # ── Question 1 : un objet d'ailleurs est INTROUVABLE ───────────────────
    def test_objet_d_une_autre_societe_toujours_404(self):
        verifiees = 0
        for reste, callback in routes_du_module():
            # Une route SANS paramètre d'objet n'a rien d'étranger à
            # demander ; elle reste soumise aux questions 2 et 3.
            if '<' not in reste:
                continue
            url = '/' + PREFIXE + self._remplir(reste, etranger=True)
            for methode in methodes_servies(callback):
                reponse = self._appeler(self.api, methode, url)
                self.assertEqual(
                    reponse.status_code, 404,
                    f'{methode} {url} rend {reponse.status_code} au lieu de '
                    '404 sur un objet d\'une AUTRE société '
                    '(un 403 confirmerait son existence).')
                verifiees += 1
        self.assertGreater(verifiees, 0, 'aucune route à objet balayée')

    # ── Question 2 : sans la permission, c'est 403 ─────────────────────────
    def test_sans_permission_toujours_403(self):
        verifiees = 0
        for reste, callback in routes_du_module():
            url = '/' + PREFIXE + self._remplir(reste, etranger=False)
            for methode in methodes_servies(callback):
                reponse = self._appeler(self.api_sans, methode, url)
                self.assertEqual(
                    reponse.status_code, 403,
                    f'{methode} {url} rend {reponse.status_code} au lieu de '
                    '403 pour un compte SANS permission calepinage.')
                verifiees += 1
        self.assertGreater(verifiees, 0, 'aucune route balayée')

    # ── Question 3 : `company` du corps est IGNORÉ ─────────────────────────
    def test_company_du_corps_est_ignoree_a_la_creation(self):
        reponse = self.api.post(
            '/' + PREFIXE + 'calepinages/',
            {'lead': self.lead.pk, 'company': self.autre.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Calepinage.objects.get(pk=reponse.data['id']).company_id,
            self.company.pk)

    def test_company_du_corps_est_ignoree_a_la_modification(self):
        reponse = self.api.patch(
            '/' + PREFIXE + f'calepinages/{self.mien.pk}/',
            {'titre': 'Renommé', 'company': self.autre.pk}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.mien.refresh_from_db()
        self.assertEqual(self.mien.company_id, self.company.pk)
        self.assertEqual(self.mien.titre, 'Renommé')

    # ── Outillage ──────────────────────────────────────────────────────────
    def _remplir(self, reste, *, etranger):
        """Remplace les paramètres d'un chemin par de VRAIS identifiants."""
        cible = self.cal_etranger if etranger else self.mien
        valeurs = {
            'pk': cible.pk,
            'variante_id': (self.variante_etrangere.pk if etranger else 0),
            'version_id': (self.version_etrangere.pk if etranger else 0),
            'job_id': (self.job_etranger.pk if etranger else 0),
            'photo_id': (self.photo_etrangere.pk if etranger else 0),
        }
        chemin = reste.lstrip('^').replace('$', '')
        for nom, valeur in valeurs.items():
            # ORDRE CRUCIAL : la forme REGEX du routeur DRF
            # (``(?P<pk>[^/.]+)``) contient ``<pk>`` comme sous-chaîne. La
            # remplacer en dernier laissait ``<pk>`` être mangé d'abord, ce
            # qui produisait le segment mort ``(?P7[^/.]+)`` — une URL qui
            # part en 301 au lieu du 404/403 que ce balayage exige, sans que
            # les deux gardes ci-dessous ne le voient (``(?P<`` avait disparu).
            chemin = chemin.replace(f'(?P<{nom}>[^/.]+)', str(valeur))
            chemin = chemin.replace(f'<int:{nom}>', str(valeur))
            chemin = chemin.replace(f'<{nom}>', str(valeur))
        self.assertNotIn('(?P<', chemin,
                         f'paramètre non couvert par le balayage : {reste}')
        self.assertNotIn('<', chemin,
                         f'paramètre non couvert par le balayage : {reste}')
        return chemin

    def _appeler(self, api, methode, url):
        if methode in ('POST', 'PUT', 'PATCH'):
            return getattr(api, methode.lower())(url, {}, format='multipart')
        return getattr(api, methode.lower())(url)
