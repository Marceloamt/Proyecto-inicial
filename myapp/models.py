from django.db import models
import random, string
from django.contrib.auth.models import User
from datetime import date
from django.db.models.signals import post_save
from django.dispatch import receiver
from django import forms

#🚨🚨🚨NO TOCAR NADA DE LO QUE YA ESTA HECHO A MENOS QUE SEA NECESARIO🚨🚨🚨

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE) 
    fecha_nacimiento = models.DateField(null=True, blank=True)

    def edad(self):
        if self.fecha_nacimiento:
            hoy = date.today()
            return hoy.year - self.fecha_nacimiento.year - (
                (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        return None
    
    def minutos_disponibles(self):
        #calcula el total de minutos disponibles sumando los bloques de Horario
        
        # Obtenemos los horarios del usuario actual que están marcados como disponibles
        horarios_query = self.usuario.horario_set.filter(disponible=True).annotate(
            # Calcula la diferencia entre hora_termino y hora_inicio
            duracion_td=ExpressionWrapper(
                F('hora_termino') - F('hora_inicio'),
                output_field=fields.DurationField()
            )
        )
        
        total_minutos = 0
        for horario in horarios_query:
            # Convertir la duración total a segundos y luego a minutos
            total_segundos = horario.duracion_td.total_seconds()
            total_minutos += int(total_segundos / 60)
            
        return total_minutos

    def __str__(self):
        return self.usuario.username

@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil(sender, instance, **kwargs):
    if hasattr(instance, 'perfil'):
        instance.perfil.save()

class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = ['fecha_nacimiento']
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
        }

class Familia(models.Model):
    nombre = models.CharField(max_length=100)
    jefe = models.OneToOneField(User, on_delete=models.CASCADE, related_name='familia_jefe')
    miembros = models.ManyToManyField(User, related_name='familias', blank=True)
    codigo_invitacion = models.CharField(max_length=8, unique=True, blank=True)

    def __str__(self):
        return f"Familia {self.nombre} (Jefe: {self.jefe.username})"

    def save(self, *args, **kwargs):
        """Genera un código de invitación único automáticamente al guardar."""
        if not self.codigo_invitacion:
            while True:
                codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                if not Familia.objects.filter(codigo_invitacion=codigo).exists():
                    self.codigo_invitacion = codigo
                    break
        super().save(*args, **kwargs)

    def generar_codigo(self):
        """Permite regenerar un nuevo código de invitación."""
        letras = string.ascii_uppercase + string.digits
        while True:
            codigo = ''.join(random.choices(letras, k=8))
            if not Familia.objects.filter(codigo_invitacion=codigo).exists():
                self.codigo_invitacion = codigo
                self.save()
                break


class Horario(models.Model):
    DIAS_SEMANA = [
        ('LUN', 'Lunes'),
        ('MAR', 'Martes'),
        ('MIE', 'Miércoles'),
        ('JUE', 'Jueves'),
        ('VIE', 'Viernes'),
        ('SAB', 'Sábado'),
        ('DOM', 'Domingo'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    dia = models.CharField(max_length=3, choices=DIAS_SEMANA)
    hora_inicio = models.TimeField()
    hora_termino = models.TimeField()
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.get_dia_display()} ({self.hora_inicio} a {self.hora_termino})"


class Tarea(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('hecha', 'Hecha'),
    ]

    nombre = models.CharField(max_length=100)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    familia = models.ForeignKey('Familia', on_delete=models.CASCADE, related_name='tareas', null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    # Tiempo y Restricción de Edad
    tiempo_requerido_minutos = models.IntegerField(
        default=30, 
        help_text="Tiempo estimado para completar la tarea (en minutos)."
    )
    requiere_edad_minima = models.BooleanField(
        default=False, 
        help_text="Marcar si esta tarea solo puede ser realizada por personas mayores a una edad específica."
    )
    edad_minima = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Edad mínima requerida para realizar la tarea (solo si requiere_edad_minima está marcado)."
    )

    def __str__(self):
        return f"{self.nombre} ({self.estado})"

    def asignar_aleatoriamente(self):
        """Asigna la tarea a un usuario aleatorio del sistema."""
        usuarios_disponibles = list(User.objects.all())
        if usuarios_disponibles:
            self.responsable = random.choice(usuarios_disponibles)
            self.save()