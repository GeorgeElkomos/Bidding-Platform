# Generated by Django 5.2.1 on 2025-05-28 08:00

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Tender', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tender_files',
            name='Uploaded_At',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
