import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from appconfig.models import CareerConfig, LicenseVersion, SystemConfig

User = get_user_model()


class Command(BaseCommand):
    help = "Carga configuracion inicial de carreras, parametros y usuario auditor."

    def add_arguments(self, parser):
        parser.add_argument("--career-map", default="career_map.csv", help="Ruta al career_map.csv")
        parser.add_argument("--auditor-user", default="auditor")
        parser.add_argument("--auditor-pass", default="Auditor123!")
        parser.add_argument("--skip-user", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["career_map"])
        if not path.exists():
            raise CommandError(f"No existe archivo: {path}")

        created = 0
        updated = 0
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                carrera_norm = (row.get("carrera_norm") or "").strip()
                if not carrera_norm:
                    continue
                defaults = {
                    "carrera_excel": (row.get("carrera_excel") or "").strip(),
                    "facultad": (row.get("facultad") or "").strip(),
                    "handle": (row.get("handle") or "").strip(),
                    "thesis_degree_name": (row.get("thesis_degree_name") or "").strip(),
                    "thesis_degree_discipline": (row.get("thesis_degree_discipline") or "").strip(),
                    "thesis_degree_grantor": (row.get("thesis_degree_grantor") or "").strip(),
                    "renati_level": (row.get("renati_level") or "").strip(),
                    "renati_discipline": (row.get("renati_discipline") or "").strip(),
                    "ocde_url": (row.get("ocde_url") or "").strip(),
                    "active": True,
                }
                obj, was_created = CareerConfig.objects.update_or_create(carrera_norm=carrera_norm, defaults=defaults)
                if was_created:
                    created += 1
                else:
                    updated += 1
                self.stdout.write(f"- {obj.carrera_norm} ({'new' if was_created else 'updated'})")

        if not options["skip_user"]:
            username = options["auditor_user"]
            password = options["auditor_pass"]
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={"role": User.ROLE_AUDITOR, "is_staff": True, "is_superuser": True},
            )
            if was_created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Usuario auditor creado: {username} / {password}"))
            else:
                self.stdout.write(f"Usuario {username} ya existe.")

        if not SystemConfig.objects.filter(key="INCLUDE_TURNITIN").exists():
            SystemConfig.objects.create(
                key="INCLUDE_TURNITIN",
                value="1",
                description="1=turnitin obligatorio para envio/aprobacion",
            )
        if not LicenseVersion.objects.exists():
            license_file = Path("license.txt")
            if license_file.exists():
                license_text = license_file.read_text(encoding="utf-8")
            else:
                license_text = "PLACEHOLDER LICENSE TEXT"
            LicenseVersion.objects.create(
                name="Licencia Inicial",
                version="1",
                text_content=license_text,
                is_active=True,
            )

        self.stdout.write(self.style.SUCCESS(f"Carreras creadas: {created} | actualizadas: {updated}"))
