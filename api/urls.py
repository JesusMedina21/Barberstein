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

urlpatterns = [
    path('', include(router.urls)),

    #endpoints   
    path('turnos-old/<str:token>/', views.delete_old_turnos_view, name='old_turnos'),
    # Endpoints personalizados de Djoser
    path('auth/reset/password/', UserViewSet.as_view({'post': 'reset_password'}), name='password-reset'),
    path('auth/reset/password/confirm/', UserViewSet.as_view({'post': 'reset_password_confirm'}), name='password-reset-confirm'),
    path('auth/reset/email/', UserViewSet.as_view({'post': 'reset_username'}), name='email-reset'),
    path('auth/reset/email/confirm/', EmailCambiadoView.as_view(), name='reset-email-confirm'),
    path('auth/activate/', UserViewSet.as_view({'post': 'activation'}), name='user-activation'),
    
]
if settings.DEBUG:
    #urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)