# Generated by Django 5.2 on 2025-06-04 10:38

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Bit', '0002_bit_is_accepted'),
        ('Tender', '0002_tender_files_uploaded_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='bit',
            unique_together={('created_by', 'tender')},
        ),
    ]
