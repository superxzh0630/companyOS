# Generated migration for adding Company model and multi-company support

from django.db import migrations, models
import django.db.models.deletion


def create_companies_and_migrate_data(apps, schema_editor):
    """Create companies and migrate existing departments and employees."""
    Company = apps.get_model('profiles', 'Company')
    Department = apps.get_model('profiles', 'Department')
    EmployeeProfile = apps.get_model('profiles', 'EmployeeProfile')
    
    # Create two companies
    tianjin = Company.objects.create(
        name='Tianjin Sunhoo',
        city_code='TJ',
        city_name='Tianjin'
    )
    
    shenyang = Company.objects.create(
        name='Shenyang Sunhoo',
        city_code='SY',
        city_name='Shenyang'
    )
    
    # Map to update existing departments with company and new codes
    department_mapping = {
        'HR': {'display_name': '人事部', 'new_code': 'HRTJ'},
        'TECH': {'display_name': '技术部', 'new_code': 'TECHTJ'},
        'MANU': {'display_name': '生产部', 'new_code': 'MANUTJ'},
        'FIN': {'display_name': '财务部', 'new_code': 'FINTJ'},
        'OPS': {'display_name': '运营部', 'new_code': 'OPSTJ'},
        'SALES': {'display_name': '销售部', 'new_code': 'SALESTJ'},
    }
    
    # Update existing departments
    for old_code, info in department_mapping.items():
        try:
            dept = Department.objects.get(code=old_code)
            dept.company_id = tianjin.id
            dept.display_name = info['display_name']
            dept.code = info['new_code']
            dept.save()
        except Department.DoesNotExist:
            pass
    
    # Update existing employees to link to Tianjin company
    EmployeeProfile.objects.all().update(company_id=tianjin.id)


def reverse_migration(apps, schema_editor):
    """Reverse the migration."""
    Company = apps.get_model('profiles', 'Company')
    Company.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0002_department_migrate_data'),
    ]

    operations = [
        # Create Company model
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Company Name')),
                ('city_code', models.CharField(max_length=10, unique=True, verbose_name='City Code')),
                ('city_name', models.CharField(max_length=50, verbose_name='City Name')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Company',
                'verbose_name_plural': 'Companies',
                'db_table': 'companies',
                'ordering': ['name'],
            },
        ),
        
        # Add display_name to Department (nullable initially)
        migrations.AddField(
            model_name='department',
            name='display_name',
            field=models.CharField(max_length=100, null=True, verbose_name='Display Name'),
        ),
        
        # Add company to Department (nullable initially)
        migrations.AddField(
            model_name='department',
            name='company',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='departments',
                to='profiles.company',
                verbose_name='Company'
            ),
        ),
        
        # Add company to EmployeeProfile (nullable initially)
        migrations.AddField(
            model_name='employeeprofile',
            name='company',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='employees',
                to='profiles.company',
                verbose_name='Company'
            ),
        ),
        
        # Run data migration
        migrations.RunPython(
            create_companies_and_migrate_data,
            reverse_migration
        ),
        
        # Make company and display_name non-nullable
        migrations.AlterField(
            model_name='department',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='departments',
                to='profiles.company',
                verbose_name='Company'
            ),
        ),
        
        migrations.AlterField(
            model_name='department',
            name='display_name',
            field=models.CharField(max_length=100, verbose_name='Display Name'),
        ),
        
        migrations.AlterField(
            model_name='employeeprofile',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='employees',
                to='profiles.company',
                verbose_name='Company'
            ),
        ),
        
        # Remove old name field uniqueness and update model
        migrations.AlterField(
            model_name='department',
            name='name',
            field=models.CharField(max_length=100, verbose_name='Department Name'),
        ),
        
        # Add unique together constraint
        migrations.AlterUniqueTogether(
            name='department',
            unique_together={('company', 'display_name')},
        ),
        
        # Update Meta ordering
        migrations.AlterModelOptions(
            name='department',
            options={
                'verbose_name': 'Department',
                'verbose_name_plural': 'Departments',
                'ordering': ['company', 'display_name']
            },
        ),
    ]
