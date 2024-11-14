# Usa una imagen base oficial de Python
FROM python:3.11.9-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Epaquetes del sistema necesarios
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia el archivo de requerimientos y el código fuente al contenedor
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación al contenedor
COPY . .

# Expone el puerto si es necesario (por ejemplo, si usas Flask)
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["python", "notificaciones.py"]
