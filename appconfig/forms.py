import re

from django import forms

from appconfig.models import AdvisorConfig, CareerConfig, JuryMemberConfig, LicenseVersion, SystemConfig

ORCID_RE = re.compile(r"^https?://orcid\.org/\d{4}-\d{4}-\d{4}-\d{4}$", re.IGNORECASE)


def _validate_person_name(value: str, label: str):
    value = (value or "").strip()
    if not value:
        return
    if "," not in value:
        raise forms.ValidationError(f"{label} debe estar en formato 'Apellidos, Nombres'.")
    left, right = [p.strip() for p in value.split(",", 1)]
    if not left or not right:
        raise forms.ValidationError(f"{label} debe incluir apellidos y nombres separados por coma.")


class CareerConfigForm(forms.ModelForm):
    class Meta:
        model = CareerConfig
        fields = [
            "carrera_excel",
            "carrera_norm",
            "facultad",
            "handle",
            "thesis_degree_name",
            "thesis_degree_discipline",
            "thesis_degree_grantor",
            "renati_level",
            "renati_discipline",
            "ocde_url",
            "active",
        ]
        widgets = {
            "carrera_excel": forms.TextInput(attrs={"class": "form-control"}),
            "carrera_norm": forms.TextInput(attrs={"class": "form-control"}),
            "facultad": forms.TextInput(attrs={"class": "form-control"}),
            "handle": forms.TextInput(attrs={"class": "form-control"}),
            "thesis_degree_name": forms.TextInput(attrs={"class": "form-control"}),
            "thesis_degree_discipline": forms.TextInput(attrs={"class": "form-control"}),
            "thesis_degree_grantor": forms.TextInput(attrs={"class": "form-control"}),
            "renati_level": forms.TextInput(attrs={"class": "form-control"}),
            "renati_discipline": forms.TextInput(attrs={"class": "form-control"}),
            "ocde_url": forms.TextInput(attrs={"class": "form-control"}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class LicenseVersionForm(forms.ModelForm):
    class Meta:
        model = LicenseVersion
        fields = ["name", "version", "text_content", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "version": forms.TextInput(attrs={"class": "form-control"}),
            "text_content": forms.Textarea(attrs={"class": "form-control", "rows": 12}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SystemConfigForm(forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = ["key", "value", "description"]
        widgets = {
            "key": forms.TextInput(attrs={"class": "form-control"}),
            "value": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
        }


class AdvisorConfigForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        nombre = (cleaned.get("nombre") or "").strip()
        if nombre:
            _validate_person_name(nombre, "Nombre")
        dni = (cleaned.get("dni") or "").strip()
        if dni and not dni.isdigit():
            self.add_error("dni", "Debe contener solo digitos.")
        orcid = (cleaned.get("orcid") or "").strip()
        if orcid and not ORCID_RE.match(orcid):
            self.add_error("orcid", "Formato invalido. Ej: https://orcid.org/0000-0000-0000-0000")
        return cleaned

    class Meta:
        model = AdvisorConfig
        fields = ["nombre", "dni", "orcid", "active"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "dni": forms.TextInput(attrs={"class": "form-control"}),
            "orcid": forms.TextInput(attrs={"class": "form-control"}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class JuryMemberConfigForm(forms.ModelForm):
    def clean(self):
        cleaned = super().clean()
        nombre = (cleaned.get("nombre") or "").strip()
        if nombre:
            _validate_person_name(nombre, "Nombre")
        dni = (cleaned.get("dni") or "").strip()
        if dni and not dni.isdigit():
            self.add_error("dni", "Debe contener solo digitos.")
        return cleaned

    class Meta:
        model = JuryMemberConfig
        fields = ["nombre", "dni", "active"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "dni": forms.TextInput(attrs={"class": "form-control"}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
