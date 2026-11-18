from django.urls import path

from . import views


urlpatterns = [
    path("", views.explorer, name="explorer"),
    path("blocks/<int:index>/", views.block_detail, name="block_detail"),
    path("transactions/<str:tx_hash>/", views.explorer_transaction, name="explorer_transaction"),
    path("validate/", views.validate, name="validate_chain"),
]
