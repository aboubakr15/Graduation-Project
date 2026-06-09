from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_coursechartroomessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseoffering',
            name='is_chat_active',
            field=models.BooleanField(default=True),
        ),
    ]
