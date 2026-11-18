from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_history, name='transaction_history'),
    path('send/', views.send_transaction, name='send_transaction'),
    path('detail/<str:tx_hash>/', views.transaction_detail, name='transaction_detail'),
]
