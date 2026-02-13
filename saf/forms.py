from django import forms


class DspaceLinksUploadForm(forms.Form):
    links_file = forms.FileField(
        label="Archivo de enlaces (JSON)",
        help_text='JSON con enlaces por NRO. Ej: {"001": "https://.../handle/20.500.../123"}',
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "application/json"}),
    )
