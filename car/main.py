import json
import paho.mqtt.client as mqtt
from vehicle import Car
from ambulance_status import AmbulanceStatus
from utils import load_my_coords
import subprocess
from avoid_logic import decide_avoid_dir
from config import Config
from avoidance.lcd_display import LcdDisplay
import time

subprocess.run(["python", "save_route_points.py"])
lcd = LcdDisplay(vehicle_name="11ga 1111")

MQTT_BROKER = Config.MQTT_BROKER
MQTT_PORT = Config.MQTT_PORT
# MQTT_TOPIC = "ambulance/vehicles"
# MQTT_TOPIC = "ambulance/feedback"
# 방향 숫자 → 문자열 매핑
last_calc_time = 0

car_coords = load_my_coords()
ambu = AmbulanceStatus()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ MQTT 연결 성공")
        client.subscribe("ambulance/vehicles")
        
    else:
        print("❌ 연결 실패:", rc)

def on_message(client, userdata, msg):
    # payload = json.loads(msg.payload.decode())
    global last_calc_time
    now = time.time()
    raw_payload = msg.payload.decode()

    # 🚑 구급차 위치 메시지
    if msg.topic == "ambulance/vehicles":
        try:
            payload = json.loads(raw_payload)  # dict 기대
            ambu.update(payload)
        except Exception as e:
            print(f"[WARN] ambulance/vehicles 처리 실패 → {e}")

        # ✅ 2초마다 계산하도록 제한
        if now - last_calc_time >= 2.0:
            last_calc_time = now
            if car.index < len(car.coords):
                my_pos = car.coords[car.index]
                my_next = car.coords[car.index+1] if car.index+1 < len(car.coords) else None
                eta, dist, same_road_and_dir, is_nearby = ambu.calculate_status(my_pos, my_next)
                print(f"on_message | eta : {eta}, same_road_and_dir : {same_road_and_dir}")
                car.send_feedback(my_pos, same_road_and_dir)

                # 현재 차선은 car 객체에 저장된 값 사용
                current_lane = car.car_lane
                total_lanes = car.total_lanes
                avoid_dir, ambulance_lane = decide_avoid_dir(current_lane, total_lanes)

                if same_road_and_dir and eta:
                    lcd.update_eta(int(eta/60), state="approaching")  # ETA 있을 때

                elif is_nearby:
                    lcd.update_eta(None, state="nearby")              # 근처에만 있을 때

                else: #경로도 다르고 주변도 아님
                    lcd.update_eta(None, state="idle")                # 아무것도 없을 때

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)

car = Car(client, car_coords)
car.start()

client.loop_forever()
