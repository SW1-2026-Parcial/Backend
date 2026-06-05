import os
import numpy as np
import tensorflow as tf
from tensorflow.keras import Sequential # type: ignore
from tensorflow.keras.layers import Dense # type: ignore

# Directorio de salida para los modelos
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mira_models"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Iniciando generación de modelos de fachada MIRA en: {OUTPUT_DIR}")
print(f"Versión de TensorFlow: {tf.__version__}")

# ──────────────────────────────────────────────────────────────────────────────
# 1. MODELO DE PREDICCIÓN DE RUTAS (route_model)
# ──────────────────────────────────────────────────────────────────────────────
print("\n--- 1. Generando modelo de Predicción de Rutas ---")
# Input: ID de nodo actual (one-hot o embedding index, ej. 20 posibles nodos) + hora del día (0-23)
# Output: Probabilidad del siguiente nodo (ej. 20 posibles nodos de destino)
input_dim = 21  # 20 para nodos + 1 para hora del día
output_dim = 20

# Datos sintéticos
X_route = np.random.rand(1000, input_dim).astype(np.float32)
y_route = np.random.randint(0, output_dim, size=(1000,))
y_route_onehot = tf.keras.utils.to_categorical(y_route, num_classes=output_dim)

model_route = Sequential([
    Dense(32, activation='relu', input_shape=(input_dim,)),
    Dense(16, activation='relu'),
    Dense(output_dim, activation='softmax')
])

model_route.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
model_route.fit(X_route, y_route_onehot, epochs=5, batch_size=32, verbose=1)

route_model_path = os.path.join(OUTPUT_DIR, "route_model.h5")
model_route.save(route_model_path)
print(f"Modelo de rutas guardado en: {route_model_path}")


# ──────────────────────────────────────────────────────────────────────────────
# 2. MODELO DE ANÁLISIS DE RIESGO DE DEMORA (risk_model)
# ──────────────────────────────────────────────────────────────────────────────
print("\n--- 2. Generando modelo de Análisis de Riesgo ---")
# Input: [horas_activo, score_prioridad, total_tareas_departamento]
# Output: 4 clases de riesgo [BAJO, MEDIO, ALTO, CRITICO]
input_dim_risk = 3
output_dim_risk = 4

# Datos sintéticos
X_risk = np.random.rand(1000, input_dim_risk).astype(np.float32)
# Generar etiquetas con cierta lógica simple: si horas_activo (col 0) es alto, el riesgo es alto
y_risk = []
for row in X_risk:
    score = row[0] * 0.5 + row[1] * 0.3 + row[2] * 0.2
    if score > 0.75:
        y_risk.append(3)  # CRITICO
    elif score > 0.5:
        y_risk.append(2)  # ALTO
    elif score > 0.25:
        y_risk.append(1)  # MEDIO
    else:
        y_risk.append(0)  # BAJO
y_risk = np.array(y_risk)
y_risk_one_hot = tf.keras.utils.to_categorical(y_risk, num_classes=output_dim_risk)

model_risk = Sequential([
    Dense(16, activation='relu', input_shape=(input_dim_risk,)),
    Dense(8, activation='relu'),
    Dense(output_dim_risk, activation='softmax')
])

model_risk.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
model_risk.fit(X_risk, y_risk_one_hot, epochs=5, batch_size=32, verbose=1)

risk_model_path = os.path.join(OUTPUT_DIR, "risk_model.h5")
model_risk.save(risk_model_path)
print(f"Modelo de riesgo guardado en: {risk_model_path}")


# ──────────────────────────────────────────────────────────────────────────────
# 3. AUTOENCODER PARA DETECCIÓN DE ANOMALÍAS (anomaly_model)
# ──────────────────────────────────────────────────────────────────────────────
print("\n--- 3. Generando modelo de Detección de Anomalías (Autoencoder) ---")
# Input: tiempos transcurridos en los últimos 5 nodos del trámite
# Output: Reconstrucción de los mismos 5 valores (el error de reconstrucción indica anomalía)
input_dim_anomaly = 5

# Datos sintéticos (simulando patrones normales con poca varianza)
X_anomaly = np.random.normal(loc=1.0, scale=0.1, size=(1000, input_dim_anomaly)).astype(np.float32)

model_anomaly = Sequential([
    Dense(8, activation='relu', input_shape=(input_dim_anomaly,)),
    Dense(4, activation='relu'),  # Bottleneck (dimensión reducida)
    Dense(8, activation='relu'),
    Dense(input_dim_anomaly, activation='linear')
])

model_anomaly.compile(optimizer='adam', loss='mse')
model_anomaly.fit(X_anomaly, X_anomaly, epochs=5, batch_size=32, verbose=1)

anomaly_model_path = os.path.join(OUTPUT_DIR, "anomaly_model.h5")
model_anomaly.save(anomaly_model_path)
print(f"Modelo de anomalías guardado en: {anomaly_model_path}")

print("\n¡Todos los modelos de fachada de MIRA han sido generados exitosamente!")
