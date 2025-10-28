from django.db import models
import random, string
from django.contrib.auth.models import User

class Familia(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    jefe = models.OneToOneField(User, on_delete=models.CASCADE, related_name='familia_jefe')
    miembros = models.ManyToManyField(User, related_name='familias', blank=True)
    codigo_invitacion = models.CharField(max_length=8, unique=True, blank=True)

    def __str__(self):
        return f"Familia {self.nombre} (Jefe: {self.jefe.username})"

    def save(self, *args, **kwargs):
        if not self.codigo_invitacion:
            self.codigo_invitacion = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    def generar_codigo(self):
        letras = string.ascii_uppercase + string.digits
        codigo = ''.join(random.choices(letras, k=8))
        while Familia.objects.filter(codigo_invitacion=codigo).exists():
            codigo = ''.join(random.choices(letras, k=8))
        self.codigo_invitacion = codigo
        self.save()

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
    familia = models.ForeignKey(Familia, on_delete=models.CASCADE, related_name='tareas')
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    familia = models.ForeignKey('Familia', on_delete=models.CASCADE, related_name='tareas', null=True, blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.estado})"

    def asignar_aleatoriamente(self):
        usuarios_disponibles = list(User.objects.all())
        if usuarios_disponibles:
            self.asignado_a = random.choice(usuarios_disponibles)
            self.save()