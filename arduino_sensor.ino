#include <DHT.h>

#define DHTPIN A0     // Digital pin connected to the DHT sensor
#define DHTTYPE DHT11   // DHT 11

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(9600);
  pinMode(8, OUTPUT);
  pinMode(9, OUTPUT);
  digitalWrite(8, LOW);
  digitalWrite(9, LOW);
  dht.begin();
}

unsigned long led_timer = 0;
bool led_active = false;

void loop() {
  // Non-blocking timer: Auto-off after 3 seconds
  if (led_active && (millis() - led_timer >= 3000)) {
    digitalWrite(8, LOW);
    digitalWrite(9, LOW);
    led_active = false;
  }

  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "dat") {
      float t = dht.readTemperature();
      if (isnan(t)) {
        Serial.println("Error: Failed to read from DHT sensor!");
        return;
      }
      Serial.println(t);
    } else if (command == "cmd_8") {
      digitalWrite(8, HIGH);
      digitalWrite(9, LOW);
      led_timer = millis();
      led_active = true;
      Serial.println("LED_8_ACTIVE_PULSE");
    } else if (command == "cmd_9") {
      digitalWrite(9, HIGH);
      digitalWrite(8, LOW);
      led_timer = millis();
      led_active = true;
      Serial.println("LED_9_ACTIVE_PULSE");
    } else {
      digitalWrite(8, LOW);
      digitalWrite(9, LOW);
      led_active = false;
      Serial.println("ALL_OFF");
    }
  }
}
