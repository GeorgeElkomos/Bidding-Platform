# Generated by Django 5.2.1 on 2025-05-28 11:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Bit', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='bit',
            name='Is_Accepted',
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
