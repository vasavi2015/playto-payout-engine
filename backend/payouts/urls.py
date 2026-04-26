from django.urls import path
from . import views

urlpatterns = [
    path('merchants/', views.merchants),
    path('bank-accounts/', views.bank_accounts),
    path('dashboard/', views.dashboard),
    path('payouts/', views.payouts),
]
