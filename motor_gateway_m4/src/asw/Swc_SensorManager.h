#ifndef SWC_SENSOR_MANAGER_H
#define SWC_SENSOR_MANAGER_H

#include "std_types.h"

/* Sensor Manager Lifecycle & Runnable APIs */
void Swc_SensorManager_Init(void);
void Runnable_SensorManager_100ms(void);

/* Sensor Data Getter */
Std_ReturnType Swc_SensorManager_GetSensors(Sensor_DataType *data);

#endif /* SWC_SENSOR_MANAGER_H */
