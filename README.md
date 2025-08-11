# Guía de instalación del proyecto Django

## ¿De que se trata este proyecto/API?

Este proyecto se trata de una API REST que es utilizada como Backend para la plataforma Barberia, permitiendo Registrar, Modificar, Eliminar y Listar los Productos. A traves de los metodos GET, POST, PUT y DELETE.

## Instalaciones necesarias

- [Visual Studio Code](https://code.visualstudio.com/)
- [Python](https://www.python.org/downloads/)

## Antes de comenzar

Antes de comenzar a instalar las dependencias del proyecto es necesario verificar que tienes las dependencias necesarias instaladas.
Abre la terminal de comandos de tu sistema y sigue los siguientes pasos para asegurarte de que todo está correcto antes de comenzar.

### Verificar instalación de Python

```
python --v
```


### Comandos para instalar el backend


- Ejecuta el siguiente comando para instalar el proyecto:

## Si estas en Windows

```
py -m venv venv 
```

```
.\venv\Scripts\activate
```

```
pip install -r requirements.txt
```

## Si estas en una Distribucion Linux basada en Debian (Ubuntu, Linux Mint etc...)

```
python3 -m venv venv
```

```
source venv/bin/activate
```

```
pip3 install -r requirements.txt
```

## Levantar el backend de la plataforma

El backend de la plataforma está construido en Django, para ejecutar el servidor de desarrollo backend debes ejecutar el siguiente comando:

## Si estas en Windows

```
python manage.py makemigrations 
```

```
python manage.py migrate 
```

```

python manage.py runserver
```

## Si estas en Linux

```
python3 manage.py makemigrations 
```

```
python3 manage.py migrate 
```

```

python3 manage.py runserver
```

Te diriges a la url localhost:8000 en el navegador


<h3 align="center">¡Y Listo! Has terminado de correr el backend 🥳</h3>
