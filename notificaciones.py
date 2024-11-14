import pika
import smtplib
import psycopg2
import json
import os
from email.mime.text import MIMEText
from flask import Flask, jsonify, request
import threading
import uuid
from datetime import datetime
from health import health_bp 

app = Flask(__name__)

# Configuración de PostgreSQL
def conectar_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
        database=os.environ.get("DB_NAME", "notificaciones"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "Asdf1234")
    )


def conectar_rabbitmq():
    try:
        # Configura las credenciales y la conexión
        rabbitmq_user = os.environ.get("RABBITMQ_USER", "user")
        rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD", "password")
        rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
        rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", 5672))

        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(rabbitmq_host, rabbitmq_port, credentials=credentials)
        )
        channel = connection.channel()

        # Declara el exchange (por ejemplo, un exchange de tipo 'direct')
        channel.exchange_declare(exchange='notificaciones-exchange', exchange_type='direct', durable=True)

        # Declara la cola (asegura que la cola existe y es durable)
        channel.queue_declare(queue='notificaciones', durable=True)

        # Crea el binding entre el exchange y la cola usando la routing key
        channel.queue_bind(exchange='notificaciones-exchange', queue='notificaciones', routing_key='notificaciones-routing-key')

        return connection, channel
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error al conectar a RabbitMQ: {e}")
        return None, None


def callback(ch, method, properties, body):
    print("Mensaje recibido de RabbitMQ:")
    try:
        data = json.loads(body)  # Convertir el mensaje de JSON a un diccionario
        destinatario = data['destinatario']
        canales = data['canales']
        mensaje = data['mensaje']

        # Llama a la función para manejar y enviar la notificación
        manejar_notificacion(destinatario, canales, mensaje)

        # Confirma la recepción del mensaje solo si se ha procesado correctamente
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"Mensaje procesado y confirmado: {body}")
    except Exception as e:
        print(f"Error al procesar el mensaje: {e}")
        # No se confirma el mensaje en caso de error, para que RabbitMQ lo reenvíe


# Función para enviar E-Mail
def enviar_email(destinatario, mensaje):
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = "ormoreno2000@gmail.com"
        smtp_password = "oelw wnwo dacp dlcr"

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)

        email_message = MIMEText(mensaje)
        email_message['Subject'] = 'Notificación'
        email_message['From'] = smtp_user
        email_message['To'] = destinatario

        server.sendmail(smtp_user, destinatario, email_message.as_string())
        server.quit()
        return "E-Mail enviado"
    except Exception as e:
        return f"Error enviando E-Mail: {e}"


# Función para enviar notificación en múltiples canales
def enviar_notificacion(destinatario, canales, mensaje):
    resultados = {}
    for canal in canales:
        if canal == "email":
            resultados["email"] = enviar_email(destinatario, mensaje)
    return resultados

# Registrar notificación en la base de datos
def registrar_notificacion_bd(notificacion_id, destinatario, canales, mensaje, resultado):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notificaciones (
            id UUID PRIMARY KEY,
            destinatario VARCHAR(255),
            canales TEXT,
            mensaje TEXT,
            resultado JSONB,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        INSERT INTO notificaciones (id, destinatario, canales, mensaje, resultado)
        VALUES (%s, %s, %s, %s, %s)
    """, (notificacion_id, destinatario, ','.join(canales), mensaje, json.dumps(resultado)))
    conn.commit()
    cursor.close()
    conn.close()

# Consumidor de mensajes asincrónicos de RabbitMQ
def consumir_mensajes():
    connection, channel = conectar_rabbitmq()
    if connection and channel:
        # Cambia auto_ack a False para confirmar manualmente
        channel.basic_consume(queue='notificaciones', on_message_callback=callback, auto_ack=False)
        print("Esperando mensajes de RabbitMQ...")
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            print("Consumo de mensajes interrumpido por el usuario.")
            channel.stop_consuming()
        finally:
            connection.close()

# Manejar notificación y registrar en la base de datos
def manejar_notificacion(destinatario, canales, mensaje):
    notificacion_id = str(uuid.uuid4())
    resultado = enviar_notificacion(destinatario, canales, mensaje)
    registrar_notificacion_bd(notificacion_id, destinatario, canales, mensaje, resultado)
    return notificacion_id

# Endpoint para crear una notificación
@app.route('/notificaciones', methods=['POST'])
def crear_notificacion():
    data = request.json
    destinatario = data['destinatario']
    canales = data['canales']
    mensaje = data['mensaje']
    modo = data.get('modo', 'async')

    if modo == 'sync':
        notificacion_id = manejar_notificacion(destinatario, canales, mensaje)
    else:
        connection, channel = conectar_rabbitmq()
        channel.basic_publish(
            exchange='',
            routing_key='notificaciones',
            body=json.dumps({"destinatario": destinatario, "canales": canales, "mensaje": mensaje})
        )
        connection.close()
        notificacion_id = "enviando en modo asíncrono"

    return jsonify({"status": "success", "notificacion_id": notificacion_id}), 200

# Endpoint para obtener todas las notificaciones registradas
@app.route('/notificaciones', methods=['GET'])
def obtener_notificaciones():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notificaciones")
    notificaciones = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(notificaciones), 200

# Endpoint para obtener detalles de una notificación específica
@app.route('/notificaciones/<notificacion_id>', methods=['GET'])
def obtener_notificacion(notificacion_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notificaciones WHERE id = %s", (notificacion_id,))
    notificacion = cursor.fetchone()
    cursor.close()
    conn.close()
    if notificacion:
        return jsonify(notificacion), 200
    return jsonify({"error": "Notificación no encontrada"}), 404


# Tiempo de inicio del servicio
start_time = datetime.now()
service_version = "1.0.0"

# Registrar los endpoints de salud
app.register_blueprint(health_bp)


if __name__ == "__main__":
    threading.Thread(target=consumir_mensajes).start()  # Iniciar consumidor de mensajes asincrónico
    app.run(host="0.0.0.0", port=5000)
