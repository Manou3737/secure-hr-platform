from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0004_migrate_employee_references"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        DROP INDEX IF EXISTS
                        employees_employeeprofile_department_id_35cae182;

                        DROP INDEX IF EXISTS
                        employees_employeeprofile_position_ref_id_a2ccf81c;

                        DROP INDEX IF EXISTS
                        employees_employeeprofile_position_id_d63e751a;

                        ALTER TABLE employees_employeeprofile
                        DROP COLUMN department;

                        ALTER TABLE employees_employeeprofile
                        DROP COLUMN job_title;

                        ALTER TABLE employees_employeeprofile
                        RENAME COLUMN department_ref_id TO department_id;

                        ALTER TABLE employees_employeeprofile
                        RENAME COLUMN position_ref_id TO position_id;

                        CREATE INDEX
                        employees_employeeprofile_department_id_35cae182
                        ON employees_employeeprofile (department_id);

                        CREATE INDEX
                        employees_employeeprofile_position_id_d63e751a
                        ON employees_employeeprofile (position_id);
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name="employeeprofile",
                    name="department",
                ),
                migrations.RemoveField(
                    model_name="employeeprofile",
                    name="job_title",
                ),
                migrations.RenameField(
                    model_name="employeeprofile",
                    old_name="department_ref",
                    new_name="department",
                ),
                migrations.RenameField(
                    model_name="employeeprofile",
                    old_name="position_ref",
                    new_name="position",
                ),
                migrations.AlterField(
                    model_name="employeeprofile",
                    name="department",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_profiles",
                        to="employees.department",
                    ),
                ),
                migrations.AlterField(
                    model_name="employeeprofile",
                    name="position",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="employee_profiles",
                        to="employees.position",
                    ),
                ),
            ],
        ),
    ]
