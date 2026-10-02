"""Create stores and associate existing products with a legacy store."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_existing_products(apps, schema_editor):
    """Preserve pre-existing products when store becomes mandatory."""
    Product = apps.get_model('eCommerce', 'Product')
    Store = apps.get_model('eCommerce', 'Store')
    if not Product.objects.using(schema_editor.connection.alias).exists():
        return
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    db = schema_editor.connection.alias
    owner = User.objects.using(db).filter(is_superuser=True).first()
    if owner is None:
        owner = User.objects.using(db).first()
    if owner is None:
        username = 'legacy_store_owner'
        suffix = 1
        while User.objects.using(db).filter(username=username).exists():
            username = f'legacy_store_owner_{suffix}'
            suffix += 1
        owner = User.objects.using(db).create(
            username=username,
            password='!',  # Django treats this as an unusable password.
            is_active=False,
        )
    store = Store.objects.using(db).create(
        owner_id=owner.pk, name='Imported Products'
    )
    Product.objects.using(db).filter(store__isnull=True).update(store_id=store.pk)


class Migration(migrations.Migration):
    """Apply the 0002 stores database schema changes."""
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('eCommerce', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Store',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stores', to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name='store',
            constraint=models.UniqueConstraint(
                fields=('owner', 'name'), name='unique_vendor_store_name'
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='store',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='products', to='eCommerce.store',
            ),
        ),
        migrations.RunPython(assign_existing_products, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='product',
            name='store',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='products', to='eCommerce.store',
            ),
        ),
    ]
