from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from rest_framework import viewsets
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
import json # Necesario para serializar datos a JavaScript
from .models import Tarea, Familia, Horario, Perfil, PerfilForm
from .forms import HorarioForm, RegistroForm
from .serializers import TareaSerializer
from itertools import chain

# VISTAS HTML PRINCIPALES (TOCAR SOLO DE SER NECESARIO Y CON CUIDADO)

def inicio(request):
    #Vista de inicio: muestra la familia del usuario si existe.
    familia = None
    if request.user.is_authenticated:
        familia = (Familia.objects.filter(jefe=request.user).first() or 
                   Familia.objects.filter(miembros=request.user).first())
    return render(request, 'inicio.html', {'familia': familia})

#perfil y familias

@login_required
def perfil(request):
    #muestra la información del usuario, su familia, horarios y tareas.
    usuario = request.user
    familia = None
    es_jefe = False

    # Revisa si el usuario es jefe o miembro
    try:
        familia = Familia.objects.get(jefe=usuario)
        es_jefe = True
    except Familia.DoesNotExist:
        familia = Familia.objects.filter(miembros=usuario).first()
        es_jefe = False

    #si el usuario no tiene familia, lo redirige a crear una
    if not familia:
        return redirect('crear_familia')

    #obtener horarios disponibles del usuario
    horarios_disponibles = Horario.objects.filter(usuario=usuario, disponible=True)
    disponibilidad_data = {}

    for h in horarios_disponibles:
        dia_semana = h.dia
        if dia_semana not in disponibilidad_data:
            disponibilidad_data[dia_semana] = []
        disponibilidad_data[dia_semana].append({
            'inicio': str(h.hora_inicio),
            'termino': str(h.hora_termino),
        })

    #tareas pendientes de la familia
    tareas_pendientes = []
    tareas_qs = Tarea.objects.filter(familia=familia, estado='pendiente').select_related('responsable')
    for t in tareas_qs:
        tareas_pendientes.append({
            'id': t.id,
            'nombre': t.nombre,
            'responsable': t.responsable.username if t.responsable else 'Sin asignar',
            'fecha_creacion': t.fecha_creacion.isoformat(),
        })

    #si pertenece a una familia, obtener sus miembros (sin el usuario actual)
    miembros = familia.miembros.exclude(id=usuario.id) if familia else None

    #manejo del perfil con fecha de nacimiento
    perfil, creado = Perfil.objects.get_or_create(usuario=usuario)

    if request.method == 'POST':
        form = PerfilForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado correctamente ✅")
            return redirect('perfil')
    else:
        form = PerfilForm(instance=perfil)

    contexto = {
        'usuario': usuario,
        'familia': familia,
        'es_jefe': es_jefe,
        'miembros': miembros,
        'horarios_disponibles': horarios_disponibles,
        'disponibilidad_json': json.dumps(disponibilidad_data),
        'tareas_json': json.dumps(tareas_pendientes),
        'form': form,
        'perfil': perfil,
    }

    return render(request, 'perfil.html', contexto)


#gestión de tareas
@login_required
def tareas(request):
    #Muestra y permite agregar tareas dentro de la familia del usuario
    usuario = request.user
    familia_usuario = (
        Familia.objects.filter(jefe=usuario).first()
        or Familia.objects.filter(miembros=usuario).first()
    )

    if not familia_usuario:
        return render(request, 'tareas.html', {
            'tareas': [],
            'mensaje': "No perteneces a ninguna familia. Crea o únete a una para ver tareas."
        })

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        responsable_username = request.POST.get('responsable')
        if nombre and responsable_username:
            try:
                responsable = User.objects.get(username=responsable_username)
            except User.DoesNotExist:
                responsable = usuario
            Tarea.objects.create(
                nombre=nombre,
                responsable=responsable,
                familia=familia_usuario
            )
        return redirect('tareas')

    tareas = Tarea.objects.filter(familia=familia_usuario)
    miembros = list(chain([familia_usuario.jefe], familia_usuario.miembros.all()))

    return render(request, 'tareas.html', {
        'tareas': tareas,
        'familia': familia_usuario,
        'miembros': miembros
    })

@login_required
def completar_tarea(request, id):
    #cambia el estado de una tarea (pendiente/hecha)
    tarea = get_object_or_404(Tarea, id=id)
    if request.method == "POST":
        tarea.estado = "hecha" if tarea.estado == "pendiente" else "pendiente"
        tarea.save()
    return redirect('tareas')

