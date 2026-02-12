from django import forms

from appconfig.models import CareerConfig, LicenseVersion, SystemConfig


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
