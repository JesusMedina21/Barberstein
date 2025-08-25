from django.contrib import admin
from django.contrib.auth.models import Group
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django import forms
from django.utils.safestring import mark_safe

from social_django.models import UserSocialAuth
from django import forms
import cloudinary.uploader

from django import forms
import json
import re
class CoordenadasField(forms.CharField):
    """Campo personalizado que acepta 'lat, lng' y convierte a GeoJSON"""
    
    def to_python(self, value):
        if not value:
            return None
        
        # Si ya es un diccionario (viene de la BD), devolverlo tal cual
        if isinstance(value, dict):
            return value
        
        # Si es string, parsear "lat, lng"
        if isinstance(value, str):
            try:
                # Extraer números del string (permite diferentes formatos)
                numbers = re.findall(r'-?\d+\.?\d*', value)
                if len(numbers) >= 2:
                    lat = float(numbers[0])
                    lng = float(numbers[1])
                    
                    # Validar rangos
                    if -90 <= lat <= 90 and -180 <= lng <= 180:
                        return {
                            'type': 'Point',
                            'coordinates': [lat, lng]
                        }
                    else:
                        raise forms.ValidationError('Latitud debe estar entre -90 y 90, Longitud entre -180 y 180')
                
            except (ValueError, TypeError):
                pass
        
        raise forms.ValidationError('Formato inválido. Use: "8.049147423101246, -72.25808037610052"')
    
    def prepare_value(self, value):
        """Convierte el GeoJSON a string para mostrarlo en el formulario"""
        if isinstance(value, dict) and value.get('type') == 'Point':
            coordinates = value.get('coordinates', [])
            if len(coordinates) == 2:
                return f"{coordinates[0]}, {coordinates[1]}"
        return value
    
################################Modelo USER-SOCIAL

# Desregistrar el modelo original de social_django
try:
    admin.site.unregister(UserSocialAuth)
except admin.exceptions.NotRegistered:
    pass

class UserSocialAuthProxy(UserSocialAuth):
    class Meta:
        proxy = True
        verbose_name = 'Usuario con Redes Sociales'
        verbose_name_plural = 'Usuarios con Redes Sociales'

@admin.register(UserSocialAuthProxy)
class UserSocialAuthProxyAdmin(admin.ModelAdmin):
    list_display = ('user', 'id', 'provider')
    readonly_fields = ('created', 'modified')
    search_fields = ('user__username', 'provider', 'uid')
    raw_id_fields = ('user',)

    fieldsets = (
        (None, {
            'fields': ('user', 'provider', 'uid', 'extra_data', 'created', 'modified')
        }),
    )

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            user_to_delete = obj.user
            if user_to_delete:
                user_to_delete.delete()
            obj.delete()

################################CLIENTES

