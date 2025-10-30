from django import forms
from .models import Horario, Perfil
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model 
User = get_user_model()

class HorarioForm(forms.ModelForm):
    class Meta:
        model = Horario
        fields = ['dia', 'hora_inicio', 'hora_termino']
        widgets = {
            'dia': forms.Select(attrs={'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_termino': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

class RegistroForm(UserCreationForm):
    email = forms.EmailField(
        required=True, 
        label='Correo Electrónico'
    )
    
    fecha_nacimiento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Fecha de nacimiento",
        required=True
    )
   
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)
        
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            try:
                perfil = user.perfil
            except Perfil.DoesNotExist:
                perfil, _ = Perfil.objects.get_or_create(usuario=user)
            perfil.fecha_nacimiento = self.cleaned_data['fecha_nacimiento']
            perfil.save()
        return user

class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['fecha_nacimiento']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class UserEditForm(forms.ModelForm):
    email = forms.EmailField(required=True, label='Nuevo Correo Electrónico')
    class Meta:
        model = User
        fields = ['email']