#gestión de familias
@login_required
def crear_familia(request):
    #Permite crear una nueva familia solo si el usuario no pertenece a otra.
    if request.method == "POST":
        nombre = request.POST.get("nombre")

        if not nombre:
            messages.error(request, "Debes ingresar un nombre para la familia.")
            return redirect("crear_familia")

        # Si ya es jefe de una familia
        if Familia.objects.filter(jefe=request.user).exists():
            messages.warning(request, "Ya eres jefe de una familia.")
            return redirect("perfil")

        # Si ya pertenece como miembro a otra familia
        elif Familia.objects.filter(miembros=request.user).exists():
                messages.warning(request, "Ya perteneces a una familia, no puedes crear otra.")
                return redirect("perfil")

        # Crear la nueva familia
        nueva_familia = Familia.objects.create(nombre=nombre, jefe=request.user)
        nueva_familia.miembros.add(request.user)
        messages.success(request, f"Familia '{nombre}' creada con éxito 🎉")
        return redirect("perfil")

    return render(request, "crear_familia.html")

@login_required
def invitar_miembro(request):
    #Permite al jefe invitar usuarios o unirse con código
    if request.method == "POST":
        nombre_usuario = request.POST.get("nombre_usuario")
        codigo = request.POST.get("codigo")

        if nombre_usuario:
            try:
                usuario_a_invitar = User.objects.get(username=nombre_usuario)
                familia = Familia.objects.filter(jefe=request.user).first()
                if not familia:
                    messages.error(request, "No eres jefe de ninguna familia.")
                else:
                    familia.miembros.add(usuario_a_invitar)
                    messages.success(request, f"{nombre_usuario} fue agregado a tu familia.")
            except User.DoesNotExist:
                messages.error(request, "Ese usuario no existe.")
            return redirect('perfil')

        elif codigo:
            try:
                familia = Familia.objects.get(codigo_invitacion=codigo)
                familia.miembros.add(request.user)
                messages.success(request, f"Te has unido a la familia '{familia.nombre}'.")
                return redirect('perfil')
            except Familia.DoesNotExist:
                messages.error(request, "Código de invitación inválido.")
    return render(request, 'invitar_miembro.html')


@login_required
def unirse_familia(request):
    #Permite unirse a una familia mediante un código de invitación
    if request.method == "POST":
        codigo = request.POST.get("codigo")
        try:
            familia = Familia.objects.get(codigo_invitacion=codigo)
            if familia.miembros.filter(id=request.user.id).exists():
                messages.warning(request, "Ya perteneces a esta familia.")
            elif Familia.objects.filter(jefe=request.user).exists():
                messages.warning(request, "Eres jefe/a de otra familia, no puedes unirte.")
            else:
                familia.miembros.add(request.user)
                messages.success(request, f"Te uniste a la familia '{familia.nombre}' 🎉")
                return redirect("perfil")
        except Familia.DoesNotExist:
            messages.error(request, "El código ingresado no corresponde a ninguna familia.")
    return render(request, "unirse_familia.html")


# vistas de horario

@login_required
def agregar_horario(request):
    #agrega un horario al usuario autenticado
    if request.method == 'POST':
        form = HorarioForm(request.POST)
        if form.is_valid():
            horario = form.save(commit=False)
            horario.usuario = request.user
            horario.disponible = True
            horario.save()
            messages.success(request, '¡Horario agregado con éxito! Puedes verlo en la lista.')
            return redirect('ver_horario')
    else:
        form = HorarioForm()
    return render(request, 'agregar_horario.html', {'form': form})

@login_required
def ver_horario(request):
    #muestra los horarios del usuario autenticado
    usuario = request.user #usuario autenticado
    horarios = Horario.objects.filter(usuario=usuario)
    return render(request, 'ver_horario.html', {'horarios': horarios})

@login_required
def editar_horario(request, horario_id):
    horario = get_object_or_404(Horario, id=horario_id, usuario=request.user)
    #Permite editar un horario existente
    if request.method == 'POST':
        dia = request.POST.get('dia')
        hora_inicio = request.POST.get('hora_inicio')
        hora_termino = request.POST.get('hora_termino')

        if dia and hora_inicio and hora_termino:
            horario.dia = dia
            horario.hora_inicio = hora_inicio
            horario.hora_termino = hora_termino
            horario.save()
            messages.success(request, "Horario actualizado correctamente.")
            return redirect('ver_horario')

    return render(request, 'editar_horario.html', {'horario': horario})

@login_required
def eliminar_horario(request, horario_id):
    # Elimina un horario del usuario.
    horario = get_object_or_404(Horario, id=horario_id, usuario=request.user)
    horario.delete()
    messages.success(request, "Horario eliminado correctamente.")
    return redirect('ver_horario')

# Autenticación

def registro(request):
    #registro de nuevos usuarios con email y fecha de nacimiento
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "¡Registro exitoso! Bienvenido a HomeBalance 🎉")
            return redirect('inicio')
    else:
        form = RegistroForm()
    return render(request, 'registro.html', {'form': form})


def login_view(request):
    #inicio de sesión de usuarios
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('inicio')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    #cierre de sesión de usuarios
    logout(request)
    return redirect('inicio')

# API restful
class TareaViewSet(viewsets.ModelViewSet):
    queryset = Tarea.objects.all()
    serializer_class = TareaSerializer
