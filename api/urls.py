from django.urls import path, include
from rest_framework import routers
from api import views
from django.conf import settings
from django.conf.urls.static import static

from django.conf import settings
from .views import *
from djoser.views import UserViewSet


#endpoints   
router = routers.DefaultRouter()
router.register(r'clients', views.ClienteViewSet, basename='clientes')
router.register(r'barbers', views.BarberiaViewSet, basename='barberias')
router.register(r'comments', views.ComentarioViewSet)
router.register(r'turnos', views.TurnoViewSet)
router.register(r'servicios', views.ServicioViewSet)

urlpatterns = [
    path('', include(router.urls)),

    #endpoints   
    path('barbers/google/', ConvertGoogleUserToBarberiaView.as_view(), name='convert-google-to-barber'),
    path('turnos/old/<str:token>/', views.delete_old_turnos_view, name='old_turnos'),
    # Endpoints personalizados de Djoser
    path('auth/activate/', CustomUserViewSet.as_view({'post': 'activation'}), name='user-activation'),
    path('auth/activate/new-email/', ActivarNuevoEmailView.as_view(), name='activation-new-email'),
    path('auth/reset/email/', UserViewSet.as_view({'post': 'reset_username'}), name='email-reset'),
    path('auth/reset/email/confirm/', ConfirmarEmail.as_view(), name='reset-email-confirm'), 
    path('auth/reset/password/', UserViewSet.as_view({'post': 'reset_password'}), name='password-reset'),
    path('auth/reset/password/confirm/', UserViewSet.as_view({'post': 'reset_password_confirm'}), name='password-reset-confirm'),
    path('auth/o/', include('social_django.urls', namespace='social')),  # << importante
    #La ruta de auth/o es api/auth/o/login/google-oauth2/
    
   
    
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)