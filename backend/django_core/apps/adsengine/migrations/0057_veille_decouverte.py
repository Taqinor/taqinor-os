"""VEIL14 — Modèles de découverte de la veille publicitaire (pilote YanBow).

Purement ADDITIVE : cinq nouvelles tables (découverte, requête, annonceur, pub
vue, verdict), aucune colonne existante touchée, aucune référence à la
connexion de campagne — entièrement revertable. ``CompetitorPage`` reste
inchangée (Page SUIVIE saisie à la main, autre usage).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

CLASSES = [
    ('vendeur', 'Vendeur'),
    ('place_de_marche', 'Place de marché ou géant'),
    ('hors_sujet', 'Hors sujet (hors vêtements, chaussures, sacs)'),
    ('pas_vendeur', 'Pas un vendeur'),
    ('doublon', "Doublon d'un autre annonceur"),
    ('incertain', 'Incertain'),
]
TRI = [('oui', 'Oui'), ('non', 'Non'), ('incertain', 'Incertain')]
JEUX = [('etalonnage', 'Étalonnage'), ('test', 'Test')]
DECIDE_PAR = [('regle', 'Règle'), ('ia', 'IA'), ('humain', 'Humain')]
SEARCH_TYPES = [
    ('KEYWORD_UNORDERED', 'Mots-clés (ordre libre)'),
    ('KEYWORD_EXACT_PHRASE', 'Expression exacte'),
]
AD_ACTIVE = [('ACTIVE', 'Actives'), ('INACTIVE', 'Inactives'),
             ('ALL', 'Toutes')]


def _id():
    return ('id', models.BigAutoField(
        auto_created=True, primary_key=True, serialize=False,
        verbose_name='ID'))


def _company():
    return ('company', models.ForeignKey(
        on_delete=django.db.models.deletion.CASCADE,
        related_name='%(app_label)s_%(class)s_set',
        to='authentication.company', verbose_name='Société'))


def _horodatage():
    return [
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('updated_at', models.DateTimeField(auto_now=True)),
    ]


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('core', '0033_ntplt29_backgroundjob'),
        ('adsengine', '0056_pub128_field_test_result'),
    ]

    operations = [
        migrations.CreateModel(
            name='VeilleDecouverte',
            fields=[
                _id(), *_horodatage(),
                ('statut', models.CharField(
                    choices=[
                        ('en_file', 'En file'),
                        ('en_cours', 'En cours'),
                        ('en_pause_quota', 'En pause (quota atteint)'),
                        ('termine', 'Terminé'),
                        ('echec', 'Échec'),
                        ('annule', 'Annulé'),
                    ],
                    default='en_file', max_length=20, verbose_name='Statut')),
                ('mots_cles', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Mots-clés et pays ([{texte, pays: [..]}])')),
                ('search_type', models.CharField(
                    choices=SEARCH_TYPES, default='KEYWORD_UNORDERED',
                    max_length=24, verbose_name='Mode de recherche')),
                ('ad_active_status', models.CharField(
                    choices=AD_ACTIVE, default='ACTIVE', max_length=10,
                    verbose_name='Statut de diffusion')),
                ('plafond_appels', models.PositiveIntegerField(
                    verbose_name="Plafond d'appels")),
                ('plafond_pages_par_requete', models.PositiveIntegerField(
                    verbose_name='Plafond de pages par requête')),
                ('appels_consommes', models.PositiveIntegerField(
                    default=0, verbose_name='Appels consommés')),
                ('pubs_recues', models.PositiveIntegerField(
                    default=0, verbose_name='Pubs reçues')),
                ('pages_lues', models.PositiveIntegerField(
                    default=0, verbose_name='Pages lues')),
                ('reprise_a', models.DateTimeField(
                    blank=True, null=True, verbose_name='Reprise à')),
                ('pauses_consecutives', models.PositiveSmallIntegerField(
                    default=0, verbose_name='Pauses de quota consécutives')),
                ('erreurs', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Erreurs ([{code, message_fr, a}])')),
                ('dernier_usage_app', models.JSONField(
                    blank=True, default=dict,
                    verbose_name='Dernier X-App-Usage')),
                ('termine_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Terminée le')),
                ('cle_idempotence', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name="Clé d'idempotence du lancement")),
                ('background_job', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='core.backgroundjob',
                    verbose_name='Job de fond')),
                _company(),
                ('cree_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='adsengine_veille_decouvertes',
                    to=settings.AUTH_USER_MODEL, verbose_name='Créée par')),
            ],
            options={
                'verbose_name': 'Découverte (veille)',
                'verbose_name_plural': 'Découvertes (veille)',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(
                    fields=['company', 'statut'],
                    name='adseng_veilledec_co_st_idx')],
            },
        ),
        migrations.CreateModel(
            name='VeilleRequete',
            fields=[
                _id(), *_horodatage(),
                ('ordre', models.PositiveIntegerField(
                    default=0, verbose_name='Ordre')),
                ('mot_cle', models.CharField(
                    max_length=100, verbose_name='Mot-clé')),
                ('pays', models.CharField(
                    max_length=2, verbose_name='Pays (ISO-2)')),
                ('search_type', models.CharField(
                    choices=SEARCH_TYPES, default='KEYWORD_UNORDERED',
                    max_length=24, verbose_name='Mode de recherche')),
                ('statut', models.CharField(
                    choices=[
                        ('a_faire', 'À faire'),
                        ('en_cours', 'En cours'),
                        ('terminee', 'Terminée'),
                        ('vide', 'Vide'),
                        ('plafond', 'Plafond atteint'),
                        ('erreur', 'Erreur'),
                    ],
                    default='a_faire', max_length=12, verbose_name='Statut')),
                ('curseur_after', models.TextField(
                    blank=True, default='',
                    verbose_name='Curseur (pendant le lancement seulement)')),
                ('pages_lues', models.PositiveIntegerField(
                    default=0, verbose_name='Pages lues')),
                ('appels', models.PositiveIntegerField(
                    default=0, verbose_name='Appels')),
                ('pubs', models.PositiveIntegerField(
                    default=0, verbose_name='Pubs reçues')),
                ('nouveaux_annonceurs', models.PositiveIntegerField(
                    default=0, verbose_name='Nouveaux annonceurs')),
                ('journal_pages', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Journal par page ([{page, pubs, nouveaux}])')),
                ('message_erreur', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Erreur')),
                _company(),
                ('decouverte', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='requetes', to='adsengine.veilledecouverte',
                    verbose_name='Découverte')),
            ],
            options={
                'verbose_name': 'Requête de découverte (veille)',
                'verbose_name_plural': 'Requêtes de découverte (veille)',
                'ordering': ['decouverte', 'ordre', 'id'],
                'constraints': [models.UniqueConstraint(
                    fields=('company', 'decouverte', 'mot_cle', 'pays',
                            'search_type'),
                    name='uniq_adseng_veillereq')],
            },
        ),
        migrations.CreateModel(
            name='VeilleAnnonceur',
            fields=[
                _id(), *_horodatage(),
                ('page_id', models.CharField(
                    max_length=64, verbose_name='ID de Page Meta')),
                ('page_name', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Nom de Page')),
                ('pays_vus', models.JSONField(
                    blank=True, default=list, verbose_name='Pays vus')),
                ('mots_cles', models.JSONField(
                    blank=True, default=list, verbose_name='Mots-clés')),
                ('nb_pubs_vues', models.PositiveIntegerField(
                    default=0,
                    verbose_name='Pubs vues (ad_archive_id distincts)')),
                ('extraits', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Extraits ([{texte ≤200, ad_archive_id}], ≤5)')),
                ('domaines', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Domaines ([{domaine, nb}])')),
                ('payeurs', models.JSONField(
                    blank=True, default=list, verbose_name='Payeurs UE')),
                ('ad_archive_id_exemple', models.CharField(
                    blank=True, default='', max_length=64,
                    verbose_name='Pub exemple (lien bibliothèque)')),
                ('classe', models.CharField(
                    choices=CLASSES, default='incertain', max_length=20,
                    verbose_name='Classe')),
                ('dropshipper_probable', models.CharField(
                    choices=TRI, default='incertain', max_length=10,
                    verbose_name='Dropshipper probable')),
                ('dropshipper_indices', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Indices dropshipper')),
                ('dropshipper_decide_par', models.CharField(
                    blank=True, choices=DECIDE_PAR, default='', max_length=8,
                    verbose_name='Dropshipper décidé par')),
                ('jeu', models.CharField(
                    blank=True, choices=JEUX, max_length=12, null=True,
                    verbose_name='Jeu de mesure (gelé)')),
                _company(),
                ('doublon_de', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='doublons', to='adsengine.veilleannonceur',
                    verbose_name='Doublon de')),
                ('jeu_decouverte', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='adsengine.veilledecouverte',
                    verbose_name='Découverte du tirage')),
            ],
            options={
                'verbose_name': 'Annonceur découvert (veille)',
                'verbose_name_plural': 'Annonceurs découverts (veille)',
                'ordering': ['page_name', 'id'],
                'constraints': [models.UniqueConstraint(
                    fields=('company', 'page_id'),
                    name='uniq_adseng_veilleannonceur')],
            },
        ),
        migrations.CreateModel(
            name='VeillePubVue',
            fields=[
                _id(), *_horodatage(),
                ('ad_archive_id', models.CharField(
                    max_length=64, verbose_name='ID de pub (archive)')),
                ('numero_page', models.PositiveIntegerField(
                    default=1, verbose_name='Numéro de page')),
                ('extrait', models.TextField(
                    blank=True, default='',
                    verbose_name='Extrait (≤ 500 caractères)')),
                ('legende', models.CharField(
                    blank=True, default='', max_length=500,
                    verbose_name='Légende du lien')),
                ('domaine', models.CharField(
                    blank=True, default='', max_length=255,
                    verbose_name='Domaine affiché')),
                ('titres', models.JSONField(
                    blank=True, default=list, verbose_name='Titres de lien')),
                ('langues', models.JSONField(
                    blank=True, default=list, verbose_name='Langues')),
                ('plateformes', models.JSONField(
                    blank=True, default=list, verbose_name='Plateformes')),
                ('payeurs', models.JSONField(
                    blank=True, default=list, verbose_name='Payeurs UE')),
                ('debut_diffusion', models.DateTimeField(
                    blank=True, null=True, verbose_name='Début de diffusion')),
                ('fin_diffusion', models.DateTimeField(
                    blank=True, null=True, verbose_name='Fin de diffusion')),
                ('pays_portee', models.JSONField(
                    blank=True, default=list, verbose_name='Pays de portée')),
                _company(),
                ('annonceur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pubs_vues', to='adsengine.veilleannonceur',
                    verbose_name='Annonceur')),
                ('requete', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pubs_vues', to='adsengine.veillerequete',
                    verbose_name='Requête')),
            ],
            options={
                'verbose_name': 'Pub vue (veille)',
                'verbose_name_plural': 'Pubs vues (veille)',
                'ordering': ['requete', 'numero_page', 'id'],
                'indexes': [models.Index(
                    fields=['company', 'ad_archive_id'],
                    name='adseng_veillepub_co_ad_idx')],
                'constraints': [models.UniqueConstraint(
                    fields=('company', 'requete', 'ad_archive_id'),
                    name='uniq_adseng_veillepub')],
            },
        ),
        migrations.CreateModel(
            name='VeilleVerdict',
            fields=[
                _id(), *_horodatage(),
                ('classe', models.CharField(
                    choices=CLASSES, max_length=20, verbose_name='Classe')),
                ('motif_fr', models.TextField(
                    blank=True, default='', verbose_name='Motif')),
                ('preuves', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Preuves ([{champ, valeur, ad_archive_id}])')),
                ('decide_par', models.CharField(
                    choices=DECIDE_PAR, max_length=8,
                    verbose_name='Décidé par')),
                ('modele', models.CharField(
                    blank=True, default='', max_length=80,
                    verbose_name='Modèle IA')),
                ('version_consigne', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Version de la consigne')),
                ('jetons_entree', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="Jetons d'entrée")),
                ('jetons_sortie', models.PositiveIntegerField(
                    blank=True, null=True, verbose_name='Jetons de sortie')),
                ('confiance', models.FloatField(
                    blank=True, null=True, verbose_name='Confiance (0..1)')),
                ('dropshipper', models.CharField(
                    choices=TRI, default='incertain', max_length=10,
                    verbose_name='Dropshipper')),
                ('dropshipper_indices', models.JSONField(
                    blank=True, default=list,
                    verbose_name='Indices dropshipper')),
                ('est_etiquette_mesure', models.BooleanField(
                    default=False, verbose_name='Étiquette de mesure')),
                ('jeu', models.CharField(
                    blank=True, choices=JEUX, max_length=12, null=True,
                    verbose_name='Jeu de mesure')),
                _company(),
                ('annonceur', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='verdicts', to='adsengine.veilleannonceur',
                    verbose_name='Annonceur')),
                ('auteur', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='adsengine_veille_verdicts',
                    to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
                ('doublon_de', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to='adsengine.veilleannonceur',
                    verbose_name='Doublon de')),
            ],
            options={
                'verbose_name': 'Verdict (veille)',
                'verbose_name_plural': 'Verdicts (veille)',
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(
                    fields=['company', 'annonceur', 'est_etiquette_mesure'],
                    name='adseng_veilleverd_co_an_idx')],
            },
        ),
        migrations.AddField(
            model_name='veilleannonceur',
            name='verdict_courant',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='adsengine.veilleverdict',
                verbose_name='Verdict courant'),
        ),
    ]
