from django.urls import path
from . import views

urlpatterns = [
        path("", views.myapp, name="myapp"),
        path("myapp/", views.myapp, name="myapp")
]