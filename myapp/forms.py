from django import forms
# Asumo que DIAS_SEMANA_CHOICES está disponible en models.py o se pasa aquí
from .models import Horario, Perfil, Tarea, Familia, DIAS_SEMANA_CHOICES # Se agrega Familia
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model 
from django.db.models import Q # Importado para futuros filtros
User = get_user_model()

# --- Horario Form ---
class HorarioForm(forms.ModelForm):
    class Meta:
        model = Horario
        fields = ['dia', 'hora_inicio', 'hora_termino']
        widgets = {
            'dia': forms.Select(attrs={'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'hora_termino': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

# --- Registro Form ---
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
                # Si el perfil no existe 
                perfil, _ = Perfil.objects.get_or_create(usuario=user) 
            perfil.fecha_nacimiento = self.cleaned_data['fecha_nacimiento']
            perfil.save()
        return user

# --- Perfil Form ---
class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['fecha_nacimiento']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

# --- User Edit Form ---
class UserEditForm(forms.ModelForm):
    email = forms.EmailField(required=True, label='Nuevo Correo Electrónico')
    class Meta:
        model = User
        fields = ['email']

# --- Tarea Form ---
class TareaForm(forms.ModelForm):
    
    # Campo extra para manejar la recurrencia con checkboxes
    dias_recurrencia_form = forms.MultipleChoiceField(
        choices=DIAS_SEMANA_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Días de la semana que se debe realizar"
    )
    
    def __init__(self, *args, **kwargs):
        
        # 🚨 PASO 1: Extraer el usuario que fue pasado desde la vista
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs)
        
        # 🚨 PASO 2: Filtrado del campo 'familia'
        if user and user.is_authenticated and 'familia' in self.fields:
            # Filtra el queryset de 'familia' para mostrar SOLO aquellas donde el usuario es el jefe.
            self.fields['familia'].queryset = Familia.objects.filter(jefe=user)

        # Inicialización: Cargar la cadena CSV del modelo a los checkboxes
        if self.instance.pk and self.instance.dias_recurrencia_csv:
            initial_days = self.instance.dias_recurrencia_csv.split(',')
            self.fields['dias_recurrencia_form'].initial = initial_days

    def clean(self):
        cleaned_data = super().clean()
        requiere_edad_minima = cleaned_data.get("requiere_edad_minima")
        edad_minima = cleaned_data.get("edad_minima")

        # Validación 1: Edad mínima
        if requiere_edad_minima and (edad_minima is None or edad_minima <= 0):
            self.add_error('edad_minima', 'Debes ingresar una edad mínima válida si marcas la restricción.')
    
        # Validación 2: Tiempo requerido
        tiempo = cleaned_data.get("tiempo_requerido_minutos")
        if tiempo is not None and tiempo <= 0:
             self.add_error('tiempo_requerido_minutos', 'El tiempo requerido debe ser un valor positivo.')

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Guardado: Convertir los checkboxes a la cadena CSV del modelo
        selected_days = self.cleaned_data.get('dias_recurrencia_form')
        if selected_days:
            instance.dias_recurrencia_csv = ','.join(selected_days)
        else:
            instance.dias_recurrencia_csv = "" # Guardamos cadena vacía en CharField
        
        if commit:
            instance.save()
        return instance

    class Meta:
        model = Tarea
        fields = [
            'nombre', 
            'familia',       
            'estado',           
            'tiempo_requerido_minutos', 
            'requiere_edad_minima', 
            'edad_minima',
            'dias_recurrencia_csv', # Ocultamos este campo, ya que se llena desde dias_recurrencia_form
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'familia': forms.HiddenInput(),
            'estado': forms.HiddenInput(),
            'tiempo_requerido_minutos': forms.NumberInput(attrs={'class': 'form-control', 'min': 10, 'placeholder': 'Tiempo en minutos'}),
            'requiere_edad_minima': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'edad_minima': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Edad mínima'}),
            'dias_recurrencia_csv': forms.HiddenInput(), # Campo oculto
        }