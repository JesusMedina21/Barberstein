from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import User
import logging

logger = logging.getLogger(__name__)

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