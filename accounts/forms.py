from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )


class UserUpsertForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña (solo crear o cambiar)",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "is_active"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        raw_password = self.cleaned_data.get("password", "").strip()
        if raw_password:
            user.set_password(raw_password)
        if commit:
            user.save()
        return user
