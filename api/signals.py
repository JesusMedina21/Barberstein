from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import *
import logging

logger = logging.getLogger(__name__)

from django.db.models.signals import post_delete
from django.dispatch import receiver
from cloudinary.uploader import destroy
import os 

from urllib.parse import urlparse # Importa la librería


from django.conf import settings
import cloudinary


@receiver(pre_save, sender=User)
def update_username_in_comments(sender, instance, **kwargs):
    if not instance.pk:  # Solo para actualizaciones, no para creaciones
        return
        
    try:
        old_user = User.objects.get(pk=instance.pk)
        if old_user.username == instance.username:
            return  # No hay cambio en el username
            
        logger.info(f"Username cambiado de {old_user.username} a {instance.username}. Actualizando comentarios...")
        
        # Buscar todas las barberías que tienen comentarios de este usuario
        barberias = User.objects.filter(barberia__isnull=False)
        
        updated_barberias = 0
        updated_comments = 0
        
        for barberia in barberias:
            if not barberia.barberia:
                continue
                
            for barberia_profile in barberia.barberia:
                if not isinstance(barberia_profile, dict) or 'comments' not in barberia_profile:
                    continue
                    
                for comment in barberia_profile['comments']:
                    if (isinstance(comment, dict) and 
                        'user' in comment and 
                        isinstance(comment['user'], dict) and 
                        'id' in comment['user'] and 
                        str(comment['user']['id']) == str(instance.pk) and 
                        comment['user'].get('username') == old_user.username):
                        
                        comment['user']['username'] = instance.username
                        updated_comments += 1
                        barberia.save()  # Guardar después de cada actualización
                        updated_barberias += 1
                        break  # Pasar a la siguiente barbería
        
        logger.info(f"Actualizados {updated_comments} comentarios en {updated_barberias} barberías")
        
    except User.DoesNotExist:
        logger.error(f"Usuario con pk {instance.pk} no encontrado al intentar actualizar comentarios")
    except Exception as e:
        logger.error(f"Error al actualizar username en comentarios: {str(e)}")

def get_cloudinary_config(is_service=False):
    """Configuración adecuada según el tipo de imagen"""
    if is_service:
        return {
            'cloud_name': settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
            'api_key': settings.SERVICIOS_CLOUDINARY['API_KEY'],
            'api_secret': settings.SERVICIOS_CLOUDINARY['API_SECRET']
        }
    else:
        return {
            'cloud_name': settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
            'api_key': settings.CLOUDINARY_STORAGE['API_KEY'],
            'api_secret': settings.CLOUDINARY_STORAGE['API_SECRET']
        }


@receiver(pre_save)
def delete_old_profile_image(sender, instance, **kwargs):
    from .models import User  # evitar import circular
    if not isinstance(instance, User):
        return  # Solo aplica a User y sus proxys
    """
    Elimina imágenes antiguas cuando se actualizan.
    """
    if not instance.pk:  # Nuevo usuario, no hay imágenes antiguas
        return
    
    try:
        old_user = User.objects.get(pk=instance.pk)
        
        # Eliminar imagen de perfil anterior si cambió (cuenta principal)
        if old_user.profile_imagen and old_user.profile_imagen != instance.profile_imagen:
            delete_image_from_cloudinary(old_user.profile_imagen.name, is_service=False)
            
    except User.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error al eliminar imágenes antiguas: {e}")

def delete_image_from_cloudinary(image_url_or_id, is_service=False):
    """
    Elimina una imagen de Cloudinary considerando la cuenta correcta
    """
    try:
        if not image_url_or_id:
            return
            
        # Configurar según el tipo de imagen
        config = get_cloudinary_config(is_service)
        cloudinary.config(**config)
        
        if isinstance(image_url_or_id, str):
            if image_url_or_id.startswith(('http://', 'https://')):
                # Si es URL, extraer public_id
                path = urlparse(image_url_or_id).path
                public_id = path.split('/')[-1].split('.')[0]
                
                # Verificar si tiene folder en la URL
                if path.count('/') > 1:
                    folder = path.split('/')[-2]
                    public_id = f"{folder}/{public_id}"
            else:
                # Si es public_id, usar directamente
                public_id = image_url_or_id
                
            # Eliminar de Cloudinary
            result = cloudinary.uploader.destroy(public_id)
            if result.get('result') == 'ok':
                logger.info(f"Imagen {public_id} eliminada de Cloudinary (servicio: {is_service})")
            else:
                logger.error(f"Error al eliminar {public_id}: {result.get('result')}")
                
    except Exception as e:
        logger.error(f"Error al eliminar imagen de Cloudinary: {e}")
        
@receiver(post_delete)
def delete_user_images(sender, instance, **kwargs):
    """
    Elimina todas las imágenes asociadas a un usuario cuando se borra su cuenta.
    """
    from .models import User  # evitar import circular
    if not isinstance(instance, User):
        return  # Solo aplica a User y sus proxys
    # Eliminar imagen de perfil (cuenta principal)
    if instance.profile_imagen:
        try:
            # Usar la función mejorada que maneja prefijos
            delete_image_from_cloudinary(instance.profile_imagen.name, is_service=False)
        except Exception as e:
            logger.error(f"Error al eliminar imagen de perfil: {e}")

@receiver(post_delete, sender=Servicio)
def delete_service_images(sender, instance, **kwargs):
    """
    Elimina imágenes de Cloudinary cuando se borra un servicio.
    """
    try:
        for public_id in instance.imagen_urls:  # 👈 usas directamente los public_id que guardaste
            cloudinary.uploader.destroy(
                public_id,
                cloud_name=settings.SERVICIOS_CLOUDINARY['CLOUD_NAME'],
                api_key=settings.SERVICIOS_CLOUDINARY['API_KEY'],
                api_secret=settings.SERVICIOS_CLOUDINARY['API_SECRET']
            )
    except Exception as e:
        print(f"Error eliminando imágenes de servicio {instance.id}: {e}")