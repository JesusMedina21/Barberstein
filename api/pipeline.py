import requests
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
import logging
import cloudinary
import cloudinary.uploader
logger = logging.getLogger(__name__)
User = get_user_model()
from decouple import config

def save_profile_picture(backend, user, response, *args, **kwargs):
    """
    Pipeline para guardar la foto de perfil de Google en Cloudinary
    con mejor manejo de errores y verificación
    """
    # Solo procesar para Google OAuth2
    if backend.name != 'google-oauth2':
        return {}
    
    # Verificar que tenemos usuario y respuesta
    if not user or not response:
        #print("❌ Usuario o respuesta no disponibles")
        return {}
    
    # Obtener URL de la imagen de perfil
    profile_picture_url = response.get('picture')
    if not profile_picture_url:
        #print("⚠️  No se encontró URL de imagen de perfil en la respuesta")
        return {}
    
    try:
        
        cloudinary.config(
            cloud_name=config('CLOUDINARY_PROFILE_CLOUD_NAME'),
            api_key=config('CLOUDINARY_PROFILE_API_KEY'),
            api_secret=config('CLOUDINARY_PROFILE_API_SECRET')
        )
        
        #print(f"📥 Descargando imagen de: {profile_picture_url}")
        
        # Descargar la imagen de Google
        image_response = requests.get(profile_picture_url, stream=True, timeout=10)
        image_response.raise_for_status()
        
        #print(f"✅ Imagen descargada correctamente")
        
        # Subir a Cloudinary en la carpeta profile_images
        upload_result = cloudinary.uploader.upload(
            image_response.content,
            folder="profile_images/",
            public_id=f"user_{user.id}",  # Prefijo para evitar conflictos
            resource_type="image",
            overwrite=True,
            transformation=[
                {'width': 200, 'height': 200, 'crop': 'fill'},
                {'quality': 'auto', 'fetch_format': 'auto'}
            ]
        )
        
        # Obtener el public_id de Cloudinary
        public_id = upload_result['public_id']
        secure_url = upload_result['secure_url']
        
        #print(f"☁️  Imagen subida a Cloudinary: {secure_url}")
        #print(f"📁 Public ID: {public_id}")
        
        # Guardar solo el public_id en la base de datos
        user.profile_imagen = public_id
        user.save()
        
        #print(f"✅ Imagen de perfil guardada para usuario {user.email}")
        
        return {'user': user}

    except requests.RequestException as e:
        print(f"❌ Error al descargar la imagen de Google: {e}")
    except cloudinary.exceptions.Error as e:
        print(f"❌ Error de Cloudinary: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
    
    return {}

def ensure_unique_association(backend, details, response, *args, **kwargs):
    """
    Forzar que cada email único cree un usuario nuevo
    """
    email = details.get('email')
    if not email:
        return {}
    
    print(f"📧 Processing email: {email}")
    
    # Buscar si ya existe un usuario con este email
    try:
        existing_user = User.objects.get(email=email)
        print(f"✅ Usuario existente: {existing_user.email} (ID: {existing_user.id})")
        
        # Devolver el usuario existente para asociación
        return {
            'user': existing_user,
            'is_new': False
        }
            
    except User.DoesNotExist:
        print(f"🆕 Nuevo usuario: {email}")
        # Dejar que el pipeline continúe y cree nuevo usuario
        return {}

def custom_associate_user(backend, details, response, *args, **kwargs):
    """
    Reemplazo del associate_user original para prevenir conflictos
    """
    email = details.get('email')
    uid = kwargs.get('uid')
    
    print(f"🔗 Custom associate: {email} (UID: {uid})")
    
    if not email or not uid:
        return {}
    
    # Buscar asociación existente por UID (no por email)
    try:
        from social_django.models import UserSocialAuth
        social = UserSocialAuth.objects.get(provider=backend.name, uid=uid)
        #print(f"📎 Asociación existente encontrada: {social.uid} -> User {social.user_id}")
        return {
            'user': social.user,
            'is_new': False
        }
    except UserSocialAuth.DoesNotExist:
        #print("🆕 Nueva asociación requerida - llamando a associate_user original")
        # Dejar que social_core maneje la asociación normalmente
        return {}
    
def prevent_user_overwrite(backend, details, response, user=None, *args, **kwargs):
    """
    Prevenir que un usuario existente sea sobrescrito
    """
    if user and user.pk:
        email = details.get('email')
        if email and email != user.email:
            print(f"🚫 ALERTA: Intento de sobrescribir usuario {user.email} con {email}")
            # Forzar creación de nuevo usuario en lugar de sobrescribir
            return {
                'user': None,
                'is_new': True
            }
    return {}

def print_jwt_token(strategy, details, response, user=None, *args, **kwargs):
    """
    NUEVO: Genera y muestra el token JWT en la consola
    """
    if user and user.is_authenticated:
        try:
            # Generar token JWT
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            
            # Imprimir en consola del backend (Django)
            print("\n" + "="*60)
            print("🔥 TOKEN JWT GENERADO PARA USUARIO SOCIAL 🔥")
            print("="*60)
            print(f"Usuario: {user.email}")
            print(f"User ID: {user.id}")
            print(f"Access Token: {access_token}")
            print(f"Refresh Token: {str(refresh)}")
            print("="*60)
            
            # También guardar en la sesión por si acaso
            strategy.session_set('jwt_access_token', access_token)
            strategy.session_set('jwt_refresh_token', str(refresh))
            
        except Exception as e:
            print(f"❌ Error generando JWT: {e}")
    
    return {'user': user}