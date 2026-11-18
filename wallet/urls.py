from django.urls import path

from . import views

urlpatterns = [
    path('', views.wallet_detail, name='wallet_detail'),
]
