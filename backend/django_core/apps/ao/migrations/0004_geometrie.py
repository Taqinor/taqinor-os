# AOF18 + AOF20 + AOF21 + AOF22 + AOF23 + AOF24 + AOF25 — GÉOMÉTRIE, PIÈCES du
# DCE, OBSTACLES, CHAÎNES DE COTES, RELEVÉS et QUESTIONS : ``ao_batiment``,
# ``ao_toiture``, ``ao_plan_source``, ``ao_piece_consultation``,
# ``ao_obstacle``, ``ao_chaine_cotes``, ``ao_releve``, ``ao_serie_questions``,
# ``ao_question``.
#
# Neuf tables NEUVES (aucun impact sur les tables ``compta_*`` héritées).
#
#   * AOF18 — enveloppe en repère LOCAL MÉTRIQUE (``contour_local_m``) : le nom
#     du champ porte l'unité ET l'ordre des axes (AOF19).
#   * AOF20 — ``PlanSource`` : les TROIS portes d'entrée sont UN CHAMP ; le
#     fichier passe par ``records.Attachment``, JAMAIS un ``FileField``.
#   * AOF21 — ``PieceConsultation`` : le DCE REÇU, additifs compris.
#   * AOF22 — ``ObstacleAO`` : la PROVENANCE pilote le dégagement ET le
#     caractère engageable ; ÉCARTÉ conserve la géométrie.
#   * AOF23 — ``ChaineCotes`` : fermeture, résidus (m et %), tolérance PAR
#     chaîne, statut de fiabilité porté par la DONNÉE.
#   * AOF24 — ``ReleveAO`` : la visite contradictoire devient un objet ;
#     obstacles et chaînes pointent le relevé qui les a produits.
#   * AOF25 — ``SerieQuestions``/``QuestionAO`` : le workflow Q/R sur documents
#     annotés. L'impact PRÉVISIONNEL en modules est la raison d'être d'une
#     question (trois séries ont fait passer un site réel de 512 à 618 modules
#     posables) : une question sans impact chiffré est refusée.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0003_projet_ao'),
        ('authentication', '0026_ntmob6_customuser_mobile_home_route'),
        ('records', '0013_vx210_snooze_trigger_event'),
    ]

    operations = [
        migrations.AddField(
            model_name='exigencecps',
            name='a_reverifier',
            field=models.BooleanField(default=False, verbose_name='À revérifier (additif reçu)'),
        ),
        migrations.CreateModel(
            name='BatimentAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code', models.CharField(max_length=30, verbose_name='Code du bâtiment')),
                ('designation', models.CharField(blank=True, default='', max_length=255, verbose_name='Désignation')),
                ('ordre', models.PositiveIntegerField(default=1, verbose_name='Ordre')),
                ('engagement_modules', models.PositiveIntegerField(blank=True, null=True, verbose_name='Engagement (modules)')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batiments', to='ao.appeloffre', verbose_name="Appel d'offres")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batiments_ao', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Bâtiment (AO)',
                'verbose_name_plural': 'Bâtiments (AO)',
                'db_table': 'ao_batiment',
                'ordering': ['appel_offre', 'ordre', 'code'],
            },
        ),
        migrations.CreateModel(
            name='PieceConsultation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('type_piece', models.CharField(choices=[('cps', 'CPS (cahier des prescriptions spéciales)'), ('reglement', 'Règlement de consultation'), ('plan_architecte', "Plan d'architecte"), ('modele_acte', "Modèle d'acte d'engagement"), ('bordereau_vierge', 'Bordereau des prix vierge'), ('additif', 'Additif / erratum'), ('autre', 'Autre pièce du DCE')], default='autre', max_length=20, verbose_name='Type de pièce')),
                ('reference', models.CharField(blank=True, default='', max_length=120, verbose_name='Référence')),
                ('version', models.CharField(blank=True, default='', max_length=40, verbose_name='Version reçue')),
                ('date_reception', models.DateField(blank=True, null=True, verbose_name='Date de réception')),
                ('pages_indexees', models.JSONField(blank=True, default=list, verbose_name='Pages indexées')),
                ('empreinte_sha256', models.CharField(blank=True, default='', max_length=64, verbose_name='Empreinte SHA-256')),
                ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pieces_consultation', to='ao.appeloffre', verbose_name="Appel d'offres")),
                ('attachment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pieces_consultation_ao', to='records.attachment', verbose_name='Fichier (MinIO)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pieces_consultation', to='authentication.company', verbose_name='Société')),
                ('modifie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='additifs', to='ao.piececonsultation', verbose_name='Pièce modifiée')),
            ],
            options={
                'verbose_name': 'Pièce du dossier de consultation',
                'verbose_name_plural': 'Pièces du dossier de consultation',
                'db_table': 'ao_piece_consultation',
                'ordering': ['appel_offre', 'type_piece', 'id'],
            },
        ),
        migrations.AddField(
            model_name='exigencecps',
            name='piece_consultation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='exigences', to='ao.piececonsultation', verbose_name='Pièce du DCE (document)'),
        ),
        migrations.CreateModel(
            name='ReleveAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date_visite', models.DateField(verbose_name='Date de la visite')),
                ('participants', models.TextField(blank=True, default='', verbose_name='Participants (un par ligne)')),
                ('contradictoire', models.BooleanField(default=False, verbose_name='Visite contradictoire')),
                ('conditions', models.TextField(blank=True, default='', verbose_name='Conditions (météo, accès, sécurité)')),
                ('notes', models.TextField(blank=True, default='', verbose_name='Notes')),
                ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='releves', to='ao.appeloffre', verbose_name="Appel d'offres")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='releves_ao', to='authentication.company', verbose_name='Société')),
                ('photos', models.ManyToManyField(blank=True, related_name='releves_ao', to='records.attachment', verbose_name='Photos')),
            ],
            options={
                'verbose_name': 'Relevé de toiture (AO)',
                'verbose_name_plural': 'Relevés de toiture (AO)',
                'db_table': 'ao_releve',
                'ordering': ['-date_visite', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ObstacleAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('repere', models.CharField(blank=True, default='', max_length=8, verbose_name='Repère (A, B, C…)')),
                ('designation', models.CharField(blank=True, default='', max_length=255, verbose_name='Désignation')),
                ('nature', models.CharField(choices=[('caisson_technique', 'Caisson technique'), ('cage_escalier', "Cage d'escalier"), ('edicule', 'Édicule'), ('souche', 'Souche'), ('groupe_clim', 'Groupe de climatisation'), ('acrotere', 'Acrotère'), ('joint_dilatation', 'Joint de dilatation'), ('muret', 'Muret'), ('decrochement_niveau', 'Décrochement de niveau'), ('pan_coupe', 'Pan coupé'), ('lanterneau', 'Lanterneau'), ('exutoire_fumee', 'Exutoire de fumée'), ('chemin_cables', 'Chemin de câbles')], default='caisson_technique', max_length=22, verbose_name='Nature')),
                ('rect_x0_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='x0 (m)')),
                ('rect_x1_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='x1 (m)')),
                ('rect_y0_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='y0 (m)')),
                ('rect_y1_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='y1 (m)')),
                ('polygone_local_m', models.JSONField(blank=True, default=list, verbose_name='Polygone local [x, y] en mètres')),
                ('hauteur_m', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Hauteur (m)')),
                ('provenance', models.CharField(choices=[('MESURE', 'Mesuré sur site'), ('MESURE_DOUTEUX', 'Mesuré, valeur douteuse'), ('PLAN', 'Lu sur plan (non relevé)'), ('DEVINE', 'Deviné (photo illisible)'), ('DECLARE_CLIENT', 'Déclaré par le client'), ('ECARTE', 'Écarté (hors compte)')], default='MESURE', max_length=16, verbose_name='Provenance')),
                ('degagement_m', models.DecimalField(decimal_places=2, default=Decimal('0.30'), max_digits=6, verbose_name='Dégagement (m)')),
                ('degagement_surcharge', models.BooleanField(default=False, verbose_name='Dégagement surchargé')),
                ('motif_surcharge', models.TextField(blank=True, default='', verbose_name='Motif de la surcharge')),
                ('regle_degagement', models.CharField(blank=True, default='', max_length=255, verbose_name='Règle de dégagement appliquée')),
                ('hors_zone_pv', models.BooleanField(default=False, verbose_name='Hors zone photovoltaïque')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('decision', models.TextField(blank=True, default='', verbose_name='Décision (écart / confirmation)')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='obstacles_ao', to='authentication.company', verbose_name='Société')),
                ('releve', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='obstacles', to='ao.releveao', verbose_name='Relevé')),
            ],
            options={
                'verbose_name': 'Obstacle de toiture (AO)',
                'verbose_name_plural': 'Obstacles de toiture (AO)',
                'db_table': 'ao_obstacle',
                'ordering': ['toiture', 'repere', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ChaineCotes',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('libelle', models.CharField(max_length=255, verbose_name='Libellé')),
                ('axe', models.CharField(choices=[('x', 'Axe X (longueur)'), ('y', 'Axe Y (largeur)'), ('oblique', 'Oblique / diagonale')], default='x', max_length=8, verbose_name='Axe')),
                ('segments', models.JSONField(blank=True, default=list, verbose_name='Segments')),
                ('mesure_totale_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Mesure totale (m)')),
                ('tolerance_m', models.DecimalField(decimal_places=3, default=Decimal('0.050'), max_digits=6, verbose_name='Tolérance (m)')),
                ('residu_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Résidu (m)')),
                ('residu_pct', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Résidu (%)')),
                ('verdict', models.CharField(choices=[('ok', 'Fermeture OK'), ('ecart', 'Écart de fermeture'), ('incomplete', 'Chaîne incomplète')], default='incomplete', max_length=12, verbose_name='Verdict')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chaines_cotes_ao', to='authentication.company', verbose_name='Société')),
                ('releve', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chaines_cotes', to='ao.releveao', verbose_name='Relevé')),
            ],
            options={
                'verbose_name': 'Chaîne de cotes (AO)',
                'verbose_name_plural': 'Chaînes de cotes (AO)',
                'db_table': 'ao_chaine_cotes',
                'ordering': ['toiture', 'axe', 'id'],
            },
        ),
        migrations.CreateModel(
            name='SerieQuestions',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('numero', models.PositiveIntegerField(default=1, verbose_name='Numéro')),
                ('date_envoi', models.DateField(blank=True, null=True, verbose_name="Date d'envoi")),
                ('canal', models.CharField(choices=[('email', 'Courriel'), ('whatsapp', 'WhatsApp'), ('courrier', 'Courrier'), ('reunion', 'Réunion'), ('autre', 'Autre')], default='email', max_length=10, verbose_name='Canal')),
                ('destinataire', models.CharField(blank=True, default='', max_length=255, verbose_name='Destinataire')),
                ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='series_questions', to='ao.appeloffre', verbose_name="Appel d'offres")),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='series_questions_ao', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Série de questions (AO)',
                'verbose_name_plural': 'Séries de questions (AO)',
                'db_table': 'ao_serie_questions',
                'ordering': ['appel_offre', 'numero'],
            },
        ),
        migrations.CreateModel(
            name='QuestionAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('repere', models.CharField(blank=True, default='', max_length=4, verbose_name="Repère sur l'image (A–K)")),
                ('texte', models.CharField(max_length=500, verbose_name='Question')),
                ('impact_min_modules', models.IntegerField(blank=True, null=True, verbose_name='Impact minimal (modules)')),
                ('impact_max_modules', models.IntegerField(blank=True, null=True, verbose_name='Impact maximal (modules)')),
                ('reponse', models.TextField(blank=True, default='', verbose_name='Réponse')),
                ('decision', models.TextField(blank=True, default='', verbose_name='Décision retenue')),
                ('date_decision', models.DateField(blank=True, null=True, verbose_name='Date de la décision')),
                ('statut', models.CharField(choices=[('posee', 'Posée'), ('repondue', 'Répondue'), ('tranchee', 'Tranchée'), ('sans_suite', 'Sans suite')], default='posee', max_length=12, verbose_name='Statut')),
                ('chaine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions', to='ao.chainecotes', verbose_name='Chaîne de cotes concernée')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions_ao', to='authentication.company', verbose_name='Société')),
                ('image', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions_ao', to='records.attachment', verbose_name='Image annotée')),
                ('obstacle', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='questions', to='ao.obstacleao', verbose_name='Obstacle concerné')),
                ('serie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='ao.seriequestions', verbose_name='Série')),
            ],
            options={
                'verbose_name': 'Question (AO)',
                'verbose_name_plural': 'Questions (AO)',
                'db_table': 'ao_question',
                'ordering': ['serie', 'repere', 'id'],
            },
        ),
        migrations.CreateModel(
            name='ToitureAO',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('code_document', models.CharField(blank=True, default='', max_length=20, verbose_name='Code de la planche (05H, 06H, 06I…)')),
                ('designation', models.CharField(blank=True, default='', max_length=255, verbose_name='Désignation')),
                ('forme', models.CharField(choices=[('rectangle', 'Rectangle'), ('polygone', 'Polygone'), ('forme_l', 'Forme en L'), ('arc', 'Arc / aile courbe')], default='rectangle', max_length=12, verbose_name='Forme')),
                ('contour_local_m', models.JSONField(blank=True, default=list, verbose_name='Contour local [x, y] en mètres')),
                ('angle_nord_deg', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Azimut du repère local vs Nord (°)')),
                ('rayon_ext_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Rayon extérieur (m)')),
                ('largeur_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Largeur de la bande (m)')),
                ('arc_segments', models.JSONField(blank=True, default=list, verbose_name="Segments de l'arc (découpage)")),
                ('murets', models.JSONField(blank=True, default=list, verbose_name='Murets / refends')),
                ('niveau', models.IntegerField(default=0, verbose_name='Niveau')),
                ('altitude_m', models.DecimalField(blank=True, decimal_places=3, max_digits=8, null=True, verbose_name='Altitude / hauteur du plan (m)')),
                ('type_couverture', models.CharField(choices=[('bac_acier', 'Bac acier'), ('dalle_beton', 'Dalle béton'), ('tuile', 'Tuile'), ('membrane', 'Membrane / étanchéité'), ('fibrociment', 'Fibrociment'), ('autre', 'Autre')], default='autre', max_length=14, verbose_name='Type de couverture')),
                ('contraintes_structure', models.TextField(blank=True, default='', verbose_name='Contraintes de structure')),
                ('surface_m2', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12, verbose_name='Surface calculée (m²)')),
                ('batiment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='toitures', to='ao.batimentao', verbose_name='Bâtiment')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='toitures_ao', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Toiture (AO)',
                'verbose_name_plural': 'Toitures (AO)',
                'db_table': 'ao_toiture',
                'ordering': ['batiment', 'code_document', 'id'],
            },
        ),
        migrations.AddField(
            model_name='releveao',
            name='toitures',
            field=models.ManyToManyField(blank=True, related_name='releves', to='ao.toitureao', verbose_name='Toitures couvertes'),
        ),
        migrations.CreateModel(
            name='PlanSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('origine', models.CharField(choices=[('plan_fourni', 'Plan fourni (PDF/DXF/image)'), ('trace_manuel', 'Tracé manuel'), ('carte', 'Reprise depuis une carte')], default='plan_fourni', max_length=14, verbose_name="Porte d'entrée")),
                ('type_fichier', models.CharField(choices=[('pdf', 'PDF'), ('dxf', 'DXF'), ('image', 'Image'), ('aucun', 'Aucun fichier')], default='aucun', max_length=8, verbose_name='Type de fichier')),
                ('page', models.PositiveIntegerField(default=1, verbose_name='Page')),
                ('calib_point_a_px', models.JSONField(blank=True, default=list, verbose_name='Point A [x, y] en pixels')),
                ('calib_point_b_px', models.JSONField(blank=True, default=list, verbose_name='Point B [x, y] en pixels')),
                ('calib_distance_reelle_m', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Distance réelle A→B (m)')),
                ('echelle_m_par_px', models.DecimalField(blank=True, decimal_places=8, max_digits=14, null=True, verbose_name='Échelle (m/px)')),
                ('origine_px', models.JSONField(blank=True, default=list, verbose_name='Origine du repère [x, y] en pixels')),
                ('rotation_deg', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6, verbose_name='Rotation (°)')),
                ('miroir_x', models.BooleanField(default=False, verbose_name='Miroir X')),
                ('miroir_y', models.BooleanField(default=False, verbose_name='Miroir Y')),
                ('empreinte_sha256', models.CharField(blank=True, default='', max_length=64, verbose_name='Empreinte SHA-256 du fichier')),
                ('etat', models.CharField(choices=[('brut', 'Brut (non calibré)'), ('calibre', 'Calibré'), ('vectorise', 'Vectorisé')], default='brut', max_length=10, verbose_name='État')),
                ('fourni_par', models.CharField(blank=True, default='', max_length=255, verbose_name='Fourni par')),
                ('attachment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='plans_source_ao', to='records.attachment', verbose_name='Fichier (MinIO)')),
                ('batiment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='plans_source', to='ao.batimentao', verbose_name='Bâtiment')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plans_source_ao', to='authentication.company', verbose_name='Société')),
                ('piece_consultation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='plans_source', to='ao.piececonsultation', verbose_name='Pièce du DCE')),
                ('toiture', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='plans_source', to='ao.toitureao', verbose_name='Toiture')),
            ],
            options={
                'verbose_name': 'Support de plan (AO)',
                'verbose_name_plural': 'Supports de plan (AO)',
                'db_table': 'ao_plan_source',
                'ordering': ['toiture', 'batiment', 'id'],
            },
        ),
        migrations.AddField(
            model_name='obstacleao',
            name='toiture',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='obstacles', to='ao.toitureao', verbose_name='Toiture'),
        ),
        migrations.AddField(
            model_name='chainecotes',
            name='toiture',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chaines_cotes', to='ao.toitureao', verbose_name='Toiture'),
        ),
        migrations.AddIndex(
            model_name='batimentao',
            index=models.Index(fields=['company', 'appel_offre'], name='ao_batiment_company_974dc7_idx'),
        ),
        migrations.AddConstraint(
            model_name='batimentao',
            constraint=models.UniqueConstraint(fields=('company', 'appel_offre', 'code'), name='uniq_batiment_ao_code'),
        ),
        migrations.AddIndex(
            model_name='piececonsultation',
            index=models.Index(fields=['company', 'appel_offre'], name='ao_piece_co_company_86e73a_idx'),
        ),
        migrations.AddIndex(
            model_name='piececonsultation',
            index=models.Index(fields=['company', 'empreinte_sha256'], name='ao_piece_co_company_978b55_idx'),
        ),
        migrations.AddIndex(
            model_name='seriequestions',
            index=models.Index(fields=['company', 'appel_offre'], name='ao_serie_qu_company_c8c30c_idx'),
        ),
        migrations.AddConstraint(
            model_name='seriequestions',
            constraint=models.UniqueConstraint(fields=('company', 'appel_offre', 'numero'), name='uniq_serie_questions_numero'),
        ),
        migrations.AddIndex(
            model_name='questionao',
            index=models.Index(fields=['company', 'serie'], name='ao_question_company_f43a99_idx'),
        ),
        migrations.AddIndex(
            model_name='questionao',
            index=models.Index(fields=['company', 'statut'], name='ao_question_company_017c6e_idx'),
        ),
        migrations.AddIndex(
            model_name='toitureao',
            index=models.Index(fields=['company', 'batiment'], name='ao_toiture_company_128213_idx'),
        ),
        migrations.AddIndex(
            model_name='releveao',
            index=models.Index(fields=['company', 'appel_offre'], name='ao_releve_company_32ba29_idx'),
        ),
        migrations.AddIndex(
            model_name='plansource',
            index=models.Index(fields=['company', 'toiture'], name='ao_plan_sou_company_4981b3_idx'),
        ),
        migrations.AddIndex(
            model_name='plansource',
            index=models.Index(fields=['company', 'empreinte_sha256'], name='ao_plan_sou_company_77f0d6_idx'),
        ),
        migrations.AddIndex(
            model_name='obstacleao',
            index=models.Index(fields=['company', 'toiture'], name='ao_obstacle_company_cd2831_idx'),
        ),
        migrations.AddIndex(
            model_name='obstacleao',
            index=models.Index(fields=['company', 'provenance'], name='ao_obstacle_company_aed528_idx'),
        ),
        migrations.AddIndex(
            model_name='chainecotes',
            index=models.Index(fields=['company', 'toiture'], name='ao_chaine_c_company_b9e11c_idx'),
        ),
    ]
