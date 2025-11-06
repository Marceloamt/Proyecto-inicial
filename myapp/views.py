from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from rest_framework import viewsets
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
import json # Necesario para serializar datos a JavaScript
from .models import Tarea, Familia, Horario, Perfil
from .forms import HorarioForm, RegistroForm, PerfilForm, UserEditForm, TareaForm
from .serializers import TareaSerializer
from itertools import chain

#🚨🚨🚨NO CAMBIAR NOMBRES DE VARIABLES NI FUNCIONES A MENOS QUE SEA ABSOLUTA Y ESTRICTAMENTE NECESARIO 🚨🚨🚨
# VISTAS HTML PRINCIPALES (🚨TOCAR VISTAS EXISTENTES SOLO DE SER NECESARIO Y CON CUIDADO🚨)

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
    usuario = request.user
    
    # Obtiene TODAS las familias donde el usuario es jefe
    familias_jefe = Familia.objects.filter(jefe=usuario)

    #Si el usuario es jefe en al menos una familia
    if familias_jefe.exists():
        # Ve todas sus tareas de jefe
        tareas = Tarea.objects.filter(familia__in=familias_jefe).order_by('-fecha_creacion')
        miembros = {} # Diccionario para almacenar miembros por familia
        
        # 3. Preparar los datos de miembros y el formulario
        for familia in familias_jefe:
            miembros[familia.id] = list(chain([familia.jefe], familia.miembros.all()))

        if request.method == 'POST':
            # La vista ahora necesita saber a qué familia aplicar la tarea
            familia_id = request.POST.get('familia_seleccionada')
            if not familia_id:
                messages.error(request, "Debe seleccionar una familia para crear la tarea.")
                form = TareaForm(request.POST) # Reusar datos POST para mostrar errores
            else:
                familia_seleccionada = get_object_or_404(Familia, id=familia_id, jefe=usuario)
                form = TareaForm(request.POST) 
                
                if form.is_valid():
                    tarea = form.save(commit=False)
                    tarea.familia = familia_seleccionada # Asignar la familia seleccionada
                    tarea.save()
                    messages.success(request, f"Tarea creada exitosamente para '{familia_seleccionada.nombre}'. ✅")
                    return redirect('tareas')
                else:
                    messages.error(request, "Error al crear la tarea. Revisa los campos marcados.")
        else:
            form = TareaForm()

        return render(request, 'tareas.html', {
            'familias_jefe': familias_jefe, # Pasamos todas las familias de jefe
            'tareas': tareas,
            'miembros': miembros,
            'form': form,
            'es_jefe_multi': familias_jefe.count() > 1, # Indica si maneja más de una familia
            'es_jefe': True, # Es jefe en al menos una familia
        })

    #Si el usuario es SOLO miembro (código original de miembro)
    familia_miembro = Familia.objects.filter(miembros=usuario).first()
    if familia_miembro:
        tareas = Tarea.objects.filter(familia=familia_miembro).order_by('-fecha_creacion')
        
        return render(request, 'tareas.html', {
            'tareas': tareas,
            'familia': familia_miembro, # Solo una familia para miembros
            'es_jefe': False,
            'miembros': list(chain([familia_miembro.jefe], familia_miembro.miembros.all())),
            'form': TareaForm() 
        })

    # Si no pertenece a ninguna familia
    return render(request, 'tareas.html', {
        'tareas': [],
        'mensaje': "No perteneces a ninguna familia. Crea o únete a una para ver tareas.",
        'form': TareaForm() 
    })

@login_required
def completar_tarea(request, id):
    #cambia el estado de una tarea (pendiente/hecha)
    tarea = get_object_or_404(Tarea, id=id)
    if request.method == "POST":
        tarea.estado = "hecha" if tarea.estado == "pendiente" else "pendiente"
        tarea.save()
    return redirect('tareas')

@login_required
def editar_tarea(request, tarea_id):
    # Obtiene la tarea, asegurando que el usuario sea el jefe de la familia a la que pertenece
    tarea = get_object_or_404(Tarea, id=tarea_id)

    # Verificar si el usuario es jefe de la familia de la tarea
    if not Familia.objects.filter(jefe=request.user, id=tarea.familia.id).exists():
        messages.error(request, "❌ No tienes permiso para editar esta tarea.")
        return redirect('tareas')

    #Manejo del formulario
    if request.method == 'POST':
        form = TareaForm(request.POST, instance=tarea)
        if form.is_valid():
            form.save()
            messages.success(request, f"Tarea '{tarea.nombre}' actualizada correctamente. ✅")
            return redirect('tareas')
        else:
            messages.error(request, "Hubo un error al guardar la tarea. Revisa los campos.")
    else:
        # Petición GET: Cargar el formulario prellenado
        form = TareaForm(instance=tarea)

    contexto = {
        'form': form,
        'tarea': tarea
    }
    return render(request, 'editar_tarea.html', contexto)


@login_required
def eliminar_tarea(request, tarea_id):
    # Obtiene la tarea
    tarea = get_object_or_404(Tarea, id=tarea_id)

    # Verificar si el usuario es jefe de la familia de la tarea
    if not Familia.objects.filter(jefe=request.user, id=tarea.familia.id).exists():
        messages.error(request, "❌ No tienes permiso para eliminar esta tarea.")
        return redirect('tareas')

    # Lógica de eliminación
    if request.method == 'POST':
        nombre_tarea = tarea.nombre
        tarea.delete()
        messages.success(request, f"Tarea '{nombre_tarea}' eliminada correctamente. 🗑️")
        return redirect('tareas')

    # Petición GET: Mostrar la página de confirmación de eliminación (opcional)
    return render(request, 'eliminar_tarea.html', {'tarea': tarea})

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
    #obteiene la instancia del horario, asegurando que solo el dueño pueda editarlo.
    horario_instancia = get_object_or_404(Horario, id=horario_id, usuario=request.user)
    
    if request.method == 'POST':
        form = HorarioForm(request.POST, instance=horario_instancia)
        if form.is_valid():
            form.save()
            messages.success(request, "Horario actualizado correctamente. ✅")
            #redirige a la página principal de perfil donde se ven los horarios
            return redirect('perfil') 
        else:
            messages.error(request, "Hubo un error al guardar el horario. Revisa los campos.")
            
    else:
        # Inicializa el formulario llenado antes con los datos actuales
        form = HorarioForm(instance=horario_instancia)
        
    contexto = {
        'form': form,
        'horario': horario_instancia
    }
    return render(request, 'editar_horario.html', contexto)

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