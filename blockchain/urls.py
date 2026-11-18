from django.urls import path

from . import views

urlpatterns = [
    path('mine/', views.mine_block, name='mine_block'),
]
