# License Admin Panel - Setup Guide

## 1. Prerrequisitos
- Python 3.8 o superior instalado.
- Una cuenta en Supabase con el proyecto configurado (`supabase_schema.sql` aplicado).

## 2. Configurar Credenciales
1.  Ve a tu proyecto en [Supabase Dashboard](https://supabase.com/dashboard).
2.  Entra a **Project Settings** -> **API**.
3.  Copia la **Project URL** y la **anon public key**.
4.  Abre el archivo `.env` en esta carpeta y pega los valores:

```env
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu-clave-anonima-larga
```

## 3. Instalación
Abre una terminal en la carpeta del proyecto (`LicenseAdminPanel`) y ejecuta:

```bash
pip install -r requirements.txt
```

Esto instalará `flask`, `supabase-py` y `python-dotenv`.

## 4. Ejecutar
Inicia el servidor de desarrollo:

```bash
python app.py
```

Verás un mensaje como `Running on http://127.0.0.1:5000`. Abre esa dirección en tu navegador.

## 5. Uso
- **Dashboard**: Vista general de licencias.
- **Nueva Licencia**: Botón arriba a la derecha. Elige tipo y se llenan los días.
- **Detalles**: Click en el icono de "ojo" en la tabla.
  - **Copiar Código**: Click en el código.
  - **Renovar**: Suma días a la licencia.
  - **Bloquear**: Deshabilita temporalmente.
  - **Desvincular Dispositivo**: Click en la "X" al lado del ID de dispositivo.
