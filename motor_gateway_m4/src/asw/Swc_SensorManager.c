#include "Swc_SensorManager.h"
#include "Mcal_Dio.h"
#include "Rte.h"
#include <math.h>

static Sensor_DataType s_sensor_data;

void Swc_SensorManager_Init(void)
{
    s_sensor_data.accel_x_g = 0.0f;
    s_sensor_data.accel_y_g = 0.0f;
    s_sensor_data.accel_z_g = 1.0f;
    s_sensor_data.accel_mag_g = 1.0f;
    s_sensor_data.temperature_c = 0.0f;
    s_sensor_data.humidity_pct = 0.0f;
    s_sensor_data.pir_detected = FALSE;

    (void)Rte_Write_ppSensorData(&s_sensor_data);
}

void Runnable_SensorManager_100ms(void)
{
    /* 1. HC-SR501 PIR (PE13) */
    s_sensor_data.pir_detected = (Dio_ReadChannel(DIO_CH_PIR_PE13) == STD_HIGH) ? TRUE : FALSE;

    /* 2. GY-61 accelerometer (3 x ADC) -> resultant vibration magnitude |a| */
    float32 ax = 0.0f, ay = 0.0f, az = 1.0f;
    if (Rte_Call_rpAccel_Read(&ax, &ay, &az) == E_OK) {
        s_sensor_data.accel_x_g = ax;
        s_sensor_data.accel_y_g = ay;
        s_sensor_data.accel_z_g = az;
        s_sensor_data.accel_mag_g = sqrtf((ax * ax) + (ay * ay) + (az * az));
    }

    /* 3. DHT11 (sampled every 2 s by CDD_Dht11 thread; here we latch the latest valid value) */
    float32 t = 0.0f, h = 0.0f;
    if (Rte_Call_rpEnvSensor_Read(&t, &h) == E_OK) {
        s_sensor_data.temperature_c = t;
        s_sensor_data.humidity_pct = h;
    }

    (void)Rte_Write_ppSensorData(&s_sensor_data);
}

Std_ReturnType Swc_SensorManager_GetSensors(Sensor_DataType *data)
{
    if (data == NULL) {
        return E_NOT_OK;
    }
    *data = s_sensor_data;
    return E_OK;
}
