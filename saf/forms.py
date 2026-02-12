from django import forms

from registry.models import ThesisRecord


class BatchCreateForm(forms.Form):
    records = forms.ModelMultipleChoiceField(
        queryset=ThesisRecord.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Registros aprobados",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["records"].queryset = ThesisRecord.objects.filter(status=ThesisRecord.STATUS_APROBADO).order_by("nro")
