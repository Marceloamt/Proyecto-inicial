from django.db import models
from django.contrib.auth.models import User

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
    hora_fin = models.TimeField()

    def __str__(self):
        return f"{self.usuario.username} - {self.dia} ({self.hora_inicio} a {self.hora_fin})"

class Tarea(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('hecha', 'Hecha'),
    ]

    nombre = models.CharField(max_length=100)
    responsable = models.CharField(max_length=100)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.estado})"

    def asignar_aleatoriamente(self):
        usuarios_disponibles = list(User.objects.all())
        if usuarios_disponibles:
            self.asignado_a = random.choice(usuarios_disponibles)
            self.save()