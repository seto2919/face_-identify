#include <Wire.h>
#include "MLX90640_API.h"
#include "MLX90640_I2C_Driver.h"
#define PIN 17
String str;

// 移除重複定義，只保留一個 mlx90640To 陣列
const byte sensor_address = 0x33; // Default 7-bit unshifted address of the MLX90640
#define TA_SHIFT 8 // Default shift for MLX90640 in open air

// 這裡定義一次陣列，並且確保其他地方不要重複定義
float mlx90640To[768]; 
paramsMLX90640 mlx90640;

void setup() {
  Wire.begin();
  Wire.setClock(800000); // Increase I2C clock speed to 400kHz

  Serial.begin(115200); // Fast serial as possible
  while (!Serial); // Wait for user to open terminal
  Serial.println("MLX90640 IR Array Example");

  if (isConnected() == false) {
    Serial.println("MLX90640 not detected at default I2C address. Please check wiring. Freezing.");
    while (1);
  }
  Serial.println("MLX90640 online!");

  // Get device parameters - We only have to do this once
  int status;
  uint16_t eeMLX90640[832];
  status = MLX90640_DumpEE(sensor_address, eeMLX90640);
  if (status != 0) {
    Serial.println("Failed to load system parameters");
  }

  status = MLX90640_ExtractParameters(eeMLX90640, &mlx90640);
  if (status != 0) {
    Serial.println("Parameter extraction failed");
  }

  // Set the refresh rate (4Hz in this example)
  MLX90640_SetRefreshRate(sensor_address, 0x03);

  // Additional setup (from the second program)
  MLX90640_I2CWrite(sensor_address, 0x800D, 6401);
  delay(4000);

  pinMode(PIN, OUTPUT);
}

void loop() {
  long startTime = millis();
  for (byte x = 0; x < 2; x++) {
    uint16_t mlx90640Frame[834];
    int status = MLX90640_GetFrameData(sensor_address, mlx90640Frame);

    if (status < 0) {
      Serial.print("GetFrame Error: ");
      Serial.println(status);
    }

    float vdd = MLX90640_GetVdd(mlx90640Frame, &mlx90640);
    float Ta = MLX90640_GetTa(mlx90640Frame, &mlx90640);

    float tr = Ta - TA_SHIFT; // Reflected temperature based on the sensor ambient temperature
    float emissivity = 0.95;

    MLX90640_CalculateTo(mlx90640Frame, &mlx90640, emissivity, tr, mlx90640To);
  }
  long stopTime = millis();

  for (int x = 0; x < 768; x++) {
    Serial.print(mlx90640To[x], 2);
    Serial.print(",");
  }
  Serial.println("");
  delay(1000); // Optional delay between reads

  if (Serial.available()) {
    // 讀取傳入的字串直到"\n"結尾
    str = Serial.readStringUntil('\n');

    if (str == "relay_ON") {           // 若字串值是 "LED_ON" 開燈
        digitalWrite(PIN, HIGH);     // 開燈
        Serial.println("relay is ON"); // 回應訊息給電腦
    } else if (str == "relay_OFF") {
        digitalWrite(PIN, LOW);
        Serial.println("relay is OFF");
    }
  }
}

// Returns true if the MLX90640 is detected on the I2C bus
boolean isConnected() {
  Wire.beginTransmission((uint8_t)sensor_address);
  if (Wire.endTransmission() != 0) {
    return (false); // Sensor did not ACK
  }
  return (true);
}
