import pika
import smtplib
import psycopg2
import json
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
        host="localhost",
        database="notificaciones",
        user="postgres",
        password="Asdf1234"
    )

# Configuración de RabbitMQ
def conectar_rabbitmq():
    try:
        credentials = pika.PlainCredentials('user', 'password')  # Reemplaza con tus credenciales
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', 5672, '/', credentials))
        channel = connection.channel()
        channel.queue_declare(queue='notificaciones')  # Declara la cola si no existe
        return connection, channel
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Error al conectar a RabbitMQ: {e}")
        return None, None



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

    def callback(ch, method, properties, body):
        data = json.loads(body)
        destinatario = data['destinatario']
        canales = data['canales']
        mensaje = data['mensaje']
        manejar_notificacion(destinatario, canales, mensaje)

    channel.basic_consume(queue='notificaciones', on_message_callback=callback, auto_ack=True)
    print("Esperando mensajes de RabbitMQ...")
    channel.start_consuming()

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
    app.run()
