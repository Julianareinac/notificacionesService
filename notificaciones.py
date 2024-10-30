import pika
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client
from flask import Flask, jsonify, request
import threading
import uuid

app = Flask(__name__)

# Almacenamos las notificaciones en memoria para esta implementación
notificaciones = {}

# Configuración de RabbitMQ
def conectar_rabbitmq():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='notificaciones')
    return connection, channel

# Configuración para Twilio (reemplaza con tus credenciales)
TWILIO_ACCOUNT_SID = 'your_account_sid'
TWILIO_AUTH_TOKEN = 'your_auth_token'
TWILIO_PHONE_NUMBER = 'your_twilio_phone_number'
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Función para enviar E-Mail
def enviar_email(destinatario, mensaje):
    try:
        # Configura el servidor SMTP
        smtp_server = "smtp.example.com"  # Cambia esto por el servidor SMTP que uses
        smtp_port = 587
        smtp_user = "tu_correo@example.com"
        smtp_password = "tu_password"

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)

        # Crea y envía el mensaje de correo
        email_message = MIMEText(mensaje)
        email_message['Subject'] = 'Notificación'
        email_message['From'] = smtp_user
        email_message['To'] = destinatario

        server.sendmail(smtp_user, destinatario, email_message.as_string())
        server.quit()
        return "E-Mail enviado"
    except Exception as e:
        return f"Error enviando E-Mail: {e}"

# Función para enviar SMS
def enviar_sms(destinatario, mensaje):
    try:
        twilio_client.messages.create(
            body=mensaje,
            from_=TWILIO_PHONE_NUMBER,
            to=destinatario
        )
        return "SMS enviado"
    except Exception as e:
        return f"Error enviando SMS: {e}"

# Función para enviar WhatsApp
def enviar_whatsapp(destinatario, mensaje):
    try:
        twilio_client.messages.create(
            body=mensaje,
            from_='whatsapp:' + TWILIO_PHONE_NUMBER,
            to='whatsapp:' + destinatario
        )
        return "WhatsApp enviado"
    except Exception as e:
        return f"Error enviando WhatsApp: {e}"

# Función para enviar notificación en múltiples canales
def enviar_notificacion(destinatario, canales, mensaje):
    resultados = {}
    for canal in canales:
        if canal == "email":
            resultados["email"] = enviar_email(destinatario, mensaje)
        elif canal == "sms":
            resultados["sms"] = enviar_sms(destinatario, mensaje)
        elif canal == "whatsapp":
            resultados["whatsapp"] = enviar_whatsapp(destinatario, mensaje)
    return resultados

# Enviar notificación y registrar el estado
def manejar_notificacion(destinatario, canales, mensaje):
    notificacion_id = str(uuid.uuid4())
    resultado = enviar_notificacion(destinatario, canales, mensaje)
    notificacion = {
        "id": notificacion_id,
        "destinatario": destinatario,
        "canales": canales,
        "mensaje": mensaje,
        "resultado": resultado
    }
    notificaciones[notificacion_id] = notificacion
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
        threading.Thread(target=manejar_notificacion, args=(destinatario, canales, mensaje)).start()
        notificacion_id = "enviando en modo asíncrono"

    return jsonify({"status": "success", "notificacion_id": notificacion_id}), 200

# Endpoint para obtener todas las notificaciones registradas
@app.route('/notificaciones', methods=['GET'])
def obtener_notificaciones():
    return jsonify(list(notificaciones.values())), 200

# Endpoint para obtener detalles de una notificación específica
@app.route('/notificaciones/<notificacion_id>', methods=['GET'])
def obtener_notificacion(notificacion_id):
    notificacion = notificaciones.get(notificacion_id)
    if notificacion:
        return jsonify(notificacion), 200
    return jsonify({"error": "Notificación no encontrada"}), 404

if __name__ == "__main__":
    app.run(debug=True)
