from django.apps import AppConfig

class ApiConfig(AppConfig):
    default_auto_field = 'django_mongodb_backend.fields.ObjectIdAutoField'  
    name = 'api'

    def ready(self):
        import api.signals  # Asegúrate de crear este archivo