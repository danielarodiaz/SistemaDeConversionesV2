# 🔄 Sistema de Conversiones V2

Sistema web de conversiones de unidades (temperatura, longitud, peso, entre otras), desarrollado como la segunda versión de un conversor inicial. La principal mejora respecto a la versión anterior es el **desacoplamiento en capas de frontend y backend**, junto con la incorporación de **Docker Compose** para facilitar el despliegue y la ejecución del entorno completo.

---

## 📋 Descripción

Esta aplicación permite al usuario realizar conversiones entre distintas unidades de medida a través de una interfaz web. La lógica de conversión se encuentra en el backend, mientras que el frontend se comunica con él mediante una API REST.

---

## 🏗️ Arquitectura

El proyecto está dividido en dos capas desacopladas:

```
SistemaDeConversionesV2/
├── frontend/       # Interfaz de usuario (cliente web)
├── backend/        # API REST con la lógica de negocio
└── docker-compose.yml
```

### Frontend
- Interfaz de usuario desarrollada como cliente web.
- Se comunica con el backend a través de peticiones HTTP a la API REST.
- Se ejecuta en su propio contenedor Docker.

### Backend
- API REST que expone los endpoints de conversión.
- Contiene toda la lógica de negocio (cálculos y conversiones de unidades).
- Se ejecuta en su propio contenedor Docker.

---

## 🚀 Tecnologías utilizadas

| Capa       | Tecnología         |
|------------|--------------------|
| Frontend   | HTML / CSS / JavaScript (o framework web) |
| Backend    | Node.js / Express (o tecnología equivalente) |
| Contenedores | Docker & Docker Compose |

---

## ⚙️ Requisitos previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:

- [Docker](https://www.docker.com/) (versión 20 o superior)
- [Docker Compose](https://docs.docker.com/compose/) (versión 2 o superior)

---

## 📦 Instalación y ejecución

1. **Clonar el repositorio:**

```bash
git clone https://github.com/danielarodiaz/SistemaDeConversionesV2.git
cd SistemaDeConversionesV2
```

2. **Levantar los servicios con Docker Compose:**

```bash
docker compose up --build
```

3. **Acceder a la aplicación:**

Abre tu navegador y navega a:

```
http://localhost:<puerto-frontend>
```

> El puerto exacto depende de la configuración definida en `docker-compose.yml`.

4. **Detener los servicios:**

```bash
docker compose down
```

---

## 🔌 Endpoints de la API (Backend)

El backend expone una API REST con endpoints para cada tipo de conversión. Algunos ejemplos:

| Método | Endpoint              | Descripción                            |
|--------|-----------------------|----------------------------------------|
| GET    | `/api/temperatura`    | Conversiones de temperatura (°C, °F, K) |
| GET    | `/api/longitud`       | Conversiones de longitud (m, km, mi, ft) |
| GET    | `/api/peso`           | Conversiones de peso (kg, g, lb, oz)   |

> Consulta la documentación interna o el código del backend para ver todos los endpoints disponibles y sus parámetros.

---

## 🔄 Diferencias respecto a la Versión 1

| Característica            | V1                        | V2                              |
|---------------------------|---------------------------|---------------------------------|
| Arquitectura              | Monolítica                | Frontend y Backend desacoplados |
| Despliegue                | Manual                    | Docker Compose                  |
| API REST                  | No                        | Sí                              |
| Escalabilidad             | Limitada                  | Mejorada por contenedores       |

---

## 👩‍💻 Autora

**Daniela Rocío Díaz**  
[GitHub](https://github.com/danielarodiaz)
