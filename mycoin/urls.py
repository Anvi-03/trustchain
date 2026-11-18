from django.contrib import admin
from django.urls import path, include

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('wallet/', include('wallet.urls')),
    path('transactions/', include('transactions.urls')),
    path('blockchain/', include('blockchain.urls')),
    path('explorer/', include('explorer.urls')),
    path('', views.home, name='home'),
]
