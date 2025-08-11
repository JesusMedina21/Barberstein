from django.http import HttpResponseForbidden
from django.conf import settings

class BlockPostmanMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if 'postman' in user_agent:
            return HttpResponseForbidden("Acceso denegado")
        return self.get_response(request)
    
class CustomHeaderMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = [
            '/admin/',    # Rutas que se pueden visualizar
            '/static/',   #Para que cargen estilos en el admin
            '/staticfiles/',
            '/serviceworker.js',  # Ruta worker
            '/manifest.json',     # Ruta del manifest
            '/offline/'           # Si tienes una ruta offline para PWA
            #'/api/docs/',    #Solo en desarrollo se descomenta  y se usa
            #'/api/schema/',  #Solo en desarrollo se descomenta  y se usa
        ]

    def __call__(self, request):
        # Verifica si la ruta está exenta
        if any(request.path.startswith(path) for path in self.exempt_paths):
            return self.get_response(request)
            
        # Verifica el header personalizado
        secret_header = request.headers.get(settings.SECURE_API_HEADER)
        if secret_header != settings.SECURE_API_VALUE:
            return HttpResponseForbidden("Acceso no autorizado")
            
        return self.get_response(request)