class UserCreationForm(forms.ModelForm):
    first_name = forms.CharField(label='Nombre', required=True)
    last_name = forms.CharField(label='Apellido', required=True)
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput)
    make_admin = forms.BooleanField(
        label='Admin',
        required=False,
        help_text='Obtiene todos los permisos de la API y sus usuarios'
    )
    ubicacion_coordenadas = CoordenadasField(
        required=False,
        label='Coordenadas',
        help_text='Formato: "latitud, longitud". Ejemplo: "-16.4897, -68.1193"',
        widget=forms.TextInput(attrs={
            'placeholder': '-16.4897, -68.1193',
            'style': 'width: 300px;'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'is_active', 'make_admin')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        #  GUARDAR COORDENADAS SI SE PROPORCIONAN
        if 'ubicacion_coordenadas' in self.cleaned_data:
            user.ubicacion_coordenadas = self.cleaned_data['ubicacion_coordenadas']
        # Subir imagen de perfil a Cloudinary (cuenta correcta)
        if 'profile_imagen' in self.cleaned_data and self.cleaned_data['profile_imagen']:
            try:
                upload_result = cloudinary.uploader.upload(
                    self.cleaned_data['profile_imagen'],
                    folder="profile_images/",
                    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                )
                user.profile_imagen = upload_result['public_id']
            except Exception as e:
                logger.error(f"Error al subir imagen de perfil a Cloudinary: {e}")
        
        if self.cleaned_data['make_admin']:
            user.is_staff = True
            user.is_superuser = True
        
        if commit:
            user.save()
        return user

        
class UserChangeForm(forms.ModelForm):
    first_name = forms.CharField(label='Nombre', required=True)
    last_name = forms.CharField(label='Apellido', required=True)
    make_admin = forms.BooleanField(
        label='Admin',
        required=False,
        help_text='Obtiene todos los permisos de la API y sus usuarios'
    )
    #  NUEVO CAMPO PARA COORDENADAS
    ubicacion_coordenadas = CoordenadasField(
        required=False,
        label='Coordenadas',
        help_text='Formato: "latitud, longitud". Ejemplo: "-16.4897, -68.1193"',
        widget=forms.TextInput(attrs={
            'placeholder': '-16.4897, -68.1193',
            'style': 'width: 300px;'
        })
    )

    class Meta:
        model = User
        fields = '__all__'

    def clean_password(self):
        """
        Si no se cambia la contraseña, devuelve la que ya tiene el usuario (hash).
        """
        password = self.cleaned_data.get("password")
        if not password:  
            return self.instance.password  # No tocar si no se modificó
        return password  # Devuelve el valor crudo para que save() lo maneje

    def save(self, commit=True):
        user = super().save(commit=False)

        # 🔥 GUARDAR COORDENADAS SI SE PROPORCIONAN
        if 'ubicacion_coordenadas' in self.cleaned_data:
            user.ubicacion_coordenadas = self.cleaned_data['ubicacion_coordenadas']

        # Solo aplicar set_password si el password realmente cambió
        if "password" in self.changed_data:
            user.set_password(self.cleaned_data["password"])

        # Subir nueva imagen de perfil a Cloudinary si se proporciona
        if 'profile_imagen' in self.cleaned_data and self.cleaned_data['profile_imagen']:
            try:
                # Primero eliminar la imagen anterior si existe
                if user.profile_imagen:
                    try:
                        cloudinary.uploader.destroy(
                            user.profile_imagen,
                            cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                            api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                            api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                        )
                    except Exception as e:
                        logger.error(f"Error al eliminar imagen anterior de Cloudinary: {e}")
                
                # Subir nueva imagen
                upload_result = cloudinary.uploader.upload(
                    self.cleaned_data['profile_imagen'],
                    folder="profile_images/",
                    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                )
                user.profile_imagen = upload_result['public_id']
            except Exception as e:
                logger.error(f"Error al subir imagen de perfil a Cloudinary: {e}")

        if self.cleaned_data['make_admin']:
            user.is_staff = True
            user.is_superuser = True

        if commit:
            user.save()
        return user

class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    list_display = ('username', 'email', 'is_staff', 'is_active')
    search_fields = ('username', 'email')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2')
        }),
        ('Información personal', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'ubicacion_coordenadas', 'profile_imagen', 'biometric')
        }),
        ('Permisos', {
            'classes': ('wide',),
            'fields': ('is_active', 'make_admin')
        }),
    )

    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'ubicacion_coordenadas', 'profile_imagen', 'biometric')}),
        ('Permisos', {
            'fields': ('is_active', 'make_admin'),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        defaults = {}
        if obj is None:
            defaults['form'] = self.add_form
        else:
            defaults['form'] = self.form
            
        defaults.update(kwargs)
        form = super().get_form(request, obj, **defaults)
        
        if 'make_admin' in form.base_fields:
            form.base_fields['make_admin'].widget.attrs.update({
                'class': 'admin-checkbox',
                'onchange': 'toggleAdminStatus(this)'
            })
            
        return form

    class Media:
        js = ('admin/js/user_admin.js',)



class ClienteAdmin(UserAdmin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model._meta.verbose_name = 'Cliente'
        self.model._meta.verbose_name_plural = 'Clientes'
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(barberia__isnull=True)

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_active')
    list_filter = ('is_active',)


##########################################BARBERIAS
from django.forms.widgets import Input

class MultipleFileInput(Input):
    input_type = 'file'
    needs_multipart_form = True
    template_name = 'django/forms/widgets/file.html'

    def __init__(self, attrs=None):
        default_attrs = {'multiple': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        value = files.get(name)
        if value is None:
            return []
        return [value] if not isinstance(value, list) else value

    def value_omitted_from_data(self, data, files, name):
        return name not in files

class MultipleImageField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Si no se suben archivos, devolver lista vacía
        if data is None:
            return []
        
        # Si es un solo archivo, convertirlo a lista
        if not isinstance(data, list):
            return [data]
        
        return data


class Barberia(User):
    class Meta:
        proxy = True
        verbose_name = 'Barberia'
        verbose_name_plural = 'Barberias'


class BarberiaCreationForm(UserCreationForm):
    first_name = forms.CharField(label='Nombre', required=False)
    last_name = forms.CharField(label='Apellido', required=False)
    # Campos extra que van dentro del JSON
    name_barber = forms.CharField(label='Nombre Barbería', required=True)
    phone = forms.CharField(label='Teléfono', required=True)
    address = forms.CharField(label='Dirección', required=True)
    ubicacion_coordenadas = CoordenadasField(
        required=False,
        label='Coordenadas',
        help_text='Formato: "latitud, longitud". Ejemplo: "-16.4897, -68.1193"',
        widget=forms.TextInput(attrs={
            'placeholder': '-16.4897, -68.1193',
            'style': 'width: 300px;'
        })
    )
    turnos_max = forms.IntegerField(label='Turnos máximos por día', required=True)
    days = forms.MultipleChoiceField(
        label='Días de trabajo',
        choices=[
            ('lunes', 'Lunes'),
            ('martes', 'Martes'),
            ('miercoles', 'Miércoles'),
            ('jueves', 'Jueves'),
            ('viernes', 'Viernes'),
            ('sabado', 'Sábado'),
            ('domingo', 'Domingo')
        ],
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    
    
    openingTime = forms.TimeField(label='Hora de apertura', widget=forms.TimeInput(attrs={'type': 'time'}),
        required=True)
    closingTime = forms.TimeField(label='Hora de cierre', widget=forms.TimeInput(attrs={'type': 'time'}),
        required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        
        
        # 🔥 GUARDAR COORDENADAS SI SE PROPORCIONAN
        if 'ubicacion_coordenadas' in self.cleaned_data:
            user.ubicacion_coordenadas = self.cleaned_data['ubicacion_coordenadas']

        # Manejo de imagen de perfil
        if 'profile_imagen' in self.cleaned_data and self.cleaned_data['profile_imagen']:
            try:
                upload_result = cloudinary.uploader.upload(
                    self.cleaned_data['profile_imagen'],
                    folder="profile_images/",
                    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],   
                    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                )
                user.profile_imagen = upload_result['public_id']
            except Exception as e:
                logger.error(f"Error al subir imagen de perfil a Cloudinary: {e}")

        # Construcción del JSON embebido
        barberia_data = {
            "name_barber": self.cleaned_data.get('name_barber'),
            "phone": self.cleaned_data.get('phone'),
            "address": self.cleaned_data.get('address'),
            "horario": [{
                "turnos_max": self.cleaned_data.get('turnos_max'),
                "days": self.cleaned_data.get('days', [])
            }],
            "openingTime": self.cleaned_data.get('openingTime').strftime('%H:%M') if self.cleaned_data.get('openingTime') else None,
            "closingTime": self.cleaned_data.get('closingTime').strftime('%H:%M') if self.cleaned_data.get('closingTime') else None
        }

        user.barberia = [barberia_data]

        if commit:
            user.save()
        return user

class BarberiaChangeForm(UserChangeForm):
    first_name = forms.CharField(label='Nombre', required=False)
    last_name = forms.CharField(label='Apellido', required=False)
    # Campos extra que van dentro del JSON
    name_barber = forms.CharField(label='Nombre Barbería', required=True)
    phone = forms.CharField(label='Teléfono', required=True)
    ubicacion_coordenadas = CoordenadasField(
        required=False,
        label='Coordenadas',
        help_text='Formato: "latitud, longitud". Ejemplo: "-16.4897, -68.1193"',
        widget=forms.TextInput(attrs={
            'placeholder': '-16.4897, -68.1193',
            'style': 'width: 300px;'
        })
    )
    address = forms.CharField(label='Dirección', required=True)
    turnos_max = forms.IntegerField(label='Turnos máximos por día', required=True)
    days = forms.MultipleChoiceField(
        label='Días de trabajo',
        choices=[
            ('lunes', 'Lunes'),
            ('martes', 'Martes'),
            ('miercoles', 'Miércoles'),
            ('jueves', 'Jueves'),
            ('viernes', 'Viernes'),
            ('sabado', 'Sabado'),
            ('domingo', 'Domingo')
        ],
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    openingTime = forms.TimeField(
        label='Hora de apertura', 
        widget=forms.TimeInput(attrs={'type': 'time'}),
        required=True
    )
    closingTime = forms.TimeField(
        label='Hora de cierre', 
        widget=forms.TimeInput(attrs={'type': 'time'}),
        required=True
    )

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.barberia and len(self.instance.barberia) > 0:
            barberia_data = self.instance.barberia[0]
            self.fields['name_barber'].initial = barberia_data.get('name_barber', '')
            self.fields['phone'].initial = barberia_data.get('phone', '')
            self.fields['address'].initial = barberia_data.get('address', '')

            # Horario
            if 'horario' in barberia_data and len(barberia_data['horario']) > 0:
                horario = barberia_data['horario'][0]
                self.fields['turnos_max'].initial = horario.get('turnos_max', '')
                self.fields['days'].initial = horario.get('days', [])
                self.fields['openingTime'].initial = barberia_data.get('openingTime', '')
                self.fields['closingTime'].initial = barberia_data.get('closingTime', '')

            # Imagen de perfil
            if self.instance and self.instance.profile_imagen:
                try:
                    profile_url, _ = cloudinary.utils.cloudinary_url(
                        self.instance.profile_imagen.name,
                        cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                        api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                        api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                    )
                    self.fields['profile_imagen'].help_text = mark_safe(
                        f'<strong>Imagen actual:</strong><br>'
                        f'<img src="{profile_url}" height="100" style="border-radius: 50%;"><br>'
                        f'<span style="color: green;">Dejar vacío para mantener la imagen actual</span>'
                    )
                    self.fields['profile_imagen'].required = False
                except Exception as e:
                    logger.error(f"Error al generar URL de imagen de perfil: {e}")
                    self.fields['profile_imagen'].help_text = "Error al cargar la imagen actual"
    def save(self, commit=True):
        user = super().save(commit=False)

        # 🔥 GUARDAR COORDENADAS SI SE PROPORCIONAN
        if 'ubicacion_coordenadas' in self.cleaned_data:
            user.ubicacion_coordenadas = self.cleaned_data['ubicacion_coordenadas']

        
        # 1. Lógica para la imagen de perfil
        # Aseguramos que solo entramos en este bloque si el campo de imagen fue tocado
        # Y tiene un archivo válido.
        # Usa `self.cleaned_data.get('profile_imagen')` directamente como condición
        # para manejar el caso de que no haya archivo subido.
        if 'profile_imagen' in self.changed_data:
            new_image = self.cleaned_data.get('profile_imagen')
        
            if new_image:
                # 1. Si hay nueva imagen => borrar la anterior y subir la nueva
                if user.profile_imagen:
                    try:
                        cloudinary.uploader.destroy(
                            user.profile_imagen,
                            cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                            api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                            api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                        )
                    except Exception as e:
                        logger.error(f"Error al eliminar imagen anterior de Cloudinary: {e}")
        
                try:
                    upload_result = cloudinary.uploader.upload(
                        new_image,
                        folder="profile_images/",
                        cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                        api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                        api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                    )
                    user.profile_imagen = upload_result['public_id']
                except Exception as e:
                    logger.error(f"Error al subir imagen de perfil a Cloudinary: {e}")
                    # 👇 NO lanzamos ValidationError, solo logueamos
                    return user  
        
            else:
                # 2. Si el usuario limpió la imagen (checkbox clear en admin)
                if user.profile_imagen:
                    try:
                        cloudinary.uploader.destroy(
                            user.profile_imagen,
                            cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
                            api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
                            api_secret=settings.CLOUDINARY_STORAGE['API_SECRET']
                        )
                    except Exception as e:
                        logger.error(f"Error al eliminar imagen de perfil de Cloudinary: {e}")
                user.profile_imagen = None  # o '' dependiendo de tu modelo

        # 3. Construir el JSON del campo 'barberia'
        barberia_data = {
            "name_barber": self.cleaned_data.get('name_barber'),
            "phone": self.cleaned_data.get('phone'),
            "address": self.cleaned_data.get('address'),
            "horario": [{
                "turnos_max": self.cleaned_data.get('turnos_max'),
                "days": self.cleaned_data.get('days', [])
            }],
            "openingTime": self.cleaned_data.get('openingTime').strftime('%H:%M') if self.cleaned_data.get('openingTime') else None,
            "closingTime": self.cleaned_data.get('closingTime').strftime('%H:%M') if self.cleaned_data.get('closingTime') else None
        }

        user.barberia = [barberia_data]

        if commit:
            user.save()
        return user
@admin.register(Barberia)
class BarberiaAdmin(UserAdmin):
    form = BarberiaChangeForm
    add_form = BarberiaCreationForm

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'profile_imagen', 'ubicacion_coordenadas', 'biometric'),
        }),
        ('Información de la Barbería', {
            'fields': ('name_barber', 'phone', 'address'),
        }),
        ('Horario', {
            'fields': ('turnos_max', 'days', 'openingTime', 'closingTime'),
        }),
        ('Estado de la barberia', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
    )

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': ('email', 'profile_imagen', 'ubicacion_coordenadas', 'biometric')}),
        ('Información de la Barbería', {
            'fields': ('name_barber', 'phone', 'address', 'get_rating'),
        }),
        ('Horario', {
            'fields': ('turnos_max', 'days', 'openingTime', 'closingTime'),
        }),
        ('Estado de la barberia', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
    )


    list_display = ( 'get_name_barber', 'email', 'get_dias', 'get_horario','get_rating',  'is_active')


    readonly_fields = ('get_rating',)  # ¡Ahora sí funciona porque es un método!
    # Método para obtener el rating
    def get_rating(self, obj):
        if obj.barberia and isinstance(obj.barberia, list) and len(obj.barberia) > 0:
            return obj.barberia[0].get('rating', '0')
        return '0'
    get_rating.short_description = 'Rating' 

    def get_name_barber(self, obj):
        return obj.barberia[0].get('name_barber', '') if obj.barberia else ''
    get_name_barber.short_description = 'Nombre Barbería'

    # Horario (días + apertura + cierre)
    def get_horario(self, obj):
        if obj.barberia and isinstance(obj.barberia, list) and len(obj.barberia) > 0:
            dias = obj.barberia[0].get('days', [])
            opening = obj.barberia[0].get('openingTime', '')
            closing = obj.barberia[0].get('closingTime', '')
            return f"{', '.join(dias)} ({opening} - {closing})"
        return ''
    get_horario.short_description = 'Horario'

    def get_dias(self, obj):
        if obj.barberia and isinstance(obj.barberia, list) and len(obj.barberia) > 0:
            horario = obj.barberia[0].get('horario', [])
            dias = horario[0].get('days', []) if horario else []
            return ', '.join(dias) if dias else 'Sin días'
        return ''
    get_dias.short_description = 'Días de trabajo'


    def get_phone(self, obj):
        return obj.barberia[0].get('phone', '') if obj.barberia else ''
    get_phone.short_description = 'Teléfono'

    def get_queryset(self, request):
        return super().get_queryset(request).filter(barberia__isnull=False)
    

class MultipleFileInput(Input):
    input_type = 'file'
    needs_multipart_form = True
    template_name = 'django/forms/widgets/file.html'

    def __init__(self, attrs=None):
        default_attrs = {'multiple': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        value = files.get(name)
        if value is None:
            return []
        return [value] if not isinstance(value, list) else value

    def value_omitted_from_data(self, data, files, name):
        return name not in files

class MultipleImageField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Si no se suben archivos, devolver lista vacía
        if data is None:
            return []
        
        # Si es un solo archivo, convertirlo a lista
        if not isinstance(data, list):
            return [data]
        
        return data
    
class ServicioForm(forms.ModelForm):
    imagenes = MultipleImageField(label='Imagenes del servicio', required=False)

    mostrar_imagenes = forms.CharField(
        required=False,
        widget=forms.HiddenInput()  # se usa solo para mostrar en el admin
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mostrar imágenes actuales (como tu ejemplo)
        if self.instance and self.instance.pk and self.instance.imagen_urls:
            try:
                images_html = "<strong>Imágenes actuales:</strong><br>"
                for public_id in self.instance.imagen_urls:
                    imagen_url, _ = cloudinary.utils.cloudinary_url(
                        public_id,
                        cloud_name=settings.SERVICIOS_CLOUDINARY["CLOUD_NAME"],
                        api_key=settings.SERVICIOS_CLOUDINARY["API_KEY"],
                        api_secret=settings.SERVICIOS_CLOUDINARY["API_SECRET"]
                    )
                    images_html += f'<img src="{imagen_url}" height="150" style="margin:5px;border-radius:10px;">'

                images_html += (
                    "<br><span style='color: green;'>"
                    "Dejar vacío para mantener las imágenes actuales o subir nuevas para reemplazarlas."
                    "</span>"
                )

                self.fields["imagenes"].help_text = mark_safe(images_html)
                self.fields["imagenes"].required = False

            except Exception as e:
                logger.error(f"Error al generar URLs de imágenes: {e}")
                self.fields["imagenes"].help_text = "Error al cargar las imágenes actuales"


    class Meta:
        model = Servicio
        fields = ["barberia", "description", "precio", "moneda", "imagenes"]  # 👈 corregido

    def save(self, commit=True):
        instance = super().save(commit=False)
    
        imagenes = self.files.getlist("imagenes")  # capturamos varias imágenes
        public_ids = []
    
        if imagenes:
            if len(imagenes) > 4:
                raise forms.ValidationError("Solo puedes subir un máximo de 4 imágenes.")
    
            # 🔹 Eliminar imágenes antiguas
            if instance.imagen_urls:
                for old_public_id in instance.imagen_urls:
                    try:
                        cloudinary.uploader.destroy(
                            old_public_id,
                            cloud_name=settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
                            api_key=settings.SERVICIOS_CLOUDINARY['API_KEY'],
                            api_secret=settings.SERVICIOS_CLOUDINARY['API_SECRET']
                        )
                    except Exception as e:
                        logger.error(f"No se pudo borrar la imagen antigua {old_public_id}: {e}")
    
            # 🔹 Subir nuevas imágenes
            for imagen in imagenes:
                upload_result = cloudinary.uploader.upload(
                    imagen,
                    folder="services_images/",
                    cloud_name=settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
                    api_key=settings.SERVICIOS_CLOUDINARY['API_KEY'],
                    api_secret=settings.SERVICIOS_CLOUDINARY['API_SECRET']
                )
                public_ids.append(upload_result["public_id"])
    
            instance.imagen_urls = public_ids  # Guardamos lista en JSONField
    
        if commit:
            instance.save()
        return instance

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("cliente", "barberia", "description", "date", "rating")
    list_filter = ("cliente", "barberia")
    search_fields = ("description", "barberia__username")

@admin.register(Turnos)
class TurnosAdmin(admin.ModelAdmin):
    list_display = ("cliente", "barberia", "turno", "fecha_turno", "estado")
    list_filter = ("cliente", "barberia")
    
@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    form = ServicioForm
    list_display = ("description", "barberia", "precio", "moneda")
    list_filter = ("moneda", "barberia")
    search_fields = ("description", "barberia__username")
    
   
admin.site.unregister(Group)
# Registro final de modelos
admin.site.register(User, UserAdmin)  # Registro temporal
admin.site.unregister(User)  # Desregistramos para registrar las versiones personalizadas
admin.site.register(User, ClienteAdmin)  # Registra solo clientes