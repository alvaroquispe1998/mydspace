import re

from django import forms
from django.conf import settings
from django.db.models import Q

from appconfig.models import CareerConfig
from registry.models import ThesisFile, ThesisRecord

ORCID_RE = re.compile(r"^https?://orcid\.org/\d{4}-\d{4}-\d{4}-\d{4}$", re.IGNORECASE)


class CareerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.carrera_excel


class ThesisRecordForm(forms.ModelForm):
    career = CareerChoiceField(
        queryset=CareerConfig.objects.all(),
        label="Carrera",
        empty_label="Selecciona una carrera",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        expected_dni = int(getattr(settings, "THESIS_DNI_DEFAULT_LENGTH", 8))
        dni_attrs = {
            "inputmode": "numeric",
            "pattern": r"\d*",
            "maxlength": str(expected_dni),
            # Guardrail client-side (no reemplaza validacion server-side).
            "oninput": "this.value=this.value.replace(/\\D/g,'');",
        }

        qs = self.fields["career"].queryset.filter(active=True).order_by("carrera_excel")
        if self.instance and self.instance.pk and self.instance.career_id:
            qs = self.fields["career"].queryset.filter(
                Q(active=True) | Q(pk=self.instance.career_id)
            ).order_by("carrera_excel")
        self.fields["career"].queryset = qs
        self.fields["career"].help_text = "Selecciona la escuela profesional."

        # Etiquetas y ayudas orientadas a usuario final
        self.fields["titulo"].label = "Título de la tesis"
        self.fields["titulo"].widget.attrs["placeholder"] = "Ej.: Influencia de..."

        self.fields["autor1_nombre"].label = "Autor 1: Apellidos, Nombres"
        self.fields["autor1_nombre"].help_text = "Formato: Apellidos, Nombres"
        self.fields["autor1_nombre"].widget.attrs["placeholder"] = "PEREZ GOMEZ, JUAN CARLOS"
        self.fields["autor1_dni"].label = "Autor 1: DNI"
        self.fields["autor1_dni"].widget.attrs["placeholder"] = "12345678"
        self.fields["autor1_dni"].widget.attrs.update(dni_attrs)

        self.fields["autor2_nombre"].label = "Autor 2: Apellidos, Nombres"
        self.fields["autor2_nombre"].help_text = "Opcional. Formato: Apellidos, Nombres"
        self.fields["autor2_dni"].label = "Autor 2: DNI"
        self.fields["autor2_dni"].widget.attrs.update(dni_attrs)
        self.fields["autor3_nombre"].label = "Autor 3: Apellidos, Nombres"
        self.fields["autor3_nombre"].help_text = "Opcional. Formato: Apellidos, Nombres"
        self.fields["autor3_dni"].label = "Autor 3: DNI"
        self.fields["autor3_dni"].widget.attrs.update(dni_attrs)

        self.fields["asesor_nombre"].label = "Asesor: Apellidos, Nombres"
        self.fields["asesor_nombre"].help_text = "Formato: Apellidos, Nombres"
        self.fields["asesor_nombre"].widget.attrs["placeholder"] = "RAMIREZ QUISPE, ANA MARIA"
        self.fields["asesor_dni"].label = "Asesor: DNI"
        self.fields["asesor_dni"].widget.attrs.update(dni_attrs)
        self.fields["asesor_orcid"].label = "Asesor: ORCID"
        self.fields["asesor_orcid"].widget.attrs["placeholder"] = "https://orcid.org/0000-0000-0000-0000"

        self.fields["jurado1"].label = "Jurado 1: Apellidos, Nombres"
        self.fields["jurado1"].help_text = "Formato: Apellidos, Nombres"
        self.fields["jurado2"].label = "Jurado 2: Apellidos, Nombres"
        self.fields["jurado2"].help_text = "Opcional. Formato: Apellidos, Nombres"
        self.fields["jurado3"].label = "Jurado 3: Apellidos, Nombres"
        self.fields["jurado3"].help_text = "Opcional. Formato: Apellidos, Nombres"

        self.fields["resumen"].label = "Resumen"
        self.fields["keywords_raw"].label = "Palabras clave"
        self.fields["keywords_raw"].help_text = "Separar por ; , | o salto de línea."

    @staticmethod
    def _validate_person_name(value: str, label: str):
        value = (value or "").strip()
        if not value:
            return
        if "," not in value:
            raise forms.ValidationError(f"{label} debe estar en formato 'Apellidos, Nombres'.")
        left, right = [p.strip() for p in value.split(",", 1)]
        if not left or not right:
            raise forms.ValidationError(f"{label} debe incluir apellidos y nombres separados por coma.")

    def clean(self):
        cleaned = super().clean()

        for f in ["autor1_dni", "autor2_dni", "autor3_dni", "asesor_dni"]:
            val = (cleaned.get(f) or "").strip()
            if not val:
                continue
            if not val.isdigit():
                self.add_error(f, "Debe contener solo digitos.")

        asesor_orcid = (cleaned.get("asesor_orcid") or "").strip()
        if asesor_orcid and not ORCID_RE.match(asesor_orcid):
            self.add_error("asesor_orcid", "Formato invalido. Ej: https://orcid.org/0000-0000-0000-0000")

        # Formato "Apellidos, Nombres"
        for f in ["autor1_nombre", "autor2_nombre", "autor3_nombre", "asesor_nombre", "jurado1", "jurado2", "jurado3"]:
            try:
                self._validate_person_name(cleaned.get(f, ""), self.fields[f].label)
            except forms.ValidationError as exc:
                self.add_error(f, exc)

        # Coherencia autor2/autor3: nombre + dni deben ir juntos
        for idx in [2, 3]:
            nombre = (cleaned.get(f"autor{idx}_nombre") or "").strip()
            dni = (cleaned.get(f"autor{idx}_dni") or "").strip()
            if nombre or dni:
                if not nombre:
                    self.add_error(f"autor{idx}_nombre", f"Completa autor {idx}: Apellidos, Nombres.")
                if not dni:
                    self.add_error(f"autor{idx}_dni", f"Completa autor {idx}: DNI.")

        autor2_nombre = (cleaned.get("autor2_nombre") or "").strip()
        autor2_dni = (cleaned.get("autor2_dni") or "").strip()
        autor3_nombre = (cleaned.get("autor3_nombre") or "").strip()
        autor3_dni = (cleaned.get("autor3_dni") or "").strip()
        if (autor3_nombre or autor3_dni) and not (autor2_nombre or autor2_dni):
            self.add_error("autor2_nombre", "Completa primero Autor 2 antes de registrar Autor 3.")

        jurado2 = (cleaned.get("jurado2") or "").strip()
        jurado3 = (cleaned.get("jurado3") or "").strip()
        if jurado3 and not jurado2:
            self.add_error("jurado2", "Completa primero Jurado 2 antes de registrar Jurado 3.")

        asesor_nombre = (cleaned.get("asesor_nombre") or "").strip()
        asesor_dni = (cleaned.get("asesor_dni") or "").strip()
        asesor_orcid = (cleaned.get("asesor_orcid") or "").strip()
        if asesor_dni and not asesor_nombre:
            self.add_error("asesor_nombre", "Si registras DNI del asesor, completa también Apellidos, Nombres.")
        if asesor_orcid and not asesor_nombre:
            self.add_error("asesor_nombre", "Si registras ORCID del asesor, completa también Apellidos, Nombres.")

        return cleaned

    class Meta:
        model = ThesisRecord
        fields = [
            "career",
            "titulo",
            "autor1_nombre",
            "autor1_dni",
            "autor2_nombre",
            "autor2_dni",
            "autor3_nombre",
            "autor3_dni",
            "asesor_nombre",
            "asesor_dni",
            "asesor_orcid",
            "jurado1",
            "jurado2",
            "jurado3",
            "resumen",
            "keywords_raw",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "autor1_nombre": forms.TextInput(attrs={"class": "form-control"}),
            "autor1_dni": forms.TextInput(attrs={"class": "form-control"}),
            "autor2_nombre": forms.TextInput(attrs={"class": "form-control"}),
            "autor2_dni": forms.TextInput(attrs={"class": "form-control"}),
            "autor3_nombre": forms.TextInput(attrs={"class": "form-control"}),
            "autor3_dni": forms.TextInput(attrs={"class": "form-control"}),
            "asesor_nombre": forms.TextInput(attrs={"class": "form-control"}),
            "asesor_dni": forms.TextInput(attrs={"class": "form-control"}),
            "asesor_orcid": forms.TextInput(attrs={"class": "form-control"}),
            "jurado1": forms.TextInput(attrs={"class": "form-control"}),
            "jurado2": forms.TextInput(attrs={"class": "form-control"}),
            "jurado3": forms.TextInput(attrs={"class": "form-control"}),
            "resumen": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "keywords_raw": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Separar por ; o , o |"}
            ),
        }


class ThesisFileUploadForm(forms.Form):
    file_type = forms.ChoiceField(choices=ThesisFile.FILE_TYPES, widget=forms.Select(attrs={"class": "form-select"}))
    file = forms.FileField(widget=forms.FileInput(attrs={"class": "form-control"}))

    def clean(self):
        cleaned = super().clean()
        ftype = cleaned.get("file_type")
        file = cleaned.get("file")
        if not file:
            return cleaned
        name = file.name.lower()
        if ftype == ThesisFile.TYPE_TESIS_DOCX and not name.endswith(".docx"):
            self.add_error("file", "Para tesis_docx debe subir .docx")
        if ftype in [ThesisFile.TYPE_TESIS_PDF, ThesisFile.TYPE_FORMULARIO, ThesisFile.TYPE_TURNITIN] and not name.endswith(
            ".pdf"
        ):
            self.add_error("file", "Este tipo requiere archivo .pdf")
        return cleaned


class AuditCommentForm(forms.Form):
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Comentario de auditoría"}),
    